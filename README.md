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

**Reviewer Docs**
- `docs/reviewer_sop_en.md`: Worker-facing English quick guide for live paper review.
- `docs/reviewer_sop_en.docx`: Word export for sharing with reviewers.
- `docs/reviewer_workflow_map.md`: Internal workflow map for the reviewer UI, RPCs, tables, and refill/routing scripts.

**Annotator App (frontend)**
Location: `apps/expert-annotator/`

Features:
- Supabase auth (email/password + Google).
- Shared general labeling queue: active labelers see the same available `human_review_ready` papers that already have a latest normalized Gemini `has_data` payload, and a paper leaves the queue after the first general submission. AI `no_usable_data` papers are provisional skips and stay out of the default labeler queue and cockpit paper overview.
- Drafts do not claim papers; stale in-progress duplicate submissions are allowed until reviewer approval finalizes the paper, and each exact payload is retained in `paper_label_submissions`.
- Editable queue papers with no saved annotation open as AI-prefilled verification tasks from the latest `ai_extractions.normalized_payload_json`; the AI output is preloaded into editable food/nutrient rows, existing drafts/submissions are never overwritten, and labelers see only DB-compliant extraction rows plus compact matched/custom/rejected row badges, not AI reasoning.
- Reviewer approval workflow: Arciel currently has `can_approve_labels=true`; Arciel submissions auto-accept, while non-Arciel submissions go to an approver-only Approval page where Arciel can edit and accept final truth.
- Read-only tester/developer cockpit accounts can inspect Approval, Dashboard, and Useful Papers views but cannot approve or mutate live rows.
- PDF viewer with table-scoped nutrient-name highlighting and click-to-add popover.
- Food and nutrient autocomplete with ranking and search logging.
- Save draft, submit usable-data extraction, or submit no-usable-data.
- Labelers can send an `Ask for Help` request from a general-queue paper when the data is confusing; this creates a cockpit-visible review item with paper, AI, reviewer, and draft-food context.
- Final `has_data=true` submissions now require at least one valid food item with at least one nutrient row.
- Exact-match general submission snapshots are stored in `paper_label_submissions`; accepted/corrected reviewer payloads and mistake diffs are stored in `paper_label_approvals`.
- Cockpit users can inspect general queue health, pending approval, labeler performance, source yield, and detailed correction history.
- Cockpit users can also inspect AI-routing state, edit stage thresholds (`positive_threshold`, `negative_threshold`, `audit_rate`), and review each useful paper's latest normalized AI extraction from the Useful Papers screen.
- The cockpit-only Useful Papers view shows useful paper routing state, latest AI extraction details, general submissions, approval status, and final outcomes. Provisional AI no-data skips are hidden from this default overview.
- Cockpit write actions remain restricted to non-tester cockpit users through `current_user_has_cockpit_write_access()`.
- Test mode toggle to disable DB writes and store actions locally.
- Suggestions now split by role: regular labelers can submit from the `?` button and track statuses in a `My Suggestions` view, while cockpit/admin users triage all incoming suggestions and help requests in the cockpit `Suggestions` tab (including attachment previews).

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
- `apps/expert-annotator/check-workflow-schema.mjs`: Verifies the live reviewer workflow tables/functions after migration.
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
- `reviewer_profiles`, plus legacy `reviewer_slots` / `reviewer_slot_members`
- `paper_label_submissions`, `paper_label_approvals`, `paper_review_outcomes`
- legacy `paper_slot_assignments`, `paper_user_assignments`, `paper_assignment_submissions`, `paper_conflicts`
- `routing_stage_configs`, `paper_stage_tasks`, `ai_extractions`

**Data Pipeline**
Location: `services/data-pipeline/`

