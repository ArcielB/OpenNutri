import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from supabase import Client, create_client


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PIPELINE_ROOT = PROJECT_ROOT / "services" / "data-pipeline"
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from food_paper_crawler.models import build_search_hit_key


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Upload crawled PDFs and metadata to Supabase.")
    parser.add_argument(
        "--data-dir",
        default="services/data-pipeline/data",
        help="Crawler data directory that contains raw_pdfs/ and manifest-linked artifacts.",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Optional explicit path to _harvest_metadata.json. Overrides --data-dir.",
    )
    return parser


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_artifact(manifest_path: Path, manifest: dict, key_name: str) -> Path:
    raw_value = manifest.get(key_name)
    if not raw_value:
        raise SystemExit(f"Missing '{key_name}' in manifest {manifest_path}")
    crawl_root = manifest_path.parent.parent.parent
    candidate = Path(str(raw_value))
    if candidate.is_absolute():
        return candidate
    if candidate.exists():
        return candidate
    crawl_relative = crawl_root / candidate
    if crawl_relative.exists():
        return crawl_relative
    project_relative = PROJECT_ROOT / candidate
    if project_relative.exists():
        return project_relative
    raise SystemExit(f"Artifact '{key_name}' not found: {raw_value}")


def _resolve_crawl_path(manifest_path: Path, raw_value: str) -> Path:
    path = Path(raw_value)
    if path.is_absolute():
        return path
    if path.exists():
        return path
    crawl_root = manifest_path.parent.parent.parent
    crawl_relative = crawl_root / path
    if crawl_relative.exists():
        return crawl_relative
    project_relative = PROJECT_ROOT / path
    if project_relative.exists():
        return project_relative
    return path


def _require_paper_fields(record: dict, *, context: str) -> None:
    required = ("source", "workflow_language", "search_gate_score", "filter_score")
    missing = [field for field in required if record.get(field) in {None, ""}]
    if missing:
        raise RuntimeError(f"{context} missing required fields: {', '.join(missing)}")
    if record.get("workflow_language") not in {"en", "tr"}:
        raise RuntimeError(f"{context} has invalid workflow_language: {record.get('workflow_language')!r}")


def _require_search_hit_fields(record: dict, *, context: str) -> None:
    required = ("source", "workflow_language", "search_gate_score")
    missing = [field for field in required if record.get(field) in {None, ""}]
    if missing:
        raise RuntimeError(f"{context} missing required fields: {', '.join(missing)}")
    if record.get("workflow_language") not in {"en", "tr"}:
        raise RuntimeError(f"{context} has invalid workflow_language: {record.get('workflow_language')!r}")


def _paper_payload(record: dict, filename: str) -> dict:
    _require_paper_fields(record, context=f"paper '{filename}'")
    pmc_id = record.get("pmc_id") or record.get("pmcid")
    return {
        "title": record.get("title") or f"PMC{pmc_id or ''}",
        "abstract": record.get("abstract"),
        "doi": record.get("doi") or (f"pmc:{pmc_id}" if pmc_id else None),
        "canonical_key": record.get("canonical_key"),
        "filename": filename,
        "source": record.get("source"),
        "source_record_id": record.get("source_record_id"),
        "workflow_language": record.get("workflow_language"),
        "search_gate_score": record.get("search_gate_score"),
        "filter_score": record.get("filter_score"),
        "ingest_status": "accepted",
        "audit_flag": False,
        "rejection_reasons": [],
    }


def _chunked(rows: list[dict], size: int) -> list[list[dict]]:
    return [rows[idx: idx + size] for idx in range(0, len(rows), size)]


def _create_supabase_client_from_env() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("Missing SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY for upload.")
    return create_client(url, key)


def _find_existing_paper(supabase: Client, payload: dict, filename: str) -> dict | None:
    canonical_key = payload.get("canonical_key")
    if canonical_key:
        existing = supabase.table("papers").select("id,canonical_key").eq("canonical_key", canonical_key).execute()
        if existing.data:
            return existing.data[0]

    doi = payload.get("doi")
    if doi:
        existing = supabase.table("papers").select("id,canonical_key").eq("doi", doi).execute()
        if existing.data:
            return existing.data[0]

    source = payload.get("source")
    source_record_id = payload.get("source_record_id")
    if source and source_record_id:
        existing = (
            supabase.table("papers")
            .select("id,canonical_key")
            .eq("source", source)
            .eq("source_record_id", source_record_id)
            .execute()
        )
        if existing.data:
            return existing.data[0]

    existing = supabase.table("papers").select("id,canonical_key").eq("filename", filename).execute()
    if not existing.data:
        return None
    for row in existing.data:
        if not row.get("canonical_key"):
            return row
    return existing.data[0]


