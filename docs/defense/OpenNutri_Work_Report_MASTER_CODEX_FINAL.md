# OpenNutri Work Report - MASTER CODEX FINAL

Prepared: 2026-06-05
Corrected: 2026-06-05
Current source snapshot used for code evidence: `0713a03b1766075f62f5093ab75a933942d99a60`
Corrected after docs-only commit: `ef213e7454d7dc61d1cd91506448707e59d18910`
Historical base preserved from: `docs/defense/OpenNutri_Work_Report_MASTER_FINAL.md`
Current implementation evidence preserved from: `docs/defense/OpenNutri_Current_Code_Work_Report.md`
Rule for conflicts: current implementation evidence from the `0713a03b1766075f62f5093ab75a933942d99a60` source snapshot wins over older historical prose.

## Correction Note

The first Codex-final draft was too short because it summarized the historical master report instead of preserving it. This corrected artifact is intentionally full-length. It carries forward the current-code work report and the existing master-final historical ledger in one file so assessment readers can see both the implementation evidence and the contributor/timeline record without losing the original detail.

This document is therefore organized as follows:

- Part I includes the current-code report in full. It is the canonical technical evidence for the current source tree, metrics, schema/RPC/RLS counts, pipeline behavior, crawler behavior, frontend behavior, tests, limitations, and validation state.
- Part II includes the historical `MASTER_FINAL` report in full. It preserves the long-form timeline, contributor framing, defense ledger, and prior attribution context.
- Where Part II describes older behavior or older metrics, Part I and current `HEAD` source are authoritative.

## Canonical Current Limitations / What Not To Claim

These caveats apply to the whole merged report:

- Do not claim every nutrition paper is in scope. OpenNutri targets direct real-food or stable-food-product composition data.
- Do not claim AI output is final human truth by default. Final active truth is reviewer-led through `paper_review_outcomes`.
- Do not claim AI-model outcomes train feedback. Feedback learning uses final human-review truth and excludes AI-model outcomes.
- Do not claim Turkish/DergiPark is active in normal daily ops. The code path remains, but current daily/refill defaults are English-only.
- Do not claim paper PDFs are stored in Supabase by default. Current ops use source-URL/on-demand PDFs unless explicitly overridden.
- Do not claim the PDF highlighter perfectly reconstructs every table, OCR case, or continuation page.
- Do not claim the L2 classifier is trained and integrated. Feedback terms exist; classifier training is deferred until enough human labels exist.
- Do not claim raw model reasoning is loaded in default cockpit lists. The current slim RPCs intentionally avoid that egress-heavy behavior.
- Do not claim this report changed app code, schema, workflow YAML, the live database, Vercel, or runtime behavior. This is a documentation-only evidence package.

## Part I. Current Code Work Report Included In Full

The following section is the full current-code report generated from the refreshed `origin/main` source snapshot. It is the canonical current technical evidence.

Prepared: 2026-06-05
Source snapshot used for evidence: `0713a03b1766075f62f5093ab75a933942d99a60`
Branch state before report creation: `HEAD...origin/main = 0 0` after `git fetch origin`
Scope: current tracked active source, schema, tests, workflow, and maintained documentation. USDA data dumps, generated binaries, `node_modules`, `dist`, legacy archive, pipeline data caches, generated feedback JSON, local untracked files, and prior work-report files are excluded from source metrics.

## 1. Executive Summary

OpenNutri is an end-to-end food-composition paper discovery and human verification system. The current codebase is not just a React labeler and not just a crawler. It is a complete workflow that starts from reference food/nutrient data, searches scientific literature, filters and downloads papers, runs a three-stage AI cascade, turns model output into a deterministic database-compatible payload, presents the evidence to human labelers, stores immutable submissions, lets an approver correct and finalize truth, and feeds accepted human truth back into the crawler.

The active system has three major deployable surfaces:

- A React 19 + Vite expert annotator in `apps/expert-annotator/`.
- A Supabase Postgres schema/RLS/RPC contract in `apps/expert-annotator/migration.sql`.
- A Python data pipeline in `services/data-pipeline/`, scheduled by `.github/workflows/daily-ops.yml`.

The most important current workflow is:

```text
Reference foods/nutrients
  -> literature search and metadata filter
  -> PDF acquisition and validation
  -> Small model screening: Gemma 31B with 26B fallback
  -> Medium model triage: Gemini 3.1 Flash-Lite
  -> Strong model extraction: Gemini 3.5 Flash
  -> normalized has_data payload
  -> shared human labeling queue
  -> immutable labeler submission
  -> approver correction/finalization
  -> paper_review_outcomes
  -> feedback terms for future crawler ranking
```

The current implementation optimizes for high-precision discovery of direct food/product composition data: real foods or food products mapped to composition values that could support a food composition database, diet tracking, inspection, food exports, or similar data uses. Papers about the health effects of nutrients, supplements, diets, extracts, processing treatments, microbes, biomarkers, animals, sensory scores, or one-off experimental formulations are treated as empty unless they also contain direct food/product composition tables useful to OpenNutri.

## 2. Reproducible Evidence Snapshot

### 2.1 Current Tracked Active Source Lines

Line counts were recomputed from tracked files only. Exclusions: `FoodData_Central_*`, `legacy/`, generated DOCX/PDF/PPTX/image/ODT/XLSX/SVG artifacts, `node_modules`, `dist`, local pipeline data, generated `feedback/latest.json`, `package-lock.json`, logs, and prior work-report files.

| Bucket | Lines | Files | Main evidence |
| --- | ---: | ---: | --- |
| Backend, ops, schema | 31,511 | 88 | Python pipeline, SQL schema/RPC/RLS files, GitHub Actions workflow. |
| Frontend | 14,061 | 53 | React app source, Vite/API/config files, UI helpers. |
| Active docs | 5,191 | 23 | README, AGENTS, handoff/state, reviewer SOP/map, maintained docs excluding work reports. |
| Proposal appendix docs | 971 | 9 | Proposal-section deliverables, counted separately from active implementation docs. |
| Other active | 24 | 1 | Small repo metadata file outside the buckets. |
| Total | 51,758 | 174 | Current active tracked text/source under the exclusions above. |

### 2.2 Key File Line Counts

| File | Lines | Why it matters |
| --- | ---: | --- |
| `apps/expert-annotator/migration.sql` | 5,396 | Current schema, RLS, RPCs, reviewer workflow, routing tables. |
| `services/data-pipeline/scripts/daily_ops_orchestrator.py` | 2,358 | Controller/drain worker tick orchestration and quota accounting. |
| `apps/expert-annotator/src/utils/PdfTextScanner.js` | 2,323 | Browser-side PDF text/table/evidence geometry engine. |
| `services/data-pipeline/food_paper_crawler/crawler_v2.py` | 2,215 | Multi-source Search -> Filter -> Acquisition crawler. |
| `services/data-pipeline/scripts/process_stage_queue.py` | 1,560 | AI task worker, retry/fallback/quota behavior, routing writes. |
| `services/data-pipeline/food_paper_crawler/feedback/update_terms.py` | 1,219 | Human-truth feedback export and query/scoring updates. |
| `apps/expert-annotator/src/pages/Annotate.jsx` | 1,163 | Main UI orchestration, queue, cockpit, approval, suggestions. |
| `apps/expert-annotator/src/components/PdfViewer.jsx` | 939 | PDF rendering, caching, headless scan, overlays, navigation. |
| `services/data-pipeline/ai_routing.py` | 842 | Routing constants, bucket logic, deterministic payload normalization. |
| `services/data-pipeline/scripts/upload_to_supabase.py` | 774 | Paper/search-hit/batch registration and AI task enqueue. |
| `services/data-pipeline/evaluator/unified_evaluator.py` | 687 | Shared model prompt, native PDF input, JSON parser, record extraction. |
| `services/data-pipeline/food_paper_crawler/dergipark_source.py` | 687 | Retained Turkish/DergiPark source adapter. |
| `apps/expert-annotator/src/components/FoodAutocomplete.jsx` | 664 | Food catalog search/ranking UX. |
| `services/data-pipeline/scripts/ensure_paper_stock.py` | 573 | Queue stock/refill wrapper and English-default behavior. |
| `apps/expert-annotator/src/utils/annotateHelpers.js` | 574 | Shared UI payload, formatting, pipeline, AI-summary helpers. |
| `services/data-pipeline/food_paper_crawler/ranking.py` | 485 | Metadata/PDF relevance and validation scoring. |
| `services/data-pipeline/scripts/recover_gemini_candidates.py` | 446 | Historical candidate recovery dry-run/apply tool. |
| `services/data-pipeline/scripts/refill_assignment_queue.py` | 408 | Compatibility stock job for the general queue. |
| `apps/expert-annotator/src/components/NutrientAutocomplete.jsx` | 334 | Nutrient catalog search/ranking UX. |
| `apps/expert-annotator/src/components/SuggestionModal.jsx` | 279 | User suggestions with attachments and rollback behavior. |
| `.github/workflows/daily-ops.yml` | 148 | Scheduled controller plus 5 drain-worker matrix. |

### 2.3 Schema/RPC/RLS Counts

From `apps/expert-annotator/migration.sql`:

| SQL object type | Count |
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

Important functions/RPCs include `hook_restrict_signup_by_email_allowlist`, `claim_paper_stage_tasks`, `sync_reviewer_profile`, `get_general_queue_papers`, `get_general_queue_cards`, `submit_general_label`, `approve_label_submission`, `get_cockpit_ai_extractions`, `get_pipeline_ops_snapshot`, `build_annotation_submission_payload`, and `build_label_payload_diff`.

### 2.4 Test Coverage Evidence

Tracked test files total 5,898 lines across 10 files. The core regression suite most relevant to current risk is 5,617 lines; the remaining tracked test scripts are older/live connectivity helpers.

| Test file | Lines | Evidence focus |
| --- | ---: | --- |
| `services/data-pipeline/tests/test_ai_routing.py` | 2,469 | AI normalization, routing, retry/fallback/quota, upload edge cases. |
| `services/data-pipeline/tests/test_bilingual_pipeline.py` | 1,120 | Crawler language/source/filter behavior, terminal state, batch feedback, PDF limits. |
| `services/data-pipeline/tests/test_daily_ops.py` | 983 | Controller/drain ticks, daily quota windows, worker requirements, stage counts. |
| `apps/expert-annotator/src/utils/PdfTextScanner.test.js` | 655 | Table/paragraph/evidence matching and page-hint behavior. |
| `apps/expert-annotator/src/utils/EvidenceLocations.test.js` | 225 | Source grouping and evidence dedup behavior. |
| `apps/expert-annotator/src/utils/evidenceStatusCache.test.js` | 92 | Evidence status cache behavior. |
| `services/data-pipeline/tests/test_pdf_page_markers.py` | 73 | Page-marker injection and text cap behavior. |
| `services/data-pipeline/test_harvest.py` | 243 | Older/live harvester checks. |
| `services/data-pipeline/scripts/test_frontend_fetch.js` | 24 | Frontend connectivity helper. |
| `services/data-pipeline/test_pg.py` | 14 | Database connectivity helper. |

The current tests include about 130 Python `test_` methods/functions and 35 frontend `it()`/`test()` blocks.

### 2.5 Contributor Evidence

Git history must be read across all refs because the original MVP/frontend commits from Aysegul are preserved on `origin/master`, while the current `main` branch later imported and reorganized that work.

`git shortlog -sne --all` at the snapshot:

| Git author | Commits |
| --- | ---: |
| `baezarciel <baezarciel@gmail.com>` | 214 |
| `landeryt <mcraft160105@gmail.com>` | 24 |
| `ayseguldogan2706-cpu <ayseguldogan2706@example.com>` | 7 |
| `ArcielB <106127166+ArcielB@users.noreply.github.com>` | 1 |

All-ref churn under the active-source filter used for this report:

| Git author | Added | Deleted | Caveat |
| --- | ---: | ---: | --- |
| `baezarciel` | 65,478 | 15,904 | Backend, schema, ops, docs, integration, and much later frontend integration. |
| `ayseguldogan2706@example.com` | 3,185 | 88 | Active-source-filtered frontend MVP lines; raw all-ref additions are 6,624 because `origin/master` includes `package-lock.json`. |
| `mcraft160105@gmail.com` | 2,188 | 582 | Huan's directly authored commits and full-stack features. |
| `ArcielB` | 1 | 0 | Initial repository README commit; treated as Arciel for attribution. |

Aysegul's seven all-ref commits are `7c2d372`, `614a82c`, `6245a17`, `00fd645`, `8a29dcb`, `969c902`, and `fb33626`; the first five are the original MVP/frontend commits on `origin/master`.

## 3. Frontend Annotator

### 3.1 What Was Built

The frontend is a production-oriented expert annotation tool in `apps/expert-annotator/`. It includes:

- Supabase login and reviewer-profile sync.
- A shared general queue of `human_review_ready` papers.
- Quiet AI prefill from the latest normalized Gemini `has_data` payload.
- Editable food/nutrient rows with custom-food/custom-nutrient support.
- A PDF viewer with table-scoped nutrient highlighting, source chips, coordinate overlays, printed-page handling, and durable PDF caching.
- Draft save, final useful-data submission, no-usable-data submission, and help requests.
- An approver workflow where Arciel can edit and accept final truth.
- Cockpit views for dashboard, pipeline, useful papers, reviewer admin, suggestions, and labeler-submitted suggestions.
- Test mode/read-only tester behavior that disables writes and stores actions locally.

### 3.2 Why It Was Needed

The project needed human experts to verify AI-extracted food composition rows against source PDFs. A normal data-entry UI would not be enough because the hard part is evidence inspection: reviewers need to jump from a normalized row to the table or paragraph in the PDF, correct foods/nutrients, and submit a DB-compliant payload that can be compared against AI output and later used as truth.

### 3.3 Technologies and Why They Fit

The annotator uses:

- React 19 and React DOM 19 for stateful, componentized UI.
- Vite 7 for fast local development and Vercel-compatible bundling.
- `@supabase/supabase-js` 2.x for auth, table reads/writes, RPC calls, and signed storage URLs.
- `react-pdf` 10.x and `pdfjs-dist` for browser PDF rendering and text-layer access.
- Plain CSS in `src/index.css` for a compact operational UI.
- ESLint 9 with React Hooks and React Refresh plugins for frontend validation.

These choices fit the problem because the app is mostly a dense workflow surface over Supabase data. React makes the multi-tab state and editable nested rows manageable; Supabase gives auth and row-level access control; PDF.js exposes text geometry needed for evidence matching.

### 3.4 How It Works

`src/pages/Annotate.jsx` is the orchestrator. On mount it calls `sync_reviewer_profile`, loads the queue immediately, and fetches reference nutrients and foods. The queue fast path calls `get_general_queue_cards`, a lean security-definer RPC that returns queue card fields, latest AI payload, and the current user's annotation status in one round trip. A legacy fallback calls `get_general_queue_papers`, `ai_extractions`, and `annotations` separately if the card RPC is not deployed.

When a queue paper has no saved annotation, `buildFoodItemsFromPayload(currentItem.latest_ai_extraction.normalized_payload_json)` initializes editable rows directly from AI output. There is no AI-reasoning banner in the queue; the rows simply become the draft that the labeler corrects.

Final submission is guarded in the UI:

- Useful-data save requires at least one valid food item.
- Final useful-data submission requires at least one nutrient row.
- `paper_label_events` records the action.
- `submit_general_label` freezes the canonical payload into `paper_label_submissions`.

Approvals use the same editable food/nutrient form and call `approve_label_submission`. The original labeler submission is not overwritten. The accepted reviewer payload and correction diff are stored separately.

Cockpit-heavy payloads are lazy-loaded only when a cockpit tab opens. The Useful Papers cockpit uses `get_cockpit_ai_extractions` rather than `ai_extractions.select('*')`, keeping raw model responses out of default browser payloads.

### 3.5 Frontend Views

The current app is split into focused views:

