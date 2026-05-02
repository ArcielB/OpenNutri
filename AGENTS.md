# OpenNutri Agent Guide

Use this file to keep context narrow. Read this first, then open only the files relevant to the current task.

## Startup Order
1. Read `INSTRUCTIONS.md`.
2. Check `git status --short` before editing so you do not disturb local run artifacts or user changes.
3. Read `Keys and links` only if the task needs credentials, network calls, or database writes. Use it as the source for GitHub auth when `git fetch`, `git pull`, or `git push` needs credentials.
4. Read `README.md` or `docs/handoff_2026-03-20/STATE.md` only for the subsystem you are touching.
5. For reviewer-queue, approval, dashboard, or reviewer-truth tasks, read `docs/reviewer_workflow_map.md` before re-deriving the workflow from code.

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
- UI workflow, general queue, approval, cockpit dashboard: `apps/expert-annotator/src/pages/Annotate.jsx`
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
- Commit every change you make once it is in a known working state.
- Push every working commit soon after it is validated; do not leave validated local-only commits sitting around.
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
- Relevance filtering currently targets English and Turkish only.
- The annotator now uses a general queue:
  every active labeler sees the same available `human_review_ready` papers, and a paper disappears from the queue as soon as a general label submission exists.
- General queue drafts are not claims. Multiple stale in-progress reviewers can still submit before final approval, and every immutable submission is retained in `paper_label_submissions`.
- Final human truth is reviewer-led approval:
  Arciel currently has `reviewer_profiles.can_approve_labels = true`; approval rights are configurable and separate from tester/cockpit visibility.
- Arciel's own submissions auto-accept into `paper_label_approvals` and `paper_review_outcomes`; non-Arciel submissions remain `pending_approval` until Arciel edits/approves them.
- The approval page is visible to cockpit/tester/developer accounts but mutation RPCs require `current_user_can_approve_labels()`, which excludes testers.
- Labeler performance and correction details come from `paper_label_submissions`, `paper_label_approvals.correction_diff_json`, and `paper_review_outcomes`.
- Old slot tables (`reviewer_slots`, `reviewer_slot_members`, `paper_slot_assignments`, `paper_user_assignments`, `paper_assignment_submissions`, `paper_conflicts`) are preserved as legacy audit/history only and should not drive new workflow work.
- Resolved crawler truth now comes from `paper_review_outcomes`; pending/superseded submissions must not feed feedback learning.
- Exact raw-match comparison uses deterministic payload snapshots stored in `paper_label_submissions` and accepted reviewer payloads in `paper_label_approvals`.
- UI test mode disables DB writes and stores actions locally.
- Legacy global no-data still exists in the schema for old data, but the active workflow is general queue + reviewer approval.

## Research Ops Notes
- Current top-level goal: finish Preliminary Study 3 fast enough to publish the paper and support the TÜBİTAK application.
- Queue strategy: keep paper stock low on purpose and refill as labeling proceeds so each crawl benefits from newer feedback.
- Automated daily ops target 50 visible papers in the shared general queue, balanced roughly across English and Turkish stock.
- Daily ops starts once at 00:15 America/Los_Angeles after Gemini RPD reset. The GitHub Actions controller loops every 5 minutes until `daily_ops_orchestrator.py` returns `terminal=true`; each iteration processes at most 5 AI tasks. Terminal stop reasons include `queues_full`, `ai_first_task_quota_limited`, `no_eligible_refill_need`, and `dry_run`. Non-terminal reasons like `ai_run_budget_exhausted` and `ai_quota_limited_after_progress` should continue after the 5-minute sleep. Manual `daily_ops_orchestrator.py`, `refill_assignment_queue.py`, and `ensure_paper_stock.py` defaults are also capped at 5 AI tasks per run unless explicitly overridden.
- Daily ops only refreshes feedback terms when it reaches the crawler/refill path. Existing `human_review_ready` general queue stock and queued-AI draining do not refresh feedback; `ensure_paper_stock.run_refill_cycle` refreshes terms immediately before DergiPark refresh/search unless `--skip-feedback` is explicitly passed.
- AI stage task claiming is retry-fair: queued tasks sort by lower `attempt_count`, then higher `priority`, then older creation order. Do not change this back to pure oldest-first, because one repeatedly failing paper can otherwise monopolize the 5-minute automation loop.
- `UnifiedEvaluator` intentionally accepts Gemini output as the requested JSON object, a top-level array of candidate rows, or nested `food -> nutrients[]` rows; keep these parser variants so shape drift does not become an infinite AI retry loop.
- `UnifiedEvaluator` should receive the full nutrient catalog in prompt, but not the full food catalog. Deterministic normalization verifies AI-provided food/nutrient IDs against DB rows, then falls back to exact/alias matching and custom rows.
- Team operating model:
  - Arciel: developer, configured approver, final reviewer, dashboard reviewer.
  - Peri, Aleyna, Aysegul, Daine: general-queue labelers unless access flags are changed.

## Common Commands
- Frontend install/run: `cd apps/expert-annotator && npm install && npm run dev`
- Frontend validation: `cd apps/expert-annotator && npm run build`
- Frontend lint: `cd apps/expert-annotator && npm run lint`
- Apply schema migration: `cd apps/expert-annotator && DATABASE_URL=... node run-migration.js`
- Verify reviewer workflow schema: `cd apps/expert-annotator && DATABASE_URL=... node check-workflow-schema.mjs`
- After changing schema, verify the new columns/indexes or behavior against the live database before closing the task.
- Refresh label-feedback terms: `python3 services/data-pipeline/food_paper_crawler/feedback/update_terms.py`
- Refill low paper stock: `python3 services/data-pipeline/scripts/ensure_paper_stock.py --threshold 0`
- Top up general queue stock: `python3 services/data-pipeline/scripts/refill_assignment_queue.py --target-open 50`

## Secrets
- `Keys and links` is the main local source for GitHub, Supabase, and database credentials.
- For Supabase database access, prefer the shared/session pooler connection from `Keys and links` on IPv4 networks; use the direct connection on IPv6-capable networks if the pooler path is unavailable.
- For GitHub network operations, use the GitHub token from `Keys and links` through a non-interactive auth path such as `GIT_ASKPASS`; do not rely on memory or interactive prompts.
- Hardcoded credentials also exist in some internal files such as `services/data-pipeline/config.py`; treat that as sensitive debt, not documentation.
- Never copy secret values into `AGENTS.md`, `README.md`, commits, tickets, or model responses.
- Refer to secrets by env var name only, for example `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, `GEMINI_API_KEY`.

## Task Routing
- Annotation workflow bugs: start in `apps/expert-annotator/src/pages/Annotate.jsx`
- PDF highlight bugs: start in `apps/expert-annotator/src/components/PdfViewer.jsx` and `apps/expert-annotator/src/utils/PdfTextScanner.js`
- Suggestion queue work: start in `apps/expert-annotator/src/components/SuggestionModal.jsx` and the related Supabase tables
- Feedback/L2 term work: start in `services/data-pipeline/food_paper_crawler/feedback/update_terms.py`
- Ranking/classifier/crawler work: start in `services/data-pipeline/food_paper_crawler/`
- Schema or policy changes: start in `apps/expert-annotator/migration.sql`

## Current Priorities
- Prevent empty food items and label-count mismatches.
- Operate and refine the general queue + Arciel approval workflow for Preliminary Study 3.
- Train and integrate the L2 classifier once label volume supports it.
- Route user suggestions into a review queue, then support attachments.
- Fix PDF nutrient highlighting reliability.
