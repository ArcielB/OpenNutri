from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PIPELINE_ROOT = PROJECT_ROOT / "services" / "data-pipeline"
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from scripts import ensure_paper_stock, refill_assignment_queue
from scripts.process_stage_queue import drain_stage_queue, require_client


TERMINAL_STOP_REASONS = {
    "daily_ai_call_budget_exhausted",
    "ai_first_task_quota_limited",
    "no_progress",
    "dry_run",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the daily recursive OpenNutri queue operation loop."
    )
    parser.add_argument("--target-open", type=int, default=50, help="Retained for stock reporting compatibility; daily ops no longer stops on this target")
    parser.add_argument("--max-cycles", type=int, default=8, help="Maximum AI/crawl cycles to run in this invocation")
    parser.add_argument("--max-ai-tasks", type=int, default=5, help="Maximum AI tasks to process in this controller invocation")
    parser.add_argument("--daily-ai-call-budget", type=int, default=20, help="Daily Gemini call budget to consume before terminal stop")
    parser.add_argument("--ai-tasks-already-used", type=int, default=0, help="Gemini calls already consumed by earlier controller invocations today")
    parser.add_argument("--refill-step-en", type=int, default=4, help="New English papers to request when needed")
    parser.add_argument("--refill-step-tr", type=int, default=4, help="New Turkish papers to request when needed")
    parser.add_argument("--seed", type=int, default=20260413, help="Random seed for assignment balancing")
    parser.add_argument("--data-dir", default="services/data-pipeline/data", help="Crawler data directory")
    parser.add_argument("--query-limit", type=int, default=50, help="Max search hits to inspect per query batch")
    parser.add_argument("--max-queries", type=int, default=80, help="Cap on query count per crawler run")
    parser.add_argument(
        "--dergipark-journal-limit",
        type=int,
        default=0,
        help="Limit DergiPark journals refreshed per cycle (0 = all)",
    )
    parser.add_argument(
        "--dergipark-max-issues-per-journal",
        type=int,
        default=12,
        help="Newest archive issues to inspect per DergiPark journal",
    )
    parser.add_argument("--skip-feedback", action="store_true", help="Skip feedback refresh before crawling")
    parser.add_argument(
        "--skip-dergipark-refresh",
        action="store_true",
        help="Skip refreshing the DergiPark journal/article index before crawling",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report planned work without writes or network jobs")
    parser.add_argument("--json-summary", action="store_true", help="Print a final JSON summary")
    return parser


def _crawler_args(args: argparse.Namespace) -> SimpleNamespace:
    return SimpleNamespace(
        data_dir=args.data_dir,
        query_limit=args.query_limit,
        max_queries=args.max_queries,
        max_ai_tasks=args.max_ai_tasks,
        dergipark_journal_limit=args.dergipark_journal_limit,
        dergipark_max_issues_per_journal=args.dergipark_max_issues_per_journal,
        skip_feedback=args.skip_feedback,
        skip_dergipark_refresh=args.skip_dergipark_refresh,
    )


def _queued_ai_paper_count(papers: list[dict]) -> int:
    return sum(
        1
        for paper in papers
        if str(paper.get("routing_status") or "").strip().lower() == "queued_for_ai"
    )


def _run_ai_drain(client: Any, args: argparse.Namespace, *, max_tasks: int) -> dict[str, object]:
    return drain_stage_queue(
        client,
        max_tasks=max(1, int(max_tasks)),
        stop_on_quota=True,
        verbose=not args.json_summary,
    )


def _assign_new_human_ready_after_ai(
    client: Any,
    args: argparse.Namespace,
    ai_summary: dict[str, object],
) -> dict[str, object] | None:
    if int(ai_summary.get("human_ready") or 0) <= 0:
        return None
    return refill_assignment_queue.assign_ready_papers(
        client,
        target_open=args.target_open,
        seed=args.seed,
        dry_run=args.dry_run,
        verbose=not args.json_summary,
    )


def _quota_stop_reason(ai_summary: dict[str, object]) -> str:
    processed = int(ai_summary.get("processed") or 0)
    successful_routes = int(ai_summary.get("human_ready") or 0) + int(ai_summary.get("finalized") or 0)
    if processed <= 1 and successful_routes <= 0:
        return "ai_first_task_quota_limited"
    return "ai_quota_limited_after_progress"


def run_daily_ops(client: Any, args: argparse.Namespace) -> dict[str, Any]:
    daily_ai_call_budget = max(1, int(getattr(args, "daily_ai_call_budget", 20)))
    ai_tasks_already_used = max(0, int(getattr(args, "ai_tasks_already_used", 0)))
    invocation_ai_task_limit = max(1, int(args.max_ai_tasks))
    ai_tasks_used = 0
    summary: dict[str, Any] = {
        "dry_run": bool(args.dry_run),
        "target_open": int(args.target_open),
        "max_ai_tasks": invocation_ai_task_limit,
        "daily_ai_call_budget": daily_ai_call_budget,
        "ai_tasks_already_used": ai_tasks_already_used,
        "ai_tasks_used": ai_tasks_used,
        "daily_ai_tasks_used": ai_tasks_already_used,
        "cycles": [],
        "stopped_reason": None,
    }

    if ai_tasks_already_used >= daily_ai_call_budget:
        summary["stopped_reason"] = "daily_ai_call_budget_exhausted"
        summary["terminal"] = True
        return summary

    for cycle in range(1, max(1, int(args.max_cycles)) + 1):
        if not args.json_summary:
            print(f"\nDaily ops cycle {cycle}")
        cycle_summary: dict[str, Any] = {"cycle": cycle}

        state = refill_assignment_queue.fetch_state(client)
        queued_before = _queued_ai_paper_count(state.get("papers", []))
        cycle_summary["queued_ai_before"] = queued_before
        remaining_daily_ai_tasks = daily_ai_call_budget - (ai_tasks_already_used + ai_tasks_used)
        remaining_invocation_ai_tasks = invocation_ai_task_limit - ai_tasks_used
        remaining_ai_tasks = min(remaining_daily_ai_tasks, remaining_invocation_ai_tasks)

        if remaining_ai_tasks <= 0:
            summary["stopped_reason"] = (
                "daily_ai_call_budget_exhausted"
                if ai_tasks_already_used + ai_tasks_used >= daily_ai_call_budget
                else "ai_run_budget_exhausted"
            )
            summary["cycles"].append(cycle_summary)
            break

        if refill_assignment_queue.has_queued_ai_work(state["papers"]):
            if args.dry_run:
                cycle_summary["ai"] = {"would_process": True}
                summary["stopped_reason"] = "dry_run"
                summary["cycles"].append(cycle_summary)
                break
            ai_summary = _run_ai_drain(client, args, max_tasks=remaining_ai_tasks)
            ai_tasks_used += int(ai_summary.get("processed") or 0)
            summary["ai_tasks_used"] = ai_tasks_used
            summary["daily_ai_tasks_used"] = ai_tasks_already_used + ai_tasks_used
            cycle_summary["ai"] = ai_summary
            if ai_summary.get("quota_limited"):
                assignment_after_ai = _assign_new_human_ready_after_ai(client, args, ai_summary)
                if assignment_after_ai is not None:
                    cycle_summary["assignment_after_ai"] = assignment_after_ai
                summary["stopped_reason"] = _quota_stop_reason(ai_summary)
                summary["cycles"].append(cycle_summary)
                break
            if int(ai_summary.get("processed") or 0) > 0:
                if ai_tasks_already_used + ai_tasks_used >= daily_ai_call_budget:
                    assignment_after_ai = _assign_new_human_ready_after_ai(client, args, ai_summary)
                    if assignment_after_ai is not None:
                        cycle_summary["assignment_after_ai"] = assignment_after_ai
                    summary["stopped_reason"] = "daily_ai_call_budget_exhausted"
                    summary["cycles"].append(cycle_summary)
                    break
                if ai_tasks_used >= invocation_ai_task_limit:
                    assignment_after_ai = _assign_new_human_ready_after_ai(client, args, ai_summary)
                    if assignment_after_ai is not None:
                        cycle_summary["assignment_after_ai"] = assignment_after_ai
                    summary["stopped_reason"] = "ai_run_budget_exhausted"
                    summary["cycles"].append(cycle_summary)
                    break
                summary["cycles"].append(cycle_summary)
                continue

        requested = {
            "en": max(0, int(args.refill_step_en)),
            "tr": max(0, int(args.refill_step_tr)),
        }
        cycle_summary["crawl_need"] = {
            "requested": requested,
            "mode": "max_ai_usage",
        }
        if requested["en"] <= 0 and requested["tr"] <= 0:
            summary["stopped_reason"] = "no_progress"
            summary["cycles"].append(cycle_summary)
            break

        if args.dry_run:
            cycle_summary["crawl"] = {"would_run": True, "requested": requested}
            summary["stopped_reason"] = "dry_run"
            summary["cycles"].append(cycle_summary)
            break

        ensure_paper_stock.run_refill_cycle(
            deficits=requested,
            env=os.environ.copy(),
            args=_crawler_args(args),
            cycle_label=f"Daily ops cycle {cycle} crawler refill",
            process_ai_after_upload=False,
        )
        cycle_summary["crawl"] = {"requested": requested}

        state_after_crawl = refill_assignment_queue.fetch_state(client)
        queued_after_crawl = _queued_ai_paper_count(state_after_crawl.get("papers", []))
        cycle_summary["queued_ai_after_crawl"] = queued_after_crawl
        if queued_after_crawl <= 0 and queued_before <= 0:
            summary["stopped_reason"] = "no_progress"
            summary["cycles"].append(cycle_summary)
            break

        remaining_daily_ai_tasks = daily_ai_call_budget - (ai_tasks_already_used + ai_tasks_used)
        remaining_invocation_ai_tasks = invocation_ai_task_limit - ai_tasks_used
        remaining_ai_tasks = min(remaining_daily_ai_tasks, remaining_invocation_ai_tasks)
        if remaining_ai_tasks <= 0:
            cycle_summary["ai_after_crawl"] = {"skipped": "run_or_daily_ai_task_budget_exhausted"}
            summary["stopped_reason"] = (
                "daily_ai_call_budget_exhausted"
                if ai_tasks_already_used + ai_tasks_used >= daily_ai_call_budget
                else "ai_run_budget_exhausted"
            )
            summary["cycles"].append(cycle_summary)
            break
        ai_summary = _run_ai_drain(client, args, max_tasks=remaining_ai_tasks)
        ai_tasks_used += int(ai_summary.get("processed") or 0)
        summary["ai_tasks_used"] = ai_tasks_used
        summary["daily_ai_tasks_used"] = ai_tasks_already_used + ai_tasks_used
        cycle_summary["ai_after_crawl"] = ai_summary
        if ai_summary.get("quota_limited"):
            assignment_after_ai = _assign_new_human_ready_after_ai(client, args, ai_summary)
            if assignment_after_ai is not None:
                cycle_summary["assignment_after_ai"] = assignment_after_ai
            summary["stopped_reason"] = _quota_stop_reason(ai_summary)
            summary["cycles"].append(cycle_summary)
            break
        if int(ai_summary.get("processed") or 0) <= 0 and queued_after_crawl <= queued_before:
            summary["stopped_reason"] = "no_progress"
            summary["cycles"].append(cycle_summary)
            break
        if int(ai_summary.get("processed") or 0) > 0 and ai_tasks_already_used + ai_tasks_used >= daily_ai_call_budget:
            assignment_after_ai = _assign_new_human_ready_after_ai(client, args, ai_summary)
            if assignment_after_ai is not None:
                cycle_summary["assignment_after_ai"] = assignment_after_ai
            summary["stopped_reason"] = "daily_ai_call_budget_exhausted"
            summary["cycles"].append(cycle_summary)
            break
        if int(ai_summary.get("processed") or 0) > 0 and ai_tasks_used >= invocation_ai_task_limit:
            assignment_after_ai = _assign_new_human_ready_after_ai(client, args, ai_summary)
            if assignment_after_ai is not None:
                cycle_summary["assignment_after_ai"] = assignment_after_ai
            summary["stopped_reason"] = "ai_run_budget_exhausted"
            summary["cycles"].append(cycle_summary)
            break

        summary["cycles"].append(cycle_summary)

    if summary["stopped_reason"] is None:
        summary["stopped_reason"] = "max_cycles"
    summary["terminal"] = summary["stopped_reason"] in TERMINAL_STOP_REASONS
    return summary


def main() -> None:
    args = build_parser().parse_args()
    client = require_client()
    summary = run_daily_ops(client, args)
    if args.json_summary:
        print(json.dumps(summary, sort_keys=True))
    else:
        print("\nDaily ops summary")
        print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
