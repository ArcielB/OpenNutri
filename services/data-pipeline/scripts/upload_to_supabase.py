import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from supabase import Client, create_client


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PIPELINE_ROOT = PROJECT_ROOT / "services" / "data-pipeline"
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from ai_routing import (
    BLOCKED_DESTINATION,
    HUMAN_REVIEW_DESTINATION,
    ROUTING_STATUS_AI_FINAL_HAS_DATA,
    ROUTING_STATUS_AI_FINAL_NO_DATA,
    ROUTING_STATUS_AI_PROVISIONAL_NO_DATA,
    ROUTING_STATUS_HUMAN_READY,
    ROUTING_STATUS_QUEUED,
    RoutingStageConfig,
)
from food_paper_crawler.models import build_search_batch_key, build_search_hit_key
from pdf_limits import max_paper_pdf_bytes, pdf_size_limit_message


EXISTING_PAPER_SELECT = "id,canonical_key,routing_status,current_stage_key,latest_ai_extraction_id,pdf_url"
CLOSED_AI_ROUTING_STATUSES = {
    ROUTING_STATUS_HUMAN_READY,
    ROUTING_STATUS_AI_PROVISIONAL_NO_DATA,
    ROUTING_STATUS_AI_FINAL_HAS_DATA,
    ROUTING_STATUS_AI_FINAL_NO_DATA,
}


def _is_payload_too_large_error(exc: Exception) -> bool:
    values = [type(exc).__name__, str(exc)]
    for attr in ("status_code", "statusCode", "code", "error", "message"):
        value = getattr(exc, attr, None)
        if value not in {None, ""}:
            values.append(str(value))
    text = " ".join(values).casefold()
    return (
        "413" in text
        or "payload too large" in text
        or "maximum allowed size" in text
        or "object exceeded" in text
    )


def _is_duplicate_paper_key_error(exc: Exception) -> bool:
    values = [type(exc).__name__, str(exc)]
    for attr in ("status_code", "statusCode", "code", "error", "message", "details"):
        value = getattr(exc, attr, None)
        if value not in {None, ""}:
            values.append(str(value))
    text = " ".join(values).casefold()
    return (
        ("23505" in text or "duplicate key" in text)
        and ("canonical_key" in text or "idx_papers_canonical_key_unique" in text)
    )


def _truthy_env(name: str, *, default: bool = False) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}


def store_pdfs_in_supabase() -> bool:
    return _truthy_env("OPENNUTRI_STORE_PDFS_IN_SUPABASE", default=False)


def _normalize_pmcid(value: object) -> str:
    text = "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())
    if not text:
        return ""
    if not text.startswith("pmc"):
        text = f"pmc{text}"
    return text.upper()


def _paper_pdf_url(record: dict) -> str | None:
    explicit_url = str(record.get("pdf_url") or "").strip()
    if explicit_url:
        return explicit_url
    pmcid = _normalize_pmcid(record.get("pmc_id") or record.get("pmcid"))
    if pmcid:
        # Direct PDF endpoint: returns application/pdf with CORS headers and no
        # redirect, so browser PDF.js (react-pdf) can fetch it. The ?pdf=render
        # form 302-redirects without CORS headers and fails in-browser.
        return f"https://europepmc.org/api/getPdf?pmcid={pmcid}"
    return None


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


def _require_search_batch_fields(record: dict, *, context: str) -> None:
    required = ("batch_id", "batch_key", "source", "workflow_language", "query_text", "template_id", "term_type")
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
        "pdf_url": _paper_pdf_url(record),
        "source": record.get("source"),
        "source_record_id": record.get("source_record_id"),
        "workflow_language": record.get("workflow_language"),
        "search_gate_score": record.get("search_gate_score"),
        "filter_score": record.get("filter_score"),
        "ingest_status": "accepted",
        "audit_flag": False,
        "rejection_reasons": [],
    }


def _metadata_refresh_payload(payload: dict, *, include_filename: bool) -> dict:
    refreshed = dict(payload)
    if not include_filename:
        refreshed.pop("filename", None)
    return refreshed


def _chunked(rows: list[dict], size: int) -> list[list[dict]]:
    return [rows[idx: idx + size] for idx in range(0, len(rows), size)]


