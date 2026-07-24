from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Settings
from .core_repository import CoreFoodRepository
from .gemini import GeminiClient
from .models import (
    CandidatePortion,
    ExtractedConcept,
    ExtractedQuantity,
    FoodCandidate,
    QuantityResolution,
    ResolutionMetadata,
    ResolutionResponse,
    ResolvedFoodItem,
    SelectorDecision,
    WeightBasisResolution,
)
from .supabase_store import SupabasePrivateStore


GRAM_UNITS = {"g", "gr", "gram", "grams", "gramme", "grammes"}
KILOGRAM_UNITS = {"kg", "kilogram", "kilograms", "kilo"}
PREPARATION_WORDS = {
    "raw",
    "cooked",
    "boiled",
    "fried",
    "baked",
    "roasted",
    "grilled",
    "drained",
    "skin",
    "skinless",
    "bone",
    "boneless",
    "çiğ",
    "pişmiş",
    "haşlanmış",
    "kızarmış",
    "süzülmüş",
    "kabuklu",
    "kabuksuz",
    "kemikli",
    "kemiksiz",
}
MATERIAL_STATE_RE = re.compile(
    r"\b(raw|cooked|boiled|fried|baked|roasted|grilled|drained|skin|skinless|"
    r"bone|boneless|çiğ|pişmiş|haşlanmış|kızarmış|süzülmüş|kabuklu|kabuksuz|"
    r"kemikli|kemiksiz)\b",
    re.IGNORECASE,
)
QUANTITY_RE = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|kilograms?|kilo|g|gr|grams?|"
    r"adet|piece|pieces|cup|cups|fincan|bardak|dilim|slice|slices)\b",
    re.IGNORECASE,
)


