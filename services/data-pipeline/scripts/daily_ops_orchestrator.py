from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PIPELINE_ROOT = PROJECT_ROOT / "services" / "data-pipeline"
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from scripts import ensure_paper_stock, refill_assignment_queue
from scripts.process_stage_queue import (
    drain_stage_queue,
    requeue_stale_processing_tasks,
    require_client,
)


TERMINAL_STOP_REASONS = {
    "ai_stage_configuration_error",
    "all_stage_quotas_exhausted",
    "dry_run",
    "extraction_daily_quota_exhausted",
    "max_wallclock_reached",
    "no_extraction_candidates",
    "source_exhausted",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the daily quota-draining OpenNutri queue controller."
    )
    parser.add_argument("--target-open", type=int, default=50, help="Retained for stock reporting compatibility; daily ops does not stop on visible stock")
    parser.add_argument("--max-cycles", type=int, default=8, help="Legacy compatibility option; wall-clock and quota now bound the controller")
    parser.add_argument("--max-ai-tasks", type=int, default=5, help="Legacy compatibility option; use --stage-rpm for scheduled quota pacing")
    parser.add_argument("--max-screening-tasks", type=int, default=50, help="Legacy compatibility option; use --stage-rpm for scheduled quota pacing")
    parser.add_argument("--daily-ai-call-budget", type=int, default=20, help="Legacy compatibility option; real model quota now stops the extraction stage")
    parser.add_argument("--ai-tasks-already-used", type=int, default=0, help="Legacy compatibility option retained for old callers")
    parser.add_argument("--refill-step-en", type=int, default=4, help="Legacy crawl batch size; scheduled daily ops uses --screening-refill-batch-en")
    parser.add_argument("--refill-step-tr", type=int, default=0, help="New Turkish papers to request when Turkish ops are explicitly re-enabled")
    parser.add_argument("--seed", type=int, default=20260413, help="Random seed for stock reporting compatibility")
    parser.add_argument("--data-dir", default="services/data-pipeline/data", help="Crawler data directory")
    parser.add_argument("--query-limit", type=int, default=50, help="Max search hits to inspect per query batch")
    parser.add_argument("--max-queries", type=int, default=80, help="Cap on query count per crawler run")
    parser.add_argument(
        "--sources",
        default="europepmc,openalex,semanticscholar",
        help="Comma-separated metadata sources for crawler runs. Defaults to English sources only.",
    )
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
    parser.add_argument("--screening-stage-key", default="gemma_proof_extraction_v1", help="Cheap first-pass model stage key")
    parser.add_argument("--extraction-stage-key", default="gemini_flash_db_payload_v2", help="Downstream Gemini extraction stage key")
    parser.add_argument(
        "--stage-rpm",
        default="gemma_proof_extraction_v1=15,gemini_flash_db_payload_v2=15",
        help="Comma-separated per-stage request pacing, for example stage_a=15,stage_b=15",
    )
    parser.add_argument(
        "--quota-cooldown-seconds",
        type=int,
        default=65,
        help="Seconds to sleep after an RPM window or per-minute quota event before retrying the same stage",
    )
    parser.add_argument(
        "--max-wallclock-minutes",
        type=int,
        default=330,
        help="Maximum controller runtime, leaving margin inside the 6-hour GitHub Actions job",
    )
    parser.add_argument(
        "--screening-queue-low-watermark",
        type=int,
        default=30,
        help="Refill Gemma screening work whenever queued screening tasks drop below this count",
    )
    parser.add_argument(
        "--screening-refill-batch-en",
        type=int,
        default=75,
        help="English accepted-paper crawl/upload batch size used to keep Gemma screening fed",
    )
    parser.add_argument(
        "--screening-refill-chunk-en",
        type=int,
        default=5,
        help="Largest single English crawl/upload request while refilling Gemma work",
    )
    return parser