- `QueueView.jsx` handles labeler queue navigation, PDF viewer, food forms, source strip, idle PDF prefetch, and action buttons.
- `ApprovalView.jsx` shows the original submission beside the editable final reviewer payload.
- `DashboardView.jsx` computes labeler performance from submissions and approval diffs.
- `AllPapersView.jsx` shows useful-paper routing state and AI Details.
- `PipelineOpsView.jsx` renders stage queues and funnel counters from `get_pipeline_ops_snapshot`.
- `SuggestionsReviewView.jsx` and `MySuggestionsView.jsx` split suggestion handling by role.
- `ReviewerAdminView.jsx` exposes reviewer flags, tester access, cockpit access, and approval rights.

### 3.6 Hard Parts Solved

The frontend solves several failure modes that would otherwise make labeling slow or unsafe:

- Queue load egress was reduced by moving to one lean queue-card RPC.
- AI prefill no longer overwrites saved drafts or submissions.
- Tester accounts remain read-only even when they can see cockpit views.
- Help requests capture paper, reviewer, draft, and AI context instead of leaving confusion in chat.
- Suggestions with image attachments upload into a private bucket and roll back uploaded files if the DB insert fails.
- The app avoids pulling raw model responses into cockpit lists by default.
- Durable Cache Storage and idle prefetch reduce repeat PDF loads.

### 3.7 Current Limitations

- Food/nutrient autocomplete ranking is heuristic, not learned.
- The frontend unit tests focus on evidence matching/caching, not every UI action.
- Live Supabase behavior is protected by RPC/RLS design but not fully covered by browser end-to-end tests in this repo.
- The PDF text-layer nutrient highlighting still cannot match nutrient names split across multiple PDF.js text items; source overlays cover broad evidence navigation separately.

## 4. PDF Evidence Scanner and Viewer

### 4.1 What Was Built

OpenNutri includes a browser-side PDF evidence engine built from `PdfViewer.jsx`, `PdfTextScanner.js`, `EvidenceLocations.js`, `EvidenceStrip.jsx`, `useEvidenceStatusCache.js`, `evidenceStatusCache.js`, `evidenceDedupStorage.js`, and `pdfCache.js`.

It provides:

- Self-hosted PDF.js worker bundled by Vite.
- Durable PDF byte caching through Cache Storage.
- Headless per-page text scanning before canvas render.
- Table-scoped nutrient-name click highlights.
- Evidence source chips built from AI/human row metadata.
- Matching to table captions, detected table blocks, paragraph quotes, and page hints.
- Printed-page-number mapping when journal/offprint PDFs show printed page labels.
- Always-on coordinate overlays for matched table/paragraph regions.
- Local and remote dedup cache so repeated source rows that resolve to one region share one chip and one overlay.

### 4.2 Why It Was Needed

AI and human payloads store broad evidence hints, not hand-drawn coordinates. Reviewers need to verify rows quickly in arbitrary publisher PDFs. PDF.js gives glyphs and text items, not tables, paragraphs, columns, or true evidence regions. The code therefore reconstructs enough document structure to turn row metadata into useful navigation.

### 4.3 How It Works

`PdfViewer.jsx` loads PDF bytes via `getPdfBytes`, passes `{ data }` to `react-pdf`, renders page 1 immediately, then runs a headless scan over each page's text content and intrinsic size. Evidence pages render early, and after scan completion all remaining pages render. The viewer builds a per-page highlight plan from:

- `buildPageTableHighlightPlan(textContent)`;
- `detectPrintedPageNumber(textContent, pageNumber, numPages)`;
- `buildPageEvidenceHighlightPlan(textContent, evidenceLocations, pageNumber, { printedPageNumber, numPages })`.

`PdfTextScanner.js` extracts positioned PDF text items, builds page metrics, detects column gutters, groups glyphs into rows/fragments, finds table captions, builds confident table regions, builds paragraph blocks outside tables, and matches evidence metadata. It treats `page_hint` as a navigation hint, not proof. If a page hint exceeds total PDF page count, it cannot be a true PDF page index, so content matching can search by table label or source quote instead of staying locked to an impossible page.

`EvidenceLocations.js` groups multiple nutrient rows into source locations using table labels, page hints, source citations, and quote overlap. `EvidenceStrip.jsx` renders the source chips with statuses: matched, hinted, or unverified. `useEvidenceStatusCache` persists dedup clusters locally and remotely through `paper_evidence_dedup`/`merge_paper_evidence_dedup`.

### 4.4 Technologies and Why They Fit

- `react-pdf` and PDF.js are the right choice because they expose both rendered canvases and text-layer content in the browser.
- Cache Storage is appropriate for PDF byte caching because it survives page navigation and avoids repeated source fetches.
- Supabase RPC/table storage is used only for dedup clusters, not raw PDF text, keeping storage low.
- Plain JS geometry is used because the input is the PDF.js text item stream, not semantic HTML.

### 4.5 Hard Parts and Failure Modes Solved

- Table regions are inferred from captions, row structure, numeric/data-like fragments, and column gutters.
- Paragraph matching avoids document chrome such as affiliations, article history, keywords, and copyright rows.
- Source quotes are matched as contiguous excerpts; ellipsis-joined distant fragments are not trusted.
- Table-caption fallback still gives a visible target when a table body is too messy to detect.
- Printed page labels map journal page numbers to PDF page indexes when possible.
- Multiple sources in one resolved block are deduplicated to one chip/overlay.
- Evidence pages render before non-evidence pages, reducing blank waits after auto-jump.

### 4.6 Validation and Known Gaps

Frontend evidence tests cover `PdfTextScanner`, `EvidenceLocations`, and evidence status cache behavior. Known limitations remain:

- Nutrient-name click highlights operate on individual PDF.js text items.
- OCR/image-only PDFs have weak text-layer support in the frontend; final Gemini PDF mode can read native PDFs, but the UI still depends on PDF.js text content for source matching.
- Complex multi-page table continuations can still require manual reviewer judgment.

## 5. Supabase Schema, RLS, and Workflow Engine

### 5.1 What Was Built

`apps/expert-annotator/migration.sql` is the current schema source of truth. It defines:

- Reference food/nutrient/source/claim tables.
- Paper discovery and search-hit/search-batch ledgers.
- Human annotations, food items, nutrient values, label events, and legacy global labels.
- Reviewer profiles and access flags.
- Current general-queue workflow tables: `paper_label_submissions`, `paper_label_approvals`, `paper_review_outcomes`.
- Legacy slot/conflict tables preserved for audit.
- AI routing tables: `routing_stage_configs`, `paper_stage_tasks`, `ai_extractions`.
- Suggestion/help-review table and storage policies.
- 75 RLS policies and 22 `SECURITY DEFINER` functions.

### 5.2 Why It Was Needed

OpenNutri has multiple principals: ordinary labelers, approvers, cockpit viewers, read-only testers, service-role workers, and Supabase auth hooks. Direct table access would either leak sensitive data or block legitimate workflows. The schema uses RLS and security-definer RPCs to expose exactly the slices needed by each role.

### 5.3 Main Data Model

The reference layer:

- `entities`: canonical foods.
- `entity_aliases`: food aliases.
- `master_nutrients`: canonical nutrients.
- `sources`: provenance.
- `claims`: normalized entity-nutrient-source facts.

The discovery layer:

- `papers`: paper identity, source metadata, `pdf_url`, workflow language, routing status, current stage, latest AI extraction.
- `paper_search_hits`: idempotent source/query hit ledger keyed by `hit_key`.
- `paper_search_batches` and `paper_search_batch_hits`: bounded query-batch history used for feedback.

The active review layer:

- `annotations`, `food_items`, `annotation_nutrient_values`: editable per-user workspace.
- `paper_label_submissions`: immutable labeler payload snapshots with canonical text/hash.
- `paper_label_approvals`: one accepted approval per paper, with correction diff.
- `paper_review_outcomes`: final paper truth.

The AI layer:

- `routing_stage_configs`: stage order, model names, thresholds, fallback models, input mode, no-data destination.
- `paper_stage_tasks`: queued/processing/completed/failed model tasks with priority and attempt count.
- `ai_extractions`: model response, normalized payload, normalization summary, bucket, destination, thresholds, audit flags.

### 5.4 RPCs and Security Design

Important security-definer functions:

- `current_auth_email`, `current_user_has_cockpit_access`, `current_user_is_tester`, `current_user_can_write`, `current_user_has_cockpit_write_access`, and `current_user_can_approve_labels` centralize role checks.
- `hook_restrict_signup_by_email_allowlist(event jsonb)` protects signup through `allowed_auth_emails`, with direct client-role table privileges revoked.
- `claim_paper_stage_tasks` uses `FOR UPDATE SKIP LOCKED` and retry-fair ordering to let parallel workers claim distinct rows.
- `get_general_queue_cards` returns the lean queue payload in one RPC.
- `submit_general_label` writes an immutable labeler submission and auto-accepts approver submissions.
- `approve_label_submission` stores corrected final truth and supersedes other pending submissions.
- `get_cockpit_ai_extractions` returns a slim AI projection without raw model reasoning.
- `get_pipeline_ops_snapshot` aggregates protected task/routing/funnel data for cockpit users.

### 5.5 Hard Parts Solved

- The migration is convergent/idempotent: many columns and constraints use `IF NOT EXISTS` or defensive `DO` blocks.
- Legacy workflow tables remain available for audit without driving the current queue.
- Tester read-only behavior is enforced at SQL predicate level, not only in React.
- Direct client access to the signup allowlist is revoked.
- `paper_label_submissions` and `paper_label_approvals` preserve original versus corrected payloads.
- SQL and Python both build canonical payload hashes, enabling exact comparison between AI and human outputs.
- `claim_paper_stage_tasks` is the concurrency primitive that makes five GitHub drain workers safe.

### 5.6 Known Limitations

- One 5,396-line convergent migration is easy to re-apply but large to audit.
- Legacy audit tables add schema complexity.
- RLS is robust but must be validated against live Supabase after schema changes; this task does not alter or apply migrations.

## 6. AI Routing, Unified Evaluator, and Normalization

### 6.1 What Was Built

The AI subsystem spans `ai_routing.py`, `evaluator/unified_evaluator.py`, `scripts/process_stage_queue.py`, `scripts/recover_gemini_candidates.py`, and `scripts/flash_lite_triage_experiment.py`.

The production cascade is:

| Role | Stage key | Model | Input mode | Daily target |
| --- | --- | --- | --- | ---: |
| Small model | `gemma_proof_extraction_v1` | `gemma-4-31b-it`, fallback `gemma-4-26b-a4b-it` | Text with page markers | ~1,500 |
| Medium model | `gemini_flash_lite_triage_v1` | `gemini-3.1-flash-lite` | Configured by stage | ~500 |
| Strong model | `gemini_flash_db_payload_v2` | `gemini-3.5-flash` | Native PDF | ~20 |

Each stage runs the shared `UnifiedEvaluator` prompt/contract, then deterministic normalization and routing decide whether to enqueue the next stage, provisional-skip the paper, finalize it, or send it to humans.

### 6.2 Why It Was Needed

The final extraction model is the scarce resource. A one-stage design would spend expensive calls on low-value papers. The cascade lets OpenNutri screen a much larger literature pool, re-rank likely positives, and spend the final extraction budget on the strongest candidates.

### 6.3 UnifiedEvaluator

`UnifiedEvaluator.EXTRACTION_PROMPT` defines what "useful OpenNutri data" means. It requires strict JSON, broad evidence metadata, per-row food/nutrient values, DB IDs when confidently matched, and true 1-based PDF page index hints. It explicitly rejects intervention/effect/outcome papers unless they contain direct food/product composition tables.

The evaluator:

- Sends the full nutrient catalog.
- Sends high-signal food candidates selected from paper text, not the full food catalog.
- Can attach native PDF bytes inline under about 15 MB, otherwise through the Gemini Files API with cleanup.
- Handles text-mode stages by passing marked text with `===== PDF PAGE N =====` markers.
- Accepts multiple model output shapes: requested object, top-level array of rows, one result object wrapped in an array, and nested `food -> nutrients[]` rows.
- Strips Markdown JSON fences and scans for balanced JSON objects/arrays inside noisy model text.

### 6.4 Deterministic Normalization

`normalize_ai_payload_with_summary` converts free-form model rows into the same canonical payload shape as a human submission:

- Drops rows missing food, nutrient, or amount.
- Standardizes only DB-compatible units: `g/100g`, `mg/100g`, `μg/100g`, `kcal/100g`, `kJ/100g`, `IU/100g`, and `%`.
- Rejects dry-matter and unsupported bases for final payload rows.
- Verifies model-provided food/nutrient IDs against current DB rows and matching names.
- Falls back to exact/alias matching.
- Preserves unresolved foods/nutrients as explicit custom rows.
- Preserves evidence metadata such as table label, page hint, source quote, section heading, paragraph hint, and source location type.
- Sorts foods/nutrients deterministically and rounds values to six decimals.
- Emits a normalization summary with accepted/rejected/unmapped counts and rejection reasons.

This is necessary because AI output and human submissions are later compared by canonical JSON and SHA-256 hash.

### 6.5 Routing and Priority

`classify_routing_bucket`, `stable_audit_sample`, and `route_bucket` map model decisions into routing destinations. Low-confidence outputs go to humans; high-confidence outputs can finalize unless sampled for audit; no-data stages can provisional-skip.

`score_followup_priority` makes the cascade top-N rather than FIFO. It rewards:

- model confidence;
- accepted normalized rows;
- evidence rows;
- per-100g rows;
- table rows;
- complete raw rows;
- direct composition language;
- high database-value signals.

It applies soft penalties for review/meta-analysis/database aggregates, feed/digestibility, sensory/outcome/biomarker/cell/animal, one-off formulation, treatment, supplement, and extract language. Unsupported-unit raw rows can increase screening priority but still cannot enter the final normalized payload.

### 6.6 Worker Failure-Mode Handling

`process_stage_queue.py` implements:

- `claim_paper_stage_tasks` RPC claiming.
- Stale `processing` requeue.
- Model runtime validation before claiming rows.
- `pdftotext` dependency failure fast.
- Source-URL PDF fetch through `papers.pdf_url`.
- Native PDF bytes for PDF-mode stages.
- Gemma-specific text cap via `GEMMA_STAGE_TEXT_LIMIT_CHARS`.
- Per-task timeout through `AI_MODEL_TASK_TIMEOUT_SECONDS`.
- Same-attempt fallback from Gemma 31B to configured 26B on retryable failures.
- Non-retryable model configuration failure as permanent task failure.
- Quota/rate-limit requeue that decrements attempt count so quota does not burn retry budget.
- Non-quota retry ceiling through `AI_STAGE_MAX_TASK_ATTEMPTS`.
- Raw-positive rescue for useful-looking Gemma output that normalized to empty rows.

### 6.7 Validation and Limitations

`test_ai_routing.py` covers normalization, unit policy, ID safety, JSON-shape salvage, priority scoring, stale requeue, fallback, quota behavior, upload races, and route preservation. Limitations:

- The model contract still depends on live Gemini/Gemma behavior and can drift.
- Strict unit policy rejects some scientifically valid rows that are not DB-ready.
- Text-mode Gemma cannot interpret scanned/image-only PDFs; routing such papers to a PDF-capable first stage is a separate follow-up.

## 7. Crawler v2, Ranking, and PDF Acquisition

### 7.1 What Was Built

`FoodCompositionCrawlerV2` implements a staged literature crawler:

```text
Search -> metadata filter -> PDF acquisition -> PDF validation -> manifest/search ledger
```

Current default sources are Europe PMC, OpenAlex, and Semantic Scholar. A DergiPark/Turkish path remains in the code but current daily ops defaults are English-only.

### 7.2 Why It Was Needed

Downloading and validating PDFs is expensive and unreliable. The crawler therefore retrieves metadata first, applies additive relevance scoring, and downloads only candidates that pass. The target is high-precision direct food composition papers, not every nutrition paper.

### 7.3 Technologies and Why They Fit

