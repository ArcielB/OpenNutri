from __future__ import annotations

import base64
import json
import logging
from typing import Any

import httpx

from .config import Settings
from .models import (
    AudioExtraction,
    AudioTranscript,
    ConceptExtraction,
    CoachModelOutput,
    CoachRequest,
    CoachVoiceModelOutput,
    ExtractedConcept,
    SearchQueryRewriteOutput,
    SelectorOutput,
)


logger = logging.getLogger(__name__)


class GeminiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        is_rate_limited: bool = False,
        is_retryable: bool = False,
        retry_after_seconds: float | None = None,
        error_code: str = "gemini_unavailable",
        partial_transcript: str | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.is_rate_limited = is_rate_limited
        self.is_retryable = is_retryable
        self.retry_after_seconds = retry_after_seconds
        self.error_code = error_code
        self.partial_transcript = partial_transcript
        self.http_status = http_status


class GeminiClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.AsyncClient(
            timeout=settings.gemini_request_timeout_seconds
        )
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    @property
    def _headers(self) -> dict[str, str]:
        if not self.settings.gemini_api_key:
            raise GeminiError(
                "Gemini is not configured",
                error_code="gemini_configuration_error",
            )
        return {
            "x-goog-api-key": self.settings.gemini_api_key,
            "content-type": "application/json",
        }

    async def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self.client.post(url, headers=self._headers, json=payload)
            response.raise_for_status()
            result = response.json()
        except httpx.HTTPStatusError as exc:
            retry_after: float | None = None
            if exc.response.status_code == 429:
                try:
                    retry_after = float(exc.response.headers.get("retry-after", ""))
                except ValueError:
                    retry_after = None
                raise GeminiError(
                    "Gemini rate limit reached",
                    is_rate_limited=True,
                    is_retryable=True,
                    retry_after_seconds=retry_after,
                    error_code="gemini_rate_limited",
                    http_status=exc.response.status_code,
                ) from exc
            if exc.response.status_code >= 500:
                raise GeminiError(
                    "Gemini is temporarily unavailable",
                    is_retryable=True,
                    error_code="gemini_unavailable",
                    http_status=exc.response.status_code,
                ) from exc
            raise GeminiError(
                "Gemini request failed",
                error_code="gemini_request_rejected",
                http_status=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise GeminiError(
                "Gemini is temporarily unavailable",
                is_retryable=True,
                error_code="gemini_unavailable",
            ) from exc
        except ValueError as exc:
            raise GeminiError(
                "Gemini returned an invalid response",
                is_retryable=True,
                error_code="gemini_invalid_output",
            ) from exc
        if not isinstance(result, dict):
            raise GeminiError(
                "Gemini returned an invalid payload",
                is_retryable=True,
                error_code="gemini_invalid_output",
            )
        return result

    @staticmethod
    def _json_text(payload: dict[str, Any]) -> Any:
        try:
            parts = payload["candidates"][0]["content"]["parts"]
            text = "".join(
                part.get("text", "")
                for part in parts
                if isinstance(part, dict)
                and isinstance(part.get("text", ""), str)
            ).strip()
            if text.startswith("```"):
                first_newline = text.find("\n")
                if first_newline != -1:
                    text = text[first_newline + 1 :]
                if text.endswith("```"):
                    text = text[:-3].rstrip()
            return json.loads(text)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise GeminiError(
                "Gemini returned invalid structured output",
                is_retryable=True,
                error_code="gemini_invalid_output",
            ) from exc

    @staticmethod
    def _thinking_level(model: str) -> str:
        # Gemini 3.7/3.8 reject `minimal`; their lowest supported setting is `low`.
        if model.startswith(("gemini-3.7-", "gemini-3.8-")):
            return "low"
        return "minimal"

    @staticmethod
    def _partial_transcript(payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        transcript = payload.get("transcript")
        if not isinstance(transcript, str):
            return None
        transcript = transcript.strip()
        return transcript[:1000] or None

    async def generate_coach_response(self, request: CoachRequest) -> CoachModelOutput:
        model = self.settings.gemini_coach_model
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are OpenNutri Coach, a concise, supportive food coach. Use only "
                            "the profile, diary totals, FDA adult Daily Value targets, and foods "
                            "provided by the user. A one-day diary can be incomplete: describe "
                            "opportunities, never diagnose deficiencies or promise health outcomes. "
                            "Respect every diet note, allergy, avoidance, and explicit preference. "
                            "For daily mode, give one useful insight and up to three concrete actions. "
                            "For oracle mode, return four to six diverse food actions ranked for the "
                            "largest stated nutrient/goal opportunities; every action must include a "
                            "short, conventional English food search_query suitable for a USDA food "
                            "database. Never invent nutrient measurements. For diet_plan mode, explain "
                            "a practical day structure compatible with the selected diet. For chat "
                            "mode, answer the message directly. memory_updates are allowed only in "
                            "chat mode and only for durable facts the user explicitly stated about "
                            "their goal, preference, avoidance, allergy, schedule, or context. Do not "
                            "infer sensitive or medical facts. Write in the requested locale when "
                            "possible, but keep oracle search_query values in English. Keep the tone "
                            "specific and calm, not preachy. Mention professional care only when the "
                            "user raises a medical condition, pregnancy, eating disorder, medication, "
                            "or other clinical issue."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": request.model_dump_json(
                                exclude_none=True,
                                exclude_defaults=False,
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "thinkingConfig": {"thinkingLevel": self._thinking_level(model)},
                "responseMimeType": "application/json",
                "responseJsonSchema": CoachModelOutput.model_json_schema(),
            },
        }
        response = await self._post(f"{self.base_url}/{model}:generateContent", payload)
        structured = self._json_text(response)
        try:
            return CoachModelOutput.model_validate(structured)
        except ValueError as exc:
            raise GeminiError(
                "Coach output did not match the contract",
                is_retryable=True,
                error_code="gemini_invalid_output",
            ) from exc

    async def generate_coach_voice_response(
        self,
        *,
        wav_bytes: bytes,
        language_hint: str,
        request: CoachRequest,
    ) -> CoachVoiceModelOutput:
        model = self.settings.gemini_coach_model
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are OpenNutri Coach. First transcribe the user's spoken message "
                            "literally in its original language. Then answer it as a concise, "
                            "supportive food coach using only the supplied profile and diary. A "
                            "one-day diary can be incomplete: never diagnose a deficiency or promise "
                            "a health outcome. Respect every explicit avoidance. memory_updates may "
                            "contain only durable goal, preference, avoidance/allergy, schedule, or "
                            "context facts explicitly spoken in this recording; never infer sensitive "
                            "or medical facts. Never store or request a name. Write the response in the "
                            "user's language when possible. This is general food guidance, not medical "
                            "care. Mention professional care only for clinical issues."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                f"Language hint: {language_hint}. Context: "
                                + request.model_dump_json(exclude_none=True)
                            )
                        },
                        {
                            "inlineData": {
                                "mimeType": "audio/wav",
                                "data": base64.b64encode(wav_bytes).decode("ascii"),
                            }
                        },
                    ],
                }
            ],
            "generationConfig": {
                "thinkingConfig": {"thinkingLevel": self._thinking_level(model)},
                "responseMimeType": "application/json",
                "responseJsonSchema": CoachVoiceModelOutput.model_json_schema(),
            },
        }
        response = await self._post(f"{self.base_url}/{model}:generateContent", payload)
        structured = self._json_text(response)
        try:
            return CoachVoiceModelOutput.model_validate(structured)
        except ValueError as exc:
            raise GeminiError(
                "Coach voice output did not match the contract",
                is_retryable=True,
                error_code="gemini_invalid_output",
                partial_transcript=self._partial_transcript(structured),
            ) from exc

    async def transcribe_and_extract(
        self,
        *,
        wav_bytes: bytes,
        language_hint: str,
    ) -> AudioExtraction:
        default_model = self.settings.gemini_audio_model
        transcription_model = self.settings.audio_model_for_language(language_hint)
        fallback_used = False
        try:
            extraction = await self._extract_audio_once(
                wav_bytes=wav_bytes,
                language_hint=language_hint,
                model=transcription_model,
            )
        except GeminiError as exc:
            logger.warning(
                "gemini_voice_attempt_failed model=%s code=%s retryable=%s status=%s",
                transcription_model,
                exc.error_code,
                exc.is_retryable,
                exc.http_status,
            )
            fallback_model = self.settings.gemini_audio_fallback_model
            if fallback_model == transcription_model and default_model != fallback_model:
                fallback_model = default_model
            if (
                not fallback_model
                or fallback_model == transcription_model
                or not exc.is_retryable
            ):
                raise
            try:
                extraction = await self._extract_audio_once(
                    wav_bytes=wav_bytes,
                    language_hint=language_hint,
                    model=fallback_model,
                )
            except GeminiError as fallback_exc:
                if fallback_exc.partial_transcript is None:
                    fallback_exc.partial_transcript = exc.partial_transcript
                logger.warning(
                    "gemini_voice_fallback_failed model=%s code=%s "
                    "retryable=%s status=%s partial_transcript=%s",
                    fallback_model,
                    fallback_exc.error_code,
                    fallback_exc.is_retryable,
                    fallback_exc.http_status,
                    fallback_exc.partial_transcript is not None,
                )
                raise
            transcription_model = fallback_model
            fallback_used = True
        return extraction.model_copy(
            update={
                "transcription_model": transcription_model,
                "transcription_fallback_used": fallback_used,
            }
        )

    async def _extract_audio_once(
        self,
        *,
        wav_bytes: bytes,
        language_hint: str,
        model: str,
    ) -> AudioExtraction:
        """Transcribe and structure one recording in a single model request.

        The older pipeline made a second text-model request after transcription.
        Keeping both jobs in one constrained response removes a full provider
        round trip while the literal transcript remains available for review.
        """
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are a literal food-diary transcription and extraction engine. "
                            "First transcribe only what is audibly spoken, in the original "
                            "language. Preserve every number, food word, unit, preparation, and "
                            "meal label exactly in transcript. Do not correct, summarize, or add "
                            "words to transcript. Then extract at most ten distinct food concepts "
                            "from that exact transcript. source_phrase must be an exact contiguous "
                            "phrase from transcript. food_name must be a concise English database-"
                            "search query that preserves the food variant and raw/cooked/drained/"
                            "skin/bone preparation. Copy every quantity exactly. Express its unit "
                            "as a canonical English unit; for counted foods use the singular food "
                            "noun, for example ten eggs is value 10 and unit egg, and iki yumurta "
                            "is value 2 and unit egg. Never invent a quantity, unit, preparation, "
                            "weight basis, food, or recipe decomposition. Raw or uncooked never "
                            "means as-purchased; set weight_basis only when the speaker literally "
                            "says edible weight, as purchased, yenilebilir ağırlık, or satın "
                            "alındığı haliyle. Set meal only when the speaker explicitly groups "
                            "the food under breakfast, lunch, dinner, or snacks; otherwise return "
                            "null. English and Turkish are supported. Preserve Turkish food words "
                            "literally in transcript and source_phrase, including şehriye, tel "
                            "şehriye, arpa şehriye, katı pişmiş, and bütün yumurta, while food_name "
                            "uses the conventional English food equivalent."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                f"Language hint: {language_hint or 'auto'}. Return the literal "
                                "transcript and its structured food concepts."
                            )
                        },
                        {
                            "inlineData": {
                                "mimeType": "audio/wav",
                                "data": base64.b64encode(wav_bytes).decode("ascii"),
                            }
                        },
                    ],
                }
            ],
            "generationConfig": {
                "thinkingConfig": {"thinkingLevel": self._thinking_level(model)},
                "responseMimeType": "application/json",
                "responseJsonSchema": AudioExtraction.model_json_schema(),
            },
        }
        response = await self._post(
            f"{self.base_url}/{model}:generateContent",
            payload,
        )
        structured = self._json_text(response)
        try:
            return AudioExtraction.model_validate(structured)
        except ValueError as exc:
            raise GeminiError(
                "Audio extraction did not match the contract",
                is_retryable=True,
                error_code="gemini_invalid_output",
                partial_transcript=self._partial_transcript(structured),
            ) from exc

    async def transcribe_audio(
        self,
        *,
        wav_bytes: bytes,
        language_hint: str,
        model: str | None = None,
    ) -> AudioTranscript:
        schema = AudioTranscript.model_json_schema()
        resolved_model = model or self.settings.gemini_audio_model
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are a literal food-diary transcription engine. Transcribe "
                            "only what is audibly spoken, in the original language. Preserve "
                            "every number, food word, unit, preparation, and meal label exactly. "
                            "Do not correct, translate, summarize, interpret, or add words. "
                            "This recording is about foods, so distinguish food words such as "
                            "eggs from letter names such as X only according to the audio. "
                            "For Turkish, preserve phrases such as 'katı pişmiş' and 'bütün "
                            "yumurta' literally. Preserve food names such as 'şehriye', 'tel "
                            "şehriye', and 'arpa şehriye' literally; do not replace them with "
                            "paraphrases."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                f"Language hint: {language_hint or 'auto'}. "
                                "Return the exact transcript."
                            )
                        },
                        {
                            "inlineData": {
                                "mimeType": "audio/wav",
                                "data": base64.b64encode(wav_bytes).decode("ascii"),
                            }
                        },
                    ],
                }
            ],
            "generationConfig": {
                "thinkingConfig": {
                    "thinkingLevel": self._thinking_level(resolved_model)
                },
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
            },
        }
        response = await self._post(
            f"{self.base_url}/{resolved_model}:generateContent",
            payload,
        )
        structured = self._json_text(response)
        try:
            return AudioTranscript.model_validate(structured)
        except ValueError as exc:
            raise GeminiError(
                "Audio transcription did not match the contract",
                is_retryable=True,
                error_code="gemini_invalid_output",
                partial_transcript=self._partial_transcript(structured),
            ) from exc

    async def extract_concepts(
        self,
        *,
        transcript: str,
        detected_language: str,
    ) -> ConceptExtraction:
        schema = ConceptExtraction.model_json_schema()
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "Extract at most ten distinct food concepts from an already literal "
                            "food-diary transcript. Never alter or reinterpret the transcript. "
                            "source_phrase must be an exact contiguous phrase from it. food_name "
                            "must be a concise English database-search query that preserves the "
                            "food variant and raw/cooked/drained/skin/bone preparation. Copy every "
                            "quantity exactly. Express its unit as a canonical English unit; for "
                            "counted foods use the singular food noun (for example, 'ten eggs' is "
                            "value 10 and unit 'egg', and 'iki yumurta' is value 2 and unit "
                            "'egg', never 'yumurta'). Never invent a quantity, unit, preparation, "
                            "weight basis, food, or recipe decomposition. Raw or uncooked never "
                            "means as-purchased; set weight_basis only when the speaker literally "
                            "says edible weight, as purchased, yenilebilir ağırlık, or satın "
                            "alındığı haliyle. Set meal only when the "
                            "speaker explicitly groups the food under breakfast, lunch, dinner, "
                            "or snacks; otherwise return null. English and Turkish are supported. "
                            "The source_phrase and food_name have different jobs: source_phrase "
                            "stays exact, while food_name must translate any Turkish food words "
                            "to English. Examples: 'çiğ makarna' becomes food_name 'raw pasta'; "
                            "'pişmiş pirinç' becomes 'cooked rice'; 'ızgara tavuk göğsü' becomes "
                            "'grilled chicken breast'; and şehriye, tel şehriye, or arpa şehriye "
                            "becomes 'pasta'. Never copy a Turkish food name into food_name when "
                            "an English equivalent exists."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "detected_language": detected_language,
                                    "literal_transcript": transcript,
                                },
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "thinkingConfig": {
                    "thinkingLevel": self._thinking_level(
                        self.settings.gemini_extraction_model
                    )
                },
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
            },
        }
        response = await self._post(
            f"{self.base_url}/{self.settings.gemini_extraction_model}:generateContent",
            payload,
        )
        try:
            return ConceptExtraction.model_validate(self._json_text(response))
        except ValueError as exc:
            raise GeminiError(
                "Concept extraction did not match the contract",
                is_retryable=True,
                error_code="gemini_invalid_output",
            ) from exc

    async def normalize_search_queries(
        self,
        concepts: list[ExtractedConcept],
    ) -> SearchQueryRewriteOutput:
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "Convert each difficult food phrase into one concise English USDA/Core "
                            "database search query. Return exactly one rewrite for every supplied "
                            "concept_index. Translate Turkish or other languages, expand a common "
                            "colloquial food name, or correct an obvious food spelling variation. "
                            "Remove quantities from search_query, but preserve every explicitly "
                            "spoken food variant and raw/cooked/boiled/fried/grilled/drained/skin/"
                            "bone state. Do not add an unspoken ingredient, preparation, brand, "
                            "food variant, or weight basis. Never decompose a dish or recipe into "
                            "ingredients. Use conventional database state words when equivalent: "
                            "uncooked pasta is 'pasta dry', not 'raw pasta'. Examples: çiğ "
                            "makarna -> pasta dry; pişmiş pirinç -> "
                            "cooked rice; ızgara tavuk göğsü -> grilled chicken breast; tel "
                            "şehriye -> pasta; PB and J sandwich -> peanut butter and jelly "
                            "sandwich. If a proper food name has no translation, transliterate it "
                            "without guessing what it contains."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "concepts": [
                                        {
                                            "concept_index": index,
                                            "source_phrase": concept.source_phrase,
                                            "food_name": concept.food_name,
                                            "preparation": concept.preparation,
                                            "weight_basis": concept.weight_basis,
                                        }
                                        for index, concept in enumerate(concepts)
                                    ]
                                },
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "thinkingConfig": {
                    "thinkingLevel": self._thinking_level(
                        self.settings.gemini_extraction_model
                    )
                },
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseJsonSchema": SearchQueryRewriteOutput.model_json_schema(),
            },
        }
        response = await self._post(
            f"{self.base_url}/{self.settings.gemini_extraction_model}:generateContent",
            payload,
        )
        try:
            return SearchQueryRewriteOutput.model_validate(self._json_text(response))
        except ValueError as exc:
            raise GeminiError(
                "Search-query normalization did not match the contract",
                is_retryable=True,
                error_code="gemini_invalid_output",
            ) from exc

    async def embed_concepts(self, concepts: list[ExtractedConcept]) -> list[list[float]]:
        requests = [
            {
                "model": f"models/{self.settings.gemini_embedding_model}",
                "content": {
                    "parts": [
                        {
                            "text": (
                                f"Food query: {concept.food_name}. "
                                f"Preparation: {', '.join(concept.preparation) or 'unspecified'}."
                            )
                        }
                    ]
                },
                "taskType": "RETRIEVAL_QUERY",
                "outputDimensionality": self.settings.embedding_dimensions,
            }
            for concept in concepts
        ]
        payload = await self._post(
            f"{self.base_url}/{self.settings.gemini_embedding_model}:batchEmbedContents",
            {"requests": requests},
        )
        try:
            vectors = [row["values"] for row in payload["embeddings"]]
        except (KeyError, TypeError) as exc:
            raise GeminiError(
                "Embedding response was invalid",
                is_retryable=True,
                error_code="gemini_invalid_output",
            ) from exc
        if len(vectors) != len(concepts) or any(
            not isinstance(vector, list)
            or len(vector) != self.settings.embedding_dimensions
            for vector in vectors
        ):
            raise GeminiError(
                "Embedding dimensions did not match the index",
                is_retryable=True,
                error_code="gemini_invalid_output",
            )
        return vectors

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        requests = [
            {
                "model": f"models/{self.settings.gemini_embedding_model}",
                "content": {"parts": [{"text": text}]},
                "taskType": "RETRIEVAL_DOCUMENT",
                "outputDimensionality": self.settings.embedding_dimensions,
            }
            for text in texts
        ]
        payload = await self._post(
            f"{self.base_url}/{self.settings.gemini_embedding_model}:batchEmbedContents",
            {"requests": requests},
        )
        try:
            vectors = [row["values"] for row in payload["embeddings"]]
        except (KeyError, TypeError) as exc:
            raise GeminiError(
                "Embedding response was invalid",
                is_retryable=True,
                error_code="gemini_invalid_output",
            ) from exc
        if len(vectors) != len(texts):
            raise GeminiError(
                "Embedding response count did not match",
                is_retryable=True,
                error_code="gemini_invalid_output",
            )
        return vectors

    async def select_candidates(
        self,
        *,
        concepts: list[ExtractedConcept],
        candidate_sets: list[list[dict[str, Any]]],
    ) -> SelectorOutput:
        compact_candidates = [
            [
                {
                    "food_id": candidate["food_id"],
                    "name": candidate["name"],
                    "category": candidate["category"],
                    "quality_status": candidate["quality_status"],
                    "matched_channels": candidate.get("matched_channels", []),
                    "matched_term": candidate.get("matched_term"),
                    "matched_term_type": candidate.get("matched_term_type"),
                    "primary_match_tier": candidate.get("primary_match_tier"),
                    "source_term_exact": candidate.get("source_term_exact", False),
                    "retrieval_score": candidate.get("retrieval_score", 0),
                    "portions": [
                        {
                            "portion_id": portion["portion_id"],
                            "description": portion["description"],
                            "gram_weight": portion["gram_weight"],
                        }
                        for portion in candidate.get("portions", [])[:8]
                    ],
                }
                for candidate in candidates
            ]
            for candidates in candidate_sets
        ]
        prompt_payload = {
            "concepts": [concept.model_dump() for concept in concepts],
            "candidate_sets": compact_candidates,
        }
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "For each concept select only a food_id from its matching candidate "
                            "set, or null for no match. Never create an ID, nutrient, portion, "
                            "conversion, or recipe decomposition. Preserve material preparation "
                            "and weight-basis distinctions as unresolved fields. An NFS/NS item "
                            "may be proposed as unspecified. Return alternatives only from that "
                            "same set, and only when they are a materially plausible choice for "
                            "the spoken food. Prefer direct primary/common-name evidence and exact "
                            "preparation matches. Do not choose a candidate with extra material "
                            "attributes that were not spoken when a less-assumptive matching "
                            "candidate exists. Confidence may be at least 0.92 only when the food "
                            "and every material attribute are directly supported."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": json.dumps(
                                prompt_payload,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "thinkingConfig": {"thinkingLevel": "low"},
                "responseMimeType": "application/json",
                "responseJsonSchema": SelectorOutput.model_json_schema(),
            },
        }
        response = await self._post(
            f"{self.base_url}/{self.settings.gemini_selector_model}:generateContent",
            payload,
        )
        try:
            return SelectorOutput.model_validate(self._json_text(response))
        except ValueError as exc:
            raise GeminiError(
                "Candidate selection did not match the contract",
                is_retryable=True,
                error_code="gemini_invalid_output",
            ) from exc
