from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable as IterableABC
from dataclasses import dataclass
from typing import Iterable, Mapping


ACTIVE_STAGE_KEY = "gemini_flash_db_payload_v2"
AI_MODEL_STAGE_KIND = "ai_model"
HUMAN_REVIEW_DESTINATION = "human_review"
FINALIZED_DESTINATION = "finalized"
BLOCKED_DESTINATION = "blocked"
ROUTING_BUCKET_HIGH_POSITIVE = "high_confidence_has_data"
ROUTING_BUCKET_HIGH_NEGATIVE = "high_confidence_no_usable_data"
ROUTING_BUCKET_LOW_POSITIVE = "low_confidence_has_data"
ROUTING_BUCKET_LOW_NEGATIVE = "low_confidence_no_usable_data"
ROUTING_STATUS_QUEUED = "queued_for_ai"
ROUTING_STATUS_PROCESSING = "ai_processing"
ROUTING_STATUS_FAILED = "ai_failed"
ROUTING_STATUS_HUMAN_READY = "human_review_ready"
ROUTING_STATUS_AI_FINAL_HAS_DATA = "ai_finalized_has_data"
ROUTING_STATUS_AI_FINAL_NO_DATA = "ai_finalized_no_usable_data"
DECISION_HAS_DATA = "has_data"
DECISION_NO_USABLE_DATA = "no_usable_data"
SUPPORTED_STANDARD_UNITS = {
    "g/100g",
    "mg/100g",
    "μg/100g",
    "kcal/100g",
    "kJ/100g",
    "IU/100g",
    "%",
}


@dataclass(frozen=True)
class RoutingStageConfig:
    stage_key: str
    stage_kind: str
    display_name: str
    model_name: str
    prompt_version: str
    active: bool
    positive_threshold: float
    negative_threshold: float
    audit_rate: float
    next_stage_on_low_confidence: str
    counts_as_truth: bool

    @classmethod
    def from_row(cls, row: Mapping[str, object]) -> "RoutingStageConfig":
        return cls(
            stage_key=str(row.get("stage_key") or "").strip(),
            stage_kind=str(row.get("stage_kind") or "").strip(),
            display_name=str(row.get("display_name") or "").strip(),
            model_name=str(row.get("model_name") or "").strip(),
            prompt_version=str(row.get("prompt_version") or "").strip(),
            active=bool(row.get("active")),
            positive_threshold=clamp_probability(row.get("positive_threshold")),
            negative_threshold=clamp_probability(row.get("negative_threshold")),
            audit_rate=clamp_probability(row.get("audit_rate")),
            next_stage_on_low_confidence=str(row.get("next_stage_on_low_confidence") or HUMAN_REVIEW_DESTINATION).strip(),
            counts_as_truth=bool(row.get("counts_as_truth")),
        )


@dataclass(frozen=True)
class PayloadNormalizationResult:
    payload: dict
    accepted_row_count: int
    rejected_row_count: int
    unmapped_food_count: int
    unmapped_nutrient_count: int
    input_row_count: int
    rejection_reasons: dict[str, int]

    @property
    def decision_kind(self) -> str:
        return str(self.payload.get("decision_kind") or DECISION_NO_USABLE_DATA)

    @property
    def has_data(self) -> bool:
        return self.decision_kind == DECISION_HAS_DATA

    def summary(self) -> dict:
        return {
            "decision_kind": self.decision_kind,
            "accepted_row_count": self.accepted_row_count,
            "rejected_row_count": self.rejected_row_count,
            "unmapped_food_count": self.unmapped_food_count,
            "unmapped_nutrient_count": self.unmapped_nutrient_count,
            "input_row_count": self.input_row_count,
            "rejection_reasons": dict(sorted(self.rejection_reasons.items())),
            "supported_units": sorted(SUPPORTED_STANDARD_UNITS),
        }


def clamp_probability(value: object) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if numeric < 0:
        return 0.0
    if numeric > 1:
        return 1.0
    return numeric


def classify_routing_bucket(
    *,
    is_useful: bool,
    overall_confidence: object,
    positive_threshold: object,
    negative_threshold: object,
) -> str:
    confidence = clamp_probability(overall_confidence)
    positive_floor = clamp_probability(positive_threshold)
    negative_floor = clamp_probability(negative_threshold)
    if is_useful:
        if confidence >= positive_floor:
            return ROUTING_BUCKET_HIGH_POSITIVE
        return ROUTING_BUCKET_LOW_POSITIVE
    if confidence >= negative_floor:
        return ROUTING_BUCKET_HIGH_NEGATIVE
    return ROUTING_BUCKET_LOW_NEGATIVE


