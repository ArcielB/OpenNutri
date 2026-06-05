# OpenNutri Work Report - MASTER CODEX FINAL

Prepared: 2026-06-05
Source snapshot used for current-code evidence: `0713a03b1766075f62f5093ab75a933942d99a60`
Historical base merged from: `docs/defense/OpenNutri_Work_Report_MASTER_FINAL.md`
Current implementation evidence merged from: `docs/defense/OpenNutri_Current_Code_Work_Report.md`
Rule for conflicts: current `HEAD` implementation wins over older prose.

## 1. Purpose and Method

This report is the assessment-facing master ledger for OpenNutri. It combines:

- Historical framing, contributor attribution, and timeline from `OpenNutri_Work_Report_MASTER_FINAL.md`.
- Exact current-code evidence from `OpenNutri_Current_Code_Work_Report.md`.
- Current tracked source at `0713a03b1766075f62f5093ab75a933942d99a60`.

The report is intentionally detailed but deduplicated. Each subsystem has one canonical technical entry. Timeline and contributor sections summarize and point back to the technical ledger instead of repeating every subsystem explanation.

Methodology:

- `git fetch origin` was run before evidence collection.
- `HEAD...origin/main` was `0 0`, so local `main` matched `origin/main`.
- The working tree contained unrelated untracked local artifacts; they were ignored.
- Metrics use tracked active source only, excluding datasets, generated media, legacy archive, build output, local data, generated feedback JSON, lockfiles, and prior work reports.
- Contributor evidence uses all refs because Aysegul's original MVP/frontend commits are on `origin/master`.

## 2. What OpenNutri Is

OpenNutri is a scientific-paper discovery and expert-labeling system for food composition data. Its target is narrow: direct composition values measured in real foods or stable food products, mapped to food/nutrient/value/unit/basis data that can support food composition datasets, diet tracking, food exporters, inspection, or similar real-world data use.

It is not a generic nutrition app, not a chatbot, and not a broad biomedical-paper classifier. Papers about effects of nutrients, supplements, extracts, diets, processing treatments, microbes, animals, biomarkers, sensory outcomes, disease outcomes, or one-off experimental formulations are empty unless they also report direct food/product composition tables useful to OpenNutri.

Current end-to-end workflow:

```text
USDA reference foods/nutrients
  -> scientific-paper crawler
  -> metadata relevance scoring
  -> PDF acquisition and validation
  -> Gemma screening
  -> Gemini Flash-Lite triage
  -> Gemini final extraction
  -> normalized DB-compatible payload
  -> shared human queue
  -> labeler submission
  -> Arciel approval/correction
  -> final paper_review_outcomes truth
  -> feedback learning for the next crawler run
```

## 3. Current Evidence Metrics

### 3.1 Source Lines

| Bucket | Lines | Files |
| --- | ---: | ---: |
| Backend, ops, schema | 31,511 | 88 |
| Frontend | 14,061 | 53 |
| Active docs | 5,191 | 23 |
| Proposal appendix docs | 971 | 9 |
| Other active | 24 | 1 |
| Total active tracked text/source | 51,758 | 174 |

### 3.2 Key Current Files

| File | Lines | Role |
| --- | ---: | --- |
| `apps/expert-annotator/migration.sql` | 5,396 | Schema, RLS, RPCs, workflow engine. |
| `services/data-pipeline/scripts/daily_ops_orchestrator.py` | 2,358 | Daily controller/drain tick orchestration. |
| `apps/expert-annotator/src/utils/PdfTextScanner.js` | 2,323 | PDF text/evidence scanner. |
| `services/data-pipeline/food_paper_crawler/crawler_v2.py` | 2,215 | Multi-source crawler. |
| `services/data-pipeline/scripts/process_stage_queue.py` | 1,560 | AI queue worker. |
| `services/data-pipeline/food_paper_crawler/feedback/update_terms.py` | 1,219 | Human-truth feedback learning. |
| `apps/expert-annotator/src/pages/Annotate.jsx` | 1,163 | Main frontend orchestrator. |
| `apps/expert-annotator/src/components/PdfViewer.jsx` | 939 | PDF rendering/overlay/caching UI. |
| `services/data-pipeline/ai_routing.py` | 842 | Routing and deterministic normalization. |
| `services/data-pipeline/evaluator/unified_evaluator.py` | 687 | Shared model evaluator/prompt/parser. |
| `.github/workflows/daily-ops.yml` | 148 | Scheduled ops workflow. |

