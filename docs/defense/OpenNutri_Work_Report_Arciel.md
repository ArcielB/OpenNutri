# OpenNutri — Work Report: Arciel Aliognis Baez Zamora (221229078)

*Self-contained account of the backend, AI-pipeline, infrastructure, schema, ETL, test, and documentation work attributed to Arciel. Companion to the master report; numbers re-derived from git on 2026-06-05, HEAD `ac8bf72`.*

## At a glance

- **208 commits** (`baezarciel` + `ArcielB`), **2025-12-19 → 2026-06-05**.
- **+47,682 / −9,098 lines** of backend/AI/infra/docs (net **+38,584**), ~66% of the project's net new code.
- **Areas owned:** the Postgres schema + RLS, the multi-source crawler, the feedback-learning loop, the 3-stage LLM extraction cascade, the daily-ops automation on GitHub Actions, the PDF-delivery stack, USDA ETL, the cockpit RPCs, the test suite, and project documentation.
- **Attribution rule:** every non-`landeryt` commit's non-frontend lines are Arciel's, by the team's standing frontend/backend division. The SQL/RPC backing of cockpit screens is Arciel's even where the React view that renders it is credited to the frontend.
- **One honesty note up front:** commit `8728564` (2026-03-09, "Snapshot Tubitak_last_edition codebase") imported a pre-existing harvester/crawler/embedding codebase from an earlier private repo. That snapshot is a real foundation but is **not** net-new authored-in-OpenNutri work; the great majority (~83%) of Arciel's backend total is net-new after it.

---

## 1. Database schema, RLS, auth, storage, workflow
**`apps/expert-annotator/migration.sql` — 5,396 lines, 43 commits. 31 tables, 26 functions/RPCs, 75 RLS policies, 32 RLS-enabled tables, 69 indexes, 2 triggers.**

### 1.1 The data model
Designed in two layers so every nutrition fact is traceable end to end:
- **Reference layer:** `entities`, `entity_aliases`, `master_nutrients`, `sources`, `claims` (a claim = food × nutrient × source with amount/unit/basis/confidence/metadata — a normalized fact with provenance).
- **Discovery layer:** `papers` (carries DOI **and** a `canonical_key` dedup identity — DOI when a reliable external id exists, `canonical_key` for missing-DOI or cross-provider duplicates — plus `ingest_status`, `rejection_reasons`, and routing-summary columns `current_stage_key`/`routing_status`/`routing_bucket`/`route_destination`/`latest_ai_extraction_id`), `paper_search_hits`, `paper_search_batches`, `paper_search_batch_hits`.
- **Annotation layer:** `annotations`, `food_items`, `annotation_nutrient_values`, `paper_label_events`, `paper_global_labels`, `search_sessions`.
- **Reviewer/approval layer:** `reviewer_profiles`, `paper_label_submissions` (immutable exact snapshots), `paper_label_approvals` (`correction_diff_json` records exactly what the reviewer changed), `paper_review_outcomes` (final truth).
- **AI-routing layer:** `routing_stage_configs`, `paper_stage_tasks`, `ai_extractions`.

### 1.2 Row-Level Security — 75 policies (the hard part)
- **Why hard:** four principals — end labeler, cockpit user, tester/developer, service role — over 31 tables, each needing a precise read/write boundary. A labeler reads shared reference data and only **their own** annotations; pipeline tables (`paper_search_hits`, batches, stage tasks) are **service-role only**; a tester gets cockpit **read** visibility but **zero** mutation.
- **RPCs as the security surface:** `get_pipeline_ops_snapshot`, `get_general_queue_papers`, `get_cockpit_ai_extractions`, and the `current_user_*` predicate functions (`can_approve_labels`, `has_cockpit_access`, `has_cockpit_write_access`, `is_tester`) are `SECURITY DEFINER`, so cockpit users see aggregates without granting raw table reads to every authenticated user. This keeps powerful queries server-side and least-privilege.
- **Auth allowlist** (`auth_allowlist.sql`, hardened in `87e2a18`): a private `allowed_auth_emails` table with RLS on and client-role privileges revoked; signup runs through a security-definer hook, never a client read/write.

