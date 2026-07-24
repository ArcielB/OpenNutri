from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BENCHMARK = ROOT / "benchmarks" / "voice-v0.1.0"
sys.path.insert(0, str(BENCHMARK))

from validate import load_cases, validate_audio, validate_core_ids  # noqa: E402


def test_voice_benchmark_is_complete_and_source_backed():
    manifest = BENCHMARK / "cases.jsonl"
    release_database = (
        ROOT
        / "services"
        / "data-pipeline"
        / "data"
        / "core"
        / "releases"
        / "opennutri-core-usda-v0.3.0"
        / "opennutri-core.sqlite"
    )
    service_database = ROOT / "services" / "voice-api" / "data" / "opennutri-core.sqlite"
    database = release_database if release_database.is_file() else service_database
    cases = load_cases(manifest)
    assert len(cases) == 240
    validate_core_ids(cases, database)
    validate_audio(cases, BENCHMARK)