### 3.3 Schema Object Counts

| Object type | Count |
| --- | ---: |
| Tables | 31 |
| Functions/RPCs | 26 |
| RLS policies | 75 |
| RLS-enabled tables | 32 |
| Indexes | 69 |
| Triggers | 2 |
| Views | 1 |
| `SECURITY DEFINER` functions | 22 |
| Storage policies | 4 |

### 3.4 Tests

Tracked test files total 5,898 lines. The focused current regression suite is 5,617 lines across AI routing, daily ops, bilingual crawler behavior, PDF page markers, PDF evidence matching, evidence location grouping, and evidence cache behavior.

Most important test files:

- `services/data-pipeline/tests/test_ai_routing.py` (2,469 lines).
- `services/data-pipeline/tests/test_bilingual_pipeline.py` (1,120 lines).
- `services/data-pipeline/tests/test_daily_ops.py` (983 lines).
- `apps/expert-annotator/src/utils/PdfTextScanner.test.js` (655 lines).
- `apps/expert-annotator/src/utils/EvidenceLocations.test.js` (225 lines).

### 3.5 Contributor Evidence

All-ref commit counts:

| Git author | Commits |
| --- | ---: |
| `baezarciel` | 214 |
| `landeryt` | 24 |
| `ayseguldogan2706-cpu` | 7 |
| `ArcielB` | 1 |

Active-source-filtered churn:

| Author | Added | Deleted | Notes |
| --- | ---: | ---: | --- |
| `baezarciel` | 65,478 | 15,904 | Backend, schema, ops, documentation, integration, much current app evolution. |
| `ayseguldogan2706@example.com` | 3,185 | 88 | Active-source MVP/frontend lines on all refs; raw all-ref additions are 6,624 with `package-lock.json`. |
| `mcraft160105@gmail.com` | 2,188 | 582 | Huan's direct commits. |
| `ArcielB` | 1 | 0 | Initial README commit. |

Attribution caveat: a current-main-only view under-credits Aysegul because original frontend commits are on `origin/master` and were later imported/reorganized. This report therefore separates git-author evidence from subsystem ownership.

## 4. Timeline

| Phase | Dates | Main work |
| --- | --- | --- |
| Bootstrap | 2025-12-19 | Repository creation and initial access. |
| MVP annotator | 2026-03-02 to 2026-03-09 | Original React/Vite/Supabase annotator, login, PDF view, food/nutrient form, Google OAuth, theme/suggestion/reset-password basics. |
| Import and reorganization | 2026-03-09 to 2026-03-16 | Codebase moved into `apps/` and `services/`, README and structure stabilized. |
| Feedback/crawler hardening | 2026-03-19 to 2026-03-30 | Label events, test mode, feedback term export, bilingual crawler split, DergiPark index path, additive no-hard-veto ranking. |
| Reviewer workflow and AI routing | 2026-04-13 to 2026-04-29 | Assignment workflow, reviewer admin, Gemini extraction, suggestion review, conflict system, AI prefill. |
| General approval queue | 2026-05-02 to 2026-05-09 | Slot workflow replaced by shared general queue plus Arciel approval; normalized AI `has_data` became queue gate. |
| Daily ops and cockpit | 2026-05-11 to 2026-05-20 | Retry-fair AI queue, quota-draining automation, pipeline cockpit, useful-paper details, PDF source strips, app refactor into views/helpers. |
| Three-stage cascade and source-URL PDFs | 2026-05-27 to 2026-05-31 | Auth allowlist hardening, Gemma -> Flash-Lite -> Gemini cascade, controller/drain-worker fan-out, source-URL PDF storage strategy. |
| Performance and defense package | 2026-06-04 to 2026-06-05 | Lean queue RPC, lazy cockpit data, self-hosted PDF worker, durable PDF cache, evidence-first rendering, master/current code reports. |

