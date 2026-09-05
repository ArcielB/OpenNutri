# OpenNutri Agent Guide

Use this file to keep context narrow. Read this first, then open only the files relevant to the current task.

## Startup Order
1. Read `/home/arciel/#AgentFiles/INSTRUCTIONS.md` and `/home/arciel/#AgentFiles/AGENTS.md` when available, then read this repo's `INSTRUCTIONS.md`. `#AgentFiles` is the operator-level context source and must be checked at the start of every OpenNutri task.
2. **Always `git fetch` and check whether `origin/main` is ahead before doing anything else.** Other teammates push throughout the day. If `origin/main` is ahead and the working tree is clean, fast-forward (`git pull --ff-only`). If the working tree has uncommitted changes, surface the divergence to the user before merging — do not silently rebase or auto-merge. Reasoning before reading code, before writing the BACKLOG, before any "is this implemented yet" check must be done against the freshly fetched tip, not the local snapshot.
3. Check `git status --short` before editing so you do not disturb local run artifacts or user changes.
4. Read `/home/arciel/#AgentFiles/Keys and links` and repo-local `Keys and links` only if the task needs credentials, network calls, or database writes. Use the available `Keys and links` files as the source for GitHub auth when `git fetch`, `git pull`, or `git push` needs credentials. **Supabase: the repo-local file points at the OLD, DEAD project (`mlirsjgolmryywlfahuf`, abandoned in the 2026-05-30 migration — any data you read there is frozen at 2026-05-29). The live project is `uhytvufqimmzhviddseo`; use the `SUPABASE_*_NEW` values in the `#AgentFiles` file for anything Supabase.**
5. Read `README.md` or `docs/handoff_2026-03-20/STATE.md` only for the subsystem you are touching.
6. For reviewer-queue, approval, dashboard, or reviewer-truth tasks, read `docs/reviewer_workflow_map.md` before re-deriving the workflow from code.

## Active Surfaces
- `apps/expert-annotator/`: React 19 + Vite labeling UI.
- `services/data-pipeline/`: Python crawler, harvester, evaluator, ETL, and label-feedback loop.
- `services/core-api/`: Read-only FastAPI product API over versioned OpenNutri Core SQLite releases.
- `services/voice-api/`: Authenticated bounded voice/submitted-text resolver using
  the separate app Supabase project. Never point it at the dormant research project.
- `apps/expert-annotator/migration.sql`: current schema and RLS source of truth.
- `BACKLOG.md`: current task list.
- `docs/handoff_2026-03-20/STATE.md`: latest high-signal project state snapshot.

## Ignore By Default
Do not spend tokens on these unless the task explicitly needs them:
- `FoodData_Central_*`
- `legacy/`
- `apps/expert-annotator/dist/`
- `apps/expert-annotator/node_modules/`
- `services/data-pipeline/data/`
- `services/data-pipeline/food_paper_crawler/feedback/latest.json`
- `**/__pycache__/`
- `docs/proposal-sections/`

## Hot Files
- UI orchestration (data fetching, top bar, view routing): `apps/expert-annotator/src/pages/Annotate.jsx`
- Per-tab UI: `apps/expert-annotator/src/views/{QueueView,ApprovalView,DashboardView,AllPapersView,PipelineOpsView,SuggestionsReviewView,MySuggestionsView,ReviewerAdminView}.jsx`
- Shared annotator helpers (formatters, payload normalization, pipeline funnel, AI extraction stats): `apps/expert-annotator/src/utils/annotateHelpers.js`
- PDF highlight behavior: `apps/expert-annotator/src/components/PdfViewer.jsx`
- PDF text matching: `apps/expert-annotator/src/utils/PdfTextScanner.js`
- Suggestion flow: `apps/expert-annotator/src/components/SuggestionModal.jsx`
- Feedback term generation: `services/data-pipeline/food_paper_crawler/feedback/update_terms.py`
- Crawl/ranking logic: `services/data-pipeline/food_paper_crawler/`
- Auto-refill candidate papers: `services/data-pipeline/scripts/ensure_paper_stock.py`
- General queue stock job: `services/data-pipeline/scripts/refill_assignment_queue.py`