def _create_supabase_client_from_env() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("Missing SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY for upload.")
    return create_client(url, key)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_active_stage_config(supabase: Client) -> RoutingStageConfig:
    response = (
        supabase.table("routing_stage_configs")
        .select("*")
        .eq("active", True)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise SystemExit("No active routing_stage_configs row found. Upload cannot enqueue AI routing.")
    return RoutingStageConfig.from_row(response.data[0])


def _paper_has_human_outcome(supabase: Client, paper_id: int) -> bool:
    response = (
        supabase.table("paper_review_outcomes")
        .select("truth_source_kind")
        .eq("paper_id", paper_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return False
    return str(response.data[0].get("truth_source_kind") or "human_review").strip().lower() == "human_review"


def _enqueue_stage_task(
    supabase: Client,
    *,
    paper_id: int,
    stage_config: RoutingStageConfig,
    filter_score: object,
    preserve_human_route: bool,
) -> None:
    existing_task_response = (
        supabase.table("paper_stage_tasks")
        .select("id,status")
        .eq("paper_id", paper_id)
        .eq("stage_key", stage_config.stage_key)
        .limit(1)
        .execute()
    )
    existing_task = existing_task_response.data[0] if existing_task_response.data else None
    existing_status = str(existing_task.get("status") or "").strip().lower() if existing_task else ""
    should_queue_task = existing_status not in {"queued", "processing", "completed"}

    if should_queue_task:
        priority = 0
        try:
            priority = int(round(float(filter_score or 0) * 100))
        except (TypeError, ValueError):
            priority = 0
        supabase.table("paper_stage_tasks").upsert(
            {
                "paper_id": paper_id,
                "stage_key": stage_config.stage_key,
                "status": "queued",
                "priority": priority,
                "last_error": None,
                "started_at": None,
                "completed_at": None,
                "updated_at": _utcnow_iso(),
            },
            on_conflict="paper_id,stage_key",
        ).execute()

    paper_update = {
        "current_stage_key": stage_config.stage_key,
        "routing_updated_at": _utcnow_iso(),
    }
    if preserve_human_route:
        paper_update["routing_status"] = ROUTING_STATUS_HUMAN_READY
        paper_update["route_destination"] = HUMAN_REVIEW_DESTINATION
    elif should_queue_task:
        paper_update["routing_status"] = ROUTING_STATUS_QUEUED
        paper_update["route_destination"] = BLOCKED_DESTINATION
        paper_update["routing_bucket"] = None
        paper_update["latest_ai_extraction_id"] = None
    supabase.table("papers").update(paper_update).eq("id", paper_id).execute()


def _find_existing_paper(supabase: Client, payload: dict, filename: str) -> dict | None:
    canonical_key = payload.get("canonical_key")
    if canonical_key:
        existing = (
            supabase.table("papers")
            .select(EXISTING_PAPER_SELECT)
            .eq("canonical_key", canonical_key)
            .execute()
        )
        if existing.data:
            return existing.data[0]

    doi = payload.get("doi")
    if doi:
        existing = supabase.table("papers").select(EXISTING_PAPER_SELECT).eq("doi", doi).execute()
        if existing.data:
            return existing.data[0]

    source = payload.get("source")
    source_record_id = payload.get("source_record_id")
    if source and source_record_id:
        existing = (
            supabase.table("papers")
            .select(EXISTING_PAPER_SELECT)
            .eq("source", source)
            .eq("source_record_id", source_record_id)
            .execute()
        )
        if existing.data:
            return existing.data[0]

    existing = supabase.table("papers").select(EXISTING_PAPER_SELECT).eq("filename", filename).execute()
    if not existing.data:
        return None
    for row in existing.data:
        if not row.get("canonical_key"):
            return row
    return existing.data[0]


def _existing_paper_has_closed_ai_route(existing: dict | None) -> bool:
    if not existing:
        return False
    routing_status = str(existing.get("routing_status") or "").strip().lower()
    latest_ai_extraction_id = str(existing.get("latest_ai_extraction_id") or "").strip()
    return bool(latest_ai_extraction_id and routing_status in CLOSED_AI_ROUTING_STATUSES)


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
            "pdf_url": _paper_pdf_url(row),
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


def _prepare_search_batches(manifest: dict) -> list[dict]:
    crawl_run_id = str(manifest.get("crawl_run_id") or "").strip()
    query_log = manifest.get("query_log")
    if not crawl_run_id or not isinstance(query_log, list):
        return []
    prepared: list[dict] = []
    for row in query_log:
        if not isinstance(row, dict):
            continue
        payload = {
            "batch_id": row.get("batch_id"),
            "batch_key": row.get("batch_key")
            or build_search_batch_key(
                source=row.get("source"),
                workflow_language=row.get("language"),
                template_id=row.get("template_id"),
                source_term=row.get("source_term"),
                query_phrase=row.get("query_phrase"),
                query_text=row.get("query"),
            ),
            "run_id": crawl_run_id,
            "batch_rank": row.get("batch_rank") or 0,
            "source": row.get("source"),
            "workflow_language": row.get("language"),
            "query_text": row.get("query"),
            "template_id": row.get("template_id"),
            "source_term": row.get("source_term"),
            "term_type": row.get("term_type"),
            "query_phrase": row.get("query_phrase"),
            "query_limit": row.get("query_limit") or 0,
            "results": row.get("results") or 0,
            "search_gate_passed": row.get("search_gate_passed") or 0,
            "search_gate_rejected": row.get("search_gate_rejected") or 0,
            "filter_passed": row.get("filter_passed") or 0,
            "duplicates": row.get("duplicates") or 0,
            "skipped_seen": row.get("skipped_seen") or 0,
            "accepted": row.get("accepted") or 0,
            "metadata_rejected": row.get("metadata_rejected") or 0,
            "pdf_fetch_fail": row.get("pdf_fetch_fail") or 0,
            "pdf_validation_fail": row.get("pdf_validation_fail") or 0,
        }
        _require_search_batch_fields(payload, context=f"search batch {payload.get('batch_id') or 'unknown'}")
        prepared.append(payload)
    return prepared


def _prepare_search_batch_hits(rows: list[dict]) -> list[dict]:
    deduped: dict[tuple[str, str], dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not row.get("search_gate_pass") or row.get("is_duplicate"):
            continue
        batch_id = str(row.get("batch_id") or "").strip()
        hit_key = str(
            row.get("hit_key")
            or build_search_hit_key(
                canonical_key=row.get("canonical_key"),
                source=row.get("source"),
                workflow_language=row.get("workflow_language"),
                template_id=row.get("template_id"),
                source_term=row.get("source_term"),
                query_phrase=row.get("query_phrase"),
                query_text=row.get("query_text") or row.get("query"),
            )
        ).strip()
        if not batch_id or not hit_key:
            continue
        result_rank = row.get("result_rank")
        try:
            parsed_rank = int(result_rank) if result_rank is not None else None
        except (TypeError, ValueError):
            parsed_rank = None
        payload = {
            "batch_id": batch_id,
            "hit_key": hit_key,
            "result_rank": parsed_rank,
        }
        deduped[(batch_id, hit_key)] = payload
    return list(deduped.values())


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

    store_pdf_files = store_pdfs_in_supabase()
    if store_pdf_files:
        try:
            supabase.storage.create_bucket("papers", options={"public": True})
        except Exception:
            pass
    else:
        print("Supabase paper PDF Storage upload is disabled; source pdf_url will be used on demand.")

    paper_id_by_key: dict[str, int] = {}
    upload_errors: list[str] = []
    skipped_uploads: list[str] = []
    registered_count = 0
    storage_upload_count = 0
    active_stage = _fetch_active_stage_config(supabase)
    max_upload_bytes = max_paper_pdf_bytes()

    for record in upload_candidates:
        file_path = _resolve_crawl_path(manifest_path, str(record.get("file") or ""))
        if not file_path.exists():
            upload_errors.append(f"Missing file on disk: {file_path}")
            continue

        filename = file_path.name
        canonical_key = record.get("canonical_key")
        candidate_row = candidate_by_key.get(canonical_key, {})
        paper_row = {**candidate_row, **record}
        payload = _paper_payload(paper_row, filename)
        existing = _find_existing_paper(supabase, payload, filename)
        existing_paper_id = int(existing["id"]) if existing else None
        preserve_human_route = (
            _paper_has_human_outcome(supabase, existing_paper_id)
            if existing_paper_id is not None
            else False
        )
        has_closed_ai_route = _existing_paper_has_closed_ai_route(existing)

        print(f"\nProcessing {filename}...")
        if existing and (preserve_human_route or has_closed_ai_route):
            supabase.table("papers").update(
                _metadata_refresh_payload(payload, include_filename=False)
            ).eq("id", existing_paper_id).execute()
            if canonical_key:
                paper_id_by_key[canonical_key] = existing_paper_id
            reason = (
                "existing paper has a human outcome"
                if preserve_human_route
                else "existing paper already has a closed AI route"
            )
            skipped_uploads.append(f"{filename}: {reason}; refreshed metadata/search-hit links only")
            print(f"  Skipped Storage upload: {reason}.")
            continue

        if not store_pdf_files and not payload.get("pdf_url"):
            upload_errors.append(
                f"{filename}: missing source pdf_url while OPENNUTRI_STORE_PDFS_IN_SUPABASE is disabled"
            )
            continue

        try:
            if store_pdf_files:
                file_size = file_path.stat().st_size
                if file_size > max_upload_bytes:
                    reason = pdf_size_limit_message(file_size, limit_bytes=max_upload_bytes)
                    skipped_uploads.append(f"{filename}: {reason}")
                    print(f"  Skipped oversized PDF: {reason}.")
                    continue
                with file_path.open("rb") as handle:
                    supabase.storage.from_("papers").upload(
                        path=filename,
                        file=handle,
                        file_options={
                            "cache-control": "604800",
                            "upsert": "true",
                            "content-type": "application/pdf",
                        },
                    )
                storage_upload_count += 1
            else:
                print("  Skipped Supabase Storage upload; source PDF URL retained.")

            if existing:
                paper_id = existing_paper_id if existing_paper_id is not None else int(existing["id"])
                supabase.table("papers").update(payload).eq("id", paper_id).execute()
                print("  Updated existing paper metadata.")
            else:
                inserted = supabase.table("papers").insert(payload).execute()
                paper_id = int(inserted.data[0]["id"])
                print("  Inserted paper row.")

            if canonical_key:
                paper_id_by_key[canonical_key] = paper_id
            registered_count += 1
            if preserve_human_route:
                print("  Existing paper has a human outcome; leaving routing unchanged.")
            elif has_closed_ai_route:
                print("  Existing paper already has a closed AI route; leaving routing unchanged.")
            else:
                _enqueue_stage_task(
                    supabase,
                    paper_id=paper_id,
                    stage_config=active_stage,
                    filter_score=payload.get("filter_score"),
                    preserve_human_route=False,
                )
                print(f"  Enqueued AI routing stage: {active_stage.stage_key}")
        except Exception as exc:
            if _is_payload_too_large_error(exc):
                reason = f"Supabase Storage rejected PDF as too large: {exc}"
                skipped_uploads.append(f"{filename}: {reason}")
                print(f"  Skipped oversized PDF: {reason}")
                continue
            if _is_duplicate_paper_key_error(exc):
                duplicate = _find_existing_paper(supabase, payload, filename)
                if duplicate:
                    paper_id = int(duplicate["id"])
                    duplicate_preserve_human = _paper_has_human_outcome(supabase, paper_id)
                    duplicate_closed_ai = _existing_paper_has_closed_ai_route(duplicate)
                    supabase.table("papers").update(
                        _metadata_refresh_payload(payload, include_filename=False)
                    ).eq("id", paper_id).execute()
                    if canonical_key:
                        paper_id_by_key[canonical_key] = paper_id
                    if duplicate_preserve_human or duplicate_closed_ai:
                        reason = "duplicate canonical paper already has a closed route"
                        skipped_uploads.append(f"{filename}: {reason}; refreshed metadata/search-hit links only")
                        print(f"  Duplicate canonical paper found; {reason}.")
                    else:
                        _enqueue_stage_task(
                            supabase,
                            paper_id=paper_id,
                            stage_config=active_stage,
                            filter_score=payload.get("filter_score"),
                            preserve_human_route=False,
                        )
                        skipped_uploads.append(
                            f"{filename}: duplicate canonical paper already exists as paper {paper_id}; reusing row"
                        )
                        print(f"  Duplicate canonical paper found; reusing paper {paper_id}.")
                    continue
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

    search_batches = _prepare_search_batches(manifest)
    search_batch_hits = _prepare_search_batch_hits(search_hits_payload.get("hits", []))

    inserted_hits = 0
    for batch in _chunked(search_hits, 500):
        supabase.table("paper_search_hits").upsert(batch, on_conflict="hit_key").execute()
        inserted_hits += len(batch)

    if inserted_hits <= 0:
        raise SystemExit("Search hits were not persisted.")

    inserted_batches = 0
    for batch in _chunked(search_batches, 250):
        supabase.table("paper_search_batches").upsert(batch, on_conflict="batch_id").execute()
        inserted_batches += len(batch)

    inserted_batch_hits = 0
    for batch in _chunked(search_batch_hits, 500):
        supabase.table("paper_search_batch_hits").upsert(batch, on_conflict="batch_id,hit_key").execute()
        inserted_batch_hits += len(batch)

    print("=" * 60)
    if registered_count > 0:
        if store_pdf_files:
            print(f"Successfully uploaded {storage_upload_count} PDFs and registered {registered_count} papers.")
        else:
            print(f"Successfully registered {registered_count} papers without Supabase PDF upload.")
    else:
        print("No PDFs were accepted in this run; persisted metadata-stage search hits only.")
    if skipped_uploads:
        print(f"Skipped {len(skipped_uploads)} PDF upload(s):")
        for skipped in skipped_uploads:
            print(f"  - {skipped}")
    print(f"Persisted {inserted_hits} metadata-stage search hits.")
    print(f"Persisted {inserted_batches} search batches.")
    print(f"Persisted {inserted_batch_hits} search batch-hit links.")
    print("=" * 60)


if __name__ == "__main__":
    parsed_args = build_parser().parse_args()
    asyncio.run(upload_papers(parsed_args, _create_supabase_client_from_env()))
