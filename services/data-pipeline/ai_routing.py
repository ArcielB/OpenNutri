from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable as IterableABC
from dataclasses import dataclass
from typing import Iterable, Mapping


ACTIVE_STAGE_KEY = "gemma_proof_extraction_v1"
AI_MODEL_STAGE_KIND = "ai_model"
HUMAN_REVIEW_DESTINATION = "human_review"
FINALIZED_DESTINATION = "finalized"
BLOCKED_DESTINATION = "blocked"
NEXT_STAGE_DESTINATION = "next_stage"
PROVISIONAL_SKIP_DESTINATION = "provisional_skip"
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
ROUTING_STATUS_AI_PROVISIONAL_NO_DATA = "ai_provisional_no_usable_data"
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
EVIDENCE_METADATA_KEYS = (
    "table_label",
    "page_hint",
    "source_quote",
    "source_location_type",
    "section_heading",
    "paragraph_hint",
)


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
    stage_order: int = 0
    next_stage_on_has_data: str = ""
    no_data_route_destination: str = HUMAN_REVIEW_DESTINATION
    fallback_model_names: tuple[str, ...] = ()

    @classmethod
    def from_row(cls, row: Mapping[str, object]) -> "RoutingStageConfig":
        try:
            stage_order = int(row.get("stage_order") or 0)
        except (TypeError, ValueError):
            stage_order = 0
        fallback_model_names = _parse_fallback_model_names(row.get("fallback_model_names"))
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
            stage_order=stage_order,
            next_stage_on_has_data=str(row.get("next_stage_on_has_data") or "").strip(),
            no_data_route_destination=str(row.get("no_data_route_destination") or HUMAN_REVIEW_DESTINATION).strip(),
            fallback_model_names=fallback_model_names,
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