## Working Rules
- Reproduce bugs first when feasible.
- Edit source files, not generated artifacts.
- Prefer small, testable changes.
- Prefer durable fixes that update the underlying automation or workflow, not one-off cleanup. If an emergency manual mitigation is needed, follow it by changing the code, scheduled job, docs, or standing ops process so the same issue does not recur silently.
- Preserve existing user-visible behavior unless the task explicitly asks to change it. When touching the annotator workflow, check for previously documented affordances such as AI prefill, Details panels, approval visibility, tester read-only mode, and queue removal rules before replacing or simplifying UI.
- Commit every change you make once it is in a known working state.
- Push every working commit soon after it is validated; do not leave validated local-only commits sitting around or wait for a large batch.
- When a task changes the deployable annotator frontend under `apps/expert-annotator/`, deploy it to Vercel in the same task after the validated commit/push unless the user explicitly says not to, and report the production deployment state.
- Do not use hard-negative veto logic in crawler/ranking relevance decisions. Prefer additive scoring and soft penalties. If a true hard reject seems necessary, stop and discuss it first.
- When a task changes `apps/expert-annotator/migration.sql` or otherwise changes the live schema, apply that migration to the target database in the same task unless the user explicitly says not to or there is a concrete blocker. Do not stop at the file edit without calling out the DB state.
- After every meaningful codebase change, review the project documentation and update or rewrite anything that is now stale. Check `BACKLOG.md`, `README.md`, handoff/state notes, and any other affected docs in the same task.
- Update `BACKLOG.md` when backlog scope changes; delete completed items instead of leaving status notes.
- Update `README.md` when commands, architecture, or important behavior changes.
- When a research-protocol, reviewer-role, or benchmark-validity decision changes, write it to the latest handoff/state note in the same task instead of leaving it only in chat.
- Clearly document important implementation details for following agents in the same task. For code or ops behavior, update `README.md` plus the latest handoff/state note; for standing workflow expectations, update this `AGENTS.md`.
- Fail fast on missing dependencies; install them instead of adding fallback behavior.
- `sentence-transformers` is required for L2 embedding scoring.
- `feedback/latest.json` is generated local output; do not hand-edit it.
- The repo often contains local data dumps, caches, and untracked experiment output. Ignore unrelated noise.

## Product Truths
- The project is a food-composition paper pipeline plus a human labeling UI.
- `apps/nutrition-app/` is the Android-first consumer diary. Voice uses the isolated
  app Supabase project and `services/voice-api/`. The production primary is one-pass
  `gemini-3.8-flash` audio extraction with `thinkingLevel=low` in Vercel `iad1`;
  `gemini-3.1-flash-lite` is an uncertainty-marked retry for timeout, rate limit, transport,
  or invalid structured output. Flutter sends English/Turkish device locale hints.
  Preserve any safe transcript on failure, keep privacy-safe stage/error logging,
  and never collapse contract validation failures into a false provider-outage UI.
  After a fallback transcript, do not make a third provider call; return lexical
  candidates for review. Downstream matching-model failures must degrade to safe
  review instead of discarding the transcript. On Android, a voice batch whose
  every item has a usable selected Core food is logged optimistically; missing quantity/basis or an
  ambiguous match becomes a visibly marked editable estimate rather than a blocking
  confirmation step. Widget-launched capture closes back to the launcher only after
  the on-device save completes and shows a native result toast.
  The 1.1 personalization profile (goal, active diet, free-form diet notes, and
  explicit coach memories) remains on-device. Coach calls are stateless and send a
  compact snapshot transiently to Gemini 3.8 Flash only after a dedicated disclosure.
  Coaching may retry once with configured Gemini 3.5 Flash-Lite; preserve actual
  model attribution from transport metadata and show it in the app. Model fallback
  can be disabled with an empty OPENNUTRI_GEMINI_COACH_FALLBACK_MODEL. Keep quota
  errors as HTTP 429; never disguise them as provider connection failures.
  Daily advice is cached by local date. Text or bounded voice chat may propose memory
  updates only from explicit user statements; the app displays and can delete each
  memory. Oracle suggestions are plain English search queries and must pass through
  public Core search/detail before logging—AI must never supply nutrient truth or an
  unvalidated food ID. FDA adult Daily Values are labeled as broad references, not
  individualized medical targets.
  The current consumer behavior map is `docs/consumer_app.md`; validation and
  limitations are in `docs/consumer_app_audit_2026-09-05.md`. Keep backend
  `auto_log_eligible` uncertainty separate from Android's optimistic save policy.
  Never delete saved entries merely to open an editor. Widget completion must
  wait for local persistence, not optional feedback. Coach/Oracle calls share the
  client's serialized AI request lane; do not eagerly generate offscreen Oracle
  requests. Missing source nutrients are unknown, not zero intake. Do not describe
  the current Oracle as a mathematical optimizer or widget capture as a durable
  background queue. Before any physical-device tap, verify that the intended app
  is foreground and use a current screen state. Pause and ask if the person is
  using another app; never keep tapping stale coordinates. Restore temporary
  device settings and remove isolated test installs after testing.
  Run device automation with `-PauditBuild=true` so synthetic
  data and consent do not enter the person's installed diary.
  Widget registration and intent tests do not prove launcher placement. Pinning
  requires the person's confirmation; never claim it was added from the native
  request's Boolean result alone.
