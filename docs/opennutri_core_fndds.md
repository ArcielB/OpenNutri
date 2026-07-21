# OpenNutri Core FNDDS Release

## Status

`v0.0.1` is the first source-specific OpenNutri Core release. It transforms USDA
FoodData Central FNDDS 2021-2023 into deterministic, application-ready artifacts
without changing or blending USDA nutrient values.

This release is a product dataset package. It is separate from the annotator's
legacy `entities`, `master_nutrients`, and `claims` vocabulary tables.

## Verified source

- Dataset: USDA Food and Nutrient Database for Dietary Studies 2021-2023
- FoodData Central release date: 2024-10-31
- Archive URL:
  `https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_survey_food_csv_2024-10-31.zip`
- Archive SHA-256:
  `5ccc25ec2777a8982fbb61378a42f415316173eb11e48c9a8ba4cb19f5a4f29c`
- Extracted source-tree SHA-256:
  `a6175e71af7fbd1fa78c73bd08c7a82324982866267678b47c98b29392b4e199`
- License: USDA FoodData Central public domain, CC0 1.0

The repo's 13 source files were compared with a fresh official download on
2026-07-21. File names and every file hash matched. Strict builds verify the
source-tree hash and exact official row counts before publishing a release.

## Build

Install the full pipeline requirements, then run:

```bash
python3 services/data-pipeline/scripts/build_core_dataset.py
```

The default output is gitignored local build data:

```text
services/data-pipeline/data/core/releases/
  opennutri-core-fndds-2021-2023-v0.0.1/
```

Use `--overwrite` to replace that exact release directory after a successful
temporary build. The builder never mutates the source CSV directory and publishes
atomically only after validation succeeds.

`--allow-nonofficial-counts` exists for fixtures and adapter development. Do not use
it for a published release.

## Artifacts

Every logical table is published as CSV and compressed Parquet. The release also
includes `opennutri-fndds.sqlite`, `quality_report.json`, and `manifest.json`.

| Table | Purpose |
|---|---|
| `dataset_releases` | Source, release dates, license, download URL, and source hashes |
| `food_categories` | WWEIA source category vocabulary |
| `foods` | Stable OpenNutri food IDs, FDC/FNDDS IDs, descriptions, search fields, and quality status |
| `nutrients` | The 65 FDC nutrients used by this FNDDS release with canonical units |
| `source_nutrient_mappings` | Explicit FNDDS source-code to FDC nutrient mapping |
| `food_nutrients` | Source nutrient values on a per-100-g edible-portion basis |
| `portions` | Positive gram-weight portions that can scale per-100-g values |

IDs are deterministic UUIDv5 values. Rebuilding identical source files with the same
builder version produces byte-identical artifacts.

## Source-specific rules

FNDDS `food_nutrient.nutrient_id` is not an FDC nutrient primary key. Values such as
`203`, `208`, and `301` join to `nutrient.nutrient_nbr`, whose rows then provide FDC
IDs such as `1003`, `1008`, and `1087`. The builder fails if any source nutrient code
does not map through this documented crosswalk.

All accepted nutrient values are nonnegative and retain the source row ID. Blank
values remain missing rather than becoming zero. Units are normalized to `g`, `mg`,
`ug`, `kcal`, `kJ`, or `IU`, while the USDA source unit is preserved in `nutrients`.

Foods receive one quality status:

- `complete`: has Energy 208, Protein 203, Fat 204, and Carbohydrate 205;
- `ambiguous`: complete, but the description contains `NFS`, `NS`, or
  `not specified`;
- `partial`: has nutrient data but lacks one or more required core nutrients; or
- `excluded`: has no usable nutrient profile.

Ambiguous records remain searchable with a lower `search_priority`. Excluded records
remain in the release for provenance but are omitted from full-text search.

Portions are accepted only when `gram_weight > 0`. A nutrient value for a portion is:

```text
portion_value = value_per_100g * gram_weight / 100
```

## Measured release

| Metric | Count |
|---|---:|
| Source foods | 5,432 |
| Searchable foods | 5,431 |
| Complete foods | 4,923 |
| Ambiguous but searchable foods | 508 |
| Excluded foods | 1 |
| Nutrients | 65 |
| Nutrient observations | 353,015 |
| Accepted portions | 22,045 |
| Foods with at least one valid portion | 5,395 |
| Rejected portions | 1 |

The excluded food is FDC `2705383`, `Milk, human`, which has no nutrient rows in the
FDC FNDDS export. Its zero-gram `Quantity not specified` portion is the one rejected
portion. Both decisions are recorded in `quality_report.json`.

## SQLite examples

Search uses an FTS5 table containing only searchable foods:

```sql
SELECT f.food_id,
       f.display_name,
       f.category_name,
       f.quality_status,
       f.search_priority
FROM food_search AS s
JOIN foods AS f ON f.food_id = s.food_id
WHERE food_search MATCH 'lentil'
ORDER BY f.search_priority DESC, bm25(food_search)
LIMIT 20;
```

Fetch a complete food profile:

```sql
SELECT n.name, fn.amount, fn.unit, fn.basis
FROM food_nutrients AS fn
JOIN nutrients AS n ON n.nutrient_id = fn.nutrient_id
WHERE fn.food_id = :food_id
ORDER BY n.sort_rank;
```

```sql
SELECT portion_description, gram_weight
FROM portions
WHERE food_id = :food_id
ORDER BY sequence_number;
```

## Known boundaries

- FNDDS represents foods reported in the US What We Eat in America survey. It is not
  a branded-product, barcode, restaurant, or global regional-food database.
- `NFS`/`NS` records are legitimate survey fallbacks but should not outrank specific
  matches in the consumer API.
- Search fields and FTS make the dataset queryable, but a manually reviewed common-
  query benchmark is still required before freezing API ranking.
- This release does not import FNDDS ingredient recipes or silently derive new
  profiles from them.
- No values are filled from SR Legacy, Foundation Foods, commercial sources, or the
  OpenNutri literature pipeline.

The next adapters are SR Legacy and Foundation Foods. They must target these source-
record contracts while preserving their values as distinct observations.
