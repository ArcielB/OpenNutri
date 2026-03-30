# OpenNutri

OpenNutri is a food composition data project with two main parts:
- A React/Vite "Annotator" web app for labeling nutrition tables from PDFs stored in Supabase.
- A Python data pipeline for harvesting papers from PubMed Central (PMC), filtering, and optional LLM extraction.

**Repo Layout**
- `apps/expert-annotator/`: Annotator frontend (React 19 + Vite).
Entry points: `apps/expert-annotator/src/main.jsx`, `apps/expert-annotator/src/App.jsx`.
- `services/data-pipeline/`: Crawlers, harvesters, evaluators, and ETL utilities.
- `FoodData_Central_*`: USDA FoodData Central CSV datasets.
- `docs/`: Proposal drafts and documentation.
- `legacy/`: Archived or unused components.
- `BACKLOG.md`: Task list.
- `AGENTS.md`: Concise repo-specific guidance for coding agents; read this before broad codebase exploration.
- `UNIFIED_ARCHIVE_MERGE.md`: Archive merge notes.
- `home/arciel/`: Empty placeholder directory tree.

**Annotator App (frontend)**
Location: `apps/expert-annotator/`

Features:
- Supabase auth (email/password + Google).
- Paper list navigation with status badges.
- PDF viewer with nutrient-name highlighting and click-to-add popover.
- Food and nutrient autocomplete with ranking and search logging.
- Save draft, mark done, or skip papers.
- `done` / `draft` with `has_data=true` now requires at least one valid food item.
- Test mode toggle to disable DB writes and store actions locally.
- Global “definitely no data” button to remove a paper for all annotators.
- Suggestions modal stored in Supabase.

Run locally:
```bash
cd apps/expert-annotator
npm install
npm run dev
```

Build:
```bash
npm run build
npm run preview
```

Supabase schema and migrations:
- `apps/expert-annotator/migration.sql`: Current schema (entities, nutrients, papers, annotations, etc.).
- `apps/expert-annotator/supabase_schema.sql`: Older simplified schema.
- `apps/expert-annotator/run-migration.js`: Applies `migration.sql` (requires `DATABASE_URL`).
- `apps/expert-annotator/create_bucket.js`: Creates the `papers` storage bucket and policies.
- `apps/expert-annotator/auth_allowlist.sql`: Allowlist + auth hook for restricted signup.
- `apps/expert-annotator/add_user.js`: Scripted Supabase sign-up for a test user.
Notes:
- `papers` includes `ingest_status`, `audit_flag`, `rejection_reasons` for audit sampling.
- `paper_search_hits` stores metadata-stage search discoveries separately from downloaded papers, including source, language, rendered query text, search-gate score, filter score, and duplicate status.
- `paper_search_batches` and `paper_search_batch_hits` now store per-query-batch history separately from hit evidence, so the crawler can evaluate exact query batches by downstream label yield without duplicating raw hit rows.

Frontend config and templates:
- `apps/expert-annotator/index.html`: Vite HTML entry point.
- `apps/expert-annotator/vite.config.js`: Vite config.
- `apps/expert-annotator/eslint.config.js`: ESLint config.
- `apps/expert-annotator/README.md`: Default Vite template README.

Supabase tables used by the UI:
- `papers`, `annotations`, `food_items`, `annotation_nutrient_values`
- `entities`, `master_nutrients`, `search_sessions`, `suggestions`
- `paper_label_events`, `paper_global_labels`

**Data Pipeline**
Location: `services/data-pipeline/`

Language scope (current relevance filtering): English + Turkish only.
Crawler v2 now splits its query budget across independent English and Turkish workflows, with separate query phrases, anchors, weighted n-grams, concept-term ordering, and language-scoped embedding/metadata scoring.
Accepted-paper targets can now be set per language, so the crawler can fill English and Turkish quotas independently instead of collapsing everything into one shared accepted pool.
Crawler v2 now also runs as `Search -> Filter -> Acquisition`:
- `Search`: metadata-only retrieval from Europe PMC, OpenAlex, Semantic Scholar, and DergiPark.
- `Search` uses source-specific query rendering; Turkish metadata search is intentionally simpler on OpenAlex / Semantic Scholar, while DergiPark now searches a locally refreshed journal/article index instead of the old global OAI slice.
- `Filter`: metadata-only relevance scoring using language-scoped lexical signals, source priors, embeddings, and learned feedback n-grams.
- `Acquisition`: PDF/full-text download plus PDF validation only after a candidate passes the metadata filter.
- Query execution is now batch-aware: each source/query task is treated as a bounded search batch (`--query-limit` / `--search-batch-size`), feedback scores those batches by later labeled yield, and the crawler stops only after finishing the current batch once a language reaches its target. Overshoot inside the final batch is allowed.
- Negative evidence is penalty-based; the active crawler no longer uses hard-negative veto terms that reject a paper immediately just because one negative phrase appears somewhere in the text.
- Crawler state now records terminal paper decisions as `accepted` or `rejected` with the stage where that outcome was reached, and future runs skip those recorded papers until state is reset.
- Accepted PDF filenames are now identity-based (`pmcid_*`, `doi_*`, or hashed canonical keys) instead of title slugs.
- DergiPark indexing is now a separate step that refreshes archive issues and article pages into `dergipark_articles.jsonl`, with coverage tracked in `dergipark_refresh_report.json`.
- Crawl manifests now include both a `summary` section with per-language and per-source funnel counts (`hits`, `search_gate_pass`, `metadata_pass`, `pdf_fetch_fail`, `pdf_validation_fail`, `accepted`) plus rejection counts by stage, and a `dergipark_index` section with the journal/article coverage that was searched.