- Python standard library HTTP/XML/JSON tools for source adapters.
- Europe PMC APIs, OpenAlex, Semantic Scholar, and retained DergiPark adapter for literature search.
- `pdftotext` from Poppler for PDF text validation.
- `sentence-transformers` via `DualEmbeddingScorer` for embedding similarity in crawler ranking.
- Supabase REST/service-role access through upload/refill scripts.
- Local manifest JSON for resumable crawler artifacts and batch audit.

### 7.4 How It Works

The crawler builds language-scoped query tasks. With current defaults, total targets go to English and Turkish target is zero. Query execution is batch-aware: every source/query task carries a batch id/key and stores search-gate/filter/acquisition counters for later feedback.

The search gate scores title/abstract with:

- composition phrase hits;
- food-term hits;
- nutrient-term hits;
- unit patterns such as `mg/100g`;
- food + nutrient combo;
- penalties for missing abstract, strong negative signals, soft negative terms, and health-outcome terms.

The metadata filter adds:

- stronger lexical weights;
- source priors;
- embedding similarity;
- soft feedback n-gram score.

PDF acquisition then fetches source PDFs or Europe PMC OA packages, checks size limits, writes local files, extracts text, strips reference sections in validation, and requires table/food/nutrient/unit evidence through `ranking.validate_pdf_text`.

### 7.5 Failure Modes Solved

- Wall-clock bounded crawler runs write partial accepted results instead of losing work at the GitHub job limit.
- Oversized PDFs are rejected before becoming storage/egress problems.
- Publisher HTML/redirect pages are handled with nested PDF discovery, curl fallback, and an MD5 proof-of-work solver for PMC pages that require it.
- Accepted filenames are identity-based, not title slug-based.
- Crawler terminal state and live Supabase `papers.canonical_key` rows are used to avoid re-downloading already queued/skipped/finalized papers.
- Metadata-only search-hit rejects are not used as global skip memory, preserving audit/benchmark flexibility.
- Negative evidence is penalty-based, not a hard veto.

### 7.6 Limitations

- Current ops are intentionally English-only, even though Turkish code remains.
- The crawler prioritizes precision and may miss useful papers that lack abstracts, explicit units, or clear composition terminology.
- `sentence-transformers` is required for embedding scoring; missing dependencies should fail fast.

## 8. Feedback Learning

### 8.1 What Was Built

`food_paper_crawler/feedback/update_terms.py` exports feedback data from labeled papers. It produces language-scoped query phrases, anchor phrases, weighted n-grams, source priors, source/template/term pair scores, batch scores, and concept scores into `feedback/latest.json`.

### 8.2 Why It Was Needed

The crawler should improve as humans approve or reject papers. Static search terms are not enough because source yield, useful food/nutrient terms, and false-positive topics shift over time.

### 8.3 How It Works

The feedback script:

- Reads `paper_review_outcomes` first.
- Includes only `truth_source_kind = human_review`.
- Excludes AI-model outcomes from feedback.
- Uses legacy label events/global labels only for older unresolved papers.
- Excludes open conflicts.
- Splits papers by `workflow_language`, falling back to language detection when needed.
- Counts title-only and title+abstract n-grams separately.
- Uses smoothed log-odds against background and bad buckets.
- Adds seed-good priors.
- Builds query phrases, anchor phrases, discovery candidates, pair scores, batch scores, source priors, and concept scores.

### 8.4 Failure Modes Solved

- Pending/superseded submissions do not become benchmark truth.
- The model does not train the crawler on its own AI-finalized outcomes.
- Duplicate search hits are deduped before feedback counts.
- Batch feedback is based on bounded query batches, not raw source-result volume.

### 8.5 Limitations

- L2 classifier training is deferred until enough accepted human outcomes exist.
- The generated `feedback/latest.json` is local generated output and should not be hand-edited.
- Feedback refresh occurs only when crawler/refill runs, not during pure queued-AI draining.

## 9. Daily Ops and Deployment Workflow

### 9.1 What Was Built

`.github/workflows/daily-ops.yml` schedules OpenNutri ops every five minutes with:

- One serialized `refill-controller` job under `daily-ops-refill-controller`.
- A parallel five-worker `drain-workers` matrix.
- Manual `workflow_dispatch` worker count control.

The controller installs full crawler requirements and may crawl/upload/refill. Workers install `requirements-worker.txt`, never crawl/upload/refill, and only drain already-created model tasks.

### 9.2 Why It Was Needed

The project runs on free/limited infrastructure and model quotas. A single long daily job is fragile; recurring ticks make progress resumable from database state. Splitting controller and workers lets paper discovery continue safely while model tasks drain in parallel.

### 9.3 How It Works

The controller:

- Requeues stale processing tasks.
- Counts per-stage completions since each stage's quota-day start.
- Counts active Gemma work from queued plus non-stale processing tasks.
- Tops up to a bounded active target, currently 150 Gemma tasks.
- Crawls English papers in bounded chunks of 30 accepted PDFs.
- Sets `OPENNUTRI_STORE_PDFS_IN_SUPABASE=0`.
- Skips storage cleanup and soft-limit measurement in scheduled source-URL mode.

The workers:

- Run drain-only tick mode.
- Process up to 20 Gemma tasks per worker tick.
- Interleave up to 10 Flash-Lite triage tasks and 2 final Gemini extraction tasks.
- Use `AI_MODEL_TASK_TIMEOUT_SECONDS=300`, `GEMINI_REQUEST_TIMEOUT_SECONDS=300`, `AI_STAGE_MAX_TASK_ATTEMPTS=2`, and `GEMMA_STAGE_TEXT_LIMIT_CHARS=24000`.
- Claim distinct rows through the DB RPC, so overlapping matrices are safe.

### 9.4 Technologies and Why They Fit

- GitHub Actions cron is enough for low-cost scheduled workers.
- Supabase Postgres is the durable queue and coordination layer.
- `FOR UPDATE SKIP LOCKED` removes the need for an external queue service.
- Environment variables and GitHub secrets provide runtime credentials.
- Poppler `pdftotext` is installed by the workflow because both crawler and workers need it.

### 9.5 Limitations

- GitHub Actions job timeouts still constrain crawler throughput.
- Provider quota and API behavior can stop a tick early.
- Source-URL PDFs depend on publisher availability; this is intentional to avoid Supabase Storage/egress pressure.

## 10. Source-URL PDF and Egress/Storage Strategy

Current paper PDFs are source-URL/on-demand by default:

- `upload_to_supabase.py` records `papers.pdf_url`.
- Supabase paper PDF Storage upload only occurs if `OPENNUTRI_STORE_PDFS_IN_SUPABASE=1`.
- Scheduled ops set `OPENNUTRI_STORE_PDFS_IN_SUPABASE=0`.
- The annotator proxies external PDFs through `apps/expert-annotator/api/pdf.js` for CORS and caching.
- `pdfCache.js` stores up to 40 PDFs in browser Cache Storage.
- Suggestion attachments still use the private `suggestion-attachments` bucket.

This design was needed because paper Storage and default AI list payloads could consume free-tier storage/egress quickly. It trades some reliance on publisher URLs for lower Supabase storage pressure.

## 11. ETL and Reference Data Utilities

### 11.1 What Was Built

OpenNutri includes USDA reference-data loaders:

- `etl_usda_to_opennutri.py` loads Foundation Foods into the OpenNutri schema.
- `etl_sr_legacy_to_opennutri.py` loads SR Legacy with stable UUIDs and alias support.
- `create_opennutri_schema.sql` and `query.json` support the broader universal schema.

### 11.2 Why It Was Needed

AI normalization and UI autocomplete need known foods and nutrients. The project also needs a baseline reference layer to compare paper-derived facts against.

### 11.3 How It Works

The ETL scripts read USDA CSVs, transform foods into `entities`, aliases into `entity_aliases`, nutrients into `master_nutrients`, provenance into `sources`, and values into `claims`. They upload through Supabase REST in batches and use conflict/upsert behavior for idempotence. The SR Legacy loader uses deterministic UUIDv5 IDs so repeated runs produce stable IDs.

### 11.4 Limitations

- Some older ETL code reads `.env` locally and is not a polished production importer.
- USDA data dumps are tracked but excluded from active source metrics.
- Reference data is a seed layer; paper extraction still requires human validation before becoming truth.

## 12. Documentation and Project-Management Artifacts

Maintained docs include:

- `README.md`: architecture, app behavior, commands, env vars, ops notes.
- `AGENTS.md`: standing project truths and coding-agent instructions.
- `docs/handoff_2026-03-20/STATE.md`: current high-signal project state.
- `docs/reviewer_workflow_map.md`: reviewer workflow/RPC/table map.
- `docs/reviewer_sop_en.md`: reviewer-facing SOP.
- `docs/defense/*`: defense/work-report artifacts.

These are not just prose. The workflow map and AGENTS file encode critical product truths: general queue, approver-led final truth, no AI no-data in labeler queue, slim cockpit AI projections, source-URL PDF strategy, and current English-only ops defaults.

## 13. Current Limitations / What Not To Claim

Do not claim:

- That every nutrition paper is in scope. OpenNutri targets direct food/product composition data only.
- That AI output is final human truth by default. Final active truth is reviewer-led through `paper_review_outcomes`; AI-model outcomes are provenance and are excluded from human-truth feedback.
- That Turkish/DergiPark is active in normal ops. Code remains, but current daily/refill defaults are English-only.
- That paper PDFs are stored in Supabase by default. They are source-URL/on-demand unless a legacy override is explicitly set.
- That the PDF highlighter perfectly understands every table. It reconstructs table/paragraph regions from PDF.js text and still has known limitations.
- That the L2 classifier is trained and integrated. Feedback terms exist; classifier training is deferred.
- That the generated `feedback/latest.json` should be edited manually. It is generated output.
- That raw model reasoning is shown in the default cockpit. The current slim RPC intentionally excludes raw responses/reasoning from default lists.
- That this report applied a schema migration, deployed Vercel, or touched the live database. It is a documentation-only current-code report.

## 14. Validation State for This Report

This report was created from current tracked source after remote refresh and status check. It is intended to be exported to DOCX with Pandoc and validated through:

- `pandoc docs/defense/OpenNutri_Current_Code_Work_Report.md -o docs/defense/docx/OpenNutri_Current_Code_Work_Report.docx`
- `pandoc docs/defense/OpenNutri_Current_Code_Work_Report.md -t plain | wc -w`
- `unzip -p docs/defense/docx/OpenNutri_Current_Code_Work_Report.docx word/document.xml`
- `git diff --check`
- `git diff --cached --check`

## Part II. Historical Master Final Included In Full

The following section preserves the existing master-final report in full for history, contributor attribution, timeline, and assessment framing. It was written against an older source snapshot; use Part I when current implementation details conflict.

Prepared: 2026-06-05
Source snapshot used for evidence: `4a8ec8af18eed030d9ccfdebd6fd979648218374` (`main`, even with `origin/main` before this final documentation file was created)
Activity span in git: 2025-12-19 to 2026-06-05
Purpose: combine the strongest parts of the Claude master report and the Codex v2 master ledger into one assessment-ready master report.

Source reports merged:

- Claude master: `docs/defense/OpenNutri_Work_Report_MASTER.md`.
- Codex v2 master: `docs/defense/OpenNutri_Work_Report_MASTER_v2.md`.

This final version keeps the v2 report's stricter methodology, refreshed metrics, attribution caveats, repository structure, assessment ledger, and chronological evidence. It also restores the older master report's deeper subsystem explanations: the AI cascade, database/RLS/RPC design, crawler v2, feedback loop, daily-ops infrastructure, PDF evidence engine, annotator frontend, Huan's full-stack features, ETL, and tests. The intent is not to be short. The intent is to give evaluators a defensible record of what was built, why it was built, how it works, what technology was used, when it changed, and where the source evidence lives.

## 1. Methodology and Attribution Rules

This report was built from current source evidence after `git fetch origin`, an ahead/behind check, and a working-tree status check. At the start of the final merge, `main...origin/main` was `0 0`. The working tree contained unrelated untracked artifacts such as older work-breakdown exports and files under `docs/defense/read_this/`; those were intentionally left untouched.

Evidence sources used across the master reports:

- Git history across all refs, because Aysegul's original MVP/frontend commits live on `origin/master` while the current `main` branch later imported and reorganized that work.
- Current tracked source inventory, excluding USDA data dumps, generated binaries, legacy archive files, `node_modules`, build output, local data caches, generated feedback JSON, lockfiles, and work-report files that would inflate the metric.
- Current source files in `apps/expert-annotator/`, `services/data-pipeline/`, `apps/expert-annotator/migration.sql`, and `.github/workflows/daily-ops.yml`.
- Existing project docs: `README.md`, `AGENTS.md`, `docs/handoff_2026-03-20/STATE.md`, and `docs/reviewer_workflow_map.md`.
- Implementation file reads and counts: `migration.sql`, `PdfViewer.jsx`, `PdfTextScanner.js`, `Annotate.jsx`, `FoodAutocomplete.jsx`, `NutrientAutocomplete.jsx`, `SuggestionModal.jsx`, `fuzzyMatch.js`, `ResetPassword.jsx`, `ai_routing.py`, `unified_evaluator.py`, `process_stage_queue.py`, `crawler_v2.py`, `ranking.py`, `update_terms.py`, and `daily-ops.yml`.

The report separates two kinds of attribution:

- **Git-author attribution:** what git directly proves. Every `landeryt` commit is credited to Huan. `baezarciel` plus the initial `ArcielB` commit are credited to Arciel. The `ayseguldogan2706-cpu` identity has seven all-ref commits, including five original MVP/frontend commits on `origin/master` and two push-test commits on the current mainline.
- **Subsystem attribution:** the team's stated ownership split for assessment. Aysegul owns the core user-facing annotator frontend: annotation UI, PDF viewing/highlighting UX, autocomplete surfaces, and workflow views. Arciel owns database/schema/RLS/RPCs, crawler, AI pipeline, daily ops, deployment infrastructure, backend-driven cockpit integrations, documentation, and project management.

That distinction is essential. A report based only on current-mainline git authorship would under-credit Aysegul because early frontend work was imported through later integration commits. A report based only on subsystem claims would hide what git directly proves. This final report uses both and labels the difference.

## 2. Reproducible Metrics

### Repository activity

`git shortlog -sne --all` at the final source snapshot:

| Git author | Commits |
| --- | ---: |
| `baezarciel <baezarciel@gmail.com>` | 213 |
| `landeryt <mcraft160105@gmail.com>` | 24 |
| `ayseguldogan2706-cpu <ayseguldogan2706@example.com>` | 7 |
| `ArcielB <106127166+ArcielB@users.noreply.github.com>` | 1 |

Filtered all-ref git-author churn, excluding USDA dumps, legacy files, lockfiles, proposal appendix drafts, and work-report files:

| Git author | Added | Deleted | Notes |
| --- | ---: | ---: | --- |
| `baezarciel` | 66,207 | 16,985 | Current integration, backend, ops, schema, docs, and many frontend integration commits, with work-report files removed from the code/project metric. |
| `landeryt` | 2,188 | 582 | Huan's directly authored commits. |
| `ayseguldogan2706-cpu` | 6,624 | 88 | Original MVP/frontend commits on `origin/master` plus push-access test commits. |
| `ArcielB` | 1 | 0 | Initial repository README commit; treated as Arciel. |

Current filtered tracked text/source total: **51,874 lines**. This excludes USDA CSV/XLSX dumps, generated DOCX/PDF/PPTX/image artifacts, legacy archive files, `node_modules`, `dist`, local pipeline data, generated `feedback/latest.json`, `package-lock.json`, and work-report files.

Active bucket split under the same exclusions:

| Bucket | Current tracked lines | Main evidence |
| --- | ---: | --- |
| Backend, ops, schema | 31,302 | `services/data-pipeline/**`, SQL schema/RPCs, GitHub Actions workflow. |
| Frontend | 14,310 | `apps/expert-annotator/**` excluding `migration.sql`, build output, and lockfile. |
| Active docs | 5,092 | README, AGENTS, reviewer workflow, handoff/state, defense notes excluding work reports and generated media. |
| Proposal appendix docs | 971 | `docs/proposal-sections/**`, counted separately because they are project deliverables rather than active implementation/docs. |

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

