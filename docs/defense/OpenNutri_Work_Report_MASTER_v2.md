# OpenNutri Work Report v2 - Master Ledger

Prepared: 2026-06-05
Repository snapshot: `1a8d1cf0394d2c86ba31604888969c30a9a47d32` (`main`, even with `origin/main`)
Activity span in git: 2025-12-19 to 2026-06-05
Scope: documentation-only report package. No application API, schema, frontend behavior, deployment configuration, database state, or live service was changed.

Correction note: the first v2 report package was intentionally evidence-backed but too compressed for assessment use. This expanded version is a fuller work ledger: it lists what was built, why it was built, how it was built, the technologies used, line/commit evidence, timing, validation evidence, and known attribution caveats.

## 1. Methodology

This report was built from current source evidence after a fresh `git fetch origin` and ahead/behind check (`main...origin/main = 0 0`). The working tree already contained unrelated untracked artifacts, including older work-breakdown exports and `docs/defense/read_this/`; those are intentionally not part of this package.

Evidence sources:

- Git history: `git log --date=short --reverse`, `git shortlog -sne --all`, per-author `git log --all --numstat`.
- Current tracked source inventory: `git ls-files` with USDA dumps, generated binaries, legacy archive, `node_modules`, `dist`, local data, `feedback/latest.json`, and `package-lock.json` excluded.
- Current code structure: `apps/expert-annotator/`, `services/data-pipeline/`, `apps/expert-annotator/migration.sql`, `.github/workflows/daily-ops.yml`.
- Existing project docs: `README.md`, `AGENTS.md`, `docs/handoff_2026-03-20/STATE.md`, and `docs/reviewer_workflow_map.md`.
- Implementation file reads and counts: `migration.sql`, `PdfViewer.jsx`, `PdfTextScanner.js`, `Annotate.jsx`, `FoodAutocomplete.jsx`, `NutrientAutocomplete.jsx`, `SuggestionModal.jsx`, `fuzzyMatch.js`, `ResetPassword.jsx`, `ai_routing.py`, `unified_evaluator.py`, `process_stage_queue.py`, `crawler_v2.py`, `ranking.py`, `update_terms.py`, and `daily-ops.yml`.

The reports separate two kinds of attribution:

- **Git-author attribution:** what git can prove directly across all local/remote refs. Every `landeryt` commit is credited to Huan. `baezarciel` plus the initial `ArcielB` repository commit are credited to Arciel. The `ayseguldogan2706-cpu` identity has seven all-ref commits: five original MVP/frontend commits on `origin/master` plus two push-test commits on the current mainline.
- **Subsystem attribution:** the team's stated ownership split used for assessment. Ayşegül owns the core user-facing annotator frontend: annotation UI, PDF viewing/highlighting UX, autocomplete surfaces, and workflow views. Arciel owns database/schema/RLS/RPCs, crawler, AI pipeline, daily ops, deployment infrastructure, backend-driven cockpit integrations, documentation, and project management.

That distinction matters. A report that only uses current-mainline git author lines would under-credit Ayşegül because her original MVP/frontend branch was later imported/reorganized through integration commits. A report that ignores git author evidence would overstate what commit history directly proves. This package uses both, and labels them explicitly.

## 2. Reproducible Metrics

### Repository activity

`git shortlog -sne --all` at the current snapshot:

| Git author | Commits |
| --- | ---: |
| `baezarciel <baezarciel@gmail.com>` | 211 |
| `landeryt <mcraft160105@gmail.com>` | 24 |
| `ayseguldogan2706-cpu <ayseguldogan2706@example.com>` | 7 |
| `ArcielB <106127166+ArcielB@users.noreply.github.com>` | 1 |

Filtered all-ref git-author churn, excluding `FoodData_Central_*`, `legacy/**`, `apps/expert-annotator/package-lock.json`, and `docs/proposal-sections/**`:

| Git author | Added | Deleted | Notes |
| --- | ---: | ---: | --- |
| `baezarciel` | 67,971 | 17,639 | Current integration, backend, ops, schema, docs, and many frontend integration commits. |
| `landeryt` | 2,188 | 582 | Huan's directly authored commits. |
| `ayseguldogan2706-cpu` | 6,624 | 88 | Original MVP/frontend commits on `origin/master` plus push-access test commits. |
| `ArcielB` | 1 | 0 | Initial repository README commit; treated as Arciel. |

Tracked source/documentation line count with the report package excluded from the metric: **52,856 lines**. This excludes USDA CSV/XLSX dumps, generated binaries, the legacy archive, `node_modules`, `dist`, local pipeline data, generated `feedback/latest.json`, and `package-lock.json`.

Active bucket split, excluding proposal appendix drafts and generated artifacts:

| Bucket | Current tracked lines | Main evidence |
| --- | ---: | --- |
| Backend, ops, schema | 31,796 | `services/data-pipeline/**`, SQL schema/RPCs, GitHub Actions workflow. |
| Frontend | 13,788 | `apps/expert-annotator/src/**`, Vite app shell, API proxy, frontend config. |
| Active docs | 6,301 | README, AGENTS, reviewer workflow, handoff, defense docs. |
| Proposal appendix docs | 971 | `docs/proposal-sections/**`, counted in the 52,856 total but excluded from active bucket discussion. |

Key implementation file sizes at this snapshot:

| File | Lines | Role |
| --- | ---: | --- |
| `apps/expert-annotator/migration.sql` | 5,396 | Database schema, RLS, RPCs, workflow engine. |
| `services/data-pipeline/food_paper_crawler/crawler_v2.py` | 2,215 | Multi-source paper crawler. |
| `apps/expert-annotator/src/utils/PdfTextScanner.js` | 2,323 | Browser PDF text/layout/evidence scanner. |
| `services/data-pipeline/scripts/process_stage_queue.py` | 1,560 | AI-stage queue worker, retry/fallback/routing. |
| `services/data-pipeline/food_paper_crawler/feedback/update_terms.py` | 1,219 | Label-feedback learning export. |
| `apps/expert-annotator/src/pages/Annotate.jsx` | 1,163 | Main annotator orchestration. |
| `apps/expert-annotator/src/components/PdfViewer.jsx` | 939 | PDF rendering, overlay, page navigation. |
| `services/data-pipeline/ai_routing.py` | 842 | Routing buckets and deterministic AI payload normalization. |
| `services/data-pipeline/evaluator/unified_evaluator.py` | 687 | Shared model prompt/contract and JSON parser. |
| `.github/workflows/daily-ops.yml` | 148 | Scheduled controller plus 5 drain-worker matrix. |

Schema object counts from `migration.sql`:

| Object type | Count |
| --- | ---: |
| Tables | 31 |
| Functions/RPCs | 26 |
| RLS policies | 75 |
| RLS-enabled tables | 32 |
| Indexes | 69 |
| Triggers | 2 |
| `SECURITY DEFINER` functions | 22 |

## 3. What OpenNutri Is

OpenNutri is a food-composition paper discovery and human-verification system. It is not a generic nutrition chatbot and not a general literature search tool. Its target is narrow: direct, real-food or food-product composition values that can become useful nutrition facts for datasets, diet tracking, food exporters, inspection, or related real-world use.

The current system has two production surfaces over one Supabase Postgres database:

- **Expert annotator frontend:** `apps/expert-annotator/`, React 19 + Vite, deployed on Vercel. It provides login, the general labeling queue, AI-prefilled editable food/nutrient rows, a PDF viewer with evidence overlays, approval workflow, dashboard, reviewer admin, useful-paper cockpit, pipeline cockpit, and suggestion review surfaces.
- **Data pipeline:** `services/data-pipeline/`, Python. It handles USDA ETL, multi-source scientific-paper crawling, feedback term learning, staged AI screening/extraction, paper upload/routing, and daily unattended operations.

The current end-to-end workflow is:

```text
USDA reference data
  -> entities / aliases / master_nutrients / sources / claims

Europe PMC / OpenAlex / Semantic Scholar crawler
  -> metadata search
  -> additive relevance filter
  -> PDF acquisition and full-text validation
  -> Supabase paper + search-hit registration
  -> Small model screening: Gemma 31B, 26B fallback, text mode
  -> Medium model triage: Gemini 3.1 Flash-Lite
  -> Strong model extraction: Gemini 3.5 Flash, PDF mode
  -> human_review_ready general queue
  -> labeler submission
  -> Arciel approval / correction
  -> paper_review_outcomes
  -> feedback-learning export for later crawler scoring
```

## 4. Repository Structure

### Frontend

