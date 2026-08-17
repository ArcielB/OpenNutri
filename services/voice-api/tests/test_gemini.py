from __future__ import annotations

import json

import httpx
import pytest

from opennutri_voice.gemini import GeminiClient, GeminiError


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
