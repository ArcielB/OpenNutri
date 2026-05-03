from __future__ import annotations

import json
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
    normalize_ai_payload_with_summary,
    stable_audit_sample,
)
from food_paper_crawler.feedback.update_terms import build_labels
from scripts import ensure_paper_stock, refill_assignment_queue, upload_to_supabase
from scripts.backfill_ai_routing import (
    cancel_unresolved_assignments_for_closed_routes,
    reset_open_human_assignments_for_ai,
)
from scripts.process_stage_queue import (
    claim_stage_tasks,
    drain_stage_queue,
    is_quota_error,
    process_one_task,
    select_food_candidates_for_text,
)
from evaluator.unified_evaluator import UnifiedEvaluator


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

    def insert(self, payload: dict | list[dict]):
        self.action = "insert"
        self.payload = payload
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

        if self.action == "insert":
            payload_rows = self.payload if isinstance(self.payload, list) else [self.payload]
            inserted = [dict(row) for row in payload_rows]
            self.client.tables.setdefault(self.name, []).extend(inserted)
            self.client.inserts.append((self.name, inserted))
            return FakeResponse(inserted)

        raise AssertionError(f"Unsupported action {self.action!r} on {self.name}")

    def _matches(self, row: dict) -> bool:
        return all(row.get(field) == value for field, value in self.filters)


