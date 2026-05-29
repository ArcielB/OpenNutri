from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from supabase import Client, create_client


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PIPELINE_ROOT = PROJECT_ROOT / "services" / "data-pipeline"
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from ai_routing import NEXT_STAGE_DESTINATION, ROUTING_STATUS_QUEUED
from scripts.process_stage_queue import is_quota_error, score_followup_priority


COMPOSITION_TITLE_MARKERS = (
    "food composition",
    "composition of",
    "nutrient composition",
    "nutritional composition",
    "chemical composition",
    "proximate composition",
    "proximate analysis",
    "mineral content",
    "vitamin content",
    "fatty acid composition",
    "amino acid composition",
)
TERMINAL_TARGET_STATUSES = {"completed", "processing"}
REQUEUEABLE_TARGET_STATUSES = {"", "failed", "cancelled"}
HUMAN_OR_READY_STATUSES = {"human_review_ready", "ai_finalized_has_data"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dry-run or apply selective recovery of high-priority Gemma candidates for Gemini extraction."
    )
    parser.add_argument("--source-stage-key", default="gemma_proof_extraction_v1")
    parser.add_argument("--target-stage-key", default="gemini_flash_db_payload_v2")
    parser.add_argument("--scan-limit", type=int, default=5000, help="Newest source-stage extraction rows to inspect.")
    parser.add_argument("--limit", type=int, default=200, help="Maximum candidates to apply or list from the ranked recovery set.")
    parser.add_argument("--min-priority", type=int, default=80, help="Minimum recomputed Gemini priority for recovery.")
    parser.add_argument("--reservoir-target", type=int, default=500, help="Soft queued Gemini candidate reservoir target.")
    parser.add_argument("--include-failed-composition-titles", action="store_true", help="Also rank failed Gemma tasks whose paper title clearly signals composition data.")
    parser.add_argument("--recompute-existing", action="store_true", default=True, help="Update priority for already queued target tasks during --apply.")
    parser.add_argument("--no-recompute-existing", action="store_false", dest="recompute_existing")
    parser.add_argument("--apply", action="store_true", help="Write queued target tasks. Without this flag the command is a dry run.")
    parser.add_argument("--json-summary", action="store_true")
    return parser


def require_client() -> Client:
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        raise SystemExit("Missing SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY.")
    return create_client(supabase_url, supabase_key)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_all(query, *, limit: int) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    remaining = max(0, int(limit))
    while remaining > 0:
        end = offset + min(remaining, 1000) - 1
        response = query.range(offset, end).execute()
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < end - offset + 1:
            break
        offset += len(batch)
        remaining -= len(batch)
    return rows


def _fetch_source_extractions(client: Client, *, source_stage_key: str, scan_limit: int) -> list[dict]:
    query = (
        client.table("ai_extractions")
        .select("id,paper_id,stage_key,model_name,is_useful,reasoning,overall_confidence,raw_data,normalized_payload_json,created_at")
        .eq("stage_key", source_stage_key)
        .order("created_at", desc=True)
    )
    return _fetch_all(query, limit=scan_limit)


def _fetch_stage_tasks(client: Client, *, stage_key: str, limit: int = 10000) -> list[dict]:
    query = (
        client.table("paper_stage_tasks")
        .select("id,paper_id,stage_key,status,priority,last_error,created_at,updated_at")
        .eq("stage_key", stage_key)
        .order("updated_at", desc=True)
    )
    return _fetch_all(query, limit=limit)


def _fetch_papers(client: Client, paper_ids: set[int]) -> dict[int, dict]:
    if not paper_ids:
        return {}
    rows: list[dict] = []
    ordered_ids = sorted(paper_ids)
    for offset in range(0, len(ordered_ids), 500):
        batch_ids = ordered_ids[offset:offset + 500]
        response = (
            client.table("papers")
            .select("id,title,routing_status,current_stage_key,route_destination,latest_ai_extraction_id")
            .in_("id", batch_ids)
            .execute()
        )
        rows.extend(response.data or [])
    return {int(row["id"]): row for row in rows if row.get("id") is not None}


