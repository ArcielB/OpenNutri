from __future__ import annotations

import sys
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import daily_ops_orchestrator, ensure_paper_stock, refill_assignment_queue


SCREENING_STAGE = "gemma_proof_extraction_v1"
EXTRACTION_STAGE = "gemini_flash_db_payload_v2"
TRIAGE_STAGE = "gemini_flash_lite_triage_v1"


def build_args(**overrides):
    defaults = {
        "target_open": 50,
        "max_cycles": 4,
        "max_ai_tasks": 5,
        "max_screening_tasks": 50,
        "daily_ai_call_budget": 20,
        "ai_tasks_already_used": 0,
        "screening_stage_key": SCREENING_STAGE,
        "extraction_stage_key": EXTRACTION_STAGE,
        "stage_rpm": f"{SCREENING_STAGE}=15,{EXTRACTION_STAGE}=15",
        "quota_cooldown_seconds": 65,
        "max_wallclock_minutes": 0,
        "screening_daily_target": 1500,
        "screening_tick_tasks": 15,
        "screening_active_target": 75,
        "extraction_daily_target": 20,
        "extraction_tick_tasks": 15,
        "interleave_extraction": False,
        "controller_only": False,
        "drain_only": False,
        "screening_queue_low_watermark": 30,
        "screening_refill_batch_en": 1500,
        "screening_refill_chunk_en": 1500,
        "screening_prefill_stall_limit": 3,
        "stage_task_stale_minutes": 120,
        "paper_storage_bucket": "papers",
        "paper_bucket_soft_limit_mb": 900,
        "storage_cleanup_batch_size": 100,
        "skip_storage_cleanup": False,
        "keep_storage_orphans": False,
        "refill_step_en": 4,
        "refill_step_tr": 0,
        "seed": 20260413,
        "data_dir": "services/data-pipeline/data",
        "query_limit": 50,
        "max_queries": 80,
        "sources": "europepmc,openalex,semanticscholar",
        "dergipark_journal_limit": 0,
        "dergipark_max_issues_per_journal": 12,
        "skip_feedback": False,
        "skip_dergipark_refresh": False,
        "dry_run": False,
        "json_summary": True,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def queued_papers(stage_key: str, count: int) -> list[dict]:
    return [
        {
            "id": f"{stage_key}-{index}",
            "routing_status": "queued_for_ai",
            "current_stage_key": stage_key,
        }
        for index in range(count)
    ]


class CountResponse:
    def __init__(self, rows: list[dict], count: int | None = None):
        self.data = rows
        self.count = count


class CountTable:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.filters: list[tuple[str, object]] = []
        self.gte_filters: list[tuple[str, object]] = []
        self.range_start = None
        self.range_end = None
        self.include_count = False

    def select(self, _columns: str, count: str | None = None):
        self.include_count = count == "exact"
        return self

    def eq(self, field: str, value: object):
        self.filters.append((field, value))
        return self

    def gte(self, field: str, value: object):
        self.gte_filters.append((field, value))
        return self

    def limit(self, count: int):
        self.range_start = 0
        self.range_end = count - 1
        return self

    def execute(self):
        rows = [row for row in self.rows if self._matches(row)]
        count = len(rows) if self.include_count else None
        if self.range_start is not None and self.range_end is not None:
            rows = rows[self.range_start:self.range_end + 1]
        return CountResponse([dict(row) for row in rows], count=count)

    def _matches(self, row: dict) -> bool:
        if not all(row.get(field) == value for field, value in self.filters):
            return False
        for field, value in self.gte_filters:
            row_value = row.get(field)
            if row_value is None or row_value < value:
                return False
        return True


class CountClient:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def table(self, name: str) -> CountTable:
        if name != "paper_stage_tasks":
            raise AssertionError(f"Unexpected table {name!r}")
        return CountTable(self.rows)


class DailyOpsTests(unittest.TestCase):
    def test_default_stock_targets_are_english_only(self) -> None:
        args = build_args(target=None, target_en=None, target_tr=None)
        self.assertEqual(ensure_paper_stock.resolve_language_targets(args), {"en": 20, "tr": 0})
        self.assertEqual(refill_assignment_queue.language_deficits_for([], 50), {"en": 50, "tr": 0})

    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_prefills_gemma_daily_target_before_draining(
        self,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        fetch_calls = {"count": 0}

        def fetch_state(_client: object) -> dict[str, list[dict]]:
            fetch_calls["count"] += 1
            queued = 60 if fetch_calls["count"] <= 2 else 1500
            return {"papers": queued_papers(SCREENING_STAGE, queued)}

        fetch_state_mock.side_effect = fetch_state
        drain_mock.side_effect = [
            {"processed": 1500, "followup_queued": 0, "quota_limited": False}
        ]

        summary = daily_ops_orchestrator.run_daily_ops(
            object(),
            build_args(stage_rpm=f"{SCREENING_STAGE}=1500,{EXTRACTION_STAGE}=15"),
            sleep_fn=Mock(),
            now_fn=Mock(return_value=0.0),
        )

        self.assertEqual(summary["stopped_reason"], "no_extraction_candidates")
        self.assertEqual(summary["screened"], 1500)
        self.assertTrue(summary["stage_summaries"][SCREENING_STAGE]["daily_target_reached"])
        crawl_mock.assert_called_once()
        self.assertEqual(crawl_mock.call_args.kwargs["deficits"], {"en": 1440, "tr": 0})
        self.assertEqual(drain_mock.call_args_list[0].kwargs["stage_key"], SCREENING_STAGE)
        self.assertEqual(drain_mock.call_count, 1)
        self.assertEqual(drain_mock.call_args_list[0].kwargs["max_tasks"], 1500)

    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_prefill_source_exhaustion_still_drains_available_gemma_work(
        self,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        fetch_state_mock.side_effect = [
            {"papers": queued_papers(SCREENING_STAGE, 1497)},
            {"papers": queued_papers(SCREENING_STAGE, 1497)},
            {"papers": queued_papers(SCREENING_STAGE, 1497)},
            {"papers": []},
            {"papers": []},
            {"papers": []},
            {"papers": []},
        ]
        drain_mock.side_effect = [
            {"processed": 1497, "followup_queued": 12, "quota_limited": False}
        ]

        summary = daily_ops_orchestrator.run_daily_ops(
            object(),
            build_args(
                stage_rpm=f"{SCREENING_STAGE}=1500,{EXTRACTION_STAGE}=15",
                screening_prefill_stall_limit=1,
            ),
            sleep_fn=Mock(),
            now_fn=Mock(return_value=0.0),
        )

        self.assertEqual(summary["stopped_reason"], "source_exhausted")
        self.assertEqual(summary["screened"], 1497)
        self.assertEqual(summary["routed_to_gemini"], 12)
        self.assertEqual(drain_mock.call_count, 1)
        self.assertEqual(drain_mock.call_args_list[0].kwargs["stage_key"], SCREENING_STAGE)
        self.assertEqual(drain_mock.call_args_list[0].kwargs["max_tasks"], 1497)
        self.assertEqual(crawl_mock.call_count, 2)

    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_minute_quota_after_progress_sleeps_and_resumes_same_stage(
        self,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        fetch_state_mock.return_value = {"papers": queued_papers(SCREENING_STAGE, 1500)}
        drain_mock.side_effect = [
            {"processed": 8, "requeued": 1, "quota_limited": True},
            {"processed": 1, "requeued": 1, "quota_limited": True},
            {"processed": 0, "quota_limited": False},
        ]
        sleep_mock = Mock()

        summary = daily_ops_orchestrator.run_daily_ops(
            object(),
            build_args(),
            sleep_fn=sleep_mock,
            now_fn=Mock(return_value=0.0),
        )

        self.assertEqual(summary["stage_summaries"][SCREENING_STAGE]["minute_quota_events"], 1)
        self.assertEqual(summary["stage_summaries"][SCREENING_STAGE]["model_calls"], 7)
        self.assertTrue(summary["stage_summaries"][SCREENING_STAGE]["quota_exhausted"])
        self.assertEqual(sleep_mock.call_args_list[0].args[0], 65.0)
        self.assertEqual(drain_mock.call_args_list[0].kwargs["stage_key"], SCREENING_STAGE)
        self.assertEqual(drain_mock.call_args_list[1].kwargs["stage_key"], SCREENING_STAGE)
        crawl_mock.assert_not_called()

    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_screening_prefill_refills_english_batch(
        self,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        fetch_state_mock.side_effect = [
            {"papers": queued_papers(SCREENING_STAGE, 10)},
            {"papers": queued_papers(SCREENING_STAGE, 10)},
            {"papers": queued_papers(SCREENING_STAGE, 30)},
            {"papers": queued_papers(EXTRACTION_STAGE, 1)},
            {"papers": queued_papers(EXTRACTION_STAGE, 1)},
        ]
        drain_mock.side_effect = [
            {"processed": 1, "requeued": 1, "quota_limited": True},
            {"processed": 1, "requeued": 1, "quota_limited": True},
        ]

        summary = daily_ops_orchestrator.run_daily_ops(
            object(),
            build_args(
                screening_daily_target=30,
                screening_refill_batch_en=75,
                screening_refill_chunk_en=5,
            ),
            sleep_fn=Mock(),
            now_fn=Mock(return_value=0.0),
        )

        crawl_mock.assert_called_once()
        self.assertEqual(crawl_mock.call_args.kwargs["deficits"], {"en": 5, "tr": 0})
        self.assertFalse(crawl_mock.call_args.kwargs["process_ai_after_upload"])
        self.assertEqual(summary["stage_summaries"][SCREENING_STAGE]["refill_requested_en"], 5)

    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_requeued_error_only_screening_task_does_not_monopolize_refill(
        self,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        fetch_state_mock.side_effect = [
            {"papers": queued_papers(SCREENING_STAGE, 1)},
            {"papers": queued_papers(SCREENING_STAGE, 31)},
            {"papers": queued_papers(SCREENING_STAGE, 31)},
            {"papers": queued_papers(EXTRACTION_STAGE, 1)},
            {"papers": queued_papers(EXTRACTION_STAGE, 1)},
        ]
        drain_mock.side_effect = [
            {"processed": 1, "requeued": 1, "quota_limited": True},
            {"processed": 1, "requeued": 1, "quota_limited": True},
        ]

        summary = daily_ops_orchestrator.run_daily_ops(
            object(),
            build_args(
                screening_daily_target=0,
                screening_refill_batch_en=75,
                screening_refill_chunk_en=5,
            ),
            sleep_fn=Mock(),
            now_fn=Mock(return_value=0.0),
        )

        crawl_mock.assert_called_once()
        self.assertEqual(crawl_mock.call_args.kwargs["deficits"], {"en": 5, "tr": 0})
        self.assertEqual(summary["stage_summaries"][SCREENING_STAGE]["model_calls"], 0)
        self.assertEqual(summary["stage_summaries"][SCREENING_STAGE]["refill_requested_en"], 5)

    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.assign_ready_papers")
    def test_quota_drain_simulation_reports_stage_totals(
        self,
        assign_mock: Mock,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        assign_mock.return_value = {"satisfied": False, "planned_general_queue_papers": 2}
        fetch_state_mock.return_value = {
            "papers": queued_papers(SCREENING_STAGE, 120) + queued_papers(EXTRACTION_STAGE, 120)
        }
        drain_mock.side_effect = [
            {"processed": 15, "followup_queued": 9, "quota_limited": False},
            {"processed": 15, "followup_queued": 8, "quota_limited": False},
            {"processed": 2, "followup_queued": 1, "requeued": 1, "quota_limited": True},
            {"processed": 15, "human_ready": 6, "quota_limited": False},
            {"processed": 6, "human_ready": 2, "requeued": 1, "quota_limited": True},
            {"processed": 1, "requeued": 1, "quota_limited": True},
        ]
        sleep_mock = Mock()

        summary = daily_ops_orchestrator.run_daily_ops(
            object(),
            build_args(screening_daily_target=31),
            sleep_fn=sleep_mock,
            now_fn=Mock(return_value=0.0),
        )

        self.assertEqual(summary["stopped_reason"], "extraction_daily_quota_exhausted")
        self.assertEqual(summary["screened"], 31)
        self.assertEqual(summary["routed_to_gemini"], 18)
        self.assertEqual(summary["gemini_used"], 20)
        self.assertEqual(summary["human_ready"], 8)
        self.assertEqual(summary["quota_exhausted_stages"], [EXTRACTION_STAGE])
        self.assertEqual(sleep_mock.call_count, 4)
        self.assertEqual(assign_mock.call_count, 1)
        crawl_mock.assert_not_called()

    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_dry_run_reports_refill_without_writes(
        self,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        fetch_state_mock.return_value = {"papers": []}

        summary = daily_ops_orchestrator.run_daily_ops(
            object(),
            build_args(dry_run=True),
            sleep_fn=Mock(),
            now_fn=Mock(return_value=0.0),
        )

        self.assertEqual(summary["stopped_reason"], "dry_run")
        self.assertEqual(summary["stage_summaries"][SCREENING_STAGE]["planned_refill"]["en"], 1500)
        drain_mock.assert_not_called()
        crawl_mock.assert_not_called()

    def test_tick_prefill_target_is_immediate_slice_at_day_start(self) -> None:
        self.assertEqual(
            daily_ops_orchestrator._screening_tick_prefill_target(
                completed_today=0,
                daily_target=1500,
                tick_tasks=15,
            ),
            15,
        )

    def test_tick_refill_request_never_exceeds_immediate_deficit(self) -> None:
        self.assertEqual(
            daily_ops_orchestrator._tick_refill_request_size(
                build_args(screening_refill_batch_en=1500, screening_refill_chunk_en=1500),
                7,
            ),
            (7, 0),
        )

    def test_extraction_quota_day_uses_pacific_midnight(self) -> None:
        now = datetime(2026, 5, 29, 8, 30, tzinfo=timezone.utc)

        self.assertEqual(
            daily_ops_orchestrator._quota_day_start_iso(
                timezone_name="America/Los_Angeles",
                now=now,
            ),
            "2026-05-29T00:00:00-07:00",
        )
        self.assertEqual(
            daily_ops_orchestrator._quota_day_start_iso(timezone_name="UTC", now=now),
            "2026-05-29T00:00:00+00:00",
        )

    def test_quota_day_summary_includes_triage_stage(self) -> None:
        now = datetime(2026, 5, 29, 8, 30, tzinfo=timezone.utc)

        starts, timezones = daily_ops_orchestrator._stage_quota_day_starts(
            build_args(triage_stage_key=TRIAGE_STAGE),
            screening_stage_key=SCREENING_STAGE,
            extraction_stage_key=EXTRACTION_STAGE,
            triage_stage_key=TRIAGE_STAGE,
            now=now,
        )

        self.assertEqual(starts[TRIAGE_STAGE], "2026-05-29T00:00:00-07:00")
        self.assertEqual(timezones[TRIAGE_STAGE], "America/Los_Angeles")

    @patch("scripts.daily_ops_orchestrator._count_queued_stage_tasks", return_value=0)
    @patch("scripts.daily_ops_orchestrator._final_queue_snapshot")
    @patch("scripts.daily_ops_orchestrator._fetch_active_stage_counts")
    @patch("scripts.daily_ops_orchestrator._count_completed_stage_tasks_since", return_value=0)
    @patch("scripts.daily_ops_orchestrator._requeue_stale_stage_tasks")
    @patch("scripts.daily_ops_orchestrator._run_controller_storage_cleanup", return_value={})
    def test_controller_summary_and_stale_requeue_include_triage_stage(
        self,
        _storage_mock: Mock,
        requeue_mock: Mock,
        _completed_mock: Mock,
        active_counts_mock: Mock,
        final_snapshot_mock: Mock,
        _queued_mock: Mock,
    ) -> None:
        active_counts_mock.return_value = {
            "total": 0,
            SCREENING_STAGE: 0,
            TRIAGE_STAGE: 0,
            EXTRACTION_STAGE: 0,
        }
        final_snapshot_mock.return_value = {
            "total": 0,
            SCREENING_STAGE: 0,
            TRIAGE_STAGE: 0,
            EXTRACTION_STAGE: 0,
        }

        summary = daily_ops_orchestrator.run_daily_ops_controller(
            object(),
            build_args(triage_stage_key=TRIAGE_STAGE, screening_daily_target=0),
        )

        self.assertEqual(summary["stage_order"], [SCREENING_STAGE, TRIAGE_STAGE, EXTRACTION_STAGE])
        self.assertIn(TRIAGE_STAGE, summary["quota_day_starts"])
        self.assertIn(TRIAGE_STAGE, summary["daily_completed"])
        self.assertIn(TRIAGE_STAGE, summary["remaining_queued"])
        self.assertEqual(
            [call.kwargs["stage_key"] for call in requeue_mock.call_args_list],
            [SCREENING_STAGE, TRIAGE_STAGE, EXTRACTION_STAGE],
        )

    def test_drain_only_import_path_does_not_require_sentence_transformers(self) -> None:
        script = """
import builtins
import sys
from pathlib import Path
root = Path.cwd() / 'services' / 'data-pipeline'
sys.path.insert(0, str(root))
original_import = builtins.__import__
def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == 'sentence_transformers' or name.startswith('sentence_transformers.'):
        raise AssertionError('drain import tried to load sentence-transformers')
    return original_import(name, globals, locals, fromlist, level)
builtins.__import__ = guarded_import
import scripts.daily_ops_orchestrator as orchestrator
orchestrator.build_parser()
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[3],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_daily_ops_workflow_uses_light_worker_requirements_and_tuned_gemma_slice(self) -> None:
        workflow = (Path(__file__).resolve().parents[3] / ".github" / "workflows" / "daily-ops.yml").read_text()

        self.assertIn("services/data-pipeline/requirements-worker.txt", workflow)
        self.assertIn("--screening-active-target 150", workflow)
        self.assertIn("--screening-refill-batch-en 150", workflow)
        self.assertIn("--screening-tick-tasks 20", workflow)
        self.assertNotIn("opennutri-worker-${{ github.run_id }}", workflow)

    @patch("scripts.daily_ops_orchestrator._count_queued_stage_tasks")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_queue_counts_use_stage_tasks_over_stale_paper_routes(
        self,
        fetch_state_mock: Mock,
        count_tasks_mock: Mock,
    ) -> None:
        fetch_state_mock.return_value = {
            "papers": queued_papers(SCREENING_STAGE, 18) + queued_papers(EXTRACTION_STAGE, 351),
        }
        count_tasks_mock.side_effect = [0, 369]

        counts = daily_ops_orchestrator._fetch_queue_counts(
            object(),
            screening_stage_key=SCREENING_STAGE,
            extraction_stage_key=EXTRACTION_STAGE,
        )

        self.assertEqual(counts["total"], 369)
        self.assertEqual(counts[SCREENING_STAGE], 0)
        self.assertEqual(counts[EXTRACTION_STAGE], 369)

    def test_active_stage_count_includes_queued_and_non_stale_processing_tasks(self) -> None:
        now = datetime.now(timezone.utc)
        client = CountClient(
            [
                {"id": "queued-1", "stage_key": SCREENING_STAGE, "status": "queued"},
                {"id": "queued-2", "stage_key": SCREENING_STAGE, "status": "queued"},
                {
                    "id": "processing-fresh",
                    "stage_key": SCREENING_STAGE,
                    "status": "processing",
                    "started_at": (now - timedelta(minutes=5)).isoformat(),
                },
                {
                    "id": "processing-stale",
                    "stage_key": SCREENING_STAGE,
                    "status": "processing",
                    "started_at": (now - timedelta(hours=3)).isoformat(),
                },
                {"id": "completed", "stage_key": SCREENING_STAGE, "status": "completed"},
                {
                    "id": "gemini-processing",
                    "stage_key": EXTRACTION_STAGE,
                    "status": "processing",
                    "started_at": (now - timedelta(minutes=10)).isoformat(),
                },
            ]
        )

        counts = daily_ops_orchestrator._fetch_active_stage_counts(
            client,
            screening_stage_key=SCREENING_STAGE,
            extraction_stage_key=EXTRACTION_STAGE,
            stale_after_minutes=120,
        )

        self.assertEqual(counts[SCREENING_STAGE], 3)
        self.assertEqual(counts[EXTRACTION_STAGE], 1)
        self.assertEqual(counts["total"], 4)

    @patch("scripts.daily_ops_orchestrator._count_completed_stage_tasks_since")
    @patch("scripts.daily_ops_orchestrator._fetch_active_stage_counts")
    @patch("scripts.daily_ops_orchestrator._run_controller_storage_cleanup")
    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    def test_controller_refills_only_active_target_deficit_without_draining(
        self,
        drain_mock: Mock,
        crawl_mock: Mock,
        storage_mock: Mock,
        active_counts_mock: Mock,
        count_completed_mock: Mock,
    ) -> None:
        storage_mock.return_value = {"remaining_bytes_after_cleanup": 100}
        count_completed_mock.side_effect = [0, 0]
        active_counts_mock.side_effect = [
            {"total": 21, SCREENING_STAGE: 20, EXTRACTION_STAGE: 1},
            {"total": 76, SCREENING_STAGE: 75, EXTRACTION_STAGE: 1},
            {"total": 75, SCREENING_STAGE: 75, EXTRACTION_STAGE: 0},
        ]

        summary = daily_ops_orchestrator.run_daily_ops_controller(
            object(),
            build_args(
                controller_only=True,
                screening_active_target=75,
                screening_refill_batch_en=75,
                screening_refill_chunk_en=75,
            ),
        )

        self.assertEqual(summary["mode"], "controller")
        self.assertEqual(summary["stopped_reason"], "controller_refill_complete")
        crawl_mock.assert_called_once()
        self.assertEqual(crawl_mock.call_args.kwargs["deficits"], {"en": 55, "tr": 0})
        drain_mock.assert_not_called()

    @patch("scripts.daily_ops_orchestrator._count_completed_stage_tasks_since")
    @patch("scripts.daily_ops_orchestrator._fetch_active_stage_counts")
    @patch("scripts.daily_ops_orchestrator._run_controller_storage_cleanup")
    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    def test_storage_soft_limit_blocks_controller_refill_not_worker_drain(
        self,
        drain_mock: Mock,
        crawl_mock: Mock,
        storage_mock: Mock,
        active_counts_mock: Mock,
        count_completed_mock: Mock,
    ) -> None:
        storage_mock.return_value = {"remaining_bytes_after_cleanup": 901 * 1024 * 1024}
        count_completed_mock.side_effect = [0, 0]
        active_counts_mock.side_effect = [
            {"total": 0, SCREENING_STAGE: 0, EXTRACTION_STAGE: 0},
            {"total": 0, SCREENING_STAGE: 0, EXTRACTION_STAGE: 0},
        ]

        controller_summary = daily_ops_orchestrator.run_daily_ops_controller(
            object(),
            build_args(controller_only=True, screening_active_target=75, paper_bucket_soft_limit_mb=900),
        )

        self.assertEqual(controller_summary["stopped_reason"], "storage_soft_limit_exceeded")
        crawl_mock.assert_not_called()
        drain_mock.assert_not_called()

        with patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state") as fetch_state_mock:
            count_completed_mock.side_effect = [0, 0]
            fetch_state_mock.side_effect = [
                {"papers": queued_papers(SCREENING_STAGE, 3)},
                {"papers": queued_papers(SCREENING_STAGE, 1)},
            ]
            drain_mock.return_value = {"processed": 3, "followup_queued": 1, "quota_limited": False}

            worker_summary = daily_ops_orchestrator.run_daily_ops_drain(
                object(),
                build_args(drain_only=True, screening_tick_tasks=3),
            )

        self.assertEqual(worker_summary["mode"], "drain")
        self.assertEqual(worker_summary["screened"], 3)
        self.assertEqual(drain_mock.call_count, 1)
        crawl_mock.assert_not_called()
        storage_mock.assert_called_once()

    @patch("scripts.daily_ops_orchestrator._count_completed_stage_tasks_since")
    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_drain_only_never_refills_or_uploads(
        self,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
        count_completed_mock: Mock,
    ) -> None:
        count_completed_mock.side_effect = [0, 0, 0]
        fetch_state_mock.side_effect = [
            {"papers": queued_papers(SCREENING_STAGE, 4) + queued_papers(EXTRACTION_STAGE, 2)},
            {"papers": queued_papers(SCREENING_STAGE, 1) + queued_papers(EXTRACTION_STAGE, 2)},
            {"papers": queued_papers(EXTRACTION_STAGE, 2)},
        ]
        drain_mock.side_effect = [
            {"processed": 4, "followup_queued": 2, "quota_limited": False},
            {"processed": 2, "human_ready": 0, "quota_limited": False},
        ]

        summary = daily_ops_orchestrator.run_daily_ops_drain(
            object(),
            build_args(drain_only=True, interleave_extraction=True, screening_tick_tasks=4, extraction_tick_tasks=2),
        )

        self.assertEqual(summary["mode"], "drain")
        self.assertEqual(summary["screened"], 4)
        self.assertEqual(summary["gemini_used"], 2)
        self.assertEqual(drain_mock.call_count, 2)
        self.assertEqual(drain_mock.call_args_list[0].kwargs["requeue_stale_minutes"], 0)
        self.assertEqual(drain_mock.call_args_list[1].kwargs["requeue_stale_minutes"], 0)
        crawl_mock.assert_not_called()

    @patch("scripts.daily_ops_orchestrator._count_completed_stage_tasks_since")
    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_tick_refills_then_drains_available_gemma_slice(
        self,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
        count_completed_mock: Mock,
    ) -> None:
        count_completed_mock.side_effect = [0, 0]
        fetch_state_mock.side_effect = [
            {"papers": []},
            {"papers": queued_papers(SCREENING_STAGE, 15)},
            {"papers": queued_papers(SCREENING_STAGE, 15)},
        ]
        drain_mock.return_value = {"processed": 15, "followup_queued": 2, "quota_limited": False}

        summary = daily_ops_orchestrator.run_daily_ops_tick(object(), build_args())

        self.assertEqual(summary["mode"], "tick")
        self.assertEqual(summary["screened"], 15)
        self.assertEqual(summary["routed_to_gemini"], 2)
        crawl_mock.assert_called_once()
        self.assertEqual(summary["stage_summaries"][SCREENING_STAGE]["tick_prefill_target"], 15)
        self.assertEqual(crawl_mock.call_args.kwargs["deficits"], {"en": 15, "tr": 0})
        self.assertEqual(drain_mock.call_count, 1)
        self.assertEqual(drain_mock.call_args.kwargs["stage_key"], SCREENING_STAGE)
        self.assertEqual(drain_mock.call_args.kwargs["max_tasks"], 15)

    @patch("scripts.daily_ops_orchestrator._count_completed_stage_tasks_since")
    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_tick_does_not_refill_when_existing_gemma_queue_exceeds_slice(
        self,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
        count_completed_mock: Mock,
    ) -> None:
        count_completed_mock.side_effect = [0, 0]
        fetch_state_mock.side_effect = [
            {"papers": queued_papers(SCREENING_STAGE, 1497)},
            {"papers": queued_papers(SCREENING_STAGE, 1482)},
        ]
        drain_mock.return_value = {"processed": 15, "followup_queued": 2, "quota_limited": False}

        summary = daily_ops_orchestrator.run_daily_ops_tick(object(), build_args())

        self.assertEqual(summary["screened"], 15)
        self.assertEqual(summary["stage_summaries"][SCREENING_STAGE]["tick_prefill_target"], 15)
        crawl_mock.assert_not_called()
        self.assertEqual(drain_mock.call_args.kwargs["max_tasks"], 15)

    @patch("scripts.daily_ops_orchestrator._count_completed_stage_tasks_since")
    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_tick_does_not_repeat_full_refill_after_gemma_phase_started(
        self,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
        count_completed_mock: Mock,
    ) -> None:
        count_completed_mock.side_effect = [15, 0]
        fetch_state_mock.side_effect = [
            {"papers": queued_papers(SCREENING_STAGE, 1482)},
            {"papers": queued_papers(SCREENING_STAGE, 1467)},
        ]
        drain_mock.return_value = {"processed": 15, "followup_queued": 1, "quota_limited": False}

        summary = daily_ops_orchestrator.run_daily_ops_tick(object(), build_args())

        self.assertEqual(summary["screened"], 15)
        self.assertEqual(summary["stage_summaries"][SCREENING_STAGE]["tick_prefill_target"], 15)
        crawl_mock.assert_not_called()
        self.assertEqual(drain_mock.call_args.kwargs["max_tasks"], 15)

    @patch("scripts.daily_ops_orchestrator._count_completed_stage_tasks_since")
    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.assign_ready_papers")
    def test_tick_can_interleave_gemini_from_ranked_candidates(
        self,
        assign_mock: Mock,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
        count_completed_mock: Mock,
    ) -> None:
        assign_mock.return_value = {"satisfied": False, "planned_general_queue_papers": 1}
        count_completed_mock.side_effect = [25, 0, 0]
        fetch_state_mock.side_effect = [
            {"papers": queued_papers(SCREENING_STAGE, 100) + queued_papers(EXTRACTION_STAGE, 4)},
            {"papers": queued_papers(SCREENING_STAGE, 85) + queued_papers(EXTRACTION_STAGE, 4)},
            {"papers": queued_papers(SCREENING_STAGE, 85) + queued_papers(EXTRACTION_STAGE, 2)},
        ]
        drain_mock.side_effect = [
            {"processed": 15, "followup_queued": 2, "quota_limited": False},
            {"processed": 2, "human_ready": 1, "quota_limited": False},
        ]

        summary = daily_ops_orchestrator.run_daily_ops_tick(
            object(),
            build_args(interleave_extraction=True, extraction_tick_tasks=2),
        )

        self.assertEqual(summary["screened"], 15)
        self.assertEqual(summary["gemini_used"], 2)
        self.assertEqual(summary["human_ready"], 1)
        self.assertEqual(summary["interleaved_extraction_reason"], "tick_complete")
        crawl_mock.assert_not_called()
        self.assertEqual(drain_mock.call_args_list[0].kwargs["stage_key"], SCREENING_STAGE)
        self.assertEqual(drain_mock.call_args_list[1].kwargs["stage_key"], EXTRACTION_STAGE)
        self.assertEqual(drain_mock.call_args_list[1].kwargs["max_tasks"], 2)
        assign_mock.assert_called_once()

    @patch("scripts.daily_ops_orchestrator._count_completed_stage_tasks_since")
    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.assign_ready_papers")
    def test_tick_interleaves_gemini_when_gemma_source_is_empty(
        self,
        assign_mock: Mock,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
        count_completed_mock: Mock,
    ) -> None:
        assign_mock.return_value = {"satisfied": False, "planned_general_queue_papers": 1}
        count_completed_mock.side_effect = [100, 10, 10]
        fetch_state_mock.side_effect = [
            {"papers": queued_papers(EXTRACTION_STAGE, 5)},
            {"papers": queued_papers(EXTRACTION_STAGE, 5)},
            {"papers": queued_papers(EXTRACTION_STAGE, 5)},
        ]
        drain_mock.return_value = {"processed": 2, "human_ready": 1, "quota_limited": False}

        summary = daily_ops_orchestrator.run_daily_ops_tick(
            object(),
            build_args(
                interleave_extraction=True,
                extraction_tick_tasks=2,
                screening_refill_batch_en=15,
                screening_refill_chunk_en=15,
            ),
        )

        self.assertEqual(summary["stopped_reason"], "source_exhausted")
        self.assertEqual(summary["interleaved_extraction_reason"], "tick_complete")
        self.assertEqual(summary["screened"], 0)
        self.assertEqual(summary["gemini_used"], 2)
        self.assertEqual(summary["human_ready"], 1)
        crawl_mock.assert_called_once()
        self.assertEqual(drain_mock.call_count, 1)
        self.assertEqual(drain_mock.call_args.kwargs["stage_key"], EXTRACTION_STAGE)
        self.assertEqual(drain_mock.call_args.kwargs["max_tasks"], 2)
        assign_mock.assert_called_once()

    @patch("scripts.daily_ops_orchestrator._count_completed_stage_tasks_since")
    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_tick_moves_to_gemini_after_daily_gemma_target(
        self,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
        count_completed_mock: Mock,
    ) -> None:
        count_completed_mock.side_effect = [1500, 0]
        fetch_state_mock.return_value = {"papers": queued_papers(EXTRACTION_STAGE, 20)}
        drain_mock.return_value = {"processed": 15, "human_ready": 4, "quota_limited": False}

        summary = daily_ops_orchestrator.run_daily_ops_tick(object(), build_args())

        self.assertEqual(summary["gemini_used"], 15)
        self.assertEqual(summary["human_ready"], 4)
        crawl_mock.assert_not_called()
        self.assertEqual(drain_mock.call_count, 1)
        self.assertEqual(drain_mock.call_args.kwargs["stage_key"], EXTRACTION_STAGE)
        self.assertEqual(drain_mock.call_args.kwargs["max_tasks"], 15)

    @patch("scripts.daily_ops_orchestrator._count_completed_stage_tasks_since")
    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_tick_stops_after_daily_gemini_target(
        self,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
        count_completed_mock: Mock,
    ) -> None:
        count_completed_mock.side_effect = [1500, 20]

        summary = daily_ops_orchestrator.run_daily_ops_tick(object(), build_args())

        self.assertEqual(summary["stopped_reason"], "daily_targets_reached")
        crawl_mock.assert_not_called()
        drain_mock.assert_not_called()

    def test_downstream_drains_triage_before_extraction(self) -> None:
        calls: list[tuple[str, str]] = []

        def fake_followup(_client, _args, *, stage_key, role, **_kwargs):
            calls.append((role, stage_key))
            return "tick_complete"

        summary = {"stage_summaries": {}}
        with patch.object(daily_ops_orchestrator, "_tick_drain_followup_stage", side_effect=fake_followup):
            daily_ops_orchestrator._tick_drain_downstream(
                object(),
                build_args(triage_stage_key=TRIAGE_STAGE),
                summary=summary,
                screening_stage_key=SCREENING_STAGE,
                extraction_stage_key=EXTRACTION_STAGE,
                extraction_daily_target=20,
                extraction_tick_tasks=2,
                stage_rpm={TRIAGE_STAGE: 20, EXTRACTION_STAGE: 15},
                day_start_iso="2026-05-29T00:00:00-07:00",
            )

        self.assertEqual(calls, [("triage", TRIAGE_STAGE), ("extraction", EXTRACTION_STAGE)])
        self.assertEqual(summary["interleaved_triage_reason"], "tick_complete")

    def test_downstream_skips_triage_when_disabled(self) -> None:
        calls: list[tuple[str, str]] = []

        def fake_followup(_client, _args, *, stage_key, role, **_kwargs):
            calls.append((role, stage_key))
            return "tick_complete"

        summary = {"stage_summaries": {}}
        with patch.object(daily_ops_orchestrator, "_tick_drain_followup_stage", side_effect=fake_followup):
            daily_ops_orchestrator._tick_drain_downstream(
                object(),
                build_args(triage_stage_key=""),
                summary=summary,
                screening_stage_key=SCREENING_STAGE,
                extraction_stage_key=EXTRACTION_STAGE,
                extraction_daily_target=20,
                extraction_tick_tasks=2,
                stage_rpm={EXTRACTION_STAGE: 15},
                day_start_iso="2026-05-29T00:00:00-07:00",
            )

        self.assertEqual(calls, [("extraction", EXTRACTION_STAGE)])
        self.assertNotIn("interleaved_triage_reason", summary)

    @patch("scripts.daily_ops_orchestrator._count_queued_stage_tasks")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_fetch_queue_counts_include_triage_stage(
        self,
        fetch_state_mock: Mock,
        count_tasks_mock: Mock,
    ) -> None:
        fetch_state_mock.return_value = {"papers": []}
        # _fetch_queue_counts queries screening, then extraction, then triage.
        count_tasks_mock.side_effect = [5, 400, 30]

        counts = daily_ops_orchestrator._fetch_queue_counts(
            object(),
            screening_stage_key=SCREENING_STAGE,
            extraction_stage_key=EXTRACTION_STAGE,
            triage_stage_key=TRIAGE_STAGE,
        )

        self.assertEqual(counts[TRIAGE_STAGE], 30)
        self.assertEqual(counts[EXTRACTION_STAGE], 400)
        self.assertEqual(counts["total"], 435)


if __name__ == "__main__":
    unittest.main()