`apps/expert-annotator/src/` is the user-facing annotator. Important files:

- `pages/Annotate.jsx`: state orchestration, queue refresh, cockpit lazy loading, annotation save/submit, approval actions, help/suggestion routing.
- `views/*.jsx`: extracted queue, approval, dashboard, paper overview, pipeline, suggestion, reviewer-admin views.
- `components/PdfViewer.jsx` and `utils/PdfTextScanner.js`: PDF rendering and evidence layout analysis.
- `components/FoodAutocomplete.jsx`, `components/NutrientAutocomplete.jsx`, `utils/fuzzyMatch.js`: catalog search and approximate matching.
- `components/SuggestionModal.jsx`, `views/SuggestionsReviewView.jsx`, `views/MySuggestionsView.jsx`: user/cockpit suggestion flow.
- `utils/annotateHelpers.js`: payload normalization, model-stage labels, cockpit funnel helpers, AI extraction summaries.

### Backend and Data Pipeline

`services/data-pipeline/` includes:

- `food_paper_crawler/crawler_v2.py`, `ranking.py`, source adapters: paper discovery and relevance scoring.
- `food_paper_crawler/feedback/update_terms.py`: human-truth feedback learning.
- `ai_routing.py`, `evaluator/unified_evaluator.py`, `scripts/process_stage_queue.py`: AI decision contract, deterministic normalization, queue processing, retry/fallback logic.
- `scripts/daily_ops_orchestrator.py`, `scripts/ensure_paper_stock.py`, `scripts/upload_to_supabase.py`: unattended ops, queue refill, upload/routing.
- USDA ETL scripts and harvester utilities retained as reference/data-ingest support.

### Database and Security

`apps/expert-annotator/migration.sql` is the current schema/RLS/RPC source of truth. It defines the canonical food/nutrient/reference layer, paper discovery tables, annotation tables, general queue and approval tables, AI extraction/routing tables, reviewer profiles, suggestion review tables, RLS policies, and service-role RPCs.

Important RPCs:

- `claim_paper_stage_tasks`: atomic `FOR UPDATE SKIP LOCKED` claim primitive for parallel workers.
- `get_general_queue_cards`: lean queue card projection with latest AI prefill and this user's annotation status.
- `submit_general_label`: freezes a labeler payload into `paper_label_submissions`.
- `approve_label_submission`: writes reviewer truth, correction diffs, and final `paper_review_outcomes`.
- `get_cockpit_ai_extractions`: egress-slim AI details for Useful Papers.
- `get_pipeline_ops_snapshot`: cockpit aggregate endpoint for crawler/model/human funnel state.

### Deployment and Operations

`.github/workflows/daily-ops.yml` schedules daily ops every 5 minutes. Each scheduled run starts:

- One serialized `refill-controller` job under `daily-ops-refill-controller`, allowed to crawl/upload/refill.
- A 5-worker `drain-workers` matrix, running in parallel with the controller and allowed only to drain already-created AI tasks.

The frontend deployable app is Vercel-hosted. Supabase stores auth/application data. Paper PDFs are source-URL/on-demand by default; suggestion attachments remain in the private `suggestion-attachments` bucket.

## 5. Timeline

| Phase | Dates | Main work |
| --- | --- | --- |
| Bootstrap | 2025-12-19 | Repository created, access verified. |
| MVP and snapshot | 2026-03-09 to 2026-03-16 | Earlier codebase imported, README/reorganization, baseline frontend and crawler brought into `apps/` and `services/`. Huan centralized theme state. |
| Feedback and crawler hardening | 2026-03-19 to 2026-03-30 | Reset password, label events/test mode, feedback terms, auto-crawl, bilingual crawler split, DergiPark index, no-hard-veto crawler scoring. |
| Reviewer workflow and AI routing | 2026-04-13 to 2026-04-29 | Assignment workflow, reviewer admin, Gemini triage/extraction, read-only queues, suggestion review, image attachments, conflict system, AI prefill. |
| General approval queue | 2026-05-02 to 2026-05-09 | Slot workflow replaced by general queue plus approval, useful AI details restored, queue limited to normalized AI `has_data`, Gemma cascade added, suggestion status changes, fuzzy matching. |
| Daily ops and cockpit | 2026-05-11 to 2026-05-20 | Retry-fair AI queue, daily quota draining, pipeline cockpit, reviewer UI polish, evidence highlighting, Annotate refactor to helpers/views, tester/developer access. |
| Three-stage cascade and PDF storage hardening | 2026-05-27 to 2026-05-31 | Auth allowlist hardening, controller/drain worker fan-out, Flash-Lite middle stage, source-URL PDFs, CORS proxy, browser cache, true PDF page numbers for Gemini. |
| Performance and report package | 2026-06-04 to 2026-06-05 | Lean queue RPC, lazy cockpit, self-hosted PDF worker, durable Cache Storage PDFs, evidence-first PDF rendering, v1/v2 work reports. |

## 6. Detailed Subsystem Work Ledger

### 6.1 Annotator Frontend and User Workflow - Ayşegül, with backend integration by Arciel

Evidence files: `Annotate.jsx` (1,163), `QueueView.jsx`, `ApprovalView.jsx`, `DashboardView.jsx`, `AllPapersView.jsx`, `PipelineOpsView.jsx`, `annotateHelpers.js` (574), `FoodItemForm.jsx`, `FoodAutocomplete.jsx` (664), `NutrientAutocomplete.jsx` (334), `NutrientPopover.jsx`, `index.css`.

What was built:

- Authenticated annotator shell, queue workspace, editor, and reviewer/cockpit tabs.
- Editable food items and nutrient rows with custom-food/custom-nutrient support.
- AI prefill: latest normalized Gemini payload becomes editable rows for queue papers without an existing draft.
- Save draft, submit reviewed data, mark no usable data, ask for help, and approver correction flows.
- Dashboard metrics built from submissions, approvals, correction diffs, and outcomes.
- Useful Papers view with normalized AI details, not raw reasoning.
- Pipeline cockpit funnel with stable stage labels: Small, Medium, Strong model roles.
- Test mode/read-only behavior that prevents DB writes.

Hard parts:

- Keeping JS, SQL, and Python payload shapes aligned so AI rows, human drafts, and approved truth are comparable.
- Avoiding Supabase egress blowups by using `get_general_queue_cards`, lazy cockpit loading, and `get_cockpit_ai_extractions` instead of raw `select('*')` extraction lists.
- Preserving the workflow truth that queue drafts are not claims, while submissions remove papers from the general visible queue.

Validation evidence:

- Current code paths call `get_general_queue_cards`, `submit_general_label`, `approve_label_submission`, and `get_pipeline_ops_snapshot`.
- README and reviewer workflow docs describe the same general queue -> approval -> `paper_review_outcomes` truth model.
- Frontend source is 13,788 tracked lines; the core frontend source churn excluding Huan-specific files is `+20,820/-7,891`.

### 6.2 PDF Evidence Highlighting and PDF Delivery - Ayşegül frontend, Arciel integration/hardening

Evidence files: `PdfTextScanner.js` (2,323), `PdfViewer.jsx` (939), `EvidenceLocations.js` (439), `pdfCache.js`, evidence status cache utilities, `/api/pdf`.

What was built:

- Browser-side PDF.js viewer with continuous document navigation, page scaling, evidence overlays, nutrient click marks, and popover insertion into nutrient rows.
- Scanner that reconstructs tables, captions, paragraphs, columns, and evidence regions from PDF text glyph positions.
- Source strip and overlay deduplication so multiple rows citing the same table or paragraph share one evidence chip/region.
- Handling for unreliable AI page hints: over-range printed journal pages are treated as non-gating, and detected printed page numbers can be mapped to actual PDF pages.
- Durable PDF browser cache via Cache Storage and idle prefetch of next queue papers.
- Source-URL PDF delivery and same-origin proxy for publisher PDFs that fail direct browser CORS loads.

Hard parts:

- PDF text extraction has no table model. `PdfTextScanner.js` derives row gaps, column gutters, paragraph blocks, table/caption regions, quote matches, and stable region keys from geometry.
- Evidence matching must prefer precision. The viewer suppresses random nutrient words in prose and highlights table/paragraph blocks only when source evidence resolves.
- Offprint page numbering required separating printed page numbers from PDF page indexes.

Validation evidence:

- 27-plus commits touch PDF viewer/scanner/highlighting behavior from 2026-04-22 through 2026-06-05.
- Current docs and AGENTS explicitly preserve content-driven highlighting, whole-block overlays, source-chip deduplication, and over-range `page_hint` handling.

