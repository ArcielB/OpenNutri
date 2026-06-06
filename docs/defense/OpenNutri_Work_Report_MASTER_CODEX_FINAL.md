# OpenNutri — Master Work Report

**Prepared:** 2026-06-05 · **Reconciled and restructured:** 2026-06-05
**Source snapshot used for code evidence:** current `main` at `cc035c3` (even with `origin/main`; metrics re-verified file-by-file against this working tree).
**Lineage:** this single report consolidates three earlier artifacts so nothing is lost and nothing is said three times — the current-code evidence report (`OpenNutri_Current_Code_Work_Report.md`), the historical master-final ledger (`OpenNutri_Work_Report_MASTER_FINAL.md`, itself a merge of the Claude master and the Codex v2 master), and the deep per-subsystem technical work log. The earlier files are preserved unchanged on disk and in git history.

This is a documentation-only artifact. Producing it did not change application code, the schema, the workflow YAML, the live database, Vercel, or any runtime behavior.

## How to read this report

| Section | What it gives an evaluator |
| --- | --- |
| 1. Executive summary & what OpenNutri is | The one-paragraph claim, the end-to-end workflow, and the precise scope. |
| 2. Methodology & attribution rules | How the evidence was gathered and how work is credited (git-author vs. subsystem ownership). |
| 3. Reproducible metrics | Line counts, schema/RPC/RLS counts, test counts, and contributor churn — each re-verifiable. |
| 4. Repository structure | Where every subsystem lives. |
| 5. Timeline | The project phases by date. |
| 6. Deep technical work log | The core. Each subsystem: what it is, why it exists, how it works internally, the hard parts, the trade-offs. |
| 7. The five hardest problems | The cross-cutting engineering crux of the project. |
| 8. Contributor assessment summary | Per-person achievements and most-defensible metrics. |
| 9. Assessment ledger | Per-workstream credit / dates / evidence pointers, for line-item evaluation. |
| 10. Chronological milestone ledger | The dated commit history that defines the project. |
| 11. Validation state & evidence commands | How the numbers and the document were checked. |

Sections 1–5 orient; section 6 is the technical heart; sections 7–11 are the assessment and evidence apparatus. Where a current-implementation fact and an older description ever conflict, the current `cc035c3` source tree is authoritative.

## Scope and honest caveats — what this report does *not* claim

These bound the whole report:

- **Not every nutrition paper is in scope.** OpenNutri targets *direct* real-food or stable food-product composition data. Papers about health effects, supplements, diets, extracts, processing treatments, microbes, biomarkers, animals, sensory scores, or one-off experimental formulations are treated as empty unless they also carry direct composition tables.
- **AI output is not final human truth by default.** Final active truth is reviewer-led through `paper_review_outcomes`. AI-model outcomes are stored as provenance and are *excluded* from the human-truth feedback that trains the crawler — the model never trains on itself.
- **Turkish / DergiPark is not active in normal daily ops.** The bilingual code path and its tests remain, but current daily/refill defaults are English-only.
- **Paper PDFs are not stored in Supabase by default.** Current ops use source-URL / on-demand PDFs unless a legacy override is explicitly set; only suggestion attachments use a private bucket.
- **The PDF highlighter does not perfectly reconstruct every table, OCR case, or continuation page.** It reconstructs table/paragraph regions from the PDF.js text layer and has known limits.
- **The L2 classifier is not trained or integrated.** The feedback *terms* exist and are applied as soft scores; classifier training is deferred until enough human labels exist.
- **Raw model reasoning is not loaded in default cockpit lists.** The slim RPCs deliberately omit it to protect egress.

## 1. Executive summary & what OpenNutri is

OpenNutri is an end-to-end food-composition **paper-discovery and human-verification** system. It is not a generic nutrition chatbot and not a general literature-search tool. Its target is narrow and deliberate: direct, real-food or food-product composition values that can become useful nutrition facts for datasets, diet tracking, food exporters, inspection, or related real-world use.

The current codebase is a complete loop: it starts from reference food/nutrient data, searches the scientific literature, filters and downloads papers, runs a three-stage AI cascade, turns model output into a deterministic database-compatible payload, presents the evidence to human labelers, stores immutable submissions, lets an approver correct and finalize truth, and feeds accepted human truth back into the crawler.

It has three deployable surfaces over one Supabase Postgres database:

- A **React 19 + Vite expert annotator** in `apps/expert-annotator/`, deployed on Vercel.
- A **Supabase Postgres schema / RLS / RPC contract** in `apps/expert-annotator/migration.sql`.
- A **Python data pipeline** in `services/data-pipeline/`, scheduled by `.github/workflows/daily-ops.yml`.

The end-to-end workflow:

```text
USDA reference data
  -> entities / aliases / master_nutrients / sources / claims

Europe PMC / OpenAlex / Semantic Scholar crawler
  -> metadata search
  -> additive relevance filter (no hard veto)
  -> PDF acquisition + full-text validation
  -> Supabase paper + search-hit registration
  -> Small model screening:  Gemma 31B  (26B fallback, text mode)   ~1,500/day
  -> Medium model triage:    Gemini 3.1 Flash-Lite                   ~500/day
  -> Strong model extraction: Gemini 3.5 Flash (native PDF)          ~20/day
  -> normalized has_data payload
  -> human_review_ready general queue
  -> immutable labeler submission
  -> Arciel approval / correction
  -> paper_review_outcomes  (final truth)
  -> feedback-learning export -> better-ranked next crawl
```

