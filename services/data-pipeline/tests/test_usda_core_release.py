from __future__ import annotations

import sqlite3
import unittest

from opennutri_core.fndds import DEFAULT_SOURCE_DIR, _build_source_audit
from opennutri_core.usda import (
    DEFAULT_FOUNDATION_SOURCE_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SR28_SOURCE_DIR,
    DEFAULT_SR_LEGACY_SOURCE_DIR,
    FOUNDATION,
    SR_LEGACY,
    _basic_food_rows,
    _build_basic_audit,
    _build_refuse_factor_audit,
    _food_search_term_rows,
    _is_useful_search_term,
)


class UsdaSourceAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.foundation = _build_basic_audit(
            FOUNDATION,
            DEFAULT_FOUNDATION_SOURCE_DIR,
            strict_official=True,
        )
        cls.sr_legacy = _build_basic_audit(
            SR_LEGACY,
            DEFAULT_SR_LEGACY_SOURCE_DIR,
            strict_official=True,
        )
        cls.refuse_factors = _build_refuse_factor_audit(
            cls.sr_legacy,
            DEFAULT_SR28_SOURCE_DIR,
            strict_official=True,
        )
        cls.fndds = _build_source_audit(DEFAULT_SOURCE_DIR)
        cls.search_terms = list(
            _food_search_term_rows(
                DEFAULT_SOURCE_DIR,
                cls.fndds,
                [cls.foundation, cls.sr_legacy],
            )
        )

    def test_verified_source_counts_and_rejections(self) -> None:
        self.assertEqual(len(self.foundation.member_rows), 365)
        self.assertEqual(self.foundation.accepted_nutrient_rows, 15_541)
        self.assertEqual(self.foundation.rejected_nutrient_rows, 37)
        self.assertEqual(len(self.sr_legacy.member_rows), 7_793)
        self.assertEqual(self.sr_legacy.accepted_nutrient_rows, 644_125)
        self.assertEqual(self.sr_legacy.rejected_nutrient_rows, 0)

    def test_red_lentils_are_complete_and_searchable(self) -> None:
        red_lentils = next(
            row
            for row in _basic_food_rows(self.sr_legacy)
            if row["source_food_id"] == "174284"
        )
        self.assertEqual(red_lentils["display_name"], "Lentils, pink or red, raw")
        self.assertEqual(red_lentils["quality_status"], "complete")
        self.assertTrue(red_lentils["is_searchable"])

    def test_new_atwater_energy_codes_count_as_foundation_energy(self) -> None:
        apple = next(
            row
            for row in _basic_food_rows(self.foundation)
            if row["source_food_id"] == "1750339"
        )
        self.assertEqual(apple["display_name"], "Apples, red delicious, with skin, raw")
        self.assertEqual(apple["quality_status"], "complete")
        self.assertTrue(apple["is_searchable"])

    def test_sr28_refuse_factors_are_source_linked_and_audited(self) -> None:
        self.assertEqual(len(self.refuse_factors.factors), 1_943)
        self.assertEqual(self.refuse_factors.usable_factor_count, 1_937)
        self.assertEqual(self.refuse_factors.raw_factor_count, 885)
        self.assertEqual(self.refuse_factors.usable_raw_factor_count, 883)
        self.assertEqual(self.refuse_factors.reviewed_food_codes, ["05066"])
        self.assertEqual(
            self.refuse_factors.conflict_food_codes,
            ["05069", "05094", "05688", "05689", "05691", "05692"],
        )

    def test_raw_skin_on_drumstick_uses_reviewed_bone_fraction(self) -> None:
        factor = next(
            row
            for row in self.refuse_factors.factors
            if row["source_food_code"] == "05066"
        )
        self.assertEqual(factor["food_id"], "b03885ae-f0a4-53cb-85c8-c61cf349bbd4")
        self.assertEqual(factor["source_refuse_percent"], 66.0)
        self.assertEqual(factor["refuse_percent"], 33.0)
        self.assertEqual(factor["edible_fraction"], 0.67)
        self.assertEqual(factor["review_status"], "reviewed")
        self.assertTrue(factor["is_usable"])

    def test_search_terms_are_filtered_deduplicated_and_provenance_preserving(self) -> None:
        self.assertEqual(len(self.search_terms), 10_953)
        keys = [(row["food_id"], row["normalized_term"]) for row in self.search_terms]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(len(keys), len(set(keys)))
        self.assertFalse(
            _is_useful_search_term(
                "any source",
                primary_name="Milk, whole",
                term_type="additional_description",
            )
        )
        self.assertFalse(
            _is_useful_search_term(
                "12345",
                primary_name="Milk, whole",
                term_type="common_name",
            )
        )
        hot_dog = next(
            row
            for row in self.search_terms
            if row["normalized_term"] == "hot dog, wiener, frank"
        )
        self.assertEqual(hot_dog["term_type"], "common_name")
        self.assertIn('"source_row_id"', hot_dog["provenance_json"])


@unittest.skipUnless(
    (DEFAULT_OUTPUT_DIR / "opennutri-core.sqlite").is_file(),
    "Local combined USDA artifact is not present",
)
class CombinedArtifactTests(unittest.TestCase):
    def test_artifact_counts_and_integrity(self) -> None:
        connection = sqlite3.connect(DEFAULT_OUTPUT_DIR / "opennutri-core.sqlite")
        try:
            self.assertEqual(connection.execute("PRAGMA quick_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM foods").fetchone()[0], 13_590)
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM food_nutrients").fetchone()[0],
                1_012_681,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM dataset_releases").fetchone()[0],
                3,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM edible_portion_factors").fetchone()[0],
                1_943,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM food_search_terms").fetchone()[0],
                10_953,
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
