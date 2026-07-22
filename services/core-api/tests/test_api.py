from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from opennutri_api.config import default_database_path
from opennutri_api.main import create_app
from opennutri_api.models import FoodDetailResponse
from opennutri_api.repository import CoreRepository, DatabaseConfigurationError


FIXTURE_FOOD_ID = "food-apple"


def create_fixture_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE dataset_releases (
                release_id TEXT PRIMARY KEY,
                artifact_version TEXT NOT NULL,
                publisher TEXT NOT NULL,
                dataset_name TEXT NOT NULL,
                data_type TEXT NOT NULL,
                release_date TEXT NOT NULL,
                coverage_start TEXT NOT NULL,
                coverage_end TEXT NOT NULL,
                download_url TEXT NOT NULL,
                archive_sha256 TEXT NOT NULL,
                source_tree_sha256 TEXT NOT NULL,
                license TEXT NOT NULL,
                license_url TEXT NOT NULL
            );
            CREATE TABLE food_categories (category_id TEXT PRIMARY KEY, name TEXT NOT NULL);
            CREATE TABLE foods (
                food_id TEXT PRIMARY KEY,
                release_id TEXT NOT NULL,
                source TEXT NOT NULL,
                data_type TEXT NOT NULL,
                source_food_id TEXT NOT NULL,
                source_food_code TEXT NOT NULL,
                original_description TEXT NOT NULL,
                normalized_description TEXT NOT NULL,
                display_name TEXT NOT NULL,
                category_id TEXT NOT NULL,
                category_name TEXT NOT NULL,
                publication_date TEXT NOT NULL,
                coverage_start TEXT NOT NULL,
                coverage_end TEXT NOT NULL,
                quality_status TEXT NOT NULL,
                is_searchable INTEGER NOT NULL,
                exclusion_reason TEXT,
                ambiguity_flags TEXT NOT NULL,
                nutrient_count INTEGER NOT NULL,
                portion_count INTEGER NOT NULL,
                search_priority INTEGER NOT NULL,
                search_text TEXT NOT NULL
            );
            CREATE TABLE nutrients (
                nutrient_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                source_nutrient_id TEXT NOT NULL,
                nutrient_number TEXT NOT NULL,
                name TEXT NOT NULL,
                unit TEXT NOT NULL,
                source_unit TEXT NOT NULL,
                sort_rank REAL,
                is_archived INTEGER NOT NULL
            );
            CREATE TABLE food_nutrients (
                food_id TEXT NOT NULL,
                nutrient_id TEXT NOT NULL,
                amount REAL NOT NULL,
                unit TEXT NOT NULL,
                basis TEXT NOT NULL,
                source_row_id TEXT NOT NULL,
                source_nutrient_code TEXT NOT NULL,
                derivation_id TEXT,
                data_points INTEGER,
                minimum REAL,
                maximum REAL,
                median REAL,
                footnote TEXT,
                min_year_acquired TEXT,
                PRIMARY KEY (food_id, nutrient_id)
            );
            CREATE TABLE portions (
                portion_id TEXT PRIMARY KEY,
                food_id TEXT NOT NULL,
                source_portion_id TEXT NOT NULL,
                sequence_number INTEGER,
                amount REAL,
                measure_unit_id TEXT NOT NULL,
                measure_unit_name TEXT NOT NULL,
                portion_description TEXT NOT NULL,
                modifier TEXT NOT NULL,
                gram_weight REAL NOT NULL,
                data_points INTEGER,
                footnote TEXT,
                min_year_acquired TEXT
            );
            CREATE VIRTUAL TABLE food_search USING fts5(
                food_id UNINDEXED,
                display_name,
                search_text,
                category_name
            );
            """
        )
        connection.execute(
            "INSERT INTO dataset_releases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "fixture-release",
                "0.0.1-test",
                "USDA Agricultural Research Service",
                "Fixture FNDDS",
                "survey_fndds_food",
                "2024-10-31",
                "2021-01-01",
                "2023-12-31",
                "https://example.test/fndds.zip",
                "a" * 64,
                "b" * 64,
                "CC0-1.0",
                "https://creativecommons.org/publicdomain/zero/1.0/",
            ),
        )
        connection.execute("INSERT INTO food_categories VALUES ('cat-apples', 'Apples')")
        foods = [
            (
                FIXTURE_FOOD_ID,
                "Apple, raw",
                "apple raw fruit",
                "complete",
                "[]",
                2,
                1,
                110,
                1,
                "100",
                "90010000",
            ),
            (
                "food-apple-nfs",
                "Apple, NFS",
                "apple nfs fruit",
                "ambiguous",
                '["not_further_specified"]',
                2,
                0,
                80,
                1,
                "101",
                "90010001",
            ),
            (
                "food-excluded",
                "Apple shell",
                "apple shell",
                "excluded",
                "[]",
                0,
                0,
                0,
                0,
                "102",
                "90010002",
            ),
        ]
        for food in foods:
            connection.execute(
                """
                INSERT INTO foods (
                    food_id, release_id, source, data_type, source_food_id,
                    source_food_code, original_description, normalized_description,
                    display_name, category_id, category_name, publication_date,
                    coverage_start, coverage_end, quality_status, is_searchable,
                    exclusion_reason, ambiguity_flags, nutrient_count, portion_count,
                    search_priority, search_text
                ) VALUES (?, 'fixture-release', 'USDA', 'survey_fndds_food', ?, ?, ?,
                          lower(?), ?, 'cat-apples', 'Apples', '2024-10-31',
                          '2021-01-01', '2023-12-31', ?, ?, NULL, ?, ?, ?, ?, ?)
                """,
                (
                    food[0],
                    food[9],
                    food[10],
                    food[1],
                    food[1],
                    food[1],
                    food[3],
                    food[8],
                    food[4],
                    food[5],
                    food[6],
                    food[7],
                    food[2],
                ),
            )
            if food[8]:
                connection.execute(
                    "INSERT INTO food_search VALUES (?, ?, ?, 'Apples')",
                    (food[0], food[1], food[2]),
                )

        connection.executemany(
            "INSERT INTO nutrients VALUES (?, 'USDA', ?, ?, ?, ?, ?, ?, 0)",
            [
                ("nutrient-energy", "1008", "208", "Energy", "kcal", "KCAL", 300),
                ("nutrient-protein", "1003", "203", "Protein", "g", "G", 600),
            ],
        )
        connection.executemany(
            """
            INSERT INTO food_nutrients VALUES (?, ?, ?, ?, 'per_100g_edible_portion',
                ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
            """,
            [
                (FIXTURE_FOOD_ID, "nutrient-energy", 52.0, "kcal", "row-energy", "208"),
                (FIXTURE_FOOD_ID, "nutrient-protein", 0.26, "g", "row-protein", "203"),
                ("food-apple-nfs", "nutrient-energy", 50.0, "kcal", "row-nfs-energy", "208"),
                ("food-apple-nfs", "nutrient-protein", 0.2, "g", "row-nfs-protein", "203"),
            ],
        )
        connection.execute(
            """
            INSERT INTO portions VALUES (
                'portion-medium', ?, 'source-portion-1', 1, 1, 'unit-unknown',
                'undetermined', '1 medium', '61238', 182.0, NULL, NULL, NULL
            )
            """,
            (FIXTURE_FOOD_ID,),
        )
        connection.commit()
    finally:
        connection.close()


class CoreApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "core.sqlite"
        create_fixture_database(self.database_path)
        self.app = create_app(self.database_path, cors_origins=())

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_health_and_release_metadata(self) -> None:
        with TestClient(self.app) as client:
            health = client.get("/health")
            release = client.get("/v1/releases/current")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(
            health.json(),
            {
                "status": "ok",
                "api_version": "0.2.0",
                "artifact_version": "0.0.1-test",
                "release_ids": ["fixture-release"],
            },
        )
        self.assertEqual(release.status_code, 200)
        payload = release.json()
        self.assertEqual(payload["artifact_version"], "0.0.1-test")
        self.assertEqual(payload["datasets"][0]["license"]["identifier"], "CC0-1.0")
        self.assertEqual(payload["datasets"][0]["coverage"]["start"], "2021-01-01")

    def test_search_is_ranked_paginated_and_excludes_nonsearchable_foods(self) -> None:
        with TestClient(self.app) as client:
            first_page = client.get("/v1/foods/search", params={"q": "apple", "limit": 1})
            second_page = client.get(
                "/v1/foods/search",
                params={"q": "apple", "limit": 1, "offset": 1},
            )

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page.json()["total"], 2)
        self.assertEqual(first_page.json()["items"][0]["name"], "Apple, raw")
        self.assertEqual(first_page.json()["items"][0]["quality"]["status"], "complete")
        self.assertEqual(second_page.json()["items"][0]["name"], "Apple, NFS")

    def test_search_treats_fts_operators_as_text_and_rejects_punctuation_only(self) -> None:
        with TestClient(self.app) as client:
            safe = client.get("/v1/foods/search", params={"q": 'apple"* OR shell'})
            invalid = client.get("/v1/foods/search", params={"q": "---"})

        self.assertEqual(safe.status_code, 200)
        self.assertEqual(safe.json()["match_mode"], "partial_terms")
        self.assertEqual(safe.json()["matched_terms"], ["apple"])
        self.assertEqual(safe.json()["total"], 2)
        self.assertEqual(invalid.status_code, 422)
        self.assertIn("searchable", invalid.json()["detail"])

    def test_search_falls_back_to_the_most_selective_available_terms(self) -> None:
        with TestClient(self.app) as client:
            response = client.get("/v1/foods/search", params={"q": "red apple"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["match_mode"], "partial_terms")
        self.assertEqual(response.json()["matched_terms"], ["apple"])
        self.assertEqual(response.json()["items"][0]["name"], "Apple, raw")

    def test_food_detail_returns_nutrients_portions_and_provenance(self) -> None:
        with TestClient(self.app) as client:
            response = client.get(f"/v1/foods/{FIXTURE_FOOD_ID}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["name"], "Apple, raw")
        self.assertEqual(payload["source"]["source_food_id"], "100")
        self.assertEqual([row["name"] for row in payload["nutrients"]], ["Energy", "Protein"])
        self.assertEqual(payload["nutrients"][0]["basis"], "per_100g_edible_portion")
        self.assertEqual(payload["portions"][0]["description"], "1 medium")
        self.assertEqual(payload["portions"][0]["gram_weight"], 182.0)

    def test_unknown_food_returns_not_found_and_excluded_food_remains_auditable(self) -> None:
        with TestClient(self.app) as client:
            missing = client.get("/v1/foods/does-not-exist")
            excluded = client.get("/v1/foods/food-excluded")

        self.assertEqual(missing.status_code, 404)
        self.assertEqual(excluded.status_code, 200)
        self.assertEqual(excluded.json()["quality"]["status"], "excluded")
        self.assertEqual(excluded.json()["nutrients"], [])

    def test_openapi_contains_the_versioned_contract(self) -> None:
        with TestClient(self.app) as client:
            schema = client.get("/openapi.json").json()

        self.assertEqual(schema["info"]["version"], "0.2.0")
        self.assertIn("/v1/foods/search", schema["paths"])
        self.assertIn("/v1/foods/{food_id}", schema["paths"])

    def test_configured_browser_origin_can_call_get_endpoints(self) -> None:
        app = create_app(self.database_path, cors_origins=("https://app.example.test",))
        with TestClient(app) as client:
            response = client.options(
                "/v1/foods/search",
                headers={
                    "Origin": "https://app.example.test",
                    "Access-Control-Request-Method": "GET",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "https://app.example.test")

    def test_repository_opens_database_read_only(self) -> None:
        repository = CoreRepository(self.database_path)
        with repository.connect() as connection:
            with self.assertRaisesRegex(sqlite3.OperationalError, "readonly"):
                connection.execute("DELETE FROM foods")

    def test_missing_database_fails_during_startup(self) -> None:
        app = create_app(Path(self.temp_dir.name) / "missing.sqlite", cors_origins=())
        with self.assertRaisesRegex(DatabaseConfigurationError, "does not exist"):
            with TestClient(app):
                pass


@unittest.skipUnless(
    default_database_path().is_file() and os.environ.get("OPENNUTRI_SKIP_REAL_RELEASE_TEST") != "1",
    "Local FNDDS release is not present",
)
class RealCoreReleaseTests(unittest.TestCase):
    def test_real_release_serves_red_lentils_from_sr_legacy(self) -> None:
        app = create_app(default_database_path(), cors_origins=())
        with TestClient(app) as client:
            search = client.get("/v1/foods/search", params={"q": "red lentils", "limit": 5})
            self.assertEqual(search.status_code, 200)
            self.assertEqual(search.json()["match_mode"], "all_terms")
            first = search.json()["items"][0]
            self.assertEqual(first["name"], "Lentils, pink or red, raw")

            detail = client.get(f"/v1/foods/{first['food_id']}")
            self.assertEqual(detail.status_code, 200)
            payload = detail.json()
            self.assertGreater(len(payload["nutrients"]), 70)
            self.assertEqual(payload["source"]["release_id"], "usda-sr-legacy-2018-04")

    def test_real_release_prioritizes_foundation_lentils(self) -> None:
        app = create_app(default_database_path(), cors_origins=())
        with TestClient(app) as client:
            search = client.get("/v1/foods/search", params={"q": "lentils", "limit": 5})

        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json()["items"][0]["name"], "Lentils, dry")
        self.assertEqual(
            search.json()["items"][0]["source"]["release_id"],
            "usda-foundation-2025-12-18",
        )

    def test_every_real_food_profile_conforms_to_the_response_contract(self) -> None:
        repository = CoreRepository(default_database_path())
        with repository.connect() as connection:
            food_ids = [row[0] for row in connection.execute("SELECT food_id FROM foods")]

        for food_id in food_ids:
            payload = repository.food_detail(food_id)
            self.assertIsNotNone(payload)
            FoodDetailResponse.model_validate(payload)

        self.assertEqual(len(food_ids), 13_590)


if __name__ == "__main__":
    unittest.main()
