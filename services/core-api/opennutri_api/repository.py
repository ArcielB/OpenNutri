from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from itertools import combinations
from pathlib import Path
from typing import Any, Iterator


API_VERSION = "0.4.0"
REQUIRED_TABLES = {
    "dataset_releases",
    "foods",
    "food_categories",
    "nutrients",
    "food_nutrients",
    "portions",
    "edible_portion_factors",
    "food_search_terms",
    "food_search",
    "food_source_term_search",
}
SEARCH_TOKEN_RE = re.compile(r"[^\W_]+(?:['-][^\W_]+)*", re.UNICODE)


class DatabaseConfigurationError(RuntimeError):
    """Raised when the configured Core database cannot safely serve the API."""


class InvalidSearchQuery(ValueError):
    """Raised when a query has no searchable terms."""


class CoreRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if not self.database_path.is_file():
            raise DatabaseConfigurationError(
                f"OpenNutri Core database does not exist: {self.database_path}"
            )
        uri = f"{self.database_path.as_uri()}?mode=ro&immutable=1"
        try:
            connection = sqlite3.connect(uri, uri=True, check_same_thread=False)
        except sqlite3.Error as exc:
            raise DatabaseConfigurationError(
                f"Could not open OpenNutri Core database read-only: {self.database_path}"
            ) from exc
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        try:
            yield connection
        finally:
            connection.close()

    def validate(self) -> None:
        with self.connect() as connection:
            quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
            if quick_check != "ok":
                raise DatabaseConfigurationError(f"SQLite quick_check failed: {quick_check}")

            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
                )
            }
            missing_tables = sorted(REQUIRED_TABLES - tables)
            if missing_tables:
                raise DatabaseConfigurationError(
                    f"OpenNutri Core database is missing required tables: {', '.join(missing_tables)}"
                )

            release_count = connection.execute("SELECT COUNT(*) FROM dataset_releases").fetchone()[0]
            if release_count < 1:
                raise DatabaseConfigurationError("OpenNutri Core database has no dataset release")

    def health(self) -> dict[str, Any]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT release_id, artifact_version
                FROM dataset_releases
                ORDER BY release_date DESC, release_id
                """
            ).fetchall()
        artifact_versions = {row["artifact_version"] for row in rows}
        if len(artifact_versions) != 1:
            raise DatabaseConfigurationError(
                "All datasets in one API artifact must have the same artifact_version"
            )
        return {
            "status": "ok",
            "api_version": API_VERSION,
            "artifact_version": artifact_versions.pop(),
            "release_ids": [row["release_id"] for row in rows],
        }

    def current_release(self) -> dict[str, Any]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT release_id,
                       artifact_version,
                       publisher,
                       dataset_name,
                       data_type,
                       release_date,
                       coverage_start,
                       coverage_end,
                       download_url,
                       archive_sha256,
                       source_tree_sha256,
                       license,
                       license_url
                FROM dataset_releases
                ORDER BY release_date DESC, release_id
                """
            ).fetchall()

        artifact_versions = {row["artifact_version"] for row in rows}
        if len(artifact_versions) != 1:
            raise DatabaseConfigurationError(
                "All datasets in one API artifact must have the same artifact_version"
            )
        return {
            "artifact_version": artifact_versions.pop(),
            "datasets": [self._release_payload(row) for row in rows],
        }

    def search_foods(self, query: str, *, limit: int, offset: int) -> dict[str, Any]:
        normalized_query = unicodedata.normalize("NFKC", query).strip()
        tokens = list(dict.fromkeys(SEARCH_TOKEN_RE.findall(normalized_query.casefold())))
        if not tokens:
            raise InvalidSearchQuery("Query must contain at least one searchable letter or number")

        with self.connect() as connection:
            fts_query, matched_terms, match_mode, total = self._resolve_search_terms(
                connection, tokens
            )
            rows = connection.execute(
                """
                WITH primary_matches AS (
                    SELECT food_id,
                           bm25(food_search, 0.0, 8.0, 3.0, 1.0) AS relevance
                    FROM food_search
                    WHERE food_search MATCH :fts_query
                ),
                source_matches AS (
                    SELECT food_id,
                           term,
                           term_type,
                           bm25(food_source_term_search, 0.0, 6.0, 0.0) AS relevance
                    FROM food_source_term_search
                    WHERE food_source_term_search MATCH :fts_query
                ),
                ranked_source_matches AS (
                    SELECT food_id,
                           term,
                           term_type,
                           relevance,
                           row_number() OVER (
                               PARTITION BY food_id
                               ORDER BY
                                   CASE term_type
                                       WHEN 'common_name' THEN 0
                                       WHEN 'foodon_label' THEN 1
                                       ELSE 2
                                   END,
                                   CASE WHEN lower(term) = lower(:query) THEN 0 ELSE 1 END,
                                   relevance,
                                   length(term),
                                   term
                           ) AS source_rank
                    FROM source_matches
                ),
                best_source_match AS (
                    SELECT food_id, term, term_type, relevance
                    FROM ranked_source_matches
                    WHERE source_rank = 1
                ),
                candidate_ids AS (
                    SELECT food_id FROM primary_matches
                    UNION
                    SELECT food_id FROM best_source_match
                )
                SELECT f.food_id,
                       f.display_name,
                       f.category_id,
                       f.category_name,
                       f.release_id,
                       r.publisher,
                       r.dataset_name,
                       f.data_type,
                       f.source_food_id,
                       f.source_food_code,
                       f.quality_status,
                       f.ambiguity_flags,
                       f.nutrient_count,
                       f.portion_count,
                       CASE
                           WHEN lower(f.display_name) = lower(:query) THEN 0
                           WHEN lower(f.display_name) LIKE lower(:query) || '%' THEN 1
                           WHEN source.term_type IN ('common_name', 'foodon_label') THEN 2
                           WHEN source.term_type = 'additional_description' THEN 3
                           ELSE 4
                       END AS match_tier,
                       coalesce(primary_match.relevance, source.relevance) AS relevance,
                       CASE
                           WHEN primary_match.food_id IS NOT NULL THEN 'primary_name'
                           ELSE 'source_term'
                       END AS matched_via,
                       CASE
                           WHEN primary_match.food_id IS NOT NULL THEN f.display_name
                           ELSE source.term
                       END AS matched_term,
                       CASE
                           WHEN primary_match.food_id IS NOT NULL THEN 'primary_name'
                           ELSE source.term_type
                       END AS matched_term_type
                FROM candidate_ids AS candidates
                JOIN foods AS f ON f.food_id = candidates.food_id
                JOIN dataset_releases AS r ON r.release_id = f.release_id
                LEFT JOIN primary_matches AS primary_match
                    ON primary_match.food_id = f.food_id
                LEFT JOIN best_source_match AS source
                    ON source.food_id = f.food_id
                ORDER BY match_tier,
                         f.search_priority DESC,
                         relevance,
                         length(f.display_name),
                         f.display_name,
                         f.food_id
                LIMIT :limit OFFSET :offset
                """,
                {
                    "fts_query": fts_query,
                    "query": normalized_query,
                    "limit": limit,
                    "offset": offset,
                },
            ).fetchall()

        return {
            "query": normalized_query,
            "match_mode": match_mode,
            "matched_terms": matched_terms,
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [self._search_item_payload(row) for row in rows],
        }

    @staticmethod
    def _resolve_search_terms(
        connection: sqlite3.Connection,
        tokens: list[str],
    ) -> tuple[str, list[str], str, int]:
        def query_for(terms: tuple[str, ...] | list[str]) -> str:
            return " ".join(f'"{term}"*' for term in terms)

        def count_for(terms: tuple[str, ...] | list[str]) -> int:
            return connection.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT food_id
                    FROM food_search
                    WHERE food_search MATCH :query
                    UNION
                    SELECT food_id
                    FROM food_source_term_search
                    WHERE food_source_term_search MATCH :query
                )
                """,
                {"query": query_for(terms)},
            ).fetchone()[0]

        total = count_for(tokens)
        if total or len(tokens) == 1:
            return query_for(tokens), tokens, "all_terms", total

        # Prefer the largest useful subset, then the most selective one. Limiting
        # fallback to six terms keeps adversarially long queries inexpensive.
        fallback_tokens = tokens[:6]
        for size in range(len(fallback_tokens) - 1, 0, -1):
            candidates: list[tuple[int, tuple[str, ...]]] = []
            for terms in combinations(fallback_tokens, size):
                count = count_for(terms)
                if count:
                    candidates.append((count, terms))
            if candidates:
                count, terms = min(candidates, key=lambda item: (item[0], item[1]))
                selected = list(terms)
                return query_for(selected), selected, "partial_terms", count

        return query_for(tokens), tokens, "all_terms", 0

    def food_detail(self, food_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            food = connection.execute(
                """
                SELECT f.food_id,
                       f.display_name,
                       f.original_description,
                       f.category_id,
                       f.category_name,
                       f.release_id,
                       r.publisher,
                       r.dataset_name,
                       f.data_type,
                       f.source_food_id,
                       f.source_food_code,
                       f.quality_status,
                       f.ambiguity_flags,
                       f.nutrient_count,
                       f.portion_count,
                       f.publication_date,
                       f.coverage_start,
                       f.coverage_end
                FROM foods AS f
                JOIN dataset_releases AS r ON r.release_id = f.release_id
                WHERE f.food_id = ?
                """,
                (food_id,),
            ).fetchone()
            if food is None:
                return None

            nutrients = connection.execute(
                """
                SELECT n.nutrient_id,
                       n.source_nutrient_id,
                       n.nutrient_number,
                       n.name,
                       fn.amount,
                       fn.unit,
                       fn.basis,
                       fn.source_row_id,
                       fn.derivation_id,
                       fn.data_points,
                       fn.minimum,
                       fn.maximum,
                       fn.median,
                       fn.footnote,
                       fn.min_year_acquired
                FROM food_nutrients AS fn
                JOIN nutrients AS n ON n.nutrient_id = fn.nutrient_id
                WHERE fn.food_id = ?
                ORDER BY n.sort_rank, n.nutrient_number, n.nutrient_id
                """,
                (food_id,),
            ).fetchall()
            portions = connection.execute(
                """
                SELECT portion_id,
                       source_portion_id,
                       sequence_number,
                       portion_description,
                       gram_weight,
                       amount,
                       measure_unit_id,
                       measure_unit_name,
                       modifier,
                       data_points,
                       footnote,
                       min_year_acquired
                FROM portions
                WHERE food_id = ?
                ORDER BY sequence_number IS NULL, sequence_number, portion_id
                """,
                (food_id,),
            ).fetchall()
            weight_factors = connection.execute(
                """
                SELECT factor_id,
                       factor_type,
                       edible_fraction,
                       refuse_percent,
                       refuse_description,
                       source_dataset,
                       source_url,
                       source_food_code,
                       source_refuse_percent,
                       derivation,
                       review_status,
                       is_usable,
                       notes
                FROM edible_portion_factors
                WHERE food_id = ?
                ORDER BY is_usable DESC, factor_id
                """,
                (food_id,),
            ).fetchall()

        return {
            "food_id": food["food_id"],
            "name": food["display_name"],
            "original_description": food["original_description"],
            "category": self._category_payload(food),
            "source": self._source_payload(food),
            "quality": self._quality_payload(food),
            "publication_date": food["publication_date"],
            "coverage": {
                "start": food["coverage_start"],
                "end": food["coverage_end"],
            },
            "nutrients": [dict(row) for row in nutrients],
            "portions": [
                {
                    "portion_id": row["portion_id"],
                    "source_portion_id": row["source_portion_id"],
                    "sequence_number": row["sequence_number"],
                    "description": row["portion_description"],
                    "gram_weight": row["gram_weight"],
                    "amount": row["amount"],
                    "measure_unit_id": row["measure_unit_id"],
                    "measure_unit_name": row["measure_unit_name"],
                    "modifier": row["modifier"],
                    "data_points": row["data_points"],
                    "footnote": row["footnote"],
                    "min_year_acquired": row["min_year_acquired"],
                }
                for row in portions
            ],
            "weight_factors": [
                {
                    "factor_id": row["factor_id"],
                    "factor_type": row["factor_type"],
                    "edible_fraction": row["edible_fraction"],
                    "refuse_percent": row["refuse_percent"],
                    "refuse_description": row["refuse_description"],
                    "source_dataset": row["source_dataset"],
                    "source_url": row["source_url"],
                    "source_food_code": row["source_food_code"],
                    "source_refuse_percent": row["source_refuse_percent"],
                    "derivation": row["derivation"],
                    "review_status": row["review_status"],
                    "is_usable": bool(row["is_usable"]),
                    "notes": row["notes"],
                }
                for row in weight_factors
            ],
        }

    @staticmethod
    def _release_payload(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "release_id": row["release_id"],
            "artifact_version": row["artifact_version"],
            "publisher": row["publisher"],
            "dataset_name": row["dataset_name"],
            "data_type": row["data_type"],
            "release_date": row["release_date"],
            "coverage": {"start": row["coverage_start"], "end": row["coverage_end"]},
            "download_url": row["download_url"],
            "archive_sha256": row["archive_sha256"],
            "source_tree_sha256": row["source_tree_sha256"],
            "license": {"identifier": row["license"], "url": row["license_url"]},
        }

    @classmethod
    def _search_item_payload(cls, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "food_id": row["food_id"],
            "name": row["display_name"],
            "category": cls._category_payload(row),
            "source": cls._source_payload(row),
            "quality": cls._quality_payload(row),
            "matched_via": row["matched_via"],
            "matched_term": row["matched_term"],
            "matched_term_type": row["matched_term_type"],
        }

    @staticmethod
    def _category_payload(row: sqlite3.Row) -> dict[str, str]:
        return {"category_id": row["category_id"], "name": row["category_name"]}

    @staticmethod
    def _source_payload(row: sqlite3.Row) -> dict[str, str]:
        return {
            "release_id": row["release_id"],
            "publisher": row["publisher"],
            "dataset_name": row["dataset_name"],
            "data_type": row["data_type"],
            "source_food_id": row["source_food_id"],
            "source_food_code": row["source_food_code"],
        }

    @staticmethod
    def _quality_payload(row: sqlite3.Row) -> dict[str, Any]:
        flags = json.loads(row["ambiguity_flags"])
        if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
            raise DatabaseConfigurationError("Food ambiguity_flags must be a JSON string array")
        return {
            "status": row["quality_status"],
            "ambiguity_flags": flags,
            "nutrient_count": row["nutrient_count"],
            "portion_count": row["portion_count"],
        }