The system optimizes for **high-precision discovery** of direct food/product composition data. The scarce resource is the final extraction model (~20 calls/day on the free quota); the cascade exists so those calls are spent on the strongest candidates out of ~1,500 screened, not on whatever arrived first.

## 2. Methodology & attribution rules

This report was built from current source evidence after `git fetch origin`, an ahead/behind check, and a working-tree status check; `main...origin/main` was even. Untracked local artifacts (older work-breakdown exports, files under `docs/defense/read_this/`, unrelated coursework) were left untouched.

Evidence sources:

- **Git history across all refs** — because Ayşegül's original MVP/frontend commits live on `origin/master` while the current `main` branch later imported and reorganized that work.
- **Current tracked source inventory**, excluding USDA data dumps, generated binaries (DOCX/PDF/PPTX/image/ODT/XLSX/SVG), the `legacy/` archive, `node_modules`, build output, local pipeline data caches, generated `feedback/latest.json`, lockfiles, and the work-report files themselves (which would inflate the metric).
- **Direct file reads and counts** of every principal implementation file: `migration.sql`, `PdfViewer.jsx`, `PdfTextScanner.js`, `EvidenceLocations.js`, `Annotate.jsx`, `annotateHelpers.js`, `FoodAutocomplete.jsx`, `NutrientAutocomplete.jsx`, `SuggestionModal.jsx`, `fuzzyMatch.js`, `ResetPassword.jsx`, `ai_routing.py`, `unified_evaluator.py`, `process_stage_queue.py`, `crawler_v2.py`, `ranking.py`, `models.py`, `update_terms.py`, `daily_ops_orchestrator.py`, `daily-ops.yml`, and the test suite.
- **Project docs**: `README.md`, `AGENTS.md`, `docs/handoff_2026-03-20/STATE.md`, `docs/reviewer_workflow_map.md`.

The report separates two kinds of attribution and labels every claim by which one it uses:

- **Git-author attribution** — what git directly proves. Every `landeryt` commit is credited to Huan. `baezarciel` plus the initial `ArcielB` commit are credited to Arciel. The `ayseguldogan2706-cpu` identity has seven all-ref commits, five of them the original MVP/frontend commits on `origin/master`.
- **Subsystem attribution** — the team's stated ownership split for assessment. **Ayşegül** owns the core user-facing annotator frontend (annotation UI, PDF viewing/highlighting UX, autocomplete surfaces, workflow views). **Arciel** owns the database/schema/RLS/RPCs, crawler, AI pipeline, daily ops, deployment infrastructure, backend-driven cockpit integrations, documentation, and project management. **Huan** owns his `landeryt` commits in full, whatever layer they touched.

This distinction is essential: a report based only on current-mainline git authorship would under-credit Ayşegül, because her early frontend work was imported through later integration commits; a report based only on subsystem claims would hide what git directly proves. This report carries both and never conflates them.

## 3. Reproducible metrics & evidence snapshot

All counts below were re-verified against the `cc035c3` working tree with `wc -l`, `git ls-files`, `git shortlog`, and `grep` over `migration.sql`. The per-file line counts, schema-object counts, and test counts are exact; the bucketed source totals and the all-ref churn are snapshot/filter-dependent and are labeled as such.

### 3.1 Tracked active source by bucket

Exclusions as in §2 (USDA dumps, generated binaries, `legacy/`, `node_modules`, `dist`, local pipeline data, generated feedback JSON, lockfiles, work-report files).

| Bucket | Lines | Files | Main evidence |
| --- | ---: | ---: | --- |
| Backend, ops, schema | ~31,500 | 88 | Python pipeline, SQL schema/RPC/RLS, GitHub Actions workflow. |
| Frontend | ~14,100 | 53 | React app source, Vite/API/config, UI helpers. |
| Active docs | ~5,150 | 23 | README, AGENTS, handoff/state, reviewer SOP/map (work reports excluded). |
| Proposal appendix docs | 971 | 9 | Proposal-section deliverables, counted separately. |
| **Total active tracked source** | **~51,800** | **~174** | Current active tracked text/source under the exclusions above. |

### 3.2 Key implementation file sizes (exact, current)

