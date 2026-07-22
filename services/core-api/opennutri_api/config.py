from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DATABASE_PATH_ENV = "OPENNUTRI_CORE_DB_PATH"
CORS_ORIGINS_ENV = "OPENNUTRI_API_CORS_ORIGINS"


def bundled_database_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "opennutri-fndds.sqlite"


def default_database_path() -> Path:
    bundled_path = bundled_database_path()
    if bundled_path.is_file():
        return bundled_path

    repo_root = Path(__file__).resolve().parents[3]
    return (
        repo_root
        / "services"
        / "data-pipeline"
        / "data"
        / "core"
        / "releases"
        / "opennutri-core-fndds-2021-2023-v0.0.1"
        / "opennutri-fndds.sqlite"
    )


def _cors_origins_from_env() -> tuple[str, ...]:
    configured = os.environ.get(CORS_ORIGINS_ENV)
    if configured is None:
        return ("http://localhost:5173", "http://127.0.0.1:5173")
    return tuple(origin.strip() for origin in configured.split(",") if origin.strip())


@dataclass(frozen=True)
class Settings:
    database_path: Path
    cors_origins: tuple[str, ...]

    @classmethod
    def from_environment(cls) -> "Settings":
        configured_path = os.environ.get(DATABASE_PATH_ENV)
        database_path = Path(configured_path).expanduser() if configured_path else default_database_path()
        return cls(
            database_path=database_path.resolve(),
            cors_origins=_cors_origins_from_env(),
        )
