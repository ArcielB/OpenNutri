from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PIPELINE_ROOT = PROJECT_ROOT / "services" / "data-pipeline"
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from scripts.process_stage_queue import drain_stage_queue, fetch_active_stage_config, require_client
from scripts.upload_to_supabase import _enqueue_stage_task
from ai_routing import BLOCKED_DESTINATION, ROUTING_STATUS_QUEUED


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill staged AI routing for existing papers.")
    parser.add_argument("--stage-key", default=None, help="Specific stage key to backfill. Defaults to the active stage.")
    parser.add_argument("--max-tasks", type=int, default=5000, help="Maximum queued tasks to process in this run.")
    parser.add_argument(
        "--reset-open-human-assignments",
        action="store_true",
        help=(
            "Cancel unresolved human assignments and force all existing papers back into queued AI routing. "
            "This reset mode queues only by default; run process_stage_queue.py separately to drain."
        ),
    )
    parser.add_argument(
        "--drain-after-reset",
        action="store_true",
        help="Immediately drain the AI queue after --reset-open-human-assignments.",
    )
    return parser


def _fetch_rows(client, table: str, select: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        response = client.table(table).select(select).range(offset, offset + 999).execute()
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < 1000:
            return rows
        offset += 1000


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def enqueue_missing_stage_tasks(client, *, stage_config) -> int:
    papers = _fetch_rows(client, "papers", "id,filter_score")
    outcomes = _fetch_rows(client, "paper_review_outcomes", "paper_id,truth_source_kind")
    tasks = (
        client.table("paper_stage_tasks")
        .select("paper_id,status")
        .eq("stage_key", stage_config.stage_key)
        .execute()
    )
    task_by_paper_id = {
        int(row["paper_id"]): str(row.get("status") or "").strip().lower()
        for row in (tasks.data or [])
        if row.get("paper_id") is not None
    }
    human_truth_ids = {
        int(row["paper_id"])
        for row in outcomes
        if row.get("paper_id") is not None
        and str(row.get("truth_source_kind") or "human_review").strip().lower() == "human_review"
    }
    enqueued = 0
    for paper in papers:
        paper_id = int(paper["id"])
        existing_status = task_by_paper_id.get(paper_id)
        if existing_status == "completed":
            continue
        _enqueue_stage_task(
            client,
            paper_id=paper_id,
            stage_config=stage_config,
            filter_score=paper.get("filter_score"),
            preserve_human_route=paper_id in human_truth_ids,
        )
        if existing_status not in {"queued", "processing"}:
            enqueued += 1
    return enqueued


def _priority_for_filter_score(filter_score: object) -> int:
    try:
        return int(round(float(filter_score or 0) * 100))
    except (TypeError, ValueError):
        return 0


def _human_work_blockers(client) -> dict[str, set[int]]:
    submissions = _fetch_rows(client, "paper_assignment_submissions", "paper_id")
    outcomes = _fetch_rows(client, "paper_review_outcomes", "paper_id,truth_source_kind")
    submitted_paper_ids = {
        int(row["paper_id"])
        for row in submissions
        if row.get("paper_id") is not None
    }
    human_outcome_paper_ids = {
        int(row["paper_id"])
        for row in outcomes
        if row.get("paper_id") is not None
        and str(row.get("truth_source_kind") or "human_review").strip().lower() == "human_review"
    }
    return {
        "assignment_submissions": submitted_paper_ids,
        "human_review_outcomes": human_outcome_paper_ids,
    }


def assert_no_human_work_to_discard(client) -> None:
    blockers = _human_work_blockers(client)
    blocking_counts = {name: len(paper_ids) for name, paper_ids in blockers.items() if paper_ids}
    if not blocking_counts:
        return
    detail = ", ".join(f"{name}={count}" for name, count in sorted(blocking_counts.items()))
    raise RuntimeError(f"Refusing to reset AI routing because submitted or human-truth work exists: {detail}")


def cancel_unresolved_human_assignments(client) -> dict[str, int]:
    slot_assignments = _fetch_rows(client, "paper_slot_assignments", "id,status")
    user_assignments = _fetch_rows(client, "paper_user_assignments", "id,status")

    slot_cancelled = 0
    for row in slot_assignments:
        status = str(row.get("status") or "").strip().lower()
        if status in {"resolved", "cancelled"}:
            continue
        client.table("paper_slot_assignments").update(
            {"status": "cancelled", "official_submission_id": None, "resolved_at": _utcnow_iso()}
        ).eq("id", row["id"]).execute()
        slot_cancelled += 1

    user_cancelled = 0
    for row in user_assignments:
        status = str(row.get("status") or "").strip().lower()
        if status in {"resolved", "cancelled"}:
            continue
        client.table("paper_user_assignments").update(
            {"status": "cancelled", "resolved_at": _utcnow_iso()}
        ).eq("id", row["id"]).execute()
        user_cancelled += 1

    return {
        "slot_assignments": slot_cancelled,
        "user_assignments": user_cancelled,
    }


def force_enqueue_existing_papers_for_ai(client, *, stage_config) -> int:
    papers = _fetch_rows(client, "papers", "id,filter_score")
    now = _utcnow_iso()
    enqueued = 0
    for paper in papers:
        paper_id = int(paper["id"])
        client.table("paper_stage_tasks").upsert(
            {
                "paper_id": paper_id,
                "stage_key": stage_config.stage_key,
                "status": "queued",
                "priority": _priority_for_filter_score(paper.get("filter_score")),
                "last_error": None,
                "started_at": None,
                "completed_at": None,
                "updated_at": now,
            },
            on_conflict="paper_id,stage_key",
        ).execute()
        client.table("papers").update(
            {
                "current_stage_key": stage_config.stage_key,
                "routing_status": ROUTING_STATUS_QUEUED,
                "routing_bucket": None,
                "route_destination": BLOCKED_DESTINATION,
                "latest_ai_extraction_id": None,
                "routing_updated_at": now,
            }
        ).eq("id", paper_id).execute()
        enqueued += 1
    return enqueued


def reset_open_human_assignments_for_ai(client, *, stage_config) -> dict[str, object]:
    assert_no_human_work_to_discard(client)
    cancelled = cancel_unresolved_human_assignments(client)
    enqueued = force_enqueue_existing_papers_for_ai(client, stage_config=stage_config)
    return {"cancelled": cancelled, "enqueued": enqueued}


def cancel_unresolved_assignments_for_closed_routes(client) -> dict[str, int]:
    papers = _fetch_rows(client, "papers", "id,routing_status")
    blocked_paper_ids = {
        int(row["id"])
        for row in papers
        if row.get("id") is not None
        and str(row.get("routing_status") or "").strip().lower()
        in {"ai_failed", "ai_finalized_has_data", "ai_finalized_no_usable_data"}
    }
    if not blocked_paper_ids:
        return {"slot_assignments": 0, "user_assignments": 0, "conflicts": 0}

    slot_assignments = _fetch_rows(client, "paper_slot_assignments", "id,paper_id,status")
    user_assignments = _fetch_rows(client, "paper_user_assignments", "id,paper_id,status")
    conflicts = _fetch_rows(client, "paper_conflicts", "id,paper_id,status")

    slot_cancelled = 0
    for row in slot_assignments:
        paper_id = row.get("paper_id")
        status = str(row.get("status") or "").strip().lower()
        if paper_id not in blocked_paper_ids or status in {"resolved", "cancelled"}:
            continue
        client.table("paper_slot_assignments").update(
            {"status": "cancelled", "official_submission_id": None, "resolved_at": _utcnow_iso()}
        ).eq("id", row["id"]).execute()
        slot_cancelled += 1

    user_cancelled = 0
    for row in user_assignments:
        paper_id = row.get("paper_id")
        status = str(row.get("status") or "").strip().lower()
        if paper_id not in blocked_paper_ids or status in {"resolved", "cancelled"}:
            continue
        client.table("paper_user_assignments").update(
            {"status": "cancelled", "resolved_at": _utcnow_iso()}
        ).eq("id", row["id"]).execute()
        user_cancelled += 1

    conflicts_cancelled = 0
    for row in conflicts:
        paper_id = row.get("paper_id")
        status = str(row.get("status") or "").strip().lower()
        if paper_id not in blocked_paper_ids or status != "open":
            continue
        client.table("paper_conflicts").update(
            {"status": "cancelled", "resolved_at": _utcnow_iso()}
        ).eq("id", row["id"]).execute()
        conflicts_cancelled += 1

    return {
        "slot_assignments": slot_cancelled,
        "user_assignments": user_cancelled,
        "conflicts": conflicts_cancelled,
    }


def main() -> None:
    args = build_parser().parse_args()
    client = require_client()
    stage_config = fetch_active_stage_config(client, args.stage_key)
    if args.reset_open_human_assignments:
        reset_summary = reset_open_human_assignments_for_ai(client, stage_config=stage_config)
        enqueued = int(reset_summary["enqueued"])
        cancelled = reset_summary["cancelled"]
        if args.drain_after_reset:
            summary = drain_stage_queue(
                client,
                stage_key=stage_config.stage_key,
                max_tasks=max(1, args.max_tasks),
                verbose=True,
            )
        else:
            summary = {"processed": 0}
    else:
        enqueued = enqueue_missing_stage_tasks(client, stage_config=stage_config)
        summary = drain_stage_queue(
            client,
            stage_key=stage_config.stage_key,
            max_tasks=max(1, args.max_tasks),
            verbose=True,
        )
        cancelled = cancel_unresolved_assignments_for_closed_routes(client)
    print(
        {
            "stage_key": stage_config.stage_key,
            "enqueued": enqueued,
            "processed": summary["processed"],
            "cancelled": cancelled,
        }
    )


if __name__ == "__main__":
    main()
