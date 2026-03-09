#!/usr/bin/env python3
"""
Seed the OpenNutri reference model from USDA SR Legacy CSV files.

Targets the annotator app schema:
- entities
- entity_aliases
- master_nutrients
- sources
- claims

Usage:
  python3 etl_sr_legacy_to_opennutri.py --dry-run
  SUPABASE_SERVICE_ROLE_KEY=... python3 etl_sr_legacy_to_opennutri.py --reset
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import uuid
from pathlib import Path

import requests
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
CSV_DIR = ROOT / "FoodData_Central_sr_legacy_food_csv_2018-04"
ENV_PATH = ROOT / "apps" / "expert-annotator" / ".env"
UUID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "opennutri/usda-sr-legacy")


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                values[key] = value
    return values


ENV = load_env()
SUPABASE_URL = ENV.get("VITE_SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_RESOLVE_IP = os.environ.get("SUPABASE_RESOLVE_IP", "")


def read_csv(filename: str) -> list[dict[str, str]]:
    with (CSV_DIR / filename).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def stable_uuid(*parts: str) -> str:
    return str(uuid.uuid5(UUID_NAMESPACE, "::".join(parts)))


def batched(rows: list[dict], size: int = 500):
    for idx in range(0, len(rows), size):
        yield rows[idx : idx + size]


def rest_request(method: str, path: str, *, headers: dict[str, str], **kwargs):
    if SUPABASE_RESOLVE_IP:
        payload_file = None
        cmd = [
            "curl",
            "-sS",
            "--resolve",
            f"{SUPABASE_URL.removeprefix('https://')}:443:{SUPABASE_RESOLVE_IP}",
            "-X",
            method,
            "-D",
            "-",
        ]
        for key, value in headers.items():
            cmd.extend(["-H", f"{key}: {value}"])
        json_payload = kwargs.pop("json", None)
        if json_payload is not None:
            handle = tempfile.NamedTemporaryFile("w", delete=False, suffix=".json")
            json.dump(json_payload, handle)
            handle.close()
            payload_file = handle.name
            cmd.extend(["--data-binary", f"@{payload_file}"])
        cmd.append(f"{SUPABASE_URL}/rest/v1/{path}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if payload_file:
            Path(payload_file).unlink(missing_ok=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr[:400] or f"curl exited with {result.returncode}")
        _, _, body = result.stdout.partition("\r\n\r\n")
        if not body:
            _, _, body = result.stdout.partition("\n\n")
        if " 4" in result.stdout.splitlines()[0] or " 5" in result.stdout.splitlines()[0]:
            raise RuntimeError(result.stdout[:400])
        class Response:
            status_code = 200
            text = body
        return Response()

    response = requests.request(method, f"{SUPABASE_URL}/rest/v1/{path}", headers=headers, timeout=60, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} failed with {response.status_code}: {response.text[:400]}")
    return response


def reset_remote_tables(headers: dict[str, str]) -> None:
    # Reverse dependency order.
    for table in ["claims", "entity_aliases", "sources", "master_nutrients", "entities"]:
        rest_request("DELETE", f"{table}?id=not.is.null", headers=headers)
        print(f"  Cleared {table}")


def build_payload() -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    sr_legacy_foods = read_csv("sr_legacy_food.csv")
    legacy_fdc_ids = {row["fdc_id"] for row in sr_legacy_foods}
    ndb_lookup = {row["fdc_id"]: row["NDB_number"] for row in sr_legacy_foods}

    food_rows = read_csv("food.csv")
    category_rows = read_csv("food_category.csv")
    nutrient_rows = read_csv("nutrient.csv")

    categories = {row["id"]: row["description"] for row in category_rows}
    foods = {
        row["fdc_id"]: row
        for row in food_rows
        if row["fdc_id"] in legacy_fdc_ids and row["data_type"] == "sr_legacy_food"
    }

    source_id = stable_uuid("source", "usda_sr_legacy", "2018-04")
    sources = [
        {
            "id": source_id,
            "source_type": "EXTERNAL_DB",
            "source_name": "USDA FoodData Central (SR Legacy)",
            "reference_uri": "https://fdc.nal.usda.gov/",
            "source_metadata": {
                "dataset": "sr_legacy_food",
                "version": "2018-04",
                "csv_dir": CSV_DIR.name,
            },
        }
    ]

    entities: list[dict] = []
    aliases: list[dict] = []
    entity_id_map: dict[str, str] = {}
    for fdc_id, row in foods.items():
        entity_id = stable_uuid("entity", fdc_id)
        entity_id_map[fdc_id] = entity_id
        entities.append(
            {
                "id": entity_id,
                "canonical_name": row["description"],
                "category": categories.get(row["food_category_id"]),
            }
        )

        ndb_number = ndb_lookup.get(fdc_id)
        if ndb_number:
            aliases.append(
                {
                    "id": stable_uuid("alias", fdc_id, ndb_number),
                    "entity_id": entity_id,
                    "alias_name": ndb_number,
                    "origin": "usda_ndb_number",
                }
            )

    used_nutrient_ids: set[str] = set()
    food_nutrients: list[dict[str, str]] = []
    with (CSV_DIR / "food_nutrient.csv").open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row["fdc_id"] not in entity_id_map:
                continue
            food_nutrients.append(row)
            used_nutrient_ids.add(row["nutrient_id"])

    nutrient_id_map: dict[str, str] = {}
    nutrient_unit_map: dict[str, str] = {}
    nutrient_name_map: dict[str, str] = {}
    master_nutrients: list[dict] = []
    for row in nutrient_rows:
        nutrient_id = row["id"]
        if nutrient_id not in used_nutrient_ids:
            continue
        nutrient_unit_map[nutrient_id] = row["unit_name"].lower()
        nutrient_name = row["name"]
        master_id = nutrient_name_map.get(nutrient_name)
        if not master_id:
            master_id = stable_uuid("nutrient", nutrient_name)
            nutrient_name_map[nutrient_name] = master_id
            master_nutrients.append(
                {
                    "id": master_id,
                    "standard_name": nutrient_name,
                    "description": f"Unit: {row['unit_name']}. USDA nutrient_nbr: {row['nutrient_nbr']}",
                }
            )
        nutrient_id_map[nutrient_id] = master_id

    claims: list[dict] = []
    for row in food_nutrients:
        entity_id = entity_id_map.get(row["fdc_id"])
        nutrient_id = nutrient_id_map.get(row["nutrient_id"])
        if not entity_id or not nutrient_id:
            continue

        try:
            amount = float(row["amount"])
        except (TypeError, ValueError):
            continue

        sample_size = None
        if row.get("data_points"):
            try:
                sample_size = int(row["data_points"])
            except ValueError:
                sample_size = None

        metadata = {
            "usda_fdc_id": row["fdc_id"],
            "usda_nutrient_id": row["nutrient_id"],
        }
        for key in ("min", "max", "median", "min_year_acquired"):
            if row.get(key):
                metadata[key] = row[key]

        claims.append(
            {
                "id": stable_uuid("claim", row["fdc_id"], row["nutrient_id"]),
                "entity_id": entity_id,
                "nutrient_id": nutrient_id,
                "source_id": source_id,
                "amount": amount,
                "unit": nutrient_unit_map[row["nutrient_id"]],
                "basis": "per_100g",
                "preparation_state": "unspecified",
                "sample_size": sample_size,
                "confidence": 1.0,
                "extraction_method": "ground_truth",
                "status": "active",
                "metadata": metadata,
            }
        )

    return entities, aliases, master_nutrients, sources, claims


def upload_dataset(
    headers: dict[str, str],
    payload: tuple[list[dict], list[dict], list[dict], list[dict], list[dict]],
    *,
    claims_offset: int = 0,
    claims_only: bool = False,
) -> None:
    entities, aliases, nutrients, sources, claims = payload

    tables = [
        ("sources", sources, "id"),
        ("entities", entities, "canonical_name"),
        ("entity_aliases", aliases, None),
        ("master_nutrients", nutrients, "standard_name"),
        ("claims", claims, "id"),
    ]

    if claims_only:
        tables = [("claims", claims, "id")]

    for table, rows, conflict in tables:
        if table == "claims" and claims_offset:
            rows = rows[claims_offset:]
        if not rows:
            print(f"  Skipped {table} (no rows)")
            continue

        for batch in batched(rows):
            path = table if not conflict else f"{table}?on_conflict={conflict}"
            rest_request(
                "POST",
                path,
                headers={
                    **headers,
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates,return=minimal",
                },
                json=batch,
            )
        print(f"  Uploaded {len(rows)} rows into {table}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed OpenNutri from USDA SR Legacy")
    parser.add_argument("--dry-run", action="store_true", help="Parse data and print counts without writing")
    parser.add_argument("--reset", action="store_true", help="Delete existing reference data before upload")
    parser.add_argument("--claims-offset", type=int, default=0, help="Resume claims upload from this 0-based row offset")
    parser.add_argument("--claims-only", action="store_true", help="Upload only claims, assuming reference tables are already loaded")
    args = parser.parse_args()

    if not SUPABASE_URL:
        raise SystemExit("Missing VITE_SUPABASE_URL in apps/expert-annotator/.env")

    payload = build_payload()
    entities, aliases, nutrients, sources, claims = payload

    print(json.dumps(
        {
            "entities": len(entities),
            "entity_aliases": len(aliases),
            "master_nutrients": len(nutrients),
            "sources": len(sources),
            "claims": len(claims),
        },
        indent=2,
    ))

    if args.dry_run:
        return 0

    if not SUPABASE_SERVICE_ROLE_KEY:
        raise SystemExit("Missing SUPABASE_SERVICE_ROLE_KEY in environment; refusing to write with anon credentials.")

    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    }

    if args.reset:
        print("Resetting existing reference data...")
        reset_remote_tables(headers)

    print("Uploading SR Legacy reference data...")
    upload_dataset(headers, payload, claims_offset=args.claims_offset, claims_only=args.claims_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
