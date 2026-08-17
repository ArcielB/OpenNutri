from __future__ import annotations

import json

import httpx
import pytest

from opennutri_voice.gemini import GeminiClient, GeminiError
from opennutri_voice.models import ExtractedConcept


@pytest.mark.asyncio
async def test_voice_uses_literal_transcription_then_text_extraction(settings):
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content)
        if len(requests) == 1:
            result = {
                "transcript": "Ten hard-boiled whole eggs.",
                "detected_language": "en",
            }
        else:
            result = {
                "concepts": [
                    {
                        "source_phrase": "Ten hard-boiled whole eggs",
                        "food_name": "hard-boiled whole egg",
                        "quantity": {"value": 10, "unit": "egg"},
                        "preparation": ["hard-boiled"],
                        "weight_basis": None,
                        "meal": None,
                    }
                ]
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
    assert len(requests) == 2
    assert requests[0].url.path.endswith("/gemini-audio:generateContent")
    assert requests[1].url.path.endswith("/gemini-extraction:generateContent")
    first_body = json.loads(requests[0].content)
    second_body = json.loads(requests[1].content)
    assert first_body["generationConfig"]["thinkingConfig"] == {
        "thinkingLevel": "minimal"
    }
    assert "temperature" not in first_body["generationConfig"]
    assert "inlineData" in first_body["contents"][0]["parts"][1]
    assert all(
        "inlineData" not in part for part in second_body["contents"][0]["parts"]
    )
    assert "10 and unit 'egg'" in second_body["systemInstruction"]["parts"][0][
        "text"
    ]
    assert "tel şehriye" in first_body["systemInstruction"]["parts"][0]["text"]
    assert "food_name must translate" in second_body["systemInstruction"]["parts"][
        0
    ]["text"]
    assert "Raw or uncooked never means as-purchased" in second_body[
        "systemInstruction"
    ]["parts"][0]["text"]


@pytest.mark.asyncio
async def test_voice_uses_review_only_audio_fallback_after_primary_rate_limit(settings):
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/gemini-audio:generateContent"):
            return httpx.Response(429, request=request)
        if request.url.path.endswith("/gemini-audio-fallback:generateContent"):
            result = {"transcript": "ten eggs", "detected_language": "en"}
        else:
            result = {
                "concepts": [
                    {
                        "source_phrase": "ten eggs",
                        "food_name": "egg",
                        "quantity": {"value": 10, "unit": "egg"},
                        "preparation": [],
                        "weight_basis": None,
                        "meal": None,
                    }
                ]
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
        "gemini-extraction:generateContent",
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
