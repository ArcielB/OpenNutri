# OpenNutri Agent Guide

Use this file to keep context narrow. Read this first, then open only the files relevant to the current task.

## Startup Order
1. Read `/home/arciel/#AgentFiles/INSTRUCTIONS.md` and `/home/arciel/#AgentFiles/AGENTS.md` when available, then read this repo's `INSTRUCTIONS.md`. `#AgentFiles` is the operator-level context source and must be checked at the start of every OpenNutri task.
2. **Always `git fetch` and check whether `origin/main` is ahead before doing anything else.** Other teammates push throughout the day. If `origin/main` is ahead and the working tree is clean, fast-forward (`git pull --ff-only`). If the working tree has uncommitted changes, surface the divergence to the user before merging — do not silently rebase or auto-merge. Reasoning before reading code, before writing the BACKLOG, before any "is this implemented yet" check must be done against the freshly fetched tip, not the local snapshot.
3. Check `git status --short` before editing so you do not disturb local run artifacts or user changes.
4. Read `/home/arciel/#AgentFiles/Keys and links` and repo-local `Keys and links` only if the task needs credentials, network calls, or database writes. Use the available `Keys and links` files as the source for GitHub auth when `git fetch`, `git pull`, or `git push` needs credentials.
5. Read `README.md` or `docs/handoff_2026-03-20/STATE.md` only for the subsystem you are touching.
6. For reviewer-queue, approval, dashboard, or reviewer-truth tasks, read `docs/reviewer_workflow_map.md` before re-deriving the workflow from code.

## Active Surfaces
- `apps/expert-annotator/`: React 19 + Vite labeling UI.
- `services/data-pipeline/`: Python crawler, harvester, evaluator, ETL, and label-feedback loop.
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
- Queue and Approval source strips are broad navigation hints built from normalized payload evidence metadata. Matched evidence snaps to whole detected table blocks or whole paragraph blocks, and every matched block renders as an always-on coordinate overlay; sources in the same resolved table or paragraph share one deduplicated overlay and one source chip. Page-only hints scroll without coloring the page, and unmatched hints remain visible as unverified. PDF navigation resolves AI `page_hint` values against detected printed page numbers from PDF headers/footers before falling back to PDF page indexes.
- Avoid emoji-dependent controls in the annotator UI; use stable text labels or accessible icon-only buttons instead.
- Cockpit Useful Papers must keep a per-paper AI Details affordance for the latest useful AI extraction. Details should show the normalized DB-compliant payload and row/normalization summary, not the model reasoning. Provisional no-data skips stay out of this default overview.
- Cockpit Pipeline must use `get_pipeline_ops_snapshot` for crawler-to-human operational visibility. It should stay presentation-first: current stage queues plus a simple all-time-by-default funnel with time filtering. Keep deeper trace/error debugging out of that main screen unless explicitly requested.
- Old slot tables (`reviewer_slots`, `reviewer_slot_members`, `paper_slot_assignments`, `paper_user_assignments`, `paper_assignment_submissions`, `paper_conflicts`) are preserved as legacy audit/history only and should not drive new workflow work.
- Resolved crawler truth now comes from `paper_review_outcomes`; pending/superseded submissions must not feed feedback learning.
- Exact raw-match comparison uses deterministic payload snapshots stored in `paper_label_submissions` and accepted reviewer payloads in `paper_label_approvals`.
- UI test mode disables DB writes and stores actions locally.
- Legacy global no-data still exists in the schema for old data, but the active workflow is general queue + reviewer approval.

