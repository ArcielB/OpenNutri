from __future__ import annotations

import pytest

from opennutri_voice.core_repository import CoreFoodRepository
from opennutri_voice.models import (
    AudioExtraction,
    ExtractedConcept,
    ExtractedQuantity,
    SelectorDecision,
    SelectorOutput,
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


class FastPathGemini:
    async def embed_concepts(self, concepts):
        raise AssertionError("exact lexical matches must not request embeddings")

    async def select_candidates(self, *, concepts, candidate_sets):
        raise AssertionError("exact lexical matches must not invoke the selector")


class LexicalSelectorGemini:
    def __init__(self) -> None:
        self.selector_calls = 0

    async def embed_concepts(self, concepts):
        raise AssertionError("lexical candidates must not request embeddings")

    async def select_candidates(self, *, concepts, candidate_sets):
        self.selector_calls += 1
        return SelectorOutput(
            decisions=[
                SelectorDecision(
                    concept_index=0,
                    selected_food_id="food-apple",
                    confidence=0.9,
                )
            ]
        )


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


def test_plural_food_query_retrieves_singular_core_name(pipeline):
    rows = pipeline.core.primary_search("hard-boiled whole eggs", limit=10)
    assert rows[0]["food_id"] == "food-egg"


def test_counted_food_uses_only_one_unambiguous_source_item_portion(pipeline):
    concept = ExtractedConcept(
        source_phrase="ten hard-boiled whole eggs",
        food_name="hard-boiled whole egg",
        quantity=ExtractedQuantity(value=10, unit="egg"),
        preparation=["hard-boiled"],
    )
    selected = {
        "portions": [
            {
                "portion_id": "cup",
                "description": "1 cup, chopped",
                "gram_weight": 136,
                "amount": 1,
            },
            {
                "portion_id": "large",
                "description": "1 large",
                "gram_weight": 50,
                "amount": 1,
            },
        ]
    }
    resolved = pipeline._resolve_quantity(concept, selected)
    assert resolved.status == "resolved"
    assert resolved.grams == 500
    assert resolved.source_portion_id == "large"

    concept.quantity = ExtractedQuantity(value=2, unit="yumurta")
    concept.source_phrase = "iki katı pişmiş bütün yumurta"
    translated_unit = pipeline._resolve_quantity(concept, selected)
    assert translated_unit.status == "resolved"
    assert translated_unit.grams == 100

    selected["portions"].append(
        {
            "portion_id": "small",
            "description": "1 small",
            "gram_weight": 38,
            "amount": 1,
        }
    )
    ambiguous = pipeline._resolve_quantity(concept, selected)
    assert ambiguous.status == "unresolved"


def test_spoken_size_selects_one_source_portion(pipeline):
    concept = ExtractedConcept(
        source_phrase="one medium banana",
        food_name="medium banana",
        quantity=ExtractedQuantity(value=1, unit="banana"),
    )
    selected = {
        "portions": [
            {
                "portion_id": "small",
                "description": "1 small",
                "gram_weight": 101,
                "amount": 1,
            },
            {
                "portion_id": "medium",
                "description": "1 medium",
                "gram_weight": 118,
                "amount": 1,
            },
            {
                "portion_id": "large",
                "description": "1 large",
                "gram_weight": 136,
                "amount": 1,
            },
        ]
    }
    resolved = pipeline._resolve_quantity(concept, selected)
    assert resolved.status == "resolved"
    assert resolved.grams == 118
    assert resolved.source_portion_id == "medium"
    assert pipeline._food_search_query(concept) == "banana"

    generic_source = {
        "portions": [
            {
                "portion_id": "banana",
                "description": "1 banana",
                "gram_weight": 126,
                "amount": None,
            },
            {
                "portion_id": "slice",
                "description": "1 slice",
                "gram_weight": 6,
                "amount": None,
            },
            {
                "portion_id": "linear-inch",
                "description": "1 linear inch",
                "gram_weight": 15,
                "amount": None,
            },
            {
                "portion_id": "unspecified",
                "description": "Quantity not specified",
                "gram_weight": 126,
                "amount": None,
            },
        ]
    }
    generic = pipeline._resolve_quantity(concept, generic_source)
    assert generic.status == "resolved"
    assert generic.grams == 126
    assert generic.source_portion_id == "banana"


def test_specific_cooking_state_cannot_be_silently_generalized(pipeline):
    selected = {"name": "Egg, whole, cooked, hard-boiled"}
    generic = ExtractedConcept(
        source_phrase="cooked egg",
        food_name="cooked egg",
        preparation=["cooked"],
    )
    assert pipeline._needs_preparation_confirmation(generic, selected) is True

    explicit = ExtractedConcept(
        source_phrase="hard-boiled egg",
        food_name="hard-boiled egg",
        preparation=["hard-boiled"],
    )
    assert pipeline._needs_preparation_confirmation(explicit, selected) is False


def test_auto_log_requires_trusted_lexical_evidence(pipeline):
    selected = pipeline.core.hydrate_candidates(["food-apple"])["food-apple"]
    selected.update(
        {
            "matched_channels": ["primary"],
            "matched_term": "Apple, raw",
            "matched_term_type": "primary_name",
            "primary_match_tier": 0,
            "source_term_exact": False,
            "retrieval_score": 6,
        }
    )
    concept = ExtractedConcept(
        source_phrase="100 grams raw apple",
        food_name="Apple, raw",
        quantity=ExtractedQuantity(value=100, unit="g"),
        preparation=["raw"],
    )
    decision = SelectorDecision(
        concept_index=0,
        selected_food_id="food-apple",
        confidence=0.99,
    )
    item = pipeline._build_item(
        concept_index=0,
        concept=concept,
        candidates=[selected],
        decision=decision,
        meal_default="lunch",
    )
    assert item.auto_log_eligible is True

    semantic_only = {
        **selected,
        "matched_channels": ["semantic"],
        "matched_term": None,
        "matched_term_type": "semantic",
        "primary_match_tier": None,
    }
    item = pipeline._build_item(
        concept_index=0,
        concept=concept,
        candidates=[semantic_only],
        decision=decision,
        meal_default="lunch",
    )
    assert item.auto_log_eligible is False


@pytest.mark.asyncio
async def test_exact_lexical_resolution_skips_semantic_and_selector(settings):
    pipeline = ResolverPipeline(
        settings=settings,
        core=CoreFoodRepository(settings.core_database_path),
        store=StubStore(),
        gemini=FastPathGemini(),
    )
    response = await pipeline._resolve_concepts(
        request_id="request-fast",
        transcript="100 grams raw apple",
        detected_language="en",
        concepts=[
            ExtractedConcept(
                source_phrase="100 grams raw apple",
                food_name="Apple, raw",
                quantity=ExtractedQuantity(value=100, unit="g"),
                preparation=["raw"],
            )
        ],
        local_timestamp="2026-07-24T12:00:00",
        timezone_name="Europe/Istanbul",
        audio_model="gemini-audio",
    )
    assert response.items[0].selected_candidate.food_id == "food-apple"
    assert response.items[0].auto_log_eligible is True
    assert response.metadata.extraction_model == "gemini-extraction"


@pytest.mark.asyncio
async def test_ambiguous_lexical_resolution_skips_semantic_but_uses_selector(settings):
    gemini = LexicalSelectorGemini()
    pipeline = ResolverPipeline(
        settings=settings,
        core=CoreFoodRepository(settings.core_database_path),
        store=StubStore(),
        gemini=gemini,
    )
    response = await pipeline._resolve_concepts(
        request_id="request-lexical-selector",
        transcript="100 grams apple",
        detected_language="en",
        concepts=[
            ExtractedConcept(
                source_phrase="100 grams apple",
                food_name="apple",
                quantity=ExtractedQuantity(value=100, unit="g"),
            )
        ],
        local_timestamp="2026-07-24T12:00:00",
        timezone_name="Europe/Istanbul",
        audio_model="gemini-audio",
    )
    assert gemini.selector_calls == 1
    assert response.items[0].selected_candidate.food_id == "food-apple"
    assert "preparation" in response.items[0].unresolved_fields


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


def test_audio_extraction_supports_a_day_batch_of_ten_foods():
    extraction = AudioExtraction(
        transcript="ten foods",
        detected_language="en",
        concepts=[
            ExtractedConcept(source_phrase=f"food {index}", food_name=f"food {index}")
            for index in range(10)
        ],
    )
    assert len(extraction.concepts) == 10


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
