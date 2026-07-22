"""Build a deterministic OpenNutri Core release from USDA FNDDS CSV files."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
import sqlite3
import tempfile
import unicodedata
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError as exc:  # pragma: no cover - exercised by dependency installation
    raise RuntimeError(
        "OpenNutri Core release builds require pyarrow. Install services/data-pipeline/requirements.txt."
    ) from exc


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "FoodData_Central_survey_food_csv_2024-10-31"
FNDDS_ARTIFACT_VERSION = "0.0.1"
FNDDS_RELEASE_ID = "usda-fndds-2021-2023"
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "services"
    / "data-pipeline"
    / "data"
    / "core"
    / "releases"
    / f"opennutri-core-fndds-2021-2023-v{FNDDS_ARTIFACT_VERSION}"
)

FNDDS_DOWNLOAD_URL = (
    "https://fdc.nal.usda.gov/fdc-datasets/"
    "FoodData_Central_survey_food_csv_2024-10-31.zip"
)
FNDDS_ARCHIVE_SHA256 = "5ccc25ec2777a8982fbb61378a42f415316173eb11e48c9a8ba4cb19f5a4f29c"
FNDDS_SOURCE_TREE_SHA256 = "a6175e71af7fbd1fa78c73bd08c7a82324982866267678b47c98b29392b4e199"
FNDDS_RELEASE_DATE = "2024-10-31"
FNDDS_COVERAGE_START = "2021-01-01"
FNDDS_COVERAGE_END = "2023-12-31"
USDA_LICENSE = "CC0-1.0"
USDA_LICENSE_URL = "https://creativecommons.org/publicdomain/zero/1.0/"

REQUIRED_SOURCE_COLUMNS = {
    "food.csv": {"fdc_id", "data_type", "description", "food_category_id", "publication_date"},
    "survey_fndds_food.csv": {
        "fdc_id",
        "food_code",
        "wweia_category_number",
        "start_date",
        "end_date",
    },
    "nutrient.csv": {"id", "name", "unit_name", "nutrient_nbr", "rank"},
    "food_nutrient.csv": {
        "id",
        "fdc_id",
        "nutrient_id",
        "amount",
        "data_points",
        "derivation_id",
        "min",
        "max",
        "median",
        "footnote",
        "min_year_acquired",
    },
    "food_portion.csv": {
        "id",
        "fdc_id",
        "seq_num",
        "amount",
        "measure_unit_id",
        "portion_description",
        "modifier",
        "gram_weight",
        "data_points",
        "footnote",
        "min_year_acquired",
    },
    "measure_unit.csv": {"id", "name"},
    "wweia_food_category.csv": {"wweia_food_category", "wweia_food_category_description"},
}

EXPECTED_OFFICIAL_COUNTS = {
    "source_foods": 5432,
    "source_nutrient_rows": 353015,
    "used_nutrients": 65,
    "source_portion_rows": 22046,
    "accepted_portions": 22045,
    "rejected_portions": 1,
    "searchable_foods": 5431,
    "complete_foods": 4923,
    "ambiguous_foods": 508,
    "partial_foods": 0,
    "excluded_foods": 1,
}

CORE_SOURCE_NUTRIENT_CODES = frozenset({"203", "204", "205", "208"})
ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://opennutri.org/core/v1")
NFS_RE = re.compile(r"\bNFS\b", re.IGNORECASE)
NS_RE = re.compile(r"\bNS\b|not specified", re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")
NON_WORD_RE = re.compile(r"[^\w]+", re.UNICODE)


class DatasetValidationError(RuntimeError):
    """Raised when source data cannot produce a trustworthy release."""


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[str, ...]
    arrow_schema: pa.Schema


@dataclass
class SourceAudit:
    member_rows: list[dict[str, str]]
    foods_by_fdc_id: dict[str, dict[str, str]]
    categories_by_number: dict[str, str]
    nutrient_by_number: dict[str, dict[str, str]]
    used_nutrient_numbers: set[str]
    nutrient_numbers_by_food: dict[str, set[str]]
    accepted_portions: list[dict[str, Any]]
    portion_count_by_food: Counter[str]
    source_nutrient_rows: int
    source_portion_rows: int
    rejected_portion_count: int
    invalid_portion_examples: list[dict[str, str]]
    source_file_manifest: list[dict[str, Any]]
    source_tree_sha256: str


def _stable_uuid(kind: str, *parts: str) -> str:
    value = "|".join((kind, *parts))
    return str(uuid.uuid5(ID_NAMESPACE, value))


def _food_id(source_fdc_id: str) -> str:
    return _stable_uuid("food", FNDDS_RELEASE_ID, source_fdc_id)


def _nutrient_id(usda_nutrient_id: str) -> str:
    return _stable_uuid("nutrient", "usda-fdc", usda_nutrient_id)


def _category_id(category_number: str) -> str:
    return _stable_uuid("category", "usda-wweia", category_number)


def _portion_id(source_portion_id: str) -> str:
    return _stable_uuid("portion", FNDDS_RELEASE_ID, source_portion_id)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_file_manifest(source_dir: Path) -> tuple[list[dict[str, Any]], str]:
    manifest: list[dict[str, Any]] = []
    tree_digest = hashlib.sha256()
    for path in sorted(item for item in source_dir.iterdir() if item.is_file()):
        file_hash = _hash_file(path)
        row = {"name": path.name, "bytes": path.stat().st_size, "sha256": file_hash}
        manifest.append(row)
        tree_digest.update(path.name.encode("utf-8"))
        tree_digest.update(b"\0")
        tree_digest.update(file_hash.encode("ascii"))
        tree_digest.update(b"\0")
    return manifest, tree_digest.hexdigest()


def _csv_rows(path: Path, required_columns: set[str]) -> Iterator[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = required_columns - columns
        if missing:
            raise DatasetValidationError(f"{path.name} is missing columns: {sorted(missing)}")
        yield from reader


def _load_rows(source_dir: Path, filename: str) -> list[dict[str, str]]:
    return list(_csv_rows(source_dir / filename, REQUIRED_SOURCE_COLUMNS[filename]))


def _unique_by(rows: Sequence[dict[str, str]], key: str, label: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    duplicates: list[str] = []
    for row in rows:
        value = row.get(key, "")
        if not value:
            raise DatasetValidationError(f"{label} contains a blank {key}")
        if value in result:
            duplicates.append(value)
        result[value] = row
    if duplicates:
        raise DatasetValidationError(f"{label} contains duplicate {key} values: {duplicates[:10]}")
    return result


def _parse_float(value: str, *, field: str, row_label: str, optional: bool = False) -> float | None:
    text = (value or "").strip()
    if not text and optional:
        return None
    try:
        parsed = float(text)
    except ValueError as exc:
        raise DatasetValidationError(f"Invalid {field} for {row_label}: {value!r}") from exc
    if not math.isfinite(parsed):
        raise DatasetValidationError(f"Non-finite {field} for {row_label}: {value!r}")
    return parsed


def _parse_int(value: str, *, field: str, row_label: str, optional: bool = False) -> int | None:
    text = (value or "").strip()
    if not text and optional:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise DatasetValidationError(f"Invalid {field} for {row_label}: {value!r}") from exc


def _canonical_unit(source_unit: str) -> str:
    units = {
        "G": "g",
        "MG": "mg",
        "UG": "ug",
        "KCAL": "kcal",
        "KJ": "kJ",
        "IU": "IU",
    }
    key = source_unit.strip().upper()
    if key not in units:
        raise DatasetValidationError(f"Unsupported USDA nutrient unit: {source_unit!r}")
    return units[key]


def _normalized_description(value: str) -> str:
    return WHITESPACE_RE.sub(" ", unicodedata.normalize("NFKC", value).casefold()).strip()


def _search_text(*values: str) -> str:
    joined = " ".join(value for value in values if value)
    normalized = unicodedata.normalize("NFKC", joined).casefold()
    return WHITESPACE_RE.sub(" ", NON_WORD_RE.sub(" ", normalized)).strip()


def _ambiguity_flags(description: str) -> list[str]:
    flags: list[str] = []
    if NFS_RE.search(description):
        flags.append("not_further_specified")
    if NS_RE.search(description):
        flags.append("not_specified")
    return flags


def _build_source_audit(source_dir: Path) -> SourceAudit:
    if not source_dir.is_dir():
        raise DatasetValidationError(f"FNDDS source directory does not exist: {source_dir}")
    for filename in REQUIRED_SOURCE_COLUMNS:
        if not (source_dir / filename).is_file():
            raise DatasetValidationError(f"Missing required FNDDS source file: {filename}")

    member_rows = _load_rows(source_dir, "survey_fndds_food.csv")
    members_by_fdc_id = _unique_by(member_rows, "fdc_id", "survey_fndds_food.csv")

    all_food_rows = _load_rows(source_dir, "food.csv")
    all_foods_by_fdc_id = _unique_by(all_food_rows, "fdc_id", "food.csv")
    foods_by_fdc_id: dict[str, dict[str, str]] = {}
    for fdc_id in members_by_fdc_id:
        row = all_foods_by_fdc_id.get(fdc_id)
        if row is None:
            raise DatasetValidationError(f"FNDDS member {fdc_id} is missing from food.csv")
        if row["data_type"] != "survey_fndds_food":
            raise DatasetValidationError(
                f"FNDDS member {fdc_id} has unexpected data_type {row['data_type']!r}"
            )
        foods_by_fdc_id[fdc_id] = row

    category_rows = _load_rows(source_dir, "wweia_food_category.csv")
    categories_by_number = {
        row["wweia_food_category"]: row["wweia_food_category_description"]
        for row in category_rows
    }
    if len(categories_by_number) != len(category_rows):
        raise DatasetValidationError("wweia_food_category.csv contains duplicate category numbers")

    nutrient_rows = _load_rows(source_dir, "nutrient.csv")
    nutrient_by_number: dict[str, dict[str, str]] = {}
    for row in nutrient_rows:
        nutrient_number = row["nutrient_nbr"].strip()
        if not nutrient_number:
            continue
        if nutrient_number in nutrient_by_number:
            raise DatasetValidationError(
                f"nutrient.csv contains duplicate nutrient_nbr {nutrient_number}"
            )
        nutrient_by_number[nutrient_number] = row

    nutrient_numbers_by_food: dict[str, set[str]] = defaultdict(set)
    used_nutrient_numbers: set[str] = set()
    seen_food_nutrient_pairs: set[tuple[str, str]] = set()
    seen_food_nutrient_ids: set[str] = set()
    source_nutrient_rows = 0
    for row in _csv_rows(
        source_dir / "food_nutrient.csv",
        REQUIRED_SOURCE_COLUMNS["food_nutrient.csv"],
    ):
        source_nutrient_rows += 1
        source_row_id = row["id"]
        fdc_id = row["fdc_id"]
        source_nutrient_code = row["nutrient_id"].strip()
        row_label = f"food_nutrient {source_row_id or source_nutrient_rows}"
        if not source_row_id or source_row_id in seen_food_nutrient_ids:
            raise DatasetValidationError(
                f"Blank or duplicate food_nutrient source row ID: {source_row_id!r}"
            )
        seen_food_nutrient_ids.add(source_row_id)
        if fdc_id not in members_by_fdc_id:
            raise DatasetValidationError(f"{row_label} references unknown FNDDS food {fdc_id}")
        if source_nutrient_code not in nutrient_by_number:
            raise DatasetValidationError(
                f"{row_label} nutrient_id {source_nutrient_code!r} does not map through nutrient_nbr"
            )
        pair = (fdc_id, source_nutrient_code)
        if pair in seen_food_nutrient_pairs:
            raise DatasetValidationError(f"Duplicate FNDDS food/nutrient pair: {pair}")
        seen_food_nutrient_pairs.add(pair)
        amount = _parse_float(row["amount"], field="amount", row_label=row_label)
        if amount is None or amount < 0:
            raise DatasetValidationError(f"Negative or blank nutrient amount for {row_label}")
        nutrient_numbers_by_food[fdc_id].add(source_nutrient_code)
        used_nutrient_numbers.add(source_nutrient_code)

    measure_rows = _load_rows(source_dir, "measure_unit.csv")
    measures_by_id = _unique_by(measure_rows, "id", "measure_unit.csv")
    portion_count_by_food: Counter[str] = Counter()
    accepted_portions: list[dict[str, Any]] = []
    invalid_portion_examples: list[dict[str, str]] = []
    seen_portion_ids: set[str] = set()
    source_portion_rows = 0
    rejected_portion_count = 0
    for row in _csv_rows(
        source_dir / "food_portion.csv",
        REQUIRED_SOURCE_COLUMNS["food_portion.csv"],
    ):
        source_portion_rows += 1
        source_portion_id = row["id"]
        fdc_id = row["fdc_id"]
        row_label = f"food_portion {source_portion_id}"
        if not source_portion_id or source_portion_id in seen_portion_ids:
            raise DatasetValidationError(f"Blank or duplicate source portion ID: {source_portion_id!r}")
        seen_portion_ids.add(source_portion_id)
        if fdc_id not in members_by_fdc_id:
            raise DatasetValidationError(f"{row_label} references unknown FNDDS food {fdc_id}")
        measure = measures_by_id.get(row["measure_unit_id"])
        if measure is None:
            raise DatasetValidationError(
                f"{row_label} references unknown measure unit {row['measure_unit_id']!r}"
            )
        gram_weight = _parse_float(
            row["gram_weight"], field="gram_weight", row_label=row_label, optional=True
        )
        if gram_weight is None or gram_weight <= 0:
            rejected_portion_count += 1
            if len(invalid_portion_examples) < 20:
                invalid_portion_examples.append(
                    {
                        "source_portion_id": source_portion_id,
                        "source_food_id": fdc_id,
                        "portion_description": row["portion_description"],
                        "gram_weight": row["gram_weight"],
                        "reason": "non_positive_gram_weight",
                    }
                )
            continue
        accepted_portions.append(
            {
                "portion_id": _portion_id(source_portion_id),
                "food_id": _food_id(fdc_id),
                "source_portion_id": source_portion_id,
                "sequence_number": _parse_int(
                    row["seq_num"], field="seq_num", row_label=row_label, optional=True
                ),
                "amount": _parse_float(
                    row["amount"], field="amount", row_label=row_label, optional=True
                ),
                "measure_unit_id": row["measure_unit_id"],
                "measure_unit_name": measure["name"],
                "portion_description": row["portion_description"],
                "modifier": row["modifier"],
                "gram_weight": gram_weight,
                "data_points": _parse_int(
                    row["data_points"], field="data_points", row_label=row_label, optional=True
                ),
                "footnote": row["footnote"] or None,
                "min_year_acquired": row["min_year_acquired"] or None,
            }
        )
        portion_count_by_food[fdc_id] += 1

    source_file_manifest, source_tree_sha256 = _source_file_manifest(source_dir)
    return SourceAudit(
        member_rows=member_rows,
        foods_by_fdc_id=foods_by_fdc_id,
        categories_by_number=categories_by_number,
        nutrient_by_number=nutrient_by_number,
        used_nutrient_numbers=used_nutrient_numbers,
        nutrient_numbers_by_food=nutrient_numbers_by_food,
        accepted_portions=accepted_portions,
        portion_count_by_food=portion_count_by_food,
        source_nutrient_rows=source_nutrient_rows,
        source_portion_rows=source_portion_rows,
        rejected_portion_count=rejected_portion_count,
        invalid_portion_examples=invalid_portion_examples,
        source_file_manifest=source_file_manifest,
        source_tree_sha256=source_tree_sha256,
    )


def _release_rows(audit: SourceAudit) -> Iterator[dict[str, Any]]:
    yield {
        "release_id": FNDDS_RELEASE_ID,
        "artifact_version": FNDDS_ARTIFACT_VERSION,
        "publisher": "USDA Agricultural Research Service",
        "dataset_name": "Food and Nutrient Database for Dietary Studies 2021-2023",
        "data_type": "survey_fndds_food",
        "release_date": FNDDS_RELEASE_DATE,
        "coverage_start": FNDDS_COVERAGE_START,
        "coverage_end": FNDDS_COVERAGE_END,
        "download_url": FNDDS_DOWNLOAD_URL,
        "archive_sha256": FNDDS_ARCHIVE_SHA256,
        "source_tree_sha256": audit.source_tree_sha256,
        "license": USDA_LICENSE,
        "license_url": USDA_LICENSE_URL,
    }


def _category_rows(audit: SourceAudit) -> Iterator[dict[str, Any]]:
    for category_number in sorted(audit.categories_by_number, key=lambda value: int(value)):
        yield {
            "category_id": _category_id(category_number),
            "source": "usda-wweia",
            "source_category_number": category_number,
            "name": audit.categories_by_number[category_number],
        }


def _food_rows(audit: SourceAudit) -> Iterator[dict[str, Any]]:
    member_by_fdc_id = {row["fdc_id"]: row for row in audit.member_rows}
    for fdc_id in sorted(member_by_fdc_id, key=int):
        member = member_by_fdc_id[fdc_id]
        food = audit.foods_by_fdc_id[fdc_id]
        category_number = member["wweia_category_number"] or food["food_category_id"]
        category_name = audit.categories_by_number.get(category_number)
        if not category_name:
            raise DatasetValidationError(
                f"FNDDS food {fdc_id} references unknown WWEIA category {category_number!r}"
            )
        nutrient_numbers = audit.nutrient_numbers_by_food.get(fdc_id, set())
        has_core = CORE_SOURCE_NUTRIENT_CODES <= nutrient_numbers
        flags = _ambiguity_flags(food["description"])
        if not nutrient_numbers:
            quality_status = "excluded"
            exclusion_reason = "missing_nutrient_profile"
        elif not has_core:
            quality_status = "partial"
            exclusion_reason = "missing_core_nutrients"
        elif flags:
            quality_status = "ambiguous"
            exclusion_reason = None
        else:
            quality_status = "complete"
            exclusion_reason = None
        is_searchable = has_core
        search_priority = 0
        if is_searchable:
            search_priority = 100 + (10 if audit.portion_count_by_food[fdc_id] else 0)
            if flags:
                search_priority -= 30

        yield {
            "food_id": _food_id(fdc_id),
            "release_id": FNDDS_RELEASE_ID,
            "source": "usda-fdc",
            "data_type": food["data_type"],
            "source_food_id": fdc_id,
            "source_food_code": member["food_code"],
            "original_description": food["description"],
            "normalized_description": _normalized_description(food["description"]),
            "display_name": food["description"],
            "category_id": _category_id(category_number),
            "category_name": category_name,
            "publication_date": food["publication_date"],
            "coverage_start": member["start_date"],
            "coverage_end": member["end_date"],
            "quality_status": quality_status,
            "is_searchable": is_searchable,
            "exclusion_reason": exclusion_reason,
            "ambiguity_flags": json.dumps(flags, separators=(",", ":")),
            "nutrient_count": len(nutrient_numbers),
            "portion_count": audit.portion_count_by_food[fdc_id],
            "search_priority": search_priority,
            "search_text": _search_text(food["description"], category_name),
        }


def _used_nutrient_definitions(audit: SourceAudit) -> list[dict[str, str]]:
    rows = [audit.nutrient_by_number[number] for number in audit.used_nutrient_numbers]

    def sort_key(row: dict[str, str]) -> tuple[float, int]:
        rank = _parse_float(row["rank"], field="rank", row_label=f"nutrient {row['id']}", optional=True)
        return (rank if rank is not None else math.inf, int(row["id"]))

    return sorted(rows, key=sort_key)


def _nutrient_rows(audit: SourceAudit) -> Iterator[dict[str, Any]]:
    for row in _used_nutrient_definitions(audit):
        yield {
            "nutrient_id": _nutrient_id(row["id"]),
            "source": "usda-fdc",
            "source_nutrient_id": row["id"],
            "nutrient_number": row["nutrient_nbr"],
            "name": row["name"],
            "unit": _canonical_unit(row["unit_name"]),
            "source_unit": row["unit_name"],
            "sort_rank": _parse_float(
                row["rank"], field="rank", row_label=f"nutrient {row['id']}", optional=True
            ),
            "is_archived": "DO NOT USE - Archived" in row["name"],
        }


def _source_nutrient_mapping_rows(audit: SourceAudit) -> Iterator[dict[str, Any]]:
    for row in _used_nutrient_definitions(audit):
        yield {
            "release_id": FNDDS_RELEASE_ID,
            "source_nutrient_code": row["nutrient_nbr"],
            "source_code_field": "food_nutrient.nutrient_id",
            "mapped_via_field": "nutrient.nutrient_nbr",
            "nutrient_id": _nutrient_id(row["id"]),
            "source_nutrient_id": row["id"],
        }


def _food_nutrient_rows(source_dir: Path, audit: SourceAudit) -> Iterator[dict[str, Any]]:
    for row in _csv_rows(
        source_dir / "food_nutrient.csv",
        REQUIRED_SOURCE_COLUMNS["food_nutrient.csv"],
    ):
        nutrient = audit.nutrient_by_number[row["nutrient_id"]]
        row_label = f"food_nutrient {row['id']}"
        yield {
            "food_id": _food_id(row["fdc_id"]),
            "nutrient_id": _nutrient_id(nutrient["id"]),
            "amount": _parse_float(row["amount"], field="amount", row_label=row_label),
            "unit": _canonical_unit(nutrient["unit_name"]),
            "basis": "per_100g_edible_portion",
            "source_row_id": row["id"],
            "source_nutrient_code": row["nutrient_id"],
            "derivation_id": row["derivation_id"] or None,
            "data_points": _parse_int(
                row["data_points"], field="data_points", row_label=row_label, optional=True
            ),
            "minimum": _parse_float(row["min"], field="min", row_label=row_label, optional=True),
            "maximum": _parse_float(row["max"], field="max", row_label=row_label, optional=True),
            "median": _parse_float(row["median"], field="median", row_label=row_label, optional=True),
            "footnote": row["footnote"] or None,
            "min_year_acquired": row["min_year_acquired"] or None,
        }


TABLE_SPECS = {
    "dataset_releases": TableSpec(
        "dataset_releases",
        (
            "release_id",
            "artifact_version",
            "publisher",
            "dataset_name",
            "data_type",
            "release_date",
            "coverage_start",
            "coverage_end",
            "download_url",
            "archive_sha256",
            "source_tree_sha256",
            "license",
            "license_url",
        ),
        pa.schema(
            [
                ("release_id", pa.string()),
                ("artifact_version", pa.string()),
                ("publisher", pa.string()),
                ("dataset_name", pa.string()),
                ("data_type", pa.string()),
                ("release_date", pa.string()),
                ("coverage_start", pa.string()),
                ("coverage_end", pa.string()),
                ("download_url", pa.string()),
                ("archive_sha256", pa.string()),
                ("source_tree_sha256", pa.string()),
                ("license", pa.string()),
                ("license_url", pa.string()),
            ]
        ),
    ),
    "food_categories": TableSpec(
        "food_categories",
        ("category_id", "source", "source_category_number", "name"),
        pa.schema(
            [
                ("category_id", pa.string()),
                ("source", pa.string()),
                ("source_category_number", pa.string()),
                ("name", pa.string()),
            ]
        ),
    ),
    "foods": TableSpec(
        "foods",
        (
            "food_id",
            "release_id",
            "source",
            "data_type",
            "source_food_id",
            "source_food_code",
            "original_description",
            "normalized_description",
            "display_name",
            "category_id",
            "category_name",
            "publication_date",
            "coverage_start",
            "coverage_end",
            "quality_status",
            "is_searchable",
            "exclusion_reason",
            "ambiguity_flags",
            "nutrient_count",
            "portion_count",
            "search_priority",
            "search_text",
        ),
        pa.schema(
            [
                ("food_id", pa.string()),
                ("release_id", pa.string()),
                ("source", pa.string()),
                ("data_type", pa.string()),
                ("source_food_id", pa.string()),
                ("source_food_code", pa.string()),
                ("original_description", pa.string()),
                ("normalized_description", pa.string()),
                ("display_name", pa.string()),
                ("category_id", pa.string()),
                ("category_name", pa.string()),
                ("publication_date", pa.string()),
                ("coverage_start", pa.string()),
                ("coverage_end", pa.string()),
                ("quality_status", pa.string()),
                ("is_searchable", pa.bool_()),
                ("exclusion_reason", pa.string()),
                ("ambiguity_flags", pa.string()),
                ("nutrient_count", pa.int32()),
                ("portion_count", pa.int32()),
                ("search_priority", pa.int32()),
                ("search_text", pa.string()),
            ]
        ),
    ),
    "nutrients": TableSpec(
        "nutrients",
        (
            "nutrient_id",
            "source",
            "source_nutrient_id",
            "nutrient_number",
            "name",
            "unit",
            "source_unit",
            "sort_rank",
            "is_archived",
        ),
        pa.schema(
            [
                ("nutrient_id", pa.string()),
                ("source", pa.string()),
                ("source_nutrient_id", pa.string()),
                ("nutrient_number", pa.string()),
                ("name", pa.string()),
                ("unit", pa.string()),
                ("source_unit", pa.string()),
                ("sort_rank", pa.float64()),
                ("is_archived", pa.bool_()),
            ]
        ),
    ),
    "source_nutrient_mappings": TableSpec(
        "source_nutrient_mappings",
        (
            "release_id",
            "source_nutrient_code",
            "source_code_field",
            "mapped_via_field",
            "nutrient_id",
            "source_nutrient_id",
        ),
        pa.schema(
            [
                ("release_id", pa.string()),
                ("source_nutrient_code", pa.string()),
                ("source_code_field", pa.string()),
                ("mapped_via_field", pa.string()),
                ("nutrient_id", pa.string()),
                ("source_nutrient_id", pa.string()),
            ]
        ),
    ),
    "food_nutrients": TableSpec(
        "food_nutrients",
        (
            "food_id",
            "nutrient_id",
            "amount",
            "unit",
            "basis",
            "source_row_id",
            "source_nutrient_code",
            "derivation_id",
            "data_points",
            "minimum",
            "maximum",
            "median",
            "footnote",
            "min_year_acquired",
        ),
        pa.schema(
            [
                ("food_id", pa.string()),
                ("nutrient_id", pa.string()),
                ("amount", pa.float64()),
                ("unit", pa.string()),
                ("basis", pa.string()),
                ("source_row_id", pa.string()),
                ("source_nutrient_code", pa.string()),
                ("derivation_id", pa.string()),
                ("data_points", pa.int32()),
                ("minimum", pa.float64()),
                ("maximum", pa.float64()),
                ("median", pa.float64()),
                ("footnote", pa.string()),
                ("min_year_acquired", pa.string()),
            ]
        ),
    ),
    "portions": TableSpec(
        "portions",
        (
            "portion_id",
            "food_id",
            "source_portion_id",
            "sequence_number",
            "amount",
            "measure_unit_id",
            "measure_unit_name",
            "portion_description",
            "modifier",
            "gram_weight",
            "data_points",
            "footnote",
            "min_year_acquired",
        ),
        pa.schema(
            [
                ("portion_id", pa.string()),
                ("food_id", pa.string()),
                ("source_portion_id", pa.string()),
                ("sequence_number", pa.int32()),
                ("amount", pa.float64()),
                ("measure_unit_id", pa.string()),
                ("measure_unit_name", pa.string()),
                ("portion_description", pa.string()),
                ("modifier", pa.string()),
                ("gram_weight", pa.float64()),
                ("data_points", pa.int32()),
                ("footnote", pa.string()),
                ("min_year_acquired", pa.string()),
            ]
        ),
    ),
}


SQLITE_SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = OFF;
PRAGMA synchronous = OFF;
PRAGMA temp_store = MEMORY;

CREATE TABLE dataset_releases (
    release_id TEXT PRIMARY KEY,
    artifact_version TEXT NOT NULL,
    publisher TEXT NOT NULL,
    dataset_name TEXT NOT NULL,
    data_type TEXT NOT NULL,
    release_date TEXT NOT NULL,
    coverage_start TEXT NOT NULL,
    coverage_end TEXT NOT NULL,
    download_url TEXT NOT NULL,
    archive_sha256 TEXT NOT NULL,
    source_tree_sha256 TEXT NOT NULL,
    license TEXT NOT NULL,
    license_url TEXT NOT NULL
);

CREATE TABLE food_categories (
    category_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_category_number TEXT NOT NULL,
    name TEXT NOT NULL,
    UNIQUE(source, source_category_number)
);

CREATE TABLE foods (
    food_id TEXT PRIMARY KEY,
    release_id TEXT NOT NULL REFERENCES dataset_releases(release_id),
    source TEXT NOT NULL,
    data_type TEXT NOT NULL,
    source_food_id TEXT NOT NULL,
    source_food_code TEXT NOT NULL,
    original_description TEXT NOT NULL,
    normalized_description TEXT NOT NULL,
    display_name TEXT NOT NULL,
    category_id TEXT NOT NULL REFERENCES food_categories(category_id),
    category_name TEXT NOT NULL,
    publication_date TEXT NOT NULL,
    coverage_start TEXT NOT NULL,
    coverage_end TEXT NOT NULL,
    quality_status TEXT NOT NULL CHECK (quality_status IN ('complete', 'ambiguous', 'partial', 'excluded')),
    is_searchable INTEGER NOT NULL CHECK (is_searchable IN (0, 1)),
    exclusion_reason TEXT,
    ambiguity_flags TEXT NOT NULL,
    nutrient_count INTEGER NOT NULL,
    portion_count INTEGER NOT NULL,
    search_priority INTEGER NOT NULL,
    search_text TEXT NOT NULL,
    UNIQUE(release_id, source_food_id)
);

CREATE TABLE nutrients (
    nutrient_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_nutrient_id TEXT NOT NULL,
    nutrient_number TEXT NOT NULL,
    name TEXT NOT NULL,
    unit TEXT NOT NULL,
    source_unit TEXT NOT NULL,
    sort_rank REAL,
    is_archived INTEGER NOT NULL CHECK (is_archived IN (0, 1)),
    UNIQUE(source, source_nutrient_id)
);

CREATE TABLE source_nutrient_mappings (
    release_id TEXT NOT NULL REFERENCES dataset_releases(release_id),
    source_nutrient_code TEXT NOT NULL,
    source_code_field TEXT NOT NULL,
    mapped_via_field TEXT NOT NULL,
    nutrient_id TEXT NOT NULL REFERENCES nutrients(nutrient_id),
    source_nutrient_id TEXT NOT NULL,
    PRIMARY KEY (release_id, source_nutrient_code)
);

CREATE TABLE food_nutrients (
    food_id TEXT NOT NULL REFERENCES foods(food_id),
    nutrient_id TEXT NOT NULL REFERENCES nutrients(nutrient_id),
    amount REAL NOT NULL CHECK (amount >= 0),
    unit TEXT NOT NULL,
    basis TEXT NOT NULL,
    source_row_id TEXT NOT NULL,
    source_nutrient_code TEXT NOT NULL,
    derivation_id TEXT,
    data_points INTEGER,
    minimum REAL,
    maximum REAL,
    median REAL,
    footnote TEXT,
    min_year_acquired TEXT,
    PRIMARY KEY (food_id, nutrient_id)
) WITHOUT ROWID;

CREATE TABLE portions (
    portion_id TEXT PRIMARY KEY,
    food_id TEXT NOT NULL REFERENCES foods(food_id),
    source_portion_id TEXT NOT NULL UNIQUE,
    sequence_number INTEGER,
    amount REAL,
    measure_unit_id TEXT NOT NULL,
    measure_unit_name TEXT NOT NULL,
    portion_description TEXT NOT NULL,
    modifier TEXT NOT NULL,
    gram_weight REAL NOT NULL CHECK (gram_weight > 0),
    data_points INTEGER,
    footnote TEXT,
    min_year_acquired TEXT
);
"""


