from __future__ import annotations

import httpx
import pytest

from opennutri_voice.supabase_store import SupabasePrivateStore


class RecordingClient:
    def __init__(self) -> None:
        self.timeout = None

    async def post(self, url, *, headers, json, timeout=None):
        self.timeout = timeout
        request = httpx.Request("POST", url)
        return httpx.Response(201, request=request)


@pytest.mark.asyncio
async def test_embedding_upsert_uses_a_bulk_write_timeout(settings):
    client = RecordingClient()
    store = SupabasePrivateStore(settings, client=client)

    await store.upsert_embeddings(
        [
            {
                "food_id": "food-apple",
                "index_version": settings.index_version,
                "core_version": settings.core_version,
                "embedding_model": settings.gemini_embedding_model,
                "dimensions": 768,
                "input_hash": "a" * 64,
                "embedding": [0.0] * 768,
            }
        ]
    )

    assert client.timeout == 90
