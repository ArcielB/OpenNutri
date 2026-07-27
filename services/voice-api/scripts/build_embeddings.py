#!/usr/bin/env python3
"""Resume-safe builder for the private OpenNutri semantic food index."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
import time
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from opennutri_voice.config import Settings
from opennutri_voice.core_repository import CoreFoodRepository
from opennutri_voice.gemini import GeminiClient
from opennutri_voice.supabase_store import SupabasePrivateStore


def embedding_input(row: dict) -> str:
    fields = [
        f"Name: {row['display_name']}",
        f"Category: {row['category_name']}",
    ]
    if row.get("source_terms"):
        fields.append(f"Source terms: {row['source_terms']}")
    if row.get("original_description") != row.get("display_name"):
        fields.append(f"Preparation description: {row['original_description']}")
    return "\n".join(fields)


def input_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def build(
    *,
    batch_size: int,
    limit: int | None,
    min_interval_seconds: float = 65.0,
    max_rate_limit_retries: int = 5,
) -> int:
    settings = Settings.from_environment()
    core = CoreFoodRepository(settings.core_database_path)
    core.validate()
    if core.artifact_version() != settings.core_version:
        raise RuntimeError("Core database version does not match OPENNUTRI_CORE_VERSION")
    store = SupabasePrivateStore(settings)
    gemini = GeminiClient(settings)
    existing = await store.existing_embedding_hashes()
    pending: list[tuple[dict, str, str]] = []
    for row in core.searchable_food_rows():
        text = embedding_input(row)
        digest = input_hash(text)
        if existing.get(row["food_id"]) == digest:
            continue
        pending.append((row, text, digest))
        if limit is not None and len(pending) >= limit:
            break

    completed = 0
    last_embedding_request_at: float | None = None
    for offset in range(0, len(pending), batch_size):
        batch = pending[offset : offset + batch_size]
        if last_embedding_request_at is not None:
            elapsed = time.monotonic() - last_embedding_request_at
            delay = max(0.0, min_interval_seconds - elapsed)
            if delay:
                print(f"Waiting {delay:.0f}s for the embedding free-tier window", flush=True)
                await asyncio.sleep(delay)

        retry_count = 0
        while True:
            last_embedding_request_at = time.monotonic()
            try:
                vectors = await gemini.embed_documents([item[1] for item in batch])
                break
            except GeminiError as exc:
                if (
                    not exc.is_rate_limited
                    or retry_count >= max_rate_limit_retries
                ):
                    raise
                retry_count += 1
                delay = max(min_interval_seconds, exc.retry_after_seconds or 0.0)
                print(
                    f"Gemini rate limited; retrying this batch in {delay:.0f}s "
                    f"({retry_count}/{max_rate_limit_retries})",
                    flush=True,
                )
                await asyncio.sleep(delay)
        rows = [
            {
                "food_id": item[0]["food_id"],
                "index_version": settings.index_version,
                "core_version": settings.core_version,
                "embedding_model": settings.gemini_embedding_model,
                "dimensions": settings.embedding_dimensions,
                "input_hash": item[2],
                "embedding": vector,
            }
            for item, vector in zip(batch, vectors, strict=True)
        ]
        await store.upsert_embeddings(rows)
        completed += len(rows)
        print(f"Embedded {completed}/{len(pending)} pending foods", flush=True)
    print(
        f"Index {settings.index_version}: {len(existing)} existing, "
        f"{completed} written, {len(pending) - completed} pending"
    )
    return completed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--min-interval-seconds",
        type=float,
        default=65.0,
        help="Minimum delay between embedding requests; keeps a Free-tier build resumable.",
    )
    parser.add_argument("--max-rate-limit-retries", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 100:
        parser.error("--batch-size must be between 1 and 100")
    if args.min_interval_seconds < 0:
        parser.error("--min-interval-seconds must be non-negative")
    if args.max_rate_limit_retries < 0:
        parser.error("--max-rate-limit-retries must be non-negative")
    asyncio.run(
        build(
            batch_size=args.batch_size,
            limit=args.limit,
            min_interval_seconds=args.min_interval_seconds,
            max_rate_limit_retries=args.max_rate_limit_retries,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
