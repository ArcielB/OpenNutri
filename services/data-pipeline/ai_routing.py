from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Mapping


ACTIVE_STAGE_KEY = "gemini_flash_triage_v1"
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


def normalize_ai_payload(*, is_useful: bool, records: Iterable[object]) -> dict:
    if not is_useful:
        return {
            "decision_kind": DECISION_NO_USABLE_DATA,
            "food_items": [],
        }

    grouped: dict[tuple[str, str, str], dict] = {}
    for record in records:
        row = _record_to_mapping(record)
        food_name = _normalize_space(row.get("food_name"))
        nutrient_name = _normalize_space(row.get("nutrient_name"))
        unit = _normalize_space(row.get("unit"))
        amount = _normalize_numeric(row.get("amount"))
        if not food_name or not nutrient_name or amount is None or not unit:
            continue
        basis = _normalize_space(row.get("basis"))
        preparation_state = _normalize_space(row.get("preparation_state"))
        group_key = (food_name.lower(), basis.lower(), preparation_state.lower())
        item = grouped.get(group_key)
        if item is None:
            item = {
                "food_name": food_name,
                "food_fdc_id": None,
                "is_custom_food": True,
                "nutrients": [],
            }
            grouped[group_key] = item
        item["nutrients"].append(
            {
                "nutrient_id": None,
                "nutrient_name": nutrient_name,
                "value": round(amount, 6),
                "unit": unit,
            }
        )

    ordered_food_items = []
    for key in sorted(grouped):
        item = grouped[key]
        item["nutrients"] = sorted(
            item["nutrients"],
            key=lambda nutrient: (
                str(nutrient.get("nutrient_name") or "").lower(),
                str(nutrient.get("unit") or "").lower(),
                nutrient.get("value"),
            ),
        )
        ordered_food_items.append(item)

    return {
        "decision_kind": DECISION_HAS_DATA,
        "food_items": ordered_food_items,
    }


def _record_to_mapping(record: object) -> Mapping[str, object]:
    if isinstance(record, Mapping):
        return record
    return {
        "food_name": getattr(record, "food_name", None),
        "nutrient_name": getattr(record, "nutrient_name", None),
        "amount": getattr(record, "amount", None),
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
