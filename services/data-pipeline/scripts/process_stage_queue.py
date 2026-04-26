from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict
from dataclasses import is_dataclass
from datetime import datetime, timezone
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
    ROUTING_STATUS_HUMAN_READY,
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


def claim_stage_tasks(client: Client, *, stage_key: str, limit: int) -> list[dict]:
    response = client.rpc(
        "claim_paper_stage_tasks",
        {"p_stage_key": stage_key, "p_limit": max(1, int(limit))},
    ).execute()
    return response.data or []


def fetch_reference_lookups(client: Client) -> dict[str, list[dict]]:
    return {
        "nutrients": _fetch_all_rows(client, "master_nutrients", "id,standard_name"),
        "foods": _fetch_all_rows(client, "entities", "id,canonical_name"),
    }


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
    update_paper_processing_state(
        client,
        paper_id=paper_id,
        stage_key=stage_config.stage_key,
        preserve_human_route=preserve_human_route,
    )

    try:
        full_text = extract_pdf_text(str(paper.get("filename") or ""))
        input_hash = input_hash_for_text(title=paper.get("title"), full_text=full_text)
        ai_result = evaluator.evaluate_and_extract(
            {
                "pmc_id": paper.get("doi") or paper.get("filename") or "",
                "title": paper.get("title") or "",
                "full_text": full_text,
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
        routing_bucket = classify_routing_bucket(
            is_useful=normalized_is_useful,
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
        extraction_row = insert_ai_extraction(
            client,
            paper_id=paper_id,
            stage_config=stage_config,
            ai_result=ai_result,
            input_hash=input_hash,
            normalized_payload_json=normalized_payload_json,
            normalization_summary=normalization.summary(),
            routing_bucket=routing_bucket,
            route_destination=route_destination,
            audit_sampled=audit_sampled,
            finalized_without_human=finalized_without_human,
        )
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
        update_paper_routing_summary(
            client,
            paper_id=paper_id,
            stage_key=stage_config.stage_key,
            routing_status=ROUTING_STATUS_QUEUED,
            routing_bucket=None,
            route_destination=BLOCKED_DESTINATION,
            latest_ai_extraction_id=paper.get("latest_ai_extraction_id"),
        )
        mark_task_requeued_after_error(client, task_id=task_id, error_text=error_text)
        return {
            "paper_id": paper_id,
            "status": ROUTING_STATUS_QUEUED,
            "route_destination": BLOCKED_DESTINATION,
            "error": error_text,
            "quota_limited": is_quota_error(error_text),
        }


def _empty_stage_summary(stage_key: str) -> dict[str, object]:
    return {
        "processed": 0,
        "finalized": 0,
        "human_ready": 0,
        "requeued": 0,
        "failed": 0,
        "quota_limited": False,
        "claimed": 0,
        "stage_key": stage_key,
    }


def _record_processing_result(summary: dict[str, object], result: dict, *, verbose: bool) -> None:
    summary["processed"] = int(summary["processed"]) + 1
    status = str(result.get("status") or "")
    if status in {"ai_finalized_has_data", "ai_finalized_no_usable_data"}:
        summary["finalized"] = int(summary["finalized"]) + 1
    elif status == ROUTING_STATUS_HUMAN_READY:
        summary["human_ready"] = int(summary["human_ready"]) + 1
    elif status == ROUTING_STATUS_QUEUED and result.get("error"):
        summary["requeued"] = int(summary["requeued"]) + 1
    if result.get("quota_limited"):
        summary["quota_limited"] = True
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
) -> dict[str, object]:
    stage_config = fetch_active_stage_config(client, stage_key or None)
    evaluator = UnifiedEvaluator(model_name=stage_config.model_name)
    if evaluator.model is None:
        raise RuntimeError("UnifiedEvaluator could not initialize a Gemini model. Check GEMINI_API_KEY.")
    reference_lookups = fetch_reference_lookups(client)
    summary = _empty_stage_summary(stage_config.stage_key)

    if stop_on_quota:
        while int(summary["processed"]) < max(1, max_tasks):
            claimed = claim_stage_tasks(client, stage_key=stage_config.stage_key, limit=1)
            if not claimed:
                break
            summary["claimed"] = int(summary["claimed"]) + len(claimed)
            result = process_one_task(
                client,
                task=claimed[0],
                stage_config=stage_config,
                evaluator=evaluator,
                reference_lookups=reference_lookups,
            )
            _record_processing_result(summary, result, verbose=verbose)
            if result.get("quota_limited"):
                break
        if verbose:
            print(json.dumps(summary, indent=2))
        return summary

    claimed = claim_stage_tasks(client, stage_key=stage_config.stage_key, limit=max(1, max_tasks))
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
        result = process_one_task(
            client,
            task=task,
            stage_config=stage_config,
            evaluator=evaluator,
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
    )
    if args.json_summary:
        print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