def stable_audit_sample(
    *,
    paper_id: object,
    stage_key: object,
    model_name: object,
    audit_rate: object,
) -> bool:
    rate = clamp_probability(audit_rate)
    if rate <= 0:
        return False
    if rate >= 1:
        return True
    digest = hashlib.sha256(
        f"{paper_id}|{stage_key}|{model_name}".encode("utf-8")
    ).digest()
    threshold = int(rate * ((1 << 64) - 1))
    sample = int.from_bytes(digest[:8], "big")
    return sample <= threshold


def decision_kind_for_useful(is_useful: bool) -> str:
    return DECISION_HAS_DATA if is_useful else DECISION_NO_USABLE_DATA


def decision_kind_for_payload(payload: Mapping[str, object]) -> str:
    return str(payload.get("decision_kind") or DECISION_NO_USABLE_DATA)


def route_bucket(
    *,
    routing_bucket: str,
    audit_sampled: bool,
    has_human_truth: bool,
) -> tuple[str, str, bool]:
    if routing_bucket in {ROUTING_BUCKET_LOW_POSITIVE, ROUTING_BUCKET_LOW_NEGATIVE}:
        return ROUTING_STATUS_HUMAN_READY, HUMAN_REVIEW_DESTINATION, False
    if audit_sampled or has_human_truth:
        return ROUTING_STATUS_HUMAN_READY, HUMAN_REVIEW_DESTINATION, False
    if routing_bucket == ROUTING_BUCKET_HIGH_POSITIVE:
        return ROUTING_STATUS_AI_FINAL_HAS_DATA, FINALIZED_DESTINATION, True
    return ROUTING_STATUS_AI_FINAL_NO_DATA, FINALIZED_DESTINATION, True


def route_failure(*, has_human_truth: bool) -> tuple[str, str]:
    if has_human_truth:
        return ROUTING_STATUS_HUMAN_READY, HUMAN_REVIEW_DESTINATION
    return ROUTING_STATUS_FAILED, BLOCKED_DESTINATION


def canonical_json_dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def payload_text_and_hash(payload: Mapping[str, object]) -> tuple[str, str]:
    payload_text = canonical_json_dumps(payload)
    payload_hash = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    return payload_text, payload_hash


def input_hash_for_text(*, title: object, full_text: object) -> str:
    normalized_title = " ".join(str(title or "").split())
    normalized_text = " ".join(str(full_text or "").split())
    return hashlib.sha256(f"{normalized_title}\n{normalized_text}".encode("utf-8")).hexdigest()


def normalize_ai_payload(
    *,
    is_useful: bool,
    records: Iterable[object],
    nutrient_lookup: Iterable[Mapping[str, object]] | None = None,
    food_lookup: Iterable[Mapping[str, object]] | None = None,
) -> dict:
    return normalize_ai_payload_with_summary(
        is_useful=is_useful,
        records=records,
        nutrient_lookup=nutrient_lookup,
        food_lookup=food_lookup,
    ).payload


