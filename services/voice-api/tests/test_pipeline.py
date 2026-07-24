from __future__ import annotations

import pytest

from opennutri_voice.core_repository import CoreFoodRepository
from opennutri_voice.models import (
    ExtractedConcept,
    ExtractedQuantity,
    SelectorDecision,
)
from opennutri_voice.pipeline import ResolverPipeline


class StubStore:
    async def semantic_search(self, *, embedding, limit):
        return [
            {"food_id": "food-rice", "similarity": 0.9},
            {"food_id": "food-apple", "similarity": 0.8},
        ]


class StubGemini:
    pass


@pytest.fixture
def pipeline(settings):
    return ResolverPipeline(
        settings=settings,
        core=CoreFoodRepository(settings.core_database_path),
        store=StubStore(),
        gemini=StubGemini(),
    )


@pytest.mark.asyncio
async def test_retrieval_fusion_is_deterministic_and_bounded(pipeline):
    first = await pipeline._retrieve("apple", [0.0] * 768)
    second = await pipeline._retrieve("apple", [0.0] * 768)

    assert first == second
    assert len(first) <= 12
    assert first[0]["food_id"] == "food-apple"
    assert set(first[0]["matched_channels"]) == {"primary", "semantic"}


def test_quantity_requires_grams_or_one_source_backed_portion(pipeline):
    concept = ExtractedConcept(
        source_phrase="two cups rice",
        food_name="rice",
        quantity=ExtractedQuantity(value=2, unit="cups"),
        preparation=["cooked"],
    )
    selected = pipeline.core.hydrate_candidates(["food-rice"])["food-rice"]
    result = pipeline._resolve_quantity(concept, selected)
    assert result.status == "resolved"
    assert result.grams == 316
    assert result.source_portion_id == "portion-cup"

    concept.quantity = ExtractedQuantity(value=2, unit="bowls")
    unresolved = pipeline._resolve_quantity(concept, selected)
    assert unresolved.status == "unresolved"
    assert unresolved.grams is None


def test_candidate_ids_outside_retrieval_set_are_rejected(pipeline):
    candidates = list(pipeline.core.hydrate_candidates(["food-apple"]).values())
    item = pipeline._build_item(
        concept_index=0,
        concept=ExtractedConcept(
            source_phrase="apple",
            food_name="apple",
            quantity=ExtractedQuantity(value=100, unit="g"),
        ),
        candidates=candidates,
        decision=SelectorDecision(
            concept_index=0,
            selected_food_id="invented-food",
            alternative_food_ids=["food-apple", "also-invented"],
            confidence=0.99,
        ),
        meal_default="lunch",
    )
    assert item.selected_candidate is None
    assert "food" in item.unresolved_fields
    assert [candidate.food_id for candidate in item.alternatives] == ["food-apple"]


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        ("2026-07-24T04:00:00", "breakfast"),
        ("2026-07-24T10:59:00", "breakfast"),
        ("2026-07-24T11:00:00", "lunch"),
        ("2026-07-24T15:59:00", "lunch"),
        ("2026-07-24T16:00:00", "dinner"),
        ("2026-07-24T21:59:00", "dinner"),
        ("2026-07-24T22:00:00", "snacks"),
        ("2026-07-24T03:59:00", "snacks"),
    ],
)
def test_meal_boundaries(timestamp, expected):
    assert ResolverPipeline.meal_for(timestamp, "Europe/Istanbul") == expected