| File | Lines | Why it matters |
| --- | ---: | --- |
| `apps/expert-annotator/migration.sql` | 5,396 | Schema, RLS, RPCs, reviewer workflow, routing tables. |
| `services/data-pipeline/scripts/daily_ops_orchestrator.py` | 2,358 | Controller/drain orchestration and quota accounting. |
| `apps/expert-annotator/src/utils/PdfTextScanner.js` | 2,323 | Browser-side PDF text/table/evidence geometry engine. |
| `services/data-pipeline/food_paper_crawler/crawler_v2.py` | 2,215 | Multi-source Search → Filter → Acquisition crawler. |
| `services/data-pipeline/scripts/process_stage_queue.py` | 1,560 | AI task worker: retry/fallback/quota, routing writes. |
| `services/data-pipeline/food_paper_crawler/feedback/update_terms.py` | 1,219 | Human-truth feedback export and term scoring. |
| `apps/expert-annotator/src/pages/Annotate.jsx` | 1,163 | Main UI orchestration: queue, cockpit, approval, suggestions. |
| `apps/expert-annotator/src/components/PdfViewer.jsx` | 939 | PDF rendering, caching, headless scan, overlays, navigation. |
| `services/data-pipeline/ai_routing.py` | 842 | Routing constants, bucket logic, deterministic payload normalization. |
| `services/data-pipeline/scripts/upload_to_supabase.py` | 774 | Paper/search-hit/batch registration and AI task enqueue. |
| `services/data-pipeline/evaluator/unified_evaluator.py` | 687 | Shared model prompt, native PDF input, JSON parser, record extraction. |
| `services/data-pipeline/food_paper_crawler/dergipark_source.py` | 687 | Retained Turkish/DergiPark source adapter. |
| `apps/expert-annotator/src/components/FoodAutocomplete.jsx` | 664 | Food catalog search/ranking UX. |
| `apps/expert-annotator/src/utils/annotateHelpers.js` | 574 | Shared UI payload, formatting, pipeline, AI-summary helpers. |
| `services/data-pipeline/scripts/ensure_paper_stock.py` | 573 | Queue stock/refill wrapper, English-default behavior. |
| `services/data-pipeline/food_paper_crawler/ranking.py` | 485 | Metadata/PDF relevance and validation scoring. |
| `apps/expert-annotator/src/utils/EvidenceLocations.js` | 439 | Source grouping and evidence dedup. |
| `services/data-pipeline/food_paper_crawler/models.py` | 374 | Candidate/query dataclasses + deterministic identity/dedup keys. |
| `apps/expert-annotator/src/components/NutrientAutocomplete.jsx` | 334 | Nutrient catalog search/ranking UX. |
| `apps/expert-annotator/src/components/SuggestionModal.jsx` | 279 | User suggestions with attachments and rollback. |
| `apps/expert-annotator/src/utils/fuzzyMatch.js` | 162 | Banded-Levenshtein fuzzy-match engine (both autocompletes). |
| `apps/expert-annotator/api/pdf.js` | 102 | Same-origin PDF proxy with SSRF hardening. |
| `.github/workflows/daily-ops.yml` | 148 | Scheduled controller + 5 drain-worker matrix. |

### 3.3 Schema / RPC / RLS counts (from `migration.sql`)

| SQL object | Count |
| --- | ---: |
| Tables | 31 |
| Functions / RPCs | 26 |
| RLS policies | 75 |
| RLS-enabled tables | 32 |
| Indexes | 69 |
| Triggers | 2 |
| Views | 1 |
| `SECURITY DEFINER` functions | 22 |
| Storage policies | 4 |

Principal RPCs: `hook_restrict_signup_by_email_allowlist`, `claim_paper_stage_tasks`, `sync_reviewer_profile`, `get_general_queue_papers`, `get_general_queue_cards`, `submit_general_label`, `approve_label_submission`, `get_cockpit_ai_extractions`, `get_pipeline_ops_snapshot`, `build_annotation_submission_payload`, `build_label_payload_diff`.

### 3.4 Test coverage (exact, current)

Tracked test files total **5,898 lines across 10 files**; the focused high-risk regression suite is **5,617 lines**. The suite holds **128 Python `test_` functions** and **35 frontend `it()`/`test()` blocks**.

| Test file | Lines | Focus |
| --- | ---: | --- |
| `tests/test_ai_routing.py` | 2,469 | AI normalization, routing, retry/fallback/quota, upload edge cases. |
| `tests/test_bilingual_pipeline.py` | 1,120 | Crawler language/source/filter behavior, terminal state, batch feedback, PDF limits. |
| `tests/test_daily_ops.py` | 983 | Controller/drain ticks, quota-day windows, worker requirements, stage counts. |
| `src/utils/PdfTextScanner.test.js` | 655 | Table/paragraph/evidence matching, page-hint behavior. |
| `src/utils/EvidenceLocations.test.js` | 225 | Source grouping and evidence dedup. |
| `src/utils/evidenceStatusCache.test.js` | 92 | Evidence status cache behavior. |
| `tests/test_pdf_page_markers.py` | 73 | Page-marker injection and text cap. |
| `test_harvest.py` | 243 | Older/live harvester checks. |
| `scripts/test_frontend_fetch.js` | 24 | Frontend connectivity helper. |
| `test_pg.py` | 14 | Database connectivity helper. |

### 3.5 Contributor evidence

Git history must be read **across all refs** because the original MVP/frontend commits from Ayşegül are preserved on `origin/master` while the current `main` later imported and reorganized that work.

`git shortlog -sne --all` at `cc035c3`:

| Git author | Commits |
| --- | ---: |
| `baezarciel <baezarciel@gmail.com>` | 216 |
| `landeryt <mcraft160105@gmail.com>` | 24 |
| `ayseguldogan2706-cpu <ayseguldogan2706@example.com>` | 7 |
| `ArcielB <…@users.noreply.github.com>` | 1 |

*(The three most recent `baezarciel` commits are these defense documents; the project-code attribution below excludes work-report files.)*

All-ref churn under the active-source filter:

| Git author | Added | Deleted | Caveat |
| --- | ---: | ---: | --- |
| `baezarciel` | ~66,000 | ~17,000 | Backend, schema, ops, docs, integration, and later frontend integration. |
| `ayseguldogan2706@example.com` | 6,624 | 88 | Original MVP/frontend on `origin/master`; raw all-ref additions include `package-lock.json` (active-source-filtered additions are ~3,200). |
| `mcraft160105@gmail.com` | 2,188 | 582 | Huan's directly authored commits and full-stack features. |
| `ArcielB` | 1 | 0 | Initial README commit; credited to Arciel. |

Ayşegül's seven all-ref commits: `7c2d372`, `614a82c`, `6245a17`, `00fd645`, `8a29dcb`, `969c902`, `fb33626`; the first five are the original MVP/frontend commits on `origin/master`.

