# OpenNutri — Full Work Report (Master)

*Comprehensive, evidence-based account of everything built for OpenNutri, who built it, how, why, what made it hard, and how it was solved.*

**Prepared:** 2026-06-05 · **Repository HEAD:** `ac8bf72` · **Activity span:** 2025-12-19 → 2026-06-05 (≈5.5 months)
**Source of truth:** the git history of this repository (`git log --all --numstat`), the live schema (`apps/expert-annotator/migration.sql`), `README.md`, and `AGENTS.md`. Nothing in this report is invented; every claim is traceable to a commit, file, or line count.

---

## 1. Team and how to read the attribution

| Member | Student no. | Primary area in this report |
| --- | --- | --- |
| Duc Huan Ngo | 221229075 | Suggestions system, conflicts, theme, reset-password, fuzzy match, infinite scroll, tester access |
| Ayşegül Doğan | 221229031 | Annotator frontend (React) — UI, PDF viewer, highlighting, autocomplete, views |
| Arciel Aliognis Baez Zamora | 221229078 | Database/RLS, paper-discovery crawler, AI extraction cascade, daily-ops automation, infra, docs |

### Attribution method (read this before the numbers)

The repository has four git identities: `baezarciel` + `ArcielB` (both Arciel), `landeryt` (Huan), and `ayseguldogan2706-cpu` (Ayşegül). Because day-to-day integration, deployment, and most pushes ran from Arciel's machine, raw commit authorship under-represents the agreed division of labor. Work is therefore attributed by the team's standing split:

- **Every `landeryt` commit → Huan**, wholesale, regardless of whether it touched frontend or SQL.
- **Every other commit is split by file area:** lines under `apps/expert-annotator/src/**` (plus the HTML/Vite shell) → **Ayşegül (frontend)**; everything else — schema, AI/pipeline, infra, ETL, tests, docs → **Arciel (backend)**.