- The consumer food-data surface is separate from the annotator schema. The current
  combined USDA Core release is built under `services/data-pipeline/opennutri_core/` and served
  read-only by `services/core-api/`; do not route it through legacy `claims` or expose
  the SQLite table layout as the HTTP contract. Core `v0.3.0` source aliases remain
  provenance-preserving and separately indexed; API `v0.4.0` exposes only optional
  matched-term metadata.
- USDA Core nutrients remain per 100 g edible portion. As-purchased logging may use
  only a usable, food-linked `edible_portion_factors` row. Do not infer a factor from
  a merely similar food or apply a conflict row. Preserve source refuse values and
  reviewed correction provenance when changing factor rules.
- The extraction target is useful OpenNutri food composition data only: real foods or food products mapped to nutrient/composition values for nutrition datasets, diet tracking, food exporters, inspection, or similar real-world use. Papers about effects of a nutrient, supplement, extract, dose, or diet on health, biomarkers, cells, animals, microbes, processing outcomes, or other responses are empty unless they also report direct food/product composition tables useful to OpenNutri. One-off experimental treatment/formulation variants are no usable data unless they represent a stable real-world food/product worth adding to the DB.
- Relevance filtering code supports English and Turkish, but current ops are English-only. Default refill/daily crawler runs request `tr=0`, skip DergiPark, and use Europe PMC/OpenAlex/Semantic Scholar unless Turkish is explicitly re-enabled.
- The annotator now uses a general queue:
  every active labeler sees the same available `human_review_ready` papers, and a paper disappears from the queue as soon as a general label submission exists.
- Only papers successfully processed by the model cascade with normalized `has_data` payloads should enter the human labeling queue. AI `no_usable_data` decisions are provisional skips by default and should not appear in the default labeler queue or cockpit paper overview.
- General queue drafts are not claims. Multiple stale in-progress reviewers can still submit before final approval, and every immutable submission is retained in `paper_label_submissions`.
- Final human truth is reviewer-led approval:
  Arciel currently has `reviewer_profiles.can_approve_labels = true`; approval rights are configurable and separate from tester/cockpit visibility.
