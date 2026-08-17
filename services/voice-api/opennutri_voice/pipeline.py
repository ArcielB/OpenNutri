from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Settings
from .core_repository import CoreFoodRepository
from .gemini import GeminiClient, GeminiError
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
from .supabase_store import SupabasePrivateStore, SupabaseStoreError


GRAM_UNITS = {"g", "gr", "gram", "grams", "gramme", "grammes"}
KILOGRAM_UNITS = {"kg", "kilogram", "kilograms", "kilo"}
GENERIC_COUNT_UNITS = {"piece", "item", "adet", "tane"}
NON_COUNT_INPUT_UNITS = {
    "bowl",
    "cup",
    "glass",
    "mug",
    "serving",
    "portion",
    "slice",
    "package",
    "packet",
    "can",
    "bottle",
    "jar",
    "kase",
    "bardak",
    "fincan",
    "porsiyon",
    "dilim",
    "paket",
    "kutu",
    "şişe",
    "kavanoz",
}
NON_ITEM_PORTION_RE = re.compile(
    r"\b(cups?|tbsp|tablespoons?|tsp|teaspoons?|fluid ounces?|fl oz|ounces?|oz|"
    r"grams?|kilograms?|kg|g|pounds?|lbs?|millilit(?:er|re)s?|ml|lit(?:er|re)s?|"
    r"packages?|packets?|containers?|cans?|bottles?|jars?|slices?|wedges?|"
    r"inches?|centimet(?:er|re)s?|cm|linear|servings?|quantity not specified)\b",
    re.IGNORECASE,
)
WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
SPECIFIC_COOKING_STATES = {
    "boiled",
    "fried",
    "baked",
    "roasted",
    "grilled",
}
PORTION_SIZE_WORDS = {"small", "medium", "large", "extra", "thin", "thick", "regular"}
COOKING_STATE_WORDS = {"raw", "cooked", *SPECIFIC_COOKING_STATES}
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
LEXICAL_MATERIAL_WORDS = {
    *PREPARATION_WORDS,
    "dry",
    "uncooked",
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
AS_PURCHASED_RE = re.compile(
    r"\b(as[ -]?purchased|satın alındığı(?: haliyle)?|satın alınan(?: haliyle)?)\b",
    re.IGNORECASE,
)
SEHRIYE_ALIAS_RE = re.compile(
    r"\b(?:tel\s+|arpa\s+)?(?:sehriye|sehirye|sehir\s+ye|sehiriye|sehrie|shehriye)\b"
)
DRY_PASTA_WORDS = {"raw", "dry", "uncooked", "cig"}
COOKED_PASTA_WORDS = {
    "cooked",
    "boiled",
    "pismis",
    "pisirilmis",
    "haslanmis",
}


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
            audio_model=(
                extraction.transcription_model or self.settings.gemini_audio_model
            ),
            transcription_fallback_used=extraction.transcription_fallback_used,
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
            transcription_fallback_used=False,
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
        transcription_fallback_used: bool = False,
    ) -> ResolutionResponse:
        # Exact lexical matches take a deterministic fast path. A single batched
        # translation/synonym pass repairs concepts with no lexical candidates
        # before the private semantic index is consulted.
        working_concepts = list(concepts)
        candidate_sets = [
            await self._retrieve(self._food_search_query(concept))
            for concept in working_concepts
        ]
        repaired_indices: set[int] = set()
        repair_indices = [
            index
            for index, (concept, candidates) in enumerate(
                zip(working_concepts, candidate_sets)
            )
            if not self._has_viable_lexical_candidate(concept, candidates)
        ]
        if repair_indices:
            for index in repair_indices:
                candidate_sets[index] = []
            try:
                rewrites = await self.gemini.normalize_search_queries(
                    [working_concepts[index] for index in repair_indices]
                )
            except GeminiError:
                rewrites = None
            if rewrites is not None:
                rewrite_by_index = {
                    rewrite.concept_index: rewrite.search_query.strip()
                    for rewrite in rewrites.rewrites
                    if 0 <= rewrite.concept_index < len(repair_indices)
                    and rewrite.search_query.strip()
                }
                for local_index, search_query in rewrite_by_index.items():
                    original_index = repair_indices[local_index]
                    working_concepts[original_index] = working_concepts[
                        original_index
                    ].model_copy(update={"food_name": search_query})
                    repaired_indices.add(original_index)
                    repaired_candidates = await self._retrieve(
                        self._food_search_query(working_concepts[original_index])
                    )
                    if self._has_viable_lexical_candidate(
                        working_concepts[original_index],
                        repaired_candidates,
                    ):
                        candidate_sets[original_index] = repaired_candidates

        decisions: dict[int, SelectorDecision] = {}
        pending = []
        for index, (concept, candidates) in enumerate(
            zip(working_concepts, candidate_sets)
        ):
            decision = self._deterministic_decision(concept, candidates)
            if decision is None:
                pending.append(index)
            else:
                decisions[index] = decision

        if pending:
            semantic_indices = [
                index for index in pending if not candidate_sets[index]
            ]
            if semantic_indices:
                semantic_concepts = [
                    working_concepts[index] for index in semantic_indices
                ]
                vectors = await self.gemini.embed_concepts(semantic_concepts)
                for index, vector in zip(semantic_indices, vectors, strict=True):
                    candidate_sets[index] = await self._retrieve(
                        self._food_search_query(working_concepts[index]),
                        vector,
                    )

            selector_indices = []
            for index in pending:
                decision = self._deterministic_decision(
                    working_concepts[index],
                    candidate_sets[index],
                )
                if decision is None:
                    selector_indices.append(index)
                else:
                    decisions[index] = decision

            if selector_indices:
                selector = await self.gemini.select_candidates(
                    concepts=[
                        working_concepts[index] for index in selector_indices
                    ],
                    candidate_sets=[candidate_sets[index] for index in selector_indices],
                )
                for decision in selector.decisions:
                    if 0 <= decision.concept_index < len(selector_indices):
                        original_index = selector_indices[decision.concept_index]
                        decisions[original_index] = decision.model_copy(
                            update={"concept_index": original_index}
                        )
        fallback_meal = self.meal_for(local_timestamp, timezone_name)
        items = [
            self._build_item(
                concept_index=index,
                concept=concept,
                candidates=candidate_sets[index],
                decision=decisions.get(index),
                meal_default=concept.meal or fallback_meal,
                transcription_fallback_used=transcription_fallback_used,
                query_repaired=index in repaired_indices,
            )
            for index, concept in enumerate(working_concepts)
        ]
        return ResolutionResponse(
            status="resolved",
            metadata=self._metadata(
                request_id,
                audio_model=audio_model,
                transcription_fallback_used=transcription_fallback_used,
            ),
            transcript=transcript,
            detected_language=detected_language,
            items=items,
        )

    async def _retrieve(
        self,
        query: str,
        embedding: list[float] | None = None,
    ) -> list[dict[str, Any]]:
        primary = self.core.primary_search(query, limit=10)
        source = self.core.source_term_search(query, limit=10)
        semantic: list[dict[str, Any]] = []
        if embedding is not None:
            try:
                semantic = await self.store.semantic_search(embedding=embedding, limit=20)
            except SupabaseStoreError:
                # The local lexical index remains useful when the private vector
                # index is temporarily unavailable.
                semantic = []
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
                        "primary_match_tier": None,
                        "source_term_exact": False,
                    },
                )
                bonus = 0.0
                if channel == "primary":
                    tier = int(row.get("match_tier", 2))
                    previous_tier = state["primary_match_tier"]
                    state["primary_match_tier"] = (
                        tier if previous_tier is None else min(previous_tier, tier)
                    )
                    query_signature = self._lexical_signature(query)
                    display_signature = self._lexical_signature(
                        str(row.get("display_name") or "")
                    )
                    if query_signature and query_signature == display_signature:
                        bonus = 8.0
                    else:
                        query_tokens = set(query_signature)
                        display_tokens = set(display_signature)
                        subset_bonus = (
                            2.0 / (1 + len(display_tokens - query_tokens))
                            if query_tokens and query_tokens.issubset(display_tokens)
                            else 0.0
                        )
                        head_bonus = (
                            4.0
                            if self._candidate_head_matches_query(
                                query,
                                str(row.get("display_name") or ""),
                            )
                            else 0.0
                        )
                        bonus = {0: 6.0, 1: 3.0, 2: 1.0}[tier]
                        bonus += subset_bonus + head_bonus
                elif channel == "source_term":
                    term = str(row.get("matched_term") or "")
                    exact = self._normalized_text(term) == self._normalized_text(query)
                    term_type = row.get("matched_term_type")
                    if exact and not state["source_term_exact"]:
                        state["matched_term"] = row.get("matched_term")
                        state["matched_term_type"] = term_type
                    state["source_term_exact"] = state["source_term_exact"] or exact
                    bonus = {
                        "common_name": 4.0 if exact else 0.4,
                        "foodon_label": 3.5 if exact else 0.25,
                        "additional_description": 1.0 if exact else 0.05,
                    }.get(term_type, 0.05)
                elif channel == "semantic":
                    bonus = float(row.get("similarity") or 0) * 0.5
                state["score"] += bonus + weight / (60 + rank)
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
                    "primary_match_tier": state["primary_match_tier"],
                    "source_term_exact": state["source_term_exact"],
                    "retrieval_score": state["score"],
                }
            )
        return results

    def _deterministic_decision(
        self,
        concept: ExtractedConcept,
        candidates: list[dict[str, Any]],
    ) -> SelectorDecision | None:
        if not candidates:
            return None
        selected = candidates[0]
        if re.search(
            r"(?:\bNFS\b|\bNS\b|not specified)",
            selected["name"],
            re.IGNORECASE,
        ):
            return None
        search_query = self._food_search_query(concept)
        direct_primary = selected.get("primary_match_tier") == 0
        same_signature = self._lexical_signature(
            search_query
        ) == self._lexical_signature(selected["name"])
        exact_alias = bool(
            selected.get("source_term_exact")
            and selected.get("matched_term_type") in {"common_name", "foodon_label"}
        )
        query_tokens = set(self._lexical_signature(search_query))
        selected_tokens = set(self._lexical_signature(selected["name"]))
        strong_head_match = bool(
            query_tokens
            and query_tokens.issubset(selected_tokens)
            and self._candidate_head_matches_query(
                search_query,
                selected["name"],
            )
        )
        if not (direct_primary or same_signature or exact_alias or strong_head_match):
            return None
        relies_on_head_match = strong_head_match and not (
            direct_primary or same_signature or exact_alias
        )
        if self._needs_preparation_confirmation(concept, selected):
            return None

        for candidate in candidates[1:]:
            competing_direct = candidate.get("primary_match_tier") == 0
            competing_alias = bool(
                candidate.get("source_term_exact")
                and candidate.get("matched_term_type") in {"common_name", "foodon_label"}
            )
            if competing_direct or competing_alias:
                return None
            candidate_tokens = set(self._lexical_signature(candidate["name"]))
            if (
                relies_on_head_match
                and query_tokens.issubset(candidate_tokens)
                and self._candidate_head_matches_query(
                    search_query,
                    candidate["name"],
                )
            ):
                return None
        return SelectorDecision(
            concept_index=0,
            selected_food_id=selected["food_id"],
            confidence=0.99,
        )

    @classmethod
    def _has_viable_lexical_candidate(
        cls,
        concept: ExtractedConcept,
        candidates: list[dict[str, Any]],
    ) -> bool:
        search_query = cls._food_search_query(concept)
        query_tokens = set(cls._lexical_signature(search_query))
        query_material = query_tokens.intersection(LEXICAL_MATERIAL_WORDS)
        for candidate in candidates:
            if candidate.get("source_term_exact"):
                return True
            candidate_tokens = set(cls._lexical_signature(candidate["name"]))
            candidate_material = candidate_tokens.intersection(
                LEXICAL_MATERIAL_WORDS
            )
            if query_material and not query_material.intersection(candidate_material):
                continue
            if candidate.get("primary_match_tier") in {0, 1}:
                return True
            if query_tokens and query_tokens.issubset(candidate_tokens):
                return True
            if cls._candidate_head_matches_query(search_query, candidate["name"]):
                return True
        return False

    @classmethod
    def _food_search_query(cls, concept: ExtractedConcept) -> str:
        alias_material = " ".join(
            [concept.source_phrase, concept.food_name, *concept.preparation]
        )
        alias_text = cls._ascii_search_text(alias_material)
        if SEHRIYE_ALIAS_RE.search(alias_text):
            alias_words = set(WORD_RE.findall(alias_text))
            if alias_words.intersection(COOKED_PASTA_WORDS):
                return "pasta cooked"
            if alias_words.intersection(DRY_PASTA_WORDS):
                return "pasta dry enriched"
            return "pasta"
        words = WORD_RE.findall(
            unicodedata.normalize("NFKC", concept.food_name)
        )
        filtered = [
            word for word in words if word.casefold() not in PORTION_SIZE_WORDS
        ]
        return " ".join(filtered).strip() or concept.food_name

    @staticmethod
    def _ascii_search_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value).casefold()
        return "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )

    @classmethod
    def _uses_curated_food_alias(cls, concept: ExtractedConcept) -> bool:
        material = " ".join(
            [concept.source_phrase, concept.food_name, *concept.preparation]
        )
        return bool(SEHRIYE_ALIAS_RE.search(cls._ascii_search_text(material)))

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
        transcription_fallback_used: bool = False,
        query_repaired: bool = False,
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
        unresolved = [
            field
            for field in (decision.unresolved_fields if decision else ["food"])
            if field not in {"quantity", "weight_basis"}
        ]
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
        if selected and (
            query_repaired or self._uses_curated_food_alias(concept)
        ):
            unresolved.append("food")
        if transcription_fallback_used:
            unresolved.append("transcription")
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
        confidence = decision.confidence if decision else 0
        auto_log_eligible = bool(
            selected is not None
            and confidence >= 0.92
            and not alternatives
            and not unresolved
            and not is_unspecified
            and quantity.status == "resolved"
            and weight_basis.status == "resolved"
            and self._has_trusted_lexical_evidence(concept, selected)
        )
        return ResolvedFoodItem(
            concept_index=concept_index,
            source_phrase=concept.source_phrase,
            selected_candidate=(
                FoodCandidate.model_validate(selected) if selected is not None else None
            ),
            alternatives=alternatives,
            confidence=confidence,
            preparation=concept.preparation,
            weight_basis=weight_basis,
            quantity=quantity,
            meal_default=meal_default,
            unresolved_fields=unresolved,
            is_unspecified=is_unspecified,
            auto_log_eligible=auto_log_eligible,
            no_match_reason=(
                "Selector returned an ID outside the retrieved candidates"
                if invalid_selection
                else decision.no_match_reason if decision else "No selector decision"
            ),
        )

    @classmethod
    def _resolve_quantity(
        cls,
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
            spoken_size_words = PORTION_SIZE_WORDS.intersection(
                cls._lexical_signature(
                    f"{concept.source_phrase} {concept.food_name}"
                )
            )
            if spoken_size_words:
                size_matches = [
                    portion
                    for portion in selected.get("portions", [])
                    if PORTION_SIZE_WORDS.intersection(
                        cls._lexical_signature(portion["description"])
                    )
                    == spoken_size_words
                ]
                if len(size_matches) == 1:
                    portion = size_matches[0]
                    source_amount = portion.get("amount") or 1
                    return QuantityResolution(
                        status="resolved",
                        grams=value * portion["gram_weight"] / source_amount,
                        spoken_value=value,
                        spoken_unit=concept.quantity.unit,
                        source_portion_id=portion["portion_id"],
                        source_portion_description=portion["description"],
                    )
            if cls._is_food_count_unit(unit, concept):
                item_portions = [
                    portion
                    for portion in selected.get("portions", [])
                    if (portion.get("amount") or 1) == 1
                    and not NON_ITEM_PORTION_RE.search(portion["description"])
                ]
                if len(item_portions) == 1:
                    portion = item_portions[0]
                    return QuantityResolution(
                        status="resolved",
                        grams=value * portion["gram_weight"],
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
        if concept.weight_basis == "as_purchased" and AS_PURCHASED_RE.search(
            concept.source_phrase
        ):
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
        spoken_material = " ".join(
            [concept.source_phrase, concept.food_name, *concept.preparation]
        )
        spoken_states = {
            match.casefold() for match in MATERIAL_STATE_RE.findall(spoken_material)
        }
        if not selected_states:
            return False

        selected_cooking = selected_states & COOKING_STATE_WORDS
        spoken_cooking = spoken_states & COOKING_STATE_WORDS
        if "raw" in selected_cooking and "raw" not in spoken_cooking:
            return True
        selected_specific_cooking = selected_cooking & SPECIFIC_COOKING_STATES
        if selected_specific_cooking:
            if not selected_specific_cooking & spoken_cooking:
                return True
        elif selected_cooking == {"cooked"} and not (
            spoken_cooking - {"raw"}
        ):
            return True

        for family in (
            {"drained"},
            {"skin", "skinless"},
            {"bone", "boneless"},
        ):
            selected_family = selected_states & family
            if selected_family and not selected_family & spoken_states:
                return True
        return False

    @classmethod
    def _has_trusted_lexical_evidence(
        cls,
        concept: ExtractedConcept,
        selected: dict[str, Any],
    ) -> bool:
        if "primary" in selected.get("matched_channels", []):
            query_tokens = set(
                cls._lexical_signature(cls._food_search_query(concept))
            )
            selected_tokens = set(cls._lexical_signature(selected["name"]))
            if query_tokens and query_tokens.issubset(selected_tokens):
                return True
        return bool(
            selected.get("source_term_exact")
            and selected.get("matched_term_type") in {"common_name", "foodon_label"}
        )

    @classmethod
    def _is_food_count_unit(cls, unit: str, concept: ExtractedConcept) -> bool:
        normalized_unit = cls._singular_token(unit)
        unit_tokens = set(cls._lexical_signature(unit))
        if normalized_unit in GENERIC_COUNT_UNITS:
            return True
        if normalized_unit in NON_COUNT_INPUT_UNITS or unit_tokens.intersection(
            NON_COUNT_INPUT_UNITS
        ):
            return False
        food_tokens = set(cls._lexical_signature(cls._food_search_query(concept)))
        if normalized_unit in food_tokens or unit_tokens.intersection(food_tokens):
            return True
        # The extractor is instructed to translate count nouns to English, but
        # structured models can occasionally preserve the spoken Turkish noun
        # (for example, `yumurta`). It is still a count when the unit is a word
        # copied from the source phrase and is not a measurement/container.
        source_tokens = {
            cls._singular_token(token)
            for token in WORD_RE.findall(
                unicodedata.normalize("NFKC", concept.source_phrase).casefold()
            )
        }
        return normalized_unit in source_tokens

    @staticmethod
    def _normalized_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).casefold()
        return " ".join(WORD_RE.findall(normalized))

    @classmethod
    def _candidate_head_matches_query(cls, query: str, candidate_name: str) -> bool:
        query_tokens = set(cls._lexical_signature(query))
        candidate_tokens = WORD_RE.findall(
            unicodedata.normalize("NFKC", candidate_name).casefold()
        )
        if not candidate_tokens:
            return False
        return cls._singular_token(candidate_tokens[0]) in query_tokens

    @staticmethod
    def _singular_token(token: str) -> str:
        if token.endswith("ies") and len(token) > 3:
            return f"{token[:-3]}y"
        if token.endswith("s") and not token.endswith("ss") and len(token) > 2:
            return token[:-1]
        return token

    @classmethod
    def _lexical_signature(cls, value: str) -> tuple[str, ...]:
        tokens = [
            cls._singular_token(token)
            for token in WORD_RE.findall(
                unicodedata.normalize("NFKC", value).casefold()
            )
        ]
        if SPECIFIC_COOKING_STATES.intersection(tokens):
            tokens = [token for token in tokens if token != "cooked"]
        return tuple(sorted(dict.fromkeys(tokens)))

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

    def _metadata(
        self,
        request_id: str,
        *,
        audio_model: str | None,
        transcription_fallback_used: bool = False,
    ) -> ResolutionMetadata:
        return ResolutionMetadata(
            request_id=request_id,
            core_version=self.settings.core_version,
            index_version=self.settings.index_version,
            audio_model=audio_model,
            transcription_fallback_used=transcription_fallback_used,
            extraction_model=(
                self.settings.gemini_extraction_model if audio_model is not None else None
            ),
            selector_model=self.settings.gemini_selector_model,
            embedding_model=self.settings.gemini_embedding_model,
        )
