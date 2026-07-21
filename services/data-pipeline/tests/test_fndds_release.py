from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import pyarrow.parquet as pq


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opennutri_core.fndds import DatasetValidationError, build_fndds_release


def write_csv(path: Path, columns: list[str], rows: list[list[object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(rows)


def build_fixture(source_dir: Path) -> None:
    write_csv(
        source_dir / "food.csv",
        ["fdc_id", "data_type", "description", "food_category_id", "publication_date"],
        [
            ["1", "survey_fndds_food", "Milk, whole", "1002", "2024-10-31"],
            ["2", "survey_fndds_food", "Yogurt, NFS", "1002", "2024-10-31"],
            ["3", "survey_fndds_food", "Milk, human", "1002", "2024-10-31"],
        ],
    )
    write_csv(
        source_dir / "survey_fndds_food.csv",
        ["fdc_id", "food_code", "wweia_category_number", "start_date", "end_date"],
        [
            ["1", "11100000", "1002", "2021-01-01", "2023-12-31"],
            ["2", "11110000", "1002", "2021-01-01", "2023-12-31"],
            ["3", "11000000", "1002", "2021-01-01", "2023-12-31"],
        ],
    )
    write_csv(
        source_dir / "nutrient.csv",
        ["id", "name", "unit_name", "nutrient_nbr", "rank"],
        [
            ["1008", "Energy", "KCAL", "208", "300"],
            ["1003", "Protein", "G", "203", "600"],
            ["1004", "Total lipid (fat)", "G", "204", "800"],
            ["1005", "Carbohydrate, by difference", "G", "205", "1110"],
        ],
    )
    nutrient_columns = [
        "id",
        "fdc_id",
        "nutrient_id",
        "amount",
        "data_points",
        "derivation_id",
        "min",
        "max",
        "median",
        "footnote",
        "min_year_acquired",
    ]
    write_csv(
        source_dir / "food_nutrient.csv",
        nutrient_columns,
        [
            ["1", "1", "208", "61", "", "", "", "", "", "", ""],
            ["2", "1", "203", "3.15", "", "", "", "", "", "", ""],
            ["3", "1", "204", "3.25", "", "", "", "", "", "", ""],
            ["4", "1", "205", "4.8", "", "", "", "", "", "", ""],
            ["5", "2", "208", "72", "", "", "", "", "", "", ""],
            ["6", "2", "203", "4.0", "", "", "", "", "", "", ""],
            ["7", "2", "204", "3.0", "", "", "", "", "", "", ""],
            ["8", "2", "205", "8.0", "", "", "", "", "", "", ""],
        ],
    )
    write_csv(
        source_dir / "measure_unit.csv",
        ["id", "name"],
        [["9999", "undetermined"]],
    )
    write_csv(
        source_dir / "food_portion.csv",
        [
            "id",
            "fdc_id",
            "seq_num",
            "amount",
            "measure_unit_id",
            "portion_description",
            "modifier",
            "gram_weight",
            "data_points",
            "footnote",
            "min_year_acquired",
        ],
        [
            ["10", "1", "1", "", "9999", "1 cup", "10000", "244", "", "", ""],
            ["11", "2", "1", "", "9999", "Quantity not specified", "90000", "0", "", "", ""],
        ],
    )
    write_csv(
        source_dir / "wweia_food_category.csv",
        ["wweia_food_category", "wweia_food_category_description"],
        [["1002", "Milk, whole"]],
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FnddsReleaseTests(unittest.TestCase):
    def test_build_maps_nutrient_numbers_and_publishes_searchable_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "source"
            output_dir = root / "release"
            source_dir.mkdir()
            build_fixture(source_dir)

            report = build_fndds_release(
                source_dir,
                output_dir,
                strict_official=False,
            )

            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["output_rows"]["foods"], 3)
            self.assertEqual(report["output_rows"]["food_nutrients"], 8)
            self.assertEqual(report["output_rows"]["portions"], 1)
            self.assertEqual(report["measured"]["rejected_portions"], 1)

            connection = sqlite3.connect(output_dir / "opennutri-fndds.sqlite")
            connection.row_factory = sqlite3.Row
            try:
                statuses = {
                    row["source_food_id"]: (row["quality_status"], row["is_searchable"])
                    for row in connection.execute(
                        "SELECT source_food_id, quality_status, is_searchable FROM foods"
                    )
                }
                self.assertEqual(statuses["1"], ("complete", 1))
                self.assertEqual(statuses["2"], ("ambiguous", 1))
                self.assertEqual(statuses["3"], ("excluded", 0))

                protein_mapping = connection.execute(
                    """
                    SELECT n.source_nutrient_id, n.name
                    FROM source_nutrient_mappings m
                    JOIN nutrients n ON n.nutrient_id = m.nutrient_id
                    WHERE m.source_nutrient_code = '203'
                    """
                ).fetchone()
                self.assertEqual(dict(protein_mapping), {"source_nutrient_id": "1003", "name": "Protein"})

                search_result = connection.execute(
                    """
                    SELECT f.source_food_id, f.display_name
                    FROM food_search s
                    JOIN foods f ON f.food_id = s.food_id
                    WHERE food_search MATCH 'yogurt'
                    """
                ).fetchone()
                self.assertEqual(dict(search_result), {"source_food_id": "2", "display_name": "Yogurt, NFS"})
            finally:
                connection.close()

            foods_parquet = pq.read_table(output_dir / "foods.parquet")
            self.assertEqual(foods_parquet.num_rows, 3)
            manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["tables"]["food_nutrients"], 8)
            self.assertEqual(len(manifest["source"]["files"][0]["sha256"]), 64)

    def test_repeated_builds_are_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "source"
            first_dir = root / "first"
            second_dir = root / "second"
            source_dir.mkdir()
            build_fixture(source_dir)

            build_fndds_release(source_dir, first_dir, strict_official=False)
            build_fndds_release(source_dir, second_dir, strict_official=False)

            first_files = sorted(path.name for path in first_dir.iterdir())
            second_files = sorted(path.name for path in second_dir.iterdir())
            self.assertEqual(first_files, second_files)
            for filename in first_files:
                self.assertEqual(sha256(first_dir / filename), sha256(second_dir / filename), filename)

    def test_duplicate_food_nutrient_pair_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "source"
            output_dir = root / "release"
            source_dir.mkdir()
            build_fixture(source_dir)
            with (source_dir / "food_nutrient.csv").open("a", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, lineterminator="\n")
                writer.writerow(["9", "1", "203", "3.15", "", "", "", "", "", "", ""])

            with self.assertRaisesRegex(DatasetValidationError, "Duplicate FNDDS food/nutrient pair"):
                build_fndds_release(source_dir, output_dir, strict_official=False)
            self.assertFalse(output_dir.exists())


if __name__ == "__main__":
    unittest.main()
