# OpenNutri Agent Guide

Use this file to keep context narrow. Read this first, then open only the files relevant to the current task.

## Startup Order
1. Read `INSTRUCTIONS.md`.
2. Check `git status --short` before editing so you do not disturb local run artifacts or user changes.
3. Read `Keys and links` only if the task needs credentials, network calls, or database writes. Use it as the source for GitHub auth when `git fetch`, `git pull`, or `git push` needs credentials.
4. Read `README.md` or `docs/handoff_2026-03-20/STATE.md` only for the subsystem you are touching.

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
- UI workflow, assignments, cockpit, conflict resolution: `apps/expert-annotator/src/pages/Annotate.jsx`
- PDF highlight behavior: `apps/expert-annotator/src/components/PdfViewer.jsx`
- PDF text matching: `apps/expert-annotator/src/utils/PdfTextScanner.js`
- Suggestion flow: `apps/expert-annotator/src/components/SuggestionModal.jsx`
- Feedback term generation: `services/data-pipeline/food_paper_crawler/feedback/update_terms.py`
- Crawl/ranking logic: `services/data-pipeline/food_paper_crawler/`
- Auto-refill candidate papers: `services/data-pipeline/scripts/ensure_paper_stock.py`
- Assignment top-up job: `services/data-pipeline/scripts/refill_assignment_queue.py`

## Working Rules
- Reproduce bugs first when feasible.
- Edit source files, not generated artifacts.
- Prefer small, testable changes.
- Commit every change you make once it is in a known working state.
- Do not use hard-negative veto logic in crawler/ranking relevance decisions. Prefer additive scoring and soft penalties. If a true hard reject seems necessary, stop and discuss it first.
- When a task changes `apps/expert-annotator/migration.sql` or otherwise changes the live schema, apply that migration to the target database in the same task unless the user explicitly says not to or there is a concrete blocker. Do not stop at the file edit without calling out the DB state.
- Update `BACKLOG.md` when backlog scope changes; delete completed items instead of leaving status notes.
- Update `README.md` when commands, architecture, or important behavior changes.
- When a research-protocol, reviewer-role, or benchmark-validity decision changes, write it to the latest handoff/state note in the same task instead of leaving it only in chat.
- Fail fast on missing dependencies; install them instead of adding fallback behavior.
- `sentence-transformers` is required for L2 embedding scoring.
- `feedback/latest.json` is generated local output; do not hand-edit it.
- The repo often contains local data dumps, caches, and untracked experiment output. Ignore unrelated noise.

## Product Truths
- The project is a food-composition paper pipeline plus a human labeling UI.
- Relevance filtering currently targets English and Turkish only.
- The annotator is now assignment-driven:
  every paper gets exactly 2 official reviewer slots and reviewers only see their own queue.
- Official reviewer slots are `arciel`, `peri`, and `aleyna`.
- `Daine` belongs inside the Arciel lane for English-only shadow review when her reviewer profile is configured; she does not count as an independent official slot.
- Resolved crawler truth now comes from `paper_review_outcomes`; unresolved disagreements must not feed feedback learning.
- Exact raw-match comparison uses deterministic submission payload snapshots stored in `paper_assignment_submissions`.
- UI test mode disables DB writes and stores actions locally.
- Legacy global no-data still exists in the schema for old data, but the active workflow is slot assignment + conflict resolution.
- Known issue to remember: if Daine’s email is not yet mapped into `reviewer_profiles` / `reviewer_slot_members`, the Arciel lane will behave as Arciel-only until that configuration is completed.

## Research Ops Notes
- Current top-level goal: finish Preliminary Study 3 fast enough to publish the paper and support the TÜBİTAK application.
- Queue strategy: keep paper stock low on purpose and refill as labeling proceeds so each crawl benefits from newer feedback.
- Team operating model:
  - Arciel: developer, official reviewer slot, cockpit/conflict resolver.
  - Peri: official reviewer slot.
  - Aleyna: official reviewer slot.
  - Daine: cheap English-only shadow helper under Arciel lane, ops-only until formally configured; not an official standalone reviewer slot.

## Common Commands
- Frontend install/run: `cd apps/expert-annotator && npm install && npm run dev`
- Frontend validation: `cd apps/expert-annotator && npm run build`
- Frontend lint: `cd apps/expert-annotator && npm run lint`
- Apply schema migration: `cd apps/expert-annotator && DATABASE_URL=... node run-migration.js`
- Verify assignment workflow schema: `cd apps/expert-annotator && DATABASE_URL=... node check-workflow-schema.mjs`
- After changing schema, verify the new columns/indexes or behavior against the live database before closing the task.
- Refresh label-feedback terms: `python3 services/data-pipeline/food_paper_crawler/feedback/update_terms.py`
- Refill low paper stock: `python3 services/data-pipeline/scripts/ensure_paper_stock.py --threshold 0`
- Top up reviewer queues: `python3 services/data-pipeline/scripts/refill_assignment_queue.py`

## Secrets
- `Keys and links` is the main local source for GitHub, Supabase, and database credentials.
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
- Operate and refine the assignment-driven labeling workflow for Preliminary Study 3.
- Train and integrate the L2 classifier once label volume supports it.
- Route user suggestions into a review queue, then support attachments.
- Fix PDF nutrient highlighting reliability.
