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
        "target_open": 10,
        "max_cycles": 4,
        "max_ai_tasks": 50,
        "refill_step_en": 4,
        "refill_step_tr": 4,
        "seed": 20260413,
        "data_dir": "services/data-pipeline/data",
        "query_limit": 50,
        "max_queries": 80,
        "dergipark_journal_limit": 0,
        "dergipark_max_issues_per_journal": 12,
        "skip_feedback": True,
        "skip_dergipark_refresh": True,
        "dry_run": False,
        "json_summary": True,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class DailyOpsTests(unittest.TestCase):
    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.assign_ready_papers")
    def test_full_queues_stop_without_ai_or_crawl(
        self,
        assign_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        assign_mock.return_value = {"satisfied": True, "made_progress": False}

        summary = daily_ops_orchestrator.run_daily_ops(object(), build_args())

        self.assertEqual(summary["stopped_reason"], "queues_full")
        drain_mock.assert_not_called()
        crawl_mock.assert_not_called()

    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.assign_ready_papers")
    def test_assignment_progress_loops_back_before_ai_or_crawl(
        self,
        assign_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        assign_mock.side_effect = [
            {"satisfied": False, "made_progress": True},
            {"satisfied": True, "made_progress": False},
        ]

        summary = daily_ops_orchestrator.run_daily_ops(object(), build_args())

        self.assertEqual(summary["stopped_reason"], "queues_full")
        self.assertEqual(assign_mock.call_count, 2)
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

        self.assertEqual(summary["stopped_reason"], "ai_quota_limited")
        drain_mock.assert_called_once()
        crawl_mock.assert_not_called()

    @patch("scripts.daily_ops_orchestrator.ensure_paper_stock.run_refill_cycle")
    @patch("scripts.daily_ops_orchestrator.drain_stage_queue")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.compute_assignment_context")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.fetch_state")
    @patch("scripts.daily_ops_orchestrator.refill_assignment_queue.assign_ready_papers")
    def test_no_queued_ai_triggers_crawl_then_ai(
        self,
        assign_mock: Mock,
        fetch_state_mock: Mock,
        context_mock: Mock,
        drain_mock: Mock,
        crawl_mock: Mock,
    ) -> None:
        assign_mock.side_effect = [
            {"satisfied": False, "made_progress": False},
            {"satisfied": True, "made_progress": False},
        ]
        fetch_state_mock.return_value = {
            "papers": [],
            "reviewer_profiles": [],
            "slot_members": [],
            "user_assignments": [],
            "slot_assignments": [],
            "review_outcomes": [],
            "global_labels": [],
        }
        profile = refill_assignment_queue.ReviewerProfile(
            id="profile-arciel",
            display_name="Arciel",
            active=True,
            can_review_en=True,
            can_review_tr=False,
            tester_access=False,
            official_slot="arciel",
            auth_user_id="auth-arciel",
        )
        context_mock.return_value = {
            "profiles": {"profile-arciel": profile},
            "deficits": {"profile-arciel": 4},
            "open_available": [],
        }
        drain_mock.return_value = {
            "processed": 1,
            "quota_limited": False,
        }

        summary = daily_ops_orchestrator.run_daily_ops(object(), build_args())

        self.assertEqual(summary["stopped_reason"], "queues_full")
        crawl_mock.assert_called_once()
        drain_mock.assert_called_once()
        self.assertEqual(crawl_mock.call_args.kwargs["deficits"], {"en": 4, "tr": 0})
        self.assertFalse(crawl_mock.call_args.kwargs["process_ai_after_upload"])


if __name__ == "__main__":
    unittest.main()
