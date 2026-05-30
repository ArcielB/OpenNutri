# OpenNutri

OpenNutri is a food composition data project with two main parts:
- A React/Vite "Annotator" web app for labeling nutrition tables from source PDFs tracked by URL.
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
- Editable queue papers with no saved annotation open as AI-prefilled verification tasks from the latest `ai_extractions.normalized_payload_json`; the AI output is preloaded directly into editable food/nutrient rows, existing drafts/submissions are never overwritten, and labelers see DB-compliant extraction rows without AI reasoning or a separate AI-prefill status banner.
- Reviewer approval workflow: Arciel currently has `can_approve_labels=true`; Arciel submissions auto-accept, while non-Arciel submissions go to an approver-only Approval page where Arciel can edit and accept final truth.
- Read-only tester/developer accounts can inspect cockpit views (Approval, Dashboard, Pipeline, Useful Papers, Suggestions) when `tester_access=true`, but cannot approve or mutate live rows.
- PDF viewer with table-scoped nutrient-name highlighting, click-to-add popover, and a compact Sources strip that jumps to matched table/paragraph text or page hints, including printed-page hints from journal PDFs. Paper PDFs load from `papers.pdf_url` when available, with legacy Supabase Storage URLs only as fallback.
- Food and nutrient autocomplete with ranking and search logging.
- Save draft, submit usable-data extraction, or submit no-usable-data.
- Labelers can send an `Ask for Help` request from a general-queue paper when the data is confusing; this creates a cockpit-visible review item with paper, AI, reviewer, and draft-food context.
- Final `has_data=true` submissions now require at least one valid food item with at least one nutrient row.
- Exact-match general submission snapshots are stored in `paper_label_submissions`; accepted/corrected reviewer payloads and mistake diffs are stored in `paper_label_approvals`.
- Cockpit users can inspect general queue health, pending approval, labeler performance, source yield, and detailed correction history.
- Cockpit users can also inspect AI-routing state, edit stage thresholds (`positive_threshold`, `negative_threshold`, `audit_rate`), and review each useful paper's latest normalized AI extraction from the Useful Papers screen.
- Cockpit users can inspect a simple Pipeline funnel from crawler search to PDF acquisition, Small model, Medium model, Strong model, and human review. The model-stage UI keeps those role names stable and shows the current model specification in parentheses, for example `Small model (Gemma 31B)`. Funnel counters are role/stage counters rather than model-name counters; historical direct Small -> Strong papers from before Medium existed are counted as Medium-entered and Medium-kept so the middle stage does not start from zero.
- The cockpit-only Useful Papers view shows useful paper routing state, latest AI extraction details, general submissions, approval status, and final outcomes. Provisional AI no-data skips are hidden from this default overview.
- Cockpit write actions remain restricted to non-tester cockpit users through `current_user_has_cockpit_write_access()`.
- Test mode toggle to disable DB writes and store actions locally.
- Suggestions now split by role: regular labelers can submit from the `Suggest` button and track statuses in a `My Suggestions` view, while cockpit/admin users triage all incoming suggestions and help requests in the cockpit `Suggestions` tab.
- Suggestion image attachments are opened from signed storage URLs at view time; both regular labelers (`My Suggestions`) and cockpit/admin reviewers (`Suggestions`) can preview and open full images.

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
- `apps/expert-annotator/create_bucket.js`: Legacy helper for the opt-in `papers` storage bucket. Current paper ops do not store PDFs in Supabase Storage by default.
- `apps/expert-annotator/auth_allowlist.sql`: Allowlist + auth hook for restricted signup. The allowlist table has RLS enabled and client-role table privileges revoked; signup checks go through the security-definer auth hook.
- `apps/expert-annotator/add_user.js`: Scripted Supabase sign-up for a test user.
Notes:
- `papers` includes `ingest_status`, `audit_flag`, `rejection_reasons` for audit sampling.
- `papers` now also carries paper-level AI routing summary fields:
  `current_stage_key`, `routing_status`, `routing_bucket`, `route_destination`, `latest_ai_extraction_id`, `routing_updated_at`.
