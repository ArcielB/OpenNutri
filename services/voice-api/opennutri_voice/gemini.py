from __future__ import annotations

import base64
import json
from typing import Any

import httpx

from .config import Settings
from .models import AudioExtraction, ExtractedConcept, SelectorOutput


class GeminiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        is_rate_limited: bool = False,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.is_rate_limited = is_rate_limited
        self.retry_after_seconds = retry_after_seconds


class GeminiClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.AsyncClient(timeout=45)
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    @property
    def _headers(self) -> dict[str, str]:
        if not self.settings.gemini_api_key:
            raise GeminiError("Gemini is not configured")
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
                    retry_after_seconds=retry_after,
                ) from exc
            raise GeminiError("Gemini request failed") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise GeminiError("Gemini request failed") from exc
        if not isinstance(result, dict):
            raise GeminiError("Gemini returned an invalid payload")
        return result

    @staticmethod
    def _json_text(payload: dict[str, Any]) -> Any:
        try:
            parts = payload["candidates"][0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts)
            return json.loads(text)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise GeminiError("Gemini returned invalid structured output") from exc

    async def transcribe_and_extract(
        self,
        *,
        wav_bytes: bytes,
        language_hint: str,
    ) -> AudioExtraction:
        schema = AudioExtraction.model_json_schema()
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "Transcribe the meal recording and extract at most five distinct "
                            "food concepts. Preserve raw/cooked, drained, skin, bone, edible, "
                            "and as-purchased wording. Never invent a quantity or preparation. "
                            "English and Turkish are supported; other languages are best effort."
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
                                "Return the transcript and structured concepts."
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
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
            },
        }
        response = await self._post(
            f"{self.base_url}/{self.settings.gemini_audio_model}:generateContent",
            payload,
        )
        try:
            return AudioExtraction.model_validate(self._json_text(response))
        except ValueError as exc:
            raise GeminiError("Audio extraction did not match the contract") from exc

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
            raise GeminiError("Embedding response was invalid") from exc
        if len(vectors) != len(concepts) or any(
            not isinstance(vector, list)
            or len(vector) != self.settings.embedding_dimensions
            for vector in vectors
        ):
            raise GeminiError("Embedding dimensions did not match the index")
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
            raise GeminiError("Embedding response was invalid") from exc
        if len(vectors) != len(texts):
            raise GeminiError("Embedding response count did not match")
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
                            "same set."
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
                "temperature": 0,
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
            raise GeminiError("Candidate selection did not match the contract") from exc