class FakeSupabaseClient:
    def __init__(self, tables: dict[str, list[dict]] | None = None, rpc_payload=None):
        self.tables = {name: [dict(row) for row in rows] for name, rows in (tables or {}).items()}
        self.updates: list[tuple[str, dict, list[tuple[str, object]]]] = []
        self.upserts: list[tuple[str, dict, str | None]] = []
        self.inserts: list[tuple[str, list[dict]]] = []
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

    def test_threshold_one_disables_ai_auto_finalization(self) -> None:
        self.assertEqual(
            classify_routing_bucket(
                is_useful=True,
                overall_confidence=1.0,
                positive_threshold=1.0,
                negative_threshold=1.0,
            ),
            ROUTING_BUCKET_LOW_POSITIVE,
        )
        self.assertEqual(
            classify_routing_bucket(
                is_useful=False,
                overall_confidence=1.0,
                positive_threshold=1.0,
                negative_threshold=1.0,
            ),
            ROUTING_BUCKET_LOW_NEGATIVE,
        )
        self.assertEqual(
            classify_routing_bucket(
                is_useful=False,
                overall_confidence=1.0,
                positive_threshold=0.99,
                negative_threshold=0.99,
            ),
            ROUTING_BUCKET_HIGH_NEGATIVE,
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
            [
                (row["nutrient_id"], row["is_custom_nutrient"], row["nutrient_name"], row["unit"], row["basis"], row["value"])
                for row in food_item["nutrients"]
            ],
            [
                (None, True, "Protein", "g/100g", "per_100g", 0.3),
                (None, True, "Vitamin C", "mg/100g", "per_100g", 4.6),
            ],
        )

    def test_normalize_ai_payload_standardizes_supported_units_and_drops_unsupported_rows(self) -> None:
        result = normalize_ai_payload_with_summary(
            is_useful=True,
            records=[
                {"food_name": "Apple", "nutrient_name": "Iron", "amount": 1, "unit": "mg", "basis": "100g"},
                {"food_name": "Apple", "nutrient_name": "Folate", "amount": 2, "unit": "mcg", "basis": "100 g"},
                {"food_name": "Apple", "nutrient_name": "Vitamin B12", "amount": 3, "unit": "µg", "basis": "per 100g"},
                {"food_name": "Apple", "nutrient_name": "Energy", "amount": 52, "unit": "kcal", "basis": "100g"},
                {"food_name": "Apple", "nutrient_name": "Moisture", "amount": 84.1, "unit": "%", "basis": "100g"},
                {"food_name": "Apple", "nutrient_name": "pH", "amount": 3.5, "unit": "pH", "basis": "100g"},
                {"food_name": "Apple", "nutrient_name": "Iron per serving", "amount": 1, "unit": "mg", "basis": "serving"},
            ],
        )

        nutrients = result.payload["food_items"][0]["nutrients"]
        self.assertEqual(
            [row["unit"] for row in nutrients],
            ["kcal/100g", "μg/100g", "mg/100g", "%", "μg/100g"],
        )
        self.assertEqual(result.accepted_row_count, 5)
        self.assertEqual(result.rejected_row_count, 2)
        self.assertEqual(result.rejection_reasons, {"unsupported_unit_or_basis": 2})

    def test_normalize_ai_payload_turns_empty_standardized_rows_into_no_usable_data(self) -> None:
        payload = normalize_ai_payload(
            is_useful=True,
            records=[
                {"food_name": "Apple", "nutrient_name": "Color", "amount": 12, "unit": "a*", "basis": "100g"},
                {"food_name": "Apple", "nutrient_name": "Iron", "amount": 1, "unit": "mg", "basis": "per serving"},
            ],
        )

        self.assertEqual(payload, {"decision_kind": "no_usable_data", "food_items": []})

    def test_normalize_ai_payload_orders_and_rounds_like_submission_contract(self) -> None:
        payload = normalize_ai_payload(
            is_useful=True,
            records=[
                {"food_name": "Banana", "nutrient_name": "Zinc", "amount": 1.23456789, "unit": "mg", "basis": "100g"},
                {"food_name": "Apple, raw", "nutrient_name": "Vitamin C", "amount": 4.6000001, "unit": "mg", "basis": "100g"},
                {"food_name": "Apple, raw", "nutrient_name": "Protein", "amount": 0.3000004, "unit": "g", "basis": "100g"},
                {"food_name": "Apple, raw", "nutrient_name": "Ascorbic acid", "amount": 5, "unit": "mg", "basis": "100g"},
            ],
            food_lookup=[
                {"id": "food-apple", "canonical_name": "Apple, raw"},
            ],
            nutrient_lookup=[
                {"id": "nutrient-protein", "standard_name": "Protein"},
                {"id": "nutrient-vitc", "standard_name": "Vitamin C", "aliases": ["Ascorbic acid"]},
            ],
        )

        self.assertEqual([item["food_name"] for item in payload["food_items"]], ["Apple, raw", "Banana"])
        apple = payload["food_items"][0]
        self.assertFalse(apple["is_custom_food"])
        self.assertEqual(apple["food_fdc_id"], "food-apple")
        self.assertEqual(
            [
                (row["nutrient_id"], row["is_custom_nutrient"], row["nutrient_name"], row["unit"], row["basis"], row["value"])
                for row in apple["nutrients"]
            ],
            [
                ("nutrient-protein", False, "Protein", "g/100g", "per_100g", 0.3),
                ("nutrient-vitc", False, "Vitamin C", "mg/100g", "per_100g", 5.0),
                ("nutrient-vitc", False, "Vitamin C", "mg/100g", "per_100g", 4.6),
            ],
        )
        self.assertEqual(
            [
                (row["nutrient_id"], row["is_custom_nutrient"], row["nutrient_name"], row["unit"], row["basis"], row["value"])
                for row in payload["food_items"][1]["nutrients"]
            ],
            [(None, True, "Zinc", "mg/100g", "per_100g", 1.234568)],
        )

    def test_normalize_ai_payload_accepts_exact_db_ids_when_names_match(self) -> None:
        payload = normalize_ai_payload(
            is_useful=True,
            records=[
                {
                    "food_name": "Apple, raw",
                    "food_fdc_id": "food-apple",
                    "nutrient_name": "Protein",
                    "nutrient_id": "nutrient-protein",
                    "amount": 0.31,
                    "unit": "g",
                    "basis": "100g",
                    "source_citation": "Table 1",
                    "confidence": 0.9,
                }
            ],
            food_lookup=[
                {"id": "food-apple", "canonical_name": "Apple, raw"},
            ],
            nutrient_lookup=[
                {"id": "nutrient-protein", "standard_name": "Protein"},
            ],
        )

        food_item = payload["food_items"][0]
        nutrient = food_item["nutrients"][0]
        self.assertEqual(payload["decision_kind"], "has_data")
        self.assertEqual(food_item["food_name"], "Apple, raw")
        self.assertEqual(food_item["food_fdc_id"], "food-apple")
        self.assertFalse(food_item["is_custom_food"])
        self.assertEqual(food_item["raw_food_name"], "Apple, raw")
        self.assertEqual(nutrient["nutrient_id"], "nutrient-protein")
        self.assertFalse(nutrient["is_custom_nutrient"])
        self.assertEqual(nutrient["nutrient_name"], "Protein")
        self.assertEqual(nutrient["raw_nutrient_name"], "Protein")
        self.assertEqual(nutrient["value"], 0.31)
        self.assertEqual(nutrient["unit"], "g/100g")
        self.assertEqual(nutrient["basis"], "per_100g")

    def test_normalize_ai_payload_rejects_stale_or_mismatched_db_ids(self) -> None:
        payload = normalize_ai_payload(
            is_useful=True,
            records=[
                {
                    "food_name": "Apple, raw",
                    "food_fdc_id": "stale-food-id",
                    "nutrient_name": "Protein",
                    "nutrient_id": "nutrient-iron",
                    "amount": 0.31,
                    "unit": "g",
                    "basis": "100g",
                }
            ],
            food_lookup=[
                {"id": "food-apple", "canonical_name": "Apple, raw"},
            ],
            nutrient_lookup=[
                {"id": "nutrient-protein", "standard_name": "Protein"},
                {"id": "nutrient-iron", "standard_name": "Iron"},
            ],
        )

        food_item = payload["food_items"][0]
        self.assertEqual(food_item["food_fdc_id"], "food-apple")
        self.assertFalse(food_item["is_custom_food"])
        self.assertEqual(food_item["nutrients"][0]["nutrient_id"], "nutrient-protein")
        self.assertEqual(food_item["nutrients"][0]["nutrient_name"], "Protein")

    def test_normalize_ai_payload_preserves_custom_foods_and_nutrients_without_matches(self) -> None:
        payload = normalize_ai_payload(
            is_useful=True,
            records=[
                {
                    "food_name": "Village apricot paste",
                    "nutrient_name": "Total phenolic compounds",
                    "amount": 18.2,
                    "unit": "mg",
                    "basis": "100g",
                }
            ],
            food_lookup=[
                {"id": "food-apple", "canonical_name": "Apple, raw"},
            ],
            nutrient_lookup=[
                {"id": "nutrient-protein", "standard_name": "Protein"},
            ],
        )

        food_item = payload["food_items"][0]
        self.assertEqual(food_item["food_name"], "Village apricot paste")
        self.assertIsNone(food_item["food_fdc_id"])
        self.assertTrue(food_item["is_custom_food"])
        self.assertEqual(food_item["nutrients"][0]["nutrient_id"], None)
        self.assertEqual(food_item["nutrients"][0]["nutrient_name"], "Total phenolic compounds")

    def test_select_food_candidates_for_text_uses_aliases_without_full_catalog(self) -> None:
        candidates = select_food_candidates_for_text(
            "The table reports Fuji apple and dried pear composition values.",
            [
                {"id": "food-apple", "canonical_name": "Apple, raw", "alias_names": ["Fuji apple"]},
                {"id": "food-bread", "canonical_name": "Bread"},
                {"id": "food-pear", "canonical_name": "Pear, dried", "alias_names": ["dried pear"]},
            ],
            limit=5,
        )

        self.assertEqual([row["id"] for row in candidates], ["food-apple", "food-pear"])

    def test_normalized_payload_preserves_raw_metadata_in_canonical_contract(self) -> None:
        payload = normalize_ai_payload(
            is_useful=True,
            records=[
                {
                    "food_name": "Apple, raw",
                    "raw_food_name": "Fuji apple",
                    "nutrient_name": "Protein",
                    "raw_nutrient_name": "crude protein",
                    "amount": 0.31,
                    "unit": "g",
                    "basis": "100g",
                    "source_citation": "Table 1, row 2",
                    "confidence": 0.9,
                }
            ],
        )

        food_item = payload["food_items"][0]
        nutrient = food_item["nutrients"][0]
        self.assertEqual(food_item["raw_food_name"], "Fuji apple")
        self.assertEqual(nutrient["raw_nutrient_name"], "crude protein")
        self.assertEqual(nutrient["source_citation"], "Table 1, row 2")
        self.assertEqual(nutrient["confidence"], 0.9)