## Research Ops Notes
- Current top-level goal: Preliminary Study 3 is skipped. Near-term pipeline work should optimize for quickly surfacing useful direct food-composition papers, even if that means accepting lower recall and revisiting skipped candidates in a later pass.
- Queue strategy: keep paper stock low on purpose and refill as labeling proceeds so each crawl benefits from newer feedback.
- Automated daily ops uses `gemma_proof_extraction_v1` with `gemma-4-31b-it` before Gemini, with `gemma-4-26b-a4b-it` configured as the same-stage fallback for retryable 31B model failures. The final extraction stage key remains `gemini_flash_db_payload_v2` and uses stable `gemini-3.5-flash`. Gemma `has_data` outputs enqueue Gemini by priority; raw-positive normalized-empty Gemma rows can also enqueue Gemini when Gemma returned candidate rows or a clear `has_data` decision. Unsupported-unit rows can raise screening priority but must not enter final normalized Gemini/human payloads. Gemma/Gemini `no_usable_data` outputs become provisional skips. Daily ops is a resumable tick system keyed to stage-specific quota-day completion counts: Gemma defaults to UTC reset, Gemini defaults to `America/Los_Angeles` reset. If Gemma source/refill is empty while Gemini still has queued candidates and remaining daily quota, the tick still drains Gemini instead of exiting early. Existing large Gemma backlogs should drain naturally instead of triggering a new 1500-paper crawl.
- Daily ops is scheduled every 5 minutes by `.github/workflows/daily-ops.yml`. Each scheduled invocation runs one serialized `refill-controller` job under the `daily-ops-refill-controller` concurrency group, then a 5-worker drain matrix. Manual dispatches accept a `workers` input for smaller controlled bursts; inactive worker entries skip checkout/setup/dependency work before the final drain step. The controller is the only scheduled path that may crawl/upload/refill. It installs full crawler requirements and keeps only a stable HuggingFace/model cache. It runs unbuffered `daily_ops_orchestrator.py --controller-only --tick-mode` with `--stage-rpm gemma_proof_extraction_v1=20,gemini_flash_db_payload_v2=15`, `--screening-daily-target 1500`, `--screening-active-target 150`, `--screening-refill-batch-en 150`, `--screening-refill-chunk-en 150`, `--paper-bucket-soft-limit-mb 900`, and `--refill-step-tr 0`. Workers install `requirements-worker.txt`, do not restore run-id keyed data/model caches, and run unbuffered `daily_ops_orchestrator.py --drain-only --tick-mode --interleave-extraction` with `--screening-tick-tasks 20` and `--extraction-tick-tasks 2`; workers must never crawl, upload, or refill. Overlapping worker matrices are allowed because `claim_paper_stage_tasks` atomically claims distinct tasks. Keep this controller-plus-drain-workers model unless the ops strategy is explicitly changed.
- Scheduled ops sets `GEMMA_STAGE_TEXT_LIMIT_CHARS=24000`, `AI_MODEL_TASK_TIMEOUT_SECONDS=300`, `AI_STAGE_MAX_TASK_ATTEMPTS=2`, and `GEMINI_REQUEST_TIMEOUT_SECONDS=300`. Gemma should receive a capped head/tail excerpt small enough to avoid repeated 300-second Gemma timeouts; Gemini extraction remains uncapped unless a Gemini-specific cap is set. The 300-second model timeout is intentional so one slow paper cannot consume a large fraction of the GitHub Actions job cap. `process_stage_queue.py` validates model runtime before claiming rows and requeues stale `processing` tasks before queue decisions so missing credentials or cancelled runners do not strand papers; non-quota task errors past the retry ceiling fail the task instead of retrying forever. Quota/rate-limit errors still requeue without consuming meaningful attempts.
- Scheduled ops storage hygiene runs inside the serialized controller. It deletes orphan `papers` bucket objects and PDFs for failed/provisional/final no-data AI routes, while preserving queued Gemini/model-processing and `human_review_ready` PDFs that are still needed for extraction or labeling. The controller skips new refill if the paper bucket remains above the default 900 MB soft limit after cleanup; this must not block workers from draining existing tasks.
- Daily ops only refreshes feedback terms when it reaches the crawler/refill path. Existing `human_review_ready` general queue stock and queued-AI draining do not refresh feedback; `ensure_paper_stock.run_refill_cycle` refreshes terms immediately before search unless `--skip-feedback` is explicitly passed. DergiPark refresh/search is disabled by default and only runs when a Turkish deficit and DergiPark source are explicitly requested.
- Uploading an already-known paper refreshes metadata/search-hit audit rows but must preserve any closed AI route or human outcome; do not requeue `human_review_ready`, provisional-skip, or finalized papers into the currently active model stage just because the active model changed. Concurrent uploader duplicate-key races on `papers.canonical_key` should recover by reusing the existing row and preserving search-hit audit links instead of failing the whole refill slice.
- AI stage task claiming is retry-fair: queued tasks sort by lower `attempt_count`, then higher `priority`, then older creation order. Daily ops must requeue stale `processing` tasks before deciding whether to crawl, and queue/refill counts must come from executable queued `paper_stage_tasks` rows rather than paper routing summaries alone, because stale historical `queued_for_ai` rows can otherwise block refill while no task can be claimed. Quota/rate-limit requeues must undo the claim attempt count so quota does not make a paper look retry-failing. Do not change this back to pure oldest-first, because one repeatedly failing paper can otherwise monopolize automation.
- Gemma 31B retryable model failures can fall back once to configured 26B in the same task attempt. Non-retryable primary model configuration errors should surface as `ai_stage_configuration_error` / permanent model errors instead of silently looping through the queue.
- Crawler batch acquisition must respect remaining per-language targets. A single search batch should not download far beyond the requested English refill size. Before metadata acquisition, crawler v2 merges local terminal crawl state with live `papers.canonical_key` rows from Supabase so already queued, skipped, human-ready, or finalized papers are not downloaded again; do not broaden this to metadata-only `paper_search_hits` rejects without discussing the benchmark/audit implications.
- `UnifiedEvaluator` is the shared prompt/contract for Gemma, Gemini, and future model stages. It intentionally accepts the requested JSON object, a top-level array of candidate rows, a single result object wrapped in a top-level array, or nested `food -> nutrients[]` rows; keep these parser variants so shape drift does not become an infinite AI retry loop.
- `UnifiedEvaluator` should receive the full nutrient catalog plus high-signal text-matched food candidates in prompt, but not the full food catalog. Deterministic normalization verifies AI-provided food/nutrient IDs against DB rows, then falls back to exact/alias matching and custom rows. Per-row source evidence (`source_citation`, `table_label`, `page_hint`, `source_quote`, `source_location_type`, `section_heading`, `paragraph_hint`) should be preserved in normalized payload metadata for PDF evidence highlighting.
- Historical recovery should use `services/data-pipeline/scripts/recover_gemini_candidates.py` dry-run first. Apply mode is capped at 200 selected candidates and should only requeue or reprioritize high-priority Gemini candidates; do not evict existing Gemini tasks without a reviewed dry-run report.
- `gemini-3.1-flash-lite` is experiment-only. Use `services/data-pipeline/scripts/flash_lite_triage_experiment.py` on a holdout set and promote only if separate quota is verified, useful-paper recall is at least 85%, known-no-data false positives are at most 25%, and it does not reduce the final `gemini-3.5-flash` daily budget.
- Team operating model:
  - Arciel: developer, configured approver, final reviewer, dashboard reviewer.
  - Peri, Aleyna, Aysegul, Daine, and the `f221229078@ktun.edu.tr` account: general-queue labelers unless access flags are changed.