### 6.3 Huan's Full-Stack User Features

Evidence files: `SuggestionModal.jsx` (279), `fuzzyMatch.js` (162), `ResetPassword.jsx` (145), `migration.sql` sections for `backlog_review_items`, `suggestion-attachments`, conflict tables/view, and landeryt commit history.

What was built:

- Suggestion submission modal with image attachments.
- Cockpit suggestion review flow and user "My Suggestions" status visibility.
- Private Supabase Storage attachment bucket with user-folder path containment and image-only limits.
- Reset password route that consumes Supabase recovery tokens and updates the user password instead of silently logging in.
- Theme centralization and system-theme handling.
- Infinite PDF scroll contribution.
- Legacy conflict table/view/UI for multiple reviewer submissions under the earlier assignment model.
- Fuzzy-match utility used by both food and nutrient autocomplete components.
- Developer/tester read visibility without write capability.

Hard parts:

- The suggestion feature is a vertical slice: frontend validation, storage upload, DB insert, RLS/storage policy alignment, and rollback of uploaded objects if DB insert fails.
- The fuzzy engine is compact but algorithmic: token normalization, inflection handling, bounded edit distance, adjacent transposition, and relation scoring.
- Tester visibility had to broaden read access without weakening mutation guards.

Validation evidence:

- 24 `landeryt` commits from 2026-03-16 to 2026-05-20.
- Filtered direct churn: `+2,188/-582`.
- README and migration file both describe/use `backlog_review_items` and `suggestion-attachments`.

### 6.4 Supabase Schema, Security, and Reviewer Truth - Arciel

Evidence file: `apps/expert-annotator/migration.sql` (5,396 lines).

What was built:

- Canonical reference layer: `entities`, `entity_aliases`, `master_nutrients`, `sources`, `claims`.
- Paper discovery layer: `papers`, `paper_search_hits`, `paper_search_batches`, `paper_search_batch_hits`.
- Annotation layer: `annotations`, `food_items`, `annotation_nutrient_values`, events and global labels.
- Workflow generations preserved for audit: legacy slot assignments, Huan's conflict model, and current general approval queue.
- AI routing tables: `routing_stage_configs`, `paper_stage_tasks`, `ai_extractions`.
- Reviewer profiles and access flags, including cockpit, tester, approver, and signup allowlist controls.
- RLS and `SECURITY DEFINER` RPCs for queue, approval, cockpit, pipeline, and service-role automation.

Hard parts:

- Keeping one convergent, idempotent migration file safe to re-run against a live Supabase project.
- Protecting private tables while still exposing queue/cockpit aggregates through controlled RPCs.
- Making AI output and human output comparable by deterministic payload building and hashing.
- Maintaining audit history while migrating from slot workflows to the current general approval queue.

Validation evidence:

- 31 tables, 26 functions/RPCs, 75 RLS policies, 32 RLS-enabled tables, 69 indexes, 2 triggers, 22 `SECURITY DEFINER` functions.
- `claim_paper_stage_tasks` uses `FOR UPDATE SKIP LOCKED`, enabling safe parallel drain workers.
- `paper_review_outcomes` is the final human-truth table used by feedback learning.

### 6.5 AI Extraction Cascade - Arciel

Evidence files: `unified_evaluator.py` (687), `ai_routing.py` (842), `process_stage_queue.py` (1,560), `recover_gemini_candidates.py`, `flash_lite_triage_experiment.py`.

What was built:

- Shared `UnifiedEvaluator` contract for all model stages.
- Three-stage cascade: Gemma proof extraction -> Gemini Flash-Lite triage -> Gemini Flash final extraction.
- Deterministic AI payload normalization into the same shape as human labels.
- Stage configuration in `routing_stage_configs`, including thresholds, fallback models, next stages, and model input mode (`text`/`pdf`).
- Retry-fair task claiming, stale processing requeue, quota-safe requeue, retry ceiling, non-retryable model error handling, and same-attempt Gemma fallback.
- Native PDF input for Gemini stages and page-marked text for Gemma.
- Follow-up priority scoring so downstream models process the highest-value candidates first.
- Provisional AI no-data skips that stay out of the default human queue.

Hard parts:

- LLM JSON shape drift is handled by fence stripping, balanced JSON candidate scanning, root coercion, top-level array support, and nested food/nutrient row flattening.
- Normalization rejects unsupported units/bases while preserving useful custom food/nutrient rows.
- Quota and timeout behavior must not make a paper look retry-failing or strand rows in `processing`.
- The final Gemini quota is low, so the cascade must rank and drain the top-N rather than process oldest-first.

Validation evidence:

- AGENTS and README describe the same stage roles, model specs, quotas, and failure policy.
- `process_stage_queue.py` validates model runtime before claiming rows and requeues stale tasks before queue decisions.
- `flash_lite_triage_experiment.py` remains as the regression harness before future triage changes.

### 6.6 Paper Crawler and Feedback Learning - Arciel

Evidence files: `crawler_v2.py` (2,215), `ranking.py` (486), source adapters, `feedback/update_terms.py` (1,219), feedback config/terms modules.

What was built:

- Multi-source crawler for Europe PMC, OpenAlex, Semantic Scholar, and retained Turkish/DergiPark support.
- Search -> metadata filter -> PDF acquisition -> full-text validation pipeline.
- Additive relevance scoring with lexical, unit, method, food/nutrient, embedding, source-prior, batch, concept, and learned n-gram signals.
- Explicit no-hard-negative-veto policy: negative phrases are penalties, not immediate rejects.
- Live and local dedup through canonical keys and terminal paper state.
- PDF acquisition fallback ladder: open-access package parsing, direct fetch, curl/browser user-agent fallback, PDF validation, oversized-PDF rejection, and accepted manifest writing.
- Feedback loop from accepted human `paper_review_outcomes` to log-odds n-gram weights, source priors, pair scores, and concept scores.

Hard parts:

- The crawler must be recall-friendly at metadata time but precision-heavy at PDF/full-text time.
- Feedback learning must not train on pending, superseded, conflicted, or AI-only truth.
- Scheduled runs must respect target sizes and wall-clock limits rather than over-downloading.
- Partial accepted crawler results must be written and uploaded when the wall-clock limit is reached.

Validation evidence:

- README records English-only current ops (`tr=0`) while retaining Turkish support.
- `update_terms.py` builds labels from `paper_review_outcomes` first and excludes `truth_source_kind='ai_model'`.
- Crawler summary manifests include stage/funnel/reason evidence for audit.

### 6.7 Daily Ops and Deployment Infrastructure - Arciel

Evidence files: `.github/workflows/daily-ops.yml` (148), `daily_ops_orchestrator.py`, `ensure_paper_stock.py`, `upload_to_supabase.py`, README/STATE ops sections.

What was built:

