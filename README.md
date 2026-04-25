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
- Assignment-driven labeling queue with a strict personal `My Queue`; cockpit users now inspect the global paper/assignment state from a separate `All Papers` admin screen instead of mixing it into the labeling view.
- Read-only developer-training accounts now use a virtual bilingual `My Queue` when `tester_access=true` and `cockpit_access=true`: they keep the normal labeling/admin UI, but annotation/admin/conflict actions stay local-only while new suggestion submissions still persist to Supabase.
- PDF viewer with table-scoped nutrient-name highlighting and click-to-add popover.
- Food and nutrient autocomplete with ranking and search logging.
- Save draft, submit usable-data extraction, or submit no-usable-data.
- `done` / `draft` with `has_data=true` now requires at least one valid food item.
- Exact-match submission snapshots are stored in `paper_assignment_submissions`.
- Cockpit users can inspect queue health, reviewer agreement/accuracy, source yield, and conflict queues.
- Cockpit users can also inspect AI-routing state, edit stage thresholds (`positive_threshold`, `negative_threshold`, `audit_rate`), and review per-paper AI provenance from the `All Papers` screen.
- The cockpit-only `All Papers` view includes an expandable AI detail panel with model decision, confidence, routing bucket, reasoning, normalized DB payload, rejected/custom row counts, raw response metadata, and any later human-outcome comparison.
- Cockpit write actions remain restricted to non-tester cockpit users through `current_user_has_cockpit_write_access()`.
- Test mode toggle to disable DB writes and store actions locally.
- Suggestions modal now writes `suggestion_review` records into `backlog_review_items`, supports image attachments with validation, and cockpit reviewers triage them in the Suggestions tab (including attachment previews).

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
- `apps/expert-annotator/check-workflow-schema.mjs`: Verifies the live assignment-workflow tables/functions after migration.
- `apps/expert-annotator/create_bucket.js`: Creates the `papers` storage bucket and policies.
- `apps/expert-annotator/auth_allowlist.sql`: Allowlist + auth hook for restricted signup.
- `apps/expert-annotator/add_user.js`: Scripted Supabase sign-up for a test user.
Notes:
- `papers` includes `ingest_status`, `audit_flag`, `rejection_reasons` for audit sampling.
- `papers` now also carries paper-level AI routing summary fields:
  `current_stage_key`, `routing_status`, `routing_bucket`, `route_destination`, `latest_ai_extraction_id`, `routing_updated_at`.
- `paper_search_hits` stores metadata-stage search discoveries separately from downloaded papers, including source, language, rendered query text, search-gate score, filter score, and duplicate status.
- `paper_search_batches` and `paper_search_batch_hits` now store per-query-batch history separately from hit evidence, so the crawler can evaluate exact query batches by downstream label yield without duplicating raw hit rows.
- Suggestion images are stored in the private `suggestion-attachments` Supabase Storage bucket; attachment metadata is saved in `backlog_review_items.attachments`.

Frontend config and templates:
- `apps/expert-annotator/index.html`: Vite HTML entry point.
- `apps/expert-annotator/vite.config.js`: Vite config.
- `apps/expert-annotator/eslint.config.js`: ESLint config.
- `apps/expert-annotator/README.md`: Default Vite template README.

Supabase tables used by the UI:
- `papers`, `annotations`, `food_items`, `annotation_nutrient_values`
- `entities`, `master_nutrients`, `search_sessions`, `backlog_review_items`
- `paper_label_events`, `paper_global_labels`
- `reviewer_slots`, `reviewer_profiles`, `reviewer_slot_members`
- `paper_slot_assignments`, `paper_user_assignments`
- `paper_assignment_submissions`, `paper_conflicts`, `paper_review_outcomes`
- `routing_stage_configs`, `paper_stage_tasks`, `ai_extractions`

**Data Pipeline**
Location: `services/data-pipeline/`

