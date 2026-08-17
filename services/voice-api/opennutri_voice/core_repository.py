from __future__ import annotations

import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


TOKEN_RE = re.compile(r"[^\W_]+(?:['-][^\W_]+)*", re.UNICODE)
UNSPECIFIED_TOKENS = {"nfs", "ns", "unspecified"}


class CoreDatabaseError(RuntimeError):
    pass


class CoreFoodRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if not self.database_path.is_file():
            raise CoreDatabaseError(f"Core database does not exist: {self.database_path}")
        connection = sqlite3.connect(
            f"{self.database_path.as_uri()}?mode=ro&immutable=1",
            uri=True,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        try:
            yield connection
        finally:
            connection.close()

    def validate(self) -> None:
        required = {
            "dataset_releases",
            "foods",
            "portions",
            "edible_portion_factors",
            "food_search",
            "food_source_term_search",
        }
        with self.connect() as connection:
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise CoreDatabaseError("Core database integrity check failed")
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
                )
            }
        missing = sorted(required - tables)
        if missing:
            raise CoreDatabaseError(f"Core database is missing: {', '.join(missing)}")

    def artifact_version(self) -> str:
        with self.connect() as connection:
            versions = {
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT artifact_version FROM dataset_releases"
                )
            }
        if len(versions) != 1:
            raise CoreDatabaseError("Core database has inconsistent artifact versions")
        return versions.pop()

    @staticmethod
    def _fts_query(query: str) -> str:
        normalized = unicodedata.normalize("NFKC", query).casefold()
        tokens = list(dict.fromkeys(TOKEN_RE.findall(normalized)))[:10]
        if not tokens:
            return ""
        terms = []
        for token in tokens:
            singular = token
            if token.endswith("ies") and len(token) > 3:
                singular = f"{token[:-3]}y"
            elif token.endswith("s") and not token.endswith("ss") and len(token) > 2:
                singular = token[:-1]
            if singular == token:
                terms.append(f'"{token}"*')
            else:
                terms.append(f'("{token}"* OR "{singular}"*)')
        return " AND ".join(terms)

    def primary_search(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        fts_query = self._fts_query(query)
        if not fts_query:
            return []
        fetch_limit = min(max(limit * 5, limit), 50)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT f.food_id,
                       f.display_name,
                       f.category_name,
                       f.quality_status,
                       f.release_id,
                       bm25(food_search, 0.0, 8.0, 3.0, 1.0) AS relevance,
                       CASE
                           WHEN lower(f.display_name) = lower(:query) THEN 0
                           WHEN lower(f.display_name) LIKE lower(:query) || '%' THEN 1
                           ELSE 2
                       END AS match_tier
                FROM food_search
                JOIN foods AS f ON f.food_id = food_search.food_id
                WHERE food_search MATCH :fts_query
                ORDER BY match_tier,
                         f.search_priority DESC,
                         relevance,
                         length(f.display_name),
                         f.food_id
                LIMIT :fetch_limit
                """,
                {
                    "query": query.strip(),
                    "fts_query": fts_query,
                    "fetch_limit": fetch_limit,
                },
            ).fetchall()
        ranked = sorted(
            enumerate(rows),
            key=lambda indexed: self._lexical_rank(
                query,
                indexed[1]["display_name"],
                indexed[0],
            ),
        )
        return [dict(row) for _, row in ranked[:limit]]

    @staticmethod
    def _singular_token(token: str) -> str:
        if token in UNSPECIFIED_TOKENS:
            return token
        if token.endswith("ies") and len(token) > 3:
            return f"{token[:-3]}y"
        if token.endswith("s") and not token.endswith("ss") and len(token) > 2:
            return token[:-1]
        return token

    @classmethod
    def _head_matches_query(cls, query: str, display_name: str) -> bool:
        query_tokens = cls._lexical_tokens(query)
        display_tokens = TOKEN_RE.findall(
            unicodedata.normalize("NFKC", display_name).casefold()
        )
        return bool(
            display_tokens
            and cls._singular_token(display_tokens[0]) in query_tokens
        )

    @classmethod
    def _lexical_tokens(cls, value: str) -> set[str]:
        return {
            cls._singular_token(token)
            for token in TOKEN_RE.findall(
                unicodedata.normalize("NFKC", value).casefold()
            )
        }

    @classmethod
    def _lexical_rank(
        cls,
        query: str,
        display_name: str,
        original_rank: int,
    ) -> tuple[bool, bool, int, bool, int]:
        query_tokens = cls._lexical_tokens(query)
        display_tokens = cls._lexical_tokens(display_name)
        covers_query = bool(query_tokens and query_tokens.issubset(display_tokens))
        extra_tokens = (
            len(display_tokens - query_tokens) if covers_query else 10_000
        )
        return (
            not cls._head_matches_query(query, display_name),
            not covers_query,
            extra_tokens,
            not bool(display_tokens.intersection(UNSPECIFIED_TOKENS)),
            original_rank,
        )

    def source_term_search(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        fts_query = self._fts_query(query)
        if not fts_query:
            return []
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT f.food_id,
                       f.display_name,
                       f.category_name,
                       f.quality_status,
                       f.release_id,
                       source.term AS matched_term,
                       source.term_type AS matched_term_type,
                       bm25(food_source_term_search, 0.0, 6.0, 0.0) AS relevance
                FROM food_source_term_search AS source
                JOIN foods AS f ON f.food_id = source.food_id
                WHERE food_source_term_search MATCH :fts_query
                ORDER BY
                    CASE source.term_type
                        WHEN 'common_name' THEN 0
                        WHEN 'foodon_label' THEN 1
                        ELSE 2
                    END,
                    CASE WHEN lower(source.term) = lower(:query) THEN 0 ELSE 1 END,
                    f.search_priority DESC,
                    relevance,
                    length(f.display_name),
                    f.food_id
                LIMIT :limit
                """,
                {"query": query.strip(), "fts_query": fts_query, "limit": limit},
            ).fetchall()
        return [dict(row) for row in rows]

    def hydrate_candidates(self, food_ids: list[str]) -> dict[str, dict[str, Any]]:
        unique_ids = list(dict.fromkeys(food_ids))
        if not unique_ids:
            return {}
        placeholders = ",".join("?" for _ in unique_ids)
        with self.connect() as connection:
            foods = connection.execute(
                f"""
                SELECT f.food_id,
                       f.display_name,
                       f.category_name,
                       f.quality_status,
                       f.release_id,
                       EXISTS (
                           SELECT 1
                           FROM edible_portion_factors AS factor
                           WHERE factor.food_id = f.food_id AND factor.is_usable = 1
                       ) AS has_usable_weight_factor
                FROM foods AS f
                WHERE f.is_searchable = 1 AND f.food_id IN ({placeholders})
                """,
                unique_ids,
            ).fetchall()
            portions = connection.execute(
                f"""
                SELECT portion_id, food_id, portion_description, gram_weight, amount
                FROM portions
                WHERE food_id IN ({placeholders})
                ORDER BY food_id, sequence_number IS NULL, sequence_number, portion_id
                """,
                unique_ids,
            ).fetchall()
        portions_by_food: dict[str, list[dict[str, Any]]] = {}
        for row in portions:
            portions_by_food.setdefault(row["food_id"], []).append(
                {
                    "portion_id": row["portion_id"],
                    "description": row["portion_description"],
                    "gram_weight": row["gram_weight"],
                    "amount": row["amount"],
                }
            )
        return {
            row["food_id"]: {
                "food_id": row["food_id"],
                "name": row["display_name"],
                "category": row["category_name"],
                "quality_status": row["quality_status"],
                "source_release_id": row["release_id"],
                "portions": portions_by_food.get(row["food_id"], []),
                "has_usable_weight_factor": bool(row["has_usable_weight_factor"]),
            }
            for row in foods
        }

    def searchable_food_rows(self) -> Iterator[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT f.food_id,
                       f.display_name,
                       f.category_name,
                       f.original_description,
                       group_concat(t.term, ' | ') AS source_terms
                FROM foods AS f
                LEFT JOIN food_search_terms AS t ON t.food_id = f.food_id
                WHERE f.is_searchable = 1
                GROUP BY f.food_id
                ORDER BY f.food_id
                """
            ).fetchall()
        for row in rows:
            yield dict(row)
