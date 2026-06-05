# OpenNutri — Work Report: Arciel Aliognis Baez Zamora (221229078)

*Self-contained, code-grounded account of the backend, AI-pipeline, infrastructure, schema, ETL, test, and documentation work. Every section was written after reading the actual source files (named at the top of each). Companion to the master report; numbers re-derived from git on 2026-06-05, HEAD `ac8bf72`.*

## At a glance

- **208 commits** (`baezarciel` + `ArcielB`), 2025-12-19 → 2026-06-05; **+47,682 / −9,098 lines** (net **+38,584**), ~66% of the project's net new code.
- **Owned:** the Postgres schema + RLS + RPCs, the multi-source learning crawler, the L2 feedback loop, the 3-stage LLM extraction cascade, the daily-ops automation on GitHub Actions, the PDF-delivery stack, USDA ETL, the cockpit RPCs, the test suite, and the project documentation.
- **Honest caveat:** commit `8728564` (2026-03-09) imported a pre-existing harvester/crawler/embedding codebase from an earlier private repo; that snapshot is a real foundation but not net-new authored-in-OpenNutri work. The great majority (~83%) of the backend total is net-new after it.

The four hardest cross-cutting problems in OpenNutri — a correct multi-principal security model, a reliable 3-model AI cascade on a fixed free quota, unattended ops inside a 5-minute free-runner tick, and a learning crawler — all live in this work. What follows is each subsystem documented from its implementation.

---
## AI extraction cascade — Gemma → Gemini Flash-Lite → Gemini Flash *(Arciel)*

**Files read in full for this section:** `evaluator/unified_evaluator.py` (688 lines), `ai_routing.py` (843), `scripts/process_stage_queue.py` (1,561), with `scripts/recover_gemini_candidates.py` (446) and `scripts/flash_lite_triage_experiment.py` (245). **34 commits** touch this subsystem.

### What it is and why it exists
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

### The shared contract: `UnifiedEvaluator` (one prompt for every model)
All three stages run the *same* `evaluate_and_extract()` against the same `EXTRACTION_PROMPT` (`opennutri_evidence_payload_v2`). The prompt is the product's domain definition in code: it spends ~25 lines enumerating exactly what "useful OpenNutri data" is (direct food/product composition values) versus what is **empty** — intervention/effect studies, one-off experimental formulations (1%/2%/4% additive levels, fertilizer/irradiation/storage/salt-stress treatments), digestibility, sensory, biomarkers, review aggregates. This precision is the difference between a database of real foods and a pile of irrelevant agronomy papers.

Each extracted row must carry **evidence-location metadata** so the frontend can later highlight it: `table_label`, `page_hint`, `source_quote` (a *short contiguous verbatim* excerpt, ≤20 words, matched against the PDF to place the highlight), `source_location_type`, `section_heading`, `paragraph_hint`. The prompt explicitly instructs the model that `page_hint` is the **1-based PDF page index from the `===== PDF PAGE N =====` markers, never the printed journal page** — the single most important instruction, because the printed-page bug is what broke highlighting (see frontend section).

The prompt is fed the **full `master_nutrients` catalog** (id + standard_name) but only **text-matched food candidates**, not the whole food table — `select_food_candidates_for_text()` substring-matches every food/alias (≥4 chars, word-boundary) against the first 500 KB of the paper and keeps the 250 longest matches. Trade-off: full nutrient catalog (small, high value for ID resolution) vs. a filtered food shortlist (the food table is large; sending it all would blow the prompt and cost).

### Robustness 1 — surviving model JSON drift
LLMs return malformed or differently-shaped JSON constantly; naively this becomes an infinite retry loop. The evaluator defends in depth (`_parse_response_json`, `_coerce_result_root`, `_iter_candidate_rows`):
- **Markdown fence stripping** (` ```json … ``` `).
- **Balanced-bracket candidate scanner** (`_balanced_json_candidates`) — a hand-written character scanner that tracks string/escape state and brace/bracket depth to extract the first *balanced* JSON object/array even when the model wraps it in prose. It yields candidates and picks the first that "looks like a result root."
- **Four accepted shapes**, all coerced to one canonical root: the requested object; a bare top-level array of rows; a single object wrapped in a one-element array; and nested `food → nutrients[]` rows (flattened by `_iter_candidate_rows` using a shared `_food_context`). A row missing food/nutrient/amount/unit is dropped, not fatal.

So *valid-but-differently-shaped* output is salvaged instead of triggering a retry. This is the concrete realization of the AGENTS rule "keep these parser variants so shape drift does not become an infinite AI retry loop."

### Robustness 2 — native PDF input + true page numbers
`_build_generate_content()` attaches the PDF as a native document part when the stage's `model_input_mode == "pdf"`: **inline** under a 15 MB cap, otherwise uploaded via the Files API with a `cleanup` callback that deletes the temp file *and* the remote upload in a `finally` (so failures don't leak files or quota). Native PDF gives the model rendered pages + tables + the auto-extracted (un-billed) embedded text, and lets it report the true page.

For text-mode stages, `annotate_pdf_page_breaks()` splits `pdftotext` output on form-feeds (`\f`), drops a trailing empty page, and injects `===== PDF PAGE N =====` markers **before** any truncation, so surviving pages keep correct numbers. **Why Gemma stays text-mode:** the probe (`probe_model_file_input.py`) confirmed Gemma *accepts* PDF parts but was measured to **time out >600 s on a 5-page PDF** (both 31B and 26B) — fatal for a ~1500/day stage — so Gemma gets page-marked text, which already gives it correct page numbers without images. This decision is encoded and documented so it isn't naively reverted.