This is the same rule the team has used since the first internal breakdown; this report re-derives it from scratch against the current HEAD and corrects two accounting issues in the older draft (Ayşegül's original MVP lived at the repo root before it was reorganized into `apps/expert-annotator/`, and the now-archived `legacy/` snapshot must not be double-counted).

### Headline numbers (code only; excludes USDA CSV dumps, `package-lock.json`, generated DOCX/PDF/PPTX/PNG)

| Member | Commits (authored identity) | Lines added | Lines deleted | Net new | Gross-add share |
| --- | --- | --- | --- | --- | --- |
| **Arciel** | 208 | **+47,682** | −9,098 | **+38,584** | ~66% |
| **Ayşegül** | 7 own + frontend area | **+22,681** | −7,581 | **+15,100** | ~31% |
| **Huan** | 23 | **+2,188** | −582 | **+1,606** | ~3% |

The share by *current* shipping code (what runs in production today, a fairer "result" metric than churn) is roughly: **~13,500 lines of frontend** (Ayşegül's surface, less Huan's ~450 lines of suggestion/reset/fuzzy code), **~25,500 lines of Python pipeline + 4,900 lines of tests + a 5,396-line schema** (Arciel), and **Huan's distinct feature surfaces** (suggestion attachments, conflicts, fuzzy match, reset-password page). Total tracked source: **47,198 lines**.

> Why "net new" is smaller than "added": OpenNutri was rewritten in place several times — the crawler went v1 → v2, the labeling model went from slot-assignment → general approval queue, the AI path went from single-model → 3-stage cascade, and `Annotate.jsx` was decomposed into eight view files. Churn (lines added) measures *effort*; current size measures *result*. Both are reported because both are real.

---

## 2. What OpenNutri is

OpenNutri is a **food-composition data platform**: it discovers scientific papers that contain real food/product nutrient tables, uses an AI cascade to pre-extract candidate composition rows, and gives human experts a precision labeling UI to verify them into normalized, provenance-backed nutrition facts.

Two halves, one Supabase Postgres database between them:

1. **Annotator web app** (`apps/expert-annotator/`, React 19 + Vite, deployed on Vercel) — auth, a shared labeling queue, a PDF viewer with table-scoped highlighting and AI-evidence overlays, an approval workflow, and cockpit dashboards.
2. **Python data pipeline** (`services/data-pipeline/`) — a multi-source crawler, a feedback-learning loop, a 3-stage LLM extraction cascade (Gemma → Gemini Flash-Lite → Gemini Flash), and a daily-ops orchestrator that runs unattended on **GitHub Actions every 5 minutes**.

The canonical data model separates **reference facts** (`entities`, `master_nutrients`, `sources`, `claims`) from the **human/AI workflow** (`papers`, `annotations`, `paper_label_submissions`, `paper_review_outcomes`, `ai_extractions`, …), so every nutrition fact is traceable from discovery → extraction → human approval → claim.

### End-to-end data flow

```
USDA CSV ──ETL──▶ entities / master_nutrients / sources / claims  (reference layer)

crawl (Europe PMC, OpenAlex, Semantic Scholar)
  └─▶ Search → Filter (lexical + embeddings + learned feedback) → Acquisition (PDF)
        └─▶ upload_to_supabase  ──▶ papers (+ paper_search_hits / batches)
              └─▶ Gemma proof-extraction (≈1500/day, text)        [Small model]
                    └─▶ Gemini Flash-Lite triage (≈500/day)        [Medium model]
                          └─▶ Gemini Flash final extraction (≈20/day, native PDF)  [Strong model]
                                └─▶ human_review_ready  ──▶ general labeling queue
                                      └─▶ submission → Arciel approval → paper_review_outcomes
                                            └─▶ feedback loop (L2) re-scores the next crawl
```

---

## 3. Timeline (phases)

| Phase | Dates | Headline work |
| --- | --- | --- |
| 0 — Repo bootstrap | 2025-12-19 | Repo created; push-access verified |
| 1 — Annotator MVP | 2026-03-02 → 03-03 | Ayşegül: annotation tool, Google OAuth, theme, flexible nutrient model, food/nutrient autocomplete, first PDF highlight |
| 2 — Pipeline import + crawler v1 | 2026-03-09 → 03-22 | Arciel: snapshot the harvester/crawler/embeddings codebase, USDA ETL, README, balanced rule-based gating, audit sampling; Huan: theme centralization, reset-password page |
| 3 — Feedback learning + crawler v2 | 2026-03-20 → 03-30 | Arciel: L2 dual-embedding scoring, cumulative soft n-gram feedback, field-aware learning, bilingual split, DergiPark journal index, test mode, handoff/AGENTS docs |
| 4 — AI integration + workflow | 2026-04-13 → 05-02 | Arciel: Gemini Flash triage/extraction, assignment-driven labeling → general approval queue, staged AI-routing gate; Huan: conflicts system, suggestions system + image attachments |
| 5 — Cascade + cockpit + daily ops | 2026-05-03 → 05-20 | Arciel: Gemma screening cascade, daily-ops orchestrator (recurring ticks, quota pacing), pipeline cockpit, coordinate-based PDF evidence overlays, `Annotate.jsx` → `views/` refactor; Huan: dev/tester read-only, fuzzy match |
| 6 — Hardening + 3-model cascade | 2026-05-27 → 05-31 | Arciel: controller/drain-worker split, Flash-Lite triage stage, auth-RLS hardening, source-URL PDFs + same-origin proxy, native-PDF Gemini with true page numbers |
| 7 — Performance + cost | 2026-06-04 → 06-05 | Arciel: durable browser PDF cache, lean queue RPC, egress reduction, evidence-page-first rendering |

---

## 4. Subsystem-by-subsystem work log

Each entry: **what / why / how / what made it hard / how solved / when / size / trade-offs.**

### A. Annotator frontend — React labeling app *(Ayşegül)*

#### A1. Annotation tool MVP — `7c2d372` (2026-03-02, +5,010)
- **What:** the first working app — `App.jsx`, `Login.jsx`, `Annotate.jsx`, `FoodItemForm.jsx`, `PdfViewer.jsx`, `supabaseClient.js`, a 695-line `index.css`, and the initial `supabase_schema.sql`.
- **Why:** nothing existed; this is the skeleton everything else hangs on.
- **How:** React + Vite SPA against Supabase (auth + Postgres). Email/password login, a paper view, a per-food form, a basic PDF render.
- **Hard part / trade-off:** establishing the React/Supabase/Vite toolchain and a schema good enough to label against, before the data model was settled. The schema was deliberately simple and later superseded by Arciel's 5,396-line `migration.sql`.

#### A2. Auth + theme + suggestion scaffold — `614a82c`, `6245a17` (2026-03-02, +369)
- Google OAuth sign-in button; light/dark theme toggle (`useTheme.js`); first `SuggestionModal.jsx` and forgot-password entry.

#### A3. Flexible nutrient model + autocomplete + first PDF highlight — `00fd645` (2026-03-03, +1,242/−80)
- **What:** the redesign that defined the product — arbitrary nutrient rows per food, `FoodAutocomplete.jsx`, `NutrientAutocomplete.jsx`, `NutrientPopover.jsx`, and the first `PdfTextScanner.js` (145 lines then; **2,323 lines today**).
- **Why:** real food tables have variable nutrient sets; a fixed form can't capture them.
- **Hard part:** matching nutrient names against the PDF text layer to highlight them — the seed of what became the hardest frontend problem in the project (see A5).

#### A4. AI-prefill verification UI + workflow surfaces *(attributed frontend; built through Phase 4–5)*
- **What:** queue papers with no saved draft open with the latest Gemini `normalized_payload_json` **preloaded as editable food/nutrient rows** — the labeler verifies/corrects AI output instead of starting blank. Plus the Details panel for AI extraction (`AiDetailPanel.jsx`), the "Ask for Help" flow (`HelpRequestModal.jsx`), test-mode local-write toggle, and global no-data skip.
- **Why:** AI pre-extraction is only useful if the human can see and correct it in one place; the UI must show DB-compliant rows **without** leaking model reasoning.
- **Hard part / trade-off:** never overwrite an existing draft/submission while still prefilling empty papers; keep the prefill silent (no banner) per product decision. Required careful guarding in `Annotate.jsx` (1,163 lines today, the central orchestrator).

#### A5. PDF nutrient highlighting — the precision problem — `6aba2f2`, `f383732`, `cce6945`, `c885403` (+ scanner growth) *(2026-04-22 → 05-20)*
- **What:** table-scoped, click-to-add nutrient highlighting. The viewer builds a **page-local allowlist** from the PDF.js text layer and only marks detected table body/header cells and table caption lines.
- **Why:** naive "highlight every nutrient word" lights up prose and is useless; click targets must be precise.
- **What made it hard:** PDFs have no notion of "table." Table regions have to be *inferred* from text-item geometry, and nutrient words appearing in narrative paragraphs must be excluded.
- **How solved:** detect table anchors per page; if a page has no confident anchor (or a table continues onto a caption-less page), **suppress** highlights rather than fall back to page-wide matching. Precision-first by design.
- **Trade-off:** matches that split across multiple PDF text items inside a table are deliberately left as a known follow-up — correctness over coverage.

#### A6. AI-evidence overlays — coordinate-based highlighting — `63ac650`, `582c34e`, `a683c49`, `8fb77f5`, `ad1b38b`, `398cc46`, `b1ab87b`, `662a5f8`, `faf5341`, `82b09b0`, `c875853`, `5a23ac3`, `3564c57`, `8e89198`, `dc855e4`, `27c44ae`, `ac8bf72` *(2026-05-13 → 06-05, 17 commits)*
- **What:** a deduplicated **Sources strip** built from normalized payload rows; matched evidence snaps to whole detected table blocks or paragraph blocks and is painted as an always-on coordinate overlay scaled onto the rendered page.
- **Why:** show the reviewer *where in the paper* each AI-extracted value came from.
- **What made it hard — and the clever solutions:**
  - **Multi-column journals:** paragraphs from adjacent columns were being merged. Solved by **column-clip bounds** and splitting fragments at narrow column gutters (`82b09b0`, `c875853`), rejecting cross-column adjacency.
  - **Document chrome:** affiliations, article-history sidebars, keyword boxes, and copyright rows polluted evidence blocks — explicitly filtered out.
  - **`page_hint` lies:** the AI only sees extracted text, so for a journal offprint it reports the *printed* page (e.g. `1217` on a 5-page file). When `page_hint > numPages` it cannot be a page index, so highlighting was made **non-gating** — caption/quote text locates the evidence on any page (`27c44ae`). Printed page labels in headers/footers are mapped to real PDF pages.
  - **Stability:** stable region IDs and suppressed inner marks stop overlays from flickering between renders (`82b09b0`).
  - **Evidence-first rendering (`ac8bf72`, 2026-06-05):** render the evidence pages first and auto-open/highlight the first one, so reviewers land on the relevant page instantly.
- **Trade-off:** overlays are *broad navigation guidance*, not exact nutrient-coordinate matching; unmatched AI evidence stays visible but flagged "unverified."

#### A7. Codebase decomposition — `675feee`, `9de76ba`, `cf35755` *(2026-05-16)*
- Extracted pure helpers into `utils/annotateHelpers.js` (574 lines), small components, and **8 sub-views** into `src/views/` (`QueueView`, `ApprovalView`, `DashboardView`, `AllPapersView`, `PipelineOpsView`, `SuggestionsReviewView`, `MySuggestionsView`, `ReviewerAdminView`). Turned a monolithic `Annotate.jsx` into an orchestrator + view modules.

#### A8. Frontend performance & cost overhaul — `e15356e`, `390c162`, `376d687`, `9d0fbc0`, `ac8bf72` *(2026-06-04 → 06-05)*
- **What:** lazy-loaded cockpit data (only when a cockpit tab opens), a **self-hosted PDF.js worker**, a **durable PDF cache in the browser Cache Storage** (`pdfCache.js`, 107 lines) with prefetch of the next queue papers, and a queue redesigned around one lean RPC running in parallel with the profile fetch.
- **Why:** load time and Supabase egress were the binding constraints on a free tier.
- **Trade-off:** more client-side caching complexity in exchange for far fewer round-trips and bytes.

> **Current frontend surface:** `PdfTextScanner.js` 2,323 · `Annotate.jsx` 1,163 · `index.css` 2,970 · `PdfViewer.jsx` 939 · `FoodAutocomplete.jsx` 664 · `annotateHelpers.js` 574 · `EvidenceLocations.js` 439 · plus 8 views, ~12 components, hooks, and tests (`PdfTextScanner.test.js` 655, `EvidenceLocations.test.js` 225). **PDF viewer + scanner alone span 27 commits.**

---

### B. Suggestions, conflicts, theme, auth-UX *(Huan — all `landeryt` commits)*

> 23 commits, **+2,188/−582**, 2026-03-16 → 2026-05-20. Small in lines but **end-to-end features** spanning React UI, SQL tables, RLS policies, and a Storage bucket.

#### B1. Theme centralization + system-preference fallback — `cbf61ad`, `341b40e` *(2026-03-16)*
- Lifted theme state into `App.jsx` so login and app chrome share one source; follows the OS/browser theme when no explicit override exists; fixed PDF-viewer dark mode.

#### B2. Reset-password page — `4e208a5` (2026-03-19, +175/−1)
- **What/why:** the recovery email used to silently log the user in. Added `ResetPassword.jsx` (145 lines) + `App.jsx` routing so the link lands on a real "set new password" page.

#### B3. Suggestions system (the largest Huan feature) — `2fcdc55`, `4db6334`, `81d96af`, `bd29ab5`, `0a5fdd6`, `967c927`, `8dc6771`, `528848c`, `ebe2a3d` *(2026-04-21 → 04-25)*
- **What:** a full feedback channel. Labelers submit suggestions and track status in `My Suggestions`; cockpit/admins triage them. Image attachments upload to a **private `suggestion-attachments` Supabase Storage bucket** (10 MiB cap, image MIME allowlist, four `storage.objects` RLS policies using `storage.foldername(name)` for per-user containment); metadata in `backlog_review_items.attachments`.
- **Backend Huan wrote:** the `backlog_review_items` table + role-based RLS via `current_user_has_cockpit_access()`, and the storage bucket + policies.
- **Hard part:** signed-URL image viewing at view-time + correct per-user storage isolation in RLS — security-sensitive, small in lines, exact in logic. Largest single Huan commit: image attachments UI `0a5fdd6` (+445/−4).

#### B4. Conflicts system — `a979d3f`, `f54f2fb`, `2121663` *(2026-04-27)*
- `paper_conflict_resolutions` table + `paper_conflict_candidates` view (joining assignment/submission tables) and a "Choose This" picker wired into `Annotate.jsx` with CSS. Delivered fully; later **superseded** by Arciel's general approval queue (`fc67b30`, 2026-05-02) — a normal architecture evolution, not a defect.

#### B5. Fuzzy match utility — `e3971b2` (2026-05-09, +203/−100)
- `src/utils/fuzzyMatch.js` (162 lines today), integrated into food/nutrient autocomplete; closed backlog §8.

#### B6. Infinite PDF scrolling — `4ade833` (2026-04-26, +108/−74)
- Replaced prev/next paging with continuous scroll in `PdfViewer.jsx`; touched `PdfTextScanner.js` to keep highlight matching consistent across scrolled pages.

#### B7. Suggestion role-split + dev/tester read-only — `967c927`, `9f18a56` *(2026-05-07, 05-19)*
- `Suggest` visible to labelers only; admins get a triage list. Developer/Tester accounts can **read** admin/cockpit tabs (except Pipeline) while every DB mutation stays blocked — a small (+13/−6) but correctness-critical change across multiple read policies.
- Also: dual admin/labeler login (`de13677`, reverted same day per supervisor), suggestion photo hotfix (`8dc6771`), dropdown CSS polish (`528848c`).

---

### C. Database, RLS, auth, storage, workflow *(Arciel)*

> `apps/expert-annotator/migration.sql` — **5,396 lines, 43 commits**: 31 tables, 26 functions/RPCs, 75 RLS policies, 32 RLS-enabled tables, 69 indexes, 2 triggers.

#### C1. Canonical + workflow schema
- **Reference layer:** `entities`, `entity_aliases`, `master_nutrients`, `sources`, `claims` (normalized facts: food × nutrient × source with amount/unit/basis/confidence).
- **Discovery layer:** `papers` (DOI + `canonical_key` dedup identity, `ingest_status`, `rejection_reasons`, routing summary columns), `paper_search_hits`, `paper_search_batches`, `paper_search_batch_hits`.
- **Annotation layer:** `annotations`, `food_items`, `annotation_nutrient_values`, `paper_label_events`, `paper_global_labels`, `search_sessions`.
- **Reviewer/approval layer:** `reviewer_profiles`, `paper_label_submissions`, `paper_label_approvals` (`correction_diff_json`), `paper_review_outcomes`.
- **AI-routing layer:** `routing_stage_configs`, `paper_stage_tasks`, `ai_extractions`.

#### C2. Row-Level Security model — 75 policies
- **Why hard:** four distinct principals (end labeler, cockpit, tester/developer, service role) over 31 tables, each needing the right read/write boundary. Users read shared reference data and only their own annotations; pipeline tables are service-role only; testers get cockpit **read** visibility but no mutation.
- **RPCs as the security surface:** `get_pipeline_ops_snapshot`, `get_general_queue_papers`, `get_cockpit_ai_extractions`, `current_user_can_approve_labels`, `current_user_has_cockpit_access`, `current_user_has_cockpit_write_access`, `current_user_is_tester` — `SECURITY DEFINER` functions expose aggregates without granting raw table reads.

#### C3. Auth allowlist — `auth_allowlist.sql` + `87e2a18` (hardening)
- Private `allowed_auth_emails` + a security-definer signup hook; RLS enabled and client-role privileges revoked so the allowlist can't be read/written from the client. `87e2a18` hardened the RLS further.

#### C4. Workflow transitions (the model changed twice)
- `e0c7254` (04-13) assignment-driven labeling → `7988e51` slot-level no-data → **`fc67b30` (05-02) replaced reviewer slots with a general approval queue** (drafts don't claim papers; every exact submission retained; first submission removes the paper from the queue; Arciel approves non-Arciel submissions). Old slot/conflict tables kept as legacy audit only.
- **Trade-off:** the general queue tolerates duplicate stale submissions (simplicity, no locking) at the cost of occasional redundant labeling, resolved at approval.

---

### D. Paper-discovery crawler + feedback learning *(Arciel)*

> `food_paper_crawler/` (crawler_v2.py 2,215 · dergipark_source.py 687 · pipeline.py 600 · ranking.py 485 · feedback/update_terms.py 1,219) — **30 commits.**

#### D1. Crawler v2 — `Search → Filter → Acquisition` — `c4a695b`, `5863d74`, `95ad659`, `fd9adf9`, `b895f8a`, `64f1adb`, `b03f801`, `6df1623`, `f6d1745` …
- **What:** metadata-only retrieval from Europe PMC / OpenAlex / Semantic Scholar, then language-scoped relevance filtering, then PDF download **only** for candidates that pass the filter.
- **Why:** downloading PDFs is the expensive step; filter on cheap metadata first.
- **Hard parts:** identity-based dedup (`pmcid_*`/`doi_*`/hashed `canonical_key`) instead of title slugs; merging local terminal crawl state with live `papers.canonical_key` so already-seen papers aren't re-downloaded; **batch-aware** query budgeting where the batch size is counted at the *search gate*, not on raw hits.
- **Design rule (in `AGENTS.md`):** **no hard-negative veto** — relevance is additive scoring + soft penalties only, so one stray negative phrase never auto-rejects a paper (`b895f8a` removed the old veto logic).

#### D2. DergiPark as a journal index — `fd9adf9`
- Rebuilt the Turkish source as a locally refreshed journal/article index (`dergipark_source.py` 687 lines + `refresh_dergipark_index.py`) instead of the old global OAI slice. Currently dormant (ops are English-only) but retained.

#### D3. L2 feedback-learning loop — `76215a9`, `8963173`, `e61583f`, `8573bbb`, `0841793`, `3cbe7d9` …
- **What:** `feedback/update_terms.py` (1,219 lines) reads accepted reviewer truth from `paper_review_outcomes`, classifies positive/negative papers, extracts **title-only and title+abstract n-grams**, runs **log-odds scoring**, and writes weighted terms / query phrases / anchor phrases / pair scores / source priors / concept scores / **batch scores**, per language, into `latest.json` for the next crawl.
- **Why:** the crawler should get better at finding composition papers as humans label more — a closed learning loop.
- **Hard part / trade-off:** only *accepted* truth feeds learning (pending/superseded submissions excluded); dual embeddings (`sentence-transformers`) score metadata but feedback is **soft** — it never hard-rejects, matching the no-veto rule.

---

### E. AI extraction cascade *(Arciel)*

> `ai_routing.py` 842 · `process_stage_queue.py` 1,560 · `evaluator/unified_evaluator.py` 687 · `recover_gemini_candidates.py` 446 · `flash_lite_triage_experiment.py` 245 — **34 commits.**

#### E1. From single model to a 3-stage cascade
- **What:** `gemma_proof_extraction_v1` (`gemma-4-31b-it`, ~1500/day, **text mode**, 26B same-stage fallback) screens & ranks → `gemini_flash_lite_triage_v1` (`gemini-3.1-flash-lite`, ~500/day) re-ranks the strongest → `gemini_flash_db_payload_v2` (`gemini-3.5-flash`, ~20/day, **native PDF**) does the final extraction. Each stage ranks via `score_followup_priority`; per-stage daily targets + priority claiming make each stage process the top-N of the previous (1500 → 500 → 20).
- **Why:** a funnel of a cheap screener → mid triage → expensive extractor maximizes useful papers per scarce Gemini call.
- **First cut:** `92fe454` (2026-04-19) integrated Gemini Flash for automated triage/extraction (blind study); `cc039eb` added the Gemma screening cascade; `686fed8` added the Flash-Lite middle stage.

#### E2. `UnifiedEvaluator` — one contract for every model
- **What:** all stages share `opennutri_evidence_payload_v2`. The model may return broad candidate rows, but routing uses a deterministic `normalized_payload_json` with the **same contract as a human label submission** (food/nutrient identity, value, unit, basis, sample size, confidence, source citation, and per-row evidence metadata: `table_label`, `page_hint`, `source_quote`, `source_location_type`, `section_heading`, `paragraph_hint`).
- **Hard parts solved:**
  - **Shape drift → infinite retries:** models return four different JSON shapes (object, top-level array, single-object-in-array, nested `food→nutrients[]`); all are flattened before normalization so valid output never becomes a parse-error retry loop.
  - **Deterministic normalization:** only DB-compatible units (`g/100g`, `mg/100g`, `μg/100g`, …) are accepted; AI-provided DB IDs are verified against live rows, with fallback to exact/alias name match, and unresolved foods/nutrients preserved as explicit custom rows. The prompt includes the full nutrient catalog + text-matched food candidates, **not** the whole food catalog (prompt-size trade-off).
  - **Don't lose likely positives:** raw-positive but normalized-empty Gemma rows can still advance if Gemma returned candidate rows or a clear `has_data` decision — so parser/normalizer drift doesn't drop real papers.

#### E3. Native-PDF mode + true page numbers — `bc93f8b`, `probe_model_file_input.py` *(2026-05-31)*
- **What:** Gemini stages receive the native PDF part (inline < ~15 MB, else Files API) so the model reads pages/tables/scans directly and reports the **true 1-based PDF page index**; `===== PDF PAGE N =====` markers are injected at pdftotext form-feed boundaries before truncation so page numbers survive.
- **The measured constraint:** Gemma **times out (>600 s on a 5-page PDF)** in PDF mode, so Gemma screening must stay text-mode — documented (`0011272`) so nobody re-flips it. Probe script verifies a model accepts file parts before switching a stage.

#### E4. Retry-fairness and recovery — `b964fec`, `cb3b8c2`, `a8c01c8`, `29f2317`, `5bb2da1`, `8ae2d8e`, `5fe1bfd`, `recover_gemini_candidates.py`
- **What made it hard:** one repeatedly-failing paper could monopolize the queue; quota errors looked like paper failures.
- **How solved:** claim order = lower `attempt_count` → higher `priority` → older; non-quota errors fail after `AI_STAGE_MAX_TASK_ATTEMPTS=2`; **quota/rate-limit requeues undo the attempt count** so quota never looks like failure; stale `processing` rows are requeued before claiming; concurrent uploader duplicate-key races recover by reusing the row. `recover_gemini_candidates.py` (dry-run-first, capped at 200) rescues historical Gemma positives.

---

### F. Daily-ops orchestration + GitHub Actions infra *(Arciel)*

> `daily_ops_orchestrator.py` — **2,358 lines, 27 commits**; `.github/workflows/daily-ops.yml`.

- **What:** unattended automation that crawls, refills, and drains the cascade. Runs as **resumable 5-minute ticks** keyed to per-stage quota-day counts (Gemma resets UTC; Gemini stages reset `America/Los_Angeles` to match provider RPD). One serialized **controller** (the only writer/crawler) under a concurrency group + a **5-worker drain matrix** in parallel; workers never crawl/upload/refill and atomically claim distinct tasks.
- **Why this shape:** it has to run on **free GitHub-hosted runners** with a job time cap. So: the crawler has a 2,400 s wall-clock budget and writes partial accepted results before being killed; the controller tops Gemma up only to a 150-active target in bounded 30-paper chunks; each model call is capped at 300 s so one slow paper can't eat the job.
- **Hard parts solved:** decoupling drain from the controller so draining continues even if the controller job fails (`e4bc421`); counting active work from executable `paper_stage_tasks` rows (not paper summaries) so stale rows don't block refill; bounding crawler runtime (`43d3d60`).
- **Trade-off:** lower recall accepted in exchange for staying within free-tier compute, storage, and Gemini quota — an explicit research-ops decision.

---

### G. PDF delivery — storage, proxy, cache *(Arciel backend + Ayşegül frontend)*

- **Source-URL migration — `f8cad36`, `a6a7be7`, `68a4285`:** stop storing paper PDFs in Supabase Storage; serve from `papers.pdf_url`. **Why:** free-tier storage + egress caps. The shared queue only exposes human-ready papers with a non-empty `pdf_url`.
- **Same-origin proxy — `52bcd12` (`api/pdf.js`, 102 lines):** many publisher PDFs lack CORS headers and can't be fetched by the browser; a Vercel serverless proxy fetches them same-origin with long-lived cache headers.
- **Durable browser cache — `7733205`, `390c162`:** Cache Storage keeps PDFs across sessions and prefetches the next queue papers, cutting repeat egress to zero.

---

### H. Reference-data ETL *(Arciel)*

- `etl_sr_legacy_to_opennutri.py` (343) and `etl_usda_to_opennutri.py` (227) load USDA SR-Legacy and Foundation-Foods CSVs into `entities`/`entity_aliases`/`master_nutrients`/`sources`/`claims` via Supabase REST with **deterministic UUIDs** (idempotent re-runs), preparation state derived from description text. Universal schema in `create_opennutri_schema.sql`.

### I. Tests *(Arciel)*

- **4,902 lines** of Python tests: `test_ai_routing.py` 2,469 · `test_bilingual_pipeline.py` 1,120 · `test_daily_ops.py` 983 · `test_pdf_page_markers.py`, plus frontend unit tests (`PdfTextScanner.test.js` 655, `EvidenceLocations.test.js` 225, `evidenceStatusCache.test.js`). The AI-routing and daily-ops logic — the parts most likely to silently corrupt data or burn quota — carry the heaviest coverage.

### J. Documentation, infra, project management *(Arciel)*

- `README.md` (≈42 KB), `AGENTS.md` (≈28 KB agent guide with hot-files/task-routing), `INSTRUCTIONS.md`, `BACKLOG.md`, `docs/handoff_2026-03-20/STATE.md`, reviewer SOP + workflow map, the bilingual midterm reports (TR + EN) and AI-algorithm defense decks with their `export_*.py` pipelines. Security hygiene: removed hardcoded secrets (`9c18db9`), documented runtime-secret handling, `.gitignore` for generated artifacts.

---

## 5. The five hardest problems (cross-cutting)

1. **Highlighting evidence on real journal PDFs.** No table primitive, multi-column layouts, document chrome, and an AI `page_hint` that reports the *printed* page, not the PDF index. Solved with geometry-based table detection, column-clip bounds, chrome filtering, content-driven (caption + verbatim-quote) matching, and non-gating page hints. *(Frontend + the evidence contract.)*
2. **A reliable AI cascade on a free quota.** Three models, four JSON shapes, deterministic normalization to a human-equivalent contract, and a funnel that spends ~20 expensive Gemini calls/day on the best of ~1500 screened papers. Native-PDF mode for page accuracy, with the measured "Gemma times out on PDF" constraint baked into the design.
3. **Running real automation on free infrastructure.** Controller/drain split, per-stage quota-day accounting across two timezones, wall-clock budgets, partial-result writes, and retry-fairness so one bad paper can't monopolize the queue — all inside a 5-minute GitHub Actions tick.
4. **A correct multi-principal security model.** 75 RLS policies and `SECURITY DEFINER` RPCs giving labelers, cockpit, testers, and the service role exactly the right read/write surface across 31 tables.
5. **A learning crawler.** Closing the loop from accepted human truth → log-odds n-gram feedback → re-ranked next crawl, with soft scoring only and no hard-negative vetoes.

---

## 6. Summary metrics

- **5.5 months**, 2025-12-19 → 2026-06-05; **240 commits**; **47,198 lines** of tracked source.
- **Frontend:** ~13,500 lines, React 19 + Vite on Vercel; PDF viewer/scanner alone 27 commits.
- **Backend:** ~25,500 lines Python + a 5,396-line schema (31 tables / 75 RLS policies / 26 RPCs) + 4,902 lines of tests.
- **Automation:** a 3-stage LLM cascade driven unattended by GitHub Actions every 5 minutes.
- **Split:** Arciel ~66% · Ayşegül ~31% · Huan ~3% of net new code, by the team's frontend/backend division.

*Per-person detail is in the three companion reports: `OpenNutri_Work_Report_Huan.md`, `OpenNutri_Work_Report_Aysegul.md`, `OpenNutri_Work_Report_Arciel.md`.*
