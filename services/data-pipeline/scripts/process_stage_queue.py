from __future__ import annotations

import argparse
import contextlib
import json
import os
import signal
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict
from dataclasses import is_dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

from supabase import Client, create_client


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PIPELINE_ROOT = PROJECT_ROOT / "services" / "data-pipeline"
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from ai_routing import (
    BLOCKED_DESTINATION,
    HUMAN_REVIEW_DESTINATION,
    NEXT_STAGE_DESTINATION,
    PROVISIONAL_SKIP_DESTINATION,
    ROUTING_STATUS_HUMAN_READY,
    ROUTING_STATUS_AI_PROVISIONAL_NO_DATA,
    ROUTING_STATUS_FAILED,
    ROUTING_STATUS_PROCESSING,
    ROUTING_STATUS_QUEUED,
    RoutingStageConfig,
    classify_routing_bucket,
    input_hash_for_text,
    normalize_ai_payload_with_summary,
    payload_text_and_hash,
    route_bucket,
    stable_audit_sample,
)
from evaluator.unified_evaluator import UnifiedEvaluator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Process the staged AI routing queue.")
    parser.add_argument("--stage-key", default=None, help="Specific stage key to drain. Defaults to the active stage.")
    parser.add_argument("--max-tasks", type=int, default=50, help="Maximum queued papers to process in one run.")
    parser.add_argument(
        "--stop-on-quota",
        action="store_true",
        help="Stop after the first Gemini quota/rate-limit error instead of burning through the claimed queue.",
    )
    parser.add_argument(
        "--requeue-stale-minutes",
        type=int,
        default=120,
        help="Requeue processing tasks older than this many minutes before claiming new work. Use 0 to disable.",
    )
    parser.add_argument("--json-summary", action="store_true", help="Print a machine-readable run summary.")
    return parser


def require_client() -> Client:
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        raise SystemExit("Missing SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY.")
    return create_client(supabase_url, supabase_key)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_active_stage_config(client: Client, stage_key: str | None = None) -> RoutingStageConfig:
    query = client.table("routing_stage_configs").select("*")
    if stage_key:
        query = query.eq("stage_key", stage_key)
    else:
        query = query.eq("active", True)
    response = query.limit(1).execute()
    if not response.data:
        raise RuntimeError(f"No routing stage config found for {stage_key or 'active stage'}.")
    return RoutingStageConfig.from_row(response.data[0])


def fetch_stage_config(client: Client, stage_key: str) -> RoutingStageConfig:
    response = (
        client.table("routing_stage_configs")
        .select("*")
        .eq("stage_key", stage_key)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise RuntimeError(f"No routing stage config found for {stage_key}.")
    return RoutingStageConfig.from_row(response.data[0])


def claim_stage_tasks(client: Client, *, stage_key: str, limit: int) -> list[dict]:
    response = client.rpc(
        "claim_paper_stage_tasks",
        {"p_stage_key": stage_key, "p_limit": max(1, int(limit))},
    ).execute()
    return response.data or []


def requeue_stale_processing_tasks(
    client: Client,
    *,
    stage_key: str | None = None,
    stale_after_minutes: int = 120,
) -> int:
    if int(stale_after_minutes) <= 0:
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=int(stale_after_minutes))).isoformat()
    query = (
        client.table("paper_stage_tasks")
        .select("id,paper_id,stage_key")
        .eq("status", "processing")
        .lt("started_at", cutoff)
    )
    if stage_key:
        query = query.eq("stage_key", stage_key)
    response = query.limit(1000).execute()
    stale_tasks = response.data or []
    if not stale_tasks:
        return 0

    now = _utcnow_iso()
    for task in stale_tasks:
        task_id = task.get("id")
        paper_id = task.get("paper_id")
        task_stage_key = str(task.get("stage_key") or stage_key or "").strip()
        if not task_id or not paper_id or not task_stage_key:
            continue
        client.table("paper_stage_tasks").update(
            {
                "status": "queued",
                "last_error": f"Requeued stale processing task after {int(stale_after_minutes)} minutes.",
                "started_at": None,
                "completed_at": None,
                "updated_at": now,
            }
        ).eq("id", task_id).execute()
        client.table("papers").update(
            {
                "routing_status": ROUTING_STATUS_QUEUED,
                "current_stage_key": task_stage_key,
                "route_destination": BLOCKED_DESTINATION,
                "routing_updated_at": now,
            }
        ).eq("id", paper_id).execute()
    return len(stale_tasks)