## 4. Repository structure

### Frontend — `apps/expert-annotator/src/`

- `pages/Annotate.jsx` — state orchestration, queue refresh, cockpit lazy-loading, save/submit, approval, help/suggestion routing.
- `views/*.jsx` — extracted queue, approval, dashboard, paper-overview, pipeline, suggestion, reviewer-admin views.
- `components/PdfViewer.jsx` + `utils/PdfTextScanner.js` + `utils/EvidenceLocations.js` — PDF rendering and evidence layout analysis.
- `components/FoodAutocomplete.jsx`, `components/NutrientAutocomplete.jsx`, `utils/fuzzyMatch.js` — catalog search and approximate matching.
- `components/SuggestionModal.jsx`, `views/SuggestionsReviewView.jsx`, `views/MySuggestionsView.jsx` — suggestion flow.
- `utils/annotateHelpers.js` — payload normalization, model-stage labels, cockpit funnel helpers, AI-extraction summaries.

### Backend & data pipeline — `services/data-pipeline/`

- `food_paper_crawler/crawler_v2.py`, `ranking.py`, `models.py`, `embeddings.py`, source adapters (`europe_pmc.py`, `dergipark_source.py`, `search_sources.py`) — paper discovery, relevance scoring, deterministic identity keys.
- `food_paper_crawler/feedback/update_terms.py` (+ `feedback_*.py`, `supabase_terms.py`) — human-truth feedback learning.
- `ai_routing.py`, `evaluator/unified_evaluator.py`, `scripts/process_stage_queue.py` — AI decision contract, deterministic normalization, queue processing, retry/fallback.
- `scripts/daily_ops_orchestrator.py`, `scripts/ensure_paper_stock.py`, `scripts/upload_to_supabase.py` — unattended ops, queue refill, upload/routing.
- `etl/` USDA loaders, plus operational/backfill scripts and a retained earlier-architecture pipeline (`pipeline.py`, `harvester/`, `core/`, `extraction/`) — see §6.10.

### Database & security

`apps/expert-annotator/migration.sql` is the single schema/RLS/RPC source of truth: canonical food/nutrient reference layer, paper-discovery tables, annotation tables, general queue + approval tables, AI extraction/routing tables, reviewer profiles, suggestion-review tables, 75 RLS policies, and 22 `SECURITY DEFINER` RPCs.

### Deployment & operations

`.github/workflows/daily-ops.yml` schedules ops every 5 minutes: one serialized `refill-controller` (may crawl/upload/refill) plus a 5-worker `drain-workers` matrix (drain-only, in parallel). The frontend is Vercel-hosted; Supabase stores auth/application data; paper PDFs are source-URL/on-demand by default.

## 5. Timeline

| Phase | Dates | Main work |
| --- | --- | --- |
| Bootstrap | 2025-12-19 | Repository created, access verified. |
| MVP & snapshot | 2026-03-09 → 03-16 | Earlier codebase imported, README/reorganization, baseline frontend + crawler into `apps/`/`services/`. Huan centralized theme state. |
| Feedback & crawler hardening | 2026-03-19 → 03-30 | Reset password, label events/test mode, feedback terms, auto-crawl, bilingual crawler split, DergiPark index, no-hard-veto scoring. |
| Reviewer workflow & AI routing | 2026-04-13 → 04-29 | Assignment workflow, reviewer admin, Gemini triage/extraction, read-only queues, suggestion review, image attachments, conflict system, AI prefill. |
| General approval queue | 2026-05-02 → 05-09 | Slot workflow replaced by general queue + approval, useful AI details restored, queue limited to normalized AI `has_data`, Gemma cascade, fuzzy matching. |
| Daily ops & cockpit | 2026-05-11 → 05-20 | Retry-fair AI queue, daily quota draining, pipeline cockpit, evidence highlighting, Annotate refactor to helpers/views, tester/developer access. |
| Three-stage cascade & PDF hardening | 2026-05-27 → 05-31 | Auth allowlist hardening, controller/drain fan-out, Flash-Lite middle stage, source-URL PDFs, CORS proxy, browser cache, true PDF page numbers. |
| Performance & report package | 2026-06-04 → 06-05 | Lean queue RPC, lazy cockpit, self-hosted PDF worker, durable Cache Storage PDFs, evidence-first rendering, bounded crawler runtime, this consolidated report. |

## 6. Deep technical work log (by subsystem)

This is the technical heart of the report. Each subsystem is described once, in depth: what it is, why it exists, how it works internally, where the hard parts are, which technologies are involved, and what trade-offs were made. The attribution and dated evidence for each subsystem are in §9 (Assessment ledger) and §10 (Milestone ledger); they are not repeated here. Owner tags in each heading follow the subsystem-attribution rule from §2.

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

**Files read for this section:** `food_paper_crawler/crawler_v2.py` (2,215 lines), `ranking.py` (485), `models.py` (374), `embeddings.py` (138), with the source adapters `europe_pmc.py`, `dergipark_source.py` (687), `search_sources.py`. **30 commits.** `FoodCompositionCrawlerV2` is a ~2,200-line orchestrator class with ~70 methods, sitting on a shared data-model module (`models.py`) that the adapters, ranking, upload, and feedback all import.

