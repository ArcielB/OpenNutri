from __future__ import annotations

from typing import Any

import httpx

from .config import Settings


class SupabaseStoreError(RuntimeError):
    pass


class SupabasePrivateStore:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.AsyncClient(timeout=15)

    @property
    def _headers(self) -> dict[str, str]:
        key = self.settings.supabase_service_role_key
        if not self.settings.supabase_url or not key:
            raise SupabaseStoreError("Private Supabase storage is not configured")
        return {
            "apikey": key,
            "authorization": f"Bearer {key}",
            "content-type": "application/json",
        }

    async def _post(
        self,
        path: str,
        payload: Any,
        *,
        prefer: str | None = None,
        timeout: float | None = None,
    ) -> Any:
        headers = self._headers
        if prefer:
            headers["prefer"] = prefer
        try:
            response = await self.client.post(
                f"{self.settings.supabase_url.rstrip('/')}{path}",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            if not response.content:
                return None
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SupabaseStoreError(f"Supabase request failed for {path}") from exc

    async def reserve_request(self, *, subject: str, request_id: str) -> dict[str, Any]:
        payload = await self._post(
            "/rest/v1/rpc/reserve_resolution_request",
            {
                "p_subject": subject,
                "p_request_id": request_id,
                "p_user_requests_per_minute": self.settings.per_user_requests_per_minute,
                "p_user_ai_per_day": self.settings.per_user_ai_resolutions_per_day,
                "p_global_ai_per_day": self.settings.global_ai_resolutions_per_day,
                "p_active_timeout_seconds": self.settings.active_request_timeout_seconds,
            },
        )
        if not isinstance(payload, dict):
            raise SupabaseStoreError("Quota RPC returned an invalid response")
        return payload

    async def release_request(self, *, subject: str, request_id: str) -> None:
        await self._post(
            "/rest/v1/rpc/release_resolution_request",
            {"p_subject": subject, "p_request_id": request_id},
        )

    async def semantic_search(
        self,
        *,
        embedding: list[float],
        limit: int,
    ) -> list[dict[str, Any]]:
        payload = await self._post(
            "/rest/v1/rpc/match_food_embeddings",
            {
                "query_embedding": embedding,
                "match_count": limit,
                "requested_core_version": self.settings.core_version,
                "requested_index_version": self.settings.index_version,
            },
        )
        if not isinstance(payload, list):
            raise SupabaseStoreError("Semantic search returned an invalid response")
        return [row for row in payload if isinstance(row, dict)]

    async def store_feedback(
        self,
        *,
        subject: str,
        rows: list[dict[str, Any]],
    ) -> int:
        payload = [{**row, "subject": subject} for row in rows]
        await self._post(
            "/rest/v1/voice_resolution_feedback",
            payload,
            prefer="return=minimal",
        )
        return len(payload)

    async def delete_feedback(self, *, subject: str) -> None:
        headers = self._headers
        try:
            response = await self.client.delete(
                f"{self.settings.supabase_url.rstrip('/')}/rest/v1/"
                "voice_resolution_feedback",
                headers=headers,
                params={"subject": f"eq.{subject}"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SupabaseStoreError("Could not delete feedback") from exc

    async def existing_embedding_hashes(self) -> dict[str, str]:
        headers = self._headers
        try:
            response = await self.client.get(
                f"{self.settings.supabase_url.rstrip('/')}/rest/v1/food_embeddings",
                headers=headers,
                params={
                    "select": "food_id,input_hash",
                    "core_version": f"eq.{self.settings.core_version}",
                    "index_version": f"eq.{self.settings.index_version}",
                },
            )
            response.raise_for_status()
            rows = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SupabaseStoreError("Could not load embedding state") from exc
        return {
            row["food_id"]: row["input_hash"]
            for row in rows
            if isinstance(row, dict)
            and isinstance(row.get("food_id"), str)
            and isinstance(row.get("input_hash"), str)
        }

    async def upsert_embeddings(self, rows: list[dict[str, Any]]) -> None:
        await self._post(
            "/rest/v1/food_embeddings?on_conflict=food_id,index_version",
            rows,
            prefer="resolution=merge-duplicates,return=minimal",
            timeout=90,
        )