- `papers.pdf_url` is the source PDF URL used by model workers and the annotator. Supabase paper-PDF storage is disabled by default to avoid storage and egress caps.
- `paper_search_hits` stores metadata-stage search discoveries separately from downloaded papers, including source, language, source PDF URL when known, rendered query text, search-gate score, filter score, and duplicate status.
- `paper_search_batches` and `paper_search_batch_hits` now store per-query-batch history separately from hit evidence, so the crawler can evaluate exact query batches by downstream label yield without duplicating raw hit rows.
- `get_pipeline_ops_snapshot(p_start_at, p_end_at, p_workflow_language, p_paper_id)` is the cockpit-only RPC backing the Pipeline tab. It is `SECURITY DEFINER` so cockpit users can see aggregate `paper_stage_tasks` queue/error state without granting direct task-table reads to every authenticated user.
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

Language scope (current operational mode): English only. The Turkish/DergiPark crawler path remains in the codebase for later reactivation, but normal refill and daily ops defaults request `tr=0` and search Europe PMC, OpenAlex, and Semantic Scholar only.
Accepted papers now pass through a staged model router before humans ever see them:
`crawl -> upload -> Gemma proof extraction -> Gemini Flash-Lite triage -> Gemini final extraction -> human_review_ready or provisional skip`.
The pipeline is a 3-stage cascade: `gemma_proof_extraction_v1` (`gemma-4-31b-it`, retryable same-stage fallback `gemma-4-26b-a4b-it`) screens and ranks ~1500 papers/day -> `gemini_flash_lite_triage_v1` (`gemini-3.1-flash-lite`, ~500/day) re-ranks the strongest Gemma candidates -> `gemini_flash_db_payload_v2` (`gemini-3.5-flash`, ~20/day) is the final extraction. Each stage ranks via `score_followup_priority`; per-stage daily targets plus priority-ordered claiming make each stage process the top-N of the previous stage's output (1500 -> top 500 -> top 20).
The AI model may extract broad candidate rows, but routing and AI finalization use a deterministic `normalized_payload_json` with the same contract as general human label submissions:
`decision_kind`, DB/custom food identity, raw food name, preparation state, DB/custom nutrient identity, raw nutrient name, value, unit, basis, sample size, confidence, source citation, and row metadata. Row metadata preserves broad evidence hints such as `table_label`, `page_hint`, `source_quote`, `source_location_type`, `section_heading`, and `paragraph_hint`.
The AI extraction prompt is scoped to useful OpenNutri food composition data only. Papers about what a nutrient, supplement, extract, dose, diet, or food does to health outcomes, biomarkers, cells, animals, microbes, processing results, sensory scores, or other responses are treated as empty unless they also report useful direct food/product composition tables. One-off experimental treatment/formulation variants are no usable data unless they represent stable real-world foods/products worth adding to the DB.
The evaluator prompt includes the full `master_nutrients` ID/name catalog plus high-signal food candidates matched from the paper text, but not the full food catalog. The normalizer accepts only DB-compatible units (`g/100g`, `mg/100g`, `μg/100g`, `kcal/100g`, `kJ/100g`, `IU/100g`, `%`) on supported bases, verifies AI-provided DB IDs against current reference rows, falls back to exact food/nutrient name or alias matching, and preserves unresolved foods/nutrients as explicit custom rows. Unsupported rows are rejected before routing. Raw model responses and normalization summaries remain in `ai_extractions.raw_data`; the DB-aligned review payload now preserves the row context needed for approval and hashing.
The evaluator accepts the requested JSON object shape plus three common model variants: a top-level array of candidate composition rows, a single result object wrapped in a top-level array, and nested `food -> nutrients[]` rows. Those variants are flattened before normalization so valid model output does not become a retry-loop parse error.
Gemma, Flash-Lite, and final Gemini share the same master extraction contract. Gemma `has_data` outputs enqueue Flash-Lite with a priority score based on raw and normalized row counts, table/evidence/per-100g signals, unsupported-unit rows, direct food-composition language, source quality, confidence, and soft penalties for review/database aggregate, feed/digestibility, sensory/outcome, supplement, or one-off formulation signals. Flash-Lite then enqueues the final Gemini stage from its strongest `has_data` outputs. Raw-positive Gemma outputs can still advance when normalized rows are empty if Gemma returned candidate rows or a clear `has_data` decision, so downstream Gemini-family stages can validate likely positives instead of losing them to parser/normalizer drift. Strict normalization still controls final Gemini/human queue entry. Gemma 31B retryable timeout/quota/transient model failures retry the same task once with the configured 26B fallback; non-retryable model configuration failures stop automation as configuration errors. Empty SDK exceptions are stored with exception type, `repr`, and traceback tail so retry/fallback classification still works. Any-stage `no_usable_data` outputs become provisional skips. Model workers fetch paper PDFs on demand from `papers.pdf_url` and keep only DB routing/audit rows, so rejected papers do not accumulate Supabase Storage. Final Gemini `has_data` outputs with normalized rows enter human review.
Daily ops are resumable ticks rather than one long once-a-day controller:
`scheduled tick -> serialized refill controller requeues stale tasks, counts active Gemma work, and tops up to at most 150 active Gemma tasks without Supabase paper-PDF storage -> 5 drain-only workers (parallel to the controller) each claim up to 20 Gemma tasks, then interleave up to 10 Flash-Lite triage drains (<=500/Pacific-day) and small Gemini-final drains from ranked candidates until 20 final calls complete that Pacific quota day`.
Gemma screening uses a capped head/tail paper excerpt by default so full-PDF prompts do not strand the worker. Gemini extraction remains uncapped unless `GEMINI_STAGE_TEXT_LIMIT_CHARS` or `AI_STAGE_TEXT_LIMIT_CHARS` is set.
GitHub Actions runs `.github/workflows/daily-ops.yml` every 5 minutes. Each invocation starts one serialized `refill-controller` job under the `daily-ops-refill-controller` concurrency group and a 5-job `drain-workers` matrix in parallel. Manual `workflow_dispatch` runs accept a `workers` input; inactive worker matrix entries skip checkout, setup, dependency install, and the drain step. The controller installs full crawler dependencies and keeps only a stable HuggingFace/model cache; workers install `services/data-pipeline/requirements-worker.txt` and do not restore run-id keyed data/model caches. The controller runs `daily_ops_orchestrator.py --controller-only --tick-mode`: it skips paper-storage cleanup/soft-limit checks, requeues stale Gemma/Flash-Lite/final-Gemini `processing` tasks, counts active Gemma work from `paper_stage_tasks.status IN ('queued', 'processing')` while excluding stale processing rows, and crawls/registers only `min(remaining_today, --screening-active-target 150) - active_count` English papers in chunks capped at 150. The controller reports a soft queued Flash-Lite/final-Gemini reservoir target of 500 candidates but does not evict tasks. Workers run `daily_ops_orchestrator.py --drain-only --tick-mode --interleave-extraction`; they never crawl, upload, or refill, and they drain only already-created model tasks. Task claiming remains DB-atomic, so overlapping scheduled worker matrices can safely process distinct rows. If Gemma source/refill is empty but queued downstream candidates and daily downstream quota remain, drain workers still process Flash-Lite and final Gemini slices instead of exiting early. Existing queued Gemma backlogs above the active target drain naturally without another 1500-paper crawl. The stage processor validates model runtime before claiming rows so missing API-key/config failures do not strand tasks in `processing`. Non-quota task errors past `AI_STAGE_MAX_TASK_ATTEMPTS=2` fail that task instead of retrying forever; quota/rate-limit errors still requeue without consuming meaningful attempts. Visible human queue stock does not stop daily AI draining.
Arciel is currently the only configured approver through `reviewer_profiles.can_approve_labels = true`; Peri, Aleyna, Aysegul, Daine, and the `f221229078@ktun.edu.tr` account are general-queue labelers unless their access flags change.
Each orchestrator run stops with a machine-readable `mode`, `day_start_utc`, per-stage `quota_day_starts` / `quota_timezones`, `daily_completed`, `stopped_reason`, per-stage summaries, `screened`, `routed_to_gemini`, `gemini_used`, `human_ready`, `quota_exhausted_stages`, and `remaining_queued`. Gemma defaults to UTC quota-day accounting; Gemini defaults to `America/Los_Angeles` to match provider RPD reset. AI processing still performs one final stock check if Gemini creates `human_review_ready` papers so the shared queue reflects new work immediately.
Controller command:
`OPENNUTRI_STORE_PDFS_IN_SUPABASE=0 python3 services/data-pipeline/scripts/daily_ops_orchestrator.py --json-summary --controller-only --tick-mode --stage-rpm gemma_proof_extraction_v1=20,gemini_flash_lite_triage_v1=20,gemini_flash_db_payload_v2=15 --max-wallclock-minutes 0 --screening-daily-target 1500 --screening-active-target 150 --triage-daily-target 500 --extraction-daily-target 20 --screening-refill-batch-en 150 --screening-refill-chunk-en 150 --screening-prefill-stall-limit 3 --paper-bucket-soft-limit-mb 0 --skip-storage-cleanup --refill-step-tr 0`.
Worker command:
`OPENNUTRI_STORE_PDFS_IN_SUPABASE=0 python3 services/data-pipeline/scripts/daily_ops_orchestrator.py --json-summary --drain-only --tick-mode --interleave-extraction --stage-rpm gemma_proof_extraction_v1=20,gemini_flash_lite_triage_v1=20,gemini_flash_db_payload_v2=15 --max-wallclock-minutes 0 --screening-daily-target 1500 --screening-tick-tasks 20 --triage-daily-target 500 --triage-tick-tasks 10 --extraction-daily-target 20 --extraction-tick-tasks 2 --refill-step-tr 0`.
The scheduled job runs on GitHub-hosted infrastructure, not on this laptop. It talks to Supabase Postgres/REST and Gemini using GitHub repository secrets; paper PDFs are fetched from source URLs instead of Supabase Storage.
Crawler v2 can split its query budget across independent English and Turkish workflows, with separate query phrases, anchors, weighted n-grams, concept-term ordering, and language-scoped embedding/metadata scoring. Current ops run English-only by default.
Accepted-paper targets can be set per language; for now default total targets are assigned entirely to English unless `--target-tr` is explicitly set.
Crawler v2 now also runs as `Search -> Filter -> Acquisition`:
- `Search`: metadata-only retrieval from Europe PMC, OpenAlex, and Semantic Scholar by default.
- `Search` uses source-specific query rendering; Turkish metadata search is intentionally simpler on OpenAlex / Semantic Scholar, while DergiPark now searches a locally refreshed journal/article index instead of the old global OAI slice.
- `Filter`: metadata-only relevance scoring using language-scoped lexical signals, source priors, embeddings, and learned feedback n-grams.
- `Acquisition`: PDF/full-text download plus PDF validation only after a candidate passes the metadata filter.
- Query execution is now batch-aware: each source/query task is treated as a bounded search batch, but the batch size is counted at the search-gate handoff, not on raw hits returned by the source. In practice `--query-limit` / `--search-batch-size` means “up to N unique papers that pass the initial search gate and move into deeper scoring,” while the crawler may scan a wider raw result pool underneath to fill that batch. Feedback scores those batches by later labeled yield, and the crawler stops only after finishing the current batch once a language reaches its target. Overshoot inside the final batch is allowed.
- Negative evidence is penalty-based; the active crawler no longer uses hard-negative veto terms that reject a paper immediately just because one negative phrase appears somewhere in the text.
- Crawler state now records terminal paper decisions as `accepted` or `rejected` with the stage where that outcome was reached, and future runs skip those recorded `paper_states` entries until state is reset. Crawler v2 also fetches live `papers.canonical_key` rows before search/acquisition so already queued, provisional-skipped, human-ready, or finalized papers are not downloaded again. Legacy `seen_ids` are no longer consulted for skip decisions, and metadata-only `paper_search_hits` rejects are not used as global skip memory.
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
- Automatic daily ops refreshes feedback terms only when it actually reaches the crawler/refill path. Pure queued-AI draining does not refresh feedback. Once crawler refill is needed, `ensure_paper_stock.run_refill_cycle` runs `update_terms.py` immediately before search unless `--skip-feedback` is explicitly passed. DergiPark refresh is skipped unless a Turkish deficit exists and DergiPark is explicitly included in `--sources`.
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
- `services/data-pipeline/scripts/upload_to_supabase.py`: Registers accepted paper metadata in Supabase, persists `papers.pdf_url`, updates `papers` by canonical identity, upserts metadata-stage discovery hits into `paper_search_hits` via deterministic `hit_key` values, and persists per-query batch history into `paper_search_batches` plus `paper_search_batch_hits`. By default it does not upload paper PDFs to Supabase Storage; set `OPENNUTRI_STORE_PDFS_IN_SUPABASE=1` only for legacy/temporary storage-backed runs. Re-uploading a paper that already has a closed AI route or human outcome now refreshes metadata/search-hit audit links without requeueing the active model stage. If concurrent workers race on the same canonical paper, duplicate-key insert errors are recovered by reusing the existing row, preserving search-hit audit links, and enqueueing the active stage only when the row is still open. Metadata-stage runs with zero accepted PDFs are valid as long as search hits exist, and hits keep `paper_id` nullable until a paper row exists. Oversized PDF handling still applies when legacy Storage upload is explicitly enabled. Pass `--data-dir` or `--manifest`; the script now requires `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
- `services/data-pipeline/scripts/process_stage_queue.py`: Claims queued model stage tasks in retry-fair order, preferring lower `attempt_count`, then higher `priority`, then older creation order. It requeues stale `processing` tasks before claiming new work, fetches source PDFs from `papers.pdf_url`, extracts text with `pdftotext`, fetches reference foods/nutrients, runs `UnifiedEvaluator` with the nutrient catalog and text-matched food candidates in prompt, standardizes candidate rows into the human-submission-shaped `normalized_payload_json`, stores routed `ai_extractions`, enqueues follow-up model stages for useful or raw-positive Gemma outputs, creates provisional skips for no-data outputs, and sends only useful Gemini outputs to human review. Supabase paper-PDF deletion only runs when legacy paper Storage is explicitly enabled. Unsupported-unit rows can raise Gemma screening priority but still cannot enter the final normalized payload. Retryable Gemma 31B model failures can use the configured 26B fallback in the same task attempt; retryable processing errors return the task and paper to `queued_for_ai` with a formatted `last_error`; quota/rate-limit requeues undo the claim attempt count so quota does not look like a paper failure; non-retryable model-configuration errors mark the task failed and stop automation with `ai_stage_configuration_error`.
- `services/data-pipeline/scripts/daily_ops_orchestrator.py`: Daily automation runner. Scheduled ops use `--controller-only` for the single writer/refill role and `--drain-only --interleave-extraction` for parallel model workers. The current scheduled controller skips paper-storage cleanup/soft-limit checks, requeues stale stage tasks for Gemma, Flash-Lite, and final Gemini, counts completed tasks from each configured quota-day start, counts active Gemma work from queued plus non-stale processing `paper_stage_tasks`, reports the soft downstream candidate reservoir, and tops up Gemma only to the configured active target. Drain workers never crawl/upload/refill; they drain bounded Gemma, Flash-Lite, and final Gemini slices from already-created tasks until the daily targets are reached. JSON output reports `mode`, `day_start_utc`, `quota_day_starts`, `quota_timezones`, `daily_completed`, `stopped_reason`, `interleaved_extraction_reason`, `interleaved_triage_reason`, per-stage summaries, screened/routed-to-triage/triage/routed-to-Gemini/Gemini/human-ready totals, exhausted stages, storage cleanup details when enabled, and remaining queued candidates.
- `services/data-pipeline/scripts/cleanup_paper_storage.py`: Legacy storage hygiene utility for opt-in paper Storage runs. Scheduled ops now skip it because paper PDFs are source-URL/on-demand by default.
- `services/data-pipeline/scripts/recover_gemini_candidates.py`: Dry-run-first recovery tool for historical Gemma output. It recomputes Gemini priorities from Gemma `ai_extractions.raw_data`, ranks raw-positive normalized-empty rows and optional clear composition-title Gemma failures, reports the current queued Gemini reservoir against the 500-candidate soft target, and only requeues or reprioritizes candidates when `--apply` is passed. Apply mode is capped at 200 selected candidates per run.
- `services/data-pipeline/scripts/flash_lite_triage_experiment.py`: Offline measurement harness for `gemini-3.1-flash-lite`. It samples known `gemini_flash_db_payload_v2` useful/no-data papers, runs Flash-Lite against the same extraction contract, and reports agreement, useful-paper recall, no-data false-positive rate, and the promotion gate. Flash-Lite is now production triage; use this script as a regression/quality check before changing the triage model, target, or prompt contract.
- `services/data-pipeline/scripts/backfill_ai_routing.py`: Enqueue and process the active AI stage for existing papers, then cancel unresolved legacy slot assignments only for papers that ended outside `human_review_ready`. The one-time `--reset-open-human-assignments` mode refuses to run if old assignment submissions, new general label submissions, or human-truth outcomes exist.
- `services/data-pipeline/scripts/ensure_paper_stock.py`: Refresh feedback terms, then crawl + upload until paper targets are met. Defaults are English-only: `--target` is assigned to English, `--target-tr` defaults to `0`, and `--sources` defaults to `europepmc,openalex,semanticscholar`. It counts only `papers.routing_status = 'human_review_ready'` papers with a latest normalized AI decision payload, no final outcome, and no pending/accepted general submission as available shared queue stock, and drains the AI queue after upload. DergiPark refresh/search only runs when a Turkish target is explicitly requested and DergiPark is included in `--sources`.
- `services/data-pipeline/scripts/refill_assignment_queue.py`: Protected ops job retained under the old filename for compatibility. It no longer creates slot/user assignments; it reports shared general queue stock from Gemini `has_data` papers only, drains queued Gemma/Gemini work before giving up, and triggers crawler refill when visible human-ready stock is below `--target-open`. Default target is 50 visible shared-queue papers.
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
- Full controller/crawler dependencies are listed in `services/data-pipeline/requirements.txt`.
- Lightweight drain-worker dependencies are listed in `services/data-pipeline/requirements-worker.txt`; this excludes `sentence-transformers` so model workers do not import or install the crawler embedding stack.
- `sentence-transformers` is required for L2 embedding scoring; crawler will error if missing.

**Environment Variables**
Frontend:
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`