#### The shared data model + deterministic identity keys (`models.py`)
`models.py` is the small but load-bearing module the whole discovery layer agrees on. It defines the candidate/query dataclasses — `CandidatePaper`, `QuerySpec`, `SearchTask`, `DownloadRecord`, `DiscoveryHit` — and, more importantly, the **three deterministic key builders** that make idempotence and dedup possible across processes: `build_canonical_key` (the cross-provider paper identity used when a reliable DOI is missing), `build_search_hit_key` (the md5 over `canonical_key|source|language|template|term|phrase|query` that keys the idempotent search-hit ledger), and `build_search_batch_key` (the per-query-batch identity behind batch feedback), plus `build_storage_filename` (identity-based PDF naming). Because the crawler, every source adapter, `ranking.py`, `upload_to_supabase.py`, and the feedback exporter all import the *same* functions, a paper computes the *same* identity everywhere — which is what lets the SQL `UNIQUE(hit_key)` index, the live-`canonical_key` skip set, and batch-yield feedback all line up without a central coordinator. `DualEmbeddingScorer` lives alongside in `embeddings.py` as the sentence-transformers wrapper the metadata gate calls for anchor-phrase similarity.

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

### Earlier pipeline architecture, shared utilities & operational tooling *(Arciel)*

The current crawler-v2 + AI-cascade path is the *second* full pipeline architecture in the repo. The earlier one was not deleted — it is retained, and it is real prior work that the line counts above do not surface. This subsection accounts for it honestly so the record is complete.

#### Shared utilities still on the active path
- **`processing/content.py` (153)** — `extract_full_text` / `extract_metadata` parse Europe PMC JATS-XML into plain text and metadata; `unified_evaluator.py` calls `extract_full_text` when a paper arrives as PMC XML rather than a PDF, so this module is still live under the current cascade.
- **`processing/validator.py` (99), `processing/extractors.py` (66)** — text-validation and field-extraction helpers shared between the old harvester and current ingest utilities.

#### The earlier ("v1") harvester pipeline — superseded, retained
Before `crawler_v2`, discovery ran through a layered harvester:
- **`food_paper_crawler/pipeline.py` (600)** — the v1 `FoodCompositionCrawler` orchestrator, still launchable through `cli.py` (the v2 entrypoint is `cli_v2.py`).
- **`harvester/` package (~1,360 lines)** — `foodcomp_crawler.py` (336), `relevance_filter.py` (205), `query_builder.py` (202), `client.py` (195), `pmc_harvester.py` (170), `foodcomp_filter.py` (143), `pdf_downloader.py` (107): the original search/filter/download stack.
- **`core/` package (~530 lines)** — `orchestrator.py` (162), `knowledge.py` (187), `data_source.py` (124), `types.py` (57), driven by `orchestrator_cli.py` ("OpenNutri Harvester CLI").
- **`extraction/` package (~340 lines)** — `nutrient_extractor.py` (192), `table_extractor.py` (149): the earlier rule-based table/nutrient extraction, before the model cascade took over extraction.

This generation was superseded by the additive-scoring crawler v2 and the three-stage AI cascade, but it shipped and worked, and its better ideas (staged search→filter→download, relevance scoring, PMC harvesting) carried forward. Keeping it costs some repo size; the trade-off is an auditable lineage of how discovery evolved.

#### Operational, backfill & migration tooling (`scripts/`)
A layer of one-purpose operational scripts keeps the live system maintainable — most are small, a few are substantial:
- **`backfill_ai_routing.py` (299)** — backfills routing-status/bucket/extraction columns onto historical papers when the routing model changed, so old rows participate in the current funnel.
- **`seed_training_stock.py` (213)** — seeds a controlled stock of papers for labeler training/onboarding without running a full crawl.
- **`cleanup_paper_storage.py` (188)** — the legacy paper-Storage janitor (only relevant when `OPENNUTRI_STORE_PDFS_IN_SUPABASE=1`; skipped in current source-URL ops).
- **`backfill_paper_workflow_language.py` (122)** — backfills `workflow_language` for papers predating the bilingual split.
- **`refill_assignment_queue.py` (408)** — the legacy slot-workflow stock job, retained for compatibility with the superseded assignment model.
- **`upload_ai_extractions.py` (83), `refresh_dergipark_index.py` (43)** — extraction upload helper and the DergiPark journal-index refresher.
- **Ingestors — `ingestor_pdf.py` (448), `ingestor.py` (387), `ingestor_structured.py` (226)** — earlier-generation PDF/structured ingest utilities feeding the harvester era.
- **Diagnostics — `check_rls.py` (24), `check_db.py` (20), `config_targets.py` (22), `test_pg.py` (14), `test_frontend_fetch.js` (24)** — quick live-connectivity/RLS/target probes used during ops hardening.

None of this is glamorous, but it is the difference between a demo and a system that has actually been operated, migrated, and recovered in production over six months.


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

Most defensible metrics: 7 all-ref commits; all-ref git-author churn `+6,624/-88` (raw additions include `package-lock.json`); ~14,100 current frontend lines under the exclusion rules; 10,334 lines in the principal queue/PDF/autocomplete/view files listed above. Current-mainline path churn is larger because later frontend evolution and integration were committed through shared/integration commits (see §2 on why git-author counts under-credit her).

### Arciel Aliognis Baez Zamora

Primary evidence: `baezarciel` and `ArcielB` commits, backend/ops/schema/docs ownership.

Assessment-facing achievements:

- Built the Supabase database contract, RLS model, reviewer truth workflow, and queue/approval/cockpit RPCs.
- Built the crawler, additive relevance scoring, feedback learning, and paper upload/routing pipeline.
- Built the three-stage AI cascade with normalization, retry fairness, quota safety, PDF/text model input modes, and follow-up prioritization.
- Built unattended daily ops on GitHub Actions with controller/drain worker split and source-URL PDF strategy.
- Performed integration, documentation, project management, and live ops hardening.

