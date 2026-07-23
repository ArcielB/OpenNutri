"""Build a deterministic OpenNutri Core artifact from complementary USDA datasets."""

from __future__ import annotations

import csv
import json
import math
import re
import shutil
import sqlite3
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Any, Iterable, Iterator

import pyarrow as pa

from .fndds import (
    CORE_SOURCE_NUTRIENT_CODES,
    DEFAULT_SOURCE_DIR as DEFAULT_FNDDS_SOURCE_DIR,
    FNDDS_ARCHIVE_SHA256,
    FNDDS_COVERAGE_END,
    FNDDS_COVERAGE_START,
    FNDDS_DOWNLOAD_URL,
    FNDDS_RELEASE_DATE,
    FNDDS_RELEASE_ID,
    FNDDS_SOURCE_TREE_SHA256,
    PROJECT_ROOT,
    SQLITE_SCHEMA,
    TABLE_SPECS,
    USDA_LICENSE,
    USDA_LICENSE_URL,
    DatasetValidationError,
    SourceAudit,
    TableSpec,
    _ambiguity_flags,
    _build_source_audit,
    _canonical_unit,
    _category_rows as _fndds_category_rows,
    _create_search_index,
    _food_nutrient_rows as _fndds_food_nutrient_rows,
    _food_rows as _fndds_food_rows,
    _hash_file,
    _normalized_description,
    _parse_float,
    _parse_int,
    _search_text,
    _source_file_manifest,
    _stable_uuid,
    _write_json,
    _write_table,
)


CORE_ARTIFACT_VERSION = "0.2.0"
FOUNDATION_CORE_NUTRIENT_GROUPS = (
    frozenset({"203"}),
    frozenset({"204"}),
    frozenset({"205"}),
    frozenset({"208", "957", "958"}),
)
DEFAULT_FOUNDATION_SOURCE_DIR = PROJECT_ROOT / "FoodData_Central_foundation_food_csv_2025-12-18"
DEFAULT_SR_LEGACY_SOURCE_DIR = PROJECT_ROOT / "FoodData_Central_sr_legacy_food_csv_2018-04"
DEFAULT_SR28_SOURCE_DIR = PROJECT_ROOT / "USDA_SR28_ASCII_2015-05"
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "services"
    / "data-pipeline"
    / "data"
    / "core"
    / "releases"
    / f"opennutri-core-usda-v{CORE_ARTIFACT_VERSION}"
)
SR28_DOWNLOAD_URL = (
    "https://www.ars.usda.gov/ARSUserFiles/80400525/Data/SR/SR28/dnload/sr28asc.zip"
)
SR28_ARCHIVE_SHA256 = "8308fd1d224ef1e5331093748007180da01a7ac713cbac6a1f5bc2a03e1ee70a"
SR28_FOOD_DES_SHA256 = "bb2047218cdad1d830da69e760386409fde3b7afabceae604c5479f280d4fa2e"
SR28_EXPECTED_FOOD_COUNT = 8_789
SR28_EXPECTED_MATCHED_FOOD_COUNT = 7_754
SR28_EXPECTED_FACTOR_COUNT = 1_943
OVERLAPPING_BONE_COMPONENT_RE = re.compile(
    r"bone and (?:cartilage|co+n+ective tissue)",
    re.IGNORECASE,
)


SR28_FOOD_DES_COLUMNS = (
    "NDB_No",
    "FdGrp_Cd",
    "Long_Desc",
    "Shrt_Desc",
    "ComName",
    "ManufacName",
    "Survey",
    "Ref_desc",
    "Refuse",
    "SciName",
    "N_Factor",
    "Pro_Factor",
    "Fat_Factor",
    "CHO_Factor",
)


REFUSE_REVIEW_OVERRIDES = {
    "05066": {
        "expected_source_refuse_percent": 66.0,
        "refuse_percent": 33.0,
        "reference_ndb_number": "05071",
        "reference_refuse_percent": 42.0,
        "reference_description_fragment": "bone and cartilage 33%, skin and separable fat 9%",
        "derivation": "reviewed_component_crosscheck",
        "notes": (
            "SR28 reports two overlapping 33% bone descriptions and totals them as 66%. "
            "The corresponding raw meat-only drumstick record 05071 identifies 33% bone "
            "plus 9% skin and separable fat; because this food includes skin and fat, only "
            "the 33% bone component is refuse."
        ),
    }
}


EDIBLE_PORTION_FACTOR_TABLE_SPEC = TableSpec(
    "edible_portion_factors",
    (
        "factor_id",
        "food_id",
        "factor_type",
        "edible_fraction",
        "refuse_percent",
        "refuse_description",
        "source_dataset",
        "source_url",
        "source_food_code",
        "source_refuse_percent",
        "derivation",
        "review_status",
        "is_usable",
        "notes",
    ),
    pa.schema(
        [
            ("factor_id", pa.string()),
            ("food_id", pa.string()),
            ("factor_type", pa.string()),
            ("edible_fraction", pa.float64()),
            ("refuse_percent", pa.float64()),
            ("refuse_description", pa.string()),
            ("source_dataset", pa.string()),
            ("source_url", pa.string()),
            ("source_food_code", pa.string()),
            ("source_refuse_percent", pa.float64()),
            ("derivation", pa.string()),
            ("review_status", pa.string()),
            ("is_usable", pa.bool_()),
            ("notes", pa.string()),
        ]
    ),
)


