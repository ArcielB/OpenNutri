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
- UI workflow, saves, test mode, global skip: `apps/expert-annotator/src/pages/Annotate.jsx`
- PDF highlight behavior: `apps/expert-annotator/src/components/PdfViewer.jsx`
- PDF text matching: `apps/expert-annotator/src/utils/PdfTextScanner.js`
- Suggestion flow: `apps/expert-annotator/src/components/SuggestionModal.jsx`
- Feedback term generation: `services/data-pipeline/food_paper_crawler/feedback/update_terms.py`
- Crawl/ranking logic: `services/data-pipeline/food_paper_crawler/`
- Auto-refill candidate papers: `services/data-pipeline/scripts/ensure_paper_stock.py`

## Working Rules
- Reproduce bugs first when feasible.
- Edit source files, not generated artifacts.
- Prefer small, testable changes.
- Do not use hard-negative veto logic in crawler/ranking relevance decisions. Prefer additive scoring and soft penalties. If a true hard reject seems necessary, stop and discuss it first.
- When a task changes `apps/expert-annotator/migration.sql` or otherwise changes the live schema, apply that migration to the target database in the same task unless the user explicitly says not to or there is a concrete blocker. Do not stop at the file edit without calling out the DB state.
- Update `BACKLOG.md` when backlog scope changes; delete completed items instead of leaving status notes.
- Update `README.md` when commands, architecture, or important behavior changes.
- Fail fast on missing dependencies; install them instead of adding fallback behavior.
- `sentence-transformers` is required for L2 embedding scoring.
- `feedback/latest.json` is generated local output; do not hand-edit it.
- The repo often contains local data dumps, caches, and untracked experiment output. Ignore unrelated noise.

## Product Truths
- The project is a food-composition paper pipeline plus a human labeling UI.
- Relevance filtering currently targets English and Turkish only.
- Positive feedback: latest user `draft` or `done` label with `has_data=true`.
- Negative feedback: global skip or at least 2 unique skips.
- Mixed signals across labelers are treated as conflicts and excluded from training.
- UI test mode disables DB writes and stores actions locally.
- Global "definitely no data" is immediate and has a short undo window.
- Known issue: label event counts can mismatch when empty food items exist.

## Common Commands
- Frontend install/run: `cd apps/expert-annotator && npm install && npm run dev`
- Frontend validation: `cd apps/expert-annotator && npm run build`
- Frontend lint: `cd apps/expert-annotator && npm run lint`
- Apply schema migration: `cd apps/expert-annotator && DATABASE_URL=... node run-migration.js`
- After changing schema, verify the new columns/indexes or behavior against the live database before closing the task.
- Refresh label-feedback terms: `python3 services/data-pipeline/food_paper_crawler/feedback/update_terms.py`
- Refill low paper stock: `python3 services/data-pipeline/scripts/ensure_paper_stock.py --threshold 0`

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
- Add a conflict resolution workflow for labels.
- Train and integrate the L2 classifier once label volume supports it.
- Route user suggestions into a review queue, then support attachments.
- Fix PDF nutrient highlighting reliability.
