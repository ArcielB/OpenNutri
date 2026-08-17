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


@pytest.mark.asyncio
async def test_existing_embedding_hashes_reads_every_supabase_page(settings):
    offsets: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params.get("offset", "0"))
        offsets.append(offset)
        size = 1000 if offset == 0 else 3
        rows = [
            {
                "food_id": f"food-{offset + index:05d}",
                "input_hash": f"hash-{offset + index:05d}",
            }
            for index in range(size)
        ]
        return httpx.Response(200, json=rows, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    store = SupabasePrivateStore(settings, client=client)
    hashes = await store.existing_embedding_hashes()
    await client.aclose()

    assert offsets == [0, 1000]
    assert len(hashes) == 1003
    assert hashes["food-01002"] == "hash-01002"
