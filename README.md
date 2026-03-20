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

Main entry points:
- `services/data-pipeline/main.py`: Europe PMC crawler v2 (PDF download + validation).
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
- Generates positive/negative phrases from labeled papers to update crawler search/filter terms and embedding anchors.
- Uses the latest label per user; any `has_data=true` draft or done counts as positive, and papers turn negative on global skip or 2+ unique skips. Mixed signals across labelers are treated as conflicts and excluded from both sides.
- Script: `python3 services/data-pipeline/food_paper_crawler/feedback/update_terms.py`
  - Requires `SUPABASE_URL` (or `VITE_SUPABASE_URL`) and `SUPABASE_SERVICE_ROLE_KEY`.
- Output: `services/data-pipeline/food_paper_crawler/feedback/latest.json` (loaded automatically by the crawler).

Utility scripts (mostly one-off or experimental):
- `services/data-pipeline/scripts/ingestor.py`: Entrez harvester into `data/raw_lake`.
- `services/data-pipeline/scripts/ingestor_pdf.py`: PDF downloader with a focused composition query.
- `services/data-pipeline/scripts/ingestor_structured.py`: XML table extraction into `data/structured_lake`.
- `services/data-pipeline/scripts/config_targets.py`: Shared query configuration for script-based harvesters.
- `services/data-pipeline/scripts/upload_to_supabase.py`: Upload PDFs to Supabase Storage and insert `papers` (including audit-flagged rejects).
- `services/data-pipeline/scripts/ensure_paper_stock.py`: Refresh feedback terms, then crawl + upload when available UI papers are at/below a threshold; repeat until a target count is reached.
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
