from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def default_core_database_path() -> Path:
    service_root = Path(__file__).resolve().parents[1]
    repository_root = Path(__file__).resolve().parents[3]
    local_release = (
        repository_root
        / "services"
        / "data-pipeline"
        / "data"
        / "core"
        / "releases"
        / "opennutri-core-usda-v0.3.0"
        / "opennutri-core.sqlite"
    )
    if local_release.is_file():
        return local_release
    return service_root / "data" / "opennutri-core.sqlite"


@dataclass(frozen=True)
class Settings:
    core_database_path: Path
    supabase_url: str
    supabase_service_role_key: str
    supabase_jwt_audience: str
    gemini_api_key: str
    gemini_audio_model: str
    gemini_audio_turkish_model: str
    gemini_audio_fallback_model: str
    gemini_extraction_model: str
    gemini_selector_model: str
    gemini_coach_model: str
    gemini_embedding_model: str
    embedding_dimensions: int
    core_version: str
    index_version: str
    per_user_requests_per_minute: int
    per_user_ai_resolutions_per_day: int
    global_ai_resolutions_per_day: int
    gemini_request_timeout_seconds: int
    active_request_timeout_seconds: int

    @property
    def jwks_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    @property
    def jwt_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    def audio_model_for_language(self, language_hint: str) -> str:
        if language_hint.lower().startswith("tr"):
            return self.gemini_audio_turkish_model
        return self.gemini_audio_model

    @classmethod
    def from_environment(cls) -> "Settings":
        configured_database = os.environ.get("OPENNUTRI_CORE_DB_PATH")
        return cls(
            core_database_path=Path(
                configured_database or default_core_database_path()
            ).expanduser().resolve(),
            supabase_url=os.environ.get("OPENNUTRI_APP_SUPABASE_URL", ""),
            supabase_service_role_key=os.environ.get(
                "OPENNUTRI_APP_SUPABASE_SERVICE_ROLE_KEY", ""
            ),
            supabase_jwt_audience=os.environ.get(
                "OPENNUTRI_APP_SUPABASE_JWT_AUDIENCE", "authenticated"
            ),
            gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
            gemini_audio_model=os.environ.get(
                "OPENNUTRI_GEMINI_AUDIO_MODEL", "gemini-3.8-flash"
            ),
            gemini_audio_turkish_model=os.environ.get(
                "OPENNUTRI_GEMINI_AUDIO_TURKISH_MODEL", "gemini-3.8-flash"
            ),
            gemini_audio_fallback_model=os.environ.get(
                "OPENNUTRI_GEMINI_AUDIO_FALLBACK_MODEL", "gemini-3.1-flash-lite"
            ),
            gemini_extraction_model=os.environ.get(
                "OPENNUTRI_GEMINI_EXTRACTION_MODEL", "gemini-3.5-flash-lite"
            ),
            gemini_selector_model=os.environ.get(
                "OPENNUTRI_GEMINI_SELECTOR_MODEL", "gemini-3.5-flash-lite"
            ),
            gemini_coach_model=os.environ.get(
                "OPENNUTRI_GEMINI_COACH_MODEL", "gemini-3.8-flash"
            ),
            gemini_embedding_model=os.environ.get(
                "OPENNUTRI_GEMINI_EMBEDDING_MODEL", "gemini-embedding-2"
            ),
            embedding_dimensions=_int_env("OPENNUTRI_EMBEDDING_DIMENSIONS", 768),
            core_version=os.environ.get("OPENNUTRI_CORE_VERSION", "0.3.0"),
            index_version=os.environ.get(
                "OPENNUTRI_SEMANTIC_INDEX_VERSION", "core-0.3.0-gemini-embedding-2-768"
            ),
            per_user_requests_per_minute=_int_env(
                "OPENNUTRI_USER_REQUESTS_PER_MINUTE", 10
            ),
            per_user_ai_resolutions_per_day=_int_env(
                "OPENNUTRI_USER_AI_RESOLUTIONS_PER_DAY", 50
            ),
            global_ai_resolutions_per_day=_int_env(
                "OPENNUTRI_GLOBAL_AI_RESOLUTIONS_PER_DAY", 200
            ),
            gemini_request_timeout_seconds=_int_env(
                "OPENNUTRI_GEMINI_REQUEST_TIMEOUT_SECONDS", 12
            ),
            active_request_timeout_seconds=_int_env(
                "OPENNUTRI_ACTIVE_REQUEST_TIMEOUT_SECONDS", 90
            ),
        )