Most defensible metrics: 216 `baezarciel` commits plus the initial `ArcielB` commit (the three most recent being these defense documents); `baezarciel` churn ~`+66,000/-17,000` with work-report files excluded from the project-code metric; backend/ops/schema bucket ~31,500 lines.


## 9. Assessment ledger — attribution, dates, and evidence by workstream

This ledger is the **attribution lens**: who built what, when, on what technology, and where the evidence lives. The *mechanics* of each workstream are in §6 (Deep Technical Work Log) and are not repeated here — each entry points to its §6 home. The ledger is organized by workstream rather than commit order because the project repeatedly replaced earlier architecture with better production versions.

### 9.1 Project bootstrap & MVP annotator
- **When:** 2025-12-19, then 2026-03-02 → 03-09. **Credit:** Ayşegül (original annotator MVP on `origin/master`); Arciel (import/reorganization into the current repo); Huan (later theme refinement). **Tech:** React, Vite, Supabase Auth/Storage, plain CSS, PDF.js/react-pdf.
- The first usable deliverable: a browser interface where a labeler could open a paper, inspect its PDF, and enter food/nutrient rows — login, app shell, Google OAuth, theme toggle, first food form and PDF highlight behavior, initial SQL schema fragments.
- **Evidence:** Ayşegül all-ref commits `7c2d372`, `614a82c`, `6245a17`, `00fd645` (flexible nutrients + autocomplete + PDF highlight redesign), `8a29dcb`; current frontend ~14,100 tracked lines; principal frontend files 10,334 current lines.

### 9.2 Authentication, roles, theme & read-only training access
- **When:** March → May 2026. **Credit:** Ayşegül (auth/frontend shell), Huan (theme centralization, reset-password, tester visibility), Arciel (role/RLS/RPC backing, reviewer-profile workflow). **Tech:** Supabase Auth, React state, `matchMedia`, session storage, Postgres RLS, `SECURITY DEFINER` predicates.
- Multi-principal access: labeler / cockpit / tester / approver / service role, with tester read-only and a private signup allowlist enforced by an auth hook. Full mechanics in §6 (Database) and §6 (Annotator app shell).
- **Evidence:** Huan commits `cbf61ad`, `341b40e`, `4e208a5`, `9f18a56`; schema evidence 75 RLS policies / 32 RLS-enabled tables / 22 `SECURITY DEFINER` functions; files `App.jsx`, `Login.jsx`, `ResetPassword.jsx`, `useTheme.js`, `migration.sql`.

### 9.3 Annotation editor, AI prefill & the payload contract
- **When:** March → June 2026, major changes 2026-04-13, 05-02, 06-04. **Credit:** Ayşegül (core editor/workflow frontend); Arciel (backend contract/RPCs, AI-prefill integration, general-queue redesign, performance). **Tech:** React 19, Supabase JS, Postgres RPCs, JSONB, deterministic hashing.
- The one stable payload language spoken by JS, SQL, and Python that makes AI rows and human rows interchangeable and hash-comparable. Full mechanics in §6 (Database — payload builders) and §6 (Annotator app).
- **Evidence:** `Annotate.jsx` (1,163), `annotateHelpers.js` (574), `ai_routing.py` (842); RPCs `submit_general_label`, `approve_label_submission`, `build_annotation_submission_payload`, `build_label_payload_diff`.

### 9.4 General queue & approval workflow
- **When:** slot workflow April 2026; general-queue replacement 2026-05-02; refinements through June. **Credit:** Arciel (schema/RPC/workflow redesign, final approval model); Ayşegül (frontend queue/approval surfaces); Huan (earlier conflict system, later superseded). **Tech:** Supabase Postgres, RLS, RPCs, React views, immutable JSON payloads.
- **Why it changed:** the slot workflow was too heavy operationally; the team needed every active labeler to see available useful papers and a paper to leave the queue as soon as a real submission exists — while final truth stayed under reviewer (Arciel) control. The schema preserves all three generations (slot → conflict → general queue); see §6 (Database, "the workflow engine was rebuilt twice").
- **Evidence:** workflow map `crawl → upload → Small → Medium → Strong → human_review_ready → paper_label_submissions → approval → paper_label_approvals → paper_review_outcomes → feedback`; `QueueView.jsx`, `ApprovalView.jsx`, `DashboardView.jsx`; `migration.sql`.

### 9.5 PDF evidence viewer, highlighting & source navigation
- **When:** initial viewer March; intensive highlighting 2026-04-22 → 06-05. **Credit:** Ayşegül (frontend PDF/highlight UX ownership); Arciel (evidence-source integration, caching, page-hint fixes, source-URL delivery); Huan (continuous scroll). **Tech:** PDF.js/react-pdf, browser text-layer geometry, Cache Storage API, localStorage LRU, Supabase dedup cache, Vercel serverless proxy.
- The single hardest piece of code in the project — turning AI `table_label`/`page_hint`/`source_quote` metadata into inspectable overlays on arbitrary publisher PDFs. Full mechanics (nine hard problems) in §6 (PDF evidence subsystem).
- **Evidence:** `PdfTextScanner.js` (2,323), `PdfViewer.jsx` (939), `EvidenceLocations.js` (439); tests `PdfTextScanner.test.js` (655), `EvidenceLocations.test.js` (225), `evidenceStatusCache.test.js` (92); commits `6aba2f2`, `f383732`, `cce6945`, `63ac650`, `a683c49`, `8fb77f5`, `ad1b38b`, `398cc46`, `b1ab87b`, `662a5f8`, `faf5341`, `82b09b0`, `c875853`, `5a23ac3`, `3564c57`, `8e89198`, `dc855e4`, `7733205`, `27c44ae`, `ac8bf72`.