- GitHub Actions scheduled tick every 5 minutes.
- One serialized controller job that can crawl/upload/refill.
- Five parallel drain workers that only process existing AI tasks.
- Manual dispatch `workers` input for controlled bursts.
- Environment-driven secrets (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`) and no committed secret values.
- Source-URL paper PDF strategy to avoid Supabase Storage/egress pressure.
- Lean cockpit/queue RPC strategy to reduce Supabase egress.

Hard parts:

- The controller must not be a bottleneck for model draining, so workers run in parallel and rely on DB-atomic claims.
- Model task processing must recover from killed runners and GitHub job timeouts.
- Supabase free-tier storage/egress limits influenced both backend and frontend design.

Validation evidence:

- Workflow uses `OPENNUTRI_STORE_PDFS_IN_SUPABASE=0`, stage RPMs, 75-minute controller wall-clock, 2,400-second crawler wall-clock, 1,500/500/20 daily stage targets, and a five-worker matrix.
- README documents the same controller/drain split, queue counting, and worker limitations.

## 7. Contributor Assessment Summary

### Duc Huan Ngo

Primary evidence: `landeryt` commits and files.

Assessment-facing achievements:

- Built a full-stack suggestion feature with attachments, storage policies, rollback behavior, user/cockpit views, and status tracking.
- Implemented a reusable fuzzy-match engine used by food/nutrient autocomplete.
- Fixed reset-password behavior by handling Supabase recovery sessions correctly.
- Added legacy conflict resolution infrastructure before the workflow was superseded.
- Contributed theme handling, infinite PDF scroll, tester/developer read visibility, and UI polish.

Most defensible metrics: 24 commits, `+2,188/-582` filtered churn, direct ownership of the files and schema pieces above.

### Ayşegül Doğan

Primary evidence: frontend subsystem ownership and current source.

Assessment-facing achievements:

- Owned the annotator frontend that labelers actually use: queue, editor, PDF viewing, autocomplete, source/evidence UI, and workflow surfaces.
- Built or owned the core user-facing PDF/evidence experience: table-scoped highlighting, evidence navigation, overlays, source strips, and nutrient insertion.
- Owned catalog-entry UX: food/nutrient forms, autocomplete interactions, custom rows, and reviewer-facing editing.
- Helped make the frontend production-suitable through responsive state management, read-only/test behavior, and user-facing cockpit surfaces.

Most defensible metrics: 7 all-ref commits; all-ref filtered git-author churn `+6,624/-88`; 13,788 current frontend lines; 10,334 lines in the principal queue/PDF/autocomplete/view files listed above. Current-mainline path churn is larger because later frontend evolution and integration were committed through shared/integration commits.

### Arciel Aliognis Baez Zamora

Primary evidence: `baezarciel` and `ArcielB` commits, backend/ops/schema/docs ownership.

Assessment-facing achievements:

- Built the Supabase database contract, RLS model, reviewer truth workflow, and queue/approval/cockpit RPCs.
- Built the crawler, additive relevance scoring, feedback learning, and paper upload/routing pipeline.
- Built the three-stage AI cascade with normalization, retry fairness, quota safety, PDF/text model input modes, and follow-up prioritization.
- Built unattended daily ops on GitHub Actions with controller/drain worker split and source-URL PDF strategy.
- Performed integration, documentation, project management, and live ops hardening.

Most defensible metrics: 211 `baezarciel` commits plus the initial `ArcielB` commit; filtered `baezarciel` churn `+67,971/-17,639`; backend/ops/schema bucket 31,796 lines.

## 8. What Did Not Change in This v2 Package

- No schema migration was edited or applied.
- No frontend source, backend source, workflow YAML, README, AGENTS, or live services were changed.
- No Vercel deploy is required.
- No Supabase database migration or data write is required.
- No secret values are copied into this report; only environment variable names are referenced.

## 9. Expanded Assessment Ledger

This section is the detailed ledger requested for defense/evaluation. It is organized by workstream rather than by raw commit order because the project repeatedly replaced earlier architecture with better production versions. For each item, the ledger records:

- What was done.
- Why it was needed.
- How it was implemented.
- Which technologies were used.
- Who should be credited under the stated attribution rules.
- When the work occurred.
- Where the source evidence lives.

### 9.1 Project Bootstrap and MVP Annotator

**When:** 2025-12-19, then 2026-03-02 to 2026-03-09.
**Credit:** Ayşegül for the original annotator MVP commits on `origin/master`; Arciel for importing/reorganizing the codebase into the current repository structure; Huan for later theme refinement.
**Technology:** React, Vite, Supabase Auth, Supabase Storage, plain CSS, PDF.js/react-pdf.

What was built:

- Initial React annotator application.
- Login screen and session-aware app shell.
- Google OAuth login.
- Light/dark theme toggle.
- Forgot-password/reset affordance at the frontend level.
- First paper/PDF annotation workspace.
- Basic food item form.
- First PDF viewer and nutrient highlight behavior.
- Initial SQL schema fragments for annotator data.

Why it was needed:

The project needed a human labeling tool before any advanced crawler or AI cascade mattered. OpenNutri's final truth is human-reviewed food composition data; therefore the earliest useful deliverable was a working interface where a labeler could open a paper, inspect its PDF, and enter food/nutrient rows.

How it was implemented:

- Ayşegül's `origin/master` commits introduced the initial Vite app, components, CSS, Supabase client, auth pages, and PDF viewer.
- Commit `00fd645` specifically added a flexible nutrients model, food autocomplete, and PDF highlight redesign.
- The March `main` snapshot/reorganization imported this application into the current `apps/expert-annotator/` tree.
- Later work split the app into smaller view/components but retained the same core role: a browser-based expert labeling interface.

Evidence:

- Direct all-ref Ayşegül commits: `7c2d372`, `614a82c`, `6245a17`, `00fd645`, `8a29dcb`.
- Current frontend tracked lines: 13,788.
- Principal frontend files listed in the Ayşegül report: 10,334 current lines.

### 9.2 Authentication, Roles, Theme, and Read-Only Training Access

**When:** March to May 2026.
**Credit:** Ayşegül for initial auth/frontend shell, Huan for theme centralization/reset-password/tester visibility changes, Arciel for role/RLS/RPC backing and reviewer profile workflow.
**Technology:** Supabase Auth, React state, browser `matchMedia`, session storage, Postgres RLS, `SECURITY DEFINER` role predicates.

What was built:

- Email/password login.
- Google OAuth login.
- Password recovery route that handles Supabase recovery sessions.
- Theme state shared between login and app chrome.
- System-theme preference support.
- Reviewer profile sync (`sync_reviewer_profile`).
- Role model: labeler, cockpit, tester, approver, service role.
- Tester/developer read-only visibility for training/review.
- Signup allowlist controlled through a private Supabase auth hook.

Why it was needed:

The project had multiple user types. Labelers needed normal queue access; Arciel needed approval permissions; testers needed to inspect the workflow without accidentally writing data; cockpit users needed dashboards; service-role automation needed privileged task/crawler operations. A simple "authenticated user can do everything" model would have leaked private rows and allowed unsafe writes.

How it was implemented:

- `App.jsx` routes normal users to `Annotate`, recovery URLs to `ResetPassword`, and unauthenticated users to `Login`.
- Huan's reset page parses recovery tokens, establishes the recovery session, validates passwords, updates the user, and cleans tokens from the URL.
- `useTheme.js` follows system theme when no override exists and persists an explicit override only when needed.
- `migration.sql` defines `reviewer_profiles` flags and the predicate functions `current_user_has_cockpit_access`, `current_user_is_tester`, `current_user_can_write`, `current_user_can_approve_labels`, and cockpit write predicates.
- RLS policies and mutation RPCs use those predicates rather than trusting frontend-only checks.
- `allowed_auth_emails` is private; the signup allowlist uses a `SECURITY DEFINER` auth hook with direct client table privileges revoked.

Evidence:

- Huan commits: `cbf61ad`, `341b40e`, `4e208a5`, `9f18a56`.
- Arciel schema evidence: 75 RLS policies, 32 RLS-enabled tables, 22 `SECURITY DEFINER` functions.
- Current files: `App.jsx`, `Login.jsx`, `ResetPassword.jsx`, `useTheme.js`, `migration.sql`.

### 9.3 Annotation Editor, AI Prefill, and Payload Contract

**When:** March to June 2026, with major workflow changes on 2026-04-13, 2026-05-02, and 2026-06-04.
**Credit:** Ayşegül for the core editor/workflow frontend; Arciel for backend contract/RPCs, AI prefill integration, general queue redesign, and performance hardening.
**Technology:** React 19, Supabase JS client, Postgres RPCs, JSONB payloads, deterministic hashing, Vite.

What was built:

- Queue paper selection and editable food/nutrient form.
- Draft saving.
- Final submission with validation.
- No usable data action.
- AI prefill from latest normalized Gemini output.
- Approval editor with original labeler payload and final reviewer payload.
- Exact payload snapshots in `paper_label_submissions`.
- Correction diffs in `paper_label_approvals.correction_diff_json`.
- Final truth rows in `paper_review_outcomes`.

Why it was needed:

The AI cascade is intentionally not final human truth for most useful papers. Human reviewers must correct the DB-compliant AI extraction into trustworthy food-composition data. That requires the frontend editor, SQL payload builders, and Python AI normalizer to speak the same payload language. Without one stable payload contract, the project could not compare AI rows to human rows or track reviewer corrections.

How it was implemented:

- `Annotate.jsx` owns queue/profile/cockpit state, loads the selected paper, initializes rows from `normalized_payload_json` only when no saved annotation exists, saves annotation rows, and calls `submit_general_label`.
- `annotateHelpers.js` converts normalized payload food/nutrient entries into editable UI rows and formats summaries.
- `build_annotation_submission_payload` in SQL creates canonical JSON from saved annotation rows.
- `normalize_ai_payload_with_summary` in Python creates the same logical JSON structure from model output.
- `payload_text_and_hash` creates deterministic hashes so identical AI/human payloads can be compared.
- `approve_label_submission` stores both the original labeler submission and the accepted reviewer payload.

Evidence:

- `Annotate.jsx`: 1,163 lines.
- `annotateHelpers.js`: 574 lines.
- SQL RPCs: `submit_general_label`, `approve_label_submission`, `build_annotation_submission_payload`, `build_label_payload_diff`.
- Python normalizer: `ai_routing.py`, 842 lines.

### 9.4 General Queue and Approval Workflow

**When:** Slot workflow in April 2026; general queue replacement on 2026-05-02; refinements through June.
**Credit:** Arciel for schema/RPC/workflow redesign and final approval model; Ayşegül for frontend queue/approval surfaces; Huan for the earlier conflict system that was later superseded.
**Technology:** Supabase Postgres, RLS, RPCs, React views, immutable JSON payloads.

What was built:

- Earlier assignment/slot workflow with official and shadow reviewers.
- Huan's conflict-detection workflow for multiple disagreeing submissions.
- Current general queue where active labelers see the same `human_review_ready` papers.
- Immutable `paper_label_submissions`.
- Reviewer approval into `paper_label_approvals`.
- Final truth in `paper_review_outcomes`.
- Dashboard metrics based on submissions/approvals/outcomes.

Why it changed:

The slot workflow was too heavy for the team's operational reality. The project needed faster throughput: every active labeler should see available useful papers, and a paper should leave the visible queue as soon as a real submission exists. However, final truth still needed reviewer control, so Arciel approval remained the final gate.

How it was implemented:

- Legacy slot tables are preserved for audit: `reviewer_slots`, `paper_slot_assignments`, `paper_user_assignments`, `paper_assignment_submissions`.
- Conflict tables/view are preserved for the old model: `paper_conflicts`, `paper_conflict_resolutions`, `paper_conflict_candidates`.
- Current workflow uses `paper_label_submissions`, `paper_label_approvals`, and `paper_review_outcomes`.
- `get_general_queue_cards` excludes papers with final outcomes, pending/accepted submissions, open legacy assignments, or global no-data labels.
- Arciel's own submissions can auto-accept because Arciel has approver rights; non-Arciel submissions stay `pending_approval`.
- Approval view allows editing the final reviewer payload before approval while preserving the original submission.

Evidence:

- Reviewer workflow map: `crawl -> upload -> Small model -> Medium model -> Strong model -> human_review_ready -> paper_label_submissions -> Arciel approval -> paper_label_approvals -> paper_review_outcomes -> feedback learning`.
- Current schema/RPC file: `migration.sql`.
- Current views: `QueueView.jsx`, `ApprovalView.jsx`, `DashboardView.jsx`.

### 9.5 PDF Evidence Viewer, Highlighting, and Source Navigation

**When:** Initial PDF viewer in March; intensive highlighting work from 2026-04-22 through 2026-06-05.
**Credit:** Ayşegül for frontend PDF/highlight UX ownership; Arciel for later evidence-source integration, caching, page-hint fixes, and source-URL delivery; Huan for continuous scroll contribution.
**Technology:** PDF.js/react-pdf, browser text-layer rendering, geometry heuristics, Cache Storage API, localStorage LRU, Supabase dedup cache, Vercel serverless PDF proxy.

What was built:

- Browser PDF viewer.
- Continuous scrolling.
- Clickable nutrient marks.
- Nutrient popover insertion into food item rows.
- Evidence strip showing AI/source locations.
- Whole-table and whole-paragraph overlays.
- Deduped source chips for sources resolving to the same block.
- Coordinate-based overlay rendering.
- Printed-page to PDF-page mapping.
- Handling for over-range `page_hint`.
- Headless evidence scan and evidence-page-first rendering.
- Durable PDF byte cache and next-paper prefetch.

Why it was needed:

Reviewers cannot trust an AI-extracted nutrient value unless they can inspect the exact source evidence in the paper. Scientific PDFs do not expose semantic tables to the browser. The UI had to turn AI metadata like `table_label`, `page_hint`, and `source_quote` into visible, inspectable evidence.

How it was implemented:

- `PdfTextScanner.js` reconstructs document structure from positioned PDF.js text items. It groups rows, detects column gutters, classifies fragments, grows caption-anchored table regions, builds paragraph blocks, clips to dominant columns, and matches source quotes.
- `PdfViewer.jsx` renders pages, collects text contents, builds page highlight plans, transforms PDF coordinates into screen coordinates, and scrolls evidence into view.
- `EvidenceLocations.js` merges overlapping/duplicate source locations.
- Cached evidence status can be stored locally/remotely to avoid rescanning the same paper every time.
- `pdfCache.js` stores PDF bytes in browser Cache Storage and keeps an LRU index in localStorage.
- `/api/pdf` proxies source PDFs through same-origin Vercel when publisher CORS would block browser loading.

Why these technologies:

- PDF.js/react-pdf was already the practical browser standard for rendering PDFs.
- Client-side geometry avoided building a separate server-side layout extraction service.
- Cache Storage was chosen over normal HTTP cache because large PDFs and no-cache headers are unreliable for repeated reviewer loads.
- Source-URL PDFs were chosen over Supabase Storage to avoid free-tier storage and egress pressure.

Evidence:

- `PdfTextScanner.js`: 2,323 lines.
- `PdfViewer.jsx`: 939 lines.
- `EvidenceLocations.js`: 439 lines.
- PDF/evidence tests: `EvidenceLocations.test.js` (225), `PdfTextScanner.test.js` (655), `evidenceStatusCache.test.js` (92).
- Related commits: `6aba2f2`, `f383732`, `cce6945`, `63ac650`, `a683c49`, `8fb77f5`, `ad1b38b`, `398cc46`, `b1ab87b`, `662a5f8`, `faf5341`, `82b09b0`, `c875853`, `5a23ac3`, `3564c57`, `8e89198`, `dc855e4`, `7733205`, `27c44ae`, `ac8bf72`.

### 9.6 Autocomplete, Fuzzy Matching, and Search Telemetry

**When:** Initial autocomplete on 2026-03-03; fuzzy-match upgrade on 2026-05-09; telemetry and refinements through May.
**Credit:** Ayşegül for autocomplete UX/components; Huan for the reusable fuzzy-match engine; Arciel for catalog loading and telemetry integration.
**Technology:** React components, Supabase catalog queries, local in-memory ranking, debouncing, fuzzy token matching, search session logging.

What was built:

- Food autocomplete over canonical foods, aliases, base names, and custom input.
- Nutrient autocomplete with aliases, category filtering, units, and custom nutrient input.
- Fuzzy token utility for exact/derived/fuzzy/prefix matches.
- Whole-food preference heuristics.
- Local ranking when full catalog is loaded.
- Supabase fallback queries before catalog load completes.
- Search session logging for query/result/resolution telemetry.

Why it was needed:

Food and nutrient names are not simple strings. Reviewers must resolve "apple", "ash", "protein", "vitamin c", or paper-specific food names quickly without accidentally selecting a processed variant or wrong nutrient. The UI needed forgiving search but not unsafe overmatching.

How it was implemented:

- Huan's `fuzzyMatch.js` normalizes tokens, handles inflections, allows bounded edit distance, detects adjacent transpositions, and returns relation tiers.
- `FoodAutocomplete.jsx` layers domain scoring on top: exact/prefix/base/alias matches, penalties for processed variants, whole-food boosts, and custom entry fallback.
- `NutrientAutocomplete.jsx` mirrors nutrient-specific matching and unit display.
- `searchSessionLogger.js` records interaction telemetry and disables itself if the optional table is missing.

Evidence:

- `FoodAutocomplete.jsx`: 664 lines.
- `NutrientAutocomplete.jsx`: 334 lines.
- `fuzzyMatch.js`: 162 lines.
- `searchSessionLogger.js`: 110 lines.
- Huan commit: `e3971b2`.

### 9.7 Suggestions, Help Requests, Attachments, and Cockpit Review

**When:** Initial suggestion modal on 2026-03-02; Huan's full suggestion system 2026-04-21 to 2026-05-12; help/context integration later.
**Credit:** Huan for suggestion/review/attachment vertical; Ayşegül for frontend suggestion surface continuity; Arciel for integration with current workflow/help context.
**Technology:** React modal/view components, Supabase table, Supabase Storage, RLS/storage policies, signed URLs.

What was built:

- Suggestion modal for regular users.
- Suggestion review list for cockpit users.
- "My Suggestions" list for users to track status.
- `backlog_review_items` table.
- Private `suggestion-attachments` Storage bucket.
- Image attachment validation and upload.
- Signed URL retrieval for viewing private images.
- Help request path that stores paper/reviewer/AI/draft context for later review.

Why it was needed:

Labelers and stakeholders needed a way to report UI problems, suggest feature changes, or ask for help without interrupting the annotation workflow. Image attachments were needed because many issues are visual: PDF display, evidence highlighting, UI state, or confusing paper content.

How it was implemented:

- `SuggestionModal.jsx` validates files by MIME/type/size/count, sanitizes names, uploads to a user-scoped path, records metadata in `backlog_review_items.attachments`, and rolls back uploaded objects if the DB insert fails.
- RLS policies allow users to insert/read their own items while cockpit users can review/update.
- Storage policies constrain user access to their folder and keep the bucket private.
- Review views show status and image links through signed URLs rather than public bucket exposure.

Evidence:

- Huan commits: `2fcdc55`, `4db6334`, `ebe2a3d`, `bd29ab5`, `0a5fdd6`, `967c927`, `8dc6771`, `528848c`.
- `SuggestionModal.jsx`: 279 lines.
- `migration.sql`: `backlog_review_items`, `suggestion-attachments`, attachment RLS/storage policies.

### 9.8 Database Schema, RPCs, and Security

**When:** March to June 2026, with major workflow migrations in April/May.
**Credit:** Arciel.
**Technology:** Supabase Postgres, SQL, PL/pgSQL, JSONB, Row Level Security, `SECURITY DEFINER` functions, triggers, indexes.

What was built:

- Food/nutrient reference schema.
- Paper discovery and search audit schema.
- Human annotation schema.
- Reviewer/admin/profile schema.
- Legacy slot and conflict schemas.
- Current general submission/approval/outcome schema.
- AI extraction and stage-task schema.
- Pipeline/cockpit aggregate RPCs.
- Queue/card RPCs.
- RLS model for client roles and service role.

Why it was needed:

Every surface depends on a shared truth store. The database needed to protect private operational tables while exposing just enough data to labelers and cockpit users. It also needed to store immutable evidence: who submitted what, who approved/corrected it, how the AI routed the paper, and what crawler/search path found it.

How it was implemented:

- Idempotent migration style: `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, constraint drop/recreate guards, backfills, and `DO $$` blocks.
- RLS on 32 tables with policies for authenticated users, cockpit users, testers, approvers, and service role.
- `SECURITY DEFINER` RPCs expose safe queue/cockpit aggregates without direct client access to task internals.
- `claim_paper_stage_tasks` uses `FOR UPDATE SKIP LOCKED`, enabling concurrent workers to claim disjoint AI tasks.
- Payload builders normalize text, round numeric values, sort deterministically, and compute structural diffs.

Evidence:

- `migration.sql`: 5,396 lines.
- Object counts: 31 tables, 26 functions/RPCs, 75 policies, 69 indexes, 2 triggers.
- Core RPCs: `claim_paper_stage_tasks`, `get_general_queue_cards`, `get_cockpit_ai_extractions`, `get_pipeline_ops_snapshot`, `submit_general_label`, `approve_label_submission`.

### 9.9 AI Cascade and Model Worker

**When:** Gemini integration in April 2026; Gemma cascade in May; Flash-Lite middle stage on 2026-05-29; PDF-mode Gemini on 2026-05-31.
**Credit:** Arciel.
**Technology:** Python, Supabase client, Gemini/Gemma model APIs through the Google generative SDK path, `pdftotext`, JSON parsing, SHA-256, Postgres RPC task claiming.

What was built:

- Unified model prompt/contract for food-composition extraction.
- Three-stage cascade: Small model (Gemma), Medium model (Gemini Flash-Lite), Strong model (Gemini Flash).
- Data-driven stage configs in database.
- Text-mode and PDF-mode model input support.
- Deterministic payload normalization.
- Routing buckets and destinations.
- Follow-up priority scoring.
- Quota/rate-limit handling.
- Retry ceiling and failure taxonomy.
- Same-attempt fallback from Gemma 31B to 26B.
- Historical recovery and Flash-Lite experiment scripts.

Why it was needed:

Final extraction calls are scarce. A single expensive model over every candidate would be too slow and too costly. The cascade lets cheap/high-volume stages narrow the candidate pool before final extraction. It also creates a ranking mechanism: the system spends strong-model calls on the most promising papers, not the oldest paper in the queue.

How it was implemented:

- `UnifiedEvaluator` prompts the model for a strict JSON shape and evidence metadata.
- The parser accepts multiple JSON shapes to avoid infinite retries from harmless model formatting drift.
- `process_stage_queue.py` claims tasks atomically, fetches source PDFs, extracts text/page markers, builds model inputs, runs the evaluator, normalizes the result, stores `ai_extractions`, and enqueues follow-up stages or routes to human/provisional skip.
- `ai_routing.py` resolves IDs/names/aliases, standardizes units, rejects unsupported bases, groups/sorts rows, and stores rejection summaries.
- Stage configs specify thresholds, fallback models, next stages, no-data destination, and input mode.
- Worker errors are classified as quota, retryable, or non-retryable; quota requeues do not burn meaningful attempts.

Evidence:

- `unified_evaluator.py`: 687 lines.
- `ai_routing.py`: 842 lines.
- `process_stage_queue.py`: 1,560 lines.
- `test_ai_routing.py`: 2,469 lines.
- `test_pdf_page_markers.py`: 73 lines.
- README/AGENTS record production model roles and quotas.

### 9.10 Paper Discovery Crawler and Relevance Scoring

**When:** March crawler reorganization, late-March crawler v2/feedback hardening, May/June daily ops refinements.
**Credit:** Arciel.
**Technology:** Python, Europe PMC/OpenAlex/Semantic Scholar APIs, DergiPark local index support, urllib/curl, `pdftotext`, sentence-transformers embeddings, JSON manifests.

What was built:

- Multi-source paper discovery pipeline.
- Search task/query generation.
- Metadata search gate.
- Rich metadata relevance decision.
- Learned feedback score application.
- PDF acquisition and full-text validation.
- Canonical dedup and local state tracking.
- Per-run manifests with funnel counts and reasons.
- English and Turkish support, with current ops English-only.

Why it was needed:

The hardest upstream problem is not extracting data from a paper; it is finding papers likely to contain direct food-composition tables. The web is full of nutrition/food papers that are not useful for OpenNutri: intervention studies, biomarkers, animal feed, extracts, treatments, review articles, and one-off experimental formulations. The crawler had to use multiple signals and stay explainable.

How it was implemented:

- Search sources return metadata candidates.
- The first gate uses cheap lexical composition/food/nutrient/unit signals and soft penalties.
- The metadata decision adds embedding similarity, source priors, learned feedback n-grams, and concept/batch scores.
- The full-text validation gate checks the actual downloaded PDF text for table/composition/method/unit evidence.
- Negative phrases are penalties, not hard vetoes.
- The crawler pages live Supabase canonical keys to avoid refetching known papers.
- It records terminal states locally and writes accepted partial results when the wall-clock budget is reached.

Evidence:

- `crawler_v2.py`: 2,215 lines.
- `ranking.py`: 486 lines.
- `test_bilingual_pipeline.py`: 1,120 lines.
- Source adapters: `europe_pmc.py`, `search_sources.py`, `dergipark_source.py`.
- Docs record English-only current ops and DergiPark retained only when Turkish is explicitly re-enabled.

### 9.11 Feedback Learning

**When:** 2026-03-20 onward, refined after reviewer-truth workflow changes.
**Credit:** Arciel.
**Technology:** Python, Supabase REST, log-odds n-gram scoring, JSON config output.

What was built:

- Human-truth export from accepted `paper_review_outcomes`.
- Legacy fallback for older label events/global labels.
- Exclusion of pending/superseded submissions.
- Exclusion of AI-only truth from current learning.
- Good/bad/background document buckets.
- Title-only and title+abstract n-gram scoring.
- Query phrase and anchor phrase selection.
- Source priors, pair scores, batch scores, and concept scores.
- Generated feedback config loaded by crawler v2.

Why it was needed:

The crawler should learn from the labels. If reviewers consistently accept papers with certain phrases and reject papers with other phrases, that evidence should guide the next search/refill cycle. But it must learn only from resolved human truth, otherwise the AI would train on its own provisional choices.

How it was implemented:

- `update_terms.py` fetches papers, outcomes, search hits, batches, conflicts, and labels.
- It builds good/bad sets from `paper_review_outcomes.truth_source_kind='human_review'`.
- It computes smoothed log-odds for terms in good vs background and bad vs background.
- It stores net scores separately for title and title+abstract.
- It merges seed terms as soft priors, not permanent winners.
- The crawler reads weighted terms and applies them as additive scores only.

Evidence:

- `update_terms.py`: 1,219 lines.
- `feedback_terms.py`, `feedback_config.py`, `supabase_terms.py`.
- README documents that pending/superseded and AI-only outcomes do not feed learning.

### 9.12 Daily Ops Automation

**When:** April recursive daily ops loop; major hardening through May 2026; controller/worker split on 2026-05-29; bounded crawler runtime on 2026-06-04.
**Credit:** Arciel.
**Technology:** GitHub Actions, Python orchestrator, Supabase service role, Gemini API secrets, `poppler-utils`, pip dependency caching, GitHub concurrency groups.

What was built:

- Scheduled GitHub Actions tick every 5 minutes.
- Serialized refill controller.
- Five drain-only workers running in parallel.
- Manual dispatch worker count.
- Stage quota-day accounting.
- Interleaved Gemma/Flash-Lite/final Gemini draining.
- Stale task requeue.
- Active Gemma target counting from executable tasks.
- Bounded crawler chunks.
- JSON summaries in job logs.

Why it was needed:

The pipeline had to run without someone manually sitting at a laptop. GitHub Actions free runners can overlap, time out, or be cancelled. The architecture therefore separates the single writer/refill role from many safe drain workers, with the database claim RPC providing concurrency control.

How it was implemented:

- `.github/workflows/daily-ops.yml` runs `refill-controller` under `daily-ops-refill-controller` concurrency.
- A matrix of five workers runs in parallel and skips setup for inactive manual-dispatch worker numbers.
- Controller installs full crawler dependencies and may crawl/upload/refill.
- Workers install lighter requirements and never crawl/upload/refill.
- Both use env vars for credentials and model runtime controls.
- Workers claim tasks through `claim_paper_stage_tasks`, so overlapping matrices do not double-process rows.

Evidence:

- `.github/workflows/daily-ops.yml`: 148 lines.
- README daily ops section and AGENTS ops notes.
- `test_daily_ops.py`: 983 lines.

### 9.13 Storage, Egress, and Frontend Performance

**When:** May 30 to June 5, 2026, with earlier storage/upload decisions in April/May.
**Credit:** Arciel for storage/egress architecture and backend projection; Ayşegül for frontend performance UX ownership.
**Technology:** Supabase Postgres/Storage, Vercel serverless function, Cache Storage API, localStorage LRU, Vite-bundled PDF worker, lean Postgres RPCs.

What was built:

- Paper PDFs no longer stored in Supabase by default.
- `papers.pdf_url` is durable source URL for workers and browser.
- Same-origin PDF proxy for browser CORS issues.
- Durable browser PDF cache and prefetch.
- Self-hosted PDF.js worker instead of CDN dependency.
- Queue loaded via lean `get_general_queue_cards`.
- Cockpit data lazy-loaded only when cockpit tab opens.
- Useful Papers AI list uses `get_cockpit_ai_extractions`, not raw `ai_extractions.select('*')`.

Why it was needed:

Supabase free-tier storage and egress were real constraints. Raw AI responses are large, and PDFs are large. The app needed to avoid downloading unnecessary rows and avoid storing paper PDFs in Supabase unless explicitly required.

How it was implemented:

- `upload_to_supabase.py` uses `OPENNUTRI_STORE_PDFS_IN_SUPABASE=0` by default and preserves `pdf_url`.
- `process_stage_queue.py` fetches source PDFs on demand.
- `api/pdf.js` proxies PDF requests for CORS.
- `pdfCache.js` stores bytes in Cache Storage and keeps a local LRU.
- `Annotate.jsx` loads queue/profile in parallel, lazy-loads cockpit, and fetches the food catalog during idle time.
- `get_cockpit_ai_extractions` returns normalized payload and normalization summary only.

Evidence:

- Commits: `f8cad36`, `a6a7be7`, `68a4285`, `52bcd12`, `7733205`, `e15356e`, `9d0fbc0`, `390c162`, `376d687`, `ac8bf72`.
- README records measured cockpit AI list egress reduction in the handoff state.

### 9.14 Tests and Validation Infrastructure

**When:** March to June 2026, expanding with each risky subsystem.
**Credit:** Arciel for test suite architecture; Ayşegül/Huan where tests cover their frontend behavior indirectly.
**Technology:** Node/Vite frontend tests, Python tests, Supabase schema-check scripts, `pandoc` doc export validation.

Current tracked test files:

| Test file | Lines | What it validates |
| --- | ---: | --- |
| `EvidenceLocations.test.js` | 225 | Evidence source merge/dedup behavior. |
| `PdfTextScanner.test.js` | 655 | PDF table/paragraph/evidence scanner behavior. |
| `evidenceStatusCache.test.js` | 92 | Evidence cache behavior. |
| `test_ai_routing.py` | 2,469 | AI normalization, routing, unit handling, priority/failure cases. |
| `test_bilingual_pipeline.py` | 1,120 | Crawler language/source/filter behavior. |
| `test_daily_ops.py` | 983 | Daily ops orchestration and quota/drain logic. |
| `test_pdf_page_markers.py` | 73 | PDF page marker injection. |
| Total | 5,617 | Focused regression suite for high-risk behavior. |

Why these tests matter:

- PDF highlighting, AI routing, crawler scoring, and daily ops are the most failure-prone parts of the project.
- Many bugs in this project are not syntax errors; they are routing/truth/permission regressions.
- The tests encode decisions that later agents must not accidentally undo, such as retry fairness, page markers, and scanner behavior.

### 9.15 Documentation and Project Management

**When:** March to June 2026.
**Credit:** Arciel primarily, with Huan/Ayşegül contributions reflected in their own feature docs and commits.
**Technology:** Markdown, DOCX/PDF export scripts, GitHub workflow docs, repo agent instructions.

What was built:

- README architecture and operations documentation.
- `AGENTS.md` standing instructions for future agents.
- `INSTRUCTIONS.md` startup/credential/workflow rules.
- Handoff state document.
- Reviewer workflow map.
- Reviewer SOP.
- Defense reports, midterm reports, decks, and work reports.
- Backlog maintenance.

Why it was needed:

The system changed quickly. Without state docs, future work would repeatedly re-derive or accidentally revert important decisions: general queue vs slots, source-URL PDFs, no hard-negative crawler vetoes, AI prefill behavior, tester read-only mode, and the three-stage cascade.

How it was implemented:

- README records active commands, architecture, secrets by env var name, daily ops, crawler, feedback, and deployment assumptions.
- AGENTS records standing rules and product truths for future coding agents.
- Handoff state records live ops audits and schema/model changes.
- Work reports are exported to DOCX for assessment.

## 10. Chronological Milestone Ledger

This is not every commit, but it records the major dated changes that define the project history. Full commit history remains the source of truth; this table is the assessment-readable version.

| Date | Commit(s) | Owner evidence | What changed | Why it mattered |
| --- | --- | --- | --- | --- |
| 2025-12-19 | `b63d1e0`, `969c902`, `fb33626` | ArcielB, Ayşegül | Repository initialized and push access verified. | Established shared project repository and access. |
| 2026-03-02 | `7c2d372`, `614a82c`, `6245a17` | Ayşegül (`origin/master`) | MVP annotator, Google OAuth, theme, forgot-password affordance, suggestion modal. | First usable human labeling app. |
| 2026-03-03 | `00fd645`, `8a29dcb` | Ayşegül (`origin/master`) | Flexible nutrients, autocomplete, PDF highlight redesign, dynamic PDF URLs. | Made annotation data entry practical for real food-composition papers. |
| 2026-03-09 | `8728564`, `ed58f87`, `76e2c06` | Arciel | Imported/reconciled prior codebase and archived Vercel production build. | Moved work into one recoverable repository. |
| 2026-03-15 | `24c1755`, `c859acb`, `e303f40` | Arciel | README and crawler reorganization; local keys ignored. | Clarified active app/service boundaries and reduced secret risk. |
| 2026-03-16 | `d3b528d`, `a5dcd89`, `0678cd4`, `5a15229` | Arciel | Feature explanation docs in English/Turkish and fuzzy suggestion notes. | Created assessment/user-facing explanation material. |
| 2026-03-16 | `cbf61ad`, `341b40e` | Huan | Centralized theme state and system preference handling. | Improved app-wide consistency and usability. |
| 2026-03-17 to 2026-03-19 | `c8ceca1`, `58f1a28`, `160aff0` | Arciel | Balanced crawler relevance gating and reject audit sampling. | Began moving paper discovery from ad hoc search to explainable scoring. |
| 2026-03-19 | `4e208a5` | Huan | Reset password route and recovery flow. | Fixed a real auth/user-access problem. |
| 2026-03-20 | `36eebe1`, `88af95c`, `3e4361d`, `ec8281e`, `87d162d` | Arciel | Label events, test mode, global no-data flow, optimistic skip UX. | Made reviewer actions auditable and safer to test. |
| 2026-03-20 | `e61583f`, `83191ff`, `8573bbb` | Arciel | Feedback term generation and auto-crawl stock refill. | Started the loop from labels back to discovery. |
| 2026-03-21 to 2026-03-22 | `3cbe7d9`, `5863d74`, `c4a695b` | Arciel | Field-aware feedback learning, language split, crawler search/filter refactor. | Made crawler relevance more maintainable and learnable. |
| 2026-03-30 | `46c5ac5`, `95ad659`, `fd9adf9`, `b895f8a`, `64f1adb`, `b03f801`, `6df1623` | Arciel | Annotator/crawler evidence handling, bounded Turkish crawl, DergiPark index, no hard-negative vetoes, query-batch feedback. | Shifted crawler from brittle rules to additive scoring and auditability. |
| 2026-03-31 to 2026-04-08 | `ee77ed4` through `e4ffe11`, `6f442b8`, `7f39f46` | Arciel | Midterm/defense reports and AI algorithm decks. | Produced formal project deliverables and explanation artifacts. |
| 2026-04-13 to 2026-04-14 | `e0c7254`, `0f7ff10`, `7988e51` | Arciel | Assignment-driven labeling workflow, reviewer admin cockpit, slot-level no-data. | First structured reviewer workflow beyond a single-user annotator. |
| 2026-04-19 to 2026-04-20 | `92fe454`, `b2f0254`, `e37c103`, `63221f8` | Arciel | Gemini triage/extraction, queue filtering fixes, workspace restoration. | Introduced AI pre-screen/extraction into the workflow. |
| 2026-04-21 | `2fcdc55`, `4db6334`, `fce3073` | Huan + Arciel integration | Suggestion review flow and merge with AI extraction features. | Added user/cockpit feedback workflow while integrating concurrent branches. |
| 2026-04-22 to 2026-04-24 | `c2bbffe`, `6aba2f2`, `f383732`, `cce6945`, `c007cb0`, `f57e244`, `a421215` | Arciel + frontend ownership | Read-only developer queues, PDF highlight stabilization, table detection, staged AI routing, standardized AI payloads. | Connected AI results to human review and strengthened evidence UX. |
| 2026-04-25 | `ebe2a3d`, `bd29ab5`, `0a5fdd6` | Huan | Suggestion completion docs, image attachment schema, image upload UI. | Completed the suggestion feature as a full-stack flow. |
| 2026-04-25 to 2026-04-26 | `949a265`, `90bb4d5`, `cd2d8ec`, `536cc47`, `b964fec` | Arciel | Recursive daily ops, Gemini reset pacing, retry-fair AI queue. | Turned AI processing into resumable automation. |
| 2026-04-26 | `4ade833` | Huan | Infinite PDF scrolling. | Improved reviewer reading flow. |
| 2026-04-27 | `9c25ed7`, `7adea28`, `4353549` | Arciel | Reviewer SOP/workflow map and DOCX exports. | Documented reviewer process for team use. |
| 2026-04-27 | `a979d3f`, `2121663`, `f54f2fb` | Huan | Conflict table/view/UI and CSS fix. | Added disagreement resolution for the earlier assignment model. |
| 2026-04-29 | `330a2b8`, `29896eb`, `4fb2063`, `e86307a` | Arciel | AI-prefilled reviewer verification and reviewer lane fixes. | Made AI output editable/verifiable by humans. |
| 2026-05-02 | `fc67b30`, `4068a33`, `4508adc` | Arciel | General approval queue, daily AI ops maximization, AI details restored. | Replaced slot-heavy workflow with shared queue plus approval. |
| 2026-05-03 | `87e827b`, `542de12`, `ff97c4f`, `cc039eb`, `864c555` | Arciel | Queue limited to AI-extracted useful data, provisional no-data handling, Gemma cascade. | Raised human queue precision and added high-volume screening. |
| 2026-05-07 | `21f8557`, `967c927` | Arciel + Huan | Labeler account access and suggestion visibility/status split. | Supported real team use. |
| 2026-05-08 to 2026-05-12 | `307d5cb` through `c15d0ff`, `8dc6771`, `528848c` | Arciel + Huan | Daily ops schedule/gemma fixes, English-only acquisition, retry caps, PDF size/timeouts, suggestion photo/dropdown fixes. | Stabilized unattended operations and suggestion review. |
| 2026-05-13 | `bc94d77`, `4108801`, `bb129ad`, `779c625`, `f68ca24`, `63ac650` | Arciel + frontend ownership | Parallel daily ticks, pipeline cockpit, reviewer UI polish, broad AI evidence highlighting. | Made ops visible and evidence review easier. |
| 2026-05-14 to 2026-05-16 | `582c34e`, `a683c49`, `8fb77f5`, `ad1b38b`, `398cc46`, `b1ab87b`, `662a5f8`, `faf5341`, `675feee`, `9de76ba`, `cf35755`, `36a8f97`, `82b09b0`, `c875853`, `5a23ac3` | Arciel + frontend ownership | Review UI polish, coordinate overlays, table/paragraph evidence snapping, helper/view refactor, dead evaluator removal, column-aware scanner fixes. | Hardened the most complex frontend subsystem and made code maintainable. |
| 2026-05-19 | `de13677`, `d671914`, `9f18a56` | Huan | Dual-login experiment/revert and developer/tester read-only visibility. | Preserved safe training/demo access without keeping a rejected login split. |
| 2026-05-20 | `3564c57`, `8e89198`, `dc855e4`, `0c1d334` | Arciel + Huan | Evidence dedup cache, paragraph/table fallback fixes, fuzzy backlog cleanup. | Improved evidence stability and closed autocomplete matching work. |
| 2026-05-27 to 2026-05-28 | `f6d1745`, `87e2a18`, `8ae2d8e`, `ca0e1db`, `928ff82`, `0c7c560`, `7062f03`, `5fe1bfd`, `e8aedc8` | Arciel | Same-run Gemma refill, auth allowlist hardening, guarded task claims, worker fanout, stale storage cleanup, queue counts from tasks, duplicate upload recovery, refill controller hardening. | Removed major live-ops failure modes. |
| 2026-05-29 | `fcccf8c`, `e4bc421`, `686fed8`, `8a1949d`, `0bc0d64`, `b1b8a8e` | Arciel | Gemini quota routing, drain workers decoupled from controller, Flash-Lite triage stage, three-stage Pipeline UI, medium-stage backfill. | Established the current three-stage cascade and visible ops funnel. |
| 2026-05-30 to 2026-05-31 | `f8cad36`, `a6a7be7`, `68a4285`, `52bcd12`, `7733205`, `27c44ae`, `938176c`, `bc93f8b`, `0011272` | Arciel + frontend ownership | Source-URL PDFs, CORS proxy, browser cache, journal page hint fix, PDF-mode Gemini, Gemma text-mode decision documented. | Solved storage/egress pressure and evidence page-number reliability. |
| 2026-06-04 to 2026-06-05 | `e15356e`, `9d0fbc0`, `390c162`, `376d687`, `43d3d60`, `ac8bf72` | Arciel + frontend ownership | Lazy cockpit, self-hosted PDF worker, egress reduction, durable PDF cache, one-RPC queue, bounded crawler runtime, evidence-first rendering. | Made the app and daily ops faster and less fragile. |
| 2026-06-05 | `fd1b930`, `bf89977`, `1a8d1cf`, `6607ac9` | Arciel | Work reports v1/v2 and frontend report deepening. | Created assessment artifacts and corrected attribution evidence. |

## 11. Evidence Commands Used for This Expanded Version

The key reproducible commands were:

```text
git fetch origin
git rev-list --left-right --count main...origin/main
git shortlog -sne --all
git log --all --author=<author> --format= --numstat -- ...exclusions...
git ls-files ... | wc -l
wc -l <key files>
rg -n <schema/RPC/policy/model/crawler evidence>
pandoc -t plain <report.md> | wc -w
pandoc <report.md> -o <report.docx>
unzip -p <report.docx> word/document.xml
```

The important limitation is equally explicit: the report is evidence-backed from source, history, docs, tests, and key implementation files, but it is not a claim that every tracked line in USDA dumps, generated documents, or every retained legacy file was read end to end.