def _write_table(
    output_dir: Path,
    connection: sqlite3.Connection,
    spec: TableSpec,
    rows: Iterable[dict[str, Any]],
    *,
    batch_size: int = 10_000,
) -> int:
    csv_path = output_dir / f"{spec.name}.csv"
    parquet_path = output_dir / f"{spec.name}.parquet"
    placeholders = ",".join("?" for _ in spec.columns)
    insert_sql = f"INSERT INTO {spec.name} ({','.join(spec.columns)}) VALUES ({placeholders})"
    parquet_writer: pq.ParquetWriter | None = None
    count = 0
    batch: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal parquet_writer
        if not batch:
            return
        connection.executemany(
            insert_sql,
            [tuple(row.get(column) for column in spec.columns) for row in batch],
        )
        table = pa.Table.from_pylist(batch, schema=spec.arrow_schema)
        if parquet_writer is None:
            parquet_writer = pq.ParquetWriter(
                parquet_path,
                spec.arrow_schema,
                compression="zstd",
                use_dictionary=True,
                write_statistics=True,
            )
        parquet_writer.write_table(table, row_group_size=len(batch))
        batch.clear()

    try:
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=spec.columns, lineterminator="\n")
            writer.writeheader()
            for source_row in rows:
                row = {column: source_row.get(column) for column in spec.columns}
                writer.writerow(row)
                batch.append(row)
                count += 1
                if len(batch) >= batch_size:
                    flush()
            flush()
        if parquet_writer is None:
            pq.write_table(
                pa.Table.from_pylist([], schema=spec.arrow_schema),
                parquet_path,
                compression="zstd",
            )
    finally:
        if parquet_writer is not None:
            parquet_writer.close()
    return count