def _fetch_human_outcome_paper_ids(client: Client, paper_ids: set[int]) -> set[int]:
    if not paper_ids:
        return set()
    resolved: set[int] = set()
    ordered_ids = sorted(paper_ids)
    for offset in range(0, len(ordered_ids), 500):
        batch_ids = ordered_ids[offset:offset + 500]
        response = (
            client.table("paper_review_outcomes")
            .select("paper_id,truth_source_kind")
            .in_("paper_id", batch_ids)
            .execute()
        )
        for row in response.data or []:
            if str(row.get("truth_source_kind") or "human_review").strip() == "human_review":
                resolved.add(int(row["paper_id"]))
    return resolved


def _parsed_result(row: dict) -> dict:
    raw_data = row.get("raw_data")
    if not isinstance(raw_data, dict):
        return {}
    parsed = raw_data.get("parsed_result")
    return parsed if isinstance(parsed, dict) else {}


def _normalization_summary(row: dict) -> dict:
    raw_data = row.get("raw_data")
    if not isinstance(raw_data, dict):
        return {}
    summary = raw_data.get("normalization_summary")
    return summary if isinstance(summary, dict) else {}


def _candidate_data(parsed: dict) -> list[dict]:
    data = parsed.get("data")
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _raw_positive_normalized_empty(row: dict) -> bool:
    payload = row.get("normalized_payload_json") if isinstance(row.get("normalized_payload_json"), dict) else {}
    if payload.get("decision_kind") == "has_data":
        return False
    parsed = _parsed_result(row)
    raw_decision = str(parsed.get("decision_kind") or "").strip().lower()
    raw_is_useful = bool(parsed.get("is_useful") or row.get("is_useful"))
    if raw_decision != "has_data" and not raw_is_useful:
        return False
    rows = _candidate_data(parsed)
    if rows:
        return True
    try:
        confidence = max(
            float(parsed.get("overall_confidence") or row.get("overall_confidence") or 0.0),
            float(parsed.get("paper_decision_confidence") or 0.0),
        )
    except (TypeError, ValueError):
        confidence = 0.0
    return raw_decision == "has_data" and confidence >= 0.75


def _title_has_composition_signal(title: object) -> bool:
    text = str(title or "").casefold()
    return any(marker in text for marker in COMPOSITION_TITLE_MARKERS)


def _priority_for_extraction(row: dict, paper: dict | None) -> int:
    parsed = _parsed_result(row)
    payload = row.get("normalized_payload_json") if isinstance(row.get("normalized_payload_json"), dict) else {}
    summary = _normalization_summary(row)
    ai_result = SimpleNamespace(
        is_useful=bool(parsed.get("is_useful") or row.get("is_useful")),
        decision_kind=parsed.get("decision_kind"),
        reasoning=parsed.get("reasoning") or row.get("reasoning") or "",
        paper_type=parsed.get("paper_type") or "",
        database_value=parsed.get("database_value") or "",
        overall_confidence=parsed.get("overall_confidence") or row.get("overall_confidence") or 0.0,
        paper_decision_confidence=parsed.get("paper_decision_confidence") or 0.0,
        extraction_confidence=parsed.get("extraction_confidence") or 0.0,
        raw_response_text=(row.get("raw_data") or {}).get("raw_response_text") if isinstance(row.get("raw_data"), dict) else "",
        data=_candidate_data(parsed),
    )
    return score_followup_priority(
        ai_result=ai_result,
        normalization_summary=summary,
        normalized_payload_json=payload,
        paper_title=str((paper or {}).get("title") or ""),
    )