def _lookup_existing_paper_id(
    supabase: Client,
    canonical_key: object,
    cache: dict[str, int | None],
) -> int | None:
    normalized_key = str(canonical_key or "").strip()
    if not normalized_key:
        return None
    if normalized_key in cache:
        return cache[normalized_key]
    existing = (
        supabase.table("papers")
        .select("id")
        .eq("canonical_key", normalized_key)
        .limit(1)
        .execute()
    )
    paper_id = int(existing.data[0]["id"]) if existing.data else None
    cache[normalized_key] = paper_id
    return paper_id


def _dedupe_search_hits(rows: list[dict]) -> list[dict]:
    deduped: dict[str, dict] = {}
    for row in rows:
        hit_key = row.get("hit_key") or build_search_hit_key(
            canonical_key=row.get("canonical_key"),
            source=row.get("source"),
            workflow_language=row.get("workflow_language"),
            template_id=row.get("template_id"),
            source_term=row.get("source_term"),
            query_phrase=row.get("query_phrase"),
            query_text=row.get("query_text"),
        )
        row["hit_key"] = hit_key
        existing = deduped.get(hit_key)
        if existing is None:
            deduped[hit_key] = row
            continue
        if existing.get("paper_id") is None and row.get("paper_id") is not None:
            existing["paper_id"] = row["paper_id"]
        if not existing.get("title") and row.get("title"):
            existing["title"] = row["title"]
        if not existing.get("abstract") and row.get("abstract"):
            existing["abstract"] = row["abstract"]
        if existing.get("search_gate_score") in {None, ""} and row.get("search_gate_score") not in {None, ""}:
            existing["search_gate_score"] = row["search_gate_score"]
        if existing.get("filter_score") in {None, ""} and row.get("filter_score") not in {None, ""}:
            existing["filter_score"] = row["filter_score"]
        existing["search_gate_pass"] = bool(existing.get("search_gate_pass") or row.get("search_gate_pass"))
        existing["filter_pass"] = bool(existing.get("filter_pass") or row.get("filter_pass"))
        existing["is_duplicate"] = bool(existing.get("is_duplicate") or row.get("is_duplicate"))
    return list(deduped.values())


def _prepare_search_hits(
    rows: list[dict],
    *,
    paper_id_by_key: dict[str, int],
    existing_paper_id_lookup,
) -> list[dict]:
    prepared: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        _require_search_hit_fields(row, context=f"search hit {row.get('canonical_key') or 'unknown'}")
        canonical_key = str(row.get("canonical_key") or "").strip()
        paper_id = paper_id_by_key.get(canonical_key)
        if paper_id is None and canonical_key:
            paper_id = existing_paper_id_lookup(canonical_key)
        payload = {
            "paper_id": paper_id,
            "hit_key": row.get("hit_key"),
            "canonical_key": row.get("canonical_key"),
            "source": row.get("source"),
            "source_record_id": row.get("source_record_id"),
            "external_id": row.get("external_id"),
            "pmcid": row.get("pmcid"),
            "doi": row.get("doi"),
            "title": row.get("title"),
            "abstract": row.get("abstract"),
            "workflow_language": row.get("workflow_language"),
            "query_text": row.get("query_text") or row.get("query"),
            "template_id": row.get("template_id"),
            "source_term": row.get("source_term"),
            "term_type": row.get("term_type"),
            "query_phrase": row.get("query_phrase"),
            "search_gate_score": row.get("search_gate_score"),
            "search_gate_pass": row.get("search_gate_pass"),
            "filter_score": row.get("filter_score"),
            "filter_pass": row.get("filter_pass"),
            "is_duplicate": row.get("is_duplicate") or False,
        }
        if not payload["canonical_key"] or not payload["source"] or not payload["query_text"]:
            raise SystemExit(f"Incomplete search-hit payload for canonical_key={payload['canonical_key']!r}")
        prepared.append(payload)
    return _dedupe_search_hits(prepared)