def _create_search_index(connection: sqlite3.Connection) -> None:
    try:
        connection.executescript(
            """
            CREATE INDEX idx_foods_source_food_id ON foods(source_food_id);
            CREATE INDEX idx_foods_source_food_code ON foods(source_food_code);
            CREATE INDEX idx_foods_normalized_description ON foods(normalized_description);
            CREATE INDEX idx_foods_category ON foods(category_id);
            CREATE INDEX idx_portions_food ON portions(food_id);
            CREATE UNIQUE INDEX idx_nutrients_source_number
                ON nutrients(source, nutrient_number)
                WHERE nutrient_number <> '';

            CREATE VIRTUAL TABLE food_search USING fts5(
                food_id UNINDEXED,
                display_name,
                search_text,
                category_name,
                tokenize = 'unicode61 remove_diacritics 2'
            );

            INSERT INTO food_search (food_id, display_name, search_text, category_name)
            SELECT food_id, display_name, search_text, category_name
            FROM foods
            WHERE is_searchable = 1
            ORDER BY source_food_id;
            """
        )
    except sqlite3.OperationalError as exc:
        raise DatasetValidationError("This Python SQLite build must include FTS5 support") from exc


def _quality_report(audit: SourceAudit, output_counts: dict[str, int]) -> dict[str, Any]:
    status_counts: Counter[str] = Counter()
    searchable_foods = 0
    foods_with_portions = 0
    for row in _food_rows(audit):
        status_counts[row["quality_status"]] += 1
        searchable_foods += int(row["is_searchable"])
        foods_with_portions += int(row["portion_count"] > 0)

    measured = {
        "source_foods": len(audit.member_rows),
        "source_nutrient_rows": audit.source_nutrient_rows,
        "used_nutrients": len(audit.used_nutrient_numbers),
        "source_portion_rows": audit.source_portion_rows,
        "accepted_portions": len(audit.accepted_portions),
        "rejected_portions": audit.rejected_portion_count,
        "searchable_foods": searchable_foods,
        "complete_foods": status_counts["complete"],
        "ambiguous_foods": status_counts["ambiguous"],
        "partial_foods": status_counts["partial"],
        "excluded_foods": status_counts["excluded"],
    }
    return {
        "release_id": FNDDS_RELEASE_ID,
        "artifact_version": FNDDS_ARTIFACT_VERSION,
        "status": "pass",
        "measured": measured,
        "output_rows": output_counts,
        "additional_metrics": {
            "foods_with_valid_portions": foods_with_portions,
            "nutrient_mapping_rate": 1.0,
            "accepted_nutrient_rows": audit.source_nutrient_rows,
            "rejected_nutrient_rows": 0,
        },
        "known_rejections": {
            "portions": audit.invalid_portion_examples,
        },
        "quality_rules": {
            "nutrient_mapping": "food_nutrient.nutrient_id -> nutrient.nutrient_nbr",
            "nutrient_basis": "per_100g_edible_portion",
            "searchable": "food has Energy 208, Protein 203, Fat 204, and Carbohydrate 205",
            "ambiguous": "description contains NFS, NS, or not specified",
            "portion_acceptance": "gram_weight must be greater than zero",
        },
    }


