from __future__ import annotations

import json
from dataclasses import replace

import httpx
import pytest

from opennutri_voice.gemini import GeminiClient, GeminiError
from opennutri_voice.models import ExtractedConcept


@pytest.mark.asyncio
async def test_voice_transcribes_and_extracts_in_one_audio_request(settings):
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content)
        result = {
            "transcript": "Ten hard-boiled whole eggs.",
            "detected_language": "en",
            "concepts": [
                {
                    "source_phrase": "Ten hard-boiled whole eggs",
                    "food_name": "hard-boiled whole egg",
                    "quantity": {"value": 10, "unit": "egg"},
                    "preparation": ["hard-boiled"],
                    "weight_basis": None,
                    "meal": None,
                }
            ],
        }
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": json.dumps(result)}]}}
                ]
            },
            request=request,
        )

    client = GeminiClient(
        settings,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    extraction = await client.transcribe_and_extract(
        wav_bytes=b"literal-wav",
        language_hint="auto",
    )

    assert extraction.transcript == "Ten hard-boiled whole eggs."
    assert extraction.transcription_model == "gemini-audio"
    assert extraction.transcription_fallback_used is False
    assert extraction.concepts[0].quantity.value == 10
    assert extraction.concepts[0].quantity.unit == "egg"
    assert len(requests) == 1
    assert requests[0].url.path.endswith("/gemini-audio:generateContent")
    body = json.loads(requests[0].content)
    assert body["generationConfig"]["thinkingConfig"] == {
        "thinkingLevel": "minimal"
    }
    assert "temperature" not in body["generationConfig"]
    assert "inlineData" in body["contents"][0]["parts"][1]
    prompt = body["systemInstruction"]["parts"][0]["text"]
    assert "value 10 and unit egg" in prompt
    assert "tel şehriye" in prompt
    assert "food_name" in prompt
    assert "Raw or uncooked never means as-purchased" in prompt


@pytest.mark.asyncio
async def test_gemini_38_audio_uses_its_supported_low_thinking_level(settings):
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        result = {
            "transcript": "150 grams of raw apple",
            "detected_language": "en",
            "concepts": [
                {
                    "source_phrase": "150 grams of raw apple",
                    "food_name": "raw apple",
                    "quantity": {"value": 150, "unit": "gram"},
                    "preparation": ["raw"],
                    "weight_basis": None,
                    "meal": None,
                }
            ],
        }
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": json.dumps(result)}]}}
                ]
            },
            request=request,
        )

    client = GeminiClient(
        replace(
            settings,
            gemini_audio_model="gemini-3.8-flash",
            gemini_audio_fallback_model="",
        ),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    extraction = await client.transcribe_and_extract(
        wav_bytes=b"literal-wav",
        language_hint="en-US",
    )

    assert extraction.transcript == "150 grams of raw apple"
    assert json.loads(requests[0].content)["generationConfig"]["thinkingConfig"] == {
        "thinkingLevel": "low"
    }


@pytest.mark.asyncio
async def test_invalid_structured_audio_output_uses_review_only_fallback(settings):
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/gemini-audio:generateContent"):
            result = {
                "transcript": "150 grams of raw apple",
                "detected_language": "en",
                "concepts": [
                    {
                        "source_phrase": "150 grams of raw apple",
                        "food_name": "raw apple",
                        "quantity": {"value": -150, "unit": "gram"},
                        "preparation": ["raw"],
                        "weight_basis": None,
                        "meal": None,
                    }
                ],
            }
        else:
            result = {
                "transcript": "150 grams of raw apple",
                "detected_language": "en",
                "concepts": [
                    {
                        "source_phrase": "150 grams of raw apple",
                        "food_name": "raw apple",
                        "quantity": {"value": 150, "unit": "gram"},
                        "preparation": ["raw"],
                        "weight_basis": None,
                        "meal": None,
                    }
                ],
            }
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": json.dumps(result)}]}}
                ]
            },
            request=request,
        )

    client = GeminiClient(
        settings,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    extraction = await client.transcribe_and_extract(
        wav_bytes=b"literal-wav",
        language_hint="en",
    )

    assert extraction.transcription_fallback_used is True
    assert extraction.transcription_model == "gemini-audio-fallback"
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_failed_fallback_preserves_transcript_from_invalid_primary(settings):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/gemini-audio-fallback:generateContent"):
            return httpx.Response(503, request=request)
        invalid = {
            "transcript": "150 grams of raw apple",
            "detected_language": "en",
            "concepts": [
                {
                    "source_phrase": "150 grams of raw apple",
                    "food_name": "raw apple",
                    "quantity": {"value": -150, "unit": "gram"},
                    "preparation": ["raw"],
                    "weight_basis": None,
                    "meal": None,
                }
            ],
        }
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": json.dumps(invalid)}]}}
                ]
            },
            request=request,
        )

    client = GeminiClient(
        settings,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(GeminiError) as raised:
        await client.transcribe_and_extract(
            wav_bytes=b"literal-wav",
            language_hint="en",
        )

    assert raised.value.error_code == "gemini_unavailable"
    assert raised.value.partial_transcript == "150 grams of raw apple"


@pytest.mark.asyncio
async def test_voice_uses_review_only_audio_fallback_after_primary_rate_limit(settings):
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/gemini-audio:generateContent"):
            return httpx.Response(429, request=request)
        result = {
            "transcript": "ten eggs",
            "detected_language": "en",
            "concepts": [
                {
                    "source_phrase": "ten eggs",
                    "food_name": "egg",
                    "quantity": {"value": 10, "unit": "egg"},
                    "preparation": [],
                    "weight_basis": None,
                    "meal": None,
                }
            ],
        }
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": json.dumps(result)}]}}
                ]
            },
            request=request,
        )

    client = GeminiClient(
        settings,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    extraction = await client.transcribe_and_extract(
        wav_bytes=b"literal-wav",
        language_hint="auto",
    )

    assert extraction.transcript == "ten eggs"
    assert extraction.transcription_model == "gemini-audio-fallback"
    assert extraction.transcription_fallback_used is True
    assert [request.url.path.rsplit("/", 1)[-1] for request in requests] == [
        "gemini-audio:generateContent",
        "gemini-audio-fallback:generateContent",
    ]


@pytest.mark.asyncio
async def test_turkish_voice_prefers_turkish_model_then_fast_default(settings):
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/gemini-audio-turkish:generateContent"):
            return httpx.Response(429, request=request)
        result = {
            "transcript": "150 gram çiğ elma",
            "detected_language": "tr",
            "concepts": [
                {
                    "source_phrase": "150 gram çiğ elma",
                    "food_name": "raw apple",
                    "quantity": {"value": 150, "unit": "gram"},
                    "preparation": ["raw"],
                    "weight_basis": None,
                    "meal": None,
                }
            ],
        }
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": json.dumps(result)}]}}
                ]
            },
            request=request,
        )

    client = GeminiClient(
        replace(settings, gemini_audio_fallback_model="gemini-audio-turkish"),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    extraction = await client.transcribe_and_extract(
        wav_bytes=b"literal-wav",
        language_hint="tr",
    )

    assert extraction.transcript == "150 gram çiğ elma"
    assert extraction.transcription_model == "gemini-audio"
    assert extraction.transcription_fallback_used is True
    assert [request.url.path.rsplit("/", 1)[-1] for request in requests] == [
        "gemini-audio-turkish:generateContent",
        "gemini-audio:generateContent",
    ]


@pytest.mark.asyncio
async def test_difficult_search_queries_are_normalized_in_one_batch(settings):
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "rewrites": [
                                                {
                                                    "concept_index": 0,
                                                    "search_query": "raw pasta",
                                                },
                                                {
                                                    "concept_index": 1,
                                                    "search_query": "cooked rice",
                                                },
                                            ]
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            },
            request=request,
        )

    client = GeminiClient(
        settings,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = await client.normalize_search_queries(
        [
            ExtractedConcept(source_phrase="çiğ makarna", food_name="çiğ makarna"),
            ExtractedConcept(
                source_phrase="pişmiş pirinç",
                food_name="pişmiş pirinç",
            ),
        ]
    )

    assert [rewrite.search_query for rewrite in result.rewrites] == [
        "raw pasta",
        "cooked rice",
    ]
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert body["generationConfig"]["temperature"] == 0
    prompt = body["systemInstruction"]["parts"][0]["text"]
    assert "Never decompose a dish or recipe" in prompt
    assert "preserve every explicitly spoken food variant" in prompt


@pytest.mark.asyncio
async def test_embedding_rate_limit_exposes_retry_hint(settings):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "12"}, request=request)

    client = GeminiClient(
        settings,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(GeminiError) as raised:
        await client.embed_documents(["Name: apple"])

    assert str(raised.value) == "Gemini rate limit reached"
    assert raised.value.is_rate_limited is True
    assert raised.value.is_retryable is True
    assert raised.value.retry_after_seconds == 12


@pytest.mark.asyncio
async def test_temporary_embedding_transport_errors_are_retryable(settings):
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("temporary DNS failure", request=request)

    client = GeminiClient(
        settings,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(GeminiError) as raised:
        await client.embed_documents(["Name: apple"])

    assert str(raised.value) == "Gemini is temporarily unavailable"
    assert raised.value.is_retryable is True
    assert raised.value.is_rate_limited is False