## 5. Canonical Technical Ledger

### 5.1 React/Vite Expert Annotator

**Primary files:** `apps/expert-annotator/src/pages/Annotate.jsx`, `src/views/*.jsx`, `src/components/*.jsx`, `src/utils/annotateHelpers.js`, `src/utils/testMode.js`.

**What was built:** a full expert-labeling app with login, reviewer-profile sync, shared general queue, AI-prefilled editable rows, draft/final/no-data submission, help requests, approval page, dashboard, useful-paper cockpit, pipeline cockpit, reviewer admin, suggestions, and role-specific suggestion tracking.

**Why it was needed:** OpenNutri's data quality depends on humans verifying AI-extracted rows against source PDFs. The UI had to make that efficient without exposing AI reasoning or other labelers' work to ordinary labelers.

**How it works:** `Annotate.jsx` calls `sync_reviewer_profile`, loads queue cards through `get_general_queue_cards`, silently builds form rows from `latest_ai_extraction.normalized_payload_json`, saves rows to `annotations`/`food_items`/`annotation_nutrient_values`, records `paper_label_events`, and calls `submit_general_label` for immutable submissions. The Approval view writes a reviewer annotation and calls `approve_label_submission` to store final truth.

**Technologies:** React 19, Vite 7, Supabase JS 2.x, React PDF/PDF.js, plain CSS, ESLint 9.

**Hard parts solved:**

- Queue load was collapsed to one lean RPC.
- Cockpit data is lazy-loaded because papers and AI summaries are heavy.
- Useful Papers uses `get_cockpit_ai_extractions` rather than `select('*')`.
- Tester accounts remain read-only.
- AI prefill initializes empty annotations without overwriting existing drafts.
- Final `has_data` requires at least one food and one nutrient row.
- Suggestions/help requests store context and attachment metadata.

**Validation:** frontend tests cover the high-risk PDF/evidence utilities; frontend build/lint are the normal validation commands, though this report task did not change frontend code.

### 5.2 PDF Evidence Scanner and Viewer

**Primary files:** `PdfViewer.jsx` (939), `PdfTextScanner.js` (2,323), `EvidenceLocations.js`, `EvidenceStrip.jsx`, `useEvidenceStatusCache.js`, `pdfCache.js`.

**What was built:** a PDF evidence navigation engine with source chips, table/paragraph/page matching, printed-page mapping, coordinate overlays, headless page scanning, durable PDF cache, and table-scoped nutrient click highlights.

**Why it was needed:** the model and human payloads store broad source metadata, not exact coordinates. Reviewers need to locate the table or paragraph quickly in arbitrary publisher PDFs.

**How it works:** PDF bytes load through Cache Storage and render via `react-pdf`. The viewer scans text content for every page before rendering every canvas. `PdfTextScanner` reconstructs rows, gutters, table captions, table regions, paragraph blocks, and source-quote matches from PDF.js text items. Evidence statuses merge into source chips, and matched regions draw overlays.

**Technologies:** PDF.js/react-pdf, browser Cache Storage, localStorage, Supabase-backed dedup storage.

**Hard parts solved:**

- PDF text items are converted into table/paragraph-like structure.
- Source rows in one table/paragraph deduplicate to one chip/overlay.
- Printed journal page numbers are mapped when detected.
- Impossible page hints do not block content matching.
- Caption fallback gives a target even when table body detection fails.
- Evidence pages render early to reduce blank auto-jumps.

**Known gaps:** cross-text-item nutrient click highlighting and difficult continuation-page tables remain future work.

### 5.3 Supabase Schema, RLS, and RPC Workflow

**Primary file:** `apps/expert-annotator/migration.sql` (5,396).

**What was built:** the Postgres contract for reference data, paper discovery, annotation rows, reviewer profiles, general queue submissions, approvals, review outcomes, AI routing, suggestions, storage policies, RLS, and security-definer RPCs.