Data pipeline and ETL:
- `SUPABASE_URL` (required for active crawler/upload/feedback write paths)
- `SUPABASE_SERVICE_ROLE_KEY` (required for write operations)
- `GEMINI_API_KEY` (required for LLM evaluator/extractor)
- `AI_MODEL_TASK_TIMEOUT_SECONDS` / `GEMINI_REQUEST_TIMEOUT_SECONDS` (optional AI worker timeout controls)
- `AI_STAGE_MAX_TASK_ATTEMPTS` (optional retry ceiling for non-quota task errors; scheduled ops sets `2`)
- `GEMMA_STAGE_TEXT_LIMIT_CHARS` (optional Gemma screening text cap; default and scheduled ops use `24000`)
- `GEMINI_STAGE_TEXT_LIMIT_CHARS` / `AI_STAGE_TEXT_LIMIT_CHARS` (optional extraction text caps; normally unset)
- `OPENNUTRI_STORE_PDFS_IN_SUPABASE` (optional legacy override; default `0`, and scheduled ops sets `0`; set `1` only when paper PDFs must be stored in Supabase Storage)
- `OPENNUTRI_SCREENING_QUOTA_TIMEZONE` (optional Gemma daily accounting reset timezone; default `UTC`)
- `OPENNUTRI_EXTRACTION_QUOTA_TIMEZONE` (optional Gemini daily accounting reset timezone; default `America/Los_Angeles`)
- `SUPABASE_RESOLVE_IP` (optional; IP pinning for SR legacy ETL)
- `DATABASE_URL` (required for `apps/expert-annotator/run-migration.js` and DB utility scripts such as `create_bucket.js`, `check_db.js`, and `test_pg.py`)
- `SIGNUP_EMAIL` / `SIGNUP_PASSWORD` (required only for `apps/expert-annotator/add_user.js`)