def fetch_reference_lookups(client: Client) -> dict[str, list[dict]]:
    foods = _fetch_all_rows(client, "entities", "id,canonical_name")
    food_aliases = _fetch_all_rows(client, "entity_aliases", "entity_id,alias_name")
    aliases_by_food_id: dict[str, list[str]] = {}
    for row in food_aliases:
        entity_id = str(row.get("entity_id") or "").strip()
        alias_name = str(row.get("alias_name") or "").strip()
        if entity_id and alias_name:
            aliases_by_food_id.setdefault(entity_id, []).append(alias_name)
    for row in foods:
        aliases = aliases_by_food_id.get(str(row.get("id") or "").strip())
        if aliases:
            row["alias_names"] = aliases

    return {
        "nutrients": _fetch_all_rows(client, "master_nutrients", "id,standard_name"),
        "foods": foods,
    }


def _candidate_lookup_text(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def select_food_candidates_for_text(
    full_text: str,
    food_lookup: list[dict],
    *,
    limit: int = 250,
) -> list[dict]:
    haystack = f" {_candidate_lookup_text(full_text[:500_000])} "
    matches: list[tuple[int, int, str, dict]] = []
    for index, row in enumerate(food_lookup or []):
        if not isinstance(row, dict) or not row.get("id"):
            continue
        candidate_names = [str(row.get("canonical_name") or "").strip()]
        aliases = row.get("alias_names")
        if isinstance(aliases, list):
            candidate_names.extend(str(alias).strip() for alias in aliases)
        best_match = ""
        for name in candidate_names:
            normalized = _candidate_lookup_text(name)
            if len(normalized) < 4:
                continue
            if f" {normalized} " in haystack and len(normalized) > len(best_match):
                best_match = normalized
        if best_match:
            matches.append((len(best_match), -index, best_match, row))

    matches.sort(reverse=True)
    return [row for _score, _index, _match, row in matches[: max(1, int(limit))]]


def _fetch_all_rows(client: Client, table_name: str, select: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        response = client.table(table_name).select(select).range(offset, offset + 999).execute()
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < 1000:
            return rows
        offset += 1000


def fetch_paper(client: Client, paper_id: int) -> dict:
    response = (
        client.table("papers")
        .select("id,title,doi,filename,workflow_language,current_stage_key,routing_status,route_destination,latest_ai_extraction_id")
        .eq("id", paper_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise RuntimeError(f"Paper {paper_id} not found.")
    return response.data[0]


def fetch_existing_outcome(client: Client, paper_id: int) -> dict | None:
    response = (
        client.table("paper_review_outcomes")
        .select("id,truth_source_kind")
        .eq("paper_id", paper_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def has_human_truth(outcome: dict | None) -> bool:
    if not outcome:
        return False
    return str(outcome.get("truth_source_kind") or "human_review").strip().lower() == "human_review"


def _public_paper_url(filename: str) -> str:
    supabase_url = os.environ.get("SUPABASE_URL")
    if not supabase_url:
        raise RuntimeError("Missing SUPABASE_URL.")
    return f"{supabase_url.rstrip('/')}/storage/v1/object/public/papers/{quote(filename)}"


def extract_pdf_text(filename: str) -> str:
    if not filename:
        raise RuntimeError("Paper is missing filename.")
    if shutil.which("pdftotext") is None:
        raise RuntimeError("Missing required dependency: pdftotext")

    url = _public_paper_url(filename)
    with urlopen(url, timeout=60) as response:
        pdf_bytes = response.read()
    if not pdf_bytes:
        raise RuntimeError(f"No PDF bytes returned for {filename}.")

    with tempfile.NamedTemporaryFile(suffix=".pdf") as pdf_file:
        pdf_file.write(pdf_bytes)
        pdf_file.flush()
        result = subprocess.run(
            ["pdftotext", pdf_file.name, "-"],
            capture_output=True,
            check=False,
            text=True,
        )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"pdftotext failed for {filename}")
    full_text = result.stdout.strip()
    if not full_text:
        raise RuntimeError(f"Empty PDF text extracted for {filename}")
    return full_text


def stage_text_for_model(full_text: str, *, stage_config: RoutingStageConfig) -> str:
    model_name = str(stage_config.model_name or "").strip().lower()
    if "gemma" in model_name:
        default_limit = "60000"
        limit_value = os.environ.get(
            "GEMMA_STAGE_TEXT_LIMIT_CHARS",
            os.environ.get("AI_STAGE_TEXT_LIMIT_CHARS", default_limit),
        )
    else:
        default_limit = "0"
        limit_value = os.environ.get(
            "GEMINI_STAGE_TEXT_LIMIT_CHARS",
            os.environ.get("AI_STAGE_TEXT_LIMIT_CHARS", default_limit),
        )
    limit = int(limit_value or default_limit)
    if limit <= 0 or len(full_text) <= limit:
        return full_text
    head_len = max(1, limit // 2)
    tail_len = max(1, limit - head_len)
    return (
        full_text[:head_len]
        + "\n\n[TRUNCATED FOR AI STAGE INPUT]\n\n"
        + full_text[-tail_len:]
    )


@contextlib.contextmanager
def ai_task_timeout(seconds: int):
    timeout_seconds = int(seconds)
    if timeout_seconds <= 0 or not hasattr(signal, "SIGALRM"):
        yield
        return

    previous_handler = signal.getsignal(signal.SIGALRM)

    def _raise_timeout(_signum, _frame):
        raise TimeoutError(f"AI evaluation exceeded {timeout_seconds} seconds")

    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def ai_result_error(ai_result) -> str | None:
    reasoning = str(getattr(ai_result, "reasoning", "") or "").strip()
    if reasoning.lower().startswith("extraction error:"):
        return reasoning
    return None


def is_quota_error(error_text: object) -> bool:
    text = str(error_text or "").strip().lower()
    if not text:
        return False
    quota_markers = (
        "quota",
        "rate limit",
        "rate-limit",
        "free_tier",
        "free-tier",
        "generativelanguage.googleapis.com",
        "gemini-api",
    )
    if any(marker in text for marker in quota_markers):
        return True
    return "429" in text and ("gemini" in text or "generate_content" in text)


def is_non_retryable_model_error(error_text: object) -> bool:
    text = str(error_text or "").strip().lower()
    if not text:
        return False
    return (
        "not found" in text
        and "models/" in text
        and ("generatecontent" in text or "generate_content" in text)
    ) or "not supported for generatecontent" in text


def max_task_attempts() -> int:
    raw_value = os.environ.get("AI_STAGE_MAX_TASK_ATTEMPTS", "2")
    try:
        return max(0, int(raw_value))
    except (TypeError, ValueError):
        return 2


def exceeded_nonquota_attempt_limit(task: dict) -> bool:
    max_attempts = max_task_attempts()
    if max_attempts <= 0:
        return False
    try:
        attempt_count = int(task.get("attempt_count") or 0)
    except (TypeError, ValueError):
        attempt_count = 0
    if attempt_count <= max_attempts:
        return False
    last_error = str(task.get("last_error") or "").strip()
    return not is_quota_error(last_error)


def fetch_task_retry_state(client: Client, task_id: str) -> dict:
    if not task_id:
        return {}
    response = (
        client.table("paper_stage_tasks")
        .select("id,attempt_count,last_error")
        .eq("id", task_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else {}


def update_paper_processing_state(
    client: Client,
    *,
    paper_id: int,
    stage_key: str,
    preserve_human_route: bool,
) -> None:
    payload = {
        "current_stage_key": stage_key,
        "routing_updated_at": _utcnow_iso(),
    }
    if not preserve_human_route:
        payload["routing_status"] = ROUTING_STATUS_PROCESSING
        payload["route_destination"] = BLOCKED_DESTINATION
    client.table("papers").update(payload).eq("id", paper_id).execute()


def mark_task_completed(client: Client, task_id: str) -> None:
    client.table("paper_stage_tasks").update(
        {
            "status": "completed",
            "last_error": None,
            "completed_at": _utcnow_iso(),
            "updated_at": _utcnow_iso(),
        }
    ).eq("id", task_id).execute()


def mark_task_requeued_after_error(client: Client, *, task_id: str, error_text: str) -> None:
    client.table("paper_stage_tasks").update(
        {
            "status": "queued",
            "last_error": error_text[:4000],
            "started_at": None,
            "completed_at": None,
            "updated_at": _utcnow_iso(),
        }
    ).eq("id", task_id).execute()


def mark_task_requeued_after_quota_error(
    client: Client,
    *,
    task_id: str,
    task: dict,
    error_text: str,
) -> None:
    try:
        previous_attempt_count = max(0, int(task.get("attempt_count") or 1) - 1)
    except (TypeError, ValueError):
        previous_attempt_count = 0
    client.table("paper_stage_tasks").update(
        {
            "status": "queued",
            "attempt_count": previous_attempt_count,
            "last_error": error_text[:4000],
            "started_at": None,
            "completed_at": None,
            "updated_at": _utcnow_iso(),
        }
    ).eq("id", task_id).execute()


def mark_task_failed_after_error(client: Client, *, task_id: str, error_text: str) -> None:
    client.table("paper_stage_tasks").update(
        {
            "status": "failed",
            "last_error": error_text[:4000],
            "started_at": None,
            "completed_at": None,
            "updated_at": _utcnow_iso(),
        }
    ).eq("id", task_id).execute()


def enqueue_followup_stage_task(
    client: Client,
    *,
    paper_id: int,
    stage_key: str,
    priority: int,
) -> None:
    existing_response = (
        client.table("paper_stage_tasks")
        .select("id,status")
        .eq("paper_id", paper_id)
        .eq("stage_key", stage_key)
        .limit(1)
        .execute()
    )
    existing = existing_response.data[0] if existing_response.data else None
    existing_status = str((existing or {}).get("status") or "").strip().lower()
    if existing_status in {"queued", "processing"}:
        return
    client.table("paper_stage_tasks").upsert(
        {
            "paper_id": paper_id,
            "stage_key": stage_key,
            "status": "queued",
            "priority": int(priority),
            "last_error": None,
            "started_at": None,
            "completed_at": None,
            "updated_at": _utcnow_iso(),
        },
        on_conflict="paper_id,stage_key",
    ).execute()


def score_followup_priority(*, ai_result, normalization_summary: dict, normalized_payload_json: dict) -> int:
    confidence_values = []
    for field in ("overall_confidence", "paper_decision_confidence", "extraction_confidence"):
        try:
            confidence_values.append(float(getattr(ai_result, field, 0.0) or 0.0))
        except (TypeError, ValueError):
            continue
    confidence = max(confidence_values) if confidence_values else 0.0
    accepted_rows = int(normalization_summary.get("accepted_row_count") or 0)
    rejected_rows = int(normalization_summary.get("rejected_row_count") or 0)
    unmapped_foods = int(normalization_summary.get("unmapped_food_count") or 0)
    unmapped_nutrients = int(normalization_summary.get("unmapped_nutrient_count") or 0)
    evidence_rows = 0
    per_100g_rows = 0
    for food_item in normalized_payload_json.get("food_items") or []:
        if not isinstance(food_item, dict):
            continue
        for nutrient in food_item.get("nutrients") or []:
            if not isinstance(nutrient, dict):
                continue
            metadata = nutrient.get("metadata") if isinstance(nutrient.get("metadata"), dict) else {}
            if nutrient.get("source_citation") or metadata.get("table_label") or metadata.get("source_quote"):
                evidence_rows += 1
            unit = str(nutrient.get("unit") or "").strip().lower()
            basis = str(nutrient.get("basis") or "").strip().lower()
            if unit.endswith("/100g") or unit == "%" or basis == "per_100g":
                per_100g_rows += 1
    signal_text = " ".join(
        str(value or "")
        for value in (
            getattr(ai_result, "reasoning", ""),
            getattr(ai_result, "paper_type", ""),
            getattr(ai_result, "database_value", ""),
        )
    ).casefold()
    direct_fit_bonus = 0
    if any(marker in signal_text for marker in ("food composition", "proximate composition", "nutritional composition", "ordinary_food_composition")):
        direct_fit_bonus += 40
    if any(marker in signal_text for marker in ("food product", "real-world food", "commercial product", "database_value\": \"high", "database value high")):
        direct_fit_bonus += 20
    penalty = 0
    penalty_markers = (
        ("review", 35),
        ("meta-analysis", 35),
        ("database aggregate", 35),
        ("food composition database", 20),
        ("feed", 30),
        ("digestibility", 30),
        ("sensory", 25),
        ("outcome", 25),
        ("biomarker", 25),
        ("one-off formulation", 35),
        ("experimental formulation", 30),
        ("treatment", 20),
        ("supplement", 20),
    )
    for marker, weight in penalty_markers:
        if marker in signal_text:
            penalty += weight
    score = (
        120 * confidence
        + min(120, accepted_rows * 6)
        + min(60, evidence_rows * 4)
        + min(50, per_100g_rows * 3)
        + direct_fit_bonus
        - min(60, rejected_rows * 5)
        - min(30, (unmapped_foods + unmapped_nutrients) * 2)
        - min(120, penalty)
    )
    return max(-1000, min(1000, int(round(score))))


def _raw_has_data_decision(ai_result) -> bool:
    raw_decision_kind = getattr(ai_result, "decision_kind", "")
    decision_kind = raw_decision_kind.strip().lower() if isinstance(raw_decision_kind, str) else ""
    if decision_kind:
        return decision_kind == "has_data"
    return bool(getattr(ai_result, "is_useful", False))


def _strong_raw_has_data_decision(ai_result) -> bool:
    if not _raw_has_data_decision(ai_result):
        return False
    confidence_values = []
    for field in ("overall_confidence", "paper_decision_confidence"):
        try:
            confidence_values.append(float(getattr(ai_result, field, 0.0) or 0.0))
        except (TypeError, ValueError):
            continue
    confidence = max(confidence_values) if confidence_values else 0.0
    return confidence >= 0.85


def finalize_ai_outcome(
    client: Client,
    *,
    paper_id: int,
    decision_kind: str,
    payload_json: dict,
    stage_config: RoutingStageConfig,
    source_confidence: float,
) -> None:
    payload_text, payload_hash = payload_text_and_hash(payload_json)
    upsert_payload = {
        "paper_id": paper_id,
        "decision_kind": decision_kind,
        "resolution_source": "ai_high_confidence",
        "payload_json": payload_json,
        "payload_text": payload_text,
        "payload_hash": payload_hash,
        "slot_submission_a_id": None,
        "slot_submission_b_id": None,
        "resolved_submission_id": None,
        "conflict_id": None,
        "resolved_by": None,
        "resolved_at": _utcnow_iso(),
        "updated_at": _utcnow_iso(),
        "truth_source_kind": "ai_model",
        "source_stage_key": stage_config.stage_key,
        "source_model_name": stage_config.model_name,
        "source_confidence": source_confidence,
        "training_weight": None,
    }
    client.table("paper_review_outcomes").upsert(upsert_payload, on_conflict="paper_id").execute()


def insert_ai_extraction(
    client: Client,
    *,
    paper_id: int,
    stage_config: RoutingStageConfig,
    ai_result,
    input_hash: str,
    normalized_payload_json: dict,
    normalization_summary: dict,
    routing_bucket: str,
    route_destination: str,
    audit_sampled: bool,
    finalized_without_human: bool,
) -> dict:
    payload = {
        "paper_id": paper_id,
        "stage_key": stage_config.stage_key,
        "prompt_version": stage_config.prompt_version,
        "input_hash": input_hash,
        "model_name": stage_config.model_name,
        "is_useful": ai_result.is_useful,
        "reasoning": ai_result.reasoning,
        "overall_confidence": ai_result.overall_confidence,
        "raw_data": {
            "raw_response_text": ai_result.raw_response_text,
            "parsed_result": {
                "reasoning": ai_result.reasoning,
                "is_useful": ai_result.is_useful,
                "decision_kind": getattr(ai_result, "decision_kind", None),
                "no_data_reason": getattr(ai_result, "no_data_reason", None),
                "paper_type": getattr(ai_result, "paper_type", None),
                "database_value": getattr(ai_result, "database_value", None),
                "paper_decision_confidence": getattr(ai_result, "paper_decision_confidence", None),
                "extraction_confidence": getattr(ai_result, "extraction_confidence", None),
                "overall_confidence": ai_result.overall_confidence,
                "data": [_serialize_ai_record(record) for record in ai_result.data],
            },
            "normalization_summary": normalization_summary,
        },
        "normalized_payload_json": normalized_payload_json,
        "positive_threshold_snapshot": stage_config.positive_threshold,
        "negative_threshold_snapshot": stage_config.negative_threshold,
        "routing_bucket": routing_bucket,
        "route_destination": route_destination,
        "audit_sampled": audit_sampled,
        "finalized_without_human": finalized_without_human,
        "status": "applied" if finalized_without_human else "pending",
    }
    response = client.table("ai_extractions").insert(payload).execute()
    if not response.data:
        raise RuntimeError(f"AI extraction insert returned no row for paper {paper_id}.")
    return response.data[0]


def _serialize_ai_record(record) -> dict:
    if is_dataclass(record):
        return asdict(record)
    if isinstance(record, dict):
        return dict(record)
    return {
        "food_name": getattr(record, "food_name", None),
        "nutrient_name": getattr(record, "nutrient_name", None),
        "amount": getattr(record, "amount", None),
        "unit": getattr(record, "unit", None),
        "basis": getattr(record, "basis", None),
        "preparation_state": getattr(record, "preparation_state", None),
        "sample_size": getattr(record, "sample_size", None),
        "confidence": getattr(record, "confidence", None),
        "source_citation": getattr(record, "source_citation", None),
        "table_label": getattr(record, "table_label", None),
        "page_hint": getattr(record, "page_hint", None),
        "source_quote": getattr(record, "source_quote", None),
        "metadata": getattr(record, "metadata", None),
        "flags": getattr(record, "flags", None),
    }


def update_paper_routing_summary(
    client: Client,
    *,
    paper_id: int,
    stage_key: str,
    routing_status: str,
    routing_bucket: str | None,
    route_destination: str,
    latest_ai_extraction_id: str | None,
) -> None:
    payload = {
        "current_stage_key": stage_key,
        "routing_status": routing_status,
        "routing_bucket": routing_bucket,
        "route_destination": route_destination,
        "latest_ai_extraction_id": latest_ai_extraction_id,
        "routing_updated_at": _utcnow_iso(),
    }
    client.table("papers").update(payload).eq("id", paper_id).execute()


def process_one_task(
    client: Client,
    *,
    task: dict,
    stage_config: RoutingStageConfig,
    evaluator: UnifiedEvaluator,
    reference_lookups: dict[str, list[dict]] | None = None,
) -> dict:
    task_id = str(task.get("id") or "").strip()
    paper_id = int(task["paper_id"])
    paper = fetch_paper(client, paper_id)
    existing_outcome = fetch_existing_outcome(client, paper_id)
    preserve_human_route = has_human_truth(existing_outcome)
    retry_state = dict(task)
    retry_state.update(fetch_task_retry_state(client, task_id))
    if exceeded_nonquota_attempt_limit(retry_state):
        error_text = (
            f"Exceeded non-quota AI task retry limit after {int(retry_state.get('attempt_count') or 0)} attempts. "
            f"Last error: {str(retry_state.get('last_error') or '').strip()[:500]}"
        )
        update_paper_routing_summary(
            client,
            paper_id=paper_id,
            stage_key=stage_config.stage_key,
            routing_status=ROUTING_STATUS_FAILED,
            routing_bucket=None,
            route_destination=BLOCKED_DESTINATION,
            latest_ai_extraction_id=paper.get("latest_ai_extraction_id"),
        )
        mark_task_failed_after_error(client, task_id=task_id, error_text=error_text)
        return {
            "paper_id": paper_id,
            "status": ROUTING_STATUS_FAILED,
            "route_destination": BLOCKED_DESTINATION,
            "error": error_text,
            "quota_limited": False,
            "permanent_model_error": False,
            "attempt_limit_exceeded": True,
        }
    update_paper_processing_state(
        client,
        paper_id=paper_id,
        stage_key=stage_config.stage_key,
        preserve_human_route=preserve_human_route,
    )

    try:
        full_text = extract_pdf_text(str(paper.get("filename") or ""))
        stage_full_text = stage_text_for_model(full_text, stage_config=stage_config)
        input_hash = input_hash_for_text(title=paper.get("title"), full_text=stage_full_text)
        if reference_lookups is not None:
            evaluator.food_candidates = select_food_candidates_for_text(
                stage_full_text,
                (reference_lookups or {}).get("foods") or [],
            )
        task_timeout_seconds = int(
            os.environ.get(
                "AI_MODEL_TASK_TIMEOUT_SECONDS",
                os.environ.get("GEMINI_REQUEST_TIMEOUT_SECONDS", "300"),
            )
        )
        with ai_task_timeout(task_timeout_seconds):
            ai_result = evaluator.evaluate_and_extract(
                {
                    "pmc_id": paper.get("doi") or paper.get("filename") or "",
                    "title": paper.get("title") or "",
                    "full_text": stage_full_text,
                }
            )
        embedded_error = ai_result_error(ai_result)
        if embedded_error:
            raise RuntimeError(embedded_error)
        normalization = normalize_ai_payload_with_summary(
            is_useful=ai_result.is_useful,
            records=ai_result.data,
            nutrient_lookup=(reference_lookups or {}).get("nutrients") or [],
            food_lookup=(reference_lookups or {}).get("foods") or [],
        )
        normalized_payload_json = normalization.payload
        normalized_is_useful = normalization.has_data
        followup_stage_key = str(stage_config.next_stage_on_has_data or "").strip()
        strong_raw_followup = (
            bool(followup_stage_key)
            and not preserve_human_route
            and not normalized_is_useful
            and _strong_raw_has_data_decision(ai_result)
        )
        routing_is_useful = normalized_is_useful or strong_raw_followup
        routing_bucket = classify_routing_bucket(
            is_useful=routing_is_useful,
            overall_confidence=ai_result.overall_confidence,
            positive_threshold=stage_config.positive_threshold,
            negative_threshold=stage_config.negative_threshold,
        )
        audit_sampled = stable_audit_sample(
            paper_id=paper_id,
            stage_key=stage_config.stage_key,
            model_name=stage_config.model_name,
            audit_rate=stage_config.audit_rate,
        )
        routing_status, route_destination, finalized_without_human = route_bucket(
            routing_bucket=routing_bucket,
            audit_sampled=audit_sampled,
            has_human_truth=preserve_human_route,
        )
        followup_priority = score_followup_priority(
            ai_result=ai_result,
            normalization_summary=normalization.summary(),
            normalized_payload_json=normalized_payload_json,
        )
        actual_route_destination = route_destination
        actual_finalized_without_human = finalized_without_human
        if (normalized_is_useful or strong_raw_followup) and followup_stage_key and not preserve_human_route:
            actual_route_destination = NEXT_STAGE_DESTINATION
            actual_finalized_without_human = False
        elif (
            not normalized_is_useful
            and stage_config.no_data_route_destination == PROVISIONAL_SKIP_DESTINATION
            and not preserve_human_route
        ):
            actual_route_destination = PROVISIONAL_SKIP_DESTINATION
            actual_finalized_without_human = False
        extraction_row = insert_ai_extraction(
            client,
            paper_id=paper_id,
            stage_config=stage_config,
            ai_result=ai_result,
            input_hash=input_hash,
            normalized_payload_json=normalized_payload_json,
            normalization_summary=normalization.summary(),
            routing_bucket=routing_bucket,
            route_destination=actual_route_destination,
            audit_sampled=audit_sampled,
            finalized_without_human=actual_finalized_without_human,
        )
        if (normalized_is_useful or strong_raw_followup) and followup_stage_key and not preserve_human_route:
            enqueue_followup_stage_task(
                client,
                paper_id=paper_id,
                stage_key=followup_stage_key,
                priority=followup_priority,
            )
            update_paper_routing_summary(
                client,
                paper_id=paper_id,
                stage_key=followup_stage_key,
                routing_status=ROUTING_STATUS_QUEUED,
                routing_bucket=routing_bucket,
                route_destination=NEXT_STAGE_DESTINATION,
                latest_ai_extraction_id=extraction_row.get("id"),
            )
            mark_task_completed(client, task_id)
            return {
                "paper_id": paper_id,
                "status": ROUTING_STATUS_QUEUED,
                "route_destination": NEXT_STAGE_DESTINATION,
                "audit_sampled": audit_sampled,
                "finalized_without_human": False,
                "followup_stage_key": followup_stage_key,
                "followup_priority": followup_priority,
                "strong_raw_followup": strong_raw_followup,
            }
        if (
            not normalized_is_useful
            and stage_config.no_data_route_destination == PROVISIONAL_SKIP_DESTINATION
            and not preserve_human_route
        ):
            update_paper_routing_summary(
                client,
                paper_id=paper_id,
                stage_key=stage_config.stage_key,
                routing_status=ROUTING_STATUS_AI_PROVISIONAL_NO_DATA,
                routing_bucket=routing_bucket,
                route_destination=PROVISIONAL_SKIP_DESTINATION,
                latest_ai_extraction_id=extraction_row.get("id"),
            )
            mark_task_completed(client, task_id)
            return {
                "paper_id": paper_id,
                "status": ROUTING_STATUS_AI_PROVISIONAL_NO_DATA,
                "route_destination": PROVISIONAL_SKIP_DESTINATION,
                "audit_sampled": audit_sampled,
                "finalized_without_human": False,
            }
        if finalized_without_human and not preserve_human_route:
            finalize_ai_outcome(
                client,
                paper_id=paper_id,
                decision_kind=normalization.decision_kind,
                payload_json=normalized_payload_json,
                stage_config=stage_config,
                source_confidence=float(ai_result.overall_confidence or 0.0),
            )
        update_paper_routing_summary(
            client,
            paper_id=paper_id,
            stage_key=stage_config.stage_key,
            routing_status=routing_status,
            routing_bucket=routing_bucket,
            route_destination=route_destination,
            latest_ai_extraction_id=extraction_row.get("id"),
        )
        mark_task_completed(client, task_id)
        return {
            "paper_id": paper_id,
            "status": routing_status,
            "route_destination": route_destination,
            "audit_sampled": audit_sampled,
            "finalized_without_human": finalized_without_human,
        }
    except Exception as exc:
        error_text = str(exc)
        if is_non_retryable_model_error(error_text):
            update_paper_routing_summary(
                client,
                paper_id=paper_id,
                stage_key=stage_config.stage_key,
                routing_status=ROUTING_STATUS_FAILED,
                routing_bucket=None,
                route_destination=BLOCKED_DESTINATION,
                latest_ai_extraction_id=paper.get("latest_ai_extraction_id"),
            )
            mark_task_failed_after_error(client, task_id=task_id, error_text=error_text)
            return {
                "paper_id": paper_id,
                "status": ROUTING_STATUS_FAILED,
                "route_destination": BLOCKED_DESTINATION,
                "error": error_text,
                "quota_limited": False,
                "permanent_model_error": True,
            }
        update_paper_routing_summary(
            client,
            paper_id=paper_id,
            stage_key=stage_config.stage_key,
            routing_status=ROUTING_STATUS_QUEUED,
            routing_bucket=None,
            route_destination=BLOCKED_DESTINATION,
            latest_ai_extraction_id=paper.get("latest_ai_extraction_id"),
        )
        quota_limited = is_quota_error(error_text)
        if quota_limited:
            mark_task_requeued_after_quota_error(
                client,
                task_id=task_id,
                task=task,
                error_text=error_text,
            )
        else:
            mark_task_requeued_after_error(client, task_id=task_id, error_text=error_text)
        return {
            "paper_id": paper_id,
            "status": ROUTING_STATUS_QUEUED,
            "route_destination": BLOCKED_DESTINATION,
            "error": error_text,
            "quota_limited": quota_limited,
        }


def _empty_stage_summary(stage_key: str) -> dict[str, object]:
    return {
        "processed": 0,
        "finalized": 0,
        "human_ready": 0,
        "followup_queued": 0,
        "provisional_skipped": 0,
        "requeued": 0,
        "failed": 0,
        "quota_limited": False,
        "permanent_model_error": False,
        "claimed": 0,
        "stale_requeued": 0,
        "stage_key": stage_key,
    }


def _record_processing_result(summary: dict[str, object], result: dict, *, verbose: bool) -> None:
    summary["processed"] = int(summary["processed"]) + 1
    status = str(result.get("status") or "")
    if status in {"ai_finalized_has_data", "ai_finalized_no_usable_data"}:
        summary["finalized"] = int(summary["finalized"]) + 1
    elif status == ROUTING_STATUS_HUMAN_READY:
        summary["human_ready"] = int(summary["human_ready"]) + 1
    elif status == ROUTING_STATUS_QUEUED and result.get("followup_stage_key"):
        summary["followup_queued"] = int(summary["followup_queued"]) + 1
    elif status == ROUTING_STATUS_AI_PROVISIONAL_NO_DATA:
        summary["provisional_skipped"] = int(summary["provisional_skipped"]) + 1
    elif status == ROUTING_STATUS_QUEUED and result.get("error"):
        summary["requeued"] = int(summary["requeued"]) + 1
    elif status == ROUTING_STATUS_FAILED:
        summary["failed"] = int(summary["failed"]) + 1
    if result.get("quota_limited"):
        summary["quota_limited"] = True
    if result.get("permanent_model_error"):
        summary["permanent_model_error"] = True
    if verbose:
        message = f"paper={result['paper_id']} status={status} destination={result.get('route_destination')}"
        if result.get("error"):
            message += f" error={result['error']}"
        print(message)


def drain_stage_queue(
    client: Client,
    *,
    stage_key: str | None = None,
    max_tasks: int = 50,
    verbose: bool = True,
    stop_on_quota: bool = False,
    requeue_stale_minutes: int = 120,
) -> dict[str, object]:
    reference_lookups = fetch_reference_lookups(client)
    evaluator_cache: dict[str, UnifiedEvaluator] = {}
    stage_cache: dict[str, RoutingStageConfig] = {}

    def get_stage_config(current_stage_key: str | None) -> RoutingStageConfig:
        resolved_key = str(current_stage_key or "").strip()
        if resolved_key:
            if resolved_key not in stage_cache:
                stage_cache[resolved_key] = fetch_stage_config(client, resolved_key)
            return stage_cache[resolved_key]
        active_config = fetch_active_stage_config(client, None)
        stage_cache[active_config.stage_key] = active_config
        return active_config

    def get_evaluator(config: RoutingStageConfig) -> UnifiedEvaluator:
        evaluator = evaluator_cache.get(config.stage_key)
        if evaluator is None:
            evaluator = UnifiedEvaluator(
                model_name=config.model_name,
                nutrient_catalog=reference_lookups.get("nutrients") or [],
                food_candidates=[],
            )
            if evaluator.model is None:
                raise RuntimeError(f"UnifiedEvaluator could not initialize model {config.model_name}. Check GEMINI_API_KEY.")
            evaluator_cache[config.stage_key] = evaluator
        return evaluator

    initial_config = get_stage_config(stage_key)
    summary = _empty_stage_summary(stage_key or "all_queued_stages")
    summary["stale_requeued"] = requeue_stale_processing_tasks(
        client,
        stage_key=stage_key,
        stale_after_minutes=requeue_stale_minutes,
    )

    if stop_on_quota:
        while int(summary["processed"]) < max(1, max_tasks):
            claimed = claim_stage_tasks(client, stage_key=stage_key, limit=1)
            if not claimed:
                break
            summary["claimed"] = int(summary["claimed"]) + len(claimed)
            task_stage_key = claimed[0].get("stage_key") or initial_config.stage_key
            task_stage_config = get_stage_config(str(task_stage_key))
            result = process_one_task(
                client,
                task=claimed[0],
                stage_config=task_stage_config,
                evaluator=get_evaluator(task_stage_config),
                reference_lookups=reference_lookups,
            )
            _record_processing_result(summary, result, verbose=verbose)
            if result.get("quota_limited") or result.get("permanent_model_error"):
                break
        if verbose:
            print(json.dumps(summary, indent=2))
        return summary

    claimed = claim_stage_tasks(client, stage_key=stage_key, limit=max(1, max_tasks))
    summary["claimed"] = len(claimed)
    claimed = sorted(
        claimed,
        key=lambda row: (
            int(row.get("attempt_count") or 0),
            -int(row.get("priority") or 0),
            str(row.get("created_at") or ""),
            str(row.get("id") or ""),
        ),
    )
    for task in claimed[:max_tasks]:
        task_stage_key = task.get("stage_key") or initial_config.stage_key
        task_stage_config = get_stage_config(str(task_stage_key))
        result = process_one_task(
            client,
            task=task,
            stage_config=task_stage_config,
            evaluator=get_evaluator(task_stage_config),
            reference_lookups=reference_lookups,
        )
        _record_processing_result(summary, result, verbose=verbose)
    if verbose:
        print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    args = build_parser().parse_args()
    client = require_client()
    summary = drain_stage_queue(
        client,
        stage_key=args.stage_key,
        max_tasks=max(1, args.max_tasks),
        verbose=not args.json_summary,
        stop_on_quota=args.stop_on_quota,
        requeue_stale_minutes=args.requeue_stale_minutes,
    )
    if args.json_summary:
        print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