### 1.3 The workflow changed twice — and that's the point
- `e0c7254` (04-13) assignment-driven labeling → `7988e51` slot-level no-data → **`fc67b30` (05-02) replaced reviewer slots with a general approval queue.** In the final model, drafts don't claim papers, multiple stale in-progress submissions are allowed (every exact payload retained), the first general submission removes the paper from the visible queue, Arciel's own submissions auto-accept, and non-Arciel submissions go to an approver-only Approval page.
- **Trade-off:** the general queue accepts occasional redundant labeling (no locking) in exchange for a far simpler concurrency model, with conflicts resolved at approval instead of at claim time. Old slot/conflict tables are kept as legacy audit only.

---

## 2. Paper-discovery crawler + feedback learning
**`food_paper_crawler/` — crawler_v2.py 2,215 · dergipark_source.py 687 · pipeline.py 600 · ranking.py 485 · feedback/update_terms.py 1,219 · 30 commits.**

### 2.1 Crawler v2 — `Search → Filter → Acquisition`
- **What:** metadata-only retrieval from Europe PMC / OpenAlex / Semantic Scholar, then language-scoped relevance scoring, then a PDF download **only** for candidates that pass the filter — because downloading is the expensive step.
- **Hard parts solved:**
  - **Identity-based dedup:** accepted PDFs are named `pmcid_*` / `doi_*` / hashed `canonical_key`, not title slugs (`46c5ac5`).
  - **Don't re-crawl known papers:** before acquisition the crawler merges local terminal crawl state with **live `papers.canonical_key` rows** from Supabase, so already-queued/skipped/human-ready/finalized papers aren't downloaded again; legacy `seen_ids` are no longer consulted (`6df1623`).
  - **Batch-aware budgeting:** `--query-limit` counts unique papers that pass the **search gate**, not raw hits, so a single batch never downloads far beyond the requested refill size (`64f1adb`, `b03f801`).
- **A deliberate design rule** (documented in `AGENTS.md`): **no hard-negative veto.** Relevance is additive scoring + soft penalties only; `b895f8a` removed the old veto logic so one stray negative phrase can never auto-reject a paper.

### 2.2 DergiPark as a journal index — `fd9adf9`
Rebuilt the Turkish source as a **locally refreshed journal/article index** (`dergipark_source.py` + `refresh_dergipark_index.py`) instead of the old global OAI slice, with coverage tracked in a refresh report. Dormant under English-only ops but retained for reactivation.

### 2.3 L2 feedback-learning loop — `update_terms.py` (1,219 lines)
- **What:** reads accepted reviewer truth from `paper_review_outcomes`, classifies positive/negative papers, extracts **title-only and title+abstract n-grams**, runs **log-odds scoring**, and writes weighted terms / query phrases / anchor phrases / pair scores / source priors / concept scores / **batch scores**, **per language**, into `latest.json`, which the crawler loads automatically.
- **Why:** close the loop — the crawler should get better at finding composition papers as humans approve more, with each crawl benefiting from newer feedback.
- **Hard part / trade-off:** only *accepted* truth feeds learning (pending/superseded submissions are excluded, AI-truth rows excluded from human-truth export); dual `sentence-transformers` embeddings score metadata, but feedback is **soft** — it never hard-rejects, consistent with the no-veto rule. Field-aware learning (`3cbe7d9`) distinguishes title vs title+abstract signal.

---

## 3. AI extraction cascade
**`ai_routing.py` 842 · `process_stage_queue.py` 1,560 · `evaluator/unified_evaluator.py` 687 · `recover_gemini_candidates.py` 446 · `flash_lite_triage_experiment.py` 245 · 34 commits.**

### 3.1 A 3-stage funnel
`gemma_proof_extraction_v1` (`gemma-4-31b-it`, ~1500/day, **text mode**, with `gemma-4-26b-a4b-it` as a same-stage fallback for retryable failures) screens & ranks → `gemini_flash_lite_triage_v1` (`gemini-3.1-flash-lite`, ~500/day) re-ranks the strongest → `gemini_flash_db_payload_v2` (`gemini-3.5-flash`, ~20/day, **native PDF**) is the final extraction. Each stage ranks via `score_followup_priority`; per-stage daily targets + priority-ordered claiming make each stage process the **top-N of the previous** (1500 → 500 → 20). First Gemini integration `92fe454` (04-19); Gemma screening `cc039eb`; Flash-Lite middle stage `686fed8`.
- **Why a cascade:** Gemini calls are the scarce resource. A cheap large-volume screener → mid triage → expensive extractor spends those ~20 daily Gemini calls on the best-ranked papers, maximizing useful papers per call.