**Why it was needed:** multiple roles need different read/write powers over the same data. The database must enforce truth boundaries, not leave them only to the frontend.

**How it works:** tables model reference foods/nutrients, papers/search hits, annotations, immutable submissions, final approvals, and AI tasks/extractions. RLS policies and role predicate functions enforce labeler, cockpit, tester, approver, service-role, and auth-hook boundaries. Security-definer RPCs expose safe aggregates and mutations.

**Technologies:** Supabase Postgres, PostgreSQL SQL/PLpgSQL, RLS, security-definer functions, Supabase Auth hooks, Storage policies.

**Hard parts solved:**

- `claim_paper_stage_tasks` uses `FOR UPDATE SKIP LOCKED` for parallel worker safety.
- `submit_general_label` freezes original labeler payloads.
- `approve_label_submission` writes corrected final truth and diff.
- `build_annotation_submission_payload` and Python normalization produce hash-comparable payloads.
- `allowed_auth_emails` is private and checked by an auth hook, not by frontend reads.
- Tester write-blocking is centralized through `current_user_can_write()`.

**Known gaps:** the one-file convergent migration is large; live DB verification is required when it changes. This report did not change it.

### 5.4 AI Cascade and Deterministic Normalization

**Primary files:** `ai_routing.py` (842), `unified_evaluator.py` (687), `process_stage_queue.py` (1,560), `recover_gemini_candidates.py` (446), `flash_lite_triage_experiment.py` (245).

**What was built:** a three-stage AI routing system: Gemma screening, Gemini Flash-Lite triage, and Gemini final extraction. Every stage uses a shared evaluator contract and a deterministic normalizer before routing.

**Why it was needed:** final extraction calls are scarce. The cascade lets the system rank a large paper pool and spend the strongest model on the top candidates.

**How it works:** workers claim stage tasks, fetch PDFs from `papers.pdf_url`, extract text with `pdftotext`, inject PDF page markers, attach native PDF bytes for PDF-mode stages, run `UnifiedEvaluator`, normalize rows into the human payload shape, store `ai_extractions`, enqueue the next stage or route/finalize/provisional-skip the paper.

**Technologies:** Python, Google Generative AI SDK, Gemma/Gemini models, Poppler `pdftotext`, Supabase service-role client, PostgreSQL RPC queue.

**Hard parts solved:**

- One prompt defines useful food-composition data and explicit non-scope cases.
- Parser salvages Markdown-fenced, embedded, top-level-array, one-object-array, and nested food/nutrient shapes.
- Strict unit/basis normalization keeps final payloads DB-compatible.
- ID-first then exact/alias matching prevents stale or mismatched model IDs.
- Raw-positive Gemma rescue avoids dropping likely positives when final normalization is empty.
- Priority scoring makes each stage process top-ranked candidates.
- Quota errors requeue without consuming meaningful attempts.
- Retryable Gemma failures can use 26B fallback in the same task attempt.
- Non-retryable model config errors fail fast instead of looping.

**Validation:** `test_ai_routing.py` is the main specification for normalization, JSON parsing, routing buckets, thresholds, priority scoring, retry classification, upload/requeue behavior, and feedback truth exclusion.

**Known gaps:** model behavior can drift; strict normalization rejects some non-per-100g data; text-mode Gemma does not handle image-only PDFs.

### 5.5 Crawler v2 and Relevance Ranking

**Primary files:** `crawler_v2.py` (2,215), `ranking.py` (485), `search_sources.py` (280), `europe_pmc.py` (180), `dergipark_source.py` (687), `models.py`.

**What was built:** a staged crawler with search, metadata filter, PDF acquisition, PDF validation, source adapters, query-batch accounting, terminal state, and manifest output.

**Why it was needed:** the system needs fresh candidate papers, but raw nutrition literature has many false positives. Downloading every PDF would be too slow and noisy.