## Common Commands
- Frontend install/run: `cd apps/expert-annotator && npm install && npm run dev`
- Frontend validation: `cd apps/expert-annotator && npm run build`
- Frontend lint: `cd apps/expert-annotator && npm run lint`
- Apply schema migration: `cd apps/expert-annotator && DATABASE_URL=... node run-migration.js`
- Verify reviewer workflow schema: `cd apps/expert-annotator && DATABASE_URL=... node check-workflow-schema.mjs`
- After changing schema, verify the new columns/indexes or behavior against the live database before closing the task.
- Refresh label-feedback terms: `python3 services/data-pipeline/food_paper_crawler/feedback/update_terms.py`
- Refill low paper stock: `python3 services/data-pipeline/scripts/ensure_paper_stock.py --threshold 0`
- Run one daily ops controller locally: `python3 services/data-pipeline/scripts/daily_ops_orchestrator.py --json-summary --controller-only --tick-mode --stage-rpm gemma_proof_extraction_v1=20,gemini_flash_db_payload_v2=15 --max-wallclock-minutes 0 --screening-daily-target 1500 --screening-active-target 150 --extraction-daily-target 20 --screening-refill-batch-en 150 --screening-refill-chunk-en 150 --screening-prefill-stall-limit 3 --paper-bucket-soft-limit-mb 900 --refill-step-tr 0`
- Run one daily ops drain worker locally: `python3 services/data-pipeline/scripts/daily_ops_orchestrator.py --json-summary --drain-only --tick-mode --interleave-extraction --stage-rpm gemma_proof_extraction_v1=20,gemini_flash_db_payload_v2=15 --max-wallclock-minutes 0 --screening-daily-target 1500 --screening-tick-tasks 20 --extraction-daily-target 20 --extraction-tick-tasks 2 --refill-step-tr 0`
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