def normalize_ai_payload_with_summary(
    *,
    is_useful: bool,
    records: Iterable[object],
    nutrient_lookup: Iterable[Mapping[str, object]] | None = None,
    food_lookup: Iterable[Mapping[str, object]] | None = None,
) -> PayloadNormalizationResult:
    record_list = list(records or [])
    if not is_useful:
        return PayloadNormalizationResult(
            payload=_empty_payload(),
            accepted_row_count=0,
            rejected_row_count=0,
            unmapped_food_count=0,
            unmapped_nutrient_count=0,
            input_row_count=len(record_list),
            rejection_reasons={},
        )

    nutrient_resolver = _build_exact_name_resolver(
        nutrient_lookup or [],
        primary_name_field="standard_name",
        alias_fields=("aliases", "alias_names"),
    )
    food_resolver = _build_exact_name_resolver(
        food_lookup or [],
        primary_name_field="canonical_name",
        alias_fields=(),
    )

    grouped: dict[tuple[str, str, bool], dict] = {}
    accepted_row_count = 0
    rejected_row_count = 0
    unmapped_food_count = 0
    unmapped_nutrient_count = 0
    rejection_reasons: dict[str, int] = {}

    for record in record_list:
        row = _record_to_mapping(record)
        food_name = _normalize_space(row.get("food_name"))
        nutrient_name = _normalize_space(row.get("nutrient_name"))
        raw_amount = row.get("amount")
        if raw_amount is None:
            raw_amount = row.get("value")
        amount = _normalize_numeric(raw_amount)
        if not food_name or not nutrient_name or amount is None:
            rejected_row_count += 1
            _bump_reason(rejection_reasons, "missing_required_field")
            continue

        unit = _standardize_unit(row.get("unit"), row.get("basis"))
        if unit is None:
            rejected_row_count += 1
            _bump_reason(rejection_reasons, "unsupported_unit_or_basis")
            continue

        food_match = _resolve_exact_name(food_resolver, food_name)
        if food_match:
            resolved_food_id = str(food_match["id"])
            resolved_food_name = _normalize_space(food_match.get("canonical_name")) or food_name
            is_custom_food = False
            group_key = (resolved_food_name.casefold(), resolved_food_id, is_custom_food)
        else:
            resolved_food_id = None
            resolved_food_name = food_name
            is_custom_food = True
            unmapped_food_count += 1
            group_key = (_normalize_lookup_text(resolved_food_name), "", is_custom_food)

        item = grouped.get(group_key)
        if item is None:
            item = {
                "food_name": resolved_food_name,
                "food_fdc_id": resolved_food_id,
                "is_custom_food": is_custom_food,
                "nutrients": [],
            }
            grouped[group_key] = item

        nutrient_match = _resolve_exact_name(nutrient_resolver, nutrient_name)
        if nutrient_match:
            nutrient_id = str(nutrient_match["id"])
            resolved_nutrient_name = _normalize_space(nutrient_match.get("standard_name")) or nutrient_name
        else:
            nutrient_id = None
            resolved_nutrient_name = nutrient_name
            unmapped_nutrient_count += 1

        item["nutrients"].append(
            {
                "nutrient_id": nutrient_id,
                "nutrient_name": resolved_nutrient_name,
                "value": round(amount, 6),
                "unit": unit,
            }
        )
        accepted_row_count += 1

    ordered_food_items = []
    for _key, item in sorted(
        grouped.items(),
        key=lambda entry: (
            _normalize_space(entry[1].get("food_name")),
            str(entry[1].get("food_fdc_id") or ""),
            bool(entry[1].get("is_custom_food")),
        ),
    ):
        item["nutrients"] = sorted(
            item["nutrients"],
            key=lambda nutrient: (
                str(nutrient.get("nutrient_id") or ""),
                _normalize_space(nutrient.get("nutrient_name")),
                _normalize_space(nutrient.get("unit")),
                nutrient.get("value"),
            ),
        )
        ordered_food_items.append(item)

    if not ordered_food_items:
        return PayloadNormalizationResult(
            payload=_empty_payload(),
            accepted_row_count=0,
            rejected_row_count=rejected_row_count,
            unmapped_food_count=0,
            unmapped_nutrient_count=0,
            input_row_count=len(record_list),
            rejection_reasons=rejection_reasons,
        )

    return PayloadNormalizationResult(
        payload={
            "decision_kind": DECISION_HAS_DATA,
            "food_items": ordered_food_items,
        },
        accepted_row_count=accepted_row_count,
        rejected_row_count=rejected_row_count,
        unmapped_food_count=unmapped_food_count,
        unmapped_nutrient_count=unmapped_nutrient_count,
        input_row_count=len(record_list),
        rejection_reasons=rejection_reasons,
    )


def _empty_payload() -> dict:
    return {
        "decision_kind": DECISION_NO_USABLE_DATA,
        "food_items": [],
    }


def _bump_reason(rejection_reasons: dict[str, int], reason: str) -> None:
    rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1


def _build_exact_name_resolver(
    rows: Iterable[Mapping[str, object]],
    *,
    primary_name_field: str,
    alias_fields: tuple[str, ...],
) -> dict[str, Mapping[str, object] | None]:
    resolver: dict[str, Mapping[str, object] | None] = {}
    for row in rows:
        if not isinstance(row, Mapping) or not row.get("id"):
            continue
        candidate_names = [_normalize_space(row.get(primary_name_field))]
        for alias_field in alias_fields:
            aliases = row.get(alias_field)
            if isinstance(aliases, str):
                candidate_names.append(aliases)
            elif isinstance(aliases, IterableABC):
                candidate_names.extend(str(alias) for alias in aliases)
        for name in candidate_names:
            key = _normalize_lookup_text(name)
            if not key:
                continue
            existing = resolver.get(key)
            if existing is None and key in resolver:
                continue
            if existing and existing.get("id") != row.get("id"):
                resolver[key] = None
            else:
                resolver[key] = row
    return resolver


