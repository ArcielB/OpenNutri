from __future__ import annotations

import httpx
import pytest

from opennutri_voice.gemini import GeminiClient, GeminiError


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
