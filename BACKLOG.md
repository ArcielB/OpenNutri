# Backlog

This backlog is written so a new contributor can understand each item without extra context.

How to use this backlog:
- each item should be understandable without asking for hidden context
- if you take an item, reproduce the problem first
- prefer small, testable changes
- if you discover extra edge cases, add them under the item instead of rewriting its scope silently

Current operating state: research-paper crawling, AI extraction, and the Supabase
watchdog are paused. Their GitHub workflows are disabled and have no cron triggers.
Near-term product work is the FNDDS Core API, search benchmark, deployment, and first
app vertical slice. Research backlog items remain preserved for a later explicit
restart.

## 1. Decide whether to archive or drop the unused `claims` reference table

### Problem
The 2026-06-04 Supabase usage audit found the live new-project database at about 286 MB by SQL, and `public.claims` alone used about 188 MB for roughly 644k imported legacy nutrition claim rows. Current runtime searches found no app or pipeline reads of `claims`; references are schema, ETL, docs, and test text.

### Goal
Reduce Free-plan database-size risk without harming the active annotator/pipeline:
- confirm with Arciel whether legacy `claims` rows are required for any near-term demo, export, or planned product surface
- if not needed online, dump/archive the table outside Supabase before deleting or truncating it
- reclaim database space after deletion with the least disruptive vacuum strategy Supabase allows on Free
- update schema/docs so future ETL does not refill `claims` accidentally

### Likely technical area
- `apps/expert-annotator/migration.sql`
- `services/data-pipeline/etl_sr_legacy_to_opennutri.py`
- `services/data-pipeline/create_opennutri_schema.sql`
- Supabase SQL editor / pooler

### Done when
- a product decision is recorded
- the live DB either keeps `claims` intentionally or removes/archives it
- the dashboard database-size usage has a comfortable margin below 500 MB

### RESOLVED 2026-06-12
Verified before acting: zero reads of `claims` in app or pipeline runtime code, zero
RPCs/views referencing it, zero foreign keys pointing into it, all 644,125 rows from a
single bulk import (one `source_id`), never updated since insert. The data is the output
of `services/data-pipeline/etl_sr_legacy_to_opennutri.py` over the SR Legacy CSVs that
live in this repo, so it is reproducible offline at any time.

Action taken: archived to `data/archives/claims_archive_2026-06-12.csv.gz` (644,125 rows
verified, 51 MB gzipped, local + gitignored), then `TRUNCATE public.claims` on the live
project. Schema kept intact so `migration.sql` stays the source of truth and the ETL can
refill it if a product surface ever needs it. DB size dropped 320 MB -> 134 MB.

Restore if ever needed (either works):
- `psql "$POOLER_URL" -c "\copy public.claims from program 'zcat data/archives/claims_archive_2026-06-12.csv.gz' with (format csv, header)"`
- or rerun `etl_sr_legacy_to_opennutri.py` against the repo CSVs.

## 12. Benchmark OpenNutri Core search and weight-factor coverage

### Problem
Combined USDA Core `v0.3.0`, API `v0.4.0`, and the Flutter diary now provide the
first vertical slice, including source-linked as-purchased conversion for validated
SR28 foods. Core `v0.3.0` adds provenance-preserving common-name, FoodOn, and
additional-description search terms. End-to-end voice/semantic search quality and
practical weight-factor coverage still need measurement against the versioned beta
benchmark.

### PARTIAL 2026-07-24
`benchmarks/voice-v0.1.0/` now provides 240 source-backed English/Turkish cases
(48 deterministic audio, 192 submitted text), committed WAV/hash validation, and an
evaluator for the rollout thresholds. Live semantic metrics remain pending because
the app-only Supabase Free project is restricted by the organization-wide egress
quota; do not report the manifest validation as retrieval/selection performance.

### Goal
- create reviewed food-concept grouping only for safe exact/identifier-backed matches
- define and run a common-query search benchmark before freezing API ranking
- define a common as-purchased benchmark across bone-in meat, fish, fruit, vegetables,
  shellfish, and nuts
- measure how often a searched raw food has a usable exact factor
- review or source only the high-frequency missing/conflicting factors

### Likely technical area
- `services/data-pipeline/opennutri_core/`
- `services/data-pipeline/scripts/build_core_dataset.py`
- `docs/opennutri_core_fndds.md`
- `services/core-api/`

### Done when
- the common-query benchmark meets its documented top-result/top-five thresholds
- the as-purchased benchmark has a documented coverage target and measured result
- every added or corrected factor retains source values, derivation, and review status

## 10. Calibrate AI routing thresholds from audited human truth

### Problem
The new AI routing stage now stores confidence, routing bucket, audit sampling, and eventual paper outcomes, but the thresholds are still manual.