GitHub Actions daily ops requires repository secrets with these same names:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `GEMINI_API_KEY`

**Development Notes**
- The annotator app is deployed on Vercel.
- Supabase is used for auth and application data. Paper PDFs are not stored there by default; suggestion image attachments still use the private `suggestion-attachments` Storage bucket.
- Reviewer workflow is now general-queue plus approval:
  active labelers see the same available paper list; submitting creates an immutable `paper_label_submissions` row and removes the paper from the visible queue.
  Arciel currently has `can_approve_labels=true`; approval rights are configurable in reviewer admin.
  Arciel submissions auto-accept; other submissions go to Approval, where Arciel can edit and accept the final payload.
  `paper_label_approvals.correction_diff_json` records what changed between the labeler payload and accepted reviewer payload.
  `tester_access` keeps an account read-only and also grants cockpit-equivalent read visibility; `cockpit_access` remains the explicit non-tester cockpit-read flag.
  Legacy slot membership tables remain in the schema for old audit data but should not be used for new queue work.
- PDF highlighting is table-scoped and precision-first for nutrient-name click targets.
  The viewer builds a page-local allowlist from PDF.js text content and only highlights detected table body/header cells plus table caption/title lines. Narrative prose with nutrient words after a table is excluded from that allowlist, so isolated words in surrounding paragraphs should not become click marks.
  If a page has no confident local table anchor, or a table continues onto a captionless page, the viewer suppresses highlights on that page instead of falling back to page-wide prose matching.
  Nutrient-name highlight markup is still injected through `react-pdf` `customTextRenderer` on single PDF text items, so matches split across multiple items inside a table are still a separate follow-up.
- AI evidence highlighting is broad location guidance, not exact nutrient-coordinate matching.
  Queue and Approval build a compact deduplicated Sources strip from normalized payload rows. The scanner snaps matched evidence to whole detected table blocks or whole paragraph blocks, including tables whose `Table N` label is split from a long caption and wide multi-column header row. Paragraph matching ignores document chrome such as affiliations, article-history sidebars, keyword boxes, and copyright rows when building evidence blocks. The viewer scales those PDF-coordinate bounds onto the rendered page stage and draws every matched source overlay, clicked or not. Sources in the same resolved table or paragraph share one deduplicated overlay and one source chip; page-only hints scroll without coloring the whole page. Printed journal page hints such as `Page 95` are mapped to the actual PDF page when the viewer can detect header/footer page labels. Unmatched AI evidence remains visible as unverified.

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
Runtime credentials must come from environment variables or GitHub/Vercel/Supabase secret stores. Do not commit API keys, database URLs, Supabase service-role keys, personal access tokens, or test passwords. The legacy compatibility files and utility scripts fail fast when required credentials are missing from the environment.