- Arciel's own submissions auto-accept into `paper_label_approvals` and `paper_review_outcomes`; non-Arciel submissions remain `pending_approval` until Arciel edits/approves them.
- The approval page is visible to cockpit/tester/developer accounts but mutation RPCs require `current_user_can_approve_labels()`, which excludes testers.
- `allowed_auth_emails` is a private signup allowlist. Keep RLS enabled and direct client-role table privileges revoked; signup access should continue through the security-definer auth hook, not frontend reads/writes.
- Labeler performance and correction details come from `paper_label_submissions`, `paper_label_approvals.correction_diff_json`, and `paper_review_outcomes`.
- Labeling queue papers with no saved annotation must open with the latest Gemini `has_data` `normalized_payload_json` prefilled as editable food/nutrient rows. Labelers review and correct the DB-compliant AI extraction; the queue must not show AI reasoning.
- Labeling queue AI prefill should stay quiet in the UI: rows load directly into the editor without a separate AI-prefill status banner.
- Queue and Approval source strips are broad navigation hints built from normalized payload evidence metadata. Matched evidence snaps to whole detected table blocks or whole paragraph blocks, and every matched block renders as an always-on coordinate overlay; sources in the same resolved table or paragraph share one deduplicated overlay and one source chip. Page-only hints scroll without coloring the page, and unmatched hints remain visible as unverified. PDF navigation resolves AI `page_hint` values against detected printed page numbers from PDF headers/footers before falling back to PDF page indexes. The AI `page_hint` is unreliable as a PDF page index — the model only sees extracted full text, so for journal/offprint PDFs it reports the printed/volume page number (e.g. 1217 on a 5-page file). When a `page_hint` exceeds the PDF's page count it cannot be a page index, so highlighting treats it as non-gating: the table-caption and source-quote fallbacks are allowed to locate the evidence by text on any page instead of staying locked to a page that does not exist. This is a no-op when `page_hint <= numPages`. Highlight presence must stay content-driven (table caption number + source-quote text), with `page_hint` only a navigation tiebreaker.
- Avoid emoji-dependent controls in the annotator UI; use stable text labels or accessible icon-only buttons instead.
- Cockpit Useful Papers must keep a per-paper AI Details affordance for the latest useful AI extraction. Details should show the normalized DB-compliant payload and row/normalization summary, not the model reasoning. Provisional no-data skips stay out of this default overview.
- Cockpit AI extraction lists must use `get_cockpit_ai_extractions` or an equally slim projection. Do not change them back to `ai_extractions.select('*')`: raw model responses and reasoning are large, unnecessary for the default UI, and can burn Supabase egress quickly. Fetch full raw AI rows only for a deliberately scoped debug/admin action.
- Cockpit Pipeline must use `get_pipeline_ops_snapshot` for crawler-to-human operational visibility. It should stay presentation-first: current stage queues plus a simple all-time-by-default funnel with time filtering. Model-stage UI labels must keep stable role names (`Small model`, `Medium model`, `Strong model`) and show only the current model spec in parentheses, for example `Small model (Gemma 31B)`, so future model swaps change the spec but not the role name. Funnel counters must be role/stage counters, not model-name counters; historical direct Small -> Strong tasks from before Medium existed are backfilled into Medium entered/kept via `model_stage_backfill.legacy_direct_strong_without_medium`. Keep deeper trace/error debugging out of that main screen unless explicitly requested.
- Old slot tables (`reviewer_slots`, `reviewer_slot_members`, `paper_slot_assignments`, `paper_user_assignments`, `paper_assignment_submissions`, `paper_conflicts`) are preserved as legacy audit/history only and should not drive new workflow work.
- Resolved crawler truth now comes from `paper_review_outcomes`; pending/superseded submissions must not feed feedback learning.
- Exact raw-match comparison uses deterministic payload snapshots stored in `paper_label_submissions` and accepted reviewer payloads in `paper_label_approvals`.
- UI test mode disables DB writes and stores actions locally.
- Legacy global no-data still exists in the schema for old data, but the active workflow is general queue + reviewer approval.

## Research Ops Notes
- **Research automation is paused as of 2026-07-21.** GitHub workflow states for
  `Daily OpenNutri Ops` and `Supabase Watchdog` are `disabled_manually`, and both
  workflow files are manual-only with no cron trigger. Do not re-enable, dispatch,
  or restore a schedule without an explicit user decision to resume paper work.
- The remaining Research Ops bullets document the dormant implementation for a
  future reviewed restart; descriptions of scheduled behavior are not current
  operations. Current product work is the FNDDS Core API, search benchmark,
  deployment, and app vertical slice.