class StockAndFeedbackTests(unittest.TestCase):
    @patch("scripts.ensure_paper_stock.fetch_rows")
    def test_fetch_available_counts_only_counts_human_review_ready(self, fetch_rows_mock: Mock) -> None:
        fetch_rows_mock.side_effect = [
            [
                {"id": 1, "workflow_language": "en", "routing_status": "human_review_ready", "latest_ai_extraction_id": "ai-1"},
                {"id": 2, "workflow_language": "tr", "routing_status": "queued_for_ai"},
                {"id": 3, "workflow_language": "tr", "routing_status": "human_review_ready", "latest_ai_extraction_id": "ai-3"},
                {"id": 4, "workflow_language": "en", "routing_status": "human_review_ready", "latest_ai_extraction_id": "ai-4"},
            ],
            [],
            [],
            [{"paper_id": 4, "status": "pending_approval"}],
            [{"paper_id": 3, "status": "pending"}],
        ]

        counts = ensure_paper_stock.fetch_available_counts("https://example.supabase.co", "service-role")
        self.assertEqual(counts["en"], 1)
        self.assertEqual(counts["tr"], 0)
        self.assertEqual(counts["total"], 1)

    def test_available_papers_excludes_non_human_ready(self) -> None:
        papers = [
            {"id": 1, "workflow_language": "en", "routing_status": "human_review_ready", "latest_ai_extraction_id": "ai-1"},
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

    def test_available_papers_sorts_oldest_human_ready_waiting_first(self) -> None:
        papers = [
            {
                "id": 1,
                "workflow_language": "en",
                "routing_status": "human_review_ready",
                "latest_ai_extraction_id": "ai-1",
                "created_at": "2026-04-01T00:00:00+00:00",
                "routing_updated_at": "2026-04-20T00:00:00+00:00",
            },
            {
                "id": 2,
                "workflow_language": "tr",
                "routing_status": "human_review_ready",
                "latest_ai_extraction_id": "ai-2",
                "created_at": "2026-04-02T00:00:00+00:00",
                "routing_updated_at": "2026-04-10T00:00:00+00:00",
            },
            {
                "id": 3,
                "workflow_language": "en",
                "routing_status": "human_review_ready",
                "latest_ai_extraction_id": "ai-3",
                "created_at": "2026-04-03T00:00:00+00:00",
                "routing_updated_at": "2026-04-10T00:00:00+00:00",
            },
        ]

        available = refill_assignment_queue.available_papers(
            papers,
            slot_assignments=[],
            review_outcomes=[],
            global_labels=[],
        )

        self.assertEqual([paper["id"] for paper in available], [2, 3, 1])

    def test_available_papers_excludes_pending_general_submissions(self) -> None:
        papers = [
            {"id": 1, "workflow_language": "en", "routing_status": "human_review_ready", "latest_ai_extraction_id": "ai-1"},
            {"id": 2, "workflow_language": "tr", "routing_status": "human_review_ready", "latest_ai_extraction_id": "ai-2"},
            {"id": 3, "workflow_language": "en", "routing_status": "human_review_ready", "latest_ai_extraction_id": "ai-3"},
        ]
        available = refill_assignment_queue.available_papers(
            papers,
            slot_assignments=[],
            review_outcomes=[],
            global_labels=[],
            label_submissions=[
                {"paper_id": 1, "status": "pending_approval"},
                {"paper_id": 2, "status": "superseded"},
            ],
        )
        self.assertEqual([paper["id"] for paper in available], [2, 3])

    def test_general_queue_stock_does_not_create_reviewer_assignments(self) -> None:
        client = FakeSupabaseClient(
            tables={
                "papers": [
                    {
                        "id": 101,
                        "title": "Paper",
                        "doi": None,
                        "filename": "paper.pdf",
                        "workflow_language": "en",
                        "created_at": "2026-04-01T00:00:00+00:00",
                        "routing_updated_at": "2026-04-01T00:00:00+00:00",
                        "routing_status": "human_review_ready",
                        "latest_ai_extraction_id": "ai-101",
                    }
                ],
                "paper_global_labels": [],
                "paper_review_outcomes": [],
                "paper_label_submissions": [],
                "paper_slot_assignments": [],
                "reviewer_profiles": [
                    {
                        "id": "profile-arciel",
                        "email": "baezarciel@gmail.com",
                        "auth_user_id": "auth-arciel",
                        "display_name": "Arciel",
                        "active": True,
                        "can_review_en": True,
                        "can_review_tr": True,
                        "tester_access": False,
                        "official_slot": "arciel",
                        "can_approve_labels": True,
                    },
                ],
            }
        )

        summary = refill_assignment_queue.assign_ready_papers(
            client,
            target_open=1,
            seed=20260413,
            dry_run=False,
            verbose=False,
        )

        self.assertEqual(client.inserts, [])
        self.assertTrue(summary["satisfied"])
        self.assertEqual(summary["planned_slot_assignments"], 0)
        self.assertEqual(summary["planned_user_assignments"], 0)
        self.assertEqual(summary["planned_general_queue_papers"], 1)

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


class UnifiedEvaluatorParsingTests(unittest.TestCase):
    def evaluator_with_response(self, payload: object) -> UnifiedEvaluator:
        evaluator = UnifiedEvaluator.__new__(UnifiedEvaluator)
        evaluator.model = Mock()
        evaluator.model.generate_content.return_value = Mock(text=json.dumps(payload))
        return evaluator

    def test_top_level_array_response_is_treated_as_candidate_rows(self) -> None:
        evaluator = self.evaluator_with_response(
            [
                {
                    "food_name": "Apple",
                    "nutrient_name": "Vitamin C",
                    "amount": 4.6,
                    "unit": "mg",
                    "basis": "100g",
                    "confidence": 0.8,
                    "source_citation": "Table 1",
                }
            ]
        )

        result = evaluator.evaluate_and_extract({"pmc_id": "paper-1", "title": "Paper", "full_text": "body"})

        self.assertTrue(result.is_useful)
        self.assertEqual(result.overall_confidence, 0.8)
        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0].food_name, "Apple")
        self.assertEqual(result.data[0].nutrient_name, "Vitamin C")

    def test_nested_food_nutrient_response_is_flattened(self) -> None:
        evaluator = self.evaluator_with_response(
            {
                "reasoning": "Table contains composition rows.",
                "is_useful": True,
                "overall_confidence": 0.9,
                "data": [
                    {
                        "food_name": "Pear",
                        "basis": "100g",
                        "source_citation": "Table 2",
                        "nutrients": [
                            {"nutrient_name": "Protein", "amount": 0.4, "unit": "g", "confidence": 0.7}
                        ],
                    }
                ],
            }
        )

        result = evaluator.evaluate_and_extract({"pmc_id": "paper-2", "title": "Paper", "full_text": "body"})

        self.assertTrue(result.is_useful)
        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0].food_name, "Pear")
        self.assertEqual(result.data[0].basis, "100g")
        self.assertEqual(result.data[0].source_citation, "Table 2")

    def test_db_ids_and_raw_names_are_preserved_on_records(self) -> None:
        evaluator = self.evaluator_with_response(
            {
                "reasoning": "Table contains composition rows.",
                "is_useful": True,
                "overall_confidence": 0.9,
                "data": [
                    {
                        "food_name": "Apple, raw",
                        "food_fdc_id": "food-apple",
                        "raw_food_name": "Fuji apple",
                        "nutrient_name": "Vitamin C",
                        "nutrient_id": "nutrient-vitc",
                        "raw_nutrient_name": "Ascorbic acid",
                        "amount": 4.6,
                        "unit": "mg",
                        "basis": "100g",
                        "confidence": 0.8,
                        "source_citation": "Table 1",
                    }
                ],
            }
        )

        result = evaluator.evaluate_and_extract({"pmc_id": "paper-3", "title": "Paper", "full_text": "body"})

        self.assertEqual(result.data[0].food_fdc_id, "food-apple")
        self.assertEqual(result.data[0].raw_food_name, "Fuji apple")
        self.assertEqual(result.data[0].nutrient_id, "nutrient-vitc")
        self.assertEqual(result.data[0].raw_nutrient_name, "Ascorbic acid")