### 9.6 Autocomplete, fuzzy matching & search telemetry
- **When:** initial autocomplete 2026-03-03; fuzzy-match upgrade 2026-05-09; telemetry through May. **Credit:** Ayşegül (autocomplete UX/components); Huan (reusable fuzzy-match engine); Arciel (catalog loading, telemetry integration). **Tech:** React, Supabase catalog queries, in-memory ranking, debouncing, fuzzy token matching, search-session logging.
- Forgiving search without unsafe over-matching (e.g. surfacing *Apple, raw* over *Apple juice, canned*). Full mechanics in §6 (Annotator app — domain-tuned IR) and §6 (Huan's `fuzzyMatch`).
- **Evidence:** `FoodAutocomplete.jsx` (664), `NutrientAutocomplete.jsx` (334), `fuzzyMatch.js` (162), `searchSessionLogger.js` (110); Huan commit `e3971b2`.

### 9.7 Suggestions, help requests, attachments & cockpit review
- **When:** initial modal 2026-03-02; Huan's full system 2026-04-21 → 05-12; help/context integration later. **Credit:** Huan (suggestion/review/attachment vertical); Ayşegül (frontend continuity); Arciel (help-context integration). **Tech:** React modal/views, Supabase table + Storage, RLS/storage policies, signed URLs.
- A complete full-stack slice with per-user folder paths, transactional upload-then-insert with rollback, and signed-URL viewing. Full mechanics in §6 (Huan's features).
- **Evidence:** Huan commits `2fcdc55`, `4db6334`, `ebe2a3d`, `bd29ab5`, `0a5fdd6`, `967c927`, `8dc6771`, `528848c`; `SuggestionModal.jsx` (279), `SuggestionAttachmentsCell.jsx` (83), `HelpRequestModal.jsx` (29); `migration.sql` (`backlog_review_items`, `suggestion-attachments` bucket + 4 storage policies).

### 9.8 Database schema, RPCs & security
- **When:** March → June 2026, major migrations April/May. **Credit:** Arciel. **Tech:** Supabase Postgres, SQL/PL-pgSQL, JSONB, RLS, `SECURITY DEFINER`, triggers, indexes.
- The shared truth store and least-privilege security model behind every surface. Full mechanics (five schema layers, the security model, the concurrency primitive, payload builders) in §6 (Database).
- **Evidence:** `migration.sql` (5,396); 31 tables / 26 RPCs / 75 policies / 69 indexes / 2 triggers / 22 `SECURITY DEFINER`; core RPCs `claim_paper_stage_tasks`, `get_general_queue_cards`, `get_cockpit_ai_extractions`, `get_pipeline_ops_snapshot`, `submit_general_label`, `approve_label_submission`.

### 9.9 AI cascade & model worker
- **When:** Gemini integration April 2026; Gemma cascade May; Flash-Lite middle stage 2026-05-29; PDF-mode Gemini 2026-05-31. **Credit:** Arciel. **Tech:** Python, Supabase client, Gemini/Gemma via the Google generative SDK path, `pdftotext`, JSON parsing, SHA-256, Postgres RPC task claiming.
- Three-stage cascade with one shared contract, deterministic normalization, routing buckets, follow-up prioritization, retry-fairness, quota safety, and same-attempt fallback. Full mechanics in §6 (AI extraction cascade).
- **Evidence:** `unified_evaluator.py` (687), `ai_routing.py` (842), `process_stage_queue.py` (1,560); `test_ai_routing.py` (2,469), `test_pdf_page_markers.py` (73); recovery/regression tools `recover_gemini_candidates.py` (446), `flash_lite_triage_experiment.py` (245).

### 9.10 Paper-discovery crawler & relevance scoring
- **When:** March crawler reorg, late-March crawler-v2/feedback hardening, May/June daily-ops refinements. **Credit:** Arciel. **Tech:** Python, Europe PMC/OpenAlex/Semantic Scholar APIs, DergiPark local index, urllib/curl, `pdftotext`, sentence-transformers, JSON manifests.
- Multi-signal, explainable, additive (no hard veto) Search→Filter→Acquisition with PMC proof-of-work PDF recovery and canonical dedup. Full mechanics in §6 (Crawler v2) including the shared `models.py` identity keys.
- **Evidence:** `crawler_v2.py` (2,215), `ranking.py` (485), `models.py` (374), `embeddings.py` (138); `test_bilingual_pipeline.py` (1,120); adapters `europe_pmc.py`, `search_sources.py`, `dergipark_source.py`.

### 9.11 Feedback learning
- **When:** 2026-03-20 onward, refined after reviewer-truth workflow changes. **Credit:** Arciel. **Tech:** Python, Supabase REST, smoothed log-odds n-gram scoring, JSON config output.
- Learns only from resolved human truth (never from AI-finalized outcomes) and feeds soft scores back to the next crawl. Full mechanics (good/bad/background log-odds, the derived pools) in §6 (L2 feedback-learning loop).
- **Evidence:** `update_terms.py` (1,219), `feedback_terms.py`, `feedback_config.py`, `supabase_terms.py`; README documents that pending/superseded and AI-only outcomes do not feed learning.

### 9.12 Daily-ops automation
- **When:** April recursive loop; hardening through May; controller/worker split 2026-05-29; bounded crawler runtime 2026-06-04. **Credit:** Arciel. **Tech:** GitHub Actions, Python orchestrator, Supabase service role, Gemini secrets, `poppler-utils`, pip caching, GitHub concurrency groups.
- One serialized refill controller + five parallel drain workers on a 5-minute cron, made safe by the DB claim RPC. Full mechanics (controller/drain logic, two-timezone quota accounting, nested wall-clock budgets) in §6 (Daily-ops orchestration).
- **Evidence:** `.github/workflows/daily-ops.yml` (148), `daily_ops_orchestrator.py` (2,358); `test_daily_ops.py` (983); README daily-ops section, AGENTS ops notes.

### 9.13 Storage, egress & frontend performance
- **When:** earlier storage/upload decisions April/May; major work 2026-05-30 → 06-05. **Credit:** Arciel (storage/egress architecture, backend projections); Ayşegül (frontend performance UX). **Tech:** Supabase Postgres/Storage, Vercel serverless, Cache Storage API, localStorage LRU, Vite-bundled PDF worker, lean RPCs.
- Source-URL PDFs (no default Supabase paper storage), same-origin PDF proxy, durable browser cache + prefetch, lean one-RPC queue, lazy cockpit, slim cockpit AI projection (measured ~82 MB → ~11 MB egress). Full mechanics in §6 (Daily-ops — PDF proxy) and §6 (Annotator app — egress-driven architecture).
- **Evidence:** commits `f8cad36`, `a6a7be7`, `68a4285`, `52bcd12`, `7733205`, `e15356e`, `9d0fbc0`, `390c162`, `376d687`, `ac8bf72`; `api/pdf.js` (102), `pdfCache.js` (107); handoff STATE.md egress audit.

### 9.14 Tests & validation infrastructure
- **When:** March → June 2026, expanding with each risky subsystem. **Credit:** Arciel (suite architecture); Ayşegül/Huan where tests cover their frontend behavior. **Tech:** Vite frontend tests, Python tests, Supabase schema-check scripts, `pandoc` doc-export validation.
- 5,617 lines of focused regression weighted toward the code that can silently corrupt data or burn quota. Full breakdown in §3.4; the `test_ai_routing.py` names read as a specification of the AI-cascade invariants (see §6 ETL + test suite).
- **Evidence:** `test_ai_routing.py` (2,469), `test_bilingual_pipeline.py` (1,120), `test_daily_ops.py` (983), `test_pdf_page_markers.py` (73); frontend `PdfTextScanner.test.js` (655), `EvidenceLocations.test.js` (225), `evidenceStatusCache.test.js` (92).

### 9.15 Documentation & project management
- **When:** March → June 2026. **Credit:** Arciel primarily, with Huan/Ayşegül feature docs. **Tech:** Markdown, DOCX/PDF export scripts, GitHub workflow docs, repo agent instructions.
- The state docs that stop future work from re-deriving or reverting key decisions (general queue vs slots, source-URL PDFs, no hard-negative vetoes, AI-prefill behavior, tester read-only, the three-stage cascade).
- **Evidence:** `README.md`, `AGENTS.md`, `INSTRUCTIONS.md`, `docs/handoff_2026-03-20/STATE.md`, `docs/reviewer_workflow_map.md`, `docs/reviewer_sop_en.md`, the defense/work-report set, `BACKLOG.md`.

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
| 2026-06-05 | `fd1b930`, `bf89977`, `1a8d1cf`, `6607ac9`, `4a8ec8a`, `0713a03`, `ef213e7`, `cc035c3` | Arciel (documentation, with Codex/Claude assist) | Per-contributor work reports v1/v2, frontend report deepening, current-code report, and this consolidated/restructured master report. | Created assessment artifacts, corrected attribution evidence, and merged the three report streams into one non-redundant document. |


## 11. Validation state & evidence commands

This report was built from the current tracked source after a remote refresh (`git fetch origin`), an ahead/behind check (`main...origin/main` even), and a working-tree status check. Every metric in §3 was re-verified file-by-file against the `cc035c3` working tree.

Reproducible commands used to gather and check the evidence:

```text
git fetch origin
git rev-list --left-right --count main...origin/main      # ahead/behind
git shortlog -sne --all                                    # commit counts by author
git log --all --author=<author> --format= --numstat -- <paths>   # filtered churn
git ls-files <globs> | wc -l                               # tracked source inventory
wc -l <key files>                                          # exact file sizes
grep -ciE 'CREATE TABLE|CREATE .*FUNCTION|CREATE POLICY|...' migration.sql   # schema counts
grep -rcE '^\s*def test_' tests/*.py                       # test-function counts
pandoc <report.md> -o <report.docx>                        # DOCX export
pandoc <report.md> -t plain | wc -w                        # word count
unzip -p <report.docx> word/document.xml | head           # DOCX sanity check
git diff --check ; git diff --cached --check               # whitespace/merge-marker check
```

Honest limitation: this report is evidence-backed from source, git history, project docs, the test suite, and direct reads of every principal implementation file. It is **not** a claim that every tracked line in the USDA data dumps, the generated documents, or every retained legacy file was read end to end. Where current implementation and older prose ever conflict, the `cc035c3` source tree is authoritative.

This is a documentation-only artifact: producing it changed no application code, no schema, no workflow YAML, no live database, and no deployment.