- Queue strategy: keep paper stock low on purpose and refill as labeling proceeds so each crawl benefits from newer feedback.
- Automated daily ops runs a 3-stage cascade. `gemma_proof_extraction_v1` (`gemma-4-31b-it`, with `gemma-4-26b-a4b-it` as the same-stage fallback for retryable 31B failures) screens and ranks up to 1500 papers/day → `gemini_flash_lite_triage_v1` (`gemini-3.1-flash-lite`, up to 500/day) re-ranks the top Gemma candidates → `gemini_flash_db_payload_v2` (`gemini-3.5-flash`, safety ceiling 250/day) is the final extraction. Daily targets are provider safety ceilings, not expected throughput. Each `ai_model` stage runs the `UnifiedEvaluator` contract, ranks via `score_followup_priority`, and routes its `has_data` papers to `next_stage_on_has_data`; priority-ordered claiming makes each stage process the strongest available candidates. Raw-positive normalized-empty Gemma rows can also advance when Gemma returned candidate rows or a clear `has_data` decision. Unsupported-unit rows can raise screening priority but must not enter final normalized Gemini/human payloads. Any-stage `no_usable_data` outputs become provisional skips. Daily ops is a resumable tick system keyed to stage-specific quota-day completion counts: Gemma defaults to UTC reset; both Gemini-family stages (triage + final) default to `America/Los_Angeles` reset. If Gemma source/refill is empty while Gemini still has queued candidates and remaining daily quota, the tick still drains Gemini instead of exiting early. Existing large Gemma backlogs should drain naturally instead of triggering a new 1500-paper crawl.
- Daily ops requests a run every 5 minutes through `.github/workflows/daily-ops.yml`, but GitHub may delay scheduled workflows under load. Each scheduled invocation runs one serialized `refill-controller` job under the `daily-ops-refill-controller` concurrency group, alongside a 5-worker drain matrix that starts in parallel and is no longer gated on the controller (the queue always carries backlog, and draining must continue even if the controller job fails). Manual dispatches accept a `workers` input for smaller controlled bursts; inactive worker entries skip checkout/setup/dependency work before the final drain step. The controller is the only scheduled path that may crawl/upload/refill. It installs full crawler requirements and keeps only a stable HuggingFace/model cache. It runs unbuffered `daily_ops_orchestrator.py --controller-only --tick-mode` with `OPENNUTRI_STORE_PDFS_IN_SUPABASE=0`, `--stage-rpm gemma_proof_extraction_v1=20,gemini_flash_lite_triage_v1=20,gemini_flash_db_payload_v2=15`, `--max-wallclock-minutes 75`, `--crawler-max-wallclock-seconds 2400`, `--screening-daily-target 1500`, `--screening-active-target 150`, `--screening-failure-window-hours 6`, `--screening-failure-circuit-min-failures 20`, `--triage-daily-target 500`, `--extraction-daily-target 250`, `--screening-refill-batch-en 30`, `--screening-refill-chunk-en 30`, `--paper-bucket-soft-limit-mb 0`, `--skip-storage-cleanup`, and `--refill-step-tr 0`. The failure circuit prevents crawler/R2 growth when recent Gemma work is systemically failing with zero completions. Crawler v2 writes partial accepted results when the crawler wall-clock limit is reached, so the controller should upload partial progress instead of being killed by the GitHub job timeout. The controller requeues stale `processing` tasks for Gemma, Flash-Lite, and final Gemini. Workers install `requirements-worker.txt`, receive R2 credentials for authenticated PDF reads, do not restore run-id keyed data/model caches, and run unbuffered `daily_ops_orchestrator.py --drain-only --tick-mode --interleave-extraction` with `OPENNUTRI_STORE_PDFS_IN_SUPABASE=0`, `--screening-tick-tasks 20`, `--triage-tick-tasks 10`, and `--extraction-tick-tasks 5`; workers must never crawl, upload, or refill. Overlapping worker matrices are allowed because `claim_paper_stage_tasks` atomically claims distinct tasks. Keep this controller-plus-drain-workers model unless the ops strategy is explicitly changed.
- Scheduled ops sets `GEMMA_STAGE_TEXT_LIMIT_CHARS=24000`, `AI_MODEL_TASK_TIMEOUT_SECONDS=300`, `AI_STAGE_MAX_TASK_ATTEMPTS=2`, and `GEMINI_REQUEST_TIMEOUT_SECONDS=300`. Gemma should receive a capped head/tail excerpt small enough to avoid repeated 300-second Gemma timeouts; Gemini extraction remains uncapped unless a Gemini-specific cap is set. The 300-second model timeout is intentional so one slow paper cannot consume a large fraction of the GitHub Actions job cap. `process_stage_queue.py` validates model runtime before claiming rows and requeues stale `processing` tasks before queue decisions so missing credentials or cancelled runners do not strand papers; non-quota task errors past the retry ceiling fail the task instead of retrying forever. Quota/rate-limit errors still requeue without consuming meaningful attempts.
- Paper PDFs are R2/on-demand by default. `papers.pdf_url` is the durable R2 location for model workers and the annotator, while `papers.source_pdf_url` preserves the publisher fallback. Workers use authenticated S3-compatible R2 reads rather than depending on public `r2.dev` reachability. `upload_to_supabase.py` does not upload paper PDFs to Supabase Storage unless `OPENNUTRI_STORE_PDFS_IN_SUPABASE=1` is explicitly set. Scheduled ops set that flag to `0`, skip paper-storage cleanup, and set the paper-bucket soft limit to `0`; do not re-enable paper Storage without discussing the free-tier storage/egress impact. Suggestion attachments still use the private `suggestion-attachments` bucket.
- Daily ops only refreshes feedback terms when it reaches the crawler/refill path. Existing `human_review_ready` general queue stock and queued-AI draining do not refresh feedback; `ensure_paper_stock.run_refill_cycle` refreshes terms immediately before search unless `--skip-feedback` is explicitly passed. DergiPark refresh/search is disabled by default and only runs when a Turkish deficit and DergiPark source are explicitly requested.
- Uploading an already-known paper refreshes metadata/search-hit audit rows but must preserve any closed AI route or human outcome; do not requeue `human_review_ready`, provisional-skip, or finalized papers into the currently active model stage just because the active model changed. Concurrent uploader duplicate-key races on `papers.canonical_key` should recover by reusing the existing row and preserving search-hit audit links instead of failing the whole refill slice.
- AI stage task claiming is retry-fair: queued tasks sort by lower `attempt_count`, then higher `priority`, then older creation order. Daily ops must requeue stale `processing` tasks before deciding whether to crawl, and queue/refill counts must come from executable queued `paper_stage_tasks` rows rather than paper routing summaries alone, because stale historical `queued_for_ai` rows can otherwise block refill while no task can be claimed. Quota/rate-limit requeues must undo the claim attempt count so quota does not make a paper look retry-failing. Do not change this back to pure oldest-first, because one repeatedly failing paper can otherwise monopolize automation.
- Gemma 31B retryable model failures can fall back once to configured 26B in the same task attempt. Non-retryable primary model configuration errors should surface as `ai_stage_configuration_error` / permanent model errors instead of silently looping through the queue.
- Crawler batch acquisition must respect remaining per-language targets. A single search batch should not download far beyond the requested English refill size. Before metadata acquisition, crawler v2 merges local terminal crawl state with live `papers.canonical_key` rows from Supabase so already queued, skipped, human-ready, or finalized papers are not downloaded again; do not broaden this to metadata-only `paper_search_hits` rejects without discussing the benchmark/audit implications.
- `UnifiedEvaluator` is the shared prompt/contract for Gemma, Gemini, and future model stages. It intentionally accepts the requested JSON object, a top-level array of candidate rows, a single result object wrapped in a top-level array, or nested `food -> nutrients[]` rows; keep these parser variants so shape drift does not become an infinite AI retry loop.
- `UnifiedEvaluator` should receive the full nutrient catalog plus high-signal text-matched food candidates in prompt, but not the full food catalog. Deterministic normalization verifies AI-provided food/nutrient IDs against DB rows, then falls back to exact/alias matching and custom rows. Per-row source evidence (`source_citation`, `table_label`, `page_hint`, `source_quote`, `source_location_type`, `section_heading`, `paragraph_hint`) should be preserved in normalized payload metadata for PDF evidence highlighting.
- Model input mode is per-stage via `routing_stage_configs.model_input_mode` (`text` | `pdf`). PDF-capable stages (the Gemini stages) receive the native PDF document part (inline under ~15MB, else Files API) so the model reads pages/tables/scans directly and reports the true 1-based PDF page index; native PDF gives the model both rendered pages and the auto-extracted embedded text, and embedded text is not billed. Text-mode stages (Gemma screening) receive pdftotext output. Both modes get `===== PDF PAGE N =====` markers injected at pdftotext form-feed boundaries (before head/tail truncation, so surviving pages keep correct numbers) so the model can report the PDF page index instead of the printed/journal page. `page_hint` is the 1-based PDF page index, NEVER the printed journal page. `source_quote` must be a short contiguous verbatim excerpt (no ellipsis joining distant fragments) because it is matched against the PDF text to place the highlight. The shared extraction prompt is `opennutri_evidence_payload_v2`. Before flipping a stage to `pdf`, confirm the model accepts file parts with `scripts/probe_model_file_input.py` (needs `GEMINI_API_KEY`). Gemma accepts PDF parts in the probe but was measured to TIME OUT (>600s on a 5-page PDF, both `gemma-4-31b-it` and `gemma-4-26b-a4b-it`), so Gemma screening MUST stay `text` — it is too slow per call for the ~1500/day stage, and the page markers already give it correct PDF page numbers without images. Do not re-flip Gemma to `pdf`. Scanned/image-only PDFs (empty pdftotext) still fail at the text-mode Gemma screening gate — routing those to a PDF/image-capable stage is a separate follow-up.
- Historical recovery should use `services/data-pipeline/scripts/recover_gemini_candidates.py` dry-run first. Apply mode is capped at 200 selected candidates and should only requeue or reprioritize high-priority Gemini candidates; do not evict existing Gemini tasks without a reviewed dry-run report.
- `gemini-3.1-flash-lite` is now the production middle triage stage, not experiment-only. Keep `services/data-pipeline/scripts/flash_lite_triage_experiment.py` as a regression/quality gate before changing the triage model, target, or prompt contract.
- Team operating model:
  - Arciel: developer, configured approver, final reviewer, dashboard reviewer.
  - Peri, Aleyna, Aysegul, Daine, and the `f221229078@ktun.edu.tr` account: general-queue labelers unless access flags are changed.