def _parse_fallback_model_names(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str) and not value.strip():
        return ()
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = [part.strip() for part in value.split(",")]
    else:
        parsed = value
    if not isinstance(parsed, IterableABC) or isinstance(parsed, (bytes, bytearray, str, Mapping)):
        return ()
    names: list[str] = []
    seen: set[str] = set()
    for item in parsed:
        name = str(item or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return tuple(names)


def meets_auto_finalize_threshold(*, confidence: object, threshold: object) -> bool:
    threshold_floor = clamp_probability(threshold)
    if threshold_floor >= 1.0:
        return False
    return clamp_probability(confidence) >= threshold_floor


def classify_routing_bucket(
    *,
    is_useful: bool,
    overall_confidence: object,
    positive_threshold: object,
    negative_threshold: object,
) -> str:
    if is_useful:
        if meets_auto_finalize_threshold(confidence=overall_confidence, threshold=positive_threshold):
            return ROUTING_BUCKET_HIGH_POSITIVE
        return ROUTING_BUCKET_LOW_POSITIVE
    if meets_auto_finalize_threshold(confidence=overall_confidence, threshold=negative_threshold):
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
    nutrient_id_resolver = _build_id_resolver(nutrient_lookup or [])
    food_resolver = _build_exact_name_resolver(
        food_lookup or [],
        primary_name_field="canonical_name",
        alias_fields=("aliases", "alias_names"),
    )
    food_id_resolver = _build_id_resolver(food_lookup or [])

    grouped: dict[tuple[str, str, bool, str, str], dict] = {}
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

        food_match = _resolve_reference_row(
            row=row,
            name_value=food_name,
            id_fields=("food_fdc_id", "food_id", "entity_id", "db_food_id"),
            id_resolver=food_id_resolver,
            name_resolver=food_resolver,
            primary_name_field="canonical_name",
            alias_fields=("aliases", "alias_names"),
        )
        raw_food_name = _normalize_space(row.get("raw_food_name")) or food_name
        preparation_state = _normalize_space(row.get("preparation_state")) or None

        if food_match:
            resolved_food_id = str(food_match["id"])
            resolved_food_name = _normalize_space(food_match.get("canonical_name")) or food_name
            is_custom_food = False
        else:
            resolved_food_id = None
            resolved_food_name = food_name
            is_custom_food = True
            unmapped_food_count += 1
        group_key = (
            _normalize_lookup_text(resolved_food_name),
            resolved_food_id or "",
            is_custom_food,
            _normalize_lookup_text(raw_food_name),
            _normalize_lookup_text(preparation_state),
        )

        item = grouped.get(group_key)
        if item is None:
            item = {
                "food_name": resolved_food_name,
                "food_fdc_id": resolved_food_id,
                "is_custom_food": is_custom_food,
                "raw_food_name": raw_food_name,
                "preparation_state": preparation_state,
                "nutrients": [],
            }
            grouped[group_key] = item

        nutrient_match = _resolve_reference_row(
            row=row,
            name_value=nutrient_name,
            id_fields=("nutrient_id", "nutrient_db_id", "master_nutrient_id", "db_nutrient_id"),
            id_resolver=nutrient_id_resolver,
            name_resolver=nutrient_resolver,
            primary_name_field="standard_name",
            alias_fields=("aliases", "alias_names"),
        )
        if nutrient_match:
            nutrient_id = str(nutrient_match["id"])
            resolved_nutrient_name = _normalize_space(nutrient_match.get("standard_name")) or nutrient_name
            is_custom_nutrient = False
        else:
            nutrient_id = None
            resolved_nutrient_name = nutrient_name
            is_custom_nutrient = True
            unmapped_nutrient_count += 1

        metadata = _normalize_metadata(row.get("metadata"))
        for evidence_key in EVIDENCE_METADATA_KEYS:
            if row.get(evidence_key) is not None:
                metadata[evidence_key] = _json_safe_value(row.get(evidence_key))
        flags = _normalize_string_list(row.get("flags"))
        if flags:
            metadata["flags"] = flags

        item["nutrients"].append(
            {
                "nutrient_id": nutrient_id,
                "is_custom_nutrient": is_custom_nutrient,
                "nutrient_name": resolved_nutrient_name,
                "raw_nutrient_name": _normalize_space(row.get("raw_nutrient_name")) or nutrient_name,
                "value": round(amount, 6),
                "unit": unit,
                "basis": "per_100g",
                "sample_size": _normalize_int(row.get("sample_size")),
                "confidence": _normalize_probability(row.get("confidence")),
                "source_citation": _normalize_space(row.get("source_citation")) or None,
                "metadata": metadata,
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
            _normalize_space(entry[1].get("raw_food_name")),
            _normalize_space(entry[1].get("preparation_state")),
        ),
    ):
        item["nutrients"] = sorted(
            item["nutrients"],
            key=lambda nutrient: (
                str(nutrient.get("nutrient_id") or ""),
                bool(nutrient.get("is_custom_nutrient")),
                _normalize_space(nutrient.get("nutrient_name")),
                _normalize_space(nutrient.get("raw_nutrient_name")),
                _normalize_space(nutrient.get("unit")),
                _normalize_space(nutrient.get("basis")),
                nutrient.get("value"),
                nutrient.get("sample_size") if nutrient.get("sample_size") is not None else -1,
                nutrient.get("confidence") if nutrient.get("confidence") is not None else -1,
                _normalize_space(nutrient.get("source_citation")),
                canonical_json_dumps(nutrient.get("metadata") or {}),
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


def _build_id_resolver(
    rows: Iterable[Mapping[str, object]],
) -> dict[str, Mapping[str, object]]:
    resolver: dict[str, Mapping[str, object]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        row_id = _normalize_identifier(row.get("id"))
        if row_id:
            resolver[row_id] = row
    return resolver


def _resolve_exact_name(
    resolver: Mapping[str, Mapping[str, object] | None],
    value: object,
) -> Mapping[str, object] | None:
    resolved = resolver.get(_normalize_lookup_text(value))
    return resolved if resolved else None


def _resolve_reference_row(
    *,
    row: Mapping[str, object],
    name_value: object,
    id_fields: tuple[str, ...],
    id_resolver: Mapping[str, Mapping[str, object]],
    name_resolver: Mapping[str, Mapping[str, object] | None],
    primary_name_field: str,
    alias_fields: tuple[str, ...],
) -> Mapping[str, object] | None:
    for field in id_fields:
        candidate_id = _normalize_identifier(row.get(field))
        if not candidate_id:
            continue
        candidate_row = id_resolver.get(candidate_id)
        if candidate_row and _reference_row_accepts_name(
            candidate_row,
            name_value,
            primary_name_field=primary_name_field,
            alias_fields=alias_fields,
        ):
            return candidate_row
        break
    return _resolve_exact_name(name_resolver, name_value)


def _reference_row_accepts_name(
    row: Mapping[str, object],
    value: object,
    *,
    primary_name_field: str,
    alias_fields: tuple[str, ...],
) -> bool:
    target = _normalize_lookup_text(value)
    if not target:
        return False
    candidate_names = [_normalize_space(row.get(primary_name_field))]
    for alias_field in alias_fields:
        aliases = row.get(alias_field)
        if isinstance(aliases, str):
            candidate_names.append(aliases)
        elif isinstance(aliases, IterableABC):
            candidate_names.extend(str(alias) for alias in aliases)
    return any(_normalize_lookup_text(name) == target for name in candidate_names)


def _standardize_unit(raw_unit: object, raw_basis: object) -> str | None:
    unit_text = _normalize_unit_text(raw_unit)
    basis_text = _normalize_basis_text(raw_basis)
    if not unit_text:
        return None

    if unit_text in {"%", "percent", "percentage"}:
        if basis_text and not _is_supported_basis_modifier_or_100g(basis_text):
            return None
        return "%"

    compound = _unit_from_compound_100g(unit_text)
    if compound:
        if basis_text and not _is_supported_basis_modifier_or_100g(basis_text):
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
    if compact in {
        "100g",
        "per100g",
        "/100g",
        "per_100g",
        "100gram",
        "100grams",
        "per100gram",
        "per100grams",
    }:
        return True
    if not any(marker in compact for marker in ("100g", "100gram", "100grams")):
        return False
    if any(marker in compact for marker in ("dry", "dm", "drymatter")):
        return False
    return any(
        marker in compact
        for marker in (
            "fresh",
            "freshweight",
            "wet",
            "wetweight",
            "asis",
            "asreceived",
            "edibleportion",
        )
    )


def _is_supported_basis_modifier_or_100g(basis_text: str) -> bool:
    if _is_supported_100g_basis(basis_text):
        return True
    compact = _compact_unit_text(basis_text)
    if any(marker in compact for marker in ("dry", "dm", "drymatter")):
        return False
    return compact in {
        "fresh",
        "freshweight",
        "wet",
        "wetweight",
        "wetbasis",
        "asis",
        "asreceived",
        "edibleportion",
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


def _normalize_identifier(value: object) -> str:
    return str(value or "").strip()


def _normalize_int(value: object) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _normalize_probability(value: object) -> float | None:
    if value is None or value == "":
        return None
    return round(clamp_probability(value), 6)


def _normalize_string_list(value: object) -> list[str]:
    if isinstance(value, str):
        candidate = _normalize_space(value)
        return [candidate] if candidate else []
    if not isinstance(value, IterableABC):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _normalize_space(item)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _normalize_metadata(value: object) -> dict:
    if not isinstance(value, Mapping):
        return {}
    metadata: dict[str, object] = {}
    for key, raw_value in sorted(value.items(), key=lambda item: str(item[0])):
        key_text = _normalize_space(key)
        if not key_text or raw_value is None:
            continue
        metadata[key_text] = _json_safe_value(raw_value)
    return metadata


def _json_safe_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe_value(nested)
            for key, nested in sorted(value.items(), key=lambda item: str(item[0]))
            if key is not None
        }
    if isinstance(value, IterableABC) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe_value(item) for item in value]
    return str(value)


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
        "sample_size": getattr(record, "sample_size", None),
        "confidence": getattr(record, "confidence", None),
        "source_citation": getattr(record, "source_citation", None),
        "metadata": getattr(record, "metadata", None),
        "table_label": getattr(record, "table_label", None),
        "page_hint": getattr(record, "page_hint", None),
        "source_quote": getattr(record, "source_quote", None),
        "source_location_type": getattr(record, "source_location_type", None),
        "section_heading": getattr(record, "section_heading", None),
        "paragraph_hint": getattr(record, "paragraph_hint", None),
        "flags": getattr(record, "flags", None),
        "raw_food_name": getattr(record, "raw_food_name", None),
        "raw_nutrient_name": getattr(record, "raw_nutrient_name", None),
        "food_fdc_id": getattr(record, "food_fdc_id", None),
        "food_id": getattr(record, "food_id", None),
        "entity_id": getattr(record, "entity_id", None),
        "db_food_id": getattr(record, "db_food_id", None),
        "nutrient_id": getattr(record, "nutrient_id", None),
        "nutrient_db_id": getattr(record, "nutrient_db_id", None),
        "master_nutrient_id": getattr(record, "master_nutrient_id", None),
        "db_nutrient_id": getattr(record, "db_nutrient_id", None),
    }


def _normalize_space(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _normalize_numeric(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