**How it works:** source adapters fetch metadata from Europe PMC/OpenAlex/Semantic Scholar, with DergiPark retained for Turkish. The search gate and metadata filter use additive positive signals and soft penalties. Candidates that pass metadata filtering are downloaded, size-checked, extracted with `pdftotext`, and validated for table/food/nutrient/unit evidence.

**Technologies:** Python, source web APIs, Poppler, sentence-transformers embeddings, local JSON state/manifests.

**Hard parts solved:**

- Negative evidence is a soft penalty, not a hard veto.
- Query batches are tracked separately from hit evidence.
- Crawler wall-clock limits produce partial accepted manifests.
- Live Supabase `canonical_key` rows prevent re-download of already routed papers.
- Oversized PDFs are rejected before upload/storage pressure.
- Publisher HTML, nested PDFs, curl fallback, and PMC proof-of-work cases are handled.

**Known gaps:** current ops are English-only; the Turkish path is retained but inactive by default. Precision-first ranking may miss subtle useful papers.

### 5.6 Feedback Learning

**Primary file:** `feedback/update_terms.py` (1,219).

**What was built:** a human-truth feedback exporter that creates language-specific query phrases, anchor phrases, weighted n-grams, source priors, batch scores, pair scores, and concept scores.

**Why it was needed:** the crawler should learn which phrases, sources, batches, and concepts lead to accepted human truth.

**How it works:** the script reads `paper_review_outcomes` first and only includes `truth_source_kind = human_review`. It excludes AI-model outcomes, pending/superseded submissions, and conflicts. It falls back to legacy label events only for older unresolved papers. It scores title and title+abstract n-grams with smoothed log odds and writes `feedback/latest.json`.

**Technologies:** Python, Supabase REST, language-scoped term extraction, JSON config.

**Hard parts solved:**

- Human truth is separated from model provenance.
- Query-batch scores reflect bounded search batches rather than raw source result volume.
- English and Turkish feedback pools are separate.

**Known gaps:** L2 classifier training is still deferred pending more human labels.

### 5.7 Daily Ops Automation

**Primary files:** `.github/workflows/daily-ops.yml` (148), `daily_ops_orchestrator.py` (2,358), `process_stage_queue.py`.

**What was built:** a resumable GitHub Actions tick system with one serialized refill controller and five parallel drain-only workers.

**Why it was needed:** OpenNutri runs within provider quota and GitHub job limits. Frequent small ticks are safer than one long daily run.

**How it works:** every five minutes, the controller may requeue stale tasks, count quota-day completions, and top up bounded Gemma work. Workers drain queued tasks only, interleaving Gemma, Flash-Lite, and final Gemini within daily targets. All task coordination goes through Supabase Postgres.

**Technologies:** GitHub Actions, Python 3.11, Supabase, Poppler, GitHub secrets, requirements split between full crawler and lightweight worker.

**Hard parts solved:**

- Controller is the only scheduled crawler/uploader.
- Workers never crawl/upload/refill.
- Worker matrices can overlap safely because task claiming is atomic.
- Gemma and Gemini-family stages use separate quota-day timezones.
- `OPENNUTRI_STORE_PDFS_IN_SUPABASE=0` avoids paper Storage growth.
- Worker dependencies exclude crawler-heavy `sentence-transformers`.

**Known gaps:** source APIs and model quota can still stop ticks; GitHub job timeout constrains crawler refill.

### 5.8 Source-URL PDF Strategy

**Primary files:** `upload_to_supabase.py`, `api/pdf.js`, `pdfCache.js`, daily workflow.

**What was built:** a default no-paper-storage strategy. Paper rows keep durable source `pdf_url`; workers and annotator fetch from the source URL; Supabase Storage upload is opt-in only.

**Why it was needed:** paper PDF storage and egress can exceed free-tier limits quickly. Source-URL/on-demand keeps Supabase focused on metadata, labels, routing, and suggestion attachments.

**How it works:** upload persists `pdf_url`, skips Storage unless `OPENNUTRI_STORE_PDFS_IN_SUPABASE=1`, and still records search hits/batches. The frontend routes external PDFs through `/api/pdf` to handle CORS and cache headers, then stores bytes in browser Cache Storage.