def _validate_official_counts(report: dict[str, Any]) -> None:
    measured = report["measured"]
    mismatches = {
        key: {"expected": expected, "actual": measured.get(key)}
        for key, expected in EXPECTED_OFFICIAL_COUNTS.items()
        if measured.get(key) != expected
    }
    if mismatches:
        raise DatasetValidationError(
            "Official FNDDS release counts changed or were parsed incorrectly: "
            + json.dumps(mismatches, sort_keys=True)
        )


def _validate_official_source(audit: SourceAudit) -> None:
    if audit.source_tree_sha256 != FNDDS_SOURCE_TREE_SHA256:
        raise DatasetValidationError(
            "FNDDS source files do not match the verified official archive: "
            f"expected tree hash {FNDDS_SOURCE_TREE_SHA256}, got {audit.source_tree_sha256}"
        )


def _artifact_manifest(output_dir: Path, audit: SourceAudit, output_counts: dict[str, int]) -> dict[str, Any]:
    artifact_files: list[dict[str, Any]] = []
    for path in sorted(item for item in output_dir.iterdir() if item.is_file() and item.name != "manifest.json"):
        artifact_files.append(
            {
                "name": path.name,
                "bytes": path.stat().st_size,
                "sha256": _hash_file(path),
            }
        )
    return {
        "schema_version": 1,
        "release_id": FNDDS_RELEASE_ID,
        "artifact_version": FNDDS_ARTIFACT_VERSION,
        "source": {
            "download_url": FNDDS_DOWNLOAD_URL,
            "archive_sha256": FNDDS_ARCHIVE_SHA256,
            "source_tree_sha256": audit.source_tree_sha256,
            "files": audit.source_file_manifest,
        },
        "tables": output_counts,
        "artifacts": artifact_files,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_into(source_dir: Path, output_dir: Path, *, strict_official: bool) -> dict[str, Any]:
    audit = _build_source_audit(source_dir)
    if strict_official:
        _validate_official_source(audit)
    sqlite_path = output_dir / "opennutri-fndds.sqlite"
    connection = sqlite3.connect(sqlite_path)
    connection.executescript(SQLITE_SCHEMA)

    output_counts: dict[str, int] = {}
    table_rows: list[tuple[str, Iterable[dict[str, Any]]]] = [
        ("dataset_releases", _release_rows(audit)),
        ("food_categories", _category_rows(audit)),
        ("foods", _food_rows(audit)),
        ("nutrients", _nutrient_rows(audit)),
        ("source_nutrient_mappings", _source_nutrient_mapping_rows(audit)),
        ("food_nutrients", _food_nutrient_rows(source_dir, audit)),
        ("portions", iter(audit.accepted_portions)),
    ]
    try:
        for table_name, rows in table_rows:
            output_counts[table_name] = _write_table(
                output_dir,
                connection,
                TABLE_SPECS[table_name],
                rows,
            )
        _create_search_index(connection)
        connection.commit()
        connection.execute("VACUUM")
    finally:
        connection.close()

    report = _quality_report(audit, output_counts)
    if strict_official:
        _validate_official_counts(report)
    _write_json(output_dir / "quality_report.json", report)
    _write_json(output_dir / "manifest.json", _artifact_manifest(output_dir, audit, output_counts))
    return report


def build_fndds_release(
    source_dir: Path = DEFAULT_SOURCE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    overwrite: bool = False,
    strict_official: bool = True,
) -> dict[str, Any]:
    """Build the FNDDS release atomically and return its quality report."""

    source_dir = Path(source_dir).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    if output_dir.exists() and not overwrite:
        raise FileExistsError(f"Output directory already exists: {output_dir}")

    temporary_dir = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=str(output_dir.parent))
    )
    try:
        report = _build_into(source_dir, temporary_dir, strict_official=strict_official)
        if output_dir.exists():
            shutil.rmtree(output_dir)
        temporary_dir.replace(output_dir)
        return report
    except Exception:
        shutil.rmtree(temporary_dir, ignore_errors=True)
        raise
