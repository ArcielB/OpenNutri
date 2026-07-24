from __future__ import annotations

import asyncio
import time
from typing import Any, Protocol

import httpx
import jwt


class AuthenticationError(RuntimeError):
    pass


class SubjectVerifier(Protocol):
    async def verify(self, token: str) -> str: ...


class SupabaseJwksVerifier:
    def __init__(
        self,
        *,
        jwks_url: str,
        issuer: str,
        audience: str,
        client: httpx.AsyncClient | None = None,
        cache_seconds: int = 3600,
    ) -> None:
        self.jwks_url = jwks_url
        self.issuer = issuer
        self.audience = audience
        self.client = client or httpx.AsyncClient(timeout=10)
        self.cache_seconds = cache_seconds
        self._keys: dict[str, Any] = {}
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def _refresh(self) -> None:
        if not self.jwks_url.startswith("https://"):
            raise AuthenticationError("Anonymous authentication is not configured")
        response = await self.client.get(self.jwks_url)
        response.raise_for_status()
        payload = response.json()
        keys = payload.get("keys")
        if not isinstance(keys, list) or not keys:
            raise AuthenticationError("Supabase JWKS did not contain signing keys")
        parsed: dict[str, Any] = {}
        for key_data in keys:
            if not isinstance(key_data, dict) or not isinstance(key_data.get("kid"), str):
                continue
            parsed[key_data["kid"]] = jwt.PyJWK.from_dict(key_data)
        if not parsed:
            raise AuthenticationError("Supabase JWKS contained no usable signing keys")
        self._keys = parsed
        self._expires_at = time.monotonic() + self.cache_seconds

    async def verify(self, token: str) -> str:
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Invalid access token") from exc
        if not isinstance(kid, str):
            raise AuthenticationError("Access token has no signing-key identifier")

        async with self._lock:
            if time.monotonic() >= self._expires_at or kid not in self._keys:
                try:
                    await self._refresh()
                except (httpx.HTTPError, ValueError) as exc:
                    raise AuthenticationError("Could not verify access token") from exc
            signing_key = self._keys.get(kid)
        if signing_key is None:
            raise AuthenticationError("Access token uses an unknown signing key")
        try:
            claims = jwt.decode(
                token,
                key=signing_key.key,
                algorithms=[signing_key.algorithm_name],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Invalid or expired access token") from exc
        subject = claims.get("sub")
        role = claims.get("role")
        if not isinstance(subject, str) or not subject:
            raise AuthenticationError("Access token has no subject")
        if role != "authenticated":
            raise AuthenticationError("Anonymous session is not authenticated")
        return subject