### The deterministic normalizer (`normalize_ai_payload_with_summary`, ai_routing.py)
The model's free-form rows are converted into the exact same `normalized_payload_json` contract a human labeler submits — this is what makes AI output and human output interchangeable downstream. The pipeline:
1. **Required-field gate:** drop rows missing food/nutrient/amount → counted as `missing_required_field`.
2. **Unit standardization (`_standardize_unit`)** — the strict gatekeeper. Only `g/100g`, `mg/100g`, `μg/100g`, `kcal/100g`, `kJ/100g`, `IU/100g`, `%` survive. It handles `µ`-vs-`μ`, casefolding, `gram(s)`/`mg`/`milligram`/`mcg`/`ug`/`microgram`/`kcal`/`kJ`/`IU` spellings, compound `mg/100g` forms, and a **basis policy**: per-100g required, **dry-matter/`dm` rejected**, but `fresh`/`wet`/`as-is`/`edible portion` accepted. Rejections counted as `unsupported_unit_or_basis`.
3. **Reference resolution (`_resolve_reference_row`)** — ID-first (verify the model's `food_fdc_id`/`nutrient_id` against live rows *and* that the row's name matches), then exact name, then alias. The name resolver (`_build_exact_name_resolver`) maps **ambiguous names to `None`** (if two DB rows share a name, neither matches) to avoid wrong links. Unresolved foods/nutrients are kept as explicit `is_custom_food`/`is_custom_nutrient` rows, not dropped.
4. **Grouping + deterministic ordering:** rows group by (resolved food, id, custom flag, raw name, prep state); foods and nutrients are sorted by a long stable key; values `round(…, 6)`. This determinism matters because the payload is **canonically serialized and SHA-256 hashed** (`payload_text_and_hash`) for dedup and exact-match comparison against human submissions — two equal extractions must hash identically.
5. **Summary accounting:** `accepted/rejected/unmapped` counts and a `rejection_reasons` histogram are stored on every extraction, so the cockpit can see *why* rows were dropped.

### Routing logic (`ai_routing.py` + `process_one_task`)
After normalization the paper is bucketed and routed:
- **`classify_routing_bucket`** → high/low × positive/negative, comparing `overall_confidence` to the stage's thresholds.
- **`stable_audit_sample`** — deterministic audit sampling: `SHA256(paper|stage|model)` compared against `audit_rate × 2^64`. Same paper always gets the same audit decision (reproducible), and a configurable fraction of even high-confidence AI finalizations are forced to human review as a quality check.
- **`route_bucket`** → low-confidence or audit-sampled or already-has-human-truth ⇒ `human_review_ready`; high-positive ⇒ `ai_finalized_has_data`; high-negative ⇒ finalized no-data.
- **Per-stage destinations** layered on top in `process_one_task`: if the stage has a `next_stage_on_has_data` and the paper is useful (or a *raw-positive rescue*, below), it is **enqueued to the next stage** instead of finalized; if the stage's `no_data_route_destination == provisional_skip`, no-data becomes a **provisional skip** (kept out of the human queue and, if legacy storage is on, its PDF is deleted).
- **Raw-positive rescue (`_clear_raw_has_data_decision`):** a Gemma output that is raw-positive but normalizes to *empty* rows still advances to the next stage if it had complete raw rows, or confidence ≥ 0.75, or ≥ 0.6 with composition language — so parser/normalizer drift never silently drops a likely-real paper. Strict normalization still gates final Gemini/human entry.

### The follow-up priority score (`score_followup_priority`) — why each stage processes the *top-N*
This is the function that makes the funnel a funnel. Each useful output gets an integer score (clamped −1000…1000) combining:
- `80 × confidence`
- accepted normalized rows (`×8`, cap 160), evidence rows (`×5`, cap 90), per-100g rows (`×4`), table rows (`×5`)
- raw-output signals (complete rows, evidence, table, per-100g, unsupported-unit rows that still indicate a real table)
- a **direct-fit bonus**: +70 for "food/nutrient/proximate composition" language, +25 for "food product / real-world / commercial / high database value", +up-to-45 for table rows, +up-to-35 for evidence rows
- **soft penalties** (subtracted): review/meta-analysis/database-aggregate (−35/−20), feed/digestibility (−30), sensory/outcome/biomarker/cell-culture/animal-model (−25), one-off/experimental formulation (−35/−30), treatment/supplement/extract (−20).

The next stage then claims tasks ordered by this priority, so Flash-Lite processes the best 500 of Gemma's output and the final Gemini the best 20 of that. The penalty list mirrors the prompt's "empty" definition — the same domain judgment encoded twice, once for the model and once for the ranker.

### Retry-fairness, fallback ladder, and quota safety (`process_stage_queue.py`)
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

### Persistence + finalization
`insert_ai_extraction` stores the full audit trail in `ai_extractions`: raw model response, parsed result, the `normalization_summary` (with rejection histogram), the normalized payload, the **threshold snapshots** at decision time, the routing bucket/destination, and `audit_sampled`/`finalized_without_human`. High-confidence AI finalizations also `upsert` into `paper_review_outcomes` with `truth_source_kind='ai_model'` (`finalize_ai_outcome`) — recorded as provenance but *excluded* from the human-truth feedback export (see feedback section). Papers that already have human truth are never overwritten (`preserve_human_route`).

### Recovery + regression tooling
- `recover_gemini_candidates.py` (446) recomputes Gemini priorities from historical Gemma `raw_data`, ranks raw-positive/normalized-empty rows against the 500-candidate soft reservoir target, and **dry-runs by default** (apply mode capped at 200/run) — so a backfill can never stampede the live queue.
- `flash_lite_triage_experiment.py` (245) samples known useful/no-data papers, runs Flash-Lite against the same contract, and reports agreement / useful-recall / no-data false-positive rate — the regression gate kept around the triage stage now that it is production, not experiment.

