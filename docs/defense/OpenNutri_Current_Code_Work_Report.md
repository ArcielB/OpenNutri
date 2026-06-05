# OpenNutri Current Code Work Report

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