def _failed_title_priority(task: dict, paper: dict | None) -> int:
    title = str((paper or {}).get("title") or "")
    ai_result = SimpleNamespace(
        is_useful=True,
        decision_kind="has_data",
        reasoning=f"Failed Gemma task with clear composition title. last_error={task.get('last_error') or ''}",
        paper_type="ordinary_food_composition",
        database_value="unknown",
        overall_confidence=0.55,
        paper_decision_confidence=0.55,
        extraction_confidence=0.0,
        raw_response_text="",
        data=[],
    )
    return score_followup_priority(
        ai_result=ai_result,
        normalization_summary={"accepted_row_count": 0, "rejected_row_count": 0},
        normalized_payload_json={"decision_kind": "no_usable_data", "food_items": []},
        paper_title=title,
    )


def _rank_candidates(
    *,
    source_extractions: list[dict],
    source_tasks: list[dict],
    target_tasks: dict[int, dict],
    papers: dict[int, dict],
    human_outcome_ids: set[int],
    min_priority: int,
    include_failed_composition_titles: bool,
) -> list[dict]:
    candidates: dict[int, dict] = {}
    for row in source_extractions:
        paper_id = row.get("paper_id")
        if paper_id is None:
            continue
        paper_id = int(paper_id)
        paper = papers.get(paper_id)
        if paper_id in human_outcome_ids:
            continue
        if str((paper or {}).get("routing_status") or "") in HUMAN_OR_READY_STATUSES:
            continue
        target = target_tasks.get(paper_id)
        target_status = str((target or {}).get("status") or "").strip().lower()
        if target_status in TERMINAL_TARGET_STATUSES:
            continue
        if not _raw_positive_normalized_empty(row):
            continue
        priority = _priority_for_extraction(row, paper)
        if priority < min_priority:
            continue
        candidates[paper_id] = {
            "paper_id": paper_id,
            "priority": priority,
            "reason": "raw_positive_normalized_empty",
            "title": (paper or {}).get("title"),
            "source_extraction_id": row.get("id"),
            "target_task_status": target_status or None,
            "target_task_priority": (target or {}).get("priority"),
        }

    if include_failed_composition_titles:
        for task in source_tasks:
            if str(task.get("status") or "").strip().lower() != "failed":
                continue
            if is_quota_error(task.get("last_error")):
                continue
            paper_id = task.get("paper_id")
            if paper_id is None or int(paper_id) in candidates:
                continue
            paper_id = int(paper_id)
            paper = papers.get(paper_id)
            if paper_id in human_outcome_ids:
                continue
            if not _title_has_composition_signal((paper or {}).get("title")):
                continue
            target = target_tasks.get(paper_id)
            target_status = str((target or {}).get("status") or "").strip().lower()
            if target_status in TERMINAL_TARGET_STATUSES:
                continue
            priority = _failed_title_priority(task, paper)
            if priority < min_priority:
                continue
            candidates[paper_id] = {
                "paper_id": paper_id,
                "priority": priority,
                "reason": "failed_composition_title",
                "title": (paper or {}).get("title"),
                "source_task_id": task.get("id"),
                "target_task_status": target_status or None,
                "target_task_priority": (target or {}).get("priority"),
            }

    ranked = sorted(
        candidates.values(),
        key=lambda row: (-int(row.get("priority") or 0), str(row.get("title") or ""), int(row.get("paper_id") or 0)),
    )
    return ranked