### Trade-offs, summarized
- **Recall sacrificed for cost/precision:** ~20 Gemini calls/day means most of 1500 screened papers wait; the priority funnel makes that acceptable by always processing the best first, and `recover_gemini_candidates.py` revisits the rest later.
- **Determinism over flexibility:** strict unit/basis acceptance rejects exotic-but-real rows (e.g., dry-matter basis) to keep the database clean and payload hashing exact.
- **Two encodings of one judgment:** the "what is useful" rule lives both in the prompt and in the priority penalties — duplication, but it keeps the screener's *ranking* aligned with the extractor's *decision*.
## Database — schema, RLS, RPCs, workflow engine *(Arciel)*

**File read for this section:** `apps/expert-annotator/migration.sql` (5,396 lines) — table definitions, constraints, the security-predicate functions, `claim_paper_stage_tasks`, the deterministic payload builders, the queue RPCs, and the RLS region. **43 commits.** Object counts: **31 tables, 26 functions/RPCs, 75 RLS policies, 32 RLS-enabled tables, 69 indexes, 2 triggers, 22 `SECURITY DEFINER` functions.** This one file is the contract between the Python pipeline and the React app.

### Migration discipline — idempotent and self-healing
The whole file is written to run repeatedly against a live database without breaking. Columns are added with `ADD COLUMN IF NOT EXISTS`; `CHECK` constraints are dropped-and-recreated inside `DO $$ … $$` blocks that first query `information_schema.table_constraints` (so re-running never errors on an existing constraint); a legacy `food_items.food_fdc_id` of the wrong type is detected and converted in place. This is what lets `run-migration.js` re-apply the schema safely after every change — the alternative (numbered migrations) was rejected in favour of one convergent file.

### Layer 1 — canonical reference model
`entities` (canonical foods, `UNIQUE canonical_name`), `entity_aliases` (`UNIQUE(entity_id, alias_name)`), `master_nutrients` (`UNIQUE standard_name`, `sort_rank`), `sources` (provenance + `source_metadata` jsonb), and `claims` — the normalized output: `entity × nutrient × source` with `amount`, `unit`, `basis` (default `per_100g`), `preparation_state`, `sample_size`, `confidence`, `extraction_method`, `status`. Foreign keys cascade so deleting a food cleans up its aliases and claims. This layer is read-shared across all users; only the service role writes it (via ETL).

### Layer 2 — discovery model + the dedup engine
`papers` is the hub: `id SERIAL`, `doi` **and** `canonical_key` (DOI when a reliable external id exists, `canonical_key` for missing-DOI/cross-provider dupes), `filename`, `pdf_url`, `workflow_language CHECK IN ('en','tr')`, `search_gate_score`/`filter_score`, `ingest_status`, `audit_flag`, `rejection_reasons` jsonb, and the AI-routing summary columns (`current_stage_key`, `routing_status`, `routing_bucket`, `route_destination`, `latest_ai_extraction_id`, `routing_updated_at`). Three `CHECK` constraints pin the routing vocabulary to exact enums (7 statuses, 4 buckets, 5 destinations) — the same constants hard-coded in `ai_routing.py`, so the DB rejects any value the router doesn't know.

`paper_search_hits` is the idempotent discovery ledger. Its `hit_key` is an **md5 of `canonical_key|source|language|template|term|phrase|query`** computed in SQL; the migration backfills it for legacy rows, **deletes duplicates** with a `ROW_NUMBER() OVER (PARTITION BY hit_key)` window, then adds a `UNIQUE` index — so repeated crawls never create duplicate hit rows. `paper_search_batches` + `paper_search_batch_hits` store per-query-batch funnel counters (`results`, `search_gate_passed/rejected`, `filter_passed`, `duplicates`, `accepted`, `pdf_fetch_fail`, `pdf_validation_fail`) **separately** from hit evidence, so the feedback loop can score exact query batches by downstream yield without polluting the idempotent hit table. A backfill `INSERT … SELECT … GROUP BY` reconstructs legacy batches from existing hits.

### Layer 3 — annotation model
`annotations` (`UNIQUE(paper_id, user_id)` — one session per user per paper, `status` draft/done/skipped), `food_items` (→ `entities`, `is_custom_food`, `raw_food_name`, `preparation_state`), `annotation_nutrient_values` (→ `master_nutrients`, `is_custom_nutrient`, `value`, `unit`, `basis`, `sample_size`, `confidence CHECK 0..1`, `metadata` jsonb), plus `paper_label_events` (audit history) and `paper_global_labels` (`definitely_no_data` with reason, `UNIQUE(paper_id, label)`). The custom-vs-canonical split (`is_custom_*` + nullable FK) is what lets a labeler record a food/nutrient the reference DB doesn't have yet without losing the mapping for ones it does.

### Layer 4 — the workflow engine (it was rebuilt twice, the tables prove it)
The schema preserves all three generations:
1. **Slot model (legacy):** `reviewer_slots`, `reviewer_slot_members`, `paper_slot_assignments`, `paper_user_assignments`, `paper_assignment_submissions` — official/shadow reviewers per language.
2. **Conflict model (Huan, legacy):** `paper_conflicts`, `paper_conflict_resolutions`, and the `paper_conflict_candidates` **view** — a CTE that groups the latest submission per assignment, counts `distinct_decision_count`/`distinct_payload_count`, and surfaces only papers with ≥2 submissions that actually disagree, labelling each `decision_mismatch` / `payload_mismatch` / `decision_and_payload_mismatch`.
3. **General approval queue (current):** `paper_label_submissions` (immutable, `payload_hash`, `status` pending/accepted/superseded) and `paper_label_approvals` (`UNIQUE(paper_id)`, `correction_diff_json`). Final truth lands in `paper_review_outcomes` (`UNIQUE(paper_id)`, `resolution_source`, plus a later `truth_source_kind` distinguishing human vs `ai_model`).

