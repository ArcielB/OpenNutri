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
        "max_wallclock_minutes": 0,
        "screening_daily_target": 1500,
        "screening_tick_tasks": 15,
        "extraction_daily_target": 20,
        "extraction_tick_tasks": 15,
        "interleave_extraction": False,
        "screening_queue_low_watermark": 30,
        "screening_refill_batch_en": 1500,
        "screening_refill_chunk_en": 1500,
        "screening_prefill_stall_limit": 3,
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
            {"papers": queued_papers(SCREENING_STAGE, 1497)},
            {"papers": queued_papers(SCREENING_STAGE, 1497)},
            {"papers": queued_papers(SCREENING_STAGE, 1497)},
        ]
        drain_mock.return_value = {"processed": 15, "followup_queued": 2, "quota_limited": False}

        summary = daily_ops_orchestrator.run_daily_ops_tick(object(), build_args())

        self.assertEqual(summary["mode"], "tick")
        self.assertEqual(summary["screened"], 15)
        self.assertEqual(summary["routed_to_gemini"], 2)
        crawl_mock.assert_called_once()
        self.assertEqual(crawl_mock.call_args.kwargs["deficits"], {"en": 1500, "tr": 0})
        self.assertEqual(drain_mock.call_count, 1)
        self.assertEqual(drain_mock.call_args.kwargs["stage_key"], SCREENING_STAGE)
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


if __name__ == "__main__":
    unittest.main()