### Goal
Add a safe threshold-tuning workflow that uses only papers which eventually received human truth:
- recompute on a fixed cadence or batch size, not paper-by-paper
- keep separate positive and negative calibration
- optimize for precision floors, not raw accuracy
- require a minimum recent audited sample before any threshold move
- cap each move size to avoid oscillation

### Likely technical area
- `services/data-pipeline/scripts/`
- `services/data-pipeline/food_paper_crawler/feedback/`
- `apps/expert-annotator/src/pages/Annotate.jsx`

### Done when
- the tuner reads audited human-reviewed outcomes only
- thresholds stay scoped per stage/model
- every automatic threshold change is explainable from stored routing provenance

## 11. Add provider-capacity monitoring and search-audit retention

### Problem
The 2026-06-21 health audit found two medium-term capacity risks:
- R2 held about 1.71 GiB and had recently grown by about 136 MiB/day, which would approach the 10 GB free allowance in roughly two months if sustained
- `paper_search_hits` plus `paper_search_batch_hits` used about 125 MB and were the main live database-growth source

### Goal
Make capacity drift visible before it interrupts ingestion:
- record daily R2 object count/bytes and Supabase database size
- alert before R2 reaches 8 GB or the database reaches 400 MB
- design a reviewed retention/compaction policy for old search-batch audit rows without weakening benchmark or provenance requirements
- track expensive recurring RPC temp usage, especially cockpit and general-queue projections

### Likely technical area
- `services/data-pipeline/scripts/`
- `.github/workflows/`
- `paper_search_hits` / `paper_search_batch_hits`
- Supabase provider metrics

### Done when
- capacity measurements are automated and retained
- warning thresholds produce a visible failed check or notification
- any audit-row retention policy is documented and validated before deletion

## 3. Train and integrate the L2 classifier (depends on label volume)

### Problem
Once labels exist, we need a trainable classifier so L2 can learn from feedback instead of only rules.

### Goal
Train a lightweight classifier on embeddings and integrate it into the pipeline:
- linear classifier (logistic regression) on top of embeddings
- probability output with configurable threshold
- model artifact versioned and reloadable
- evaluation on a fixed holdout split

### Likely technical area
- `services/data-pipeline/food_paper_crawler/`
- `services/data-pipeline/food_paper_crawler/training/`

### Sources to check when needed
- scikit-learn text classification pipeline: https://scikit-learn.org/1.3/tutorial/text_analytics/working_with_text_data.html
- fastText supervised classification: https://fasttext.cc/docs/en/supervised-tutorial.html

### Done when
- classifier training is repeatable from labeled data
- crawler uses the classifier before downloading PDFs
- per-run metrics include classifier precision/recall






## 4. (Later, depends on 3 + label volume) L2 fine-tuned multilingual transformer (XLM-R)


### Problem
The embedding + classifier baseline may miss nuanced language cues or underperform on multilingual edge cases once more labels accumulate.

### Goal
- optional upgrade for higher ceiling; not required for multilingual coverage
Fine-tune a multilingual transformer (XLM-R) for relevance classification and compare it against the embedding baseline:
- trained on the growing labeled set
- evaluated on a fixed holdout split
- only adopted if it improves precision/recall meaningfully

### Likely technical area
- `services/data-pipeline/food_paper_crawler/`
- new `services/data-pipeline/food_paper_crawler/training/` scripts

### Done when
- XLM-R beats the embedding baseline on the holdout set
- the model can be swapped in via config




## 7. Improve PDF highlight recall inside detected table regions

### Problem
PDF nutrient highlighting is now intentionally limited to detected table body/header cells and caption/title lines only. That fixed the false positives in nearby prose, but some legitimate table matches are still missed.

### Remaining limits to solve
- nutrient names split across multiple PDF text items inside the same detected table row do not reconstruct into one highlight
- captionless continuation pages are suppressed entirely, even when the next page is obviously the rest of the same table

### Likely technical area
- `apps/expert-annotator/src/components/PdfViewer.jsx`
- `apps/expert-annotator/src/utils/PdfTextScanner.js`

### Goal
Improve recall without undoing the precision-first rule that prose, footnotes, legends, and ambiguous pages must stay unhighlighted.

### Acceptance criteria
- cross-item nutrient phrases inside detected table regions can highlight cleanly
- safe continuation-page support is added only when the table region can still be identified confidently
- surrounding prose still never becomes highlight-eligible again
- click-to-open nutrient popover still works

### Notes
- keep the table-only allowlist model
- if a continuation-page heuristic is not clearly reliable, suppress highlights instead of expanding scope

### Done when
- detected table rows can highlight split nutrient phrases that currently fall between PDF text items
- clearly confident continuation pages can opt in without page-wide matching
- ambiguous pages still render with no nutrient highlights