A `BEFORE INSERT/UPDATE` trigger (`enforce_human_review_ready_assignment`) refuses to attach an assignment to a paper that isn't `human_review_ready` — a schema-level guard against routing bugs. Old slot tables are kept for audit only; the README/AGENTS forbid driving new work from them.

### Layer 5 — AI routing tables
`ai_extractions` (raw_data, `normalized_payload_json`, `positive/negative_threshold_snapshot`, `routing_bucket`, `route_destination`, `audit_sampled`, `finalized_without_human`, `status`), `routing_stage_configs` (the data-driven stage table: thresholds, `fallback_model_names` jsonb-array with a `jsonb_typeof = 'array'` CHECK, `no_data_route_destination`, `model_input_mode` text/pdf), and `paper_stage_tasks` (`status`, `priority`, `attempt_count`, `last_error`, `UNIQUE(paper_id, stage_key)`). The seed `INSERT`s show the model history in the data itself: `gemini_flash_triage_v1` (`gemini-3-flash-preview`) was seeded then deactivated; `gemini_flash_db_payload_v2` (`gemini-3.5-flash`) is the final stage with `no_data_route_destination = 'provisional_skip'`.

### The security model — least privilege over 31 tables
**75 RLS policies** on **32 RLS-enabled tables**, built on six `SECURITY DEFINER` predicate functions:
- `current_auth_email()` — the JWT email, lowercased.
- `current_user_has_cockpit_access()` — `cockpit_access OR tester_access`, active, matched by `auth_user_id` **or** email (so a profile works before the auth row links).
- `current_user_is_tester()`, and the key one-liner **`current_user_can_write() = NOT current_user_is_tester()`** — read-only tester access falls out of a single negation rather than being re-encoded per table.
- `current_user_has_cockpit_write_access() = cockpit AND can_write`, `current_user_can_approve_labels() = can_write AND can_approve_labels`.

Because these are `SECURITY DEFINER`, the RPCs can expose aggregates and queue slices without granting any authenticated user direct reads of `paper_stage_tasks`, `ai_extractions`, or other users' annotations. The **signup allowlist** is enforced by `hook_restrict_signup_by_email_allowlist(event jsonb)` — a `SECURITY DEFINER` auth hook granted only to `supabase_auth_admin`, with `EXECUTE` revoked from `anon`/`authenticated` and all table privileges on `allowed_auth_emails` revoked from the client roles, so the allowlist can be neither read nor bypassed from the browser. `upsert_reviewer_admin_config` even refuses to complete if it would leave **zero** active cockpit-write reviewers — you cannot lock the whole team out.

### Concurrency primitive — `claim_paper_stage_tasks`
The single most important RPC for the automation: `SECURITY DEFINER`, requires `service_role`, and claims queued tasks with
```sql
SELECT id FROM paper_stage_tasks
WHERE status='queued' AND (p_stage_key IS NULL OR stage_key=p_stage_key)
ORDER BY attempt_count ASC, priority DESC, created_at ASC, id ASC
LIMIT … FOR UPDATE SKIP LOCKED
```
then flips them to `processing` and bumps `attempt_count`. **`FOR UPDATE SKIP LOCKED`** is what lets the five parallel GitHub Actions drain workers grab *disjoint* sets of tasks with zero coordination and zero double-processing — the entire parallel-worker design rests on this one clause. The `ORDER BY` is the retry-fair ordering (lowest attempts first) enforced at the database.

### Deterministic payload builders (why AI output == human output)
`build_annotation_submission_payload(annotation_id, decision_kind)` assembles the canonical submission JSON straight from `food_items` + `annotation_nutrient_values`, with `normalize_submission_text()` (collapse whitespace), `round(value, 6)`, and a long deterministic `ORDER BY`. It produces **byte-identical structure** to the Python `normalize_ai_payload` — so a human submission and an AI extraction of the same data hash identically, which is what makes exact-match comparison and dedup work across the human/AI boundary.

`build_label_payload_diff(original, final)` is a full structural diff in SQL: it explodes both payloads into food-level and nutrient-level rows with composite keys, then computes `missing_foods`/`added_foods`/`missing_nutrient_rows`/`added_nutrient_rows` via `NOT EXISTS` anti-joins, plus decision-change flags and counts. Its output is stored as `paper_label_approvals.correction_diff_json` — the exact record of what the approver changed versus what the labeler submitted, which is the raw material for labeler-performance metrics.

### Queue + cockpit RPCs
- `get_general_queue_papers` / `get_general_queue_cards` encode the precise "visible paper" predicate: `routing_status='human_review_ready'` **AND** non-empty `pdf_url` **AND** latest AI decision `has_data` **AND** `NOT EXISTS` (a final outcome, a pending/accepted submission, an open legacy assignment, or a `definitely_no_data` global label). `get_general_queue_cards` returns the whole queue — minimal card fields joined with the latest AI payload **and this user's annotation status** — as **one jsonb round-trip** (the performance redesign that replaced three separate fetches).
- `get_cockpit_ai_extractions` is deliberately **egress-slim**: it returns the normalized payload and only `raw_data->'normalization_summary'`, dropping the large raw model response/reasoning. AGENTS explicitly forbids reverting it to `select('*')` because that burns Supabase egress.
- `get_pipeline_ops_snapshot` (≈500 lines) backs the cockpit Pipeline funnel with stage-level queue/error aggregates, role-stable model-stage labels, and `model_stage_backfill` so historical direct Small→Strong papers count into the Medium stage.