async def upload_papers(args: argparse.Namespace, supabase: Client) -> None:
    manifest_path = (
        Path(args.manifest)
        if args.manifest
        else Path(args.data_dir) / "raw_pdfs" / "_harvest_metadata.json"
    )

    print("=" * 60)
    print("OpenNutri: Uploading Crawled PDFs to Supabase")
    print("=" * 60)
    print(f"Manifest: {manifest_path}")

    if not manifest_path.exists():
        raise SystemExit(f"Manifest file not found at {manifest_path}")

    manifest = _load_json(manifest_path)
    results = manifest.get("results", [])
    upload_candidates = [row for row in results if row.get("status") == "success"]
    candidate_store_path = _resolve_artifact(manifest_path, manifest, "candidate_store")
    search_hits_path = _resolve_artifact(manifest_path, manifest, "search_hits")
    candidate_store = _load_json(candidate_store_path)
    search_hits_payload = _load_json(search_hits_path)
    if not isinstance(candidate_store.get("candidates"), list):
        raise SystemExit(f"Candidate store is missing 'candidates': {candidate_store_path}")
    if not isinstance(search_hits_payload.get("hits"), list):
        raise SystemExit(f"Search-hit payload is missing 'hits': {search_hits_path}")

    print(f"Found {len(upload_candidates)} successful downloads in metadata.")
    print(f"Candidate store: {candidate_store_path}")
    print(f"Search hits: {search_hits_path}")

    candidate_by_key = {
        row.get("canonical_key"): row
        for row in candidate_store.get("candidates", [])
        if isinstance(row, dict) and row.get("canonical_key")
    }
    paper_id_cache: dict[str, int | None] = {}

    try:
        supabase.storage.create_bucket("papers", options={"public": True})
    except Exception:
        pass

    paper_id_by_key: dict[str, int] = {}
    upload_errors: list[str] = []
    uploaded_count = 0

    for record in upload_candidates:
        file_path = _resolve_crawl_path(manifest_path, str(record.get("file") or ""))
        if not file_path.exists():
            upload_errors.append(f"Missing file on disk: {file_path}")
            continue

        filename = file_path.name
        canonical_key = record.get("canonical_key")
        candidate_row = candidate_by_key.get(canonical_key, {})
        paper_row = {**candidate_row, **record}

        print(f"\nProcessing {filename}...")
        try:
            with file_path.open("rb") as handle:
                supabase.storage.from_("papers").upload(
                    path=filename,
                    file=handle,
                    file_options={
                        "cache-control": "3600",
                        "upsert": "true",
                        "content-type": "application/pdf",
                    },
                )

            payload = _paper_payload(paper_row, filename)
            existing = _find_existing_paper(supabase, payload, filename)
            if existing:
                paper_id = int(existing["id"])
                supabase.table("papers").update(payload).eq("id", paper_id).execute()
                print("  Updated existing paper metadata.")
            else:
                inserted = supabase.table("papers").insert(payload).execute()
                paper_id = int(inserted.data[0]["id"])
                print("  Inserted paper row.")

            if canonical_key:
                paper_id_by_key[canonical_key] = paper_id
            uploaded_count += 1
        except Exception as exc:
            upload_errors.append(f"{filename}: {exc}")

    if upload_errors:
        raise SystemExit("Upload failed:\n- " + "\n- ".join(upload_errors))

    search_hits = _prepare_search_hits(
        search_hits_payload.get("hits", []),
        paper_id_by_key=paper_id_by_key,
        existing_paper_id_lookup=lambda canonical_key: _lookup_existing_paper_id(
            supabase,
            canonical_key,
            paper_id_cache,
        ),
    )

    if not search_hits:
        raise SystemExit("Search-hit persistence is empty; refusing to treat this upload as successful.")

    inserted_hits = 0
    for batch in _chunked(search_hits, 500):
        supabase.table("paper_search_hits").upsert(batch, on_conflict="hit_key").execute()
        inserted_hits += len(batch)

    if inserted_hits <= 0:
        raise SystemExit("Search hits were not persisted.")

    print("=" * 60)
    if uploaded_count > 0:
        print(f"Successfully uploaded and registered {uploaded_count} PDFs.")
    else:
        print("No PDFs were accepted in this run; persisted metadata-stage search hits only.")
    print(f"Persisted {inserted_hits} metadata-stage search hits.")
    print("=" * 60)


if __name__ == "__main__":
    parsed_args = build_parser().parse_args()
    asyncio.run(upload_papers(parsed_args, _create_supabase_client_from_env()))
