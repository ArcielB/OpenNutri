#!/usr/bin/env python3
"""Validate the benchmark manifest, Core IDs, and committed WAV fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import wave
from collections import Counter
from pathlib import Path
from typing import Any


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(cases) < 200:
        raise AssertionError(f"expected at least 200 cases, found {len(cases)}")
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise AssertionError("case IDs must be unique")
    counts = Counter((case["language"], case["modality"]) for case in cases)
    for language in ("en", "tr"):
        if counts[(language, "text")] < 40 or counts[(language, "audio")] < 20:
            raise AssertionError(f"insufficient {language} text/audio coverage: {counts}")
    required_tags = {
        "colloquial",
        "multiple_foods",
        "source_portion",
        "missing_quantity",
        "cooking_state",
        "skin",
        "bone",
        "drained",
        "as_purchased",
        "transcription_error",
        "no_match_dish",
        "raw_cooked_ambiguity",
    }
    tags = {tag for case in cases for tag in case["tags"]}
    if missing := required_tags - tags:
        raise AssertionError(f"missing benchmark tags: {sorted(missing)}")
    return cases


def validate_core_ids(cases: list[dict[str, Any]], database: Path) -> None:
    expected = {
        food_id
        for case in cases
        for concept in case["expected"]["concepts"]
        for food_id in concept["acceptable_food_ids"]
    }
    connection = sqlite3.connect(database)
    try:
        found = {
            row[0]
            for row in connection.execute(
                f"SELECT food_id FROM foods WHERE is_searchable = 1 "
                f"AND food_id IN ({','.join('?' for _ in expected)})",
                sorted(expected),
            )
        }
    finally:
        connection.close()
    if missing := expected - found:
        raise AssertionError(f"benchmark contains invalid Core IDs: {sorted(missing)}")


def validate_audio(cases: list[dict[str, Any]], root: Path) -> None:
    for case in cases:
        if case["modality"] != "audio":
            if "audio_path" in case:
                raise AssertionError(f"text case has audio path: {case['id']}")
            continue
        path = root / case["audio_path"]
        if not path.is_file():
            raise AssertionError(f"missing audio fixture: {path}")
        if path.stat().st_size > 1024 * 1024:
            raise AssertionError(f"audio fixture exceeds 1 MB: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != case.get("audio_sha256"):
            raise AssertionError(f"audio hash mismatch: {path}")
        with wave.open(str(path), "rb") as wav:
            duration = wav.getnframes() / wav.getframerate()
            actual = (wav.getframerate(), wav.getnchannels(), wav.getsampwidth())
        if actual != (16_000, 1, 2):
            raise AssertionError(f"invalid WAV format {actual}: {path}")
        if duration > 20:
            raise AssertionError(f"audio fixture exceeds 20 seconds: {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("cases.jsonl"))
    parser.add_argument("--core-db", type=Path, required=True)
    args = parser.parse_args()
    manifest = args.manifest.resolve()
    cases = load_cases(manifest)
    validate_core_ids(cases, args.core_db)
    validate_audio(cases, manifest.parent)
    counts = Counter((case["language"], case["modality"]) for case in cases)
    print(f"Validated {len(cases)} benchmark cases: {dict(sorted(counts.items()))}")


if __name__ == "__main__":
    main()