### Trade-offs
- **One convergent migration file** (not numbered migrations): simpler to reason about and re-apply, at the cost of a 5,396-line file with lots of defensive `DO` blocks.
- **Legacy tables kept, not dropped:** the slot/conflict generations remain for audit history, accepting schema bloat to preserve provenance.
- **Determinism enforced twice** (SQL builder + Python normalizer): duplicated ordering logic, but it's the only way the two producers of truth can be compared by hash.
- **General queue tolerates duplicate submissions** (no row-level claim/lock on papers): simpler concurrency, redundant labeling resolved at approval instead of prevented.
## Paper-discovery crawler v2 — Search → Filter → Acquisition *(Arciel)*

**Files read for this section:** `food_paper_crawler/crawler_v2.py` (2,215 lines), `ranking.py` (486), with the source adapters `europe_pmc.py`, `dergipark_source.py` (687), `search_sources.py`. **30 commits.** `FoodCompositionCrawlerV2` is a ~2,200-line orchestrator class with ~70 methods.

### Architecture and why it's staged
`run()` executes **Search → Filter → Acquisition** so the expensive step happens last:
1. **Search** — metadata-only retrieval from Europe PMC / OpenAlex / Semantic Scholar (DergiPark for Turkish) via per-source query rendering.
2. **Filter** — a two-gate, purely *additive* relevance decision on title+abstract (no PDF downloaded yet).
3. **Acquisition** — only papers that pass the metadata filter get their PDF fetched, then a *stricter* full-text validation gate.

Downloading PDFs is slow and failure-prone, so filtering on cheap metadata first is the core efficiency decision. The run is **wall-clock bounded** (`_wallclock_reached()` against a `time.monotonic()` deadline, 2,400 s in scheduled ops); when the deadline hits it stops cleanly and still writes every accepted partial result + a manifest, so a GitHub Actions timeout never loses work.

### The two-gate additive filter (`ranking.py` + `_search_gate_decision` / `_metadata_decision`)
The relevance logic is deliberately **additive with soft penalties — never a hard veto** (a design rule in AGENTS; `b895f8a` removed the old veto logic). A single negative phrase lowers a score; it never auto-rejects.

- **Search gate** (cheap pre-filter): composition phrase +0.9, food term +0.35, nutrient term +0.35, a `mg/100g`-style **unit regex** +0.7, food+nutrient combo +0.45; penalties for a missing abstract, `STRONG_NEGATIVE_SIGNAL_TERMS` (cement, concrete, radionuclide, nanoparticle, genome, body-composition, essential-oil…), `SOFT_NEGATIVE_TERMS` (clinical trial, review, broiler, rat, feed…), and language-scoped health-outcome terms. Accept if the score clears a threshold.
- **Metadata decision** (richer): the same lexical signals at higher weights **plus** three learned signals — a **per-source prior** (clamped), a **sentence-embedding similarity** to language-scoped anchor phrases (`embedding_scorer.score`, +1.45/+0.75 above threshold), and the **learned feedback n-gram score** (below). Acceptance is `score ≥ METADATA_ACCEPT_THRESHOLD`. Every contribution is logged as a `{code, text}` reason, so each accept/reject is fully explainable in the manifest.

`ranking.py` then re-validates the **downloaded full text** with a much stricter gate (`validate_pdf_text`): it strips reference sections (EN+TR markers) so bibliographies don't inflate hits, counts AOAC/HPLC/GC/ICP method evidence and `mg/100g` units, and requires `score ≥ 18` **AND** a table signal **AND** a food signal **AND** an overlap of ≥4 with a strong proximate-nutrient panel (moisture/protein/fat/ash/fibre/carb/energy/minerals). The loose metadata gate maximizes recall into acquisition; the strict full-text gate guards precision out of it. Matching is `bounded_contains` — a `(?<!\w)…(?!\w)` Unicode word-boundary regex, so the Turkish word "et" (meat) matches as a word and not inside "diet".

### The learned feedback applied at crawl time (`_feedback_score`)
This is where the L2 loop closes back into the crawler. For each candidate it extracts title-only and title+abstract n-grams, looks each up in the language's learned `weighted_terms` (`title_net` / `ta_net` evidence produced by `update_terms.py`), multiplies by `filter_title_weight` / `filter_ta_weight`, **clamps per-term and total** so no single n-gram dominates, and logs the strongest contributors. Feedback is a *soft score only* — consistent with the no-veto rule. Learned query generation also pairs a rotated food/nutrient term with a high-confidence phrase from the matching language (`_build_learned_query`, `_build_concept_pool`), while evergreen base queries preserve breadth.

### Dedup — never crawl the same paper twice
Before searching, `run()` builds `skip_keys = local terminal states ∪ live Supabase canonical_keys`:
- `_live_paper_skip_keys()` pages **every `papers.canonical_key`** straight from the Supabase REST API (1,000-row pages), so anything already queued / provisional-skipped / human-ready / finalized is skipped at the source.
- `_state_skip_keys()` reads local `paper_states` — terminal `accepted`/`rejected` decisions with the stage they were reached at. `_record_terminal_states()` writes these after each run, **including search-gate rejects** that never became candidates, so a metadata reject isn't re-fetched next run. (Per AGENTS, metadata-only `paper_search_hits` rejects are deliberately *not* used as global skip memory — only terminal `paper_states` and live `canonical_key` are, to keep the benchmark honest.)
Accepted PDFs are named by **identity** (`pmcid_*` / `doi_*` / hashed `canonical_key`) via `build_storage_filename`, not title slugs, so the file name is a stable dedup key too.