USDA_SQLITE_SCHEMA = (
    SQLITE_SCHEMA
    + """

CREATE TABLE edible_portion_factors (
    factor_id TEXT PRIMARY KEY,
    food_id TEXT NOT NULL REFERENCES foods(food_id),
    factor_type TEXT NOT NULL CHECK (factor_type = 'as_purchased_to_edible'),
    edible_fraction REAL CHECK (edible_fraction > 0 AND edible_fraction <= 1),
    refuse_percent REAL CHECK (refuse_percent >= 0 AND refuse_percent < 100),
    refuse_description TEXT NOT NULL,
    source_dataset TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_food_code TEXT NOT NULL,
    source_refuse_percent REAL NOT NULL CHECK (
        source_refuse_percent >= 0 AND source_refuse_percent < 100
    ),
    derivation TEXT NOT NULL,
    review_status TEXT NOT NULL CHECK (
        review_status IN ('source_reported', 'reviewed', 'conflict')
    ),
    is_usable INTEGER NOT NULL CHECK (is_usable IN (0, 1)),
    notes TEXT,
    CHECK (
        (is_usable = 1 AND edible_fraction IS NOT NULL AND refuse_percent IS NOT NULL)
        OR
        (is_usable = 0 AND edible_fraction IS NULL AND refuse_percent IS NULL)
    ),
    UNIQUE(food_id)
);
"""
)


@dataclass(frozen=True)
class BasicDatasetDefinition:
    release_id: str
    dataset_name: str
    data_type: str
    member_filename: str
    release_date: str
    download_url: str
    archive_sha256: str
    source_tree_sha256: str
    expected_food_count: int
    base_search_priority: int


FOUNDATION = BasicDatasetDefinition(
    release_id="usda-foundation-2025-12-18",
    dataset_name="USDA FoodData Central Foundation Foods",
    data_type="foundation_food",
    member_filename="foundation_food.csv",
    release_date="2025-12-18",
    download_url=(
        "https://fdc.nal.usda.gov/fdc-datasets/"
        "FoodData_Central_foundation_food_csv_2025-12-18.zip"
    ),
    archive_sha256="3850de85effd6d9aa471f48aab2a76c20f9bc5feb3f2f52c8ce693f9cf75d52b",
    source_tree_sha256="f5ba8944c0885b5757818ff6e5a411cdd9d9c180c87836713487565085e1194e",
    expected_food_count=365,
    base_search_priority=140,
)

SR_LEGACY = BasicDatasetDefinition(
    release_id="usda-sr-legacy-2018-04",
    dataset_name="USDA National Nutrient Database for Standard Reference, Legacy Release",
    data_type="sr_legacy_food",
    member_filename="sr_legacy_food.csv",
    release_date="2019-04-01",
    download_url=(
        "https://fdc.nal.usda.gov/fdc-datasets/"
        "FoodData_Central_sr_legacy_food_csv_2018-04.zip"
    ),
    archive_sha256="b80817294b8850530aaedf2e515c02593b1824f763a0ff356e5c2081643e6fd0",
    source_tree_sha256="233e1e31ba1480d0a6f8899b4436d2d270c415ef4ac059938b1419614664d625",
    expected_food_count=7_793,
    base_search_priority=90,
)


REQUIRED_BASIC_COLUMNS = {
    "food.csv": {"fdc_id", "data_type", "description", "food_category_id", "publication_date"},
    "food_category.csv": {"id", "description"},
    "nutrient.csv": {"id", "name", "unit_name", "nutrient_nbr", "rank"},
    "food_nutrient.csv": {
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
    },
    "food_portion.csv": {
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
    },
    "measure_unit.csv": {"id", "name"},
}


@dataclass
class BasicSourceAudit:
    definition: BasicDatasetDefinition
    source_dir: Path
    member_rows: list[dict[str, str]]
    foods_by_fdc_id: dict[str, dict[str, str]]
    categories_by_id: dict[str, str]
    nutrients_by_id: dict[str, dict[str, str]]
    used_nutrient_ids: set[str]
    nutrient_numbers_by_food: dict[str, set[str]]
    accepted_portions: list[dict[str, Any]]
    portion_count_by_food: Counter[str]
    source_nutrient_rows: int
    accepted_nutrient_rows: int
    rejected_nutrient_rows: int
    source_portion_rows: int
    rejected_portion_count: int
    rejection_examples: dict[str, list[dict[str, str]]]
    source_file_manifest: list[dict[str, Any]]
    source_tree_sha256: str


@dataclass
class RefuseFactorAudit:
    source_dir: Path
    source_file_sha256: str
    source_file_manifest: list[dict[str, Any]]
    source_tree_sha256: str
    source_food_count: int
    matched_food_count: int
    factors: list[dict[str, Any]]
    usable_factor_count: int
    raw_factor_count: int
    usable_raw_factor_count: int
    conflict_food_codes: list[str]
    reviewed_food_codes: list[str]