**Known gaps:** source URLs can disappear or block access. That trade-off is currently accepted to control storage/egress.

### 5.9 Suggestions, Help Requests, and Huan's Full-Stack Work

**Primary files:** `SuggestionModal.jsx`, `SuggestionsReviewView.jsx`, `MySuggestionsView.jsx`, `HelpRequestModal.jsx`, `migration.sql` suggestion/storage policies.

**What was built:** labelers can submit suggestions and help requests; cockpit/admin users triage them; image attachments are stored privately and opened through signed URLs.

**Why it was needed:** reviewers need a structured path to report confusing papers, UI problems, data issues, and attachment-backed feedback without using an external tracker.

**How it works:** `SuggestionModal` validates MIME type, max image count, max file size, and duplicate files. It uploads files to a user-scoped path, inserts `backlog_review_items`, and removes uploaded objects if the insert fails. Help requests insert the same table with general-queue context.

**Technologies:** React, Supabase Storage, RLS storage policies, Supabase table writes.

**Hard parts solved:** upload rollback, per-user storage containment, role split between submitter and cockpit reviewer, test-mode local events.

### 5.10 Autocomplete and Fuzzy Matching

**Primary files:** `FoodAutocomplete.jsx`, `NutrientAutocomplete.jsx`, `fuzzyMatch.js`, `searchSessionLogger.js`.

**What was built:** food and nutrient search components with exact/prefix/token/fuzzy ranking, custom rows, keyboard navigation, debounced search logging, and local/Supabase fallback behavior.

**Why it was needed:** food and nutrient names vary across papers and USDA references. Reviewers need fast search but must also be able to enter custom rows.

**How it works:** Huan's `fuzzyMatch.js` provides normalization, token relations, inflection handling, banded Levenshtein, and transposition support. Food/nutrient components add domain-specific scoring and penalties.

**Technologies:** React, Supabase, custom JS fuzzy matching.

**Known gaps:** weights are hand-tuned constants rather than learned ranking.

### 5.11 ETL and Reference Data

**Primary files:** `etl_usda_to_opennutri.py`, `etl_sr_legacy_to_opennutri.py`, `create_opennutri_schema.sql`.

**What was built:** utilities to seed canonical foods, aliases, nutrients, sources, and claims from USDA FoodData Central datasets.

**Why it was needed:** the AI normalizer and UI autocomplete require a reference food/nutrient layer, and OpenNutri needs known reference claims for comparison and future data integration.

**How it works:** CSV rows are transformed into OpenNutri tables and upserted through Supabase REST. SR Legacy uses deterministic UUIDv5 IDs for stable reruns.

**Known gaps:** these loaders are practical project utilities, not a polished general ETL platform.

## 6. Contributor Assessment

### 6.1 Arciel Aliognis Baez Zamora

**Git evidence:** `baezarciel` 214 commits plus `ArcielB` initial commit; active-source-filtered churn `+65,478/-15,904`.

**Assessment-facing contribution:**

- Built the Supabase schema/RLS/RPC contract.
- Built the general queue, approval workflow, final truth model, and cockpit RPCs.
- Built the crawler v2, relevance scoring, source adapters, upload/registration, and feedback learning path.
- Built the AI cascade, deterministic normalization, routing buckets, priority scoring, fallback/retry/quota behavior, and recovery tools.
- Built daily ops controller/drain worker automation and source-URL PDF strategy.
- Performed major integration, live ops hardening, documentation, and project management.

**Best evidence files:** `migration.sql`, `ai_routing.py`, `unified_evaluator.py`, `process_stage_queue.py`, `daily_ops_orchestrator.py`, `crawler_v2.py`, `ranking.py`, `update_terms.py`, `.github/workflows/daily-ops.yml`, README/AGENTS/handoff docs.

### 6.2 Aysegul Dogan

**Git evidence:** 7 all-ref commits on `origin/master`/history; active-source-filtered churn `+3,185/-88`, raw all-ref additions `+6,624` including `package-lock.json`.

