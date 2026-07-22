# OpenNutri Core USDA Release

## Status

`v0.1.1` combines three complementary, public-domain USDA FoodData Central
datasets into one source-aware product artifact:

| Source | Role | Foods | Searchable |
|---|---|---:|---:|
| FNDDS 2021-2023 | Common prepared and survey-reported foods with strong portions | 5,432 | 5,431 |
| Foundation 2025-12-18 | Current analytically measured basic foods | 365 | 313 |
| SR Legacy 2018-04 | Broad ingredient and food-variety coverage | 7,793 | 7,793 |
| **Combined** | | **13,590** | **13,537** |

The sources remain distinct records. OpenNutri does not average values or silently
copy nutrients between foods. Every search result and detail response identifies its
USDA dataset, release, FDC ID, and original description.

## Build

```bash
python3 services/data-pipeline/scripts/build_core_dataset.py
```

The default output is:

```text
services/data-pipeline/data/core/releases/opennutri-core-usda-v0.1.1/
```

It contains normalized CSV and Parquet tables, `opennutri-core.sqlite`, a quality
report, and a manifest containing source and artifact hashes. Official builds verify
all three extracted source-tree hashes and exact source food counts.

The SQLite nutrient table uses a composite `(food_id, nutrient_id)` primary key with
`WITHOUT ROWID`. The builder validates source rows before insertion, so the runtime
database avoids redundant indexes while retaining every accepted observation.

## Measured Output

| Table | Rows |
|---|---:|
| Dataset releases | 3 |
| Foods | 13,590 |
| Nutrients | 246 |
| Food nutrient observations | 1,012,681 |
| Portions | 36,619 |
| Food categories | 200 |

Thirty-seven blank or negative Foundation nutrient observations are rejected and
recorded in `quality_report.json`; missing values are never converted to zero. One
non-positive FNDDS portion is also rejected. Foundation specific-gravity data is
retained with a `physical_property` basis and must not be scaled as a per-100-g
nutrient.

## Search Policy

Search ranks exact and prefix name matches first, then source quality and FTS
relevance. Foundation records have the highest source priority, FNDDS follows, and
SR Legacy supplies breadth. Ambiguous `NFS`/`NS` records receive a penalty.

All query terms are required when possible. If no food contains every term, the API
uses the largest and most selective matching subset and returns
`match_mode=partial_terms` plus `matched_terms`, allowing clients to label the result
as a suggestion instead of presenting it as an exact match.

Examples:

- `red lentils` -> `Lentils, pink or red, raw` (SR Legacy)
- `lentils` -> `Lentils, dry` (Foundation), followed by prepared FNDDS records
- `apple raw` -> current Foundation apple varieties before generic records

## Known Boundaries

- This is still a USDA-centered database, not a global or Turkish food catalog.
- It does not yet include branded/barcode foods, restaurant menus, user recipes, or
  the literature-extraction dataset.
- Source records that represent the same practical food are not deduplicated yet.
  Ranking reduces clutter, but a reviewed equivalence layer remains future work.
- A common-query benchmark is required to measure coverage and ranking instead of
  inferring quality from the total row count.