def _csv_rows(path: Path, required_columns: set[str]) -> Iterator[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required_columns - set(reader.fieldnames or [])
        if missing:
            raise DatasetValidationError(f"{path.name} is missing columns: {sorted(missing)}")
        yield from reader


def _load_rows(source_dir: Path, filename: str) -> list[dict[str, str]]:
    return list(_csv_rows(source_dir / filename, REQUIRED_BASIC_COLUMNS[filename]))


def _unique_by(rows: Iterable[dict[str, str]], key: str, label: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row.get(key, "")
        if not value or value in result:
            raise DatasetValidationError(f"{label} contains a blank or duplicate {key}: {value!r}")
        result[value] = row
    return result


def _food_id(release_id: str, source_food_id: str) -> str:
    return _stable_uuid("food", release_id, source_food_id)


def _portion_id(release_id: str, source_portion_id: str) -> str:
    return _stable_uuid("portion", release_id, source_portion_id)


def _category_id(source_category_id: str) -> str:
    return _stable_uuid("category", "usda-fdc", source_category_id)


def _nutrient_id(source_nutrient_id: str) -> str:
    return _stable_uuid("nutrient", "usda-fdc", source_nutrient_id)


def _edible_portion_factor_id(source_food_code: str) -> str:
    return _stable_uuid("edible-portion-factor", "usda-sr28", source_food_code)


def _portion_description(row: dict[str, str], measure_name: str) -> str:
    description = row["portion_description"].strip()
    if description:
        return description
    pieces = [row["amount"].strip(), measure_name.strip(), row["modifier"].strip()]
    fallback = " ".join(piece for piece in pieces if piece)
    return fallback or "Quantity specified by USDA"


def _sr28_food_description_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen_codes: set[str] = set()
    with path.open("r", encoding="latin-1", newline="") as handle:
        reader = csv.reader(handle, delimiter="^", quotechar="~")
        for line_number, values in enumerate(reader, start=1):
            if len(values) != len(SR28_FOOD_DES_COLUMNS):
                raise DatasetValidationError(
                    f"FOOD_DES.txt line {line_number} has {len(values)} fields; "
                    f"expected {len(SR28_FOOD_DES_COLUMNS)}"
                )
            row = dict(zip(SR28_FOOD_DES_COLUMNS, values, strict=True))
            source_food_code = row["NDB_No"].zfill(5)
            if source_food_code in seen_codes:
                raise DatasetValidationError(
                    f"FOOD_DES.txt contains duplicate NDB_No {source_food_code}"
                )
            row["NDB_No"] = source_food_code
            seen_codes.add(source_food_code)
            rows.append(row)
    return rows


def _has_overlapping_bone_components(description: str) -> bool:
    return len(OVERLAPPING_BONE_COMPONENT_RE.findall(description)) > 1


def _build_refuse_factor_audit(
    sr_legacy: BasicSourceAudit,
    source_dir: Path,
    *,
    strict_official: bool,
) -> RefuseFactorAudit:
    source_dir = source_dir.resolve()
    source_path = source_dir / "FOOD_DES.txt"
    if not source_path.is_file():
        raise DatasetValidationError(f"Missing USDA SR28 source file: {source_path}")

    source_file_sha256 = _hash_file(source_path)
    source_file_manifest, source_tree_sha256 = _source_file_manifest(source_dir)
    source_rows = _sr28_food_description_rows(source_path)
    source_rows_by_code = {row["NDB_No"]: row for row in source_rows}
    fdc_id_by_ndb_number = {
        row["NDB_number"].zfill(5): row["fdc_id"]
        for row in sr_legacy.member_rows
    }
    matched_food_count = len(source_rows_by_code.keys() & fdc_id_by_ndb_number.keys())

    factors: list[dict[str, Any]] = []
    conflict_food_codes: list[str] = []
    reviewed_food_codes: list[str] = []
    raw_factor_count = 0
    usable_raw_factor_count = 0
    for source_food_code in sorted(source_rows_by_code):
        fdc_id = fdc_id_by_ndb_number.get(source_food_code)
        if fdc_id is None:
            continue
        source_row = source_rows_by_code[source_food_code]
        refuse_text = source_row["Refuse"].strip()
        if not refuse_text:
            continue
        source_refuse_percent = _parse_float(
            refuse_text,
            field="Refuse",
            row_label=f"SR28 FOOD_DES {source_food_code}",
        )
        if source_refuse_percent is None or source_refuse_percent <= 0:
            continue
        if source_refuse_percent >= 100:
            raise DatasetValidationError(
                f"SR28 FOOD_DES {source_food_code} has invalid refuse percent "
                f"{source_refuse_percent}"
            )

        is_raw = bool(re.search(r"\braw\b", source_row["Long_Desc"], re.IGNORECASE))
        raw_factor_count += int(is_raw)
        selected_refuse_percent: float | None = source_refuse_percent
        derivation = "source_refuse_percent"
        review_status = "source_reported"
        is_usable = True
        notes: str | None = None

        if _has_overlapping_bone_components(source_row["Ref_desc"]):
            override = REFUSE_REVIEW_OVERRIDES.get(source_food_code)
            if override is None:
                selected_refuse_percent = None
                derivation = "overlapping_refuse_components"
                review_status = "conflict"
                is_usable = False
                notes = (
                    "The SR28 refuse description contains overlapping bone component "
                    "percentages that were added together; this factor requires review."
                )
                conflict_food_codes.append(source_food_code)
            else:
                if source_refuse_percent != override["expected_source_refuse_percent"]:
                    raise DatasetValidationError(
                        f"Reviewed SR28 factor {source_food_code} expected source refuse "
                        f"{override['expected_source_refuse_percent']}, got "
                        f"{source_refuse_percent}"
                    )
                reference = source_rows_by_code[override["reference_ndb_number"]]
                reference_refuse = _parse_float(
                    reference["Refuse"],
                    field="Refuse",
                    row_label=f"SR28 FOOD_DES {reference['NDB_No']}",
                )
                if (
                    reference_refuse != override["reference_refuse_percent"]
                    or override["reference_description_fragment"].casefold()
                    not in reference["Ref_desc"].casefold()
                ):
                    raise DatasetValidationError(
                        f"Reviewed SR28 factor {source_food_code} reference "
                        f"{reference['NDB_No']} changed"
                    )
                selected_refuse_percent = override["refuse_percent"]
                derivation = override["derivation"]
                review_status = "reviewed"
                notes = override["notes"]
                reviewed_food_codes.append(source_food_code)

        edible_fraction = (
            round((100.0 - selected_refuse_percent) / 100.0, 6)
            if selected_refuse_percent is not None
            else None
        )
        usable_raw_factor_count += int(is_raw and is_usable)
        factors.append(
            {
                "factor_id": _edible_portion_factor_id(source_food_code),
                "food_id": _food_id(SR_LEGACY.release_id, fdc_id),
                "factor_type": "as_purchased_to_edible",
                "edible_fraction": edible_fraction,
                "refuse_percent": selected_refuse_percent,
                "refuse_description": source_row["Ref_desc"].strip(),
                "source_dataset": (
                    "USDA National Nutrient Database for Standard Reference, Release 28"
                ),
                "source_url": SR28_DOWNLOAD_URL,
                "source_food_code": source_food_code,
                "source_refuse_percent": source_refuse_percent,
                "derivation": derivation,
                "review_status": review_status,
                "is_usable": is_usable,
                "notes": notes,
            }
        )

    if strict_official:
        expected_values = {
            "source_food_count": (len(source_rows), SR28_EXPECTED_FOOD_COUNT),
            "matched_food_count": (matched_food_count, SR28_EXPECTED_MATCHED_FOOD_COUNT),
            "factor_count": (len(factors), SR28_EXPECTED_FACTOR_COUNT),
        }
        for label, (actual, expected) in expected_values.items():
            if actual != expected:
                raise DatasetValidationError(
                    f"USDA SR28 {label} changed: expected {expected}, got {actual}"
                )
        if source_file_sha256 != SR28_FOOD_DES_SHA256:
            raise DatasetValidationError(
                "USDA SR28 FOOD_DES.txt hash changed: "
                f"expected {SR28_FOOD_DES_SHA256}, got {source_file_sha256}"
            )

    return RefuseFactorAudit(
        source_dir=source_dir,
        source_file_sha256=source_file_sha256,
        source_file_manifest=source_file_manifest,
        source_tree_sha256=source_tree_sha256,
        source_food_count=len(source_rows),
        matched_food_count=matched_food_count,
        factors=factors,
        usable_factor_count=sum(int(row["is_usable"]) for row in factors),
        raw_factor_count=raw_factor_count,
        usable_raw_factor_count=usable_raw_factor_count,
        conflict_food_codes=conflict_food_codes,
        reviewed_food_codes=reviewed_food_codes,
    )


def _build_basic_audit(
    definition: BasicDatasetDefinition,
    source_dir: Path,
    *,
    strict_official: bool,
) -> BasicSourceAudit:
    source_dir = source_dir.resolve()
    required_files = set(REQUIRED_BASIC_COLUMNS) | {definition.member_filename}
    for filename in required_files:
        if not (source_dir / filename).is_file():
            raise DatasetValidationError(f"Missing {definition.data_type} source file: {filename}")

    with (source_dir / definition.member_filename).open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        member_rows = list(csv.DictReader(handle))
    members_by_fdc_id = _unique_by(member_rows, "fdc_id", definition.member_filename)
    all_foods = _unique_by(_load_rows(source_dir, "food.csv"), "fdc_id", "food.csv")
    foods_by_fdc_id: dict[str, dict[str, str]] = {}
    for fdc_id in members_by_fdc_id:
        food = all_foods.get(fdc_id)
        if food is None:
            raise DatasetValidationError(f"{definition.data_type} member {fdc_id} is absent from food.csv")
        if food["data_type"] != definition.data_type:
            raise DatasetValidationError(
                f"{definition.data_type} member {fdc_id} has data_type {food['data_type']!r}"
            )
        foods_by_fdc_id[fdc_id] = food

    category_rows = _load_rows(source_dir, "food_category.csv")
    categories_by_id = {
        row["id"]: row["description"]
        for row in category_rows
    }
    if len(categories_by_id) != len(category_rows):
        raise DatasetValidationError("food_category.csv contains duplicate category IDs")

    nutrients_by_id = _unique_by(_load_rows(source_dir, "nutrient.csv"), "id", "nutrient.csv")
    nutrient_numbers_by_food: dict[str, set[str]] = defaultdict(set)
    used_nutrient_ids: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    seen_row_ids: set[str] = set()
    source_nutrient_rows = 0
    accepted_nutrient_rows = 0
    rejected_nutrient_rows = 0
    nutrient_rejections: list[dict[str, str]] = []
    for row in _csv_rows(source_dir / "food_nutrient.csv", REQUIRED_BASIC_COLUMNS["food_nutrient.csv"]):
        fdc_id = row["fdc_id"]
        if fdc_id not in members_by_fdc_id:
            continue
        source_nutrient_rows += 1
        source_row_id = row["id"]
        source_nutrient_id = row["nutrient_id"]
        if not source_row_id or source_row_id in seen_row_ids:
            raise DatasetValidationError(f"Blank or duplicate food_nutrient row ID: {source_row_id!r}")
        seen_row_ids.add(source_row_id)
        pair = (fdc_id, source_nutrient_id)
        if pair in seen_pairs:
            raise DatasetValidationError(f"Duplicate food/nutrient pair in {definition.release_id}: {pair}")
        seen_pairs.add(pair)
        amount_text = row["amount"].strip()
        if not amount_text:
            rejected_nutrient_rows += 1
            if len(nutrient_rejections) < 20:
                nutrient_rejections.append(
                    {
                        "source_row_id": source_row_id,
                        "source_food_id": fdc_id,
                        "source_nutrient_id": source_nutrient_id,
                        "reason": "blank_amount",
                    }
                )
            continue
        nutrient = nutrients_by_id.get(source_nutrient_id)
        if nutrient is None:
            raise DatasetValidationError(
                f"food_nutrient {source_row_id} references unknown nutrient {source_nutrient_id}"
            )
        amount = _parse_float(amount_text, field="amount", row_label=f"food_nutrient {source_row_id}")
        if amount is None or amount < 0:
            rejected_nutrient_rows += 1
            if len(nutrient_rejections) < 20:
                nutrient_rejections.append(
                    {
                        "source_row_id": source_row_id,
                        "source_food_id": fdc_id,
                        "source_nutrient_id": source_nutrient_id,
                        "amount": amount_text,
                        "reason": "negative_amount",
                    }
                )
            continue
        accepted_nutrient_rows += 1
        used_nutrient_ids.add(source_nutrient_id)
        nutrient_numbers_by_food[fdc_id].add(nutrient["nutrient_nbr"])

    measures_by_id = _unique_by(_load_rows(source_dir, "measure_unit.csv"), "id", "measure_unit.csv")
    accepted_portions: list[dict[str, Any]] = []
    portion_count_by_food: Counter[str] = Counter()
    seen_portion_ids: set[str] = set()
    source_portion_rows = 0
    rejected_portion_count = 0
    portion_rejections: list[dict[str, str]] = []
    for row in _csv_rows(source_dir / "food_portion.csv", REQUIRED_BASIC_COLUMNS["food_portion.csv"]):
        fdc_id = row["fdc_id"]
        if fdc_id not in members_by_fdc_id:
            continue
        source_portion_rows += 1
        source_portion_id = row["id"]
        if not source_portion_id or source_portion_id in seen_portion_ids:
            raise DatasetValidationError(f"Blank or duplicate food_portion row ID: {source_portion_id!r}")
        seen_portion_ids.add(source_portion_id)
        measure = measures_by_id.get(row["measure_unit_id"])
        if measure is None:
            raise DatasetValidationError(
                f"food_portion {source_portion_id} references unknown measure {row['measure_unit_id']!r}"
            )
        gram_weight = _parse_float(
            row["gram_weight"],
            field="gram_weight",
            row_label=f"food_portion {source_portion_id}",
            optional=True,
        )
        if gram_weight is None or gram_weight <= 0:
            rejected_portion_count += 1
            if len(portion_rejections) < 20:
                portion_rejections.append(
                    {
                        "source_portion_id": source_portion_id,
                        "source_food_id": fdc_id,
                        "gram_weight": row["gram_weight"],
                        "reason": "non_positive_gram_weight",
                    }
                )
            continue
        amount = _parse_float(
            row["amount"],
            field="amount",
            row_label=f"food_portion {source_portion_id}",
            optional=True,
        )
        accepted_portions.append(
            {
                "portion_id": _portion_id(definition.release_id, source_portion_id),
                "food_id": _food_id(definition.release_id, fdc_id),
                "source_portion_id": source_portion_id,
                "sequence_number": _parse_int(
                    row["seq_num"],
                    field="seq_num",
                    row_label=f"food_portion {source_portion_id}",
                    optional=True,
                ),
                "amount": amount if amount is not None and amount > 0 else None,
                "measure_unit_id": row["measure_unit_id"],
                "measure_unit_name": measure["name"],
                "portion_description": _portion_description(row, measure["name"]),
                "modifier": row["modifier"],
                "gram_weight": gram_weight,
                "data_points": _parse_int(
                    row["data_points"],
                    field="data_points",
                    row_label=f"food_portion {source_portion_id}",
                    optional=True,
                ),
                "footnote": row["footnote"] or None,
                "min_year_acquired": row["min_year_acquired"] or None,
            }
        )
        portion_count_by_food[fdc_id] += 1

    source_file_manifest, source_tree_sha256 = _source_file_manifest(source_dir)
    if strict_official:
        if source_tree_sha256 != definition.source_tree_sha256:
            raise DatasetValidationError(
                f"{definition.release_id} source tree hash changed: "
                f"expected {definition.source_tree_sha256}, got {source_tree_sha256}"
            )
        if len(member_rows) != definition.expected_food_count:
            raise DatasetValidationError(
                f"{definition.release_id} food count changed: "
                f"expected {definition.expected_food_count}, got {len(member_rows)}"
            )

    return BasicSourceAudit(
        definition=definition,
        source_dir=source_dir,
        member_rows=member_rows,
        foods_by_fdc_id=foods_by_fdc_id,
        categories_by_id=categories_by_id,
        nutrients_by_id=nutrients_by_id,
        used_nutrient_ids=used_nutrient_ids,
        nutrient_numbers_by_food=nutrient_numbers_by_food,
        accepted_portions=accepted_portions,
        portion_count_by_food=portion_count_by_food,
        source_nutrient_rows=source_nutrient_rows,
        accepted_nutrient_rows=accepted_nutrient_rows,
        rejected_nutrient_rows=rejected_nutrient_rows,
        source_portion_rows=source_portion_rows,
        rejected_portion_count=rejected_portion_count,
        rejection_examples={"nutrients": nutrient_rejections, "portions": portion_rejections},
        source_file_manifest=source_file_manifest,
        source_tree_sha256=source_tree_sha256,
    )


def _release_rows(
    fndds: SourceAudit,
    basic_audits: Iterable[BasicSourceAudit],
) -> Iterator[dict[str, Any]]:
    yield {
        "release_id": FNDDS_RELEASE_ID,
        "artifact_version": CORE_ARTIFACT_VERSION,
        "publisher": "USDA Agricultural Research Service",
        "dataset_name": "Food and Nutrient Database for Dietary Studies 2021-2023",
        "data_type": "survey_fndds_food",
        "release_date": FNDDS_RELEASE_DATE,
        "coverage_start": FNDDS_COVERAGE_START,
        "coverage_end": FNDDS_COVERAGE_END,
        "download_url": FNDDS_DOWNLOAD_URL,
        "archive_sha256": FNDDS_ARCHIVE_SHA256,
        "source_tree_sha256": fndds.source_tree_sha256,
        "license": USDA_LICENSE,
        "license_url": USDA_LICENSE_URL,
    }
    for audit in basic_audits:
        publication_dates = sorted(
            food["publication_date"] for food in audit.foods_by_fdc_id.values()
        )
        definition = audit.definition
        yield {
            "release_id": definition.release_id,
            "artifact_version": CORE_ARTIFACT_VERSION,
            "publisher": "USDA Agricultural Research Service",
            "dataset_name": definition.dataset_name,
            "data_type": definition.data_type,
            "release_date": definition.release_date,
            "coverage_start": publication_dates[0],
            "coverage_end": publication_dates[-1],
            "download_url": definition.download_url,
            "archive_sha256": definition.archive_sha256,
            "source_tree_sha256": audit.source_tree_sha256,
            "license": USDA_LICENSE,
            "license_url": USDA_LICENSE_URL,
        }


def _basic_category_rows(audits: Iterable[BasicSourceAudit]) -> Iterator[dict[str, Any]]:
    categories: dict[str, str] = {}
    for audit in audits:
        for category_id, name in audit.categories_by_id.items():
            previous = categories.setdefault(category_id, name)
            if previous != name:
                raise DatasetValidationError(
                    f"USDA category {category_id} changed from {previous!r} to {name!r}"
                )
    for source_category_id in sorted(categories, key=int):
        yield {
            "category_id": _category_id(source_category_id),
            "source": "usda-fdc",
            "source_category_number": source_category_id,
            "name": categories[source_category_id],
        }


def _fndds_foods_with_combined_priority(audit: SourceAudit) -> Iterator[dict[str, Any]]:
    for row in _fndds_food_rows(audit):
        if row["is_searchable"]:
            row["search_priority"] += 20
        yield row


def _basic_food_rows(audit: BasicSourceAudit) -> Iterator[dict[str, Any]]:
    members_by_id = {row["fdc_id"]: row for row in audit.member_rows}
    definition = audit.definition
    for fdc_id in sorted(members_by_id, key=int):
        member = members_by_id[fdc_id]
        food = audit.foods_by_fdc_id[fdc_id]
        source_category_id = food["food_category_id"]
        category_name = audit.categories_by_id.get(source_category_id)
        if category_name is None:
            raise DatasetValidationError(
                f"{definition.release_id} food {fdc_id} has unknown category {source_category_id!r}"
            )
        nutrient_numbers = audit.nutrient_numbers_by_food.get(fdc_id, set())
        has_core = all(
            nutrient_numbers & acceptable_codes
            for acceptable_codes in FOUNDATION_CORE_NUTRIENT_GROUPS
        )
        flags = _ambiguity_flags(food["description"])
        if not nutrient_numbers:
            quality_status = "excluded"
            exclusion_reason = "missing_nutrient_profile"
        elif not has_core:
            quality_status = "partial"
            exclusion_reason = "missing_core_nutrients"
        elif flags:
            quality_status = "ambiguous"
            exclusion_reason = None
        else:
            quality_status = "complete"
            exclusion_reason = None
        is_searchable = has_core
        search_priority = 0
        if is_searchable:
            search_priority = definition.base_search_priority
            if audit.portion_count_by_food[fdc_id]:
                search_priority += 10
            if flags:
                search_priority -= 30
        publication_date = food["publication_date"]
        yield {
            "food_id": _food_id(definition.release_id, fdc_id),
            "release_id": definition.release_id,
            "source": "usda-fdc",
            "data_type": definition.data_type,
            "source_food_id": fdc_id,
            "source_food_code": member.get("NDB_number", ""),
            "original_description": food["description"],
            "normalized_description": _normalized_description(food["description"]),
            "display_name": food["description"],
            "category_id": _category_id(source_category_id),
            "category_name": category_name,
            "publication_date": publication_date,
            "coverage_start": publication_date,
            "coverage_end": publication_date,
            "quality_status": quality_status,
            "is_searchable": is_searchable,
            "exclusion_reason": exclusion_reason,
            "ambiguity_flags": json.dumps(flags, separators=(",", ":")),
            "nutrient_count": len(nutrient_numbers),
            "portion_count": audit.portion_count_by_food[fdc_id],
            "search_priority": search_priority,
            "search_text": _search_text(food["description"], category_name),
        }


def _canonical_nutrient_definitions(
    fndds: SourceAudit,
    basic_audits: list[BasicSourceAudit],
) -> list[dict[str, str]]:
    used_ids = set().union(*(audit.used_nutrient_ids for audit in basic_audits))
    for nutrient_number in fndds.used_nutrient_numbers:
        used_ids.add(fndds.nutrient_by_number[nutrient_number]["id"])

    definitions: dict[str, dict[str, str]] = {}
    # Newer Foundation definitions contain corrections to a few legacy nutrient names.
    for audit in reversed(basic_audits):
        definitions.update(audit.nutrients_by_id)
    definitions.update(basic_audits[0].nutrients_by_id)
    for row in fndds.nutrient_by_number.values():
        definitions.setdefault(row["id"], row)
    missing = sorted(used_ids - definitions.keys(), key=int)
    if missing:
        raise DatasetValidationError(f"Missing canonical nutrient definitions: {missing}")

    def sort_key(row: dict[str, str]) -> tuple[float, int]:
        rank = _parse_float(
            row["rank"], field="rank", row_label=f"nutrient {row['id']}", optional=True
        )
        return (rank if rank is not None else math.inf, int(row["id"]))

    return sorted((definitions[source_id] for source_id in used_ids), key=sort_key)


def _canonical_unit_for_row(row: dict[str, str]) -> str:
    if row["unit_name"].upper() == "SP_GR":
        return "ratio"
    return _canonical_unit(row["unit_name"])


def _nutrient_rows(definitions: Iterable[dict[str, str]]) -> Iterator[dict[str, Any]]:
    for row in definitions:
        yield {
            "nutrient_id": _nutrient_id(row["id"]),
            "source": "usda-fdc",
            "source_nutrient_id": row["id"],
            "nutrient_number": row["nutrient_nbr"],
            "name": row["name"].strip(),
            "unit": _canonical_unit_for_row(row),
            "source_unit": row["unit_name"],
            "sort_rank": _parse_float(
                row["rank"], field="rank", row_label=f"nutrient {row['id']}", optional=True
            ),
            "is_archived": "DO NOT USE - Archived" in row["name"],
        }


def _source_nutrient_mapping_rows(
    fndds: SourceAudit,
    basic_audits: Iterable[BasicSourceAudit],
) -> Iterator[dict[str, Any]]:
    for source_code in sorted(fndds.used_nutrient_numbers, key=int):
        nutrient = fndds.nutrient_by_number[source_code]
        yield {
            "release_id": FNDDS_RELEASE_ID,
            "source_nutrient_code": source_code,
            "source_code_field": "food_nutrient.nutrient_id",
            "mapped_via_field": "nutrient.nutrient_nbr",
            "nutrient_id": _nutrient_id(nutrient["id"]),
            "source_nutrient_id": nutrient["id"],
        }
    for audit in basic_audits:
        for source_nutrient_id in sorted(audit.used_nutrient_ids, key=int):
            yield {
                "release_id": audit.definition.release_id,
                "source_nutrient_code": source_nutrient_id,
                "source_code_field": "food_nutrient.nutrient_id",
                "mapped_via_field": "nutrient.id",
                "nutrient_id": _nutrient_id(source_nutrient_id),
                "source_nutrient_id": source_nutrient_id,
            }


def _basic_food_nutrient_rows(audit: BasicSourceAudit) -> Iterator[dict[str, Any]]:
    member_ids = set(audit.foods_by_fdc_id)
    for row in _csv_rows(
        audit.source_dir / "food_nutrient.csv",
        REQUIRED_BASIC_COLUMNS["food_nutrient.csv"],
    ):
        if row["fdc_id"] not in member_ids or not row["amount"].strip():
            continue
        amount = _parse_float(
            row["amount"], field="amount", row_label=f"food_nutrient {row['id']}"
        )
        if amount is None or amount < 0:
            continue
        nutrient = audit.nutrients_by_id[row["nutrient_id"]]
        source_nutrient_id = nutrient["id"]
        row_label = f"food_nutrient {row['id']}"
        yield {
            "food_id": _food_id(audit.definition.release_id, row["fdc_id"]),
            "nutrient_id": _nutrient_id(source_nutrient_id),
            "amount": amount,
            "unit": _canonical_unit_for_row(nutrient),
            "basis": (
                "physical_property" if nutrient["unit_name"].upper() == "SP_GR"
                else "per_100g_edible_portion"
            ),
            "source_row_id": row["id"],
            "source_nutrient_code": source_nutrient_id,
            "derivation_id": row["derivation_id"] or None,
            "data_points": _parse_int(
                row["data_points"], field="data_points", row_label=row_label, optional=True
            ),
            "minimum": _parse_float(row["min"], field="min", row_label=row_label, optional=True),
            "maximum": _parse_float(row["max"], field="max", row_label=row_label, optional=True),
            "median": _parse_float(row["median"], field="median", row_label=row_label, optional=True),
            "footnote": row["footnote"] or None,
            "min_year_acquired": row["min_year_acquired"] or None,
        }


def _food_status_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts[row["quality_status"]] += 1
        counts["searchable"] += int(row["is_searchable"])
    return dict(counts)


def _quality_report(
    fndds: SourceAudit,
    basic_audits: list[BasicSourceAudit],
    refuse_factors: RefuseFactorAudit,
    output_counts: dict[str, int],
) -> dict[str, Any]:
    datasets: dict[str, Any] = {}
    fndds_status = _food_status_counts(_fndds_food_rows(fndds))
    datasets[FNDDS_RELEASE_ID] = {
        "source_foods": len(fndds.member_rows),
        "source_nutrient_rows": fndds.source_nutrient_rows,
        "accepted_nutrient_rows": fndds.source_nutrient_rows,
        "rejected_nutrient_rows": 0,
        "source_portion_rows": fndds.source_portion_rows,
        "accepted_portions": len(fndds.accepted_portions),
        "rejected_portions": fndds.rejected_portion_count,
        "food_statuses": fndds_status,
    }
    for audit in basic_audits:
        datasets[audit.definition.release_id] = {
            "source_foods": len(audit.member_rows),
            "source_nutrient_rows": audit.source_nutrient_rows,
            "accepted_nutrient_rows": audit.accepted_nutrient_rows,
            "rejected_nutrient_rows": audit.rejected_nutrient_rows,
            "source_portion_rows": audit.source_portion_rows,
            "accepted_portions": len(audit.accepted_portions),
            "rejected_portions": audit.rejected_portion_count,
            "food_statuses": _food_status_counts(_basic_food_rows(audit)),
            "known_rejections": audit.rejection_examples,
        }
    return {
        "artifact_version": CORE_ARTIFACT_VERSION,
        "status": "pass",
        "datasets": datasets,
        "edible_portion_factors": {
            "source_foods": refuse_factors.source_food_count,
            "matched_sr_legacy_foods": refuse_factors.matched_food_count,
            "factor_rows": len(refuse_factors.factors),
            "usable_factors": refuse_factors.usable_factor_count,
            "raw_factors": refuse_factors.raw_factor_count,
            "usable_raw_factors": refuse_factors.usable_raw_factor_count,
            "reviewed_source_food_codes": refuse_factors.reviewed_food_codes,
            "conflict_source_food_codes": refuse_factors.conflict_food_codes,
        },
        "output_rows": output_counts,
        "quality_rules": {
            "nutrient_basis": "per_100g_edible_portion unless explicitly physical_property",
            "searchable": "food has Energy 208, Protein 203, Fat 204, and Carbohydrate 205",
            "ambiguous": "description contains NFS, NS, or not specified",
            "blank_nutrient_amount": "reject; never coerce missing values to zero",
            "portion_acceptance": "gram_weight must be greater than zero",
            "as_purchased_conversion": (
                "edible_weight = as_purchased_weight * edible_fraction"
            ),
            "refuse_conflicts": (
                "overlapping bone component percentages are not usable without review"
            ),
        },
    }


def _artifact_manifest(
    output_dir: Path,
    fndds: SourceAudit,
    basic_audits: list[BasicSourceAudit],
    refuse_factors: RefuseFactorAudit,
    output_counts: dict[str, int],
) -> dict[str, Any]:
    artifacts = [
        {"name": path.name, "bytes": path.stat().st_size, "sha256": _hash_file(path)}
        for path in sorted(output_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    ]
    sources = [
        {
            "release_id": FNDDS_RELEASE_ID,
            "download_url": FNDDS_DOWNLOAD_URL,
            "archive_sha256": FNDDS_ARCHIVE_SHA256,
            "source_tree_sha256": fndds.source_tree_sha256,
            "files": fndds.source_file_manifest,
        }
    ]
    sources.extend(
        {
            "release_id": audit.definition.release_id,
            "download_url": audit.definition.download_url,
            "archive_sha256": audit.definition.archive_sha256,
            "source_tree_sha256": audit.source_tree_sha256,
            "files": audit.source_file_manifest,
        }
        for audit in basic_audits
    )
    sources.append(
        {
            "release_id": "usda-sr28-food-description-2015",
            "download_url": SR28_DOWNLOAD_URL,
            "archive_sha256": SR28_ARCHIVE_SHA256,
            "source_tree_sha256": refuse_factors.source_tree_sha256,
            "files": refuse_factors.source_file_manifest,
        }
    )
    return {
        "schema_version": 2,
        "artifact_version": CORE_ARTIFACT_VERSION,
        "release_ids": [FNDDS_RELEASE_ID, *(audit.definition.release_id for audit in basic_audits)],
        "sources": sources,
        "tables": output_counts,
        "artifacts": artifacts,
    }


def _build_into(
    fndds_source_dir: Path,
    foundation_source_dir: Path,
    sr_legacy_source_dir: Path,
    sr28_source_dir: Path,
    output_dir: Path,
    *,
    strict_official: bool,
) -> dict[str, Any]:
    fndds = _build_source_audit(fndds_source_dir)
    if strict_official and fndds.source_tree_sha256 != FNDDS_SOURCE_TREE_SHA256:
        raise DatasetValidationError(
            f"FNDDS source tree hash changed: expected {FNDDS_SOURCE_TREE_SHA256}, "
            f"got {fndds.source_tree_sha256}"
        )
    foundation = _build_basic_audit(
        FOUNDATION, foundation_source_dir, strict_official=strict_official
    )
    sr_legacy = _build_basic_audit(
        SR_LEGACY, sr_legacy_source_dir, strict_official=strict_official
    )
    basic_audits = [foundation, sr_legacy]
    refuse_factors = _build_refuse_factor_audit(
        sr_legacy,
        sr28_source_dir,
        strict_official=strict_official,
    )
    nutrient_definitions = _canonical_nutrient_definitions(fndds, basic_audits)

    sqlite_path = output_dir / "opennutri-core.sqlite"
    connection = sqlite3.connect(sqlite_path)
    connection.executescript(USDA_SQLITE_SCHEMA)
    table_rows: list[tuple[str, Iterable[dict[str, Any]]]] = [
        ("dataset_releases", _release_rows(fndds, basic_audits)),
        (
            "food_categories",
            chain(_fndds_category_rows(fndds), _basic_category_rows(basic_audits)),
        ),
        (
            "foods",
            chain(
                _fndds_foods_with_combined_priority(fndds),
                *(_basic_food_rows(audit) for audit in basic_audits),
            ),
        ),
        ("nutrients", _nutrient_rows(nutrient_definitions)),
        ("source_nutrient_mappings", _source_nutrient_mapping_rows(fndds, basic_audits)),
        (
            "food_nutrients",
            chain(
                _fndds_food_nutrient_rows(fndds_source_dir, fndds),
                *(_basic_food_nutrient_rows(audit) for audit in basic_audits),
            ),
        ),
        (
            "portions",
            chain(fndds.accepted_portions, *(audit.accepted_portions for audit in basic_audits)),
        ),
        ("edible_portion_factors", iter(refuse_factors.factors)),
    ]
    table_specs = {
        **TABLE_SPECS,
        "edible_portion_factors": EDIBLE_PORTION_FACTOR_TABLE_SPEC,
    }
    output_counts: dict[str, int] = {}
    try:
        for table_name, rows in table_rows:
            output_counts[table_name] = _write_table(
                output_dir, connection, table_specs[table_name], rows
            )
        _create_search_index(connection)
        connection.commit()
        connection.execute("VACUUM")
    finally:
        connection.close()

    report = _quality_report(fndds, basic_audits, refuse_factors, output_counts)
    _write_json(output_dir / "quality_report.json", report)
    _write_json(
        output_dir / "manifest.json",
        _artifact_manifest(output_dir, fndds, basic_audits, refuse_factors, output_counts),
    )
    return report


def build_usda_core_release(
    fndds_source_dir: Path = DEFAULT_FNDDS_SOURCE_DIR,
    foundation_source_dir: Path = DEFAULT_FOUNDATION_SOURCE_DIR,
    sr_legacy_source_dir: Path = DEFAULT_SR_LEGACY_SOURCE_DIR,
    sr28_source_dir: Path = DEFAULT_SR28_SOURCE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    overwrite: bool = False,
    strict_official: bool = True,
) -> dict[str, Any]:
    """Build the combined USDA core release atomically."""

    source_dirs = tuple(
        Path(path).resolve()
        for path in (
            fndds_source_dir,
            foundation_source_dir,
            sr_legacy_source_dir,
            sr28_source_dir,
        )
    )
    output_dir = Path(output_dir).resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    if output_dir.exists() and not overwrite:
        raise FileExistsError(f"Output directory already exists: {output_dir}")

    temporary_dir = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=str(output_dir.parent))
    )
    try:
        report = _build_into(
            *source_dirs,
            temporary_dir,
            strict_official=strict_official,
        )
        if output_dir.exists():
            shutil.rmtree(output_dir)
        temporary_dir.replace(output_dir)
        return report
    except Exception:
        shutil.rmtree(temporary_dir, ignore_errors=True)
        raise