def _resolve_exact_name(
    resolver: Mapping[str, Mapping[str, object] | None],
    value: object,
) -> Mapping[str, object] | None:
    resolved = resolver.get(_normalize_lookup_text(value))
    return resolved if resolved else None


def _standardize_unit(raw_unit: object, raw_basis: object) -> str | None:
    unit_text = _normalize_unit_text(raw_unit)
    basis_text = _normalize_basis_text(raw_basis)
    if not unit_text:
        return None

    if unit_text in {"%", "percent", "percentage"}:
        if basis_text and not _is_supported_100g_basis(basis_text):
            return None
        return "%"

    compound = _unit_from_compound_100g(unit_text)
    if compound:
        if basis_text and not _is_supported_100g_basis(basis_text):
            return None
        return compound

    base_unit = _canonical_base_unit(unit_text)
    if not base_unit or not _is_supported_100g_basis(basis_text):
        return None
    return f"{base_unit}/100g"


def _unit_from_compound_100g(unit_text: str) -> str | None:
    compact = _compact_unit_text(unit_text)
    for separator in ("/100g", "per100g"):
        if compact.endswith(separator):
            base = compact[: -len(separator)]
            canonical = _canonical_base_unit(base)
            return f"{canonical}/100g" if canonical else None
    return None


def _canonical_base_unit(unit_text: str) -> str | None:
    compact = _compact_unit_text(unit_text)
    mapping = {
        "g": "g",
        "gram": "g",
        "grams": "g",
        "mg": "mg",
        "milligram": "mg",
        "milligrams": "mg",
        "μg": "μg",
        "ug": "μg",
        "mcg": "μg",
        "microgram": "μg",
        "micrograms": "μg",
        "kcal": "kcal",
        "kilocalorie": "kcal",
        "kilocalories": "kcal",
        "kj": "kJ",
        "kilojoule": "kJ",
        "kilojoules": "kJ",
        "iu": "IU",
        "i.u.": "IU",
        "internationalunit": "IU",
        "internationalunits": "IU",
    }
    return mapping.get(compact)


def _is_supported_100g_basis(basis_text: str) -> bool:
    compact = _compact_unit_text(basis_text)
    return compact in {
        "100g",
        "per100g",
        "/100g",
        "per_100g",
        "100gram",
        "100grams",
        "per100gram",
        "per100grams",
    }


def _normalize_unit_text(value: object) -> str:
    text = _normalize_space(value).replace("µ", "μ")
    return text.casefold()


def _normalize_basis_text(value: object) -> str:
    return _normalize_space(value).replace("µ", "μ").casefold()


def _compact_unit_text(value: object) -> str:
    return (
        _normalize_space(value)
        .replace("µ", "μ")
        .casefold()
        .replace(" ", "")
        .replace("-", "")
    )


def _normalize_lookup_text(value: object) -> str:
    return _normalize_space(value).replace("µ", "μ").casefold()


def count_payload_nutrient_rows(payload: Mapping[str, object]) -> int:
    food_items = payload.get("food_items")
    if not isinstance(food_items, list):
        return 0
    return sum(
        len(food_item.get("nutrients") or [])
        for food_item in food_items
        if isinstance(food_item, Mapping)
    )


def normalized_payload_has_data(payload: Mapping[str, object]) -> bool:
    return (
        decision_kind_for_payload(payload) == DECISION_HAS_DATA
        and count_payload_nutrient_rows(payload) > 0
    )


def normalize_payload_decision(payload: Mapping[str, object]) -> dict:
    if normalized_payload_has_data(payload):
        return {
            "decision_kind": DECISION_HAS_DATA,
            "food_items": list(payload.get("food_items") or []),
        }
    return _empty_payload()


def _record_to_mapping(record: object) -> Mapping[str, object]:
    if isinstance(record, Mapping):
        return record
    amount = getattr(record, "amount", None)
    if amount is None:
        amount = getattr(record, "value", None)
    return {
        "food_name": getattr(record, "food_name", None) or getattr(record, "food", None),
        "nutrient_name": getattr(record, "nutrient_name", None) or getattr(record, "nutrient", None),
        "amount": amount,
        "unit": getattr(record, "unit", None),
        "basis": getattr(record, "basis", None),
        "preparation_state": getattr(record, "preparation_state", None),
    }


def _normalize_space(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _normalize_numeric(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
