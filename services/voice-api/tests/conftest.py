from __future__ import annotations

import io
import sqlite3
import wave
from pathlib import Path

import pytest

from opennutri_voice.config import Settings


def make_wav(
    *,
    seconds: float = 1,
    sample_rate: int = 16_000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(sample_width)
        audio.setframerate(sample_rate)
        audio.writeframes(b"\0" * int(seconds * sample_rate * channels * sample_width))
    return output.getvalue()


def create_core_fixture(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE dataset_releases (
            release_id TEXT PRIMARY KEY,
            artifact_version TEXT NOT NULL
        );
        INSERT INTO dataset_releases VALUES ('fixture-release', '0.3.0');
        CREATE TABLE foods (
            food_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            original_description TEXT NOT NULL,
            category_name TEXT NOT NULL,
            quality_status TEXT NOT NULL,
            release_id TEXT NOT NULL,
            is_searchable INTEGER NOT NULL,
            search_priority INTEGER NOT NULL
        );
        CREATE TABLE portions (
            portion_id TEXT PRIMARY KEY,
            food_id TEXT NOT NULL,
            sequence_number INTEGER,
            portion_description TEXT NOT NULL,
            gram_weight REAL NOT NULL,
            amount REAL
        );
        CREATE TABLE edible_portion_factors (
            factor_id TEXT PRIMARY KEY,
            food_id TEXT NOT NULL,
            is_usable INTEGER NOT NULL
        );
        CREATE TABLE food_search_terms (
            term_id TEXT PRIMARY KEY,
            food_id TEXT NOT NULL,
            term TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE food_search USING fts5(
            food_id UNINDEXED,
            display_name,
            search_text,
            category_name
        );
        CREATE VIRTUAL TABLE food_source_term_search USING fts5(
            term_id UNINDEXED,
            food_id UNINDEXED,
            term,
            term_type UNINDEXED
        );
        INSERT INTO foods VALUES
            ('food-apple', 'Apple, raw', 'Apple, raw', 'Fruit', 'complete',
             'fixture-release', 1, 100),
            ('food-apple-cooked', 'Apple, cooked', 'Apple, cooked', 'Fruit',
             'complete', 'fixture-release', 1, 90),
            ('food-rice', 'Rice, cooked', 'Rice, cooked', 'Grains', 'complete',
             'fixture-release', 1, 100),
            ('food-egg', 'Egg, whole, cooked, hard-boiled',
             'Egg, whole, cooked, hard-boiled', 'Eggs', 'complete',
             'fixture-release', 1, 100),
            ('food-pasta-dry', 'Pasta, dry, enriched', 'Pasta, dry, enriched',
             'Grains', 'complete', 'fixture-release', 1, 100),
            ('food-pasta-cooked', 'Pasta, cooked', 'Pasta, cooked', 'Grains',
             'complete', 'fixture-release', 1, 100),
            ('food-bulgur', 'Bulgur, dry, raw', 'Bulgur, dry, raw', 'Grains',
             'complete', 'fixture-release', 1, 200);
        INSERT INTO food_search VALUES
            ('food-apple', 'Apple, raw', 'apple raw fruit', 'Fruit'),
            ('food-apple-cooked', 'Apple, cooked', 'apple cooked fruit', 'Fruit'),
            ('food-rice', 'Rice, cooked', 'rice cooked grain', 'Grains'),
            ('food-egg', 'Egg, whole, cooked, hard-boiled',
             'egg whole cooked hard-boiled', 'Eggs'),
            ('food-pasta-dry', 'Pasta, dry, enriched',
             'pasta dry enriched grain', 'Grains'),
            ('food-pasta-cooked', 'Pasta, cooked', 'pasta cooked grain',
             'Grains'),
            ('food-bulgur', 'Bulgur, dry, raw',
             'bulgur dry raw cereal grains and pasta', 'Grains');
        INSERT INTO food_source_term_search VALUES
            ('term-elma', 'food-apple', 'elma', 'common_name');
        INSERT INTO food_search_terms VALUES ('term-elma', 'food-apple', 'elma');
        INSERT INTO portions VALUES
            ('portion-cup', 'food-rice', 1, '1 cup', 158, 1);
        """
    )
    connection.commit()
    connection.close()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    database = tmp_path / "core.sqlite"
    create_core_fixture(database)
    return Settings(
        core_database_path=database,
        supabase_url="https://fixture.supabase.co",
        supabase_service_role_key="service-role",
        supabase_jwt_audience="authenticated",
        gemini_api_key="gemini-key",
        gemini_audio_model="gemini-audio",
        gemini_audio_turkish_model="gemini-audio-turkish",
        gemini_audio_fallback_model="gemini-audio-fallback",
        gemini_extraction_model="gemini-extraction",
        gemini_selector_model="gemini-selector",
        gemini_coach_model="gemini-coach",
        gemini_embedding_model="gemini-embedding-2",
        embedding_dimensions=768,
        core_version="0.3.0",
        index_version="fixture-index",
        per_user_requests_per_minute=10,
        per_user_ai_resolutions_per_day=50,
        global_ai_resolutions_per_day=200,
        gemini_request_timeout_seconds=12,
        active_request_timeout_seconds=90,
    )