Main entry points:
- `services/data-pipeline/main.py`: Multi-source crawler v2.
- `services/data-pipeline/food_paper_crawler/`: Europe PMC crawler v1/v2 + ranking logic.
- `services/data-pipeline/orchestrator_cli.py`: Systematic PMC harvester (Entrez-based).
- `services/data-pipeline/harvester/foodcomp_crawler.py`: High-precision food composition crawler (PMC XML + PDF).
- `services/data-pipeline/test_harvest.py`: Live tests for PMC queries and filters.
- `services/data-pipeline/evaluator/main.py`: Phase 2 LLM/heuristic evaluation.
- `services/data-pipeline/evaluator/test_unified.py`: End-to-end extraction test using Gemini.

Key modules:
- `harvester/`: Entrez client, query builder, relevance filters, PMC coordinator, PDF downloader.
- `processing/`: Metadata extraction, table validation, term extraction.
- `extraction/`: LLM-based nutrient extraction and table parsing.
- `core/`: Knowledge base (dedup + term scoring), orchestrator, Supabase data source.

**Label Feedback Loop (L2)**
- Generates cumulative field-aware n-gram stats from labeled papers to update crawler query phrases and soft metadata scoring.
- Uses the latest label per user; a paper only counts as positive when the latest visible `draft`/`done` state also has `has_data=true`, `food_item_count > 0`, and `nutrient_value_count > 0`. Papers turn negative on global skip or 2+ unique skips. Mixed signals across labelers are treated as conflicts and excluded from both sides.
- Feedback export now classifies papers into English vs Turkish buckets and writes separate phrase / anchor / weighted-term pools for each workflow.
- Script: `python3 services/data-pipeline/food_paper_crawler/feedback/update_terms.py`
  - Requires `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
- Output: `services/data-pipeline/food_paper_crawler/feedback/latest.json` (loaded automatically by the crawler).
- `latest.json` now includes `languages.en` and `languages.tr` sections, plus language-specific query phrases, anchor phrases, weighted terms, pair scores, source priors, and concept-term scores.
- `latest.json` also includes language-scoped `batch_scores`, so exact query batches can be re-ranked by observed positive yield in later refill runs.
- `weighted_terms` stores cumulative per-term evidence for `title` and `title+abstract`, plus derived `good`, `bad`, and net scores.
- Seed composition phrases are treated as a small positive prior, not as permanently merged winners.
- The crawler uses each language's stored `weighted_terms` as soft scores only; feedback does not hard-reject papers.
- Learned query generation pairs a rotated food/nutrient term with a high-confidence phrase from the matching language workflow, while evergreen base queries remain for breadth in each language.
- The shared feedback refresh also writes `pair_scores`, `source_priors`, `concept_scores`, and discovery candidates so both source-term pairs and standalone concept terms can be ranked by observed yield instead of only lexical relevance.
- Batch feedback is tracked separately from hit evidence: query-batch performance is based on bounded search batches, while `paper_search_hits` stays idempotent as the canonical hit-evidence table.

Utility scripts (mostly one-off or experimental):
- `services/data-pipeline/scripts/ingestor.py`: Entrez harvester into `data/raw_lake`.
- `services/data-pipeline/scripts/ingestor_pdf.py`: PDF downloader with a focused composition query.
- `services/data-pipeline/scripts/ingestor_structured.py`: XML table extraction into `data/structured_lake`.
- `services/data-pipeline/scripts/config_targets.py`: Shared query configuration for script-based harvesters.
- `services/data-pipeline/scripts/refresh_dergipark_index.py`: Refresh the local DergiPark journal/article index from archive and article pages. Outputs `dergipark_journals.json`, `dergipark_articles.jsonl`, `dergipark_refresh_state.json`, and `dergipark_refresh_report.json` under the chosen `--data-dir`.
- `services/data-pipeline/scripts/upload_to_supabase.py`: Upload accepted PDFs to Supabase Storage, update `papers` by canonical identity, upsert metadata-stage discovery hits into `paper_search_hits` via deterministic `hit_key` values, and persist per-query batch history into `paper_search_batches` plus `paper_search_batch_hits`. Metadata-stage runs with zero accepted PDFs are now valid as long as search hits exist, and hits keep `paper_id` nullable until a paper row exists. Pass `--data-dir` or `--manifest`; the script now requires `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
- `services/data-pipeline/scripts/ensure_paper_stock.py`: Refresh feedback terms, refresh the DergiPark journal/article index, then crawl + upload until per-language targets are met. Supports `--target-en`, `--target-tr`, `--max-effort-tr`, `--quota-fallback`, `--dergipark-journal-limit`, and `--dergipark-max-issues-per-journal`, and prints both the crawler funnel summary and DergiPark index coverage after each cycle.
- `services/data-pipeline/scripts/check_db.py`, `check_db.js`, `test_frontend_fetch.js`: DB and frontend connectivity checks.
- `services/data-pipeline/scripts/check_rls.py`: Placeholder for RLS checks.