class QueueAndBackfillTests(unittest.TestCase):
    def stage_config(self) -> RoutingStageConfig:
        return RoutingStageConfig(
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

    def test_enqueue_stage_task_requeues_failed_tasks(self) -> None:
        stage = self.stage_config()
        client = FakeSupabaseClient(
            tables={
                "paper_stage_tasks": [
                    {"paper_id": 11, "stage_key": "gemini_flash_triage_v1", "status": "failed"},
                ],
                "papers": [{"id": 11, "routing_status": None, "latest_ai_extraction_id": "old-extraction"}],
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
        self.assertIsNone(client.updates[-1][1]["latest_ai_extraction_id"])

    def test_claim_stage_tasks_calls_rpc_with_requested_limit(self) -> None:
        client = FakeSupabaseClient(rpc_payload=[{"id": "task-1", "paper_id": 11}])
        claimed = claim_stage_tasks(client, stage_key="gemini_flash_triage_v1", limit=3)
        self.assertEqual(claimed, [{"id": "task-1", "paper_id": 11}])
        self.assertEqual(
            client.rpc_calls,
            [("claim_paper_stage_tasks", {"p_stage_key": "gemini_flash_triage_v1", "p_limit": 3})],
        )

    def test_is_quota_error_detects_gemini_quota_without_treating_generic_429_as_ai_limit(self) -> None:
        self.assertTrue(is_quota_error("Extraction error: 429 quota exceeded"))
        self.assertTrue(
            is_quota_error(
                "429 generate_content_free_tier_requests from generativelanguage.googleapis.com"
            )
        )
        self.assertFalse(is_quota_error("HTTP Error 429 while downloading https://example.org/paper.pdf"))

    @patch("scripts.process_stage_queue.process_one_task")
    @patch("scripts.process_stage_queue.claim_stage_tasks")
    @patch("scripts.process_stage_queue.fetch_reference_lookups", return_value={})
    @patch("scripts.process_stage_queue.UnifiedEvaluator")
    @patch("scripts.process_stage_queue.fetch_active_stage_config")
    def test_stop_on_quota_claims_one_task_at_a_time_and_stops(
        self,
        fetch_stage_mock: Mock,
        evaluator_mock: Mock,
        _reference_mock: Mock,
        claim_mock: Mock,
        process_mock: Mock,
    ) -> None:
        fetch_stage_mock.return_value = self.stage_config()
        evaluator_mock.return_value = Mock(model=object())
        claim_mock.side_effect = [
            [{"id": "task-1", "paper_id": 11, "created_at": "2026-04-24"}],
            [{"id": "task-2", "paper_id": 12, "created_at": "2026-04-24"}],
        ]
        process_mock.return_value = {
            "paper_id": 11,
            "status": "queued_for_ai",
            "route_destination": "blocked",
            "error": "Extraction error: 429 quota exceeded",
            "quota_limited": True,
        }

        summary = drain_stage_queue(
            FakeSupabaseClient(),
            max_tasks=10,
            stop_on_quota=True,
            verbose=False,
        )

        self.assertEqual(summary["processed"], 1)
        self.assertEqual(summary["claimed"], 1)
        self.assertEqual(summary["requeued"], 1)
        self.assertTrue(summary["quota_limited"])
        self.assertEqual(claim_mock.call_count, 1)

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

    def test_reset_cancels_unresolved_assignments_and_enqueues_existing_papers(self) -> None:
        client = FakeSupabaseClient(
            tables={
                "papers": [
                    {"id": 1, "filter_score": 0.76, "routing_status": "human_review_ready", "latest_ai_extraction_id": "old-1"},
                    {"id": 2, "filter_score": 0.21, "routing_status": None, "latest_ai_extraction_id": "old-2"},
                ],
                "paper_assignment_submissions": [],
                "paper_review_outcomes": [],
                "paper_slot_assignments": [
                    {"id": "slot-1", "paper_id": 1, "status": "pending"},
                    {"id": "slot-2", "paper_id": 2, "status": "resolved"},
                ],
                "paper_user_assignments": [
                    {"id": "user-1", "paper_id": 1, "status": "assigned"},
                    {"id": "user-2", "paper_id": 2, "status": "cancelled"},
                ],
                "paper_stage_tasks": [
                    {"paper_id": 2, "stage_key": "gemini_flash_triage_v1", "status": "completed"},
                ],
            }
        )

        result = reset_open_human_assignments_for_ai(client, stage_config=self.stage_config())

        self.assertEqual(result["enqueued"], 2)
        self.assertEqual(result["cancelled"], {"slot_assignments": 1, "user_assignments": 1})
        self.assertEqual(client.tables["paper_slot_assignments"][0]["status"], "cancelled")
        self.assertEqual(client.tables["paper_user_assignments"][0]["status"], "cancelled")
        self.assertEqual([paper["routing_status"] for paper in client.tables["papers"]], ["queued_for_ai", "queued_for_ai"])
        self.assertEqual([paper["route_destination"] for paper in client.tables["papers"]], ["blocked", "blocked"])
        self.assertEqual([paper["latest_ai_extraction_id"] for paper in client.tables["papers"]], [None, None])
        self.assertEqual([upsert[1]["status"] for upsert in client.upserts], ["queued", "queued"])

    def test_reset_refuses_to_discard_submitted_or_human_truth_work(self) -> None:
        client = FakeSupabaseClient(
            tables={
                "papers": [{"id": 1, "filter_score": 0.76, "routing_status": "human_review_ready"}],
                "paper_assignment_submissions": [{"paper_id": 1}],
                "paper_label_submissions": [{"paper_id": 3}],
                "paper_review_outcomes": [{"paper_id": 2, "truth_source_kind": "human_review"}],
                "paper_slot_assignments": [{"id": "slot-1", "paper_id": 1, "status": "pending"}],
                "paper_user_assignments": [{"id": "user-1", "paper_id": 1, "status": "assigned"}],
                "paper_stage_tasks": [],
            }
        )

        with self.assertRaisesRegex(RuntimeError, "Refusing to reset AI routing"):
            reset_open_human_assignments_for_ai(client, stage_config=self.stage_config())

        self.assertEqual(client.tables["paper_slot_assignments"][0]["status"], "pending")
        self.assertEqual(client.tables["paper_user_assignments"][0]["status"], "assigned")
        self.assertEqual(client.upserts, [])

    def test_ai_processing_errors_requeue_task_and_paper(self) -> None:
        client = FakeSupabaseClient(
            tables={
                "papers": [
                    {
                        "id": 9,
                        "title": "Missing file paper",
                        "doi": "10.123/example",
                        "filename": "",
                        "latest_ai_extraction_id": "old-extraction",
                    }
                ],
                "paper_review_outcomes": [],
                "paper_stage_tasks": [{"id": "task-9", "paper_id": 9, "status": "processing"}],
            }
        )

        result = process_one_task(
            client,
            task={"id": "task-9", "paper_id": 9},
            stage_config=self.stage_config(),
            evaluator=Mock(),
        )

        self.assertEqual(result["status"], "queued_for_ai")
        self.assertEqual(result["route_destination"], "blocked")
        self.assertIn("missing filename", result["error"])
        self.assertEqual(client.tables["paper_stage_tasks"][0]["status"], "queued")
        self.assertIn("missing filename", client.tables["paper_stage_tasks"][0]["last_error"])
        self.assertEqual(client.tables["papers"][0]["routing_status"], "queued_for_ai")
        self.assertEqual(client.tables["papers"][0]["route_destination"], "blocked")

    @patch("scripts.process_stage_queue.extract_pdf_text", return_value="paper text")
    def test_embedded_evaluator_errors_requeue_instead_of_routing_to_humans(self, _extract_mock: Mock) -> None:
        client = FakeSupabaseClient(
            tables={
                "papers": [
                    {
                        "id": 10,
                        "title": "Quota paper",
                        "doi": "10.123/quota",
                        "filename": "quota.pdf",
                        "latest_ai_extraction_id": None,
                    }
                ],
                "paper_review_outcomes": [],
                "paper_stage_tasks": [{"id": "task-10", "paper_id": 10, "status": "processing"}],
            }
        )
        evaluator = Mock()
        evaluator.evaluate_and_extract.return_value = Mock(
            is_useful=False,
            reasoning="Extraction error: 429 quota exceeded",
            overall_confidence=0.0,
            data=[],
            raw_response_text="",
        )

        result = process_one_task(
            client,
            task={"id": "task-10", "paper_id": 10},
            stage_config=self.stage_config(),
            evaluator=evaluator,
        )

        self.assertEqual(result["status"], "queued_for_ai")
        self.assertTrue(result["quota_limited"])
        self.assertEqual(client.tables["paper_stage_tasks"][0]["status"], "queued")
        self.assertIn("429 quota exceeded", client.tables["paper_stage_tasks"][0]["last_error"])
        self.assertEqual(client.tables["papers"][0]["routing_status"], "queued_for_ai")
        self.assertEqual(client.tables["papers"][0]["route_destination"], "blocked")
        self.assertEqual(client.inserts, [])

    @patch("scripts.process_stage_queue.extract_pdf_text", return_value="paper text")
    def test_ai_routing_uses_normalized_decision_not_raw_model_usefulness(self, _extract_mock: Mock) -> None:
        client = FakeSupabaseClient(
            tables={
                "papers": [
                    {
                        "id": 12,
                        "title": "Non-composition metrics paper",
                        "doi": "10.123/noncomposition",
                        "filename": "paper.pdf",
                        "latest_ai_extraction_id": None,
                    }
                ],
                "paper_review_outcomes": [],
                "paper_stage_tasks": [{"id": "task-12", "paper_id": 12, "status": "processing"}],
            }
        )
        stage = RoutingStageConfig(
            stage_key="gemini_flash_db_payload_v2",
            stage_kind="ai_model",
            display_name="Gemini Flash DB Payload v2",
            model_name="gemini-3-flash-preview",
            prompt_version="gemini_flash_db_payload_v2",
            active=True,
            positive_threshold=1.0,
            negative_threshold=0.99,
            audit_rate=0.0,
            next_stage_on_low_confidence=HUMAN_REVIEW_DESTINATION,
            counts_as_truth=False,
        )
        evaluator = Mock()
        evaluator.evaluate_and_extract.return_value = Mock(
            is_useful=True,
            reasoning="The paper reports table values, but they are not standardized composition rows.",
            overall_confidence=1.0,
            data=[
                {"food_name": "Apple", "nutrient_name": "pH", "amount": 3.4, "unit": "pH", "basis": "100g"},
                {"food_name": "Apple", "nutrient_name": "Iron", "amount": 1.2, "unit": "mg", "basis": "serving"},
            ],
            raw_response_text="{}",
        )

        result = process_one_task(
            client,
            task={"id": "task-12", "paper_id": 12},
            stage_config=stage,
            evaluator=evaluator,
        )

        self.assertEqual(result["status"], "ai_finalized_no_usable_data")
        extraction_payload = client.inserts[0][1][0]
        self.assertTrue(extraction_payload["is_useful"])
        self.assertEqual(extraction_payload["routing_bucket"], "high_confidence_no_usable_data")
        self.assertEqual(extraction_payload["normalized_payload_json"], {"decision_kind": "no_usable_data", "food_items": []})
        self.assertEqual(
            extraction_payload["raw_data"]["normalization_summary"]["rejection_reasons"],
            {"unsupported_unit_or_basis": 2},
        )
        self.assertEqual(client.upserts[0][0], "paper_review_outcomes")
        self.assertEqual(client.upserts[0][1]["decision_kind"], "no_usable_data")

    @patch("scripts.process_stage_queue.extract_pdf_text", return_value="paper text")
    def test_threshold_one_routes_no_usable_data_to_humans(self, _extract_mock: Mock) -> None:
        client = FakeSupabaseClient(
            tables={
                "papers": [
                    {
                        "id": 13,
                        "title": "Perfect confidence paper",
                        "doi": "10.123/perfect",
                        "filename": "paper.pdf",
                        "latest_ai_extraction_id": None,
                    }
                ],
                "paper_review_outcomes": [],
                "paper_stage_tasks": [{"id": "task-13", "paper_id": 13, "status": "processing"}],
            }
        )
        stage = RoutingStageConfig(
            stage_key="gemini_flash_db_payload_v2",
            stage_kind="ai_model",
            display_name="Gemini Flash DB Payload v2",
            model_name="gemini-3-flash-preview",
            prompt_version="gemini_flash_db_payload_v2",
            active=True,
            positive_threshold=1.0,
            negative_threshold=1.0,
            audit_rate=0.0,
            next_stage_on_low_confidence=HUMAN_REVIEW_DESTINATION,
            counts_as_truth=False,
        )
        evaluator = Mock()
        evaluator.evaluate_and_extract.return_value = Mock(
            is_useful=False,
            reasoning="No standardized food composition rows.",
            overall_confidence=1.0,
            data=[],
            raw_response_text="{}",
        )

        result = process_one_task(
            client,
            task={"id": "task-13", "paper_id": 13},
            stage_config=stage,
            evaluator=evaluator,
        )

        self.assertEqual(result["status"], "human_review_ready")
        extraction_payload = client.inserts[0][1][0]
        self.assertEqual(extraction_payload["routing_bucket"], "low_confidence_no_usable_data")
        self.assertFalse(extraction_payload["finalized_without_human"])
        self.assertEqual(extraction_payload["normalized_payload_json"], {"decision_kind": "no_usable_data", "food_items": []})
        self.assertEqual(client.upserts, [])


if __name__ == "__main__":
    unittest.main()
