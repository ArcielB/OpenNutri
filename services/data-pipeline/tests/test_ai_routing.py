from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_routing import (
    HUMAN_REVIEW_DESTINATION,
    ROUTING_BUCKET_HIGH_NEGATIVE,
    ROUTING_BUCKET_HIGH_POSITIVE,
    ROUTING_BUCKET_LOW_NEGATIVE,
    ROUTING_BUCKET_LOW_POSITIVE,
    RoutingStageConfig,
    classify_routing_bucket,
    normalize_ai_payload,
    stable_audit_sample,
)
from food_paper_crawler.feedback.update_terms import build_labels
from scripts import ensure_paper_stock, refill_assignment_queue, upload_to_supabase
from scripts.backfill_ai_routing import cancel_unresolved_assignments_for_closed_routes
from scripts.process_stage_queue import claim_stage_tasks


class FakeResponse:
    def __init__(self, data=None):
        self.data = data or []


class FakeRPC:
    def __init__(self, client, name: str, params: dict):
        self.client = client
        self.name = name
        self.params = params

    def execute(self):
        self.client.rpc_calls.append((self.name, self.params))
        return FakeResponse(self.client.rpc_payload)


class FakeTable:
    def __init__(self, client, name: str):
        self.client = client
        self.name = name
        self.action = None
        self.payload = None
        self.on_conflict = None
        self.filters: list[tuple[str, object]] = []
        self.range_start = None
        self.range_end = None

    def select(self, _columns: str):
        self.action = "select"
        return self

    def eq(self, field: str, value: object):
        self.filters.append((field, value))
        return self

    def limit(self, count: int):
        self.range_start = 0
        self.range_end = count - 1
        return self

    def range(self, start: int, end: int):
        self.range_start = start
        self.range_end = end
        return self

    def update(self, payload: dict):
        self.action = "update"
        self.payload = payload
        return self

    def upsert(self, payload: dict, on_conflict: str | None = None):
        self.action = "upsert"
        self.payload = payload
        self.on_conflict = on_conflict
        return self

    def execute(self):
        rows = [row for row in self.client.tables.get(self.name, []) if self._matches(row)]
        if self.action == "select":
            if self.range_start is not None and self.range_end is not None:
                rows = rows[self.range_start:self.range_end + 1]
            return FakeResponse([dict(row) for row in rows])

        if self.action == "update":
            for row in rows:
                row.update(self.payload)
            self.client.updates.append((self.name, dict(self.payload), list(self.filters)))
            return FakeResponse([dict(row) for row in rows])

        if self.action == "upsert":
            key_fields = [field.strip() for field in (self.on_conflict or "").split(",") if field.strip()]
            payload = dict(self.payload)
            matched_row = None
            if key_fields:
                for row in self.client.tables.setdefault(self.name, []):
                    if all(row.get(field) == payload.get(field) for field in key_fields):
                        matched_row = row
                        break
            if matched_row is None:
                self.client.tables.setdefault(self.name, []).append(payload)
            else:
                matched_row.update(payload)
            self.client.upserts.append((self.name, payload, self.on_conflict))
            return FakeResponse([payload])

        raise AssertionError(f"Unsupported action {self.action!r} on {self.name}")

    def _matches(self, row: dict) -> bool:
        return all(row.get(field) == value for field, value in self.filters)


class FakeSupabaseClient:
    def __init__(self, tables: dict[str, list[dict]] | None = None, rpc_payload=None):
        self.tables = {name: [dict(row) for row in rows] for name, rows in (tables or {}).items()}
        self.updates: list[tuple[str, dict, list[tuple[str, object]]]] = []
        self.upserts: list[tuple[str, dict, str | None]] = []
        self.rpc_calls: list[tuple[str, dict]] = []
        self.rpc_payload = rpc_payload or []

    def table(self, name: str) -> FakeTable:
        return FakeTable(self, name)

    def rpc(self, name: str, params: dict) -> FakeRPC:
        return FakeRPC(self, name, params)


