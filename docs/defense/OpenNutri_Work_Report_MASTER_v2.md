# OpenNutri Work Report v2 - Master Ledger

Prepared: 2026-06-05
Repository snapshot: `1a8d1cf0394d2c86ba31604888969c30a9a47d32` (`main`, even with `origin/main`)
Activity span in git: 2025-12-19 to 2026-06-05
Scope: documentation-only report package. No application API, schema, frontend behavior, deployment configuration, database state, or live service was changed.

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