Focused test coverage by line count:

| Test file | Lines | What it validates |
| --- | ---: | --- |
| `apps/expert-annotator/src/utils/PdfTextScanner.test.js` | 655 | PDF table/paragraph/evidence scanner behavior. |
| `apps/expert-annotator/src/utils/EvidenceLocations.test.js` | 225 | Evidence source merge/dedup behavior. |
| `apps/expert-annotator/src/utils/evidenceStatusCache.test.js` | 92 | Evidence cache behavior. |
| `services/data-pipeline/tests/test_ai_routing.py` | 2,469 | AI normalization, routing, units, thresholds, priority, retry behavior. |
| `services/data-pipeline/tests/test_bilingual_pipeline.py` | 1,120 | Crawler language/source/filter behavior. |
| `services/data-pipeline/tests/test_daily_ops.py` | 983 | Daily ops orchestration and quota/drain logic. |
| `services/data-pipeline/tests/test_pdf_page_markers.py` | 73 | PDF page marker injection. |
| Total | 5,617 | Regression suite focused on high-risk behavior. |

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
| Performance and report package | 2026-06-04 to 2026-06-05 | Lean queue RPC, lazy cockpit, self-hosted PDF worker, durable Cache Storage PDFs, evidence-first PDF rendering, v1/v2 work reports, and this combined Master Final. |

## 6. Deep Technical Work Log

This section is brought forward from the older master report because it contains the most detailed technical explanation. It is organized by subsystem and describes what each subsystem is, why it exists, how it works internally, where the hard parts are, which technologies are involved, and what trade-offs were made.

### AI extraction cascade — Gemma → Gemini Flash-Lite → Gemini Flash *(Arciel)*

**Files read in full for this section:** `evaluator/unified_evaluator.py` (687 lines), `ai_routing.py` (842), `scripts/process_stage_queue.py` (1,560), with `scripts/recover_gemini_candidates.py` (446) and `scripts/flash_lite_triage_experiment.py` (245). **34 commits** touch this subsystem.

#### What it is and why it exists
Every accepted paper passes a three-stage model funnel before a human ever sees it:

```
gemma_proof_extraction_v1   gemma-4-31b-it   text mode   ~1500/day   "Small model"
        │  (has_data + priority score)         fallback: gemma-4-26b-a4b-it
        ▼
gemini_flash_lite_triage_v1 gemini-3.1-flash-lite  ~500/day          "Medium model"
        │  (re-ranks the strongest Gemma output)
        ▼
gemini_flash_db_payload_v2  gemini-3.5-flash  native PDF  ~20/day     "Strong model"
        │  (final extraction)
        ▼
   human_review_ready  ──►  general labeling queue
```

**Why a cascade and not one model:** the final Gemini extraction is the scarce, expensive resource (~20 calls/day on the free quota). A cheap high-volume screener (Gemma, ~1500/day) → a mid re-ranker (Flash-Lite, ~500/day) → the expensive extractor (~20/day) means those 20 calls are spent on the **top-ranked** papers out of 1500, not on whatever arrived first. Each stage is configured in the `routing_stage_configs` table (`positive_threshold`, `negative_threshold`, `audit_rate`, `next_stage_on_has_data`, `fallback_model_names`, `model_input_mode`), so the pipeline shape is data-driven and a model can be swapped without code changes.

#### The shared contract: `UnifiedEvaluator` (one prompt for every model)
All three stages run the *same* `evaluate_and_extract()` against the same `EXTRACTION_PROMPT` (`opennutri_evidence_payload_v2`). The prompt is the product's domain definition in code: it spends ~25 lines enumerating exactly what "useful OpenNutri data" is (direct food/product composition values) versus what is **empty** — intervention/effect studies, one-off experimental formulations (1%/2%/4% additive levels, fertilizer/irradiation/storage/salt-stress treatments), digestibility, sensory, biomarkers, review aggregates. This precision is the difference between a database of real foods and a pile of irrelevant agronomy papers.

Each extracted row must carry **evidence-location metadata** so the frontend can later highlight it: `table_label`, `page_hint`, `source_quote` (a *short contiguous verbatim* excerpt, ≤20 words, matched against the PDF to place the highlight), `source_location_type`, `section_heading`, `paragraph_hint`. The prompt explicitly instructs the model that `page_hint` is the **1-based PDF page index from the `===== PDF PAGE N =====` markers, never the printed journal page** — the single most important instruction, because the printed-page bug is what broke highlighting (see frontend section).

The prompt is fed the **full `master_nutrients` catalog** (id + standard_name) but only **text-matched food candidates**, not the whole food table — `select_food_candidates_for_text()` substring-matches every food/alias (≥4 chars, word-boundary) against the first 500 KB of the paper and keeps the 250 longest matches. Trade-off: full nutrient catalog (small, high value for ID resolution) vs. a filtered food shortlist (the food table is large; sending it all would blow the prompt and cost).

#### Robustness 1 — surviving model JSON drift
LLMs return malformed or differently-shaped JSON constantly; naively this becomes an infinite retry loop. The evaluator defends in depth (`_parse_response_json`, `_coerce_result_root`, `_iter_candidate_rows`):
- **Markdown fence stripping** (` ```json … ``` `).
- **Balanced-bracket candidate scanner** (`_balanced_json_candidates`) — a hand-written character scanner that tracks string/escape state and brace/bracket depth to extract the first *balanced* JSON object/array even when the model wraps it in prose. It yields candidates and picks the first that "looks like a result root."
- **Four accepted shapes**, all coerced to one canonical root: the requested object; a bare top-level array of rows; a single object wrapped in a one-element array; and nested `food → nutrients[]` rows (flattened by `_iter_candidate_rows` using a shared `_food_context`). A row missing food/nutrient/amount/unit is dropped, not fatal.

So *valid-but-differently-shaped* output is salvaged instead of triggering a retry. This is the concrete realization of the AGENTS rule "keep these parser variants so shape drift does not become an infinite AI retry loop."

#### Robustness 2 — native PDF input + true page numbers
`_build_generate_content()` attaches the PDF as a native document part when the stage's `model_input_mode == "pdf"`: **inline** under a 15 MB cap, otherwise uploaded via the Files API with a `cleanup` callback that deletes the temp file *and* the remote upload in a `finally` (so failures don't leak files or quota). Native PDF gives the model rendered pages + tables + the auto-extracted (un-billed) embedded text, and lets it report the true page.

For text-mode stages, `annotate_pdf_page_breaks()` splits `pdftotext` output on form-feeds (`\f`), drops a trailing empty page, and injects `===== PDF PAGE N =====` markers **before** any truncation, so surviving pages keep correct numbers. **Why Gemma stays text-mode:** the probe (`probe_model_file_input.py`) confirmed Gemma *accepts* PDF parts but was measured to **time out >600 s on a 5-page PDF** (both 31B and 26B) — fatal for a ~1500/day stage — so Gemma gets page-marked text, which already gives it correct page numbers without images. This decision is encoded and documented so it isn't naively reverted.

#### The deterministic normalizer (`normalize_ai_payload_with_summary`, ai_routing.py)
The model's free-form rows are converted into the exact same `normalized_payload_json` contract a human labeler submits — this is what makes AI output and human output interchangeable downstream. The pipeline:
1. **Required-field gate:** drop rows missing food/nutrient/amount → counted as `missing_required_field`.
2. **Unit standardization (`_standardize_unit`)** — the strict gatekeeper. Only `g/100g`, `mg/100g`, `μg/100g`, `kcal/100g`, `kJ/100g`, `IU/100g`, `%` survive. It handles `µ`-vs-`μ`, casefolding, `gram(s)`/`mg`/`milligram`/`mcg`/`ug`/`microgram`/`kcal`/`kJ`/`IU` spellings, compound `mg/100g` forms, and a **basis policy**: per-100g required, **dry-matter/`dm` rejected**, but `fresh`/`wet`/`as-is`/`edible portion` accepted. Rejections counted as `unsupported_unit_or_basis`.
3. **Reference resolution (`_resolve_reference_row`)** — ID-first (verify the model's `food_fdc_id`/`nutrient_id` against live rows *and* that the row's name matches), then exact name, then alias. The name resolver (`_build_exact_name_resolver`) maps **ambiguous names to `None`** (if two DB rows share a name, neither matches) to avoid wrong links. Unresolved foods/nutrients are kept as explicit `is_custom_food`/`is_custom_nutrient` rows, not dropped.
4. **Grouping + deterministic ordering:** rows group by (resolved food, id, custom flag, raw name, prep state); foods and nutrients are sorted by a long stable key; values `round(…, 6)`. This determinism matters because the payload is **canonically serialized and SHA-256 hashed** (`payload_text_and_hash`) for dedup and exact-match comparison against human submissions — two equal extractions must hash identically.
5. **Summary accounting:** `accepted/rejected/unmapped` counts and a `rejection_reasons` histogram are stored on every extraction, so the cockpit can see *why* rows were dropped.

#### Routing logic (`ai_routing.py` + `process_one_task`)
After normalization the paper is bucketed and routed:
- **`classify_routing_bucket`** → high/low × positive/negative, comparing `overall_confidence` to the stage's thresholds.
- **`stable_audit_sample`** — deterministic audit sampling: `SHA256(paper|stage|model)` compared against `audit_rate × 2^64`. Same paper always gets the same audit decision (reproducible), and a configurable fraction of even high-confidence AI finalizations are forced to human review as a quality check.
- **`route_bucket`** → low-confidence or audit-sampled or already-has-human-truth ⇒ `human_review_ready`; high-positive ⇒ `ai_finalized_has_data`; high-negative ⇒ finalized no-data.
- **Per-stage destinations** layered on top in `process_one_task`: if the stage has a `next_stage_on_has_data` and the paper is useful (or a *raw-positive rescue*, below), it is **enqueued to the next stage** instead of finalized; if the stage's `no_data_route_destination == provisional_skip`, no-data becomes a **provisional skip** (kept out of the human queue and, if legacy storage is on, its PDF is deleted).
- **Raw-positive rescue (`_clear_raw_has_data_decision`):** a Gemma output that is raw-positive but normalizes to *empty* rows still advances to the next stage if it had complete raw rows, or confidence ≥ 0.75, or ≥ 0.6 with composition language — so parser/normalizer drift never silently drops a likely-real paper. Strict normalization still gates final Gemini/human entry.

#### The follow-up priority score (`score_followup_priority`) — why each stage processes the *top-N*
This is the function that makes the funnel a funnel. Each useful output gets an integer score (clamped −1000…1000) combining:
- `80 × confidence`
- accepted normalized rows (`×8`, cap 160), evidence rows (`×5`, cap 90), per-100g rows (`×4`), table rows (`×5`)
- raw-output signals (complete rows, evidence, table, per-100g, unsupported-unit rows that still indicate a real table)
- a **direct-fit bonus**: +70 for "food/nutrient/proximate composition" language, +25 for "food product / real-world / commercial / high database value", +up-to-45 for table rows, +up-to-35 for evidence rows
- **soft penalties** (subtracted): review/meta-analysis/database-aggregate (−35/−20), feed/digestibility (−30), sensory/outcome/biomarker/cell-culture/animal-model (−25), one-off/experimental formulation (−35/−30), treatment/supplement/extract (−20).

The next stage then claims tasks ordered by this priority, so Flash-Lite processes the best 500 of Gemma's output and the final Gemini the best 20 of that. The penalty list mirrors the prompt's "empty" definition — the same domain judgment encoded twice, once for the model and once for the ranker.