**Attribution caveat:** current `main` under-represents her because original MVP/frontend commits were imported/reorganized later. The assessment should credit her for the original user-facing frontend foundation and the annotator surfaces established there, while recognizing that later mainline evolution was heavily integrated by Arciel.

**Assessment-facing contribution:**

- Original React/Vite/Supabase annotator MVP.
- Login and Google OAuth user flow.
- Early annotation workspace and PDF viewing.
- Flexible food/nutrient forms and autocomplete-facing UI.
- Early PDF highlighting work.
- Light/dark theme, forgot-password, and suggestion feedback surfaces in the MVP line.

**Best evidence commits:** `7c2d372`, `614a82c`, `6245a17`, `00fd645`, `8a29dcb` on `origin/master`.

### 6.3 Duc Huan Ngo

**Git evidence:** `landeryt` 24 commits; active-source-filtered churn `+2,188/-582`.

**Assessment-facing contribution:**

- Built reusable fuzzy matching infrastructure now used by food/nutrient autocomplete.
- Built suggestion attachment flow with validation, storage paths, rollback behavior, and role-aware review surfaces.
- Fixed reset-password behavior by handling Supabase recovery sessions and URL hash tokens correctly.
- Added legacy conflict-resolution infrastructure later superseded by the general approval queue.
- Contributed theme handling, infinite PDF scroll behavior, developer/tester read visibility, and UI polish.

**Best evidence files:** `fuzzyMatch.js`, `SuggestionModal.jsx`, `ResetPassword.jsx`, suggestion/storage SQL policies, conflict-resolution schema/view/UI history.

## 7. Hardest Engineering Problems

1. **PDF evidence reconstruction.** PDF.js exposes glyphs and text items, not semantic tables. OpenNutri reconstructs enough table/paragraph/page structure for reviewable overlays.
2. **AI output determinism.** LLM rows are free-form; OpenNutri converts them into hash-comparable human payloads with strict units, evidence metadata, custom rows, and stable ordering.
3. **Quota-aware automation.** The daily workflow makes progress through short resumable ticks, stage-specific quotas, retry-fair task ordering, and DB-atomic parallel worker claims.
4. **Security across roles.** Labelers, approvers, cockpit viewers, testers, service workers, and signup hooks all need different access. The database, not only the UI, enforces the boundaries.
5. **Learning without corrupting truth.** Feedback reads final human outcomes, excludes pending/superseded submissions and AI-model outcomes, and turns accepted labels into soft crawler scoring.
6. **Storage/egress control.** Source-URL PDFs, slim AI cockpit projections, lazy cockpit loading, PDF browser cache, and queue-card RPCs are all responses to real free-tier constraints.

## 8. Current Limitations / What Not To Claim

- Do not claim Turkish/DergiPark is active in current daily ops. It is retained but defaults are English-only.
- Do not claim the model has final human authority. Reviewer-led `paper_review_outcomes` are the final active truth.
- Do not claim AI-model outcomes train feedback. They are excluded from human-truth feedback.
- Do not claim paper PDFs are stored in Supabase by default. They are source-URL/on-demand by default.
- Do not claim the PDF highlighter perfectly reconstructs every table or OCR case.
- Do not claim L2 classifier training is complete. It is deferred.
- Do not claim raw model reasoning is loaded in default cockpit lists. The current design intentionally avoids it.
- Do not claim this report changed runtime behavior. The report task is documentation-only.

## 9. Validation Plan for This Artifact

The Markdown report is intended to be exported to DOCX and checked with:

- `pandoc docs/defense/OpenNutri_Work_Report_MASTER_CODEX_FINAL.md -o docs/defense/docx/OpenNutri_Work_Report_MASTER_CODEX_FINAL.docx`
- `pandoc docs/defense/OpenNutri_Work_Report_MASTER_CODEX_FINAL.md -t plain | wc -w`
- `unzip -p docs/defense/docx/OpenNutri_Work_Report_MASTER_CODEX_FINAL.docx word/document.xml`
- `git diff --check`
- `git diff --cached --check`