Logs and misc:
- `services/data-pipeline/migration.log`, `migration_run.log`: Output from `etl_usda_to_opennutri.py`.
- `services/data-pipeline/query.json`: JSON wrapper of the universal schema SQL.

Pipeline data outputs:
- `services/data-pipeline/data/raw_lake/`: Harvested PMC XML stored as JSON.
- `services/data-pipeline/data/raw_pdfs/`: Downloaded PDFs + `_harvest_metadata.json`.
- `services/data-pipeline/data/foodcomp/`: Strict crawler runs (PDFs, XML, `state.json`).
- `services/data-pipeline/data/verification_harvest/` + `harvest_full_check/`: Sample XML/JSON for checks.

**USDA ETL**
- `services/data-pipeline/etl_sr_legacy_to_opennutri.py`: Seed SR Legacy 2018-04 into Supabase.
- `services/data-pipeline/etl_usda_to_opennutri.py`: Seed Foundation Foods 2025-12-18 via REST.
- `services/data-pipeline/create_opennutri_schema.sql` + `query.json`: Universal schema for ETL.

**Datasets (FoodData Central)**
- `FoodData_Central_foundation_food_csv_2025-12-18/`: Foundation Foods dataset.
- `FoodData_Central_sr_legacy_food_csv_2018-04/`: SR Legacy dataset.
- `FoodData_Central_survey_food_csv_2024-10-31/`: Survey dataset.

**Docs**
- `docs/combined_application.md`: Combined proposal.
- `docs/proposal-sections/`: Per-section drafts.
- `docs/convert_to_docx.py`: Builds DOCX from markdown (currently expects `sections/`, may need updating to `docs/proposal-sections/`).
- `docs/FAAP.md`: Food engineering action points.
- `docs/draft_commercialization.txt`: Commercialization notes (TR).

**Python Dependencies**
- `sentence-transformers` (required for L2 embedding scoring; crawler will error if missing). Install with `python3 -m pip install sentence-transformers`.

**Environment Variables**
Frontend:
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`

Data pipeline and ETL:
- `SUPABASE_URL` (required for active crawler/upload/feedback write paths)
- `SUPABASE_SERVICE_ROLE_KEY` (required for write operations)
- `GEMINI_API_KEY` (required for LLM evaluator/extractor)
- `SUPABASE_RESOLVE_IP` (optional; IP pinning for SR legacy ETL)
- `DATABASE_URL` (required for `apps/expert-annotator/run-migration.js`)

**Development Notes**
- The annotator app is deployed on Vercel.
- Supabase is used for auth and application data.
- PDF highlighting is tricky because PDF.js text layers may split visible words into multiple spans.

**Contributing**
When taking a backlog item:
- reproduce the issue first
- edit source files, not built artifacts
- prefer minimal, testable fixes
- validate app changes with `npm run build`

**Legacy**
Moved into `legacy/` because these are not used by the current app/pipeline but might be useful later:
- `legacy/archive/`: Old Streamlit batch crawler UI.
- `legacy/services/data-pipeline/scraper.py`: Simple HTML scraper (`NutriCrawler`).
- `legacy/expert-annotator-vercel-recovery/`: Vercel deployment artifact snapshot and notes.

**Security / Secrets Note**
Some scripts and configs include hardcoded Supabase URLs/keys or database credentials, intended for internal use. Before sharing the repo, review and rotate:
- `services/data-pipeline/config.py`
- `services/data-pipeline/test_pg.py`
- `services/data-pipeline/scripts/check_db.js`
- `apps/expert-annotator/add_user.js`
- `apps/expert-annotator/create_bucket.js`