def _apply_candidates(
    client: Client,
    *,
    candidates: list[dict],
    target_stage_key: str,
    recompute_existing: bool,
) -> dict[str, int]:
    counts = {"queued": 0, "priority_updated": 0, "skipped_existing": 0}
    now = _utcnow_iso()
    for candidate in candidates:
        paper_id = int(candidate["paper_id"])
        target_status = str(candidate.get("target_task_status") or "").strip().lower()
        target_priority = candidate.get("target_task_priority")
        priority = int(candidate.get("priority") or 0)
        if target_status == "queued":
            if recompute_existing and int(target_priority or 0) != priority:
                client.table("paper_stage_tasks").update(
                    {
                        "priority": priority,
                        "updated_at": now,
                    }
                ).eq("paper_id", paper_id).eq("stage_key", target_stage_key).execute()
                counts["priority_updated"] += 1
            else:
                counts["skipped_existing"] += 1
            continue
        if target_status not in REQUEUEABLE_TARGET_STATUSES:
            counts["skipped_existing"] += 1
            continue
        client.table("paper_stage_tasks").upsert(
            {
                "paper_id": paper_id,
                "stage_key": target_stage_key,
                "status": "queued",
                "priority": priority,
                "last_error": None,
                "started_at": None,
                "completed_at": None,
                "updated_at": now,
            },
            on_conflict="paper_id,stage_key",
        ).execute()
        client.table("papers").update(
            {
                "current_stage_key": target_stage_key,
                "routing_status": ROUTING_STATUS_QUEUED,
                "route_destination": NEXT_STAGE_DESTINATION,
                "routing_updated_at": now,
            }
        ).eq("id", paper_id).execute()
        counts["queued"] += 1
    return counts


def run_recovery(client: Client, args: argparse.Namespace) -> dict[str, Any]:
    source_extractions = _fetch_source_extractions(
        client,
        source_stage_key=args.source_stage_key,
        scan_limit=max(1, int(args.scan_limit)),
    )
    source_tasks = _fetch_stage_tasks(client, stage_key=args.source_stage_key) if args.include_failed_composition_titles else []
    target_task_rows = _fetch_stage_tasks(client, stage_key=args.target_stage_key)
    target_tasks = {
        int(row["paper_id"]): row
        for row in target_task_rows
        if row.get("paper_id") is not None
    }
    paper_ids = {
        int(row["paper_id"])
        for row in source_extractions + source_tasks
        if row.get("paper_id") is not None
    }
    papers = _fetch_papers(client, paper_ids)
    human_outcome_ids = _fetch_human_outcome_paper_ids(client, paper_ids)
    ranked = _rank_candidates(
        source_extractions=source_extractions,
        source_tasks=source_tasks,
        target_tasks=target_tasks,
        papers=papers,
        human_outcome_ids=human_outcome_ids,
        min_priority=max(-1000, int(args.min_priority)),
        include_failed_composition_titles=bool(args.include_failed_composition_titles),
    )
    queued_target_count = sum(1 for row in target_task_rows if str(row.get("status") or "").strip().lower() == "queued")
    reservoir_deficit = max(0, int(args.reservoir_target) - queued_target_count)
    requested_limit = max(0, int(args.limit))
    apply_limit = min(requested_limit, 200) if args.apply else requested_limit
    selected_limit = min(apply_limit, len(ranked))
    selected = ranked[:selected_limit]
    apply_counts = {"queued": 0, "priority_updated": 0, "skipped_existing": 0}
    if args.apply and selected:
        apply_counts = _apply_candidates(
            client,
            candidates=selected,
            target_stage_key=args.target_stage_key,
            recompute_existing=bool(args.recompute_existing),
        )
    return {
        "dry_run": not bool(args.apply),
        "source_stage_key": args.source_stage_key,
        "target_stage_key": args.target_stage_key,
        "scan_limit": int(args.scan_limit),
        "source_extractions_scanned": len(source_extractions),
        "source_failed_tasks_scanned": len(source_tasks),
        "queued_target_count": queued_target_count,
        "reservoir_target": int(args.reservoir_target),
        "reservoir_deficit": reservoir_deficit,
        "min_priority": int(args.min_priority),
        "ranked_candidate_count": len(ranked),
        "selected_count": len(selected),
        "apply_limit_capped_at": 200 if args.apply else None,
        "apply_counts": apply_counts,
        "top_candidates": selected[:25],
    }


def main() -> None:
    args = build_parser().parse_args()
    client = require_client()
    summary = run_recovery(client, args)
    if args.json_summary:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