### PDF acquisition — the genuinely hard part
Publisher PDFs fight back; `_download_candidate` → `_fetch_pdf_with_oa` → `_fetch_pdf` is a layered fallback ladder:
1. **PMC Open-Access package** (`_fetch_pdf_from_oa_package`): query the PMC OA API, parse the XML for `format="pdf"` links and `tgz` links; try the PDFs, else download the **`.tar.gz` and extract the largest `.pdf` member** (`_download_tgz_pdf` with `tarfile`). `ftp://` NCBI URLs are rewritten to `https://`.
2. **Direct fetch** (`_fetch_pdf`): urllib with a crawler User-Agent; verify the body starts with `%PDF`.
3. **On HTTP/URL error → `curl` fallback** with a full **browser User-Agent** (Chrome UA string) — many publishers block non-browser agents.
4. **If the response is HTML, solve a PMC proof-of-work**: `_solve_pmc_pow` parses `POW_CHALLENGE`/`POW_DIFFICULTY`/`POW_COOKIE_NAME` out of the page and brute-forces a **hashcash nonce** — incrementing `nonce` until `md5(challenge+nonce)` starts with `difficulty` zeros — then retries with the solution cookie. (A bot-wall defeated with an actual mining loop.)
5. **Else** scrape a nested `.pdf` href from the HTML and fetch that, else final `curl`.
A **size cap** (`max_paper_pdf_bytes`) rejects oversized PDFs; `_validate_downloaded_pdf` runs `pdftotext` and the strict `validate_pdf_text` gate; rejected files are deleted unless **audit sampling** (`_next_audit_flag`, every Nth reject) keeps them for manual QA.

### Bilingual + sources
`crawler_v2` can split its query budget across independent English and Turkish workflows with separate phrases, anchors, weighted n-grams, concept ordering, and **language-scoped embedding/metadata scoring** (`normalize_language_text` handles Turkish casing). DergiPark was rebuilt (`dergipark_source.py`, 687 lines) as a **locally refreshed journal/article index** instead of the old global OAI slice. Current ops run English-only (`tr=0`, DergiPark skipped), but the whole bilingual path is retained and tested (`test_bilingual_pipeline.py`, 1,120 lines).

### Output — a self-documenting manifest
`_build_run_summary` emits per-language, per-source funnel counts (`hits → search_gate_pass → metadata_pass → pdf_fetch_fail → pdf_validation_fail → accepted`) plus rejection counts by stage, the embedding config, the feedback phrase/anchor/weighted-term samples, and the DergiPark index coverage — so every run is auditable end to end.

### Trade-offs
- **Recall-first metadata gate, precision-first PDF gate:** accept liberally into the (cheap) download decision, reject strictly after seeing the full text — costs some wasted downloads to avoid missing real papers.
- **No hard-negative veto:** robust to one stray phrase, at the cost of needing the multi-signal score to do the discriminating.
- **Brute-force PoW + curl fallback:** fragile to publisher changes and a bit slow, but recovers PDFs that plain urllib simply cannot get.
- **Live `canonical_key` paging every run:** an extra Supabase scan, traded for never wasting a download on a known paper.
## L2 feedback-learning loop *(Arciel)*

**File read for this section:** `food_paper_crawler/feedback/update_terms.py` (1,219 lines), with `feedback_config.py`, `supabase_terms.py`, `feedback_terms.py`. This is the closed loop that makes the crawler *learn* from human labels rather than relying only on a fixed lexicon.

### The loop
```
human approvals (paper_review_outcomes) ──▶ log-odds n-gram scoring ──▶ latest.json
        ▲                                                                     │
        └──────────────── better-ranked next crawl ◀── crawler _feedback_score
```
Every run reads accepted human truth, recomputes which words/phrases predict a *useful* paper versus a *useless* one, and writes per-language weight pools that the crawler loads automatically on its next pass.