Language scope (current relevance filtering): English + Turkish only.
Accepted papers now pass through a staged AI router before humans ever see them:
`crawl -> upload -> AI queue -> routing -> human_review_ready or AI-finalized outcome`.
The active stage is currently `gemini_flash_db_payload_v2`.
The AI model may extract broad candidate rows, but routing and AI finalization use only a deterministic `normalized_payload_json` with the same contract as human assignment submissions:
`decision_kind`, `food_items[].food_name`, `food_fdc_id`, `is_custom_food`, and `nutrients[].nutrient_id`, `nutrient_name`, `value`, `unit`.
The normalizer accepts only DB-compatible units (`g/100g`, `mg/100g`, `μg/100g`, `kcal/100g`, `kJ/100g`, `IU/100g`, `%`) on supported bases, exact food matches against `entities.canonical_name`, and exact nutrient name/alias matches against `master_nutrients`; unresolved foods/nutrients remain custom and unsupported rows are rejected before routing.
Daily ops are designed as a recursive top-up loop:
`assign existing human-ready papers -> process already queued AI papers -> crawl/upload only if reviewer deficits remain -> process the new AI queue -> repeat`.
The runner stops cleanly when all reviewer queues are full, when Gemini quota/rate limit is hit, or when the configured cycle cap is reached.
This is automated by GitHub Actions in `.github/workflows/daily-ops.yml` at 07:00 Europe/Istanbul (`04:00 UTC`) and can also be run manually:
`python3 services/data-pipeline/scripts/daily_ops_orchestrator.py`.
The scheduled job runs on GitHub-hosted infrastructure, not on this laptop. It talks to Supabase, Supabase Storage, and Gemini using GitHub repository secrets.
Crawler v2 now splits its query budget across independent English and Turkish workflows, with separate query phrases, anchors, weighted n-grams, concept-term ordering, and language-scoped embedding/metadata scoring.
Accepted-paper targets can now be set per language, so the crawler can fill English and Turkish quotas independently instead of collapsing everything into one shared accepted pool.
Crawler v2 now also runs as `Search -> Filter -> Acquisition`:
- `Search`: metadata-only retrieval from Europe PMC, OpenAlex, Semantic Scholar, and DergiPark.
- `Search` uses source-specific query rendering; Turkish metadata search is intentionally simpler on OpenAlex / Semantic Scholar, while DergiPark now searches a locally refreshed journal/article index instead of the old global OAI slice.
- `Filter`: metadata-only relevance scoring using language-scoped lexical signals, source priors, embeddings, and learned feedback n-grams.
- `Acquisition`: PDF/full-text download plus PDF validation only after a candidate passes the metadata filter.
- Query execution is now batch-aware: each source/query task is treated as a bounded search batch, but the batch size is counted at the search-gate handoff, not on raw hits returned by the source. In practice `--query-limit` / `--search-batch-size` means “up to N unique papers that pass the initial search gate and move into deeper scoring,” while the crawler may scan a wider raw result pool underneath to fill that batch. Feedback scores those batches by later labeled yield, and the crawler stops only after finishing the current batch once a language reaches its target. Overshoot inside the final batch is allowed.
- Negative evidence is penalty-based; the active crawler no longer uses hard-negative veto terms that reject a paper immediately just because one negative phrase appears somewhere in the text.
- Crawler state now records terminal paper decisions as `accepted` or `rejected` with the stage where that outcome was reached, and future runs skip only those recorded `paper_states` entries until state is reset. Legacy `seen_ids` are no longer consulted for skip decisions.
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
- Resolved truth now comes from `paper_review_outcomes` first; legacy `paper_label_events` / `paper_global_labels` are fallback only for older papers that do not yet have resolved assignment outcomes.
- `paper_review_outcomes.truth_source_kind = 'ai_model'` rows are stored for provenance and final paper state, but they are currently excluded from the human-truth feedback export.
- Uses the latest label per user; a paper only counts as positive when the latest visible `draft`/`done` state also has `has_data=true`, `food_item_count > 0`, and `nutrient_value_count > 0`. Papers turn negative on global skip or 2+ unique skips. Mixed signals across labelers are treated as conflicts and excluded from both sides.
- In the assignment workflow, `Definitely No Data` is a slot-level global skip: one reviewer lane can mark the paper globally unusable, which cancels the remaining assignments and writes final `global_skip` truth immediately.
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
- `services/data-pipeline/scripts/backfill_paper_workflow_language.py`: Backfill only the legacy `papers.workflow_language IS NULL` rows using `food_paper_crawler.language_utils.detect_supported_language(..., default="en")`. Supports `--dry-run`.
- `services/data-pipeline/scripts/refresh_dergipark_index.py`: Refresh the local DergiPark journal/article index from archive and article pages. Outputs `dergipark_journals.json`, `dergipark_articles.jsonl`, `dergipark_refresh_state.json`, and `dergipark_refresh_report.json` under the chosen `--data-dir`.
- `services/data-pipeline/scripts/upload_to_supabase.py`: Upload accepted PDFs to Supabase Storage, update `papers` by canonical identity, upsert metadata-stage discovery hits into `paper_search_hits` via deterministic `hit_key` values, and persist per-query batch history into `paper_search_batches` plus `paper_search_batch_hits`. Metadata-stage runs with zero accepted PDFs are now valid as long as search hits exist, and hits keep `paper_id` nullable until a paper row exists. Pass `--data-dir` or `--manifest`; the script now requires `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
- `services/data-pipeline/scripts/process_stage_queue.py`: Claims one oldest-first batch of queued AI stage tasks per run, runs `UnifiedEvaluator`, standardizes candidate rows into the human-submission-shaped `normalized_payload_json`, stores routed `ai_extractions`, and either finalizes high-confidence AI outcomes or releases low-confidence/audited papers to human review. AI processing errors return the task and paper to `queued_for_ai` with `last_error` preserved for the next run.
- `services/data-pipeline/scripts/daily_ops_orchestrator.py`: Daily recursive ops runner for automation. It first tops up reviewers from existing `human_review_ready` stock, then drains already queued AI work with `--stop-on-quota`, then crawls/uploads only when deficits remain, and stops for the day if Gemini quota is exhausted.
- `services/data-pipeline/scripts/backfill_ai_routing.py`: Enqueue and process the active AI stage for existing papers, then cancel unresolved human assignments only for papers that ended outside `human_review_ready`. The one-time `--reset-open-human-assignments` mode first refuses to run if submitted/human-truth work exists, cancels unresolved human assignment rows, and queues every existing paper for AI without draining unless `--drain-after-reset` is passed.
- `services/data-pipeline/scripts/ensure_paper_stock.py`: Refresh feedback terms, refresh the DergiPark journal/article index, then crawl + upload until per-language targets are met. It now counts only `papers.routing_status = 'human_review_ready'` as available reviewer stock and drains the AI queue after upload. Supports `--target-en`, `--target-tr`, `--max-effort-tr`, `--quota-fallback`, `--dergipark-journal-limit`, and `--dergipark-max-issues-per-journal`, and prints both the crawler funnel summary and DergiPark index coverage after each cycle.
- `services/data-pipeline/scripts/refill_assignment_queue.py`: Protected ops job that tops reviewer queues back up to a target open backlog, creates slot/user assignments only from `human_review_ready` papers ordered by oldest routing update/creation time, reuses cancelled assignment rows when reset papers return from AI, drains queued AI work before giving up on stock, and triggers crawler refill when the human-ready pool is exhausted.
- `services/data-pipeline/scripts/seed_training_stock.py`: Read-only inspection helper that prints the exact bilingual pool and ordering logic feeding read-only developer-training queues. Supports `--dry-run`.
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
- Data pipeline dependencies are listed in `services/data-pipeline/requirements.txt`.
- `sentence-transformers` is required for L2 embedding scoring; crawler will error if missing.

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

GitHub Actions daily ops requires repository secrets with these same names:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `GEMINI_API_KEY`

**Development Notes**
- The annotator app is deployed on Vercel.
- Supabase is used for auth and application data.
- Reviewer workflow is now slot-based:
  `arciel`, `peri`, and `aleyna` are the official reviewer slots.
  The cockpit can now create reviewer profiles, assign official slots, and add/remove shadow slot memberships without direct SQL edits.
  `tester_access` keeps an account read-only, while `tester_access + cockpit_access` creates a read-only developer-training account with admin visibility and a virtual bilingual queue.
  Daine should be configured there as an English-only shadow member inside the Arciel slot when her actual reviewer profile is available.
  Peri and Aleyna can be assigned papers before their first login because `paper_user_assignments.auth_user_id` is backfilled later by `sync_reviewer_profile`.
- PDF highlighting is table-scoped and precision-first.
  The viewer builds a page-local allowlist from PDF.js text content and only highlights detected table body/header cells plus table caption/title lines.
  If a page has no confident local table anchor, or a table continues onto a captionless page, the viewer suppresses highlights on that page instead of falling back to page-wide prose matching.
  Highlight markup is still injected through `react-pdf` `customTextRenderer` on single PDF text items, so matches split across multiple items inside a table are still a separate follow-up.

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
