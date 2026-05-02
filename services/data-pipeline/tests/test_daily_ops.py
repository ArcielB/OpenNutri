from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import daily_ops_orchestrator, refill_assignment_queue


def build_args(**overrides):
    defaults = {
        "target_open": 50,
        "max_cycles": 4,
        "max_ai_tasks": 5,
        "daily_ai_call_budget": 20,
        "ai_tasks_already_used": 0,
        "refill_step_en": 4,
        "refill_step_tr": 4,
        "seed": 20260413,
        "data_dir": "services/data-pipeline/data",
        "query_limit": 50,
        "max_queries": 80,
        "dergipark_journal_limit": 0,
        "dergipark_max_issues_per_journal": 12,
        "skip_feedback": False,
        "skip_dergipark_refresh": False,
        "dry_run": False,
        "json_summary": True,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class DailyOpsTests(unittest.TestCase):
    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_existing_queued_ai_is_processed_before_crawl(
        self,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        fetch_state_mock.return_value = {"papers": [{"routing_status": "queued_for_ai"}]}
        drain_mock.return_value = {"processed": 1, "quota_limited": False}

        summary = daily_ops_orchestrator.run_daily_ops(object(), build_args(max_ai_tasks=1))

        self.assertEqual(summary["stopped_reason"], "ai_run_budget_exhausted")
        self.assertEqual(summary["ai_tasks_used"], 1)
        drain_mock.assert_called_once()
        self.assertEqual(drain_mock.call_args.kwargs["max_tasks"], 1)
        crawl_mock.assert_not_called()

    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_daily_budget_terminal_before_work(
        self,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        summary = daily_ops_orchestrator.run_daily_ops(
            object(),
            build_args(ai_tasks_already_used=20, daily_ai_call_budget=20),
        )

        self.assertEqual(summary["stopped_reason"], "daily_ai_call_budget_exhausted")
        self.assertTrue(summary["terminal"])
        fetch_state_mock.assert_not_called()
        drain_mock.assert_not_called()
        crawl_mock.assert_not_called()

    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.assign_ready_papers")
    def test_queued_ai_quota_stops_before_crawl(
        self,
        assign_mock: Mock,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        assign_mock.return_value = {"satisfied": False, "made_progress": False}
        fetch_state_mock.return_value = {"papers": [{"routing_status": "queued_for_ai"}]}
        drain_mock.return_value = {
            "processed": 1,
            "requeued": 1,
            "quota_limited": True,
        }

        summary = daily_ops_orchestrator.run_daily_ops(object(), build_args())

        self.assertEqual(summary["stopped_reason"], "ai_first_task_quota_limited")
        self.assertTrue(summary["terminal"])
        drain_mock.assert_called_once()
        crawl_mock.assert_not_called()

    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.assign_ready_papers")
    def test_queued_ai_quota_assigns_new_human_ready_before_stop(
        self,
        assign_mock: Mock,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        assign_mock.return_value = {"satisfied": False, "made_progress": True, "planned_user_assignments": 2}
        fetch_state_mock.return_value = {"papers": [{"routing_status": "queued_for_ai"}]}
        drain_mock.return_value = {
            "processed": 2,
            "human_ready": 1,
            "requeued": 1,
            "quota_limited": True,
        }

        summary = daily_ops_orchestrator.run_daily_ops(object(), build_args())

        self.assertEqual(summary["stopped_reason"], "ai_quota_limited_after_progress")
        self.assertFalse(summary["terminal"])
        self.assertEqual(assign_mock.call_count, 1)
        self.assertEqual(summary["cycles"][0]["assignment_after_ai"]["planned_user_assignments"], 2)
        crawl_mock.assert_not_called()

    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.assign_ready_papers")
    def test_ai_task_budget_is_per_run_and_assigns_new_human_ready(
        self,
        assign_mock: Mock,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        assign_mock.return_value = {"satisfied": False, "made_progress": True, "planned_user_assignments": 2}
        fetch_state_mock.return_value = {"papers": [{"routing_status": "queued_for_ai"}]}
        drain_mock.return_value = {
            "processed": 1,
            "human_ready": 1,
            "quota_limited": False,
        }

        summary = daily_ops_orchestrator.run_daily_ops(object(), build_args(max_ai_tasks=1))

        self.assertEqual(summary["stopped_reason"], "ai_run_budget_exhausted")
        self.assertFalse(summary["terminal"])
        self.assertEqual(summary["ai_tasks_used"], 1)
        self.assertEqual(assign_mock.call_count, 1)
        self.assertEqual(drain_mock.call_args.kwargs["max_tasks"], 1)
        self.assertEqual(summary["cycles"][0]["assignment_after_ai"]["planned_user_assignments"], 2)
        crawl_mock.assert_not_called()

    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_no_queued_ai_triggers_crawl_then_ai(
        self,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        fetch_state_mock.side_effect = [
            {"papers": []},
            {"papers": [{"routing_status": "queued_for_ai"}]},
        ]
        drain_mock.return_value = {
            "processed": 1,
            "quota_limited": False,
        }

        summary = daily_ops_orchestrator.run_daily_ops(object(), build_args(max_ai_tasks=1))

        self.assertEqual(summary["stopped_reason"], "ai_run_budget_exhausted")
        crawl_mock.assert_called_once()
        drain_mock.assert_called_once()
        self.assertEqual(crawl_mock.call_args.kwargs["deficits"], {"en": 4, "tr": 4})
        self.assertFalse(crawl_mock.call_args.kwargs["args"].skip_feedback)
        self.assertFalse(crawl_mock.call_args.kwargs["args"].skip_dergipark_refresh)
        self.assertFalse(crawl_mock.call_args.kwargs["process_ai_after_upload"])

    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.assign_ready_papers")
    def test_after_crawl_quota_assigns_new_human_ready_before_stop(
        self,
        assign_mock: Mock,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        assign_mock.return_value = {"satisfied": False, "made_progress": True, "planned_user_assignments": 2}
        fetch_state_mock.side_effect = [
            {"papers": []},
            {"papers": [{"routing_status": "queued_for_ai"}]},
        ]
        drain_mock.return_value = {
            "processed": 2,
            "human_ready": 1,
            "requeued": 1,
            "quota_limited": True,
        }

        summary = daily_ops_orchestrator.run_daily_ops(object(), build_args())

        self.assertEqual(summary["stopped_reason"], "ai_quota_limited_after_progress")
        self.assertFalse(summary["terminal"])
        crawl_mock.assert_called_once()
        drain_mock.assert_called_once()
        self.assertEqual(assign_mock.call_count, 1)
        self.assertEqual(summary["cycles"][0]["assignment_after_ai"]["planned_user_assignments"], 2)

    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_crawl_zero_output_stops_no_progress(
        self,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        fetch_state_mock.side_effect = [
            {"papers": []},
            {"papers": []},
        ]

        summary = daily_ops_orchestrator.run_daily_ops(object(), build_args())

        self.assertEqual(summary["stopped_reason"], "no_progress")
        self.assertTrue(summary["terminal"])
        crawl_mock.assert_called_once()
        drain_mock.assert_not_called()

    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    def test_daily_budget_exhausted_after_processing(
        self,
        fetch_state_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        fetch_state_mock.return_value = {"papers": [{"routing_status": "queued_for_ai"}]}
        drain_mock.return_value = {"processed": 1, "quota_limited": False}

        summary = daily_ops_orchestrator.run_daily_ops(
            object(),
            build_args(ai_tasks_already_used=19, daily_ai_call_budget=20, max_ai_tasks=5),
        )

        self.assertEqual(summary["stopped_reason"], "daily_ai_call_budget_exhausted")
        self.assertTrue(summary["terminal"])
        self.assertEqual(summary["daily_ai_tasks_used"], 20)
        self.assertEqual(drain_mock.call_args.kwargs["max_tasks"], 1)
        crawl_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
