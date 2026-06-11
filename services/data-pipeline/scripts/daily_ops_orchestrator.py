from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PIPELINE_ROOT = PROJECT_ROOT / "services" / "data-pipeline"
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from scripts.process_stage_queue import (
    drain_stage_queue,
    requeue_stale_processing_tasks,
    require_client,
)


class _LazyScriptModule:
    def __init__(self, module_name: str) -> None:
        object.__setattr__(self, "_module_name", module_name)
        object.__setattr__(self, "_module", None)

    def _load(self):
        module = object.__getattribute__(self, "_module")
        if module is None:
            module = importlib.import_module(f"scripts.{object.__getattribute__(self, '_module_name')}")
            object.__setattr__(self, "_module", module)
        return module

    def __getattr__(self, name: str):
        return getattr(self._load(), name)

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"_module_name", "_module"}:
            object.__setattr__(self, name, value)
        else:
            object.__setattr__(self, name, value)


cleanup_paper_storage = _LazyScriptModule("cleanup_paper_storage")
ensure_paper_stock = _LazyScriptModule("ensure_paper_stock")
refill_assignment_queue = _LazyScriptModule("refill_assignment_queue")


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
        description="Run the daily target-led OpenNutri queue controller."
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
    parser.add_argument(
        "--tick-mode",
        action="store_true",
        help="Run one resumable daily-ops tick and exit; intended for frequent GitHub cron recalls.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--controller-only",
        action="store_true",
        help="Run the serialized refill controller only: storage cleanup, stale-task requeue, active-task count, and bounded crawl/upload refill.",
    )
    mode_group.add_argument(
        "--drain-only",
        action="store_true",
        help="Run model queue draining only. This mode never crawls, uploads, or refills.",
    )
    parser.add_argument(
        "--interleave-extraction",
        action="store_true",
        help="In tick mode, also drain a bounded Gemini slice from already-ranked candidates after the Gemma slice.",
    )
    parser.add_argument("--screening-stage-key", default="gemma_proof_extraction_v1", help="Cheap first-pass model stage key")
    parser.add_argument("--extraction-stage-key", default="gemini_flash_db_payload_v2", help="Downstream Gemini extraction stage key")
    parser.add_argument(
        "--triage-stage-key",
        default="gemini_flash_lite_triage_v1",
        help="Intermediate Gemini Flash-Lite triage/re-rank stage between Gemma and final extraction. Empty string disables the 3-stage cascade.",
    )
    parser.add_argument(
        "--triage-daily-target",
        type=int,
        default=500,
        help="Flash-Lite triage calls to run each provider quota day in tick mode.",
    )
    parser.add_argument(
        "--triage-tick-tasks",
        type=int,
        default=10,
        help="Maximum Flash-Lite triage tasks to process in one tick-mode invocation.",
    )
    parser.add_argument(
        "--triage-quota-timezone",
        default=os.environ.get("OPENNUTRI_TRIAGE_QUOTA_TIMEZONE", "America/Los_Angeles"),
        help="IANA timezone whose midnight starts the Flash-Lite triage daily quota accounting window.",
    )
    parser.add_argument(
        "--stage-rpm",
        default="gemma_proof_extraction_v1=20,gemini_flash_lite_triage_v1=20,gemini_flash_db_payload_v2=15",
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
        default=0,
        help="Maximum controller runtime in minutes; 0 disables the internal wall-clock stop",
    )
    parser.add_argument(
        "--crawler-max-wallclock-seconds",
        type=int,
        default=0,
        help="Maximum crawler refill runtime in seconds; 0 disables the crawler-level wall-clock stop",
    )
    parser.add_argument(
        "--screening-daily-target",
        type=int,
        default=1500,
        help="Gemma screening calls to run each day after preloading enough queued papers",
    )
    parser.add_argument(
        "--screening-tick-tasks",
        type=int,
        default=20,
        help="Maximum Gemma tasks to process in one tick-mode invocation.",
    )
    parser.add_argument(
        "--screening-active-target",
        type=int,
        default=150,
        help="Controller-only target for active Gemma tasks, counting queued plus non-stale processing rows.",
    )
    parser.add_argument(
        "--extraction-daily-target",
        type=int,
        default=20,
        help="Gemini extraction calls to run each provider quota day in tick mode.",
    )
    parser.add_argument(
        "--extraction-tick-tasks",
        type=int,
        default=15,
        help="Maximum Gemini tasks to process in one tick-mode invocation.",
    )
    parser.add_argument(
        "--screening-queue-low-watermark",
        type=int,
        default=30,
        help="Legacy low-watermark refill threshold used only when --screening-daily-target is 0",
    )
    parser.add_argument(
        "--screening-refill-batch-en",
        type=int,
        default=150,
        help="English accepted-paper crawl/upload target used to preload Gemma screening work",
    )
    parser.add_argument(
        "--screening-refill-chunk-en",
        type=int,
        default=150,
        help="Largest single English crawl/upload request while preloading Gemma work",
    )
    parser.add_argument(
        "--screening-quota-timezone",
        default=os.environ.get("OPENNUTRI_SCREENING_QUOTA_TIMEZONE", "UTC"),
        help="IANA timezone whose midnight starts the Gemma daily quota accounting window.",
    )
    parser.add_argument(
        "--extraction-quota-timezone",
        default=os.environ.get("OPENNUTRI_EXTRACTION_QUOTA_TIMEZONE", "America/Los_Angeles"),
        help="IANA timezone whose midnight starts the Gemini daily quota accounting window.",
    )
    parser.add_argument(
        "--extraction-candidate-reservoir-target",
        type=int,
        default=500,
        help="Soft target for queued Gemini candidates; currently reported for ops visibility without evicting tasks.",
    )
    parser.add_argument(
        "--screening-prefill-stall-limit",
        type=int,
        default=3,
        help="Stop as source_exhausted after this many consecutive prefill refills do not increase queued Gemma work; 0 disables the guard",
    )
    parser.add_argument(
        "--stage-task-stale-minutes",
        type=int,
        default=120,
        help="Processing tasks older than this many minutes are stale for controller requeue and active-task counting.",
    )
    parser.add_argument(
        "--paper-storage-bucket",
        default="papers",
        help="Supabase Storage bucket that stores paper PDFs for controller cleanup and soft-limit checks.",
    )
    parser.add_argument(
        "--paper-bucket-soft-limit-mb",
        type=int,
        default=900,
        help="Skip controller refill when the paper storage bucket remains above this size after cleanup; 0 disables the limit.",
    )
    parser.add_argument(
        "--storage-cleanup-batch-size",
        type=int,
        default=100,
        help="Storage object delete batch size for controller cleanup.",
    )
    parser.add_argument(
        "--skip-storage-cleanup",
        action="store_true",
        help="Skip controller storage cleanup and soft-limit measurement.",
    )
    parser.add_argument(
        "--keep-storage-orphans",
        action="store_true",
        help="Keep orphan paper bucket objects during controller storage cleanup.",
    )
    return parser


