from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


MealType = Literal["breakfast", "lunch", "dinner", "snacks"]
TermType = Literal[
    "primary_name",
    "common_name",
    "foodon_label",
    "additional_description",
    "semantic",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExtractedQuantity(StrictModel):
    value: float | None = Field(default=None, gt=0)
    unit: str | None = None


class ExtractedConcept(StrictModel):
    source_phrase: str = Field(min_length=1, max_length=160)
    food_name: str = Field(min_length=1, max_length=160)
    quantity: ExtractedQuantity = Field(default_factory=ExtractedQuantity)
    preparation: list[str] = Field(default_factory=list, max_length=8)
    weight_basis: Literal["edible", "as_purchased"] | None = None


class AudioExtraction(StrictModel):
    transcript: str = Field(max_length=1000)
    detected_language: str = Field(max_length=32)
    concepts: list[ExtractedConcept] = Field(min_length=1, max_length=5)


class CandidatePortion(StrictModel):
    portion_id: str
    description: str
    gram_weight: float = Field(gt=0)
    amount: float | None = Field(default=None, gt=0)


class FoodCandidate(StrictModel):
    food_id: str
    name: str
    category: str
    quality_status: str
    source_release_id: str
    portions: list[CandidatePortion] = Field(default_factory=list)
    has_usable_weight_factor: bool = False
    matched_channels: list[Literal["primary", "source_term", "semantic"]] = Field(
        default_factory=list
    )
    matched_term: str | None = None
    matched_term_type: TermType | None = None
    retrieval_score: float = 0


class SelectorDecision(StrictModel):
    concept_index: int = Field(ge=0, le=4)
    selected_food_id: str | None = None
    alternative_food_ids: list[str] = Field(default_factory=list, max_length=4)
    confidence: float = Field(ge=0, le=1)
    unresolved_fields: list[
        Literal[
            "food",
            "quantity",
            "preparation",
            "weight_basis",
            "unspecified_food",
        ]
    ] = Field(default_factory=list)
    no_match_reason: str | None = Field(default=None, max_length=180)


class SelectorOutput(StrictModel):
    decisions: list[SelectorDecision] = Field(max_length=5)


class QuantityResolution(StrictModel):
    status: Literal["resolved", "unresolved"]
    grams: float | None = Field(default=None, gt=0)
    spoken_value: float | None = Field(default=None, gt=0)
    spoken_unit: str | None = None
    source_portion_id: str | None = None
    source_portion_description: str | None = None


class WeightBasisResolution(StrictModel):
    status: Literal["resolved", "unresolved"]
    value: Literal["edible", "as_purchased"] | None = None


class ResolvedFoodItem(StrictModel):
    concept_index: int = Field(ge=0, le=4)
    source_phrase: str
    selected_candidate: FoodCandidate | None
    alternatives: list[FoodCandidate]
    confidence: float = Field(ge=0, le=1)
    preparation: list[str]
    weight_basis: WeightBasisResolution
    quantity: QuantityResolution
    meal_default: MealType
    unresolved_fields: list[str]
    is_unspecified: bool = False
    no_match_reason: str | None = None


class ResolutionMetadata(StrictModel):
    request_id: str
    core_version: str
    index_version: str
    audio_model: str | None = None
    selector_model: str | None = None
    embedding_model: str | None = None


class ResolutionResponse(StrictModel):
    status: Literal["resolved", "manual_search"]
    metadata: ResolutionMetadata
    transcript: str
    detected_language: str
    items: list[ResolvedFoodItem] = Field(default_factory=list, max_length=5)
    manual_search_query: str | None = None
    manual_search_candidates: list[FoodCandidate] = Field(default_factory=list)
    error_code: str | None = None


class ResolveTextRequest(StrictModel):
    query: str = Field(min_length=1, max_length=200)
    local_timestamp: str | None = Field(default=None, max_length=64)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)


class FeedbackItem(StrictModel):
    source_phrase: str = Field(min_length=1, max_length=160)
    proposed_food_id: str | None = Field(default=None, max_length=100)
    final_food_id: str = Field(min_length=1, max_length=100)
    corrected: bool


class FeedbackRequest(StrictModel):
    request_id: str = Field(min_length=1, max_length=64)
    core_version: str = Field(min_length=1, max_length=64)
    index_version: str = Field(min_length=1, max_length=128)
    model_version: str = Field(min_length=1, max_length=128)
    items: list[FeedbackItem] = Field(min_length=1, max_length=5)


class FeedbackResponse(StrictModel):
    stored: int = Field(ge=0, le=5)


class DeleteFeedbackResponse(StrictModel):
    deleted: bool


class HealthResponse(StrictModel):
    status: Literal["ok"]
    service_version: str
    core_version: str
    index_version: str
    providers_configured: bool