class ResolverPipeline:
    def __init__(
        self,
        *,
        settings: Settings,
        core: CoreFoodRepository,
        store: SupabasePrivateStore,
        gemini: GeminiClient,
    ) -> None:
        self.settings = settings
        self.core = core
        self.store = store
        self.gemini = gemini

    async def resolve_voice(
        self,
        *,
        request_id: str,
        wav_bytes: bytes,
        language_hint: str,
        local_timestamp: str,
        timezone_name: str,
    ) -> ResolutionResponse:
        extraction = await self.gemini.transcribe_and_extract(
            wav_bytes=wav_bytes,
            language_hint=language_hint,
        )
        return await self._resolve_concepts(
            request_id=request_id,
            transcript=extraction.transcript,
            detected_language=extraction.detected_language,
            concepts=extraction.concepts,
            local_timestamp=local_timestamp,
            timezone_name=timezone_name,
            audio_model=self.settings.gemini_audio_model,
        )

    async def resolve_text(
        self,
        *,
        request_id: str,
        query: str,
        local_timestamp: str | None,
        timezone_name: str,
    ) -> ResolutionResponse:
        concept = self._concept_from_text(query)
        return await self._resolve_concepts(
            request_id=request_id,
            transcript=query,
            detected_language=self._text_language(query),
            concepts=[concept],
            local_timestamp=local_timestamp or datetime.now().isoformat(),
            timezone_name=timezone_name,
            audio_model=None,
        )

    async def _resolve_concepts(
        self,
        *,
        request_id: str,
        transcript: str,
        detected_language: str,
        concepts: list[ExtractedConcept],
        local_timestamp: str,
        timezone_name: str,
        audio_model: str | None,
    ) -> ResolutionResponse:
        vectors = await self.gemini.embed_concepts(concepts)
        candidate_sets: list[list[dict[str, Any]]] = []
        for concept, vector in zip(concepts, vectors, strict=True):
            candidate_sets.append(await self._retrieve(concept.food_name, vector))
        selector = await self.gemini.select_candidates(
            concepts=concepts,
            candidate_sets=candidate_sets,
        )
        decisions = {decision.concept_index: decision for decision in selector.decisions}
        meal_default = self.meal_for(local_timestamp, timezone_name)
        items = [
            self._build_item(
                concept_index=index,
                concept=concept,
                candidates=candidate_sets[index],
                decision=decisions.get(index),
                meal_default=meal_default,
            )
            for index, concept in enumerate(concepts)
        ]
        return ResolutionResponse(
            status="resolved",
            metadata=self._metadata(request_id, audio_model=audio_model),
            transcript=transcript,
            detected_language=detected_language,
            items=items,
        )

    async def _retrieve(
        self,
        query: str,
        embedding: list[float],
    ) -> list[dict[str, Any]]:
        primary = self.core.primary_search(query, limit=10)
        source = self.core.source_term_search(query, limit=10)
        semantic = await self.store.semantic_search(embedding=embedding, limit=20)
        fused: dict[str, dict[str, Any]] = {}

        def add(
            rows: list[dict[str, Any]],
            *,
            channel: str,
            weight: float,
        ) -> None:
            for rank, row in enumerate(rows, start=1):
                food_id = row.get("food_id")
                if not isinstance(food_id, str):
                    continue
                state = fused.setdefault(
                    food_id,
                    {
                        "score": 0.0,
                        "channels": [],
                        "matched_term": None,
                        "matched_term_type": None,
                    },
                )
                state["score"] += weight / (60 + rank)
                if channel not in state["channels"]:
                    state["channels"].append(channel)
                if channel == "source_term" and state["matched_term"] is None:
                    state["matched_term"] = row.get("matched_term")
                    state["matched_term_type"] = row.get("matched_term_type")

        add(primary, channel="primary", weight=1.0)
        add(source, channel="source_term", weight=0.9)
        add(semantic, channel="semantic", weight=0.8)
        ordered_ids = [
            food_id
            for food_id, _ in sorted(
                fused.items(),
                key=lambda item: (-item[1]["score"], item[0]),
            )[:12]
        ]
        hydrated = self.core.hydrate_candidates(ordered_ids)
        results: list[dict[str, Any]] = []
        for food_id in ordered_ids:
            food = hydrated.get(food_id)
            if food is None:
                continue
            state = fused[food_id]
            results.append(
                {
                    **food,
                    "matched_channels": state["channels"],
                    "matched_term": state["matched_term"],
                    "matched_term_type": state["matched_term_type"]
                    or ("semantic" if state["channels"] == ["semantic"] else "primary_name"),
                    "retrieval_score": state["score"],
                }
            )
        return results

    def manual_search_response(
        self,
        *,
        request_id: str,
        query: str,
        error_code: str,
        audio_model: str | None,
    ) -> ResolutionResponse:
        lexical = self.core.primary_search(query, limit=8) if query else []
        hydrated = self.core.hydrate_candidates(
            [row["food_id"] for row in lexical if isinstance(row.get("food_id"), str)]
        )
        candidates = [
            FoodCandidate(
                **hydrated[row["food_id"]],
                matched_channels=["primary"],
                matched_term=hydrated[row["food_id"]]["name"],
                matched_term_type="primary_name",
            )
            for row in lexical
            if row["food_id"] in hydrated
        ]
        return ResolutionResponse(
            status="manual_search",
            metadata=self._metadata(request_id, audio_model=audio_model),
            transcript="",
            detected_language="unknown",
            manual_search_query=query or None,
            manual_search_candidates=candidates,
            error_code=error_code,
        )

    def _build_item(
        self,
        *,
        concept_index: int,
        concept: ExtractedConcept,
        candidates: list[dict[str, Any]],
        decision: SelectorDecision | None,
        meal_default: str,
    ) -> ResolvedFoodItem:
        candidate_by_id = {candidate["food_id"]: candidate for candidate in candidates}
        allowed_ids = set(candidate_by_id)
        selected_id = decision.selected_food_id if decision else None
        invalid_selection = selected_id is not None and selected_id not in allowed_ids
        selected = None if invalid_selection else candidate_by_id.get(selected_id or "")
        alternative_ids = [
            food_id
            for food_id in (decision.alternative_food_ids if decision else [])
            if food_id in allowed_ids and food_id != selected_id
        ][:4]
        alternatives = [
            FoodCandidate.model_validate(candidate_by_id[food_id])
            for food_id in alternative_ids
        ]
        unresolved = list(decision.unresolved_fields if decision else ["food"])
        if invalid_selection or selected is None:
            unresolved.append("food")
        quantity = self._resolve_quantity(concept, selected)
        if quantity.status == "unresolved":
            unresolved.append("quantity")
        weight_basis = self._resolve_weight_basis(concept, selected)
        if weight_basis.status == "unresolved":
            unresolved.append("weight_basis")
        if selected and self._needs_preparation_confirmation(concept, selected):
            unresolved.append("preparation")
        is_unspecified = bool(
            selected
            and re.search(
                r"(?:\bNFS\b|\bNS\b|not specified)",
                selected["name"],
                re.IGNORECASE,
            )
        )
        if is_unspecified and any(
            not re.search(
                r"(?:\bNFS\b|\bNS\b|not specified)",
                alternative.name,
                re.IGNORECASE,
            )
            for alternative in alternatives
        ):
            unresolved.append("unspecified_food")
        unresolved = list(dict.fromkeys(unresolved))
        return ResolvedFoodItem(
            concept_index=concept_index,
            source_phrase=concept.source_phrase,
            selected_candidate=(
                FoodCandidate.model_validate(selected) if selected is not None else None
            ),
            alternatives=alternatives,
            confidence=decision.confidence if decision else 0,
            preparation=concept.preparation,
            weight_basis=weight_basis,
            quantity=quantity,
            meal_default=meal_default,
            unresolved_fields=unresolved,
            is_unspecified=is_unspecified,
            no_match_reason=(
                "Selector returned an ID outside the retrieved candidates"
                if invalid_selection
                else decision.no_match_reason if decision else "No selector decision"
            ),
        )

    @staticmethod
    def _resolve_quantity(
        concept: ExtractedConcept,
        selected: dict[str, Any] | None,
    ) -> QuantityResolution:
        value = concept.quantity.value
        unit = (concept.quantity.unit or "").strip().casefold()
        if value is None or not unit:
            return QuantityResolution(
                status="unresolved",
                spoken_value=value,
                spoken_unit=concept.quantity.unit,
            )
        if unit in GRAM_UNITS:
            return QuantityResolution(
                status="resolved",
                grams=value,
                spoken_value=value,
                spoken_unit=concept.quantity.unit,
            )
        if unit in KILOGRAM_UNITS:
            return QuantityResolution(
                status="resolved",
                grams=value * 1000,
                spoken_value=value,
                spoken_unit=concept.quantity.unit,
            )
        if selected:
            normalized_unit = unit.rstrip("s")
            matches = [
                portion
                for portion in selected.get("portions", [])
                if re.search(
                    rf"\b{re.escape(normalized_unit)}s?\b",
                    portion["description"],
                    re.IGNORECASE,
                )
            ]
            if len(matches) == 1:
                portion = matches[0]
                source_amount = portion.get("amount") or 1
                return QuantityResolution(
                    status="resolved",
                    grams=value * portion["gram_weight"] / source_amount,
                    spoken_value=value,
                    spoken_unit=concept.quantity.unit,
                    source_portion_id=portion["portion_id"],
                    source_portion_description=portion["description"],
                )
        return QuantityResolution(
            status="unresolved",
            spoken_value=value,
            spoken_unit=concept.quantity.unit,
        )

    @staticmethod
    def _resolve_weight_basis(
        concept: ExtractedConcept,
        selected: dict[str, Any] | None,
    ) -> WeightBasisResolution:
        if concept.weight_basis == "as_purchased":
            if selected and selected.get("has_usable_weight_factor"):
                return WeightBasisResolution(status="resolved", value="as_purchased")
            return WeightBasisResolution(status="unresolved")
        if concept.weight_basis == "edible":
            return WeightBasisResolution(status="resolved", value="edible")
        material = " ".join(
            [concept.source_phrase, selected["name"] if selected else ""]
        )
        if re.search(r"\b(bone|shell|pit|core|peel|kemik|kabuk)\b", material, re.IGNORECASE):
            return WeightBasisResolution(status="unresolved")
        return WeightBasisResolution(status="resolved", value="edible")

    @staticmethod
    def _needs_preparation_confirmation(
        concept: ExtractedConcept,
        selected: dict[str, Any],
    ) -> bool:
        selected_states = {
            match.casefold() for match in MATERIAL_STATE_RE.findall(selected["name"])
        }
        spoken_states = {value.casefold() for value in concept.preparation}
        return bool(selected_states and not selected_states & spoken_states)

    @staticmethod
    def _concept_from_text(query: str) -> ExtractedConcept:
        match = QUANTITY_RE.search(query)
        quantity = ExtractedQuantity()
        if match:
            quantity = ExtractedQuantity(
                value=float(match.group("value").replace(",", ".")),
                unit=match.group("unit"),
            )
        preparation = [
            word
            for word in PREPARATION_WORDS
            if re.search(rf"\b{re.escape(word)}\b", query, re.IGNORECASE)
        ]
        lowered = query.casefold()
        basis = None
        if any(value in lowered for value in ("as purchased", "satın alındığı")):
            basis = "as_purchased"
        elif any(value in lowered for value in ("edible", "yenilebilir")):
            basis = "edible"
        food_name = QUANTITY_RE.sub(" ", query)
        food_name = re.sub(r"\s+", " ", food_name).strip(" ,")
        return ExtractedConcept(
            source_phrase=query,
            food_name=food_name or query,
            quantity=quantity,
            preparation=preparation,
            weight_basis=basis,
        )

    @staticmethod
    def _text_language(query: str) -> str:
        return "tr" if re.search(r"[çğıöşüÇĞİÖŞÜ]", query) else "en"

    @staticmethod
    def meal_for(local_timestamp: str, timezone_name: str) -> str:
        try:
            timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            timezone = ZoneInfo("UTC")
        try:
            timestamp = datetime.fromisoformat(local_timestamp.replace("Z", "+00:00"))
        except ValueError:
            timestamp = datetime.now(timezone)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone)
        else:
            timestamp = timestamp.astimezone(timezone)
        hour = timestamp.hour
        if 4 <= hour <= 10:
            return "breakfast"
        if 11 <= hour <= 15:
            return "lunch"
        if 16 <= hour <= 21:
            return "dinner"
        return "snacks"

    def _metadata(self, request_id: str, *, audio_model: str | None) -> ResolutionMetadata:
        return ResolutionMetadata(
            request_id=request_id,
            core_version=self.settings.core_version,
            index_version=self.settings.index_version,
            audio_model=audio_model,
            selector_model=self.settings.gemini_selector_model,
            embedding_model=self.settings.gemini_embedding_model,
        )
