from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import daily_ops_orchestrator, ensure_paper_stock, refill_assignment_queue


SCREENING_STAGE = "gemma_proof_extraction_v1"
EXTRACTION_STAGE = "gemini_flash_db_payload_v2"


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
        "max_wallclock_minutes": 330,
        "screening_queue_low_watermark": 30,
        "screening_refill_batch_en": 75,
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


class DailyOpsTests(unittest.TestCase):
    def test_default_stock_targets_are_english_only(self) -> None:
        args = build_args(target=None, target_en=None, target_tr=None)
        self.assertEqual(ensure_paper_stock.resolve_language_targets(args), {"en": 20, "tr": 0})
        self.assertEqual(refill_assignment_queue.language_deficits_for([], 50), {"en": 50, "tr": 0})

    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_gemma_drains_before_gemini_until_daily_quota(
        self,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        fetch_state_mock.return_value = {
            "papers": queued_papers(SCREENING_STAGE, 60) + queued_papers(EXTRACTION_STAGE, 60)
        }
        drain_mock.side_effect = [
            {"processed": 1, "requeued": 1, "quota_limited": True},
            {"processed": 1, "requeued": 1, "quota_limited": True},
        ]

        summary = daily_ops_orchestrator.run_daily_ops(
            object(),
            build_args(),
            sleep_fn=Mock(),
            now_fn=Mock(return_value=0.0),
        )

        self.assertEqual(summary["stopped_reason"], "all_stage_quotas_exhausted")
        self.assertEqual(summary["quota_exhausted_stages"], [SCREENING_STAGE, EXTRACTION_STAGE])
        self.assertEqual(drain_mock.call_args_list[0].kwargs["stage_key"], SCREENING_STAGE)
        self.assertEqual(drain_mock.call_args_list[1].kwargs["stage_key"], EXTRACTION_STAGE)
        crawl_mock.assert_not_called()

    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_minute_quota_after_progress_sleeps_and_resumes_same_stage(
        self,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        fetch_state_mock.return_value = {"papers": queued_papers(SCREENING_STAGE, 60)}
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
    def test_screening_low_watermark_refills_english_batch(
        self,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        fetch_state_mock.side_effect = [
            {"papers": queued_papers(SCREENING_STAGE, 10)},
            {"papers": queued_papers(SCREENING_STAGE, 75)},
            {"papers": queued_papers(SCREENING_STAGE, 75)},
            {"papers": queued_papers(EXTRACTION_STAGE, 1)},
            {"papers": queued_papers(EXTRACTION_STAGE, 1)},
        ]
        drain_mock.side_effect = [
            {"processed": 1, "requeued": 1, "quota_limited": True},
            {"processed": 1, "requeued": 1, "quota_limited": True},
        ]

        summary = daily_ops_orchestrator.run_daily_ops(
            object(),
            build_args(),
            sleep_fn=Mock(),
            now_fn=Mock(return_value=0.0),
        )

        crawl_mock.assert_called_once()
        self.assertEqual(crawl_mock.call_args.kwargs["deficits"], {"en": 75, "tr": 0})
        self.assertFalse(crawl_mock.call_args.kwargs["process_ai_after_upload"])
        self.assertEqual(summary["stage_summaries"][SCREENING_STAGE]["refill_requested_en"], 75)

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
            {"processed": 1, "requeued": 1, "quota_limited": True},
            {"processed": 15, "human_ready": 6, "quota_limited": False},
            {"processed": 6, "human_ready": 2, "requeued": 1, "quota_limited": True},
            {"processed": 1, "requeued": 1, "quota_limited": True},
        ]
        sleep_mock = Mock()

        summary = daily_ops_orchestrator.run_daily_ops(
            object(),
            build_args(),
            sleep_fn=sleep_mock,
            now_fn=Mock(return_value=0.0),
        )

        self.assertEqual(summary["stopped_reason"], "all_stage_quotas_exhausted")
        self.assertEqual(summary["screened"], 31)
        self.assertEqual(summary["routed_to_gemini"], 18)
        self.assertEqual(summary["gemini_used"], 20)
        self.assertEqual(summary["human_ready"], 8)
        self.assertEqual(summary["quota_exhausted_stages"], [SCREENING_STAGE, EXTRACTION_STAGE])
        self.assertEqual(sleep_mock.call_count, 5)
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
        self.assertEqual(summary["stage_summaries"][SCREENING_STAGE]["planned_refill"]["en"], 75)
        drain_mock.assert_not_called()
        crawl_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