def _crawler_args(args: argparse.Namespace) -> SimpleNamespace:
    return SimpleNamespace(
        data_dir=args.data_dir,
        query_limit=args.query_limit,
        max_queries=args.max_queries,
        crawler_max_wallclock_seconds=getattr(args, "crawler_max_wallclock_seconds", 0),
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


def _count_queued_stage_tasks(client: Any, *, stage_key: str) -> int | None:
    return _count_stage_tasks_by_status(client, stage_key=stage_key, status="queued")


def _count_queued_ai_papers(client: Any, *, stage_key: str | None = None) -> int | None:
    if not hasattr(client, "table"):
        return None
    query = (
        client.table("papers")
        .select("id", count="exact")
        .eq("routing_status", "queued_for_ai")
    )
    if stage_key is not None:
        query = query.eq("current_stage_key", stage_key)
    response = query.limit(1).execute()
    count = getattr(response, "count", None)
    if count is None:
        return None
    return int(count)


def _count_stage_tasks_by_status(
    client: Any,
    *,
    stage_key: str,
    status: str,
    started_at_gte: str | None = None,
) -> int | None:
    if not hasattr(client, "table"):
        return None
    query = (
        client.table("paper_stage_tasks")
        .select("id", count="exact")
        .eq("stage_key", stage_key)
        .eq("status", status)
    )
    if started_at_gte is not None:
        query = query.gte("started_at", started_at_gte)
    response = query.limit(1).execute()
    count = getattr(response, "count", None)
    if count is None:
        return None
    return int(count)


def _active_processing_started_cutoff_iso(*, stale_after_minutes: int) -> str | None:
    stale_after_minutes = int(stale_after_minutes)
    if stale_after_minutes <= 0:
        return None
    return (datetime.now(timezone.utc) - timedelta(minutes=stale_after_minutes)).isoformat()


def _count_active_stage_tasks(
    client: Any,
    *,
    stage_key: str,
    stale_after_minutes: int = 120,
) -> int | None:
    queued_count = _count_stage_tasks_by_status(client, stage_key=stage_key, status="queued")
    processing_count = _count_stage_tasks_by_status(
        client,
        stage_key=stage_key,
        status="processing",
        started_at_gte=_active_processing_started_cutoff_iso(stale_after_minutes=stale_after_minutes),
    )
    if queued_count is None or processing_count is None:
        return None
    return int(queued_count) + int(processing_count)


def _fetch_queue_counts(
    client: Any,
    *,
    screening_stage_key: str,
    extraction_stage_key: str,
    triage_stage_key: str | None = None,
) -> dict[str, int]:
    # Count-only queries. The previous implementation called
    # refill_assignment_queue.fetch_state, downloading every papers and
    # ai_extractions row (~9 MB per call, 3-4 calls per tick, six concurrent
    # jobs) just to derive these counts — that alone exceeded the Supabase
    # free-tier egress budget. Clients without PostgREST support (test fakes,
    # dry runs) keep the original full-state path.
    queued_total = _count_queued_ai_papers(client)
    if queued_total is None:
        state = refill_assignment_queue.fetch_state(client)
        papers = state.get("papers", [])
        queued_total = _queued_ai_paper_count(papers)
        queued_screening = _queued_ai_paper_count_for_stage(papers, screening_stage_key)
        queued_extraction = _queued_ai_paper_count_for_stage(papers, extraction_stage_key)
        queued_triage_papers = (
            _queued_ai_paper_count_for_stage(papers, triage_stage_key) if triage_stage_key else 0
        )
    else:
        queued_screening = int(_count_queued_ai_papers(client, stage_key=screening_stage_key) or 0)
        queued_extraction = int(_count_queued_ai_papers(client, stage_key=extraction_stage_key) or 0)
        queued_triage_papers = (
            int(_count_queued_ai_papers(client, stage_key=triage_stage_key) or 0)
            if triage_stage_key
            else 0
        )
    screening_task_count = _count_queued_stage_tasks(client, stage_key=screening_stage_key)
    extraction_task_count = _count_queued_stage_tasks(client, stage_key=extraction_stage_key)
    if screening_task_count is not None:
        queued_screening = screening_task_count
    if extraction_task_count is not None:
        queued_extraction = extraction_task_count
    queued_triage = 0
    triage_task_count = None
    if triage_stage_key:
        triage_task_count = _count_queued_stage_tasks(client, stage_key=triage_stage_key)
        queued_triage = (
            int(triage_task_count)
            if triage_task_count is not None
            else queued_triage_papers
        )
    if screening_task_count is not None and extraction_task_count is not None:
        queued_total = queued_screening + queued_extraction + (queued_triage if triage_stage_key else 0)
    if queued_total > 0 and queued_screening <= 0 and queued_extraction <= 0 and queued_triage <= 0:
        queued_extraction = queued_total
    counts = {
        "total": queued_total,
        screening_stage_key: queued_screening,
        extraction_stage_key: queued_extraction,
    }
    if triage_stage_key:
        counts[triage_stage_key] = queued_triage
    return counts


def _fetch_active_stage_counts(
    client: Any,
    *,
    screening_stage_key: str,
    extraction_stage_key: str,
    triage_stage_key: str | None = None,
    stale_after_minutes: int = 120,
) -> dict[str, int]:
    screening_task_count = _count_active_stage_tasks(
        client,
        stage_key=screening_stage_key,
        stale_after_minutes=stale_after_minutes,
    )
    extraction_task_count = _count_active_stage_tasks(
        client,
        stage_key=extraction_stage_key,
        stale_after_minutes=stale_after_minutes,
    )
    triage_task_count = None
    if triage_stage_key:
        triage_task_count = _count_active_stage_tasks(
            client,
            stage_key=triage_stage_key,
            stale_after_minutes=stale_after_minutes,
        )
    if screening_task_count is None or extraction_task_count is None or (triage_stage_key and triage_task_count is None):
        return _fetch_queue_counts(
            client,
            screening_stage_key=screening_stage_key,
            extraction_stage_key=extraction_stage_key,
            triage_stage_key=triage_stage_key,
        )
    counts = {
        "total": int(screening_task_count) + int(extraction_task_count) + (int(triage_task_count or 0) if triage_stage_key else 0),
        screening_stage_key: int(screening_task_count),
        extraction_stage_key: int(extraction_task_count),
    }
    if triage_stage_key:
        counts[triage_stage_key] = int(triage_task_count or 0)
    return counts


def _log(args: argparse.Namespace, message: str) -> None:
    print(f"[daily-ops] {message}", file=sys.stderr, flush=True)


def _utc_day_start_iso(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    return current.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _quota_day_start_iso(*, timezone_name: str, now: datetime | None = None) -> str:
    zone_name = str(timezone_name or "UTC").strip() or "UTC"
    try:
        zone = ZoneInfo(zone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown quota timezone {zone_name!r}") from exc
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    local_current = current.astimezone(zone)
    return local_current.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _stage_quota_day_starts(
    args: argparse.Namespace,
    *,
    screening_stage_key: str,
    extraction_stage_key: str,
    triage_stage_key: str | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    timezones = {
        screening_stage_key: str(getattr(args, "screening_quota_timezone", "UTC") or "UTC"),
        extraction_stage_key: str(getattr(args, "extraction_quota_timezone", "America/Los_Angeles") or "America/Los_Angeles"),
    }
    if triage_stage_key:
        timezones[triage_stage_key] = str(
            getattr(args, "triage_quota_timezone", "America/Los_Angeles") or "America/Los_Angeles"
        )
    starts = {
        stage_key: _quota_day_start_iso(timezone_name=timezone_name, now=now)
        for stage_key, timezone_name in timezones.items()
    }
    return starts, timezones


def _count_completed_stage_tasks_since(client: Any, *, stage_key: str, since_iso: str) -> int:
    if not hasattr(client, "table"):
        return 0
    response = (
        client.table("paper_stage_tasks")
        .select("id", count="exact")
        .eq("stage_key", stage_key)
        .eq("status", "completed")
        .gte("completed_at", since_iso)
        .limit(1)
        .execute()
    )
    count = getattr(response, "count", None)
    if count is None:
        return 0
    return int(count)


def _optional_triage_stage_key(args: argparse.Namespace) -> str | None:
    stage_key = str(getattr(args, "triage_stage_key", "") or "").strip()
    return stage_key or None


def _ordered_stage_keys(screening_stage_key: str, extraction_stage_key: str, triage_stage_key: str | None = None) -> list[str]:
    if triage_stage_key:
        return [screening_stage_key, triage_stage_key, extraction_stage_key]
    return [screening_stage_key, extraction_stage_key]


def _stage_rpm_summary(stage_order: Sequence[str], stage_rpm: dict[str, int]) -> dict[str, int]:
    return {stage_key: int(stage_rpm.get(stage_key, 15)) for stage_key in stage_order}


def _parse_stage_rpm(
    raw_value: object,
    *,
    screening_stage_key: str,
    extraction_stage_key: str,
    triage_stage_key: str | None = None,
) -> dict[str, int]:
    stage_rpm = {
        screening_stage_key: 20,
        extraction_stage_key: 15,
    }
    if triage_stage_key:
        stage_rpm[triage_stage_key] = 20
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
    requeue_stale_minutes = max(0, int(getattr(args, "stage_task_stale_minutes", 120)))
    if bool(getattr(args, "drain_only", False)):
        requeue_stale_minutes = 0
    return drain_stage_queue(
        client,
        stage_key=stage_key,
        max_tasks=max(1, int(max_tasks)),
        stop_on_quota=True,
        verbose=not args.json_summary,
        requeue_stale_minutes=requeue_stale_minutes,
    )


def _assign_new_human_ready_after_ai(
    client: Any,
    args: argparse.Namespace,
    ai_summary: dict[str, object],
) -> dict[str, object] | None:
    if int(ai_summary.get("human_ready") or 0) <= 0:
        return None
    assign_ready_papers = refill_assignment_queue.assign_ready_papers
    if not hasattr(client, "table") and type(assign_ready_papers).__module__ != "unittest.mock":
        return None
    return assign_ready_papers(
        client,
        target_open=args.target_open,
        seed=args.seed,
        dry_run=args.dry_run,
        verbose=not args.json_summary,
    )


def _new_stage_summary(stage_key: str, *, rpm: int, role: str, daily_target: int | None = None) -> dict[str, Any]:
    return {
        "stage_key": stage_key,
        "role": role,
        "rpm": int(rpm),
        "daily_target": daily_target,
        "daily_target_reached": False,
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
        "prefill_target": None,
        "prefill_satisfied": False,
        "prefill_stalled_refills": 0,
        "prefill_stall_limit": None,
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
    deadline: float | None,
    now_fn: Callable[[], float],
    sleep_fn: Callable[[float], None],
) -> bool:
    cooldown = max(0, int(getattr(args, "quota_cooldown_seconds", 65)))
    if cooldown <= 0:
        return True
    if deadline is None:
        sleep_seconds = float(cooldown)
    else:
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
    return deadline is None or now_fn() < deadline


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
    _log_crawl_outcome(args, cycle_index=cycle_index)


def _log_crawl_outcome(args: argparse.Namespace, *, cycle_index: int) -> None:
    # The orchestrator's stdout is piped through `tail -n 1` in CI to capture
    # the JSON summary, which swallows the crawler's own prints. Surface the
    # per-language crawl outcome on stderr so workflow logs show why a refill
    # did or did not produce new papers.
    payload = ensure_paper_stock._load_manifest_payload(args.data_dir)
    summary = payload.get("summary") if isinstance(payload, dict) else None
    if not isinstance(summary, dict):
        _log(args, f"crawler refill {cycle_index} outcome: no manifest summary available")
        return
    stop_reason = str((payload or {}).get("stop_reason") or "").strip()
    languages = summary.get("languages") if isinstance(summary.get("languages"), dict) else {}
    parts = []
    for language, row in sorted(languages.items()):
        if not isinstance(row, dict):
            continue
        parts.append(
            f"{language.upper()} hits={int(row.get('hits', 0))}"
            f" gate_pass={int(row.get('search_gate_pass', 0))}"
            f" metadata_pass={int(row.get('metadata_pass', 0))}"
            f" pdf_fail={int(row.get('pdf_fetch_fail', 0)) + int(row.get('pdf_validation_fail', 0))}"
            f" accepted={int(row.get('accepted', 0))}"
        )
    detail = "; ".join(parts) if parts else "no per-language stats"
    suffix = f" stop_reason={stop_reason}" if stop_reason else ""
    _log(args, f"crawler refill {cycle_index} outcome: {detail}{suffix}")


def _paper_bucket_soft_limit_bytes(args: argparse.Namespace) -> int:
    return max(0, int(getattr(args, "paper_bucket_soft_limit_mb", 900))) * 1024 * 1024


def _run_controller_storage_cleanup(client: Any, args: argparse.Namespace) -> dict[str, Any]:
    if bool(getattr(args, "skip_storage_cleanup", False)):
        return {"skipped": True}
    cleanup_args = SimpleNamespace(
        bucket=str(getattr(args, "paper_storage_bucket", "papers") or "papers"),
        statuses=",".join(sorted(cleanup_paper_storage.DEFAULT_DELETE_STATUSES)),
        keep_orphans=bool(getattr(args, "keep_storage_orphans", False)),
        batch_size=max(1, int(getattr(args, "storage_cleanup_batch_size", 100))),
        apply=not bool(getattr(args, "dry_run", False)),
        json_summary=True,
    )
    return cleanup_paper_storage.run_cleanup(client, cleanup_args)


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
    stale_requeued = requeue_stale_processing_tasks(
        client,
        stage_key=stage_key,
        stale_after_minutes=max(0, int(getattr(args, "stage_task_stale_minutes", 120))),
    )
    if stale_requeued:
        stage_summary["stale_requeued"] = int(stage_summary.get("stale_requeued") or 0) + int(stale_requeued)
        _log(args, f"requeued {stale_requeued} stale processing task(s) for {stage_key}")


def _deadline_reached(deadline: float | None, now_fn: Callable[[], float]) -> bool:
    return deadline is not None and now_fn() >= deadline


def _refill_request_size(args: argparse.Namespace, deficit: int) -> tuple[int, int]:
    deficit = max(0, int(deficit))
    refill_batch_en = max(0, int(getattr(args, "screening_refill_batch_en", getattr(args, "refill_step_en", 150))))
    refill_chunk_en = max(
        1,
        int(getattr(args, "screening_refill_chunk_en", refill_batch_en or getattr(args, "refill_step_en", 150))),
    )
    requested_en = min(deficit, refill_batch_en if refill_batch_en > 0 else deficit, refill_chunk_en)
    requested_tr = max(0, int(getattr(args, "refill_step_tr", 0)))
    return requested_en, requested_tr


def _tick_refill_request_size(args: argparse.Namespace, deficit: int) -> tuple[int, int]:
    deficit = max(0, int(deficit))
    refill_batch_en = max(0, int(getattr(args, "screening_refill_batch_en", 150)))
    refill_chunk_en = max(1, int(getattr(args, "screening_refill_chunk_en", refill_batch_en or 150)))
    requested_en = min(deficit, refill_batch_en if refill_batch_en > 0 else deficit, refill_chunk_en)
    requested_tr = max(0, int(getattr(args, "refill_step_tr", 0)))
    return requested_en, requested_tr


def _screening_tick_prefill_target(*, completed_today: int, daily_target: int, tick_tasks: int) -> int:
    remaining_today = max(0, int(daily_target) - int(completed_today))
    if remaining_today <= 0:
        return 0
    return min(remaining_today, max(1, int(tick_tasks)))


def _ensure_screening_queue_target(
    client: Any,
    args: argparse.Namespace,
    *,
    stage_key: str,
    screening_stage_key: str,
    extraction_stage_key: str,
    stage_summary: dict[str, Any],
    summary: dict[str, Any],
    target_count: int,
    deadline: float | None,
    now_fn: Callable[[], float],
) -> tuple[str, int]:
    del summary
    target_count = max(0, int(target_count))
    stage_summary["prefill_target"] = target_count
    if target_count <= 0:
        stage_summary["prefill_satisfied"] = True
        return "target_reached", 0
    stall_limit = max(0, int(getattr(args, "screening_prefill_stall_limit", 3)))
    stalled_refills = 0
    stage_summary["prefill_stall_limit"] = stall_limit

    while True:
        if _deadline_reached(deadline, now_fn):
            stage_summary["stop_reason"] = "max_wallclock_reached"
            return "max_wallclock_reached", 0

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
                "prefill": True,
                "prefill_target": target_count,
            }
        )
        _log(args, f"{stage_key} prefill observation: queued_for_stage={queue_count} target={target_count}")

        if queue_count >= target_count:
            stage_summary["prefill_satisfied"] = True
            return "target_reached", queue_count

        deficit = target_count - queue_count
        requested_en, requested_tr = _refill_request_size(args, deficit)
        if args.dry_run:
            stage_summary["stop_reason"] = "dry_run"
            stage_summary["planned_refill"] = {
                "en": requested_en,
                "tr": requested_tr,
                "queued_before": queue_count,
                "target": target_count,
            }
            return "dry_run", queue_count

        if requested_en <= 0 and requested_tr <= 0:
            stage_summary["source_exhausted"] = True
            stage_summary["stop_reason"] = "source_exhausted"
            _log(args, f"{stage_key} needs {deficit} more queued task(s), but no refill was requested")
            return "source_exhausted", queue_count

        _log(args, f"{stage_key} prefill needs {deficit} more queued task(s); crawling EN={requested_en} TR={requested_tr}")
        _run_screening_refill(
            client,
            args,
            stage_summary=stage_summary,
            cycle_index=int(stage_summary["refill_cycles"]) + 1,
            requested_en=requested_en,
            requested_tr=requested_tr,
        )
        refreshed_counts = _fetch_queue_counts(
            client,
            screening_stage_key=screening_stage_key,
            extraction_stage_key=extraction_stage_key,
        )
        refreshed_count = int(refreshed_counts.get(stage_key) or 0)
        stage_summary["queue_observations"].append(
            {
                "total": refreshed_counts["total"],
                "queued_for_stage": refreshed_count,
                "after_refill": True,
                "prefill": True,
                "prefill_target": target_count,
            }
        )
        if refreshed_count >= target_count:
            stage_summary["prefill_satisfied"] = True
            return "target_reached", refreshed_count
        if refreshed_count <= queue_count:
            stalled_refills += 1
            stage_summary["prefill_stalled_refills"] = stalled_refills
            _log(
                args,
                f"{stage_key} prefill did not increase queued work "
                f"({refreshed_count}/{target_count}); stalled_refills={stalled_refills}/{stall_limit or 'unlimited'}",
            )
            if stall_limit > 0 and stalled_refills >= stall_limit:
                stage_summary["source_exhausted"] = True
                stage_summary["stop_reason"] = "source_exhausted"
                return "source_exhausted", refreshed_count
        else:
            stalled_refills = 0


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
    deadline: float | None,
    now_fn: Callable[[], float],
    sleep_fn: Callable[[float], None],
    daily_target: int | None = None,
) -> str:
    target_limit = None if daily_target is None else max(0, int(daily_target))
    stage_summary = _new_stage_summary(stage_key, rpm=rpm, role=role, daily_target=target_limit)
    summary["stage_summaries"][stage_key] = stage_summary
    low_watermark = max(0, int(getattr(args, "screening_queue_low_watermark", 30)))
    _log(args, f"starting stage {stage_key} role={role} rpm={rpm} daily_target={target_limit}")
    force_refill_next = False

    while True:
        if target_limit is not None and int(stage_summary.get("model_calls") or 0) >= target_limit:
            stage_summary["daily_target_reached"] = True
            stage_summary["stop_reason"] = "daily_target_reached"
            _log(args, f"{stage_key} daily target reached: {target_limit} model call(s)")
            return "daily_target_reached"

        if _deadline_reached(deadline, now_fn):
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

        remaining_target = None
        if target_limit is not None:
            remaining_target = max(0, target_limit - int(stage_summary.get("model_calls") or 0))

        if refill_screening and remaining_target is not None and queue_count < remaining_target:
            stage_summary["low_watermark_events"] = int(stage_summary["low_watermark_events"]) + 1
            prefill_reason, refreshed_count = _ensure_screening_queue_target(
                client,
                args,
                stage_key=stage_key,
                screening_stage_key=screening_stage_key,
                extraction_stage_key=extraction_stage_key,
                stage_summary=stage_summary,
                summary=summary,
                target_count=remaining_target,
                deadline=deadline,
                now_fn=now_fn,
            )
            if prefill_reason in {"dry_run", "max_wallclock_reached"}:
                return prefill_reason
            if prefill_reason == "source_exhausted":
                if refreshed_count <= 0:
                    return prefill_reason
                _log(
                    args,
                    f"{stage_key} prefill source exhausted with {refreshed_count} queued task(s); "
                    "draining available work before stopping",
                )
            queue_count = refreshed_count

        elif refill_screening and target_limit is None and (queue_count < low_watermark or force_refill_next):
            if 0 < queue_count < low_watermark:
                _log(args, f"{stage_key} below low watermark with {queue_count} queued task(s); refilling before draining")
            if force_refill_next and queue_count > 0:
                _log(args, f"{stage_key} forcing refill before retrying requeued error-only work")
            force_refill_next = False
            stage_summary["low_watermark_events"] = int(stage_summary["low_watermark_events"]) + 1
            requested_en, requested_tr = _refill_request_size(args, max(1, low_watermark - queue_count))
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

        drain_limit = min(int(rpm), max(1, queue_count))
        if remaining_target is not None:
            drain_limit = min(drain_limit, max(1, remaining_target))

        drain_summary = _run_ai_drain(
            client,
            args,
            max_tasks=drain_limit,
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

        if target_limit is not None and int(stage_summary.get("model_calls") or 0) >= target_limit:
            stage_summary["daily_target_reached"] = True
            stage_summary["stop_reason"] = "daily_target_reached"
            _log(args, f"{stage_key} daily target reached: {target_limit} model call(s)")
            return "daily_target_reached"

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
    triage_stage_key: str | None = None,
) -> dict[str, int]:
    return _fetch_queue_counts(
        client,
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
        triage_stage_key=triage_stage_key,
    )


def _finish_summary(
    client: Any,
    summary: dict[str, Any],
    *,
    screening_stage_key: str,
    extraction_stage_key: str,
) -> dict[str, Any]:
    triage_stage_key = str(summary.get("triage_stage_key") or "").strip() or None
    screening_summary = summary["stage_summaries"].get(screening_stage_key, {})
    triage_summary = summary["stage_summaries"].get(triage_stage_key, {}) if triage_stage_key else {}
    extraction_summary = summary["stage_summaries"].get(extraction_stage_key, {})
    summary["screened"] = int(screening_summary.get("model_calls") or 0)
    if triage_stage_key:
        summary["routed_to_triage"] = int(screening_summary.get("followup_queued") or 0)
        summary["triage_used"] = int(triage_summary.get("model_calls") or 0)
        summary["routed_to_gemini"] = int(triage_summary.get("followup_queued") or 0)
    else:
        summary["routed_to_gemini"] = int(screening_summary.get("followup_queued") or 0)
    summary["gemini_used"] = int(extraction_summary.get("model_calls") or 0)
    summary["human_ready"] = int(extraction_summary.get("human_ready") or 0)
    try:
        summary["remaining_queued"] = _final_queue_snapshot(
            client,
            screening_stage_key=screening_stage_key,
            extraction_stage_key=extraction_stage_key,
            triage_stage_key=triage_stage_key,
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
    max_wallclock_minutes = max(0, int(getattr(args, "max_wallclock_minutes", 0)))
    deadline = None if max_wallclock_minutes <= 0 else now_fn() + max_wallclock_minutes * 60
    screening_daily_target = max(0, int(getattr(args, "screening_daily_target", 1500)))
    screening_target_for_drain = screening_daily_target if screening_daily_target > 0 else None
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
        "screening_daily_target": screening_daily_target,
        "screening_queue_low_watermark": max(0, int(getattr(args, "screening_queue_low_watermark", 30))),
        "screening_refill_batch_en": max(0, int(getattr(args, "screening_refill_batch_en", 150))),
        "screening_refill_chunk_en": max(1, int(getattr(args, "screening_refill_chunk_en", 150))),
        "screening_prefill_stall_limit": max(0, int(getattr(args, "screening_prefill_stall_limit", 3))),
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
        daily_target=screening_target_for_drain,
    )

    if screening_reason in {"ai_stage_configuration_error", "dry_run", "max_wallclock_reached", "source_exhausted"}:
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


def run_daily_ops_controller(client: Any, args: argparse.Namespace) -> dict[str, Any]:
    screening_stage_key = str(getattr(args, "screening_stage_key", "gemma_proof_extraction_v1") or "gemma_proof_extraction_v1")
    extraction_stage_key = str(getattr(args, "extraction_stage_key", "gemini_flash_db_payload_v2") or "gemini_flash_db_payload_v2")
    triage_stage_key = _optional_triage_stage_key(args)
    stage_rpm = _parse_stage_rpm(
        getattr(args, "stage_rpm", ""),
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
        triage_stage_key=triage_stage_key,
    )
    stage_order = _ordered_stage_keys(screening_stage_key, extraction_stage_key, triage_stage_key)
    screening_daily_target = max(0, int(getattr(args, "screening_daily_target", 1500)))
    triage_daily_target = max(0, int(getattr(args, "triage_daily_target", 500)))
    extraction_daily_target = max(0, int(getattr(args, "extraction_daily_target", 20)))
    screening_active_target = max(0, int(getattr(args, "screening_active_target", 150)))
    stale_after_minutes = max(0, int(getattr(args, "stage_task_stale_minutes", 120)))
    quota_day_starts, quota_timezones = _stage_quota_day_starts(
        args,
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
        triage_stage_key=triage_stage_key,
    )
    soft_limit_bytes = _paper_bucket_soft_limit_bytes(args)
    extraction_reservoir_target = max(0, int(getattr(args, "extraction_candidate_reservoir_target", 500)))
    max_wallclock_minutes = max(0, int(getattr(args, "max_wallclock_minutes", 0)))
    crawler_max_wallclock_seconds = max(0, int(getattr(args, "crawler_max_wallclock_seconds", 0)))
    controller_deadline = (
        time.monotonic() + max_wallclock_minutes * 60
        if max_wallclock_minutes > 0
        else None
    )

    summary: dict[str, Any] = {
        "mode": "controller",
        "dry_run": bool(args.dry_run),
        "target_open": int(args.target_open),
        "screening_stage_key": screening_stage_key,
        "triage_stage_key": triage_stage_key,
        "extraction_stage_key": extraction_stage_key,
        "stage_order": stage_order,
        "stage_rpm": _stage_rpm_summary(stage_order, stage_rpm),
        "screening_daily_target": screening_daily_target,
        "triage_daily_target": triage_daily_target,
        "extraction_daily_target": extraction_daily_target,
        "screening_active_target": screening_active_target,
        "extraction_candidate_reservoir_target": extraction_reservoir_target,
        "stage_task_stale_minutes": stale_after_minutes,
        "max_wallclock_minutes": max_wallclock_minutes,
        "crawler_max_wallclock_seconds": crawler_max_wallclock_seconds,
        "paper_bucket_soft_limit_mb": max(0, int(getattr(args, "paper_bucket_soft_limit_mb", 900))),
        "paper_bucket_soft_limit_bytes": soft_limit_bytes,
        "day_start_utc": _utc_day_start_iso(),
        "quota_day_starts": quota_day_starts,
        "quota_timezones": quota_timezones,
        "ai_tasks_already_used": max(0, int(getattr(args, "ai_tasks_already_used", 0))),
        "ai_tasks_used": 0,
        "daily_ai_tasks_used": max(0, int(getattr(args, "ai_tasks_already_used", 0))),
        "stage_summaries": {},
        "quota_exhausted_stages": [],
        "cooldowns": [],
        "stopped_reason": None,
    }

    screening_summary = _tick_stage_summary(
        summary,
        screening_stage_key,
        rpm=int(stage_rpm.get(screening_stage_key, 15)),
        role="screening_controller",
        daily_target=screening_daily_target,
    )
    extraction_summary = _tick_stage_summary(
        summary,
        extraction_stage_key,
        rpm=int(stage_rpm.get(extraction_stage_key, 15)),
        role="extraction_controller",
        daily_target=extraction_daily_target,
    )
    triage_summary = None
    if triage_stage_key:
        triage_summary = _tick_stage_summary(
            summary,
            triage_stage_key,
            rpm=int(stage_rpm.get(triage_stage_key, 20)),
            role="triage_controller",
            daily_target=triage_daily_target,
        )

    try:
        storage_cleanup = _run_controller_storage_cleanup(client, args)
    except Exception as exc:
        storage_cleanup = {"error": str(exc)}
        _log(args, f"storage cleanup failed before controller refill: {exc}")
    summary["storage_cleanup"] = storage_cleanup

    _requeue_stale_stage_tasks(client, args, stage_key=screening_stage_key, stage_summary=screening_summary)
    if triage_stage_key and triage_summary is not None:
        _requeue_stale_stage_tasks(client, args, stage_key=triage_stage_key, stage_summary=triage_summary)
    _requeue_stale_stage_tasks(client, args, stage_key=extraction_stage_key, stage_summary=extraction_summary)

    screening_completed_today = _count_completed_stage_tasks_since(
        client,
        stage_key=screening_stage_key,
        since_iso=quota_day_starts[screening_stage_key],
    )
    extraction_completed_today = _count_completed_stage_tasks_since(
        client,
        stage_key=extraction_stage_key,
        since_iso=quota_day_starts[extraction_stage_key],
    )
    summary["daily_completed"] = {
        screening_stage_key: screening_completed_today,
        extraction_stage_key: extraction_completed_today,
    }
    if triage_stage_key:
        summary["daily_completed"][triage_stage_key] = _count_completed_stage_tasks_since(
            client,
            stage_key=triage_stage_key,
            since_iso=quota_day_starts[triage_stage_key],
        )

    active_counts = _fetch_active_stage_counts(
        client,
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
        triage_stage_key=triage_stage_key,
        stale_after_minutes=stale_after_minutes,
    )
    active_screening = int(active_counts.get(screening_stage_key) or 0)
    active_triage = int(active_counts.get(triage_stage_key) or 0) if triage_stage_key else 0
    queued_extraction = int(_count_queued_stage_tasks(client, stage_key=extraction_stage_key) or active_counts.get(extraction_stage_key) or 0)
    queued_triage = int(_count_queued_stage_tasks(client, stage_key=triage_stage_key) or active_triage or 0) if triage_stage_key else 0
    remaining_today = max(0, screening_daily_target - screening_completed_today)
    controller_target = min(remaining_today, screening_active_target)
    deficit = max(0, controller_target - active_screening)
    screening_summary["active_target"] = controller_target
    screening_summary["active_count"] = active_screening
    extraction_summary["candidate_reservoir_target"] = extraction_reservoir_target
    extraction_summary["queued_candidate_count"] = queued_extraction
    extraction_summary["reservoir_satisfied"] = queued_extraction >= extraction_reservoir_target if extraction_reservoir_target > 0 else True
    if triage_summary is not None:
        triage_summary["candidate_reservoir_target"] = extraction_reservoir_target
        triage_summary["queued_candidate_count"] = queued_triage
        triage_summary["reservoir_satisfied"] = queued_triage >= extraction_reservoir_target if extraction_reservoir_target > 0 else True
    screening_summary["queue_observations"].append(
        {
            "total": active_counts["total"],
            "active_for_stage": active_screening,
            "active_target": controller_target,
            "controller": True,
        }
    )
    extraction_summary["queue_observations"].append(
        {
            "total": active_counts["total"],
            "queued_for_stage": queued_extraction,
            "candidate_reservoir_target": extraction_reservoir_target,
            "controller": True,
        }
    )
    if triage_summary is not None:
        triage_summary["queue_observations"].append(
            {
                "total": active_counts["total"],
                "queued_for_stage": queued_triage,
                "candidate_reservoir_target": extraction_reservoir_target,
                "controller": True,
            }
        )
    _log(
        args,
        f"{screening_stage_key} controller observation: completed_today={screening_completed_today} "
        f"active_for_stage={active_screening} active_target={controller_target}",
    )

    storage_remaining = storage_cleanup.get("remaining_bytes_after_cleanup")
    storage_over_limit = (
        soft_limit_bytes > 0
        and storage_remaining is not None
        and int(storage_remaining) > soft_limit_bytes
    )
    if storage_over_limit:
        summary["storage_soft_limit_exceeded"] = True
        screening_summary["storage_soft_limit_exceeded"] = True
    storage_cleanup_failed = bool(storage_cleanup.get("error"))

    if remaining_today <= 0:
        screening_summary["daily_target_reached"] = True
        screening_summary["stop_reason"] = "daily_target_reached"
        summary["stopped_reason"] = "screening_daily_target_reached"
    elif controller_target <= 0 or deficit <= 0:
        screening_summary["prefill_satisfied"] = True
        screening_summary["stop_reason"] = "active_target_satisfied"
        summary["stopped_reason"] = "screening_active_target_satisfied"
    elif _deadline_reached(controller_deadline, time.monotonic):
        screening_summary["stop_reason"] = "max_wallclock_reached"
        summary["stopped_reason"] = "max_wallclock_reached"
    elif storage_over_limit:
        screening_summary["stop_reason"] = "storage_soft_limit_exceeded"
        summary["stopped_reason"] = "storage_soft_limit_exceeded"
        _log(
            args,
            f"skipping refill: paper bucket remains above soft limit "
            f"({int(storage_remaining)} > {soft_limit_bytes} bytes)",
        )
    elif storage_cleanup_failed:
        screening_summary["stop_reason"] = "storage_cleanup_failed"
        summary["stopped_reason"] = "storage_cleanup_failed"
    else:
        requested_en, requested_tr = _tick_refill_request_size(args, deficit)
        screening_summary["low_watermark_events"] = int(screening_summary["low_watermark_events"]) + 1
        if args.dry_run:
            screening_summary["planned_refill"] = {
                "en": requested_en,
                "tr": requested_tr,
                "active_before": active_screening,
                "target": controller_target,
            }
            screening_summary["stop_reason"] = "dry_run"
            summary["stopped_reason"] = "dry_run"
        elif requested_en <= 0 and requested_tr <= 0:
            screening_summary["source_exhausted"] = True
            screening_summary["stop_reason"] = "source_exhausted"
            summary["stopped_reason"] = "source_exhausted"
        else:
            _log(
                args,
                f"{screening_stage_key} controller refill: active_for_stage={active_screening} "
                f"target={controller_target} crawling EN={requested_en} TR={requested_tr}",
            )
            _run_screening_refill(
                client,
                args,
                stage_summary=screening_summary,
                cycle_index=int(screening_summary["refill_cycles"]) + 1,
                requested_en=requested_en,
                requested_tr=requested_tr,
            )
            refreshed_counts = _fetch_active_stage_counts(
                client,
                screening_stage_key=screening_stage_key,
                extraction_stage_key=extraction_stage_key,
                triage_stage_key=triage_stage_key,
                stale_after_minutes=stale_after_minutes,
            )
            refreshed_screening = int(refreshed_counts.get(screening_stage_key) or 0)
            screening_summary["active_count_after_refill"] = refreshed_screening
            screening_summary["queue_observations"].append(
                {
                    "total": refreshed_counts["total"],
                    "active_for_stage": refreshed_screening,
                    "active_target": controller_target,
                    "after_refill": True,
                    "controller": True,
                }
            )
            if refreshed_screening <= active_screening:
                screening_summary["source_exhausted"] = True
                screening_summary["stop_reason"] = "source_exhausted"
                summary["stopped_reason"] = "source_exhausted"
            else:
                screening_summary["prefill_satisfied"] = refreshed_screening >= controller_target
                screening_summary["stop_reason"] = "controller_refill_complete"
                summary["stopped_reason"] = "controller_refill_complete"

    extraction_summary["stop_reason"] = extraction_summary.get("stop_reason") or "controller_no_drain"
    if triage_summary is not None:
        triage_summary["stop_reason"] = triage_summary.get("stop_reason") or "controller_no_drain"
    return _finish_summary(
        client,
        summary,
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
    )


def run_daily_ops_drain(client: Any, args: argparse.Namespace) -> dict[str, Any]:
    screening_stage_key = str(getattr(args, "screening_stage_key", "gemma_proof_extraction_v1") or "gemma_proof_extraction_v1")
    extraction_stage_key = str(getattr(args, "extraction_stage_key", "gemini_flash_db_payload_v2") or "gemini_flash_db_payload_v2")
    triage_stage_key = _optional_triage_stage_key(args)
    stage_rpm = _parse_stage_rpm(
        getattr(args, "stage_rpm", ""),
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
        triage_stage_key=triage_stage_key,
    )
    stage_order = _ordered_stage_keys(screening_stage_key, extraction_stage_key, triage_stage_key)
    screening_daily_target = max(0, int(getattr(args, "screening_daily_target", 1500)))
    triage_daily_target = max(0, int(getattr(args, "triage_daily_target", 500)))
    extraction_daily_target = max(0, int(getattr(args, "extraction_daily_target", 20)))
    screening_tick_tasks = max(1, int(getattr(args, "screening_tick_tasks", stage_rpm.get(screening_stage_key, 20))))
    triage_tick_tasks = max(1, int(getattr(args, "triage_tick_tasks", stage_rpm.get(triage_stage_key or "", 20))))
    extraction_tick_tasks = max(1, int(getattr(args, "extraction_tick_tasks", stage_rpm.get(extraction_stage_key, 15))))
    quota_day_starts, quota_timezones = _stage_quota_day_starts(
        args,
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
        triage_stage_key=triage_stage_key,
    )

    summary: dict[str, Any] = {
        "mode": "drain",
        "dry_run": bool(args.dry_run),
        "target_open": int(args.target_open),
        "screening_stage_key": screening_stage_key,
        "triage_stage_key": triage_stage_key,
        "extraction_stage_key": extraction_stage_key,
        "stage_order": stage_order,
        "stage_rpm": _stage_rpm_summary(stage_order, stage_rpm),
        "screening_daily_target": screening_daily_target,
        "triage_daily_target": triage_daily_target,
        "extraction_daily_target": extraction_daily_target,
        "screening_tick_tasks": screening_tick_tasks,
        "triage_tick_tasks": triage_tick_tasks,
        "extraction_tick_tasks": extraction_tick_tasks,
        "interleave_extraction": bool(getattr(args, "interleave_extraction", False)),
        "day_start_utc": _utc_day_start_iso(),
        "quota_day_starts": quota_day_starts,
        "quota_timezones": quota_timezones,
        "ai_tasks_already_used": max(0, int(getattr(args, "ai_tasks_already_used", 0))),
        "ai_tasks_used": 0,
        "daily_ai_tasks_used": max(0, int(getattr(args, "ai_tasks_already_used", 0))),
        "stage_summaries": {},
        "quota_exhausted_stages": [],
        "cooldowns": [],
        "stopped_reason": None,
    }

    screening_completed_today = _count_completed_stage_tasks_since(
        client,
        stage_key=screening_stage_key,
        since_iso=quota_day_starts[screening_stage_key],
    )
    extraction_completed_today = _count_completed_stage_tasks_since(
        client,
        stage_key=extraction_stage_key,
        since_iso=quota_day_starts[extraction_stage_key],
    )
    summary["daily_completed"] = {
        screening_stage_key: screening_completed_today,
        extraction_stage_key: extraction_completed_today,
    }
    if triage_stage_key:
        summary["daily_completed"][triage_stage_key] = _count_completed_stage_tasks_since(
            client,
            stage_key=triage_stage_key,
            since_iso=quota_day_starts[triage_stage_key],
        )

    if screening_completed_today < screening_daily_target:
        stage_summary = _tick_stage_summary(
            summary,
            screening_stage_key,
            rpm=int(stage_rpm.get(screening_stage_key, 15)),
            role="screening",
            daily_target=screening_daily_target,
        )
        queue_counts = _fetch_queue_counts(
            client,
            screening_stage_key=screening_stage_key,
            extraction_stage_key=extraction_stage_key,
            triage_stage_key=triage_stage_key,
        )
        queue_count = int(queue_counts.get(screening_stage_key) or 0)
        stage_summary["queue_observations"].append(
            {
                "total": queue_counts["total"],
                "queued_for_stage": queue_count,
                "drain_only": True,
            }
        )
        _log(args, f"{screening_stage_key} drain observation: completed_today={screening_completed_today} queued_for_stage={queue_count}")
        if queue_count > 0:
            remaining_today = max(0, screening_daily_target - screening_completed_today)
            reason = _tick_drain_stage(
                client,
                args,
                stage_key=screening_stage_key,
                stage_summary=stage_summary,
                max_tasks=min(screening_tick_tasks, remaining_today, queue_count),
                summary=summary,
                role="screening",
            )
            if reason == "daily_quota_exhausted":
                summary["stopped_reason"] = "screening_daily_quota_exhausted"
            elif reason == "ai_stage_configuration_error":
                summary["stopped_reason"] = reason
            elif screening_completed_today + int(stage_summary.get("model_calls") or 0) >= screening_daily_target:
                stage_summary["daily_target_reached"] = True
                summary["stopped_reason"] = "screening_daily_target_reached"
            else:
                summary["stopped_reason"] = reason
            if bool(getattr(args, "interleave_extraction", False)) and reason not in {"ai_stage_configuration_error", "daily_quota_exhausted", "dry_run"}:
                extraction_reason = _tick_drain_downstream(
                    client,
                    args,
                    summary=summary,
                    screening_stage_key=screening_stage_key,
                    extraction_stage_key=extraction_stage_key,
                    extraction_daily_target=extraction_daily_target,
                    extraction_tick_tasks=extraction_tick_tasks,
                    stage_rpm=stage_rpm,
                    day_start_iso=quota_day_starts[extraction_stage_key],
                )
                summary["interleaved_extraction_reason"] = extraction_reason
            return _finish_summary(
                client,
                summary,
                screening_stage_key=screening_stage_key,
                extraction_stage_key=extraction_stage_key,
            )

        stage_summary["queue_empty"] = True
        stage_summary["stop_reason"] = "queue_empty"
        summary["stopped_reason"] = "no_screening_candidates"
        if bool(getattr(args, "interleave_extraction", False)):
            extraction_reason = _tick_drain_downstream(
                client,
                args,
                summary=summary,
                screening_stage_key=screening_stage_key,
                extraction_stage_key=extraction_stage_key,
                extraction_daily_target=extraction_daily_target,
                extraction_tick_tasks=extraction_tick_tasks,
                stage_rpm=stage_rpm,
                day_start_iso=quota_day_starts[extraction_stage_key],
            )
            summary["interleaved_extraction_reason"] = extraction_reason
            if extraction_reason == "tick_complete":
                summary["stopped_reason"] = "tick_complete"
            elif extraction_reason == "ai_stage_configuration_error":
                summary["stopped_reason"] = extraction_reason
        return _finish_summary(
            client,
            summary,
            screening_stage_key=screening_stage_key,
            extraction_stage_key=extraction_stage_key,
        )

    _drain_triage_tick(
        client,
        args,
        summary=summary,
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
        stage_rpm=stage_rpm,
    )
    stage_summary = _tick_stage_summary(
        summary,
        extraction_stage_key,
        rpm=int(stage_rpm.get(extraction_stage_key, 15)),
        role="extraction",
        daily_target=extraction_daily_target,
    )
    if extraction_completed_today >= extraction_daily_target:
        stage_summary["daily_target_reached"] = True
        stage_summary["stop_reason"] = "daily_target_reached"
        summary["stopped_reason"] = "daily_targets_reached"
        return _finish_summary(
            client,
            summary,
            screening_stage_key=screening_stage_key,
            extraction_stage_key=extraction_stage_key,
        )

    queue_counts = _fetch_queue_counts(
        client,
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
        triage_stage_key=triage_stage_key,
    )
    queue_count = int(queue_counts.get(extraction_stage_key) or 0)
    stage_summary["queue_observations"].append(
        {
            "total": queue_counts["total"],
            "queued_for_stage": queue_count,
            "drain_only": True,
        }
    )
    _log(args, f"{extraction_stage_key} drain observation: completed_today={extraction_completed_today} queued_for_stage={queue_count}")
    if queue_count <= 0:
        stage_summary["queue_empty"] = True
        stage_summary["stop_reason"] = "queue_empty"
        summary["stopped_reason"] = "no_extraction_candidates"
        return _finish_summary(
            client,
            summary,
            screening_stage_key=screening_stage_key,
            extraction_stage_key=extraction_stage_key,
        )

    reason = _tick_drain_stage(
        client,
        args,
        stage_key=extraction_stage_key,
        stage_summary=stage_summary,
        max_tasks=min(extraction_tick_tasks, extraction_daily_target - extraction_completed_today, queue_count),
        summary=summary,
        role="extraction",
    )
    assignment_after_ai = _assign_new_human_ready_after_ai(client, args, stage_summary)
    if assignment_after_ai is not None:
        summary["assignment_after_ai"] = assignment_after_ai
    if reason == "daily_quota_exhausted":
        summary["stopped_reason"] = "extraction_daily_quota_exhausted"
    elif reason == "ai_stage_configuration_error":
        summary["stopped_reason"] = reason
    elif extraction_completed_today + int(stage_summary.get("model_calls") or 0) >= extraction_daily_target:
        stage_summary["daily_target_reached"] = True
        summary["stopped_reason"] = "daily_targets_reached"
    else:
        summary["stopped_reason"] = reason
    return _finish_summary(
        client,
        summary,
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
    )


def _tick_stage_summary(summary: dict[str, Any], stage_key: str, *, rpm: int, role: str, daily_target: int) -> dict[str, Any]:
    stage_summary = _new_stage_summary(stage_key, rpm=rpm, role=role, daily_target=daily_target)
    summary["stage_summaries"][stage_key] = stage_summary
    return stage_summary


def _tick_drain_stage(
    client: Any,
    args: argparse.Namespace,
    *,
    stage_key: str,
    stage_summary: dict[str, Any],
    max_tasks: int,
    summary: dict[str, Any],
    role: str,
) -> str:
    if args.dry_run:
        stage_summary["stop_reason"] = "dry_run"
        stage_summary["would_process"] = max(0, int(max_tasks))
        return "dry_run"

    drain_summary = _run_ai_drain(
        client,
        args,
        max_tasks=max(1, int(max_tasks)),
        stage_key=stage_key,
    )
    _log(
        args,
        f"{stage_key} tick drain: processed={int(drain_summary.get('processed') or 0)} "
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
    if drain_summary.get("quota_limited") and model_calls <= 0:
        stage_summary["quota_exhausted"] = True
        stage_summary["stop_reason"] = "daily_quota_exhausted"
        summary.setdefault("quota_exhausted_stages", []).append(stage_key)
        return "daily_quota_exhausted"
    if int(drain_summary.get("processed") or 0) <= 0:
        stage_summary["stop_reason"] = "no_progress"
        return "no_progress"
    stage_summary["stop_reason"] = "tick_complete"
    return "tick_complete"


def _tick_drain_followup_stage(
    client: Any,
    args: argparse.Namespace,
    *,
    summary: dict[str, Any],
    screening_stage_key: str,
    extraction_stage_key: str,
    triage_stage_key: str | None,
    stage_key: str,
    daily_target: int,
    tick_tasks: int,
    stage_rpm: dict[str, int],
    day_start_iso: str,
    role: str,
) -> str | None:
    completed_today = _count_completed_stage_tasks_since(
        client,
        stage_key=stage_key,
        since_iso=day_start_iso,
    )
    summary.setdefault("daily_completed", {})[stage_key] = completed_today
    stage_summary = summary["stage_summaries"].get(stage_key)
    if stage_summary is None:
        stage_summary = _tick_stage_summary(
            summary,
            stage_key,
            rpm=int(stage_rpm.get(stage_key, 15)),
            role=role,
            daily_target=daily_target,
        )
    if completed_today >= daily_target:
        stage_summary["daily_target_reached"] = True
        stage_summary["stop_reason"] = "daily_target_reached"
        return "daily_target_reached"

    if not bool(getattr(args, "drain_only", False)):
        _requeue_stale_stage_tasks(client, args, stage_key=stage_key, stage_summary=stage_summary)
    queue_counts = _fetch_queue_counts(
        client,
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
        triage_stage_key=triage_stage_key,
    )
    queue_count = int(queue_counts.get(stage_key) or 0)
    stage_summary["queue_observations"].append(
        {
            "total": queue_counts["total"],
            "queued_for_stage": queue_count,
            "tick": True,
            "interleaved": True,
        }
    )
    _log(args, f"{stage_key} interleaved tick observation: completed_today={completed_today} queued_for_stage={queue_count}")
    if queue_count <= 0:
        stage_summary["queue_empty"] = True
        stage_summary["stop_reason"] = "queue_empty"
        return "no_followup_candidates"

    remaining_today = max(0, daily_target - completed_today)
    drain_limit = min(tick_tasks, remaining_today, queue_count)
    reason = _tick_drain_stage(
        client,
        args,
        stage_key=stage_key,
        stage_summary=stage_summary,
        max_tasks=drain_limit,
        summary=summary,
        role=role,
    )
    if role == "extraction":
        assignment_after_ai = _assign_new_human_ready_after_ai(client, args, stage_summary)
        if assignment_after_ai is not None:
            summary["assignment_after_ai"] = assignment_after_ai
    return reason


def _drain_triage_tick(
    client: Any,
    args: argparse.Namespace,
    *,
    summary: dict[str, Any],
    screening_stage_key: str,
    extraction_stage_key: str,
    stage_rpm: dict[str, int],
) -> str | None:
    triage_stage_key = str(getattr(args, "triage_stage_key", "") or "").strip()
    if not triage_stage_key:
        return None
    triage_day_start = _quota_day_start_iso(
        timezone_name=str(getattr(args, "triage_quota_timezone", "America/Los_Angeles") or "America/Los_Angeles")
    )
    reason = _tick_drain_followup_stage(
        client,
        args,
        summary=summary,
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
        triage_stage_key=triage_stage_key,
        stage_key=triage_stage_key,
        daily_target=max(0, int(getattr(args, "triage_daily_target", 500))),
        tick_tasks=max(1, int(getattr(args, "triage_tick_tasks", 10))),
        stage_rpm=stage_rpm,
        day_start_iso=triage_day_start,
        role="triage",
    )
    summary["interleaved_triage_reason"] = reason
    return reason


def _tick_drain_downstream(
    client: Any,
    args: argparse.Namespace,
    *,
    summary: dict[str, Any],
    screening_stage_key: str,
    extraction_stage_key: str,
    extraction_daily_target: int,
    extraction_tick_tasks: int,
    stage_rpm: dict[str, int],
    day_start_iso: str,
) -> str | None:
    # Drain the intermediate Flash-Lite triage stage first so it feeds fresh
    # ranked candidates into the final extraction queue within the same tick,
    # then drain the scarce final extraction stage.
    triage_reason = _drain_triage_tick(
        client,
        args,
        summary=summary,
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
        stage_rpm=stage_rpm,
    )
    if triage_reason == "ai_stage_configuration_error":
        return triage_reason
    triage_stage_key = str(getattr(args, "triage_stage_key", "") or "").strip() or None
    return _tick_drain_followup_stage(
        client,
        args,
        summary=summary,
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
        triage_stage_key=triage_stage_key,
        stage_key=extraction_stage_key,
        daily_target=extraction_daily_target,
        tick_tasks=extraction_tick_tasks,
        stage_rpm=stage_rpm,
        day_start_iso=day_start_iso,
        role="extraction",
    )


def run_daily_ops_tick(client: Any, args: argparse.Namespace) -> dict[str, Any]:
    screening_stage_key = str(getattr(args, "screening_stage_key", "gemma_proof_extraction_v1") or "gemma_proof_extraction_v1")
    extraction_stage_key = str(getattr(args, "extraction_stage_key", "gemini_flash_db_payload_v2") or "gemini_flash_db_payload_v2")
    triage_stage_key = _optional_triage_stage_key(args)
    stage_rpm = _parse_stage_rpm(
        getattr(args, "stage_rpm", ""),
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
        triage_stage_key=triage_stage_key,
    )
    stage_order = _ordered_stage_keys(screening_stage_key, extraction_stage_key, triage_stage_key)
    screening_daily_target = max(0, int(getattr(args, "screening_daily_target", 1500)))
    triage_daily_target = max(0, int(getattr(args, "triage_daily_target", 500)))
    extraction_daily_target = max(0, int(getattr(args, "extraction_daily_target", 20)))
    screening_tick_tasks = max(1, int(getattr(args, "screening_tick_tasks", stage_rpm.get(screening_stage_key, 20))))
    triage_tick_tasks = max(1, int(getattr(args, "triage_tick_tasks", stage_rpm.get(triage_stage_key or "", 20))))
    extraction_tick_tasks = max(1, int(getattr(args, "extraction_tick_tasks", stage_rpm.get(extraction_stage_key, 15))))
    quota_day_starts, quota_timezones = _stage_quota_day_starts(
        args,
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
        triage_stage_key=triage_stage_key,
    )

    summary: dict[str, Any] = {
        "mode": "tick",
        "dry_run": bool(args.dry_run),
        "target_open": int(args.target_open),
        "screening_stage_key": screening_stage_key,
        "triage_stage_key": triage_stage_key,
        "extraction_stage_key": extraction_stage_key,
        "stage_order": stage_order,
        "stage_rpm": _stage_rpm_summary(stage_order, stage_rpm),
        "screening_daily_target": screening_daily_target,
        "triage_daily_target": triage_daily_target,
        "extraction_daily_target": extraction_daily_target,
        "screening_tick_tasks": screening_tick_tasks,
        "triage_tick_tasks": triage_tick_tasks,
        "extraction_tick_tasks": extraction_tick_tasks,
        "interleave_extraction": bool(getattr(args, "interleave_extraction", False)),
        "day_start_utc": _utc_day_start_iso(),
        "quota_day_starts": quota_day_starts,
        "quota_timezones": quota_timezones,
        "ai_tasks_already_used": max(0, int(getattr(args, "ai_tasks_already_used", 0))),
        "ai_tasks_used": 0,
        "daily_ai_tasks_used": max(0, int(getattr(args, "ai_tasks_already_used", 0))),
        "stage_summaries": {},
        "quota_exhausted_stages": [],
        "cooldowns": [],
        "stopped_reason": None,
    }

    screening_completed_today = _count_completed_stage_tasks_since(
        client,
        stage_key=screening_stage_key,
        since_iso=quota_day_starts[screening_stage_key],
    )
    extraction_completed_today = _count_completed_stage_tasks_since(
        client,
        stage_key=extraction_stage_key,
        since_iso=quota_day_starts[extraction_stage_key],
    )
    summary["daily_completed"] = {
        screening_stage_key: screening_completed_today,
        extraction_stage_key: extraction_completed_today,
    }
    if triage_stage_key:
        summary["daily_completed"][triage_stage_key] = _count_completed_stage_tasks_since(
            client,
            stage_key=triage_stage_key,
            since_iso=quota_day_starts[triage_stage_key],
        )

    if screening_completed_today < screening_daily_target:
        stage_summary = _tick_stage_summary(
            summary,
            screening_stage_key,
            rpm=int(stage_rpm.get(screening_stage_key, 15)),
            role="screening",
            daily_target=screening_daily_target,
        )
        _requeue_stale_stage_tasks(client, args, stage_key=screening_stage_key, stage_summary=stage_summary)
        queue_counts = _fetch_queue_counts(
            client,
            screening_stage_key=screening_stage_key,
            extraction_stage_key=extraction_stage_key,
            triage_stage_key=triage_stage_key,
        )
        queue_count = int(queue_counts.get(screening_stage_key) or 0)
        stage_summary["queue_observations"].append(
            {
                "total": queue_counts["total"],
                "queued_for_stage": queue_count,
                "tick": True,
            }
        )
        _log(args, f"{screening_stage_key} tick observation: completed_today={screening_completed_today} queued_for_stage={queue_count}")

        prefill_target = _screening_tick_prefill_target(
            completed_today=screening_completed_today,
            daily_target=screening_daily_target,
            tick_tasks=screening_tick_tasks,
        )
        stage_summary["tick_prefill_target"] = prefill_target
        if queue_count < prefill_target:
            requested_en, requested_tr = _tick_refill_request_size(args, prefill_target - queue_count)
            stage_summary["low_watermark_events"] = int(stage_summary["low_watermark_events"]) + 1
            if args.dry_run:
                stage_summary["planned_refill"] = {
                    "en": requested_en,
                    "tr": requested_tr,
                    "queued_before": queue_count,
                    "target": prefill_target,
                }
                summary["stopped_reason"] = "dry_run"
                return _finish_summary(
                    client,
                    summary,
                    screening_stage_key=screening_stage_key,
                    extraction_stage_key=extraction_stage_key,
                )
            if requested_en > 0 or requested_tr > 0:
                _log(args, f"{screening_stage_key} tick refill: queued_for_stage={queue_count} target={prefill_target} crawling EN={requested_en} TR={requested_tr}")
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
                    triage_stage_key=triage_stage_key,
                )
                queue_count = int(queue_counts.get(screening_stage_key) or 0)
                stage_summary["queue_observations"].append(
                    {
                        "total": queue_counts["total"],
                        "queued_for_stage": queue_count,
                        "after_refill": True,
                        "tick": True,
                    }
                )

        if queue_count <= 0:
            stage_summary["queue_empty"] = True
            stage_summary["stop_reason"] = "queue_empty"
            summary["stopped_reason"] = "source_exhausted"
            if bool(getattr(args, "interleave_extraction", False)):
                extraction_reason = _tick_drain_downstream(
                    client,
                    args,
                    summary=summary,
                    screening_stage_key=screening_stage_key,
                    extraction_stage_key=extraction_stage_key,
                    extraction_daily_target=extraction_daily_target,
                    extraction_tick_tasks=extraction_tick_tasks,
                    stage_rpm=stage_rpm,
                    day_start_iso=quota_day_starts[extraction_stage_key],
                )
                summary["interleaved_extraction_reason"] = extraction_reason
                if extraction_reason == "ai_stage_configuration_error":
                    summary["stopped_reason"] = extraction_reason
            return _finish_summary(
                client,
                summary,
                screening_stage_key=screening_stage_key,
                extraction_stage_key=extraction_stage_key,
            )

        remaining_today = max(0, screening_daily_target - screening_completed_today)
        drain_limit = min(screening_tick_tasks, remaining_today, queue_count)
        reason = _tick_drain_stage(
            client,
            args,
            stage_key=screening_stage_key,
            stage_summary=stage_summary,
            max_tasks=drain_limit,
            summary=summary,
            role="screening",
        )
        if reason == "daily_quota_exhausted":
            summary["stopped_reason"] = "screening_daily_quota_exhausted"
        elif reason == "ai_stage_configuration_error":
            summary["stopped_reason"] = reason
        elif screening_completed_today + int(stage_summary.get("model_calls") or 0) >= screening_daily_target:
            stage_summary["daily_target_reached"] = True
            summary["stopped_reason"] = "screening_daily_target_reached"
        else:
            summary["stopped_reason"] = reason
        if bool(getattr(args, "interleave_extraction", False)) and reason not in {"ai_stage_configuration_error", "daily_quota_exhausted", "dry_run"}:
            extraction_reason = _tick_drain_downstream(
                client,
                args,
                summary=summary,
                screening_stage_key=screening_stage_key,
                extraction_stage_key=extraction_stage_key,
                extraction_daily_target=extraction_daily_target,
                extraction_tick_tasks=extraction_tick_tasks,
                stage_rpm=stage_rpm,
                day_start_iso=quota_day_starts[extraction_stage_key],
            )
            summary["interleaved_extraction_reason"] = extraction_reason
        return _finish_summary(
            client,
            summary,
            screening_stage_key=screening_stage_key,
            extraction_stage_key=extraction_stage_key,
        )

    _drain_triage_tick(
        client,
        args,
        summary=summary,
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
        stage_rpm=stage_rpm,
    )
    stage_summary = _tick_stage_summary(
        summary,
        extraction_stage_key,
        rpm=int(stage_rpm.get(extraction_stage_key, 15)),
        role="extraction",
        daily_target=extraction_daily_target,
    )
    if extraction_completed_today >= extraction_daily_target:
        stage_summary["daily_target_reached"] = True
        stage_summary["stop_reason"] = "daily_target_reached"
        summary["stopped_reason"] = "daily_targets_reached"
        return _finish_summary(
            client,
            summary,
            screening_stage_key=screening_stage_key,
            extraction_stage_key=extraction_stage_key,
        )

    _requeue_stale_stage_tasks(client, args, stage_key=extraction_stage_key, stage_summary=stage_summary)
    queue_counts = _fetch_queue_counts(
        client,
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
        triage_stage_key=triage_stage_key,
    )
    queue_count = int(queue_counts.get(extraction_stage_key) or 0)
    stage_summary["queue_observations"].append(
        {
            "total": queue_counts["total"],
            "queued_for_stage": queue_count,
            "tick": True,
        }
    )
    _log(args, f"{extraction_stage_key} tick observation: completed_today={extraction_completed_today} queued_for_stage={queue_count}")
    if queue_count <= 0:
        stage_summary["queue_empty"] = True
        stage_summary["stop_reason"] = "queue_empty"
        summary["stopped_reason"] = "no_extraction_candidates"
        return _finish_summary(
            client,
            summary,
            screening_stage_key=screening_stage_key,
            extraction_stage_key=extraction_stage_key,
        )

    remaining_today = max(0, extraction_daily_target - extraction_completed_today)
    drain_limit = min(extraction_tick_tasks, remaining_today, queue_count)
    reason = _tick_drain_stage(
        client,
        args,
        stage_key=extraction_stage_key,
        stage_summary=stage_summary,
        max_tasks=drain_limit,
        summary=summary,
        role="extraction",
    )
    assignment_after_ai = _assign_new_human_ready_after_ai(client, args, stage_summary)
    if assignment_after_ai is not None:
        summary["assignment_after_ai"] = assignment_after_ai

    if reason == "daily_quota_exhausted":
        summary["stopped_reason"] = "extraction_daily_quota_exhausted"
    elif reason == "ai_stage_configuration_error":
        summary["stopped_reason"] = reason
    elif extraction_completed_today + int(stage_summary.get("model_calls") or 0) >= extraction_daily_target:
        stage_summary["daily_target_reached"] = True
        summary["stopped_reason"] = "daily_targets_reached"
    else:
        summary["stopped_reason"] = reason
    return _finish_summary(
        client,
        summary,
        screening_stage_key=screening_stage_key,
        extraction_stage_key=extraction_stage_key,
    )


def main() -> None:
    args = build_parser().parse_args()
    client = require_client()
    if getattr(args, "controller_only", False):
        summary = run_daily_ops_controller(client, args)
    elif getattr(args, "drain_only", False):
        summary = run_daily_ops_drain(client, args)
    elif getattr(args, "tick_mode", False):
        summary = run_daily_ops_tick(client, args)
    else:
        summary = run_daily_ops(client, args)
    if args.json_summary:
        print(json.dumps(summary, sort_keys=True))
    else:
        print("\nDaily ops summary")
        print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