## Common Commands
- Core API run: `cd services/core-api && python3 -m uvicorn opennutri_api.main:app --reload`
- Core API tests: `cd services/core-api && python3 -m unittest discover -s tests -p 'test_*.py' -v`
- Frontend install/run: `cd apps/expert-annotator && npm install && npm run dev`
- Frontend validation: `cd apps/expert-annotator && npm run build`
- Frontend lint: `cd apps/expert-annotator && npm run lint`
- Apply schema migration: `cd apps/expert-annotator && DATABASE_URL=... node run-migration.js`
- Verify reviewer workflow schema: `cd apps/expert-annotator && DATABASE_URL=... node check-workflow-schema.mjs`
- After changing schema, verify the new columns/indexes or behavior against the live database before closing the task.
- Refresh label-feedback terms: `python3 services/data-pipeline/food_paper_crawler/feedback/update_terms.py`
- Refill low paper stock: `python3 services/data-pipeline/scripts/ensure_paper_stock.py --threshold 0`
- Run one daily ops controller locally: `OPENNUTRI_STORE_PDFS_IN_SUPABASE=0 python3 services/data-pipeline/scripts/daily_ops_orchestrator.py --json-summary --controller-only --tick-mode --stage-rpm gemma_proof_extraction_v1=20,gemini_flash_lite_triage_v1=20,gemini_flash_db_payload_v2=15 --max-wallclock-minutes 75 --crawler-max-wallclock-seconds 2400 --screening-daily-target 1500 --screening-active-target 150 --screening-failure-window-hours 6 --screening-failure-circuit-min-failures 20 --triage-daily-target 500 --extraction-daily-target 250 --screening-refill-batch-en 30 --screening-refill-chunk-en 30 --screening-prefill-stall-limit 3 --paper-bucket-soft-limit-mb 0 --skip-storage-cleanup --refill-step-tr 0`
- Run one daily ops drain worker locally: `OPENNUTRI_STORE_PDFS_IN_SUPABASE=0 python3 services/data-pipeline/scripts/daily_ops_orchestrator.py --json-summary --drain-only --tick-mode --interleave-extraction --stage-rpm gemma_proof_extraction_v1=20,gemini_flash_lite_triage_v1=20,gemini_flash_db_payload_v2=15 --max-wallclock-minutes 0 --screening-daily-target 1500 --screening-tick-tasks 20 --triage-daily-target 500 --triage-tick-tasks 10 --extraction-daily-target 250 --extraction-tick-tasks 5 --refill-step-tr 0`
- Dry-run historical Gemini candidate recovery: `python3 services/data-pipeline/scripts/recover_gemini_candidates.py --json-summary --limit 200`
- Run Flash-Lite holdout listing without model calls: `python3 services/data-pipeline/scripts/flash_lite_triage_experiment.py --dry-run --json-summary`