### Truth selection — only accepted human decisions count (`build_labels`)
This is deliberately conservative:
- Positives/negatives come from `paper_review_outcomes` **only when `truth_source_kind = 'human_review'`** — `ai_model` outcomes are stored for provenance but **excluded** from learning, so the model never trains on itself.
- `decision_kind='has_data'` → **good**, `no_usable_data'` → **bad**.
- **Open conflicts are removed** from both sets (ambiguous truth doesn't teach).
- Legacy `paper_label_events` / `paper_global_labels` are used **only as a fallback** for older papers that have no resolved outcome (`row.paper_id not in resolved_paper_ids`).
Pending/superseded submissions never feed learning — only finalized truth.

### The scorer — smoothed log-odds over three buckets (`build_scored_terms` + `log_odds`)
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

### The derived pools (all per language, written to `latest.json`)
`build_scored_terms` is the core; `main()` then derives and writes, for **each of `languages.en` / `languages.tr`**:
- **`weighted_terms`** — `{title_net, ta_net, good, bad}` per term (the crawler's soft filter score).
- **`query_phrases`** (`_query_rank`/`select_query_phrases`) — top terms to pair with food/nutrient terms into new search queries.
- **`anchor_phrases`** (`_anchor_rank`) — phrases used as **embedding anchors** for the semantic similarity gate.
- **`pair_scores`** (`build_search_pair_feedback`) — observed yield of `source × term` pairs.
- **`batch_scores`** (`build_search_batch_feedback`) — yield of exact query batches, so good query batches are re-run and weak ones demoted.
- **`source_priors`** — per-source positive/negative bias.
- **`concept_scores`** (`build_concept_feedback`) — standalone concept-term yields.

So three distinct learned signals reach the crawler from one labeled corpus: **soft n-gram scores** (filter), **anchor phrases** (embedding), and **pair/batch/source/concept scores** (query generation and ranking).

### When it runs
Daily ops refreshes feedback **only when it actually reaches the crawler/refill path** — `ensure_paper_stock.run_refill_cycle` runs `update_terms.py` immediately before search unless `--skip-feedback` is passed. Pure queued-AI draining does not refresh feedback (no new truth, no point). DergiPark refresh is gated behind an explicit Turkish deficit.

### Trade-offs
- **Soft scores only, never hard rejects** — consistent with the crawler's no-veto rule; a learned-negative term lowers rank but can't block a paper a human might still want.
- **Needs label volume** — with few labeled papers the log-odds are noisy; the seed priors + background smoothing keep early behavior sane, and AGENTS lists "train the L2 classifier once label volume supports it" as a standing priority.
- **Background-corpus assumption** — treats unlabeled papers as a neutral reference, which is approximately (not perfectly) true.
## Daily-ops orchestration + GitHub Actions infrastructure *(Arciel)*

**Files read for this section:** `scripts/daily_ops_orchestrator.py` (2,358 lines — its full method map + the controller and drain entrypoints), `.github/workflows/daily-ops.yml`, `apps/expert-annotator/api/pdf.js` (102), with `scripts/ensure_paper_stock.py` (573) and `scripts/upload_to_supabase.py` (774). **27 commits** on the orchestrator alone.

### The problem
Run a real, continuous data pipeline — crawl, upload, screen ~1500 papers/day, triage, extract — **for free**, on GitHub-hosted runners with a per-job time cap, against the Gemini free-tier daily quota, with no dedicated server. Every architectural choice here is downstream of that constraint.

### Architecture — one serialized controller + a parallel drain matrix
`.github/workflows/daily-ops.yml` runs on a **5-minute cron** and launches two jobs:
- **`refill-controller`** — the *only* job allowed to crawl/upload/refill. It runs under a `concurrency: { group: daily-ops-refill-controller, cancel-in-progress: false }` so **at most one controller ever runs at a time** and a new tick never kills an in-flight crawl. It installs the *full* crawler stack (`requirements.txt` + `poppler-utils`) and keeps a stable HuggingFace cache.
- **`drain-workers`** — a `matrix: worker:[1..5]` of five jobs that run **in parallel and are no longer gated on the controller** (comment in the yml: "draining must continue even if the controller job fails"). They install the *lightweight* `requirements-worker.txt` (no `sentence-transformers`) and only drain already-queued model tasks. `workflow_dispatch` exposes a `workers` input, and every worker step is guarded by `if: matrix.worker <= fromJSON(inputs.workers)` so a manual run can scale down.

Five workers can run safely in parallel because claiming goes through `claim_paper_stage_tasks` with `FOR UPDATE SKIP LOCKED` (schema section) — each worker grabs a disjoint task set with zero coordination.

### The controller logic (`run_daily_ops_controller`)
A single tick, not a long-running loop:
1. **Requeue stale tasks** for all three stages (returns `processing` rows older than 120 min to `queued`) — so a previous killed runner never strands papers.
2. **Count completed-today per stage** since that stage's **quota-day start**.
3. **Count active screening work** = queued + non-stale `processing` `paper_stage_tasks` (counted from executable rows, *not* paper routing summaries — stale `queued_for_ai` rows must not block refill).
4. Compute `controller_target = min(remaining_today, screening_active_target=150)` and `deficit = controller_target − active_screening`.
5. **Stop or refill** via an explicit decision tree: daily target reached → stop; deficit ≤ 0 (enough active work) → stop; controller deadline (75 min) reached → stop; paper-storage soft limit exceeded → stop; else **crawl `deficit` English papers in bounded 30-paper chunks** (`_run_screening_refill` → `ensure_paper_stock.run_refill_cycle`, which refreshes feedback terms then crawls+uploads), then re-measure active count and detect **source exhaustion** (refill didn't raise the active count).

The point of the *active target* (150) rather than a daily flood is the README's "keep paper stock low on purpose and refill as labeling proceeds, so each crawl benefits from newer feedback."

### The drain logic (`run_daily_ops_drain`) — a resumable quota-day tick
Each worker tick:
1. Count completed-today per stage (against quota-day starts).
2. **If screening is below its 1500/day target and has queued tasks**, drain `min(screening_tick_tasks=20, remaining_today, queue_count)` Gemma tasks (`_tick_drain_stage`), then — with `--interleave-extraction` — also drain the downstream triage + final-Gemini slices (`_tick_drain_downstream`).
3. **If screening's queue is empty, still interleave the downstream drain** — this is the "drain Gemini when Gemma source is empty" behavior: queued Flash-Lite/Gemini candidates keep flowing even when there's nothing left to screen.
4. **If screening has hit its daily target**, drain a triage tick, then drain the final-Gemini stage up to its 20/day target, then run `_assign_new_human_ready_after_ai` — one final stock check so freshly human-ready papers appear in the labeling queue immediately.
Quota-exhausted and `ai_stage_configuration_error` are distinguished as stop reasons; the run returns a machine-readable summary (`mode`, `daily_completed` per stage, `screened`, `routed_to_gemini`, `gemini_used`, `human_ready`, `quota_exhausted_stages`, `stopped_reason`, …) that the workflow parses into a one-line log.

### Quota-day accounting across two timezones
Each stage resets on its provider's schedule: **Gemma counts a UTC day**, both **Gemini stages count an `America/Los_Angeles` day** to match Google's RPD reset (`_stage_quota_day_starts` / `_quota_day_start_iso`). Completed-today counts come from `paper_stage_tasks` completion timestamps since that boundary, so the funnel spends exactly the daily budget and no more, regardless of when in the GitHub UTC schedule a tick fires.

### Engineered for the free-tier ceiling
- **Lazy module loading** (`_LazyScriptModule`): the orchestrator imports heavy crawler/upload modules only when the controller path actually needs them, so drain workers (which never crawl) don't pay the import or the dependency install.
- **Three nested wall-clock budgets:** controller job 75 min, crawler 2,400 s (writes partial accepted results before being killed), each model call 300 s (`SIGALRM`) — so one slow paper or a long crawl can never blow the GitHub job cap.
- **Paper PDFs are source-URL/on-demand** (`OPENNUTRI_STORE_PDFS_IN_SUPABASE=0`): the controller skips paper-storage cleanup and the bucket soft-limit, because storing PDFs would blow the Supabase free storage/egress caps.

### Supporting jobs
- `ensure_paper_stock.py` (573) — `run_refill_cycle`: refresh feedback terms, then crawl+upload until per-language targets are met; counts only `human_review_ready` papers with a normalized `has_data` payload and no outcome/submission as available stock.
- `upload_to_supabase.py` (774) — registers accepted papers by **canonical identity** (upsert on `canonical_key`, preserving any closed AI route or human outcome — never requeues a finalized paper just because the active model changed), upserts discovery hits by deterministic `hit_key`, persists per-query batch history, and **recovers concurrent duplicate-key races** by reusing the existing row and preserving its search-hit audit links (so two workers racing on the same paper don't fail the refill slice).

### Same-origin PDF proxy (`api/pdf.js`, Vercel serverless)
Many publisher PDFs (and EuropePMC's `?pdf=render`) lack CORS headers, so PDF.js can't fetch them in-browser. This 102-line function fetches them server-side and re-serves same-origin, with real engineering around abuse and cost: **https-only**, **SSRF hardening** (rejects `localhost`/`.local`/`.internal`, IPv4 literals, IPv6), a 25 MB cap, a **`%PDF-` magic-byte check** (so it can't be used as a generic open proxy), a 25 s `AbortController` timeout, and a **1-year `immutable` Cache-Control** so each paper is fetched from the upstream host at most once and then served from the browser + Vercel edge.

### Trade-offs
- **Lower recall for zero cost:** ~20 Gemini extractions/day is a deliberate ceiling; the priority funnel + `recover_gemini_candidates.py` make it acceptable.
- **A genuinely complex tick state machine** (controller vs drain vs combined tick, three stages, two quota timezones, interleaving) — the price of being resumable and idempotent inside a 5-minute window instead of a simple long-running daemon.
- **Controller/drain split** adds moving parts but means draining survives a controller failure and parallel workers scale throughput without locks.
## Reference-data ETL + test suite *(Arciel)*

### USDA → Supabase ETL
**Files read:** `etl_usda_to_opennutri.py` (227), `etl_sr_legacy_to_opennutri.py` (343). Two loaders seed the canonical reference layer from USDA FoodData Central CSVs into `entities` / `entity_aliases` / `master_nutrients` / `sources` / `claims` over the Supabase REST API:
- `read_csv` streams the FoodData Central dumps; `parse_preparation_state` **derives the preparation state from the food description text** (raw/cooked/dried…) so claims carry a usable `preparation_state` instead of an opaque label.
- `rest_insert(table, data, conflict_col)` does an **upsert keyed on a conflict column**, so re-running the ETL is **idempotent** — a second load updates rather than duplicating, and the reference IDs stay stable for the foreign keys in `claims`/`food_items` to point at. (README documents deterministic UUIDs for the SR-Legacy seed so the same source row always maps to the same `entities.id`.)
- The seed run is logged to `migration.log` / `migration_run.log`.

This is the layer that turns a public nutrition dataset into OpenNutri's canonical foods/nutrients, which the AI normalizer and the autocomplete then resolve against.

### Test suite — coverage concentrated on the dangerous code
**128 test functions, ~4,900 lines** of Python tests, deliberately weighted toward the logic that can silently corrupt data or burn quota:

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

### Trade-off
These are behavior/unit tests against pure logic (normalization, routing, scoring, gates) rather than full live-API integration tests — fast and deterministic in CI, but they mock the model/DB boundary, so the live Gemini/Supabase contract is validated by the offline harnesses (`flash_lite_triage_experiment.py`, `probe_model_file_input.py`) instead.
## Backend documentation, security hygiene, project management *(Arciel)*

- **Docs as a maintained system:** `README.md` (≈42 KB), `AGENTS.md` (≈28 KB — a coding-agent guide with hot-files map, task routing, product truths, and research-ops notes), `INSTRUCTIONS.md`, `BACKLOG.md`, `docs/handoff_2026-03-20/STATE.md`, reviewer SOP + workflow map, bilingual midterm reports (TR + EN), and AI-algorithm defense decks with their `export_*.py` build scripts. A standing rule (in AGENTS) keeps these updated in the same task as any behavior change.
- **Security hygiene:** removed hardcoded runtime secrets (`9c18db9`), documented env-var-only secret handling (`d3d8788`), hardened the auth allowlist RLS (`87e2a18`), and the SSRF-safe PDF proxy (`api/pdf.js`). Secrets live only in environment variables / GitHub / Vercel / Supabase secret stores.
- **Cockpit RPCs** (covered in the schema section): `get_pipeline_ops_snapshot` (the funnel), `get_cockpit_ai_extractions` (egress-slim), `get_general_queue_papers`/`_cards`, plus the reviewer-admin and read-only developer-queue controls.

## Why this is the project's largest body of work

Arciel's ~38,600 net new lines span the entire backend: a 5,396-line schema with 75 RLS policies and 26 RPCs; a 2,215-line learning crawler with a proof-of-work PDF fetcher; an 842 + 1,560 + 687-line AI cascade with a deterministic normalizer and a priority funnel; a 2,358-line orchestrator that runs real automation on free GitHub runners; a log-odds feedback learner; an ETL layer; ~4,900 lines of tests; and the documentation. The four hardest cross-cutting problems in OpenNutri all live here, and roughly 83% of it is net-new in this repository after the March pipeline snapshot.
