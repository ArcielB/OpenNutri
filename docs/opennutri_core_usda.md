# OpenNutri Core USDA Release

## Status

`v0.3.0` combines three complementary, public-domain USDA FoodData Central
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

The release also restores the food-linked refuse percentages from USDA Standard
Reference 28 `FOOD_DES.txt`. These records allow an as-purchased weight containing
bone, shell, core, peel, or similar refuse to be converted to edible grams without
matching the food to a separate buying-guide record.

## Build

```bash
python3 services/data-pipeline/scripts/build_core_dataset.py
```

The default output is:

```text
services/data-pipeline/data/core/releases/opennutri-core-usda-v0.3.0/
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
| Edible-portion factors | 1,943 |
| Search terms | 10,953 |

Of the 1,943 SR28 factor records, 1,937 are usable. The source contains 885
positive-refuse factors for raw foods, of which 883 are usable. Six poultry records
with overlapping bone-component percentages remain auditable but are explicitly
disabled.

Thirty-seven blank or negative Foundation nutrient observations are rejected and
recorded in `quality_report.json`; missing values are never converted to zero. One
non-positive FNDDS portion is also rejected. Foundation specific-gravity data is
retained with a `physical_property` basis and must not be scaled as a per-100-g
nutrient.

## As-Purchased Weight

Nutrients remain stored exactly as published per 100 g edible portion. A usable
`edible_portion_factors` row supplies the conversion:

```text
edible_weight = as_purchased_weight * edible_fraction
nutrient_amount = nutrient_per_100g_edible * edible_weight / 100
```

For SR Legacy FDC `172373`, raw chicken drumstick meat and skin, OpenNutri uses
an edible fraction of `0.67`. SR28's total-refuse field incorrectly adds two
overlapping 33% bone descriptions to produce 66%. The reviewed correction is
derived from the corresponding raw meat-only drumstick record `05071`, which
separates 33% bone from 9% skin and separable fat. Since the selected food includes
skin and fat, only the 33% bone component is refuse. Both the original source value
and correction provenance remain in the factor row.

This conversion does not model cooking loss, nutrient retention, or discarded
cooking liquid. A user who knows the raw bone-in weight selects the raw food and the
as-purchased basis. Cooked-food records require a factor describing the cooked item
as served.

## Search Policy

Search ranks exact and prefix name matches first, then source quality and FTS
relevance. Foundation records have the highest source priority, FNDDS follows, and
SR Legacy supplies breadth. Ambiguous `NFS`/`NS` records receive a penalty.

The release retains 10,953 source-derived aliases in `food_search_terms`: 1,082
USDA common names, 375 useful item-level FoodOn labels, and 9,496 lower-weight
additional descriptions. Empty, numeric-only, administrative, generic, and
primary-name duplicate terms are rejected. Duplicate values for one food collapse
to one searchable row while all contributing source rows remain in
`provenance_json`. The dedicated `food_source_term_search` FTS5 index keeps source
terms separate from primary names so the API can enforce the ranking tiers.

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
- Refuse coverage is limited to SR Legacy foods that still map to SR28. Foundation
  and FNDDS records do not inherit factors from merely similar foods.
- A common-query benchmark is required to measure coverage and ranking instead of
  inferring quality from the total row count.
