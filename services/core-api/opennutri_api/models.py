from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


QualityStatus = Literal["complete", "ambiguous", "partial", "excluded"]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    api_version: str
    artifact_version: str
    release_ids: list[str]


class CoveragePeriod(BaseModel):
    start: date
    end: date


class LicenseInfo(BaseModel):
    identifier: str
    url: str


class DatasetRelease(BaseModel):
    release_id: str
    artifact_version: str
    publisher: str
    dataset_name: str
    data_type: str
    release_date: date
    coverage: CoveragePeriod
    download_url: str
    archive_sha256: str
    source_tree_sha256: str
    license: LicenseInfo


class CurrentReleaseResponse(BaseModel):
    artifact_version: str
    datasets: list[DatasetRelease]


class FoodCategory(BaseModel):
    category_id: str
    name: str


class FoodSource(BaseModel):
    release_id: str
    publisher: str
    dataset_name: str
    data_type: str
    source_food_id: str
    source_food_code: str


class FoodQuality(BaseModel):
    status: QualityStatus
    ambiguity_flags: list[str]
    nutrient_count: int = Field(ge=0)
    portion_count: int = Field(ge=0)


class FoodSearchItem(BaseModel):
    food_id: str
    name: str
    category: FoodCategory
    source: FoodSource
    quality: FoodQuality


class FoodSearchResponse(BaseModel):
    query: str
    match_mode: Literal["all_terms", "partial_terms"]
    matched_terms: list[str]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    items: list[FoodSearchItem]


class NutrientValue(BaseModel):
    nutrient_id: str
    source_nutrient_id: str
    nutrient_number: str
    name: str
    amount: float = Field(ge=0)
    unit: str
    basis: str
    source_row_id: str
    derivation_id: str | None
    data_points: int | None = Field(default=None, ge=0)
    minimum: float | None = Field(default=None, ge=0)
    maximum: float | None = Field(default=None, ge=0)
    median: float | None = Field(default=None, ge=0)
    footnote: str | None
    min_year_acquired: str | None


class FoodPortion(BaseModel):
    portion_id: str
    source_portion_id: str
    sequence_number: int | None
    description: str
    gram_weight: float = Field(gt=0)
    amount: float | None = Field(default=None, gt=0)
    measure_unit_id: str
    measure_unit_name: str
    modifier: str
    data_points: int | None = Field(default=None, ge=0)
    footnote: str | None
    min_year_acquired: str | None


class EdiblePortionFactor(BaseModel):
    factor_id: str
    factor_type: Literal["as_purchased_to_edible"]
    edible_fraction: float | None = Field(default=None, gt=0, le=1)
    refuse_percent: float | None = Field(default=None, ge=0, lt=100)
    refuse_description: str
    source_dataset: str
    source_url: str
    source_food_code: str
    source_refuse_percent: float = Field(ge=0, lt=100)
    derivation: str
    review_status: Literal["source_reported", "reviewed", "conflict"]
    is_usable: bool
    notes: str | None


class FoodDetailResponse(BaseModel):
    food_id: str
    name: str
    original_description: str
    category: FoodCategory
    source: FoodSource
    quality: FoodQuality
    publication_date: date
    coverage: CoveragePeriod
    nutrients: list[NutrientValue]
    portions: list[FoodPortion]
    weight_factors: list[EdiblePortionFactor]