#### Retry-fairness, fallback ladder, and quota safety (`process_stage_queue.py`)
The execution engine is built so that **no single bad paper or quota blip can stall automation**:
- **Atomic claiming:** tasks come from the `claim_paper_stage_tasks` RPC (DB-atomic), so overlapping GitHub Actions worker matrices never double-process a row.
- **Fair ordering:** claimed tasks are sorted `(attempt_count ASC, priority DESC, created_at, id)` — lowest-attempt first so a repeatedly-failing paper can't monopolize; then highest priority; then oldest. (AGENTS explicitly forbids reverting to pure oldest-first for this reason.)
- **Stale requeue:** `requeue_stale_processing_tasks` returns `processing` rows older than 120 min to `queued` before claiming, so a killed runner never strands a paper.
- **Model validated before claiming:** `get_evaluator(initial_config)` constructs the model first; a missing `GEMINI_API_KEY` raises *before* any row is claimed, so config errors don't leave rows stuck in `processing`.
- **Hard per-paper timeout:** `ai_task_timeout` uses `SIGALRM`/`setitimer` to raise after `AI_MODEL_TASK_TIMEOUT_SECONDS` (300 s in prod) — one slow paper can't consume a large slice of the GitHub Actions job.
- **Error taxonomy:** `is_quota_error` (quota/rate-limit/429), `is_non_retryable_model_error` ("model not found / not supported for generateContent"), `is_retryable_model_error` (timeout/deadline/503/500/quota). Each routes differently:
  - **Non-retryable** ⇒ task `failed`, paper `ai_failed`, automation stops with a config error (don't loop on a misconfigured model).
  - **Retryable + the stage has `fallback_model_names`** ⇒ try each fallback (Gemma 31B → 26B) **in the same task attempt** via `replace(stage_config, model_name=…)`.
  - **Quota** ⇒ requeue but **decrement `attempt_count`** (`mark_task_requeued_after_quota_error`) so a quota wait never looks like a paper failure and never burns the retry budget.
  - **Other retryable** ⇒ requeue with the formatted error (type + `repr` + traceback tail, via `format_exception_for_storage`, so even empty SDK exceptions are classifiable).
  - **> `AI_STAGE_MAX_TASK_ATTEMPTS=2` non-quota attempts** ⇒ fail the task instead of retrying forever.

#### Persistence + finalization
`insert_ai_extraction` stores the full audit trail in `ai_extractions`: raw model response, parsed result, the `normalization_summary` (with rejection histogram), the normalized payload, the **threshold snapshots** at decision time, the routing bucket/destination, and `audit_sampled`/`finalized_without_human`. High-confidence AI finalizations also `upsert` into `paper_review_outcomes` with `truth_source_kind='ai_model'` (`finalize_ai_outcome`) — recorded as provenance but *excluded* from the human-truth feedback export (see feedback section). Papers that already have human truth are never overwritten (`preserve_human_route`).

#### Recovery + regression tooling
- `recover_gemini_candidates.py` (446) recomputes Gemini priorities from historical Gemma `raw_data`, ranks raw-positive/normalized-empty rows against the 500-candidate soft reservoir target, and **dry-runs by default** (apply mode capped at 200/run) — so a backfill can never stampede the live queue.
- `flash_lite_triage_experiment.py` (245) samples known useful/no-data papers, runs Flash-Lite against the same contract, and reports agreement / useful-recall / no-data false-positive rate — the regression gate kept around the triage stage now that it is production, not experiment.

#### Trade-offs, summarized
- **Recall sacrificed for cost/precision:** ~20 Gemini calls/day means most of 1500 screened papers wait; the priority funnel makes that acceptable by always processing the best first, and `recover_gemini_candidates.py` revisits the rest later.
- **Determinism over flexibility:** strict unit/basis acceptance rejects exotic-but-real rows (e.g., dry-matter basis) to keep the database clean and payload hashing exact.
- **Two encodings of one judgment:** the "what is useful" rule lives both in the prompt and in the priority penalties — duplication, but it keeps the screener's *ranking* aligned with the extractor's *decision*.
### Database — schema, RLS, RPCs, workflow engine *(Arciel)*

**File read for this section:** `apps/expert-annotator/migration.sql` (5,396 lines) — table definitions, constraints, the security-predicate functions, `claim_paper_stage_tasks`, the deterministic payload builders, the queue RPCs, and the RLS region. **43 commits.** Object counts: **31 tables, 26 functions/RPCs, 75 RLS policies, 32 RLS-enabled tables, 69 indexes, 2 triggers, 22 `SECURITY DEFINER` functions.** This one file is the contract between the Python pipeline and the React app.

#### Migration discipline — idempotent and self-healing
The whole file is written to run repeatedly against a live database without breaking. Columns are added with `ADD COLUMN IF NOT EXISTS`; `CHECK` constraints are dropped-and-recreated inside `DO $$ … $$` blocks that first query `information_schema.table_constraints` (so re-running never errors on an existing constraint); a legacy `food_items.food_fdc_id` of the wrong type is detected and converted in place. This is what lets `run-migration.js` re-apply the schema safely after every change — the alternative (numbered migrations) was rejected in favour of one convergent file.

#### Layer 1 — canonical reference model
`entities` (canonical foods, `UNIQUE canonical_name`), `entity_aliases` (`UNIQUE(entity_id, alias_name)`), `master_nutrients` (`UNIQUE standard_name`, `sort_rank`), `sources` (provenance + `source_metadata` jsonb), and `claims` — the normalized output: `entity × nutrient × source` with `amount`, `unit`, `basis` (default `per_100g`), `preparation_state`, `sample_size`, `confidence`, `extraction_method`, `status`. Foreign keys cascade so deleting a food cleans up its aliases and claims. This layer is read-shared across all users; only the service role writes it (via ETL).

#### Layer 2 — discovery model + the dedup engine
`papers` is the hub: `id SERIAL`, `doi` **and** `canonical_key` (DOI when a reliable external id exists, `canonical_key` for missing-DOI/cross-provider dupes), `filename`, `pdf_url`, `workflow_language CHECK IN ('en','tr')`, `search_gate_score`/`filter_score`, `ingest_status`, `audit_flag`, `rejection_reasons` jsonb, and the AI-routing summary columns (`current_stage_key`, `routing_status`, `routing_bucket`, `route_destination`, `latest_ai_extraction_id`, `routing_updated_at`). Three `CHECK` constraints pin the routing vocabulary to exact enums (7 statuses, 4 buckets, 5 destinations) — the same constants hard-coded in `ai_routing.py`, so the DB rejects any value the router doesn't know.

`paper_search_hits` is the idempotent discovery ledger. Its `hit_key` is an **md5 of `canonical_key|source|language|template|term|phrase|query`** computed in SQL; the migration backfills it for legacy rows, **deletes duplicates** with a `ROW_NUMBER() OVER (PARTITION BY hit_key)` window, then adds a `UNIQUE` index — so repeated crawls never create duplicate hit rows. `paper_search_batches` + `paper_search_batch_hits` store per-query-batch funnel counters (`results`, `search_gate_passed/rejected`, `filter_passed`, `duplicates`, `accepted`, `pdf_fetch_fail`, `pdf_validation_fail`) **separately** from hit evidence, so the feedback loop can score exact query batches by downstream yield without polluting the idempotent hit table. A backfill `INSERT … SELECT … GROUP BY` reconstructs legacy batches from existing hits.

#### Layer 3 — annotation model
`annotations` (`UNIQUE(paper_id, user_id)` — one session per user per paper, `status` draft/done/skipped), `food_items` (→ `entities`, `is_custom_food`, `raw_food_name`, `preparation_state`), `annotation_nutrient_values` (→ `master_nutrients`, `is_custom_nutrient`, `value`, `unit`, `basis`, `sample_size`, `confidence CHECK 0..1`, `metadata` jsonb), plus `paper_label_events` (audit history) and `paper_global_labels` (`definitely_no_data` with reason, `UNIQUE(paper_id, label)`). The custom-vs-canonical split (`is_custom_*` + nullable FK) is what lets a labeler record a food/nutrient the reference DB doesn't have yet without losing the mapping for ones it does.

#### Layer 4 — the workflow engine (it was rebuilt twice, the tables prove it)
The schema preserves all three generations:
1. **Slot model (legacy):** `reviewer_slots`, `reviewer_slot_members`, `paper_slot_assignments`, `paper_user_assignments`, `paper_assignment_submissions` — official/shadow reviewers per language.
2. **Conflict model (Huan, legacy):** `paper_conflicts`, `paper_conflict_resolutions`, and the `paper_conflict_candidates` **view** — a CTE that groups the latest submission per assignment, counts `distinct_decision_count`/`distinct_payload_count`, and surfaces only papers with ≥2 submissions that actually disagree, labelling each `decision_mismatch` / `payload_mismatch` / `decision_and_payload_mismatch`.
3. **General approval queue (current):** `paper_label_submissions` (immutable, `payload_hash`, `status` pending/accepted/superseded) and `paper_label_approvals` (`UNIQUE(paper_id)`, `correction_diff_json`). Final truth lands in `paper_review_outcomes` (`UNIQUE(paper_id)`, `resolution_source`, plus a later `truth_source_kind` distinguishing human vs `ai_model`).

A `BEFORE INSERT/UPDATE` trigger (`enforce_human_review_ready_assignment`) refuses to attach an assignment to a paper that isn't `human_review_ready` — a schema-level guard against routing bugs. Old slot tables are kept for audit only; the README/AGENTS forbid driving new work from them.

#### Layer 5 — AI routing tables
`ai_extractions` (raw_data, `normalized_payload_json`, `positive/negative_threshold_snapshot`, `routing_bucket`, `route_destination`, `audit_sampled`, `finalized_without_human`, `status`), `routing_stage_configs` (the data-driven stage table: thresholds, `fallback_model_names` jsonb-array with a `jsonb_typeof = 'array'` CHECK, `no_data_route_destination`, `model_input_mode` text/pdf), and `paper_stage_tasks` (`status`, `priority`, `attempt_count`, `last_error`, `UNIQUE(paper_id, stage_key)`). The seed `INSERT`s show the model history in the data itself: `gemini_flash_triage_v1` (`gemini-3-flash-preview`) was seeded then deactivated; `gemini_flash_db_payload_v2` (`gemini-3.5-flash`) is the final stage with `no_data_route_destination = 'provisional_skip'`.

#### The security model — least privilege over 31 tables
**75 RLS policies** on **32 RLS-enabled tables**, built on six `SECURITY DEFINER` predicate functions:
- `current_auth_email()` — the JWT email, lowercased.
- `current_user_has_cockpit_access()` — `cockpit_access OR tester_access`, active, matched by `auth_user_id` **or** email (so a profile works before the auth row links).
- `current_user_is_tester()`, and the key one-liner **`current_user_can_write() = NOT current_user_is_tester()`** — read-only tester access falls out of a single negation rather than being re-encoded per table.
- `current_user_has_cockpit_write_access() = cockpit AND can_write`, `current_user_can_approve_labels() = can_write AND can_approve_labels`.

Because these are `SECURITY DEFINER`, the RPCs can expose aggregates and queue slices without granting any authenticated user direct reads of `paper_stage_tasks`, `ai_extractions`, or other users' annotations. The **signup allowlist** is enforced by `hook_restrict_signup_by_email_allowlist(event jsonb)` — a `SECURITY DEFINER` auth hook granted only to `supabase_auth_admin`, with `EXECUTE` revoked from `anon`/`authenticated` and all table privileges on `allowed_auth_emails` revoked from the client roles, so the allowlist can be neither read nor bypassed from the browser. `upsert_reviewer_admin_config` even refuses to complete if it would leave **zero** active cockpit-write reviewers — you cannot lock the whole team out.

#### Concurrency primitive — `claim_paper_stage_tasks`
The single most important RPC for the automation: `SECURITY DEFINER`, requires `service_role`, and claims queued tasks with
```sql
SELECT id FROM paper_stage_tasks
WHERE status='queued' AND (p_stage_key IS NULL OR stage_key=p_stage_key)
ORDER BY attempt_count ASC, priority DESC, created_at ASC, id ASC
LIMIT … FOR UPDATE SKIP LOCKED
```
then flips them to `processing` and bumps `attempt_count`. **`FOR UPDATE SKIP LOCKED`** is what lets the five parallel GitHub Actions drain workers grab *disjoint* sets of tasks with zero coordination and zero double-processing — the entire parallel-worker design rests on this one clause. The `ORDER BY` is the retry-fair ordering (lowest attempts first) enforced at the database.

#### Deterministic payload builders (why AI output == human output)
`build_annotation_submission_payload(annotation_id, decision_kind)` assembles the canonical submission JSON straight from `food_items` + `annotation_nutrient_values`, with `normalize_submission_text()` (collapse whitespace), `round(value, 6)`, and a long deterministic `ORDER BY`. It produces **byte-identical structure** to the Python `normalize_ai_payload` — so a human submission and an AI extraction of the same data hash identically, which is what makes exact-match comparison and dedup work across the human/AI boundary.

`build_label_payload_diff(original, final)` is a full structural diff in SQL: it explodes both payloads into food-level and nutrient-level rows with composite keys, then computes `missing_foods`/`added_foods`/`missing_nutrient_rows`/`added_nutrient_rows` via `NOT EXISTS` anti-joins, plus decision-change flags and counts. Its output is stored as `paper_label_approvals.correction_diff_json` — the exact record of what the approver changed versus what the labeler submitted, which is the raw material for labeler-performance metrics.

#### Queue + cockpit RPCs
- `get_general_queue_papers` / `get_general_queue_cards` encode the precise "visible paper" predicate: `routing_status='human_review_ready'` **AND** non-empty `pdf_url` **AND** latest AI decision `has_data` **AND** `NOT EXISTS` (a final outcome, a pending/accepted submission, an open legacy assignment, or a `definitely_no_data` global label). `get_general_queue_cards` returns the whole queue — minimal card fields joined with the latest AI payload **and this user's annotation status** — as **one jsonb round-trip** (the performance redesign that replaced three separate fetches).
- `get_cockpit_ai_extractions` is deliberately **egress-slim**: it returns the normalized payload and only `raw_data->'normalization_summary'`, dropping the large raw model response/reasoning. AGENTS explicitly forbids reverting it to `select('*')` because that burns Supabase egress.
- `get_pipeline_ops_snapshot` (≈500 lines) backs the cockpit Pipeline funnel with stage-level queue/error aggregates, role-stable model-stage labels, and `model_stage_backfill` so historical direct Small→Strong papers count into the Medium stage.

#### Trade-offs
- **One convergent migration file** (not numbered migrations): simpler to reason about and re-apply, at the cost of a 5,396-line file with lots of defensive `DO` blocks.
- **Legacy tables kept, not dropped:** the slot/conflict generations remain for audit history, accepting schema bloat to preserve provenance.
- **Determinism enforced twice** (SQL builder + Python normalizer): duplicated ordering logic, but it's the only way the two producers of truth can be compared by hash.
- **General queue tolerates duplicate submissions** (no row-level claim/lock on papers): simpler concurrency, redundant labeling resolved at approval instead of prevented.
### Paper-discovery crawler v2 — Search → Filter → Acquisition *(Arciel)*

**Files read for this section:** `food_paper_crawler/crawler_v2.py` (2,215 lines), `ranking.py` (485), with the source adapters `europe_pmc.py`, `dergipark_source.py` (687), `search_sources.py`. **30 commits.** `FoodCompositionCrawlerV2` is a ~2,200-line orchestrator class with ~70 methods.

#### Architecture and why it's staged
`run()` executes **Search → Filter → Acquisition** so the expensive step happens last:
1. **Search** — metadata-only retrieval from Europe PMC / OpenAlex / Semantic Scholar (DergiPark for Turkish) via per-source query rendering.
2. **Filter** — a two-gate, purely *additive* relevance decision on title+abstract (no PDF downloaded yet).
3. **Acquisition** — only papers that pass the metadata filter get their PDF fetched, then a *stricter* full-text validation gate.

Downloading PDFs is slow and failure-prone, so filtering on cheap metadata first is the core efficiency decision. The run is **wall-clock bounded** (`_wallclock_reached()` against a `time.monotonic()` deadline, 2,400 s in scheduled ops); when the deadline hits it stops cleanly and still writes every accepted partial result + a manifest, so a GitHub Actions timeout never loses work.

#### The two-gate additive filter (`ranking.py` + `_search_gate_decision` / `_metadata_decision`)
The relevance logic is deliberately **additive with soft penalties — never a hard veto** (a design rule in AGENTS; `b895f8a` removed the old veto logic). A single negative phrase lowers a score; it never auto-rejects.

- **Search gate** (cheap pre-filter): composition phrase +0.9, food term +0.35, nutrient term +0.35, a `mg/100g`-style **unit regex** +0.7, food+nutrient combo +0.45; penalties for a missing abstract, `STRONG_NEGATIVE_SIGNAL_TERMS` (cement, concrete, radionuclide, nanoparticle, genome, body-composition, essential-oil…), `SOFT_NEGATIVE_TERMS` (clinical trial, review, broiler, rat, feed…), and language-scoped health-outcome terms. Accept if the score clears a threshold.
- **Metadata decision** (richer): the same lexical signals at higher weights **plus** three learned signals — a **per-source prior** (clamped), a **sentence-embedding similarity** to language-scoped anchor phrases (`embedding_scorer.score`, +1.45/+0.75 above threshold), and the **learned feedback n-gram score** (below). Acceptance is `score ≥ METADATA_ACCEPT_THRESHOLD`. Every contribution is logged as a `{code, text}` reason, so each accept/reject is fully explainable in the manifest.

`ranking.py` then re-validates the **downloaded full text** with a much stricter gate (`validate_pdf_text`): it strips reference sections (EN+TR markers) so bibliographies don't inflate hits, counts AOAC/HPLC/GC/ICP method evidence and `mg/100g` units, and requires `score ≥ 18` **AND** a table signal **AND** a food signal **AND** an overlap of ≥4 with a strong proximate-nutrient panel (moisture/protein/fat/ash/fibre/carb/energy/minerals). The loose metadata gate maximizes recall into acquisition; the strict full-text gate guards precision out of it. Matching is `bounded_contains` — a `(?<!\w)…(?!\w)` Unicode word-boundary regex, so the Turkish word "et" (meat) matches as a word and not inside "diet".

#### The learned feedback applied at crawl time (`_feedback_score`)
This is where the L2 loop closes back into the crawler. For each candidate it extracts title-only and title+abstract n-grams, looks each up in the language's learned `weighted_terms` (`title_net` / `ta_net` evidence produced by `update_terms.py`), multiplies by `filter_title_weight` / `filter_ta_weight`, **clamps per-term and total** so no single n-gram dominates, and logs the strongest contributors. Feedback is a *soft score only* — consistent with the no-veto rule. Learned query generation also pairs a rotated food/nutrient term with a high-confidence phrase from the matching language (`_build_learned_query`, `_build_concept_pool`), while evergreen base queries preserve breadth.

#### Dedup — never crawl the same paper twice
Before searching, `run()` builds `skip_keys = local terminal states ∪ live Supabase canonical_keys`:
- `_live_paper_skip_keys()` pages **every `papers.canonical_key`** straight from the Supabase REST API (1,000-row pages), so anything already queued / provisional-skipped / human-ready / finalized is skipped at the source.
- `_state_skip_keys()` reads local `paper_states` — terminal `accepted`/`rejected` decisions with the stage they were reached at. `_record_terminal_states()` writes these after each run, **including search-gate rejects** that never became candidates, so a metadata reject isn't re-fetched next run. (Per AGENTS, metadata-only `paper_search_hits` rejects are deliberately *not* used as global skip memory — only terminal `paper_states` and live `canonical_key` are, to keep the benchmark honest.)
Accepted PDFs are named by **identity** (`pmcid_*` / `doi_*` / hashed `canonical_key`) via `build_storage_filename`, not title slugs, so the file name is a stable dedup key too.

#### PDF acquisition — the genuinely hard part
Publisher PDFs fight back; `_download_candidate` → `_fetch_pdf_with_oa` → `_fetch_pdf` is a layered fallback ladder:
1. **PMC Open-Access package** (`_fetch_pdf_from_oa_package`): query the PMC OA API, parse the XML for `format="pdf"` links and `tgz` links; try the PDFs, else download the **`.tar.gz` and extract the largest `.pdf` member** (`_download_tgz_pdf` with `tarfile`). `ftp://` NCBI URLs are rewritten to `https://`.
2. **Direct fetch** (`_fetch_pdf`): urllib with a crawler User-Agent; verify the body starts with `%PDF`.
3. **On HTTP/URL error → `curl` fallback** with a full **browser User-Agent** (Chrome UA string) — many publishers block non-browser agents.
4. **If the response is HTML, solve a PMC proof-of-work**: `_solve_pmc_pow` parses `POW_CHALLENGE`/`POW_DIFFICULTY`/`POW_COOKIE_NAME` out of the page and brute-forces a **hashcash nonce** — incrementing `nonce` until `md5(challenge+nonce)` starts with `difficulty` zeros — then retries with the solution cookie. (A bot-wall defeated with an actual mining loop.)
5. **Else** scrape a nested `.pdf` href from the HTML and fetch that, else final `curl`.
A **size cap** (`max_paper_pdf_bytes`) rejects oversized PDFs; `_validate_downloaded_pdf` runs `pdftotext` and the strict `validate_pdf_text` gate; rejected files are deleted unless **audit sampling** (`_next_audit_flag`, every Nth reject) keeps them for manual QA.

#### Bilingual + sources
`crawler_v2` can split its query budget across independent English and Turkish workflows with separate phrases, anchors, weighted n-grams, concept ordering, and **language-scoped embedding/metadata scoring** (`normalize_language_text` handles Turkish casing). DergiPark was rebuilt (`dergipark_source.py`, 687 lines) as a **locally refreshed journal/article index** instead of the old global OAI slice. Current ops run English-only (`tr=0`, DergiPark skipped), but the whole bilingual path is retained and tested (`test_bilingual_pipeline.py`, 1,120 lines).

#### Output — a self-documenting manifest
`_build_run_summary` emits per-language, per-source funnel counts (`hits → search_gate_pass → metadata_pass → pdf_fetch_fail → pdf_validation_fail → accepted`) plus rejection counts by stage, the embedding config, the feedback phrase/anchor/weighted-term samples, and the DergiPark index coverage — so every run is auditable end to end.

#### Trade-offs
- **Recall-first metadata gate, precision-first PDF gate:** accept liberally into the (cheap) download decision, reject strictly after seeing the full text — costs some wasted downloads to avoid missing real papers.
- **No hard-negative veto:** robust to one stray phrase, at the cost of needing the multi-signal score to do the discriminating.
- **Brute-force PoW + curl fallback:** fragile to publisher changes and a bit slow, but recovers PDFs that plain urllib simply cannot get.
- **Live `canonical_key` paging every run:** an extra Supabase scan, traded for never wasting a download on a known paper.
### L2 feedback-learning loop *(Arciel)*

**File read for this section:** `food_paper_crawler/feedback/update_terms.py` (1,219 lines), with `feedback_config.py`, `supabase_terms.py`, `feedback_terms.py`. This is the closed loop that makes the crawler *learn* from human labels rather than relying only on a fixed lexicon.

#### The loop
```
human approvals (paper_review_outcomes) ──▶ log-odds n-gram scoring ──▶ latest.json
        ▲                                                                     │
        └──────────────── better-ranked next crawl ◀── crawler _feedback_score
```
Every run reads accepted human truth, recomputes which words/phrases predict a *useful* paper versus a *useless* one, and writes per-language weight pools that the crawler loads automatically on its next pass.

#### Truth selection — only accepted human decisions count (`build_labels`)
This is deliberately conservative:
- Positives/negatives come from `paper_review_outcomes` **only when `truth_source_kind = 'human_review'`** — `ai_model` outcomes are stored for provenance but **excluded** from learning, so the model never trains on itself.
- `decision_kind='has_data'` → **good**, `no_usable_data'` → **bad**.
- **Open conflicts are removed** from both sets (ambiguous truth doesn't teach).
- Legacy `paper_label_events` / `paper_global_labels` are used **only as a fallback** for older papers that have no resolved outcome (`row.paper_id not in resolved_paper_ids`).
Pending/superseded submissions never feed learning — only finalized truth.

#### The scorer — smoothed log-odds over three buckets (`build_scored_terms` + `log_odds`)
Papers split into **good**, **bad**, and **background** (everything labeled neither). For every n-gram, document-frequencies are counted in each bucket, **separately for title-only and title+abstract** (`count_bucket_terms`). Then four informative log-odds are computed with add-α smoothing:

```
log_odds(left, right, left_total, right_total, α)
  = log((left+α)/(left_missing+α)) − log((right+α)/(right_missing+α))
```

- `title_good = log_odds(term in good titles vs background titles)`
- `title_bad  = log_odds(term in bad  titles vs background titles)`
- `ta_good`, `ta_bad` = the same for title+abstract.
- **`title_net = title_good − title_bad`** and **`ta_net = ta_good − ta_bad`** — the net evidence that the term marks a *useful* paper, net of how much it also marks a *useless* one.

These two numbers are exactly what the crawler's `_feedback_score` multiplies by `filter_title_weight` / `filter_ta_weight`. **Why title and title+abstract are scored separately:** a concise high-signal phrase in a *title* (e.g. "proximate composition") is stronger evidence than the same phrase buried in an abstract, so the crawler can weight them independently instead of collapsing both into one number.

Design details that matter:
- **Background bucket** is the key to specificity: scoring good-vs-bad alone rewards common words; scoring each against the large *background* corpus (informative Dirichlet log-odds, the Monroe et al. method) surfaces terms that are genuinely *distinctive* of useful papers.
- **Add-α smoothing** prevents `log(0)` and tames rare-term noise.
- **Support threshold** (`min_total`) drops n-grams with too little evidence.
- **Seed composition phrases** get a small `seed_good_prior` — a *soft* prior, explicitly "not permanently merged winners" (README), so learned evidence can override the seed list over time.
- Ranking sorts by `|1.5·title_net + ta_net|` — title evidence weighted higher.

#### The derived pools (all per language, written to `latest.json`)
`build_scored_terms` is the core; `main()` then derives and writes, for **each of `languages.en` / `languages.tr`**:
- **`weighted_terms`** — `{title_net, ta_net, good, bad}` per term (the crawler's soft filter score).
- **`query_phrases`** (`_query_rank`/`select_query_phrases`) — top terms to pair with food/nutrient terms into new search queries.
- **`anchor_phrases`** (`_anchor_rank`) — phrases used as **embedding anchors** for the semantic similarity gate.
- **`pair_scores`** (`build_search_pair_feedback`) — observed yield of `source × term` pairs.
- **`batch_scores`** (`build_search_batch_feedback`) — yield of exact query batches, so good query batches are re-run and weak ones demoted.
- **`source_priors`** — per-source positive/negative bias.
- **`concept_scores`** (`build_concept_feedback`) — standalone concept-term yields.

So three distinct learned signals reach the crawler from one labeled corpus: **soft n-gram scores** (filter), **anchor phrases** (embedding), and **pair/batch/source/concept scores** (query generation and ranking).

#### When it runs
Daily ops refreshes feedback **only when it actually reaches the crawler/refill path** — `ensure_paper_stock.run_refill_cycle` runs `update_terms.py` immediately before search unless `--skip-feedback` is passed. Pure queued-AI draining does not refresh feedback (no new truth, no point). DergiPark refresh is gated behind an explicit Turkish deficit.

#### Trade-offs
- **Soft scores only, never hard rejects** — consistent with the crawler's no-veto rule; a learned-negative term lowers rank but can't block a paper a human might still want.
- **Needs label volume** — with few labeled papers the log-odds are noisy; the seed priors + background smoothing keep early behavior sane, and AGENTS lists "train the L2 classifier once label volume supports it" as a standing priority.
- **Background-corpus assumption** — treats unlabeled papers as a neutral reference, which is approximately (not perfectly) true.
### Daily-ops orchestration + GitHub Actions infrastructure *(Arciel)*

**Files read for this section:** `scripts/daily_ops_orchestrator.py` (2,358 lines — its full method map + the controller and drain entrypoints), `.github/workflows/daily-ops.yml`, `apps/expert-annotator/api/pdf.js` (102), with `scripts/ensure_paper_stock.py` (573) and `scripts/upload_to_supabase.py` (774). **27 commits** on the orchestrator alone.

#### The problem
Run a real, continuous data pipeline — crawl, upload, screen ~1500 papers/day, triage, extract — **for free**, on GitHub-hosted runners with a per-job time cap, against the Gemini free-tier daily quota, with no dedicated server. Every architectural choice here is downstream of that constraint.

#### Architecture — one serialized controller + a parallel drain matrix
`.github/workflows/daily-ops.yml` runs on a **5-minute cron** and launches two jobs:
- **`refill-controller`** — the *only* job allowed to crawl/upload/refill. It runs under a `concurrency: { group: daily-ops-refill-controller, cancel-in-progress: false }` so **at most one controller ever runs at a time** and a new tick never kills an in-flight crawl. It installs the *full* crawler stack (`requirements.txt` + `poppler-utils`) and keeps a stable HuggingFace cache.
- **`drain-workers`** — a `matrix: worker:[1..5]` of five jobs that run **in parallel and are no longer gated on the controller** (comment in the yml: "draining must continue even if the controller job fails"). They install the *lightweight* `requirements-worker.txt` (no `sentence-transformers`) and only drain already-queued model tasks. `workflow_dispatch` exposes a `workers` input, and every worker step is guarded by `if: matrix.worker <= fromJSON(inputs.workers)` so a manual run can scale down.

Five workers can run safely in parallel because claiming goes through `claim_paper_stage_tasks` with `FOR UPDATE SKIP LOCKED` (schema section) — each worker grabs a disjoint task set with zero coordination.

#### The controller logic (`run_daily_ops_controller`)
A single tick, not a long-running loop:
1. **Requeue stale tasks** for all three stages (returns `processing` rows older than 120 min to `queued`) — so a previous killed runner never strands papers.
2. **Count completed-today per stage** since that stage's **quota-day start**.
3. **Count active screening work** = queued + non-stale `processing` `paper_stage_tasks` (counted from executable rows, *not* paper routing summaries — stale `queued_for_ai` rows must not block refill).
4. Compute `controller_target = min(remaining_today, screening_active_target=150)` and `deficit = controller_target − active_screening`.
5. **Stop or refill** via an explicit decision tree: daily target reached → stop; deficit ≤ 0 (enough active work) → stop; controller deadline (75 min) reached → stop; paper-storage soft limit exceeded → stop; else **crawl `deficit` English papers in bounded 30-paper chunks** (`_run_screening_refill` → `ensure_paper_stock.run_refill_cycle`, which refreshes feedback terms then crawls+uploads), then re-measure active count and detect **source exhaustion** (refill didn't raise the active count).

The point of the *active target* (150) rather than a daily flood is the README's "keep paper stock low on purpose and refill as labeling proceeds, so each crawl benefits from newer feedback."

#### The drain logic (`run_daily_ops_drain`) — a resumable quota-day tick
Each worker tick:
1. Count completed-today per stage (against quota-day starts).
2. **If screening is below its 1500/day target and has queued tasks**, drain `min(screening_tick_tasks=20, remaining_today, queue_count)` Gemma tasks (`_tick_drain_stage`), then — with `--interleave-extraction` — also drain the downstream triage + final-Gemini slices (`_tick_drain_downstream`).
3. **If screening's queue is empty, still interleave the downstream drain** — this is the "drain Gemini when Gemma source is empty" behavior: queued Flash-Lite/Gemini candidates keep flowing even when there's nothing left to screen.
4. **If screening has hit its daily target**, drain a triage tick, then drain the final-Gemini stage up to its 20/day target, then run `_assign_new_human_ready_after_ai` — one final stock check so freshly human-ready papers appear in the labeling queue immediately.
Quota-exhausted and `ai_stage_configuration_error` are distinguished as stop reasons; the run returns a machine-readable summary (`mode`, `daily_completed` per stage, `screened`, `routed_to_gemini`, `gemini_used`, `human_ready`, `quota_exhausted_stages`, `stopped_reason`, …) that the workflow parses into a one-line log.

#### Quota-day accounting across two timezones
Each stage resets on its provider's schedule: **Gemma counts a UTC day**, both **Gemini stages count an `America/Los_Angeles` day** to match Google's RPD reset (`_stage_quota_day_starts` / `_quota_day_start_iso`). Completed-today counts come from `paper_stage_tasks` completion timestamps since that boundary, so the funnel spends exactly the daily budget and no more, regardless of when in the GitHub UTC schedule a tick fires.

#### Engineered for the free-tier ceiling
- **Lazy module loading** (`_LazyScriptModule`): the orchestrator imports heavy crawler/upload modules only when the controller path actually needs them, so drain workers (which never crawl) don't pay the import or the dependency install.
- **Three nested wall-clock budgets:** controller job 75 min, crawler 2,400 s (writes partial accepted results before being killed), each model call 300 s (`SIGALRM`) — so one slow paper or a long crawl can never blow the GitHub job cap.
- **Paper PDFs are source-URL/on-demand** (`OPENNUTRI_STORE_PDFS_IN_SUPABASE=0`): the controller skips paper-storage cleanup and the bucket soft-limit, because storing PDFs would blow the Supabase free storage/egress caps.

#### Supporting jobs
- `ensure_paper_stock.py` (573) — `run_refill_cycle`: refresh feedback terms, then crawl+upload until per-language targets are met; counts only `human_review_ready` papers with a normalized `has_data` payload and no outcome/submission as available stock.
- `upload_to_supabase.py` (774) — registers accepted papers by **canonical identity** (upsert on `canonical_key`, preserving any closed AI route or human outcome — never requeues a finalized paper just because the active model changed), upserts discovery hits by deterministic `hit_key`, persists per-query batch history, and **recovers concurrent duplicate-key races** by reusing the existing row and preserving its search-hit audit links (so two workers racing on the same paper don't fail the refill slice).

#### Same-origin PDF proxy (`api/pdf.js`, Vercel serverless)
Many publisher PDFs (and EuropePMC's `?pdf=render`) lack CORS headers, so PDF.js can't fetch them in-browser. This 102-line function fetches them server-side and re-serves same-origin, with real engineering around abuse and cost: **https-only**, **SSRF hardening** (rejects `localhost`/`.local`/`.internal`, IPv4 literals, IPv6), a 25 MB cap, a **`%PDF-` magic-byte check** (so it can't be used as a generic open proxy), a 25 s `AbortController` timeout, and a **1-year `immutable` Cache-Control** so each paper is fetched from the upstream host at most once and then served from the browser + Vercel edge.

#### Trade-offs
- **Lower recall for zero cost:** ~20 Gemini extractions/day is a deliberate ceiling; the priority funnel + `recover_gemini_candidates.py` make it acceptable.
- **A genuinely complex tick state machine** (controller vs drain vs combined tick, three stages, two quota timezones, interleaving) — the price of being resumable and idempotent inside a 5-minute window instead of a simple long-running daemon.
- **Controller/drain split** adds moving parts but means draining survives a controller failure and parallel workers scale throughput without locks.
### PDF evidence subsystem — table detection, overlays, durable cache *(Ayşegül / frontend)*

**Files read in full for this section:** `utils/PdfTextScanner.js` (2,323), `components/PdfViewer.jsx` (939), `utils/EvidenceLocations.js` (439), `utils/pdfCache.js` (107), `hooks/useEvidenceStatusCache.js` (101), `utils/evidenceStatusCache.js` (139), `utils/evidenceDedupStorage.js` (44). **27 commits** to the viewer + scanner. ~4,050 lines that do **document layout analysis in the browser** — the single hardest piece of code in the project, frontend or backend.

#### The core problem
PDF.js hands you a flat list of positioned glyphs — `{str, x, y, width, height}` — with no notion of a table, column, or paragraph. To (a) make nutrient names *inside tables* clickable and (b) paint an overlay over exactly the table/paragraph an AI value came from, the scanner must **reconstruct page structure from geometry**. `PdfTextScanner.js` is ~70 functions of computational geometry; `PdfViewer.jsx` renders and scales it; three cache layers make it fast and durable.

#### Pipeline (`buildPageEvidenceHighlightPlan`)
Per page: `extractPositionedTextItems → buildPageMetrics → detectColumnGutters → groupItemsIntoRows(gutter-aware) → finalizeRow→createFragment → buildTableRegionsAndCaptionFallbacks → buildParagraphBlocks`, then an ordered **matcher cascade** per AI evidence location.

#### Hard problem 1 — adaptive metrics (`buildPageMetrics`)
Every threshold derives from the page's own typography. `medianHeight` (glyph size) and `medianRowGap` drive `rowTolerance`, `fragmentGapThreshold`, `captionMergeGap`, `bodyGapThreshold`, `paragraphGapThreshold`, `bandMargin` — each `clamp()`-ed. The same code works on a 7 pt dense table and a 12 pt abstract with no hardcoded pixels.

#### Hard problem 2 — column detection by projection profile (`detectColumnGutters`)
Multi-column journals merged columns into one "paragraph." The fix is a classic **vertical projection profile**, hand-written: bin the x-axis at **2 pt**, record which y-bands have ink per bin; a **gutter** is a run of bins where ≤ 8 % of bands have content, ≥ 6 pt wide; keep only gutters with **content on *both* sides** (distinguishing a real inter-column gutter from page margins). `finalizeRow` then splits a row into fragments whenever the inter-glyph gap exceeds `fragmentGapThreshold` **or crosses a gutter**, so a left-column and right-column line at the same y never fuse.

#### Hard problem 3 — a per-fragment table/prose/narrative classifier (`createFragment`)
This is the engine's brain and was nowhere in my first pass. For each text fragment it computes a feature vector: numeric-token count, **sample-code** tokens (e.g. "T1", "Cv3"), abbreviation tokens, letter/lowercase/digit ratios, all-caps tokens, caption-prefix match ("Table N"), header tokens, unit labels, **major-cluster count** (`countMajorClusters`: gaps > 12 pt or wide whitespace), sentence punctuation, narrative connectors. From those it derives `looksProseLike`, `looksNarrativeLike`, and an integer **`tableScore`** (header +3, unit +2, all-caps-short +2, ≥2 numerics +2, digit-ratio +1, sample-code +1, ≥2 abbreviations +2, …) → `isTableLike = tableScore ≥ 2`. So each fragment is classified as table-cell vs prose vs caption from its own shape — a hand-built text classifier running per glyph-run.

#### Hard problem 4 — caption-anchored table-region growth (`buildCaptionBlocks` → `buildTableRegionForCaptionBlock` → `selectFragmentsForTableRow`)
Tables are found from their captions: caption-anchor fragments ("Table N") are merged across continuation lines (`extendCaptionBlock`), then the region grows **downward** row by row while rows overlap the caption band and stay within `bodyGapThreshold`. `selectFragmentsForTableRow` decides per row which fragments are body cells: it keeps `isTableLike` fragments, recognizes **header-like rows** (all short-header fragments under a word limit), and — crucially — once a data-like row is accepted it **keeps accepting later data-like rows even if they don't individually score `isTableLike`** ("Nd" or a lone "1.50" only scores 1 alone but is plainly table body in context). A region is `isConfident` only with ≥ 2 body rows OR bodyScore ≥ 4 OR a data-like fragment; otherwise it degrades to a **caption-only fallback** so a table-cited source still highlights *something* (the caption line) instead of nothing.

#### Hard problem 5 — paragraph blocks + interleaved-data merging (`buildParagraphBlocks`, `mergeAdjacentParagraphBlocks`)
Prose lines (excluding table items and document chrome via `isDocumentChromeFragment`) become paragraph candidates (`isParagraphCandidateSegment`: ≥ 5 words, ≥ 8 letters, lowercase ratio ≥ 0.35, punctuation, no sample codes), grown greedily into blocks then **clipped to the dominant column**. A second pass (`mergeAdjacentParagraphBlocks`) re-joins blocks that a stray interleaved numeric line split apart — it walks the rows between two same-column blocks and merges only if every gap is small and each intervening row is a `isParagraphInternalDataRow` (not a table, header, or chrome). This is why a paragraph quoting "22.04 ± 1.25 g/100 g" mid-sentence still resolves to one overlay.

#### Hard problem 6 — robust column clipping with MAD (`clipEntriesToDominantColumn`)
Even with gutters, PDF.js sometimes fuses two columns into one wide fragment. The clipper computes the **median** left/right edge and a **median absolute deviation (MAD)** spread, fences outliers at `3×MAD` (asymmetric — looser lower-right fence because paragraph last lines are legitimately short), and the code comments justify MAD over IQR ("IQR would absorb the outlier into q3"). Textbook robust statistics applied to layout.

#### Hard problem 7 — the source-quote matcher (3-tier cascade, `findSourceQuoteTextMatch`)
The AI's verbatim `source_quote` is located by: **paragraph-fragment match** → **search-fragment match** (`groupFragmentsByColumn` clusters fragments into columns so a windowed scan of up to 6 adjacent fragments is actually visually adjacent) → **row-window match** (up to 4 rows). Each tier falls back through `expandFragmentsToParagraph` / `expandRowsToParagraph` + `clipEntriesToDominantColumn` + `snapToNearestParagraphBlock` (reuse the nearest same-column block's id/bounds within 60 pt, so near-misses share a stable dedup identity). `normalizeSearchText` inserts whitespace at **digit↔letter boundaries** (Unicode-aware) on both sides so "10.80g/100 g" matches "10.80 g/100 g".

#### Hard problem 8 — the lying `page_hint` (`buildPageEvidenceHighlightPlan` + `resolvePrintedPageHint`)
The AI reports `page_hint` from extracted text, so on an offprint it gives the *printed* page (e.g. 1217 on a 5-page file). When `hintExceedsPages` (`pageHint > numPages`) the hint is made **non-gating** so caption/quote matchers can locate evidence on any page. And `PdfViewer.resolvePrintedPageHint` builds a **histogram of printed-vs-PDF page offsets** across every scanned page and maps the hint via the *modal* offset — so even a page whose header wasn't detected resolves to the right PDF page (`mapped_page_hint`).

#### Hard problem 9 — stable overlays + de-duplication (union-find, twice)
`unifyOverlappingParagraphMatches` runs **union-find with path compression** over a page's paragraph matches, collapsing any pair with ≥ 50 % horizontal overlap and a small vertical gap into one `regionKey` + unioned bounds. `buildStableRegionKey` keys by a stable `regionId` (else rounded bounds) so overlays don't flicker between renders. `EvidenceLocations.mergeQuoteOverlappingLocations` does a *second* union-find at the source level, merging two sources whose quotes share a **longest-common-substring ≥ 40 chars or ≥ 60 % of the shorter** (`longestCommonSubstringLength`, a two-row DP) — so three AI rows citing the same paragraph become one chip and one overlay.

#### `PdfViewer.jsx` (939) — headless scan + evidence-first rendering
Far more than a `<Document>` wrapper:
- **Self-hosted PDF.js worker** via `new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url)` — a Vite-bundled, content-hashed, same-origin asset instead of an unpkg-CDN serial dependency on the critical path.
- **Headless evidence scan:** a `useEffect` reads each page's text + intrinsic size straight from the parsed `PDFDocumentProxy` **without rendering its canvas**, yielding between pages with `requestIdleCallback`. This precomputes highlight plans for every page, sizes placeholders so scroll is stable before anything rasterizes, and learns which pages hold evidence.
- **Evidence-first rendering:** `activePages` = page 1 ∪ evidence pages ∪ (all pages once the scan completes), so page 1 paints instantly, evidence pages render next, the rest backfill — while DOM order stays 1..N with placeholders.
- **Coordinate transform:** `buildOverlayForRegionBounds` scales PDF bounds to rendered pixels (`scaleX = pageWidth/originalWidth`), **flips the Y axis** (PDF origin bottom-left → screen top-left via `originalHeight - pdfTop`), and applies type-specific padding (table 14 px, paragraph 6/2 px). `mergeNearbyOverlays` is a third merge pass at the pixel level. `scrollPageRegionIntoView` centers the overlay region in the viewport with exact scroll math.
- **`customTextRenderer`** injects clickable nutrient `<mark>`s only on items inside a detected table **and not inside a matched evidence region**; `bindNutrientHighlightInteractions` resolves the clicked mark through **three strategies** (`closest` → `elementsFromPoint` → `caretPositionFromPoint`) so clicks land even through overlapping text layers.

#### Three cache layers — durable, instant, shared
- **`pdfCache.js`** — PDF bytes in the **Cache Storage API** (not the volatile HTTP cache, which evicts 25 MB PDFs and which Supabase serves `no-cache`), keyed by URL, with an **LRU index in localStorage** (cap 40), a fresh `ArrayBuffer` per call (safe against PDF.js detaching on transfer), and `prefetchPdf` for idle warming. `QueueView` prefetches the **next two** queue papers during idle.
- **`evidenceStatusCache.js` + `evidenceDedupStorage.js` + `useEvidenceStatusCache.js`** — the resolved match for each source (regionKey + bounds + page) is cached **per paper, locally (localStorage, LRU 64) *and* remotely** in a Supabase `paper_evidence_dedup` table via the `merge_paper_evidence_dedup` RPC. On re-open, `applyCachedDedup` collapses sources that previously resolved to the same region **without re-scanning**, and `buildCachedEvidenceOverlays` paints overlays from cache **before** the headless scan even finishes — so a paper anyone has reviewed opens with overlays already in place.

#### Trade-offs
- **Precision over recall:** suppress highlighting rather than guess (a nutrient word in prose never becomes a stray click target); multi-item-fused table cells are a known follow-up.
- **All geometry client-side:** ~2,300 lines of layout analysis run in the browser — no server round-trip, works on any open-access PDF.
- **Heuristic, but adaptive:** thresholds are tuned against real journal PDFs across 27 commits, clamped and median-derived rather than fixed.

### Annotator app — orchestration, autocomplete, workflow, cockpit *(Ayşegül / frontend)*

**Files read in full for this section:** `pages/Annotate.jsx` (1,163), `utils/annotateHelpers.js` (574), `components/FoodAutocomplete.jsx` (664), `components/NutrientAutocomplete.jsx` (334), `components/NutrientPopover.jsx` (128), `components/FoodItemForm.jsx` (110), `components/AiDetailPanel.jsx` (118), `components/EvidenceStrip.jsx` (54), `views/{QueueView,ApprovalView,DashboardView,AllPapersView,PipelineOpsView}.jsx`, `utils/searchSessionLogger.js` (110), `hooks/useTheme.js` (75), `App.jsx`, `pages/Login.jsx`. ~4,300 lines.

#### `App.jsx` + `useTheme` — shell, auth, theme
`App` checks the Supabase session, detects a **recovery URL** (`type=recovery` in hash/query or `/reset` path, or a `PASSWORD_RECOVERY` auth event) and routes to `ResetPassword`, else `Login`, else `Annotate`. `useTheme` resolves `override || systemTheme`, listens to `prefers-color-scheme` via `matchMedia`, writes `data-theme` in a `useLayoutEffect` (no flash), and persists the override in **`sessionStorage` only when it differs from the system theme** — clearing it otherwise, so the app follows the OS by default and the override is per-session. `Login` does email/password, **Google OAuth**, and `resetPasswordForEmail`.

#### `Annotate.jsx` (1,163) — the orchestrator
Owns ~30 state hooks, all data fetching, view routing, and every labeling action. Its design is shaped by the same free-tier egress limit as the backend:
- **Parallel boot, no waterfall:** the queue loads on mount in parallel with the reviewer-profile sync (`sync_reviewer_profile` RPC) rather than after it; the shell paints immediately (no full-screen gate).
- **One-RPC queue with a versioned fallback:** `refreshQueue` calls `get_general_queue_cards` (lean cards + latest AI payload + this user's annotation status in one round-trip); if the RPC isn't deployed (`PGRST202`) it transparently falls back to `loadQueueItemsLegacy` (three queries: papers RPC + AI extractions + annotations).
- **Lazy cockpit:** `refreshCockpit` (10 parallel queries) runs **only on first visit to a cockpit tab** (`COCKPIT_DATA_VIEWS`), not on login, so cockpit accounts still get a fast Queue.
- **Idle food-catalog load:** the full `entities` catalog is fetched **paginated (1,000-row batches) during `requestIdleCallback`**, so the heavy autocomplete data never blocks first paint.
- **AI-prefill without overwrite (`loadAnnotation`):** a queue paper with no saved draft opens with its latest `normalized_payload_json` converted to editable rows via `buildFoodItemsFromPayload`, recording the source extraction id in `aiPrefillSources`; an existing draft/submission is loaded from the DB instead and **never overwritten**.
- **Submit + approve paths:** `saveAnnotation` validates (≥ 1 food item; ≥ 1 nutrient row for a final submit), writes annotation + food/nutrient rows (`saveAnnotationRows`: upsert annotation, delete-then-insert children), logs a `paper_label_events` row, and calls `submit_general_label`. `approveSelectedSubmission` (approvers only) writes the corrected rows and calls `approve_label_submission`. Every write is **test-mode aware** — in test mode it appends to a local event log instead of touching Supabase.
- **Help + suggestions:** `submitHelpRequest` builds a `buildGeneralHelpContext` record (paper + AI + reviewer + draft food items) into `backlog_review_items`.

#### `annotateHelpers.js` (574) — the shared brain
Two pieces are substantial:
- **Payload normalization** (`normalizeFoodItem`, `buildFoodItemsFromPayload`, `isValidFoodItem`, `normalizeOptional*`) — the client-side mirror of the SQL `build_annotation_submission_payload` and the Python `normalize_ai_payload`. The **same shape on all three sides** is what makes AI output, human drafts, and stored truth interchangeable and hash-comparable.
- **The pipeline funnel** (`buildPipelineSteps`, `formatModelSpecification`, `getPipelineModelStageViews`) — builds the cockpit's 10-stage funnel (search → filter → upload → small/medium/strong start+kept → human) with **role-stable labels** (`Small model (Gemma 31B)`), choosing batch counts over hit counts when available, and applying the **legacy Medium-stage backfill** (`legacy_direct_strong_without_medium`) so historical Small→Strong papers don't make the middle stage start at zero. `formatModelSpecification` maps model ids to display names with regex fallbacks so a model swap changes only the spec in parentheses. Plus `getPublicPdfUrl` (routes every external PDF through the `/api/pdf` proxy for CORS + immutable cache), `getAiPrefillStats`/`getNormalizationSummary`, `countCorrectionItems` (renders `correction_diff_json`), and the status/routing formatters.

#### `FoodAutocomplete` + `NutrientAutocomplete` — domain-tuned IR on top of Huan's fuzzy engine
Both import Huan's `fuzzyMatch` (tokenizer, inflection, banded Levenshtein) and add a weighted scorer. `scoreFoodMatch` (664-line component) ranks over canonical name, an extracted base name, and aliases:
- Exact = +2000/+1700/+1600; prefix = +900/+1200/+800; first-token = +180/+260/+180.
- **Per-token relation scoring** — `exact`/`derived`(stem)/`fuzzy`(edit-distance) at different weights, **boosted for single-word "generic" queries**.
- Coverage +260 if all tokens match, −180 per unmatched, −35 × earliest position; length penalties to prefer concise base names.
- **Whole-food disambiguation:** for generic queries, penalize `PROCESSING_WORDS` (canned/dried, −55 each), processed-primary pairs (−180), `babyfood`/`restaurant` (−180), derived-prefix false friends (−140); reward `WHOLE_FOOD_HINTS` and base-name matches (+220) — so "apple" surfaces *Apple, raw* over *Apple juice, canned*. A generic query with no useful token overlap is hard-rejected (−9999).
- **Data path:** when the in-memory catalog is loaded it ranks locally; before that it runs a **two-query Supabase strategy** (a prefix `ilike` of token variants + a broad `ilike`) merged and ranked. Debounced 250 ms, full keyboard nav, custom-food on blur/Enter. `NutrientAutocomplete` mirrors this (alias-weighted, skips "proximates"/"minerals"/"do not use") and maps units via `formatUnit`. Both log resolution to `search_sessions`.
- **`searchSessionLogger`** records each query step + a snapshot of shown options, persists a session on resolve/abandon to `search_sessions` (or a local event in test mode), and **self-disables** if the table is missing (`PGRST205`). This is the search-UX telemetry feeding model/UI work.

#### The clickable bridge (`NutrientPopover`, `FoodItemForm`)
A click on a highlighted nutrient in the PDF opens `NutrientPopover`, which **positions itself viewport-aware** (below the anchor, clamped to the viewport, flipped above if no room), focuses the value input, closes on Escape/outside-click, and emits a nutrient row that `handlePdfNutrientAdd` appends to the first food item (deduped by id). `FoodItemForm` composes `FoodAutocomplete` + dynamic nutrient rows + `NutrientAutocomplete` into one food card.

#### The views (8, extracted from a once-monolithic `Annotate.jsx`)
- **`QueueView`** — the labeler workspace: `PdfViewer` + `FoodItemForm`s + `EvidenceStrip`, builds evidence locations from the current rows (falling back to the AI payload), drives the durable evidence-status cache, auto-focuses the first evidence on load, **prefetches the next two PDFs on idle**, and the action bar (Ask for Help / No Usable Data / Save Draft / Submit Reviewed Data) with a read-only banner for testers.
- **`ApprovalView`** — side-by-side `PayloadSummary` (original labeler submission) vs an **editable** Reviewer Final Payload, decision select, approval note, gated to approvers (read-only preview otherwise).
- **`DashboardView`** — labeler-performance metrics computed client-side from submissions + approvals (submitted/pending/accepted/**corrected**/superseded/**correction items** via `countCorrectionItems(correction_diff_json)`), plus a per-submission "mistake detail" table.
- **`AllPapersView`** ("Useful Papers") — routing/AI/submission/approval/outcome table filtered by `shouldShowPaperInUsefulOverview` (hides provisional skips), with an expandable **`AiDetailPanel`** showing confidence, accepted/input rows, DB-vs-custom food/nutrient counts, the **rejection-reason histogram**, the DB-compliant rows, and the normalized JSON — exactly the normalization summary, *not* the model's reasoning.
- **`PipelineOpsView`** — renders `buildPipelineSteps` as a funnel (bars, % retained, dropped counts) plus a "Right Now" grid of per-stage queued/processing counts and human-ready/approval/failed, with a time-range filter.
- Plus `ReviewerAdminView`, `SuggestionsReviewView`, `MySuggestionsView`.

#### Trade-offs
- **Triple-encoded payload shape** (JS + SQL + Python): duplicated normalization kept in lockstep so the three producers of truth stay comparable.
- **Egress-driven architecture:** one-RPC queue + lazy cockpit + idle catalog load + slim cockpit projections — more client coordination in exchange for staying inside the Supabase free tier.
- **Heuristic, weight-tuned ranking:** the autocompletes are tuned constants rather than a learned model — fast and debuggable at this catalog size, hand-maintained.

### Huan's features — read at the source *(Duc Huan Ngo)*

**Files read for this section:** `utils/fuzzyMatch.js` (162), `components/SuggestionModal.jsx` (279), `pages/ResetPassword.jsx` (145), plus his SQL in `migration.sql` (`backlog_review_items`, the `suggestion-attachments` bucket policies, `paper_conflict_resolutions` + `paper_conflict_candidates`). **23 `landeryt` commits.** Reading the actual code raises the assessment of his work above what the raw line count (~1,600 net) suggests — two of his files are *infrastructure that other features depend on*.

#### 1. `fuzzyMatch.js` — a real fuzzy-match library that powers both autocompletes
This is the most undervalued Huan file. It is the shared tokenization + approximate-matching engine that **`FoodAutocomplete` and `NutrientAutocomplete` both import** — the ranking described in the frontend app section sits on top of it. It contains genuine algorithm work:
- **Banded Levenshtein** (`levenshteinDistance`) — two-row rolling arrays, an early-exit `Math.abs(aLen-bLen) > maxDistance` guard, and a per-row `minInRow > maxDistance` bail-out so it stops as soon as the edit distance provably exceeds the allowed band. O(n·band) instead of O(n·m).
- **Damerau adjacent transposition** (`isSingleAdjacentTransposition`) — catches "abc"↔"acb" typos that plain Levenshtein scores as distance 2.
- **Length-scaled tolerance** (`getAllowedFuzzyDistance`) — 0 edits under 4 chars, 1 under 8, 2 at 8+, so short words aren't over-matched.
- **Inflection/stemming** (`normalizeToken`) — `ies→y`, `oes→o`, trailing-`s` removal with `ss`/`us`/`is` guards, plus an `IRREGULAR_TOKEN_MAP` (mice→mouse, feet→foot…).
- **A relation cascade** (`findTokenRelationIndex`) returning `exact → derived → fuzzy`, which is exactly the relation tiering the food/nutrient scorers weight differently.
This closed BACKLOG §8 and the dependent §9 (fuzzy in PDF highlight). It is small in lines because it is dense, reusable algorithm code.

#### 2. Suggestions system — a careful full-stack feature
`SuggestionModal.jsx` plus his SQL is a complete vertical slice with real engineering judgment:
- **Client-side validation:** a 7-type image MIME allowlist, max 5 images, 10 MB each, dedup by `name+size+lastModified`, filename sanitization.
- **RLS-aligned storage paths:** files upload to `${user.id}/${timestamp}-${i}-${name}` — a **per-user folder**, which is precisely what his four `storage.objects` policies enforce via `storage.foldername(name)`. The UI and the security policy were designed together.
- **Transactional upload-then-insert with rollback:** uploaded storage objects are tracked in `uploadedStorageObjects`; if the subsequent `backlog_review_items` insert throws, the modal **deletes the already-uploaded files** so a failed submission never leaves orphaned objects in the bucket. That is the kind of cleanup most student code skips.
- **Test-mode aware:** in local-only mode it records the suggestion to `appendTestEvent` instead of touching Supabase.
- **His backend:** the `backlog_review_items` table (role-based RLS via `current_user_has_cockpit_access()`), the **private `suggestion-attachments` bucket** (10 MiB limit, image-MIME allowlist, four view/upload/update/delete policies with per-user containment), and the role-split (labelers submit + track in `My Suggestions`; cockpit triages in `Suggestions`, opening images from **signed URLs at view time**).

#### 3. Reset-password page — a real auth-bug fix
`ResetPassword.jsx` fixes a genuine defect: Supabase recovery links used to silently log the user in. His version parses `access_token`/`refresh_token` **out of the URL hash**, calls `supabase.auth.setSession`, validates the recovery session (clear error if expired), enforces password rules (match + ≥8 chars), calls `updateUser`, and **cleans the tokens out of the URL** with `history.replaceState` before returning to login. Correct session handling, not a toy form.

#### 4. Conflicts system (legacy) — table + SQL view + UI
He built `paper_conflict_resolutions` and the `paper_conflict_candidates` **view** (a CTE that aggregates the latest submission per assignment and flags `decision_mismatch` / `payload_mismatch` / `decision_and_payload_mismatch`), wired into `Annotate.jsx` with a "Choose This" picker. Fully delivered; later superseded by Arciel's general approval queue — normal architecture evolution, the feature shipped and worked for the model that existed then.

#### 5. Theme system, infinite scroll, dev/tester read-only
- **Theme centralization** (`cbf61ad`, `341b40e`): lifted theme into `App.jsx`, follows OS/browser preference when no override, fixed PDF dark mode.
- **Infinite PDF scrolling** (`4ade833`): replaced prev/next paging with continuous scroll, touching `PdfTextScanner.js` so highlight matching stayed correct across streamed pages.
- **Dev/Tester read-only access** (`9f18a56`): a small (+13/−6) but correctness-critical predicate change so `tester_access=TRUE` accounts can read admin/cockpit tabs (except Pipeline) while every mutation stays blocked.

#### Honest assessment
Huan's ~1,600 net lines under-represent the contribution because two of his files are **load-bearing infrastructure** (the fuzzy-match engine powering both autocompletes; the suggestion vertical with its own table, bucket, and four security policies) and one is a real **auth-bug fix**. Full-stack features where a wrong RLS predicate leaks private data — and where the code actually rolls back partial failures — are a harder category than the line count shows.
### Reference-data ETL + test suite *(Arciel)*

#### USDA → Supabase ETL
**Files read:** `etl_usda_to_opennutri.py` (227), `etl_sr_legacy_to_opennutri.py` (343). Two loaders seed the canonical reference layer from USDA FoodData Central CSVs into `entities` / `entity_aliases` / `master_nutrients` / `sources` / `claims` over the Supabase REST API:
- `read_csv` streams the FoodData Central dumps; `parse_preparation_state` **derives the preparation state from the food description text** (raw/cooked/dried…) so claims carry a usable `preparation_state` instead of an opaque label.
- `rest_insert(table, data, conflict_col)` does an **upsert keyed on a conflict column**, so re-running the ETL is **idempotent** — a second load updates rather than duplicating, and the reference IDs stay stable for the foreign keys in `claims`/`food_items` to point at. (README documents deterministic UUIDs for the SR-Legacy seed so the same source row always maps to the same `entities.id`.)
- The seed run is logged to `migration.log` / `migration_run.log`.

This is the layer that turns a public nutrition dataset into OpenNutri's canonical foods/nutrients, which the AI normalizer and the autocomplete then resolve against.

#### Test suite — coverage concentrated on the dangerous code
**128 Python test functions plus 35 frontend test blocks, 5,617 tracked test lines**, deliberately weighted toward the logic that can silently corrupt data or burn quota:

| File | Tests | Lines | Focus |
| --- | --- | --- | --- |
| `tests/test_ai_routing.py` | 60 | 2,469 | normalization, routing, thresholds, priority, retry classification |
| `tests/test_bilingual_pipeline.py` | 32 | 1,120 | EN/TR crawler gates, language scoping |
| `tests/test_daily_ops.py` | 30 | 983 | queue counting, refill, quota-day ticks |
| `tests/test_pdf_page_markers.py` | 6 | 73 | `===== PDF PAGE N =====` injection |

The `test_ai_routing.py` names read like a specification of the invariants documented in the AI-cascade section, each pinned by a test:
- **Normalizer determinism:** `normalize_ai_payload_matches_human_shape`, `orders_and_rounds_like_submission_contract` — proves AI output is byte-comparable to a human submission.
- **Unit policy:** `standardizes_supported_units_and_drops_unsupported_rows`, `accepts_explicit_fresh_wet_as_is`, `turns_empty_standardized_rows_into_no_usable_data`.
- **ID resolution safety:** `accepts_exact_db_ids_when_names_match`, `rejects_stale_or_mismatched_db_ids`, `preserves_custom_foods_and_nutrients_without_matches`.
- **Routing:** `bucket_classification_uses_separate_positive_and_negative_thresholds`, `threshold_one_disables_ai_auto_finalization`, **`audit_sampling_is_deterministic`**.
- **JSON-shape salvaging:** `unwraps_single_result_object_array`, `top_level_array_response_is_treated_as_candidate_rows`.
- **Priority funnel:** `followup_priority_rewards_composition_evidence_and_soft_penalizes_outcomes`, `uses_unsupported_raw_rows_as_screening_signal`.
- **Retry classification:** `blank_exception_text_preserves_type_repr_and_retry_classification` — even an empty SDK exception is correctly classified.
- **Queue predicates:** `fetch_available_counts_only_counts_human_review_ready`, `excludes_pending_general_submissions`, `general_queue_stock_does_not_create_reviewer_assignments`.
- **Feedback truth:** `build_labels_excludes_ai_model_outcomes` — the model never trains on itself.

Frontend unit tests cover the geometry engine too: `PdfTextScanner.test.js` (655), `EvidenceLocations.test.js` (225), `evidenceStatusCache.test.js` (92).

#### Trade-off
These are behavior/unit tests against pure logic (normalization, routing, scoring, gates) rather than full live-API integration tests — fast and deterministic in CI, but they mock the model/DB boundary, so the live Gemini/Supabase contract is validated by the offline harnesses (`flash_lite_triage_experiment.py`, `probe_model_file_input.py`) instead.

## 7. The five hardest problems (cross-cutting)

1. **Reconstructing document structure from PDF glyphs (frontend).** No table/column/paragraph primitive exists; `PdfTextScanner.js` does projection-profile column detection, adaptive metrics, MAD-robust column clipping, caption-anchored table regions, union-find chip de-duplication, and content-driven matching that survives a lying `page_hint`.
2. **A reliable 3-model AI cascade on a fixed free quota (backend).** One shared contract across three models, four salvaged JSON shapes, a deterministic normalizer whose output is hash-comparable to human submissions, native-PDF page accuracy with the measured "Gemma times out on PDF" constraint encoded, and a priority funnel that spends ~20 Gemini calls/day on the best of ~1500 screened papers.
3. **Running real automation on free infrastructure (backend).** A serialized controller + 5 parallel drain workers on a 5-minute GitHub Actions cron, `FOR UPDATE SKIP LOCKED` atomic claiming, per-stage quota-day accounting across two timezones, nested wall-clock budgets, partial-result writes, and retry-fairness so one bad paper can't monopolize the queue.
4. **A correct multi-principal security model (backend).** 75 RLS policies and 22 `SECURITY DEFINER` RPCs giving labelers, cockpit, testers, and the service role exactly the right surface across 31 tables, with read-only-tester falling out of a single `NOT is_tester()` negation and a guard that the team can never be locked out.
5. **A learning crawler + a learning library (backend + Huan).** Smoothed log-odds n-gram scoring over good/bad/background buckets closes the loop from human truth to the next crawl; Huan's banded-Levenshtein + inflection engine powers both autocompletes; and the crawler defeats publisher bot-walls with an actual MD5 proof-of-work solver.

## 8. Contributor Assessment Summary

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

Most defensible metrics: 7 all-ref commits; all-ref filtered git-author churn `+6,624/-88`; 14,310 current frontend lines under the final exclusion rules; 10,334 lines in the principal queue/PDF/autocomplete/view files listed above. Current-mainline path churn is larger because later frontend evolution and integration were committed through shared/integration commits.

### Arciel Aliognis Baez Zamora

Primary evidence: `baezarciel` and `ArcielB` commits, backend/ops/schema/docs ownership.

Assessment-facing achievements:

- Built the Supabase database contract, RLS model, reviewer truth workflow, and queue/approval/cockpit RPCs.
- Built the crawler, additive relevance scoring, feedback learning, and paper upload/routing pipeline.
- Built the three-stage AI cascade with normalization, retry fairness, quota safety, PDF/text model input modes, and follow-up prioritization.
- Built unattended daily ops on GitHub Actions with controller/drain worker split and source-URL PDF strategy.
- Performed integration, documentation, project management, and live ops hardening.

Most defensible metrics: 213 `baezarciel` commits plus the initial `ArcielB` commit; filtered `baezarciel` churn `+66,207/-16,985` with work-report files excluded from the project-code metric; backend/ops/schema bucket 31,302 lines.

## 9. Expanded Assessment Ledger

This section carries forward the detailed v2 assessment ledger requested for defense/evaluation. It is organized by workstream rather than by raw commit order because the project repeatedly replaced earlier architecture with better production versions. For each item, the ledger records:

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
- Current frontend tracked lines under the refreshed final metric: 14,310.
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
| 2026-06-05 | `fd1b930`, `bf89977`, `1a8d1cf`, `6607ac9`, `4a8ec8` | Arciel/Codex documentation work | Work reports v1/v2 and frontend report deepening. | Created assessment artifacts and corrected attribution evidence. |

## 11. Evidence Commands Used for This Final Version

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