def _crawler_args(args: argparse.Namespace) -> SimpleNamespace:
    return SimpleNamespace(
        data_dir=args.data_dir,
        query_limit=args.query_limit,
        max_queries=args.max_queries,
        max_ai_tasks=args.max_ai_tasks,
        dergipark_journal_limit=args.dergipark_journal_limit,
        dergipark_max_issues_per_journal=args.dergipark_max_issues_per_journal,
        sources=getattr(args, "sources", "europepmc,openalex,semanticscholar"),
        skip_feedback=args.skip_feedback,
        skip_dergipark_refresh=args.skip_dergipark_refresh,
    )


def _queued_ai_paper_count(papers: list[dict]) -> int:
    return sum(
        1
        for paper in papers
        if str(paper.get("routing_status") or "").strip().lower() == "queued_for_ai"
    )


def _queued_ai_paper_count_for_stage(papers: list[dict], stage_key: str) -> int:
    return sum(
        1
        for paper in papers
        if str(paper.get("routing_status") or "").strip().lower() == "queued_for_ai"
        and str(paper.get("current_stage_key") or "").strip() == stage_key
    )


def _fetch_queue_counts(client: Any, *, screening_stage_key: str, extraction_stage_key: str) -> dict[str, int]:
    state = refill_assignment_queue.fetch_state(client)
    papers = state.get("papers", [])
    queued_total = _queued_ai_paper_count(papers)
    queued_screening = _queued_ai_paper_count_for_stage(papers, screening_stage_key)
    queued_extraction = _queued_ai_paper_count_for_stage(papers, extraction_stage_key)
    if queued_total > 0 and queued_screening <= 0 and queued_extraction <= 0:
        queued_extraction = queued_total
    return {
        "total": queued_total,
        screening_stage_key: queued_screening,
        extraction_stage_key: queued_extraction,
    }


def _log(args: argparse.Namespace, message: str) -> None:
    print(f"[daily-ops] {message}", file=sys.stderr, flush=True)


def _parse_stage_rpm(raw_value: object, *, screening_stage_key: str, extraction_stage_key: str) -> dict[str, int]:
    stage_rpm = {
        screening_stage_key: 15,
        extraction_stage_key: 15,
    }
    raw = str(raw_value or "").strip()
    if not raw:
        return stage_rpm
    for chunk in raw.split(","):
        if not chunk.strip():
            continue
        if "=" not in chunk:
            raise ValueError(f"Invalid --stage-rpm entry {chunk!r}; expected stage_key=integer")
        key, value = chunk.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid --stage-rpm entry {chunk!r}; stage key is empty")
        try:
            rpm = int(value)
        except ValueError as exc:
            raise ValueError(f"Invalid --stage-rpm value for {key!r}: {value!r}") from exc
        stage_rpm[key] = max(1, rpm)
    return stage_rpm