## Secrets
- `/home/arciel/#AgentFiles/Keys and links` and repo-local `Keys and links` are the local sources for GitHub, Supabase, and database credentials.
- For Supabase database access, prefer the shared/session pooler connection from the available `Keys and links` files on IPv4 networks; use the direct connection on IPv6-capable networks if the pooler path is unavailable.
- For GitHub network operations, use the GitHub token from the available `Keys and links` files through a non-interactive auth path such as `GIT_ASKPASS`; do not rely on memory or interactive prompts.
- Runtime credentials must come from environment variables or local secret stores. Do not reintroduce hardcoded API keys, database URLs, Supabase service-role keys, personal access tokens, or test passwords in tracked files.
- If a secret is exposed in git history or a public repository alert, treat it as compromised: remove current tracked occurrences, rotate/revoke the secret at the provider, and discuss history rewriting/force-push before attempting it.
- Never copy secret values into `AGENTS.md`, `README.md`, commits, tickets, or model responses.
- Refer to secrets by env var name only, for example `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, `GEMINI_API_KEY`.

## Task Routing
- Consumer food API/search work: start in `services/core-api/` and `docs/opennutri_core_fndds.md`
- Annotation workflow bugs (queue/approval/cockpit data fetch + routing): start in `apps/expert-annotator/src/pages/Annotate.jsx`
- Bugs scoped to one tab: start in the matching `apps/expert-annotator/src/views/*.jsx`
- Helper or formatting bugs: start in `apps/expert-annotator/src/utils/annotateHelpers.js`
- PDF highlight bugs: start in `apps/expert-annotator/src/components/PdfViewer.jsx` and `apps/expert-annotator/src/utils/PdfTextScanner.js`
- Suggestion queue work: start in `apps/expert-annotator/src/components/SuggestionModal.jsx` and the related Supabase tables
- Feedback/L2 term work: start in `services/data-pipeline/food_paper_crawler/feedback/update_terms.py`
- Ranking/classifier/crawler work: start in `services/data-pipeline/food_paper_crawler/`
- Schema or policy changes: start in `apps/expert-annotator/migration.sql`

## Current Priorities
- Prevent empty food items and label-count mismatches.
- Operate and refine the general queue + Arciel approval workflow around high-precision useful-paper discovery.
- Train and integrate the L2 classifier once label volume supports it.
- Route user suggestions into a review queue, then support attachments.
- Fix PDF nutrient highlighting reliability.