### 3.2 `UnifiedEvaluator` — one contract for every model
- All stages share the `opennutri_evidence_payload_v2` prompt and emit a deterministic `normalized_payload_json` with the **same contract as a human label submission** (food/nutrient identity, value, unit, basis, sample size, confidence, source citation, and per-row evidence metadata: `table_label`, `page_hint`, `source_quote`, `source_location_type`, `section_heading`, `paragraph_hint`).
- **Hard problems solved:**
  - **Shape drift → infinite retry loop:** models return four different JSON shapes (object, top-level array, single-object-in-array, nested `food→nutrients[]`). All are flattened before normalization so valid output never becomes a parse-error retry.
  - **Deterministic normalization:** only DB-compatible units accepted; AI-supplied DB IDs verified against live rows, with fallback to exact/alias name match and unresolved items preserved as explicit **custom rows**. The prompt carries the full nutrient catalog + text-matched food candidates but **not** the full food catalog (a prompt-size trade-off).
  - **Don't lose likely positives:** raw-positive but normalized-empty Gemma rows can still advance when Gemma returned candidate rows or a clear `has_data` decision, so parser/normalizer drift doesn't silently drop real papers; strict normalization still gates final Gemini/human entry.

### 3.3 Native-PDF mode + true page numbers — `bc93f8b`, `probe_model_file_input.py`
- Gemini stages receive the native PDF part (inline < ~15 MB, else the Files API) so the model reads pages/tables/scans directly and reports the **true 1-based PDF page index**; `===== PDF PAGE N =====` markers are injected at pdftotext form-feed boundaries **before** truncation so surviving pages keep correct numbers.
- **The measured constraint:** Gemma **times out (>600 s on a 5-page PDF)** in PDF mode (both 31B and 26B), so Gemma screening must stay text-mode — measured, then documented (`0011272`) so it isn't naively re-flipped. `probe_model_file_input.py` verifies a model accepts file parts before a stage is switched.

### 3.4 Retry-fairness, quota safety, recovery
- **What made it hard:** one repeatedly-failing paper could monopolize automation, and quota errors looked like paper failures.
- **How solved:** claim order = lower `attempt_count` → higher `priority` → older creation; non-quota errors fail after `AI_STAGE_MAX_TASK_ATTEMPTS=2`; **quota/rate-limit requeues undo the attempt count** so quota never looks like failure (`cb3b8c2`, `a8c01c8`, `29f2317`, `5bb2da1`); stale `processing` rows are requeued before claiming (`8ae2d8e`); concurrent uploader duplicate-key races recover by reusing the existing row (`5fe1bfd`). `recover_gemini_candidates.py` (dry-run first, capped at 200 per apply) rescues historical Gemma positives. `flash_lite_triage_experiment.py` is the regression/quality gate kept around the triage stage.

---

## 4. Daily-ops orchestration + GitHub Actions infra
**`scripts/daily_ops_orchestrator.py` — 2,358 lines, 27 commits; `.github/workflows/daily-ops.yml`.**

- **What:** unattended automation that crawls, refills, and drains the cascade as **resumable 5-minute ticks** keyed to per-stage quota-day counts (Gemma resets **UTC**; both Gemini stages reset **`America/Los_Angeles`** to match provider RPD). Architecture: one serialized **controller** (the only writer/crawler, under the `daily-ops-refill-controller` concurrency group) + a **5-worker drain matrix in parallel**; workers never crawl/upload/refill and atomically claim **distinct** tasks via `claim_paper_stage_tasks`.
- **Why this exact shape — free infrastructure:** it runs on free GitHub-hosted runners with a hard job-time cap, so: the crawler has a **2,400 s wall-clock budget** and writes partial accepted results before being killed; the controller tops Gemma up only to a **150-active** target in bounded **30-paper** chunks; each model call is capped at **300 s** so one slow paper can't consume a large fraction of the job.
- **Hard parts solved:** decoupling drain workers from the controller so draining continues even if the controller job fails (`e4bc421`); counting active work from **executable `paper_stage_tasks` rows** rather than paper summaries, so stale `queued_for_ai` rows don't block refill while no task can be claimed; bounding crawler refill runtime (`43d3d60`); fanning out scheduled workers (`ca0e1db`).
- **Trade-off (explicit research-ops decision):** accept lower recall to stay within free-tier compute, storage, and Gemini quota — surface useful papers fast now, revisit skipped candidates later.