def _run_ai_drain(
    client: Any,
    args: argparse.Namespace,
    *,
    max_tasks: int,
    stage_key: str | None = None,
) -> dict[str, object]:
    return drain_stage_queue(
        client,
        stage_key=stage_key,
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


def _new_stage_summary(stage_key: str, *, rpm: int, role: str) -> dict[str, Any]:
    return {
        "stage_key": stage_key,
        "role": role,
        "rpm": int(rpm),
        "processed": 0,
        "model_calls": 0,
        "finalized": 0,
        "human_ready": 0,
        "followup_queued": 0,
        "provisional_skipped": 0,
        "requeued": 0,
        "failed": 0,
        "claimed": 0,
        "stale_requeued": 0,
        "quota_limited": False,
        "quota_exhausted": False,
        "minute_quota_events": 0,
        "permanent_model_error": False,
        "queue_observations": [],
        "windows": [],
        "refill_cycles": 0,
        "refill_requested_en": 0,
        "refill_requested_tr": 0,
        "low_watermark_events": 0,
        "source_exhausted": False,
        "queue_empty": False,
        "stop_reason": None,
    }


def _merge_drain_summary(stage_summary: dict[str, Any], drain_summary: dict[str, object]) -> None:
    for key in (
        "processed",
        "finalized",
        "human_ready",
        "followup_queued",
        "provisional_skipped",
        "requeued",
        "failed",
        "claimed",
        "stale_requeued",
    ):
        stage_summary[key] = int(stage_summary.get(key) or 0) + int(drain_summary.get(key) or 0)
    if drain_summary.get("quota_limited"):
        stage_summary["quota_limited"] = True
    if drain_summary.get("permanent_model_error"):
        stage_summary["permanent_model_error"] = True


def _model_calls_before_quota(drain_summary: dict[str, object]) -> int:
    processed = int(drain_summary.get("processed") or 0)
    if processed <= 0:
        return 0
    if drain_summary.get("quota_limited"):
        return max(0, processed - 1)
    requeued = int(drain_summary.get("requeued") or 0)
    failed = int(drain_summary.get("failed") or 0)
    return max(0, processed - requeued - failed)


def _sleep_for_cooldown(
    *,
    args: argparse.Namespace,
    summary: dict[str, Any],
    stage_key: str,
    reason: str,
    deadline: float,
    now_fn: Callable[[], float],
    sleep_fn: Callable[[float], None],
) -> bool:
    cooldown = max(0, int(getattr(args, "quota_cooldown_seconds", 65)))
    if cooldown <= 0:
        return True
    remaining = deadline - now_fn()
    if remaining <= 0:
        return False
    sleep_seconds = min(float(cooldown), max(0.0, remaining))
    summary.setdefault("cooldowns", []).append(
        {
            "stage_key": stage_key,
            "reason": reason,
            "seconds": sleep_seconds,
        }
    )
    if not args.dry_run and sleep_seconds > 0:
        sleep_fn(sleep_seconds)
    return now_fn() < deadline


def _run_screening_refill(
    client: Any,
    args: argparse.Namespace,
    *,
    stage_summary: dict[str, Any],
    cycle_index: int,
    requested_en: int,
    requested_tr: int,
) -> None:
    del client
    requested = {
        "en": max(0, int(requested_en)),
        "tr": max(0, int(requested_tr)),
    }
    stage_summary["refill_cycles"] = int(stage_summary["refill_cycles"]) + 1
    stage_summary["refill_requested_en"] = int(stage_summary["refill_requested_en"]) + requested["en"]
    stage_summary["refill_requested_tr"] = int(stage_summary["refill_requested_tr"]) + requested["tr"]
    _log(args, f"starting crawler refill {cycle_index}: EN={requested['en']} TR={requested['tr']}")
    ensure_paper_stock.run_refill_cycle(
        deficits=requested,
        env=os.environ.copy(),
        args=_crawler_args(args),
        cycle_label=f"Daily ops Gemma refill {cycle_index}",
        process_ai_after_upload=False,
    )
    _log(args, f"finished crawler refill {cycle_index}: EN={requested['en']} TR={requested['tr']}")


def _requeue_stale_stage_tasks(
    client: Any,
    args: argparse.Namespace,
    *,
    stage_key: str,
    stage_summary: dict[str, Any],
) -> None:
    if args.dry_run:
        return
    if not hasattr(client, "table"):
        return
    stale_requeued = requeue_stale_processing_tasks(client, stage_key=stage_key)
    if stale_requeued:
        stage_summary["stale_requeued"] = int(stage_summary.get("stale_requeued") or 0) + int(stale_requeued)
        _log(args, f"requeued {stale_requeued} stale processing task(s) for {stage_key}")


def _drain_stage_quota_led(
    client: Any,
    args: argparse.Namespace,
    *,
    stage_key: str,
    role: str,
    rpm: int,
    screening_stage_key: str,
    extraction_stage_key: str,
    refill_screening: bool,
    summary: dict[str, Any],
    deadline: float,
    now_fn: Callable[[], float],
    sleep_fn: Callable[[float], None],
) -> str:
    stage_summary = _new_stage_summary(stage_key, rpm=rpm, role=role)
    summary["stage_summaries"][stage_key] = stage_summary
    low_watermark = max(0, int(getattr(args, "screening_queue_low_watermark", 30)))
    refill_chunk_en = max(
        1,
        int(
            getattr(
                args,
                "screening_refill_chunk_en",
                getattr(args, "screening_refill_batch_en", getattr(args, "refill_step_en", 75)),
            )
        ),
    )
    _log(args, f"starting stage {stage_key} role={role} rpm={rpm}")
    force_refill_next = False

    while True:
        if now_fn() >= deadline:
            stage_summary["stop_reason"] = "max_wallclock_reached"
            return "max_wallclock_reached"

        _requeue_stale_stage_tasks(
            client,
            args,
            stage_key=stage_key,
            stage_summary=stage_summary,
        )
        queue_counts = _fetch_queue_counts(
            client,
            screening_stage_key=screening_stage_key,
            extraction_stage_key=extraction_stage_key,
        )
        queue_count = int(queue_counts.get(stage_key) or 0)
        stage_summary["queue_observations"].append(
            {
                "total": queue_counts["total"],
                "queued_for_stage": queue_count,
            }
        )
        _log(args, f"{stage_key} queue observation: queued_for_stage={queue_count} total_queued_ai={queue_counts['total']}")

        if refill_screening and 0 < queue_count < low_watermark:
            _log(args, f"{stage_key} below low watermark with {queue_count} queued task(s); draining available work before refilling")

        if refill_screening and force_refill_next and queue_count > 0:
            _log(args, f"{stage_key} forcing refill before retrying requeued error-only work")

        if refill_screening and (queue_count <= 0 or force_refill_next):
            force_refill_next = False
            stage_summary["low_watermark_events"] = int(stage_summary["low_watermark_events"]) + 1
            refill_batch_en = max(0, int(getattr(args, "screening_refill_batch_en", getattr(args, "refill_step_en", 75))))
            requested_en = min(refill_batch_en, refill_chunk_en)
            requested_tr = max(0, int(getattr(args, "refill_step_tr", 0)))
            if args.dry_run:
                stage_summary["stop_reason"] = "dry_run"
                stage_summary["planned_refill"] = {
                    "en": requested_en,
                    "tr": requested_tr,
                    "queued_before": queue_count,
                }
                return "dry_run"

            if requested_en <= 0 and requested_tr <= 0:
                stage_summary["source_exhausted"] = True
                stage_summary["stop_reason"] = "source_exhausted"
                _log(args, f"{stage_key} below low watermark but no refill was requested")
                return "source_exhausted"

            _run_screening_refill(
                client,
                args,
                stage_summary=stage_summary,
                cycle_index=int(stage_summary["refill_cycles"]) + 1,
                requested_en=requested_en,
                requested_tr=requested_tr,
            )
            queue_counts = _fetch_queue_counts(
                client,
                screening_stage_key=screening_stage_key,
                extraction_stage_key=extraction_stage_key,
            )
            refreshed_count = int(queue_counts.get(stage_key) or 0)
            stage_summary["queue_observations"].append(
                {
                    "total": queue_counts["total"],
                    "queued_for_stage": refreshed_count,
                    "after_refill": True,
                }
            )
            if refreshed_count <= 0 and queue_count <= 0:
                stage_summary["source_exhausted"] = True
                stage_summary["stop_reason"] = "source_exhausted"
                _log(args, f"{stage_key} refill produced no queued work; treating source as exhausted")
                return "source_exhausted"
            queue_count = refreshed_count

        if queue_count <= 0:
            stage_summary["queue_empty"] = True
            stage_summary["stop_reason"] = "queue_empty"
            _log(args, f"{stage_key} queue empty")
            return "queue_empty"

        if args.dry_run:
            stage_summary["stop_reason"] = "dry_run"
            stage_summary["would_process"] = min(int(rpm), queue_count)
            return "dry_run"

        drain_summary = _run_ai_drain(
            client,
            args,
            max_tasks=min(int(rpm), max(1, queue_count)),
            stage_key=stage_key,
        )
        _log(
            args,
            f"{stage_key} drain window: processed={int(drain_summary.get('processed') or 0)} "
            f"human_ready={int(drain_summary.get('human_ready') or 0)} "
            f"followup_queued={int(drain_summary.get('followup_queued') or 0)} "
            f"provisional_skipped={int(drain_summary.get('provisional_skipped') or 0)} "
            f"quota_limited={bool(drain_summary.get('quota_limited'))} "
            f"permanent_model_error={bool(drain_summary.get('permanent_model_error'))}"
        )
        stage_summary["windows"].append(drain_summary)
        _merge_drain_summary(stage_summary, drain_summary)
        model_calls = _model_calls_before_quota(drain_summary)
        stage_summary["model_calls"] = int(stage_summary["model_calls"]) + model_calls
        if role == "extraction":
            summary["ai_tasks_used"] = int(summary.get("ai_tasks_used") or 0) + model_calls
            summary["daily_ai_tasks_used"] = int(summary.get("ai_tasks_already_used") or 0) + int(summary["ai_tasks_used"])

        if drain_summary.get("permanent_model_error"):
            stage_summary["stop_reason"] = "ai_stage_configuration_error"
            return "ai_stage_configuration_error"

        if drain_summary.get("quota_limited"):
            if model_calls <= 0:
                stage_summary["quota_exhausted"] = True
                stage_summary["stop_reason"] = "daily_quota_exhausted"
                summary.setdefault("quota_exhausted_stages", []).append(stage_key)
                _log(args, f"{stage_key} daily quota exhausted")
                return "daily_quota_exhausted"
            stage_summary["minute_quota_events"] = int(stage_summary["minute_quota_events"]) + 1
            _log(args, f"{stage_key} minute quota after {model_calls} successful call(s); cooling down")
            if not _sleep_for_cooldown(
                args=args,
                summary=summary,
                stage_key=stage_key,
                reason="minute_quota_after_progress",
                deadline=deadline,
                now_fn=now_fn,
                sleep_fn=sleep_fn,
            ):
                stage_summary["stop_reason"] = "max_wallclock_reached"
                return "max_wallclock_reached"
            continue

        if (
            refill_screening
            and model_calls <= 0
            and int(drain_summary.get("requeued") or 0) > 0
        ):
            force_refill_next = True
            _log(args, f"{stage_key} had only requeued error work; refilling before another retry")
            continue

        if int(drain_summary.get("processed") or 0) <= 0:
            stage_summary["stop_reason"] = "no_progress"
            _log(args, f"{stage_key} made no progress")
            return "no_progress"

        if model_calls >= int(rpm):
            _log(args, f"{stage_key} completed rpm window with {model_calls} call(s); cooling down")
            if not _sleep_for_cooldown(
                args=args,
                summary=summary,
                stage_key=stage_key,
                reason="rpm_window_complete",
                deadline=deadline,
                now_fn=now_fn,
                sleep_fn=sleep_fn,
            ):
                stage_summary["stop_reason"] = "max_wallclock_reached"
                return "max_wallclock_reached"


def _final_queue_snapshot(
    client: Any,
    *,
    screening_stage_key: str,
    extraction_stage_key: str,
) -> dict[str, int]:
    return _fetch_queue_counts(
        client,
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
    )


def _finish_summary(
    client: Any,
    summary: dict[str, Any],
    *,
    screening_stage_key: str,
    extraction_stage_key: str,
) -> dict[str, Any]:
    screening_summary = summary["stage_summaries"].get(screening_stage_key, {})
    extraction_summary = summary["stage_summaries"].get(extraction_stage_key, {})
    summary["screened"] = int(screening_summary.get("model_calls") or 0)
    summary["routed_to_gemini"] = int(screening_summary.get("followup_queued") or 0)
    summary["gemini_used"] = int(extraction_summary.get("model_calls") or 0)
    summary["human_ready"] = int(extraction_summary.get("human_ready") or 0)
    try:
        summary["remaining_queued"] = _final_queue_snapshot(
            client,
            screening_stage_key=screening_stage_key,
            extraction_stage_key=extraction_stage_key,
        )
    except Exception as exc:
        summary["remaining_queued_error"] = str(exc)
    summary["terminal"] = True
    return summary


def run_daily_ops(
    client: Any,
    args: argparse.Namespace,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
    now_fn: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    screening_stage_key = str(getattr(args, "screening_stage_key", "gemma_proof_extraction_v1") or "gemma_proof_extraction_v1")
    extraction_stage_key = str(getattr(args, "extraction_stage_key", "gemini_flash_db_payload_v2") or "gemini_flash_db_payload_v2")
    stage_rpm = _parse_stage_rpm(
        getattr(args, "stage_rpm", ""),
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
    )
    max_wallclock_minutes = max(1, int(getattr(args, "max_wallclock_minutes", 330)))
    deadline = now_fn() + max_wallclock_minutes * 60
    summary: dict[str, Any] = {
        "dry_run": bool(args.dry_run),
        "target_open": int(args.target_open),
        "screening_stage_key": screening_stage_key,
        "extraction_stage_key": extraction_stage_key,
        "stage_order": [screening_stage_key, extraction_stage_key],
        "stage_rpm": {
            screening_stage_key: int(stage_rpm.get(screening_stage_key, 15)),
            extraction_stage_key: int(stage_rpm.get(extraction_stage_key, 15)),
        },
        "quota_cooldown_seconds": max(0, int(getattr(args, "quota_cooldown_seconds", 65))),
        "max_wallclock_minutes": max_wallclock_minutes,
        "screening_queue_low_watermark": max(0, int(getattr(args, "screening_queue_low_watermark", 30))),
        "screening_refill_batch_en": max(0, int(getattr(args, "screening_refill_batch_en", 75))),
        "screening_refill_chunk_en": max(1, int(getattr(args, "screening_refill_chunk_en", 5))),
        "legacy_daily_ai_call_budget": int(getattr(args, "daily_ai_call_budget", 20)),
        "ai_tasks_already_used": max(0, int(getattr(args, "ai_tasks_already_used", 0))),
        "ai_tasks_used": 0,
        "daily_ai_tasks_used": max(0, int(getattr(args, "ai_tasks_already_used", 0))),
        "stage_summaries": {},
        "quota_exhausted_stages": [],
        "cooldowns": [],
        "stopped_reason": None,
    }

    screening_reason = _drain_stage_quota_led(
        client,
        args,
        stage_key=screening_stage_key,
        role="screening",
        rpm=int(stage_rpm.get(screening_stage_key, 15)),
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
        refill_screening=True,
        summary=summary,
        deadline=deadline,
        now_fn=now_fn,
        sleep_fn=sleep_fn,
    )

    if screening_reason in {"ai_stage_configuration_error", "dry_run", "max_wallclock_reached"}:
        summary["stopped_reason"] = screening_reason
        return _finish_summary(
            client,
            summary,
            screening_stage_key=screening_stage_key,
            extraction_stage_key=extraction_stage_key,
        )

    extraction_reason = _drain_stage_quota_led(
        client,
        args,
        stage_key=extraction_stage_key,
        role="extraction",
        rpm=int(stage_rpm.get(extraction_stage_key, 15)),
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
        refill_screening=False,
        summary=summary,
        deadline=deadline,
        now_fn=now_fn,
        sleep_fn=sleep_fn,
    )

    extraction_summary = summary["stage_summaries"].get(extraction_stage_key, {})
    assignment_after_ai = _assign_new_human_ready_after_ai(client, args, extraction_summary)
    if assignment_after_ai is not None:
        summary["assignment_after_ai"] = assignment_after_ai

    if extraction_reason in {"ai_stage_configuration_error", "dry_run", "max_wallclock_reached"}:
        summary["stopped_reason"] = extraction_reason
    elif extraction_reason == "daily_quota_exhausted":
        if screening_reason == "daily_quota_exhausted":
            summary["stopped_reason"] = "all_stage_quotas_exhausted"
        else:
            summary["stopped_reason"] = "extraction_daily_quota_exhausted"
    elif extraction_reason == "queue_empty":
        if screening_reason == "source_exhausted":
            summary["stopped_reason"] = "source_exhausted"
        else:
            summary["stopped_reason"] = "no_extraction_candidates"
    elif extraction_reason == "no_progress":
        summary["stopped_reason"] = "no_progress"
    else:
        summary["stopped_reason"] = extraction_reason or screening_reason or "no_progress"

    return _finish_summary(
        client,
        summary,
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
    )


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