Language scope (current relevance filtering): English + Turkish only.
Accepted papers now pass through a staged model router before humans ever see them:
`crawl -> upload -> Gemini extraction -> human_review_ready or provisional skip`.
The active enqueue stage is currently `gemini_flash_db_payload_v2`. The `gemma_proof_extraction_v1` screening stage is retained but inactive until a compatible cheap model is validated.
The AI model may extract broad candidate rows, but routing and AI finalization use a deterministic `normalized_payload_json` with the same contract as general human label submissions:
`decision_kind`, DB/custom food identity, raw food name, preparation state, DB/custom nutrient identity, raw nutrient name, value, unit, basis, sample size, confidence, source citation, and row metadata.
The AI extraction prompt is scoped to useful OpenNutri food composition data only. Papers about what a nutrient, supplement, extract, dose, diet, or food does to health outcomes, biomarkers, cells, animals, microbes, processing results, sensory scores, or other responses are treated as empty unless they also report useful direct food/product composition tables. One-off experimental treatment/formulation variants are no usable data unless they represent stable real-world foods/products worth adding to the DB.
The evaluator prompt includes the full `master_nutrients` ID/name catalog plus high-signal food candidates matched from the paper text, but not the full food catalog. The normalizer accepts only DB-compatible units (`g/100g`, `mg/100g`, `μg/100g`, `kcal/100g`, `kJ/100g`, `IU/100g`, `%`) on supported bases, verifies AI-provided DB IDs against current reference rows, falls back to exact food/nutrient name or alias matching, and preserves unresolved foods/nutrients as explicit custom rows. Unsupported rows are rejected before routing. Raw model responses and normalization summaries remain in `ai_extractions.raw_data`; the DB-aligned review payload now preserves the row context needed for approval and hashing.
The evaluator accepts the requested JSON object shape plus two common model variants: a top-level array of candidate composition rows, and nested `food -> nutrients[]` rows. Those variants are flattened before normalization so valid model output does not become a retry-loop parse error.
All model stages share the same master extraction contract. The inactive Gemma screening stage can still enqueue Gemini for `has_data` outputs if re-enabled, but normal daily ops currently routes new uploads directly to Gemini. Gemini `no_usable_data` outputs become provisional skips; Gemini `has_data` outputs with normalized rows enter human review.
Daily ops are designed as a recursive high-precision loop:
`process queued Gemini tasks -> process queued non-Gemini screening tasks if any -> crawl/upload when no model queue is available -> process newly queued Gemini tasks -> repeat`.
The daily automation target is 20 Gemini calls. Cheap screening is disabled for now because the previous `gemma-3-27b-it` model is no longer available through the Gemini API.
Arciel is currently the only configured approver through `reviewer_profiles.can_approve_labels = true`; Peri, Aleyna, Aysegul, Daine, and the `f221229078@ktun.edu.tr` account are general-queue labelers unless their access flags change.
Each orchestrator iteration stops with a machine-readable `stopped_reason` and `terminal` flag.
Terminal stop reasons are: the 20-call daily budget is consumed (`daily_ai_call_budget_exhausted`), the first AI paper in an iteration immediately hits quota (`ai_first_task_quota_limited`), a non-retryable stage model/configuration error is detected (`ai_stage_configuration_error`), a crawl/AI pass produces no useful work (`no_progress`), or dry-run exit.
Non-terminal stop reasons, such as `ai_run_budget_exhausted`, `ai_quota_limited_after_progress`, and `max_cycles`, make the GitHub Actions controller sleep 5 minutes and invoke the recursive runner again.
If AI processing creates `human_review_ready` papers and then hits quota or the per-iteration AI budget, the runner performs one final stock check before exiting that iteration so those papers can enter the shared queue immediately.
This is automated by GitHub Actions in `.github/workflows/daily-ops.yml` around the Gemini RPD reset. The workflow is scheduled once per America/Los_Angeles day at `00:17`; two UTC cron entries cover DST, and the gate selects the active cron by Pacific UTC offset so delayed GitHub runners still execute. After startup, it loops internally every 5 minutes until the orchestrator returns a terminal stop reason.
Each controller iteration uses `--max-ai-tasks 5` and the workflow tracks cumulative `daily_ai_tasks_used` until it reaches `--daily-ai-call-budget 20`.
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
- Resolved truth now comes from `paper_review_outcomes` first; legacy `paper_label_events` / `paper_global_labels` are fallback only for older papers that do not yet have resolved outcomes.
- `paper_review_outcomes.truth_source_kind = 'ai_model'` rows are stored for provenance and final paper state, but they are currently excluded from the human-truth feedback export.
- Pending and superseded general submissions do not feed feedback. Only accepted reviewer truth in `paper_review_outcomes` feeds current human-truth learning.
- Legacy `paper_label_events` / `paper_global_labels` fallback remains only for older unresolved papers without a resolved outcome.
- Feedback export now classifies papers into English vs Turkish buckets and writes separate phrase / anchor / weighted-term pools for each workflow.
- Script: `python3 services/data-pipeline/food_paper_crawler/feedback/update_terms.py`
  - Requires `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
- Output: `services/data-pipeline/food_paper_crawler/feedback/latest.json` (loaded automatically by the crawler).
- Automatic daily ops refreshes feedback terms only when it actually reaches the crawler/refill path. Pure queued-AI draining does not refresh feedback. Once crawler refill is needed, `ensure_paper_stock.run_refill_cycle` runs `update_terms.py` immediately before DergiPark refresh and search unless `--skip-feedback` is explicitly passed.
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
- `services/data-pipeline/scripts/process_stage_queue.py`: Claims one retry-fair batch of queued model stage tasks per run, preferring lower `attempt_count`, then higher `priority`, then older creation order. It fetches reference foods/nutrients, runs `UnifiedEvaluator` with the nutrient catalog and text-matched food candidates in prompt, standardizes candidate rows into the human-submission-shaped `normalized_payload_json`, stores routed `ai_extractions`, enqueues follow-up model stages for useful screening outputs, creates provisional skips for no-data outputs, and sends only useful Gemini outputs to human review. Retryable processing errors return the task and paper to `queued_for_ai` with `last_error` preserved; non-retryable model-configuration errors mark the task failed and stop automation with `ai_stage_configuration_error`.
- `services/data-pipeline/scripts/daily_ops_orchestrator.py`: Recursive ops runner for automation. It drains Gemini extraction work within the daily Gemini call budget, drains any queued non-Gemini screening work with a separate larger budget, crawls/uploads when no model queue is available, then processes newly queued Gemini work. Each invocation returns a JSON `stopped_reason`, `terminal`, and cumulative daily Gemini count; the workflow controller repeats non-terminal invocations every 5 minutes until 20 Gemini calls are used or a terminal stop occurs.
- `services/data-pipeline/scripts/backfill_ai_routing.py`: Enqueue and process the active AI stage for existing papers, then cancel unresolved legacy slot assignments only for papers that ended outside `human_review_ready`. The one-time `--reset-open-human-assignments` mode refuses to run if old assignment submissions, new general label submissions, or human-truth outcomes exist.
- `services/data-pipeline/scripts/ensure_paper_stock.py`: Refresh feedback terms, refresh the DergiPark journal/article index, then crawl + upload until per-language targets are met. It counts only `papers.routing_status = 'human_review_ready'` papers with a latest normalized AI decision payload, no final outcome, and no pending/accepted general submission as available shared queue stock, and drains the AI queue after upload. Supports `--target-en`, `--target-tr`, `--max-ai-tasks`, `--max-effort-tr`, `--quota-fallback`, `--dergipark-journal-limit`, and `--dergipark-max-issues-per-journal`, and prints both the crawler funnel summary and DergiPark index coverage after each cycle.
- `services/data-pipeline/scripts/refill_assignment_queue.py`: Protected ops job retained under the old filename for compatibility. It no longer creates slot/user assignments; it reports shared general queue stock from Gemini `has_data` papers only, drains queued model work before giving up, and triggers crawler refill when visible human-ready stock is below `--target-open`. Default target is 50 visible shared-queue papers.
- `services/data-pipeline/scripts/seed_training_stock.py`: Legacy read-only inspection helper for the old developer-training queue. General queue stock now uses `refill_assignment_queue.py` / `get_general_queue_papers()`.
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
- Reviewer workflow is now general-queue plus approval:
  active labelers see the same available paper list; submitting creates an immutable `paper_label_submissions` row and removes the paper from the visible queue.
  Arciel currently has `can_approve_labels=true`; approval rights are configurable in reviewer admin.
  Arciel submissions auto-accept; other submissions go to Approval, where Arciel can edit and accept the final payload.
  `paper_label_approvals.correction_diff_json` records what changed between the labeler payload and accepted reviewer payload.
  `tester_access` keeps an account read-only, while `tester_access + cockpit_access` can inspect Approval, Dashboard, and Useful Papers without mutating live state.
  Legacy slot membership tables remain in the schema for old audit data but should not be used for new queue work.
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