class RoutingLogicTests(unittest.TestCase):
    def test_bucket_classification_uses_separate_positive_and_negative_thresholds(self) -> None:
        self.assertEqual(
            classify_routing_bucket(
                is_useful=True,
                overall_confidence=0.92,
                positive_threshold=0.9,
                negative_threshold=0.2,
            ),
            ROUTING_BUCKET_HIGH_POSITIVE,
        )
        self.assertEqual(
            classify_routing_bucket(
                is_useful=True,
                overall_confidence=0.89,
                positive_threshold=0.9,
                negative_threshold=0.2,
            ),
            ROUTING_BUCKET_LOW_POSITIVE,
        )
        self.assertEqual(
            classify_routing_bucket(
                is_useful=False,
                overall_confidence=0.91,
                positive_threshold=0.99,
                negative_threshold=0.9,
            ),
            ROUTING_BUCKET_HIGH_NEGATIVE,
        )
        self.assertEqual(
            classify_routing_bucket(
                is_useful=False,
                overall_confidence=0.89,
                positive_threshold=0.99,
                negative_threshold=0.9,
            ),
            ROUTING_BUCKET_LOW_NEGATIVE,
        )

    def test_audit_sampling_is_deterministic(self) -> None:
        baseline = stable_audit_sample(
            paper_id=42,
            stage_key="gemini_flash_triage_v1",
            model_name="gemini-3-flash-preview",
            audit_rate=0.05,
        )
        repeated = stable_audit_sample(
            paper_id=42,
            stage_key="gemini_flash_triage_v1",
            model_name="gemini-3-flash-preview",
            audit_rate=0.05,
        )
        self.assertEqual(baseline, repeated)
        self.assertFalse(
            stable_audit_sample(
                paper_id=42,
                stage_key="gemini_flash_triage_v1",
                model_name="gemini-3-flash-preview",
                audit_rate=0.0,
            )
        )
        self.assertTrue(
            stable_audit_sample(
                paper_id=42,
                stage_key="gemini_flash_triage_v1",
                model_name="gemini-3-flash-preview",
                audit_rate=1.0,
            )
        )
        sampled = sum(
            stable_audit_sample(
                paper_id=paper_id,
                stage_key="gemini_flash_triage_v1",
                model_name="gemini-3-flash-preview",
                audit_rate=0.05,
            )
            for paper_id in range(1, 1001)
        )
        self.assertGreater(sampled, 20)
        self.assertLess(sampled, 80)

    def test_normalize_ai_payload_matches_human_shape(self) -> None:
        payload = normalize_ai_payload(
            is_useful=True,
            records=[
                {
                    "food_name": "Apple, raw",
                    "nutrient_name": "Protein",
                    "amount": 0.3,
                    "unit": "g",
                    "basis": "100g",
                    "preparation_state": "raw",
                },
                {
                    "food_name": "Apple, raw",
                    "nutrient_name": "Vitamin C",
                    "amount": 4.6,
                    "unit": "mg",
                    "basis": "100g",
                    "preparation_state": "raw",
                },
            ],
        )
        self.assertEqual(payload["decision_kind"], "has_data")
        self.assertEqual(len(payload["food_items"]), 1)
        food_item = payload["food_items"][0]
        self.assertEqual(food_item["food_name"], "Apple, raw")
        self.assertIsNone(food_item["food_fdc_id"])
        self.assertTrue(food_item["is_custom_food"])
        self.assertEqual(
            food_item["nutrients"],
            [
                {"nutrient_id": None, "nutrient_name": "Protein", "unit": "g", "value": 0.3},
                {"nutrient_id": None, "nutrient_name": "Vitamin C", "unit": "mg", "value": 4.6},
            ],
        )


class StockAndFeedbackTests(unittest.TestCase):
    @patch("scripts.ensure_paper_stock.fetch_rows")
    def test_fetch_available_counts_only_counts_human_review_ready(self, fetch_rows_mock: Mock) -> None:
        fetch_rows_mock.side_effect = [
            [
                {"id": 1, "workflow_language": "en", "routing_status": "human_review_ready"},
                {"id": 2, "workflow_language": "tr", "routing_status": "queued_for_ai"},
                {"id": 3, "workflow_language": "tr", "routing_status": "human_review_ready"},
            ],
            [],
            [],
            [{"paper_id": 3, "status": "pending"}],
        ]

        counts = ensure_paper_stock.fetch_available_counts("https://example.supabase.co", "service-role")
        self.assertEqual(counts["en"], 1)
        self.assertEqual(counts["tr"], 0)
        self.assertEqual(counts["total"], 1)

    def test_available_papers_excludes_non_human_ready(self) -> None:
        papers = [
            {"id": 1, "workflow_language": "en", "routing_status": "human_review_ready"},
            {"id": 2, "workflow_language": "tr", "routing_status": "queued_for_ai"},
            {"id": 3, "workflow_language": "en", "routing_status": "ai_failed"},
        ]
        available = refill_assignment_queue.available_papers(
            papers,
            slot_assignments=[],
            review_outcomes=[],
            global_labels=[],
        )
        self.assertEqual([paper["id"] for paper in available], [1])

    def test_build_labels_excludes_ai_model_outcomes(self) -> None:
        good_ids, bad_ids, conflict_ids = build_labels(
            review_outcomes=[
                {"paper_id": 1, "decision_kind": "has_data", "truth_source_kind": "ai_model"},
                {"paper_id": 2, "decision_kind": "no_usable_data", "truth_source_kind": "human_review"},
            ],
            open_conflicts=[],
            label_events=[],
            global_labels=[],
        )
        self.assertEqual(good_ids, set())
        self.assertEqual(bad_ids, {2})
        self.assertEqual(conflict_ids, set())