---

## 5. PDF delivery — storage, proxy, cache
- **Source-URL migration** (`f8cad36`, `a6a7be7`, `68a4285`): stop storing paper PDFs in Supabase Storage; serve from `papers.pdf_url`. **Why:** free-tier storage + egress caps. The shared queue only exposes human-ready papers with a non-empty `pdf_url`. Model workers fetch PDFs on demand and keep only DB routing/audit rows, so rejected papers never accumulate storage.
- **Same-origin proxy** (`52bcd12`, `api/pdf.js` 102 lines): many publisher PDFs lack CORS headers and can't be fetched by the browser; a Vercel serverless function proxies them same-origin with long-lived cache headers.
- **Browser durable cache** (`7733205`, `390c162`): Cache Storage keeps PDFs across sessions and prefetches the next queue papers, driving repeat egress toward zero. (Frontend side credited in Ayşegül's report; the proxy and storage policy are backend.)

---

## 6. Reference-data ETL (USDA → Supabase)
- `etl_sr_legacy_to_opennutri.py` (343) seeds USDA SR-Legacy 2018-04; `etl_usda_to_opennutri.py` (227) seeds Foundation Foods 2025-12-18 — both into `entities`/`entity_aliases`/`master_nutrients`/`sources`/`claims` via Supabase REST with **deterministic UUIDs** (so re-runs are idempotent), preparation state derived from description text. Universal schema in `create_opennutri_schema.sql`.

## 7. Cockpit RPCs + pipeline dashboard
- **Pipeline cockpit** (`4108801`, `bb129ad`, `0bc0d64`): `get_pipeline_ops_snapshot` + the funnel UI that shows crawler → PDF → Small → Medium → Strong → human review. **Role-stable labels** (`Small model (Gemma 31B)` etc.) so a future model swap changes only the spec in parentheses; historical direct Small→Strong papers are backfilled into the Medium stage so the middle counter doesn't start at zero (`b1b8a8e`).
- **Useful Papers / dashboard** use `get_cockpit_ai_extractions` — a deliberately slim projection (normalized payload + normalization summary, **omitting** raw model responses/reasoning) to protect Supabase egress. Reviewer-admin cockpit controls (`0f7ff10`), labeler-account access (`21f8557`), read-only developer training queues (`c2bbffe`).

## 8. Tests
**4,902 lines of Python tests:** `test_ai_routing.py` 2,469 · `test_bilingual_pipeline.py` 1,120 · `test_daily_ops.py` 983 · `test_pdf_page_markers.py` 73. The cascade routing and daily-ops logic — the parts most able to silently corrupt data or burn quota — carry the heaviest coverage; bilingual crawler behavior is regression-locked.

## 9. Documentation, security, project management
- `README.md` (≈42 KB), `AGENTS.md` (≈28 KB — agent guide with hot-files map, task routing, product truths, and research-ops notes), `INSTRUCTIONS.md`, `BACKLOG.md`, `docs/handoff_2026-03-20/STATE.md`, reviewer SOP + workflow map, bilingual midterm reports (TR + EN), AI-algorithm defense decks, and the `export_*.py` doc pipelines.
- **Security hygiene:** removed hardcoded runtime secrets (`9c18db9`), documented env-var-only secret handling (`d3d8788`), expanded `.gitignore` for generated artifacts (`972e851`).

---

## Why this is the project's largest body of work

Arciel's ~38,600 net new lines span **the entire backend**: a 5,396-line schema with 75 RLS policies and 26 RPCs, a 2,215-line learning crawler, an 842 + 1,560 + 687-line AI cascade, a 2,358-line orchestrator that runs real automation on free infrastructure, an ETL layer, ~4,900 lines of tests, and the project's documentation. The four hardest cross-cutting problems in OpenNutri — a correct multi-principal security model, a reliable 3-model AI cascade on a fixed quota, unattended ops inside a 5-minute free-runner tick, and a learning crawler — all live here. Roughly 83% of it is net-new in this repository after the March pipeline snapshot.