class QueueAndBackfillTests(unittest.TestCase):
    def test_enqueue_stage_task_requeues_failed_tasks(self) -> None:
        stage = RoutingStageConfig(
            stage_key="gemini_flash_triage_v1",
            stage_kind="ai_model",
            display_name="Gemini Flash Triage v1",
            model_name="gemini-3-flash-preview",
            prompt_version="gemini_flash_triage_v1",
            active=True,
            positive_threshold=1.0,
            negative_threshold=1.0,
            audit_rate=0.05,
            next_stage_on_low_confidence=HUMAN_REVIEW_DESTINATION,
            counts_as_truth=False,
        )
        client = FakeSupabaseClient(
            tables={
                "paper_stage_tasks": [
                    {"paper_id": 11, "stage_key": "gemini_flash_triage_v1", "status": "failed"},
                ],
                "papers": [{"id": 11, "routing_status": None}],
            }
        )

        upload_to_supabase._enqueue_stage_task(
            client,
            paper_id=11,
            stage_config=stage,
            filter_score=0.8,
            preserve_human_route=False,
        )

        self.assertEqual(len(client.upserts), 1)
        self.assertEqual(client.upserts[0][0], "paper_stage_tasks")
        self.assertEqual(client.upserts[0][1]["status"], "queued")
        self.assertEqual(client.updates[-1][0], "papers")
        self.assertEqual(client.updates[-1][1]["routing_status"], "queued_for_ai")

    def test_claim_stage_tasks_calls_rpc_with_requested_limit(self) -> None:
        client = FakeSupabaseClient(rpc_payload=[{"id": "task-1", "paper_id": 11}])
        claimed = claim_stage_tasks(client, stage_key="gemini_flash_triage_v1", limit=3)
        self.assertEqual(claimed, [{"id": "task-1", "paper_id": 11}])
        self.assertEqual(
            client.rpc_calls,
            [("claim_paper_stage_tasks", {"p_stage_key": "gemini_flash_triage_v1", "p_limit": 3})],
        )

    def test_backfill_cancels_only_non_human_ready_final_routes(self) -> None:
        client = FakeSupabaseClient(
            tables={
                "papers": [
                    {"id": 1, "routing_status": "ai_finalized_has_data"},
                    {"id": 2, "routing_status": "human_review_ready"},
                    {"id": 3, "routing_status": "ai_failed"},
                ],
                "paper_slot_assignments": [
                    {"id": "slot-1", "paper_id": 1, "status": "pending"},
                    {"id": "slot-2", "paper_id": 2, "status": "pending"},
                    {"id": "slot-3", "paper_id": 3, "status": "submitted"},
                ],
                "paper_user_assignments": [
                    {"id": "user-1", "paper_id": 1, "status": "assigned"},
                    {"id": "user-2", "paper_id": 2, "status": "draft"},
                    {"id": "user-3", "paper_id": 3, "status": "conflict"},
                ],
                "paper_conflicts": [
                    {"id": "conflict-1", "paper_id": 1, "status": "open"},
                    {"id": "conflict-2", "paper_id": 2, "status": "open"},
                    {"id": "conflict-3", "paper_id": 3, "status": "open"},
                ],
            }
        )

        cancelled = cancel_unresolved_assignments_for_closed_routes(client)

        self.assertEqual(cancelled["slot_assignments"], 2)
        self.assertEqual(cancelled["user_assignments"], 2)
        self.assertEqual(cancelled["conflicts"], 2)
        self.assertEqual(client.tables["paper_slot_assignments"][0]["status"], "cancelled")
        self.assertEqual(client.tables["paper_slot_assignments"][1]["status"], "pending")
        self.assertEqual(client.tables["paper_slot_assignments"][2]["status"], "cancelled")
        self.assertEqual(client.tables["paper_user_assignments"][0]["status"], "cancelled")
        self.assertEqual(client.tables["paper_user_assignments"][1]["status"], "draft")
        self.assertEqual(client.tables["paper_user_assignments"][2]["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
