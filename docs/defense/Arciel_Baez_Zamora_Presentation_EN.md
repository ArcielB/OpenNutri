# OpenNutri — Arciel Aliognis Baez Zamora — Defense Presentation (English)

> **Scope of this document.** This is Arciel Baez Zamora's individual presentation script. The OpenNutri project was built by three people; their work divides as:
>
> - **Arciel Aliognis Baez Zamora — the entire backend:** the Supabase database (schema, RLS, the RPC contract, the workflow engine), the three-stage AI extraction cascade, the deterministic normalizer and confidence-gated routing, the paper-discovery crawler, the feedback-learning loop, the unattended daily-ops automation, the reference-data ETL, storage/egress/PDF-delivery hardening, the test suite, and the documentation. (~31,800 backend/ops/schema lines; `migration.sql` alone is 5,396 lines.)
> - **Ayşegül Doğan — the entire annotator frontend:** the PDF evidence engine, the annotation workspace, the food/nutrient autocomplete, and the cockpit/workflow views.
> - **Duc Huan Ngo — reusable & full-stack pieces:** the `fuzzyMatch` engine, the suggestions/attachments feature, the reset-password fix, the legacy conflict system, theme centralization, infinite scroll.
>
> This document is written in the **first person ("I")** as Arciel, and is organized in five parts:
> **1.** the general problem · **2.** how we solved it as a team · **3.** what my part is and why it is necessary · **4.** everything I built, one by one (why it is needed · how I did it · the hard part · the technologies · the files & line counts) · **5.** a closing summary.
>
> The Turkish version of this document is in a separate file: `Arciel_Baez_Zamora_Presentation_TR.md`.

---

## 1. What is the general problem?

Accurate **food-composition data** — how much protein, fat, iron or vitamin C a food contains — sits behind every nutrition label, diet app, and dietary guideline. But this data is still built **by hand**: experts read scientific papers and **type the numbers into a database one at a time.** That is slow and expensive, so the databases stay narrow and quickly go out of date. The data itself already exists — it's published constantly, just locked inside unstructured PDFs — but reading it out by hand doesn't scale, and letting an AI read it unchecked produces too many wrong numbers to trust on a food label.

## 2. How did we solve it (as a team)?

We built **OpenNutri**: instead of a person reading each paper from scratch, **the AI does the reading and proposes the numbers, and a person verifies the ones the AI is unsure about.** It splits into three parts:

- **A backend pipeline** (me) that finds relevant papers, downloads the PDFs, and runs AI models over them to produce *candidate* nutrient values — and decides which candidates are trustworthy enough to keep automatically and which need a human.
- **A database** (me) that stores everything and runs the review workflow.
- **The annotator web app** (Ayşegül's frontend) — where a human checks and corrects the candidate values the system is unsure about.

**My part is the entire backend — everything that happens before and around the human, and the database contract the human's app is built on. The rest of this document is about it.**

## 3. What is my part, why is it necessary, and what did I do?

**My part is the entire backend** — the database, the AI pipeline, the crawler, the learning loop, and the automation that runs all of it unattended, on free infrastructure, every five minutes.

**Why it's necessary.** The frontend can only ever be as good as what reaches it. Someone has to *find* the right papers out of the entire scientific literature, *get* the PDFs out of hostile publisher sites, *read* them with models cheaply enough to afford, *decide* which results are trustworthy and which need a human, *store* all of it under a security model that lets labelers, reviewers and automation each do exactly the right thing, and *keep the whole machine running* without a server and without a budget. That is the backend. Without it there is no queue, no AI prefill, no evidence to highlight, no truth to approve, and nothing for the crawler to learn from.

And it carries the project's real risk: a wrong number that the system auto-accepts goes straight into a food database; a broken RLS policy leaks private data; a stalled worker stops the whole pipeline; a crawler that admits the wrong papers wastes scarce model quota and labeler time. The backend is where "correct, cheap, and unattended" all have to be true at once.

**What I did, in one sentence:** I built a self-running research pipeline — it crawls the literature, defeats publisher bot-walls to get the PDFs, screens ~1,500 papers a day through a three-model funnel that spends its ~20 expensive extractions on the best candidates, converts each model's free-form output into the *exact* same structured shape a human would submit, decides by confidence whether to auto-finalize or route to a human, stores it all under a 75-policy security model, and learns from every human decision to crawl better next time — all on Supabase's and GitHub's free tiers. Concretely, I own seven things, which the next section walks through one by one:

1. The **database & security contract** — 31 tables, 75 RLS policies, and the RPCs every other part calls.
2. The **paper-discovery crawler** — the front door: search → filter → acquisition, with a bot-wall-defeating PDF fetcher.
3. The **three-stage AI cascade** — Gemma → Gemini Flash-Lite → Gemini Flash, one shared contract across three models.
4. The **deterministic normalizer & confidence-gated routing** — turning model output into database-comparable data and deciding human vs. auto.
5. The **feedback-learning loop** — human approvals re-score the next crawl.
6. The **daily-ops automation** — a controller + five parallel workers on a 5-minute GitHub Actions cron.
7. The **reference data, PDF/egress hardening, tests & documentation** — the supporting layer that makes it a system, not a demo.

## 4. Everything I built, one by one

For each piece: **why it is needed · how I did it · the hard part · the technologies · the files and line counts.**

---

### 4.1 The database & security contract — *the spine of the whole project*

**Why it is needed.** Every other part of OpenNutri meets here. The frontend cannot submit a label, the crawler cannot register a paper, the model workers cannot claim a task, and the dashboard cannot show truth without these tables, RPCs, and policies. This one file is the **contract** between the Python pipeline and the React app.

**How I did it.** `migration.sql` is **5,396 lines** defining **31 tables, 26 functions/RPCs, 75 RLS policies, 69 indexes, 2 triggers, and 22 `SECURITY DEFINER` functions.** It is written as **one convergent, idempotent migration** — safe to re-run against the live database any number of times: columns are added `IF NOT EXISTS`, `CHECK` constraints are dropped-and-recreated inside `DO $$ … $$` blocks that first query `information_schema` so a re-run never errors, and a mistyped legacy column is detected and converted in place. The schema is five layers:

- **Reference layer** — `entities` (canonical foods), `entity_aliases`, `master_nutrients`, `sources`, and `claims` (the normalized `food × nutrient × source` fact with amount, unit, basis, confidence, provenance). Read-shared by everyone; written only by the service role.
- **Discovery layer** — `papers` (the hub, with both `doi` and a `canonical_key` for missing-DOI/cross-provider dedup, plus the routing-summary columns), and the idempotent discovery ledger `paper_search_hits` whose `hit_key` is an md5 computed *in SQL*, with duplicate rows deleted by a `ROW_NUMBER()` window before a `UNIQUE` index is added. Separate `paper_search_batches` tables store per-query funnel counters for the feedback loop.
- **Annotation layer** — `annotations` (`UNIQUE(paper_id, user_id)`), `food_items`, `annotation_nutrient_values`, with the custom-vs-canonical split (`is_custom_*` + nullable FK) that lets a labeler record something the reference DB doesn't have yet without losing the mapping for the ones it does.
- **Workflow engine** — rebuilt twice, and the schema **proves it**: the legacy slot model, Huan's legacy conflict model (including the `paper_conflict_candidates` view), and the current **general queue + approval** model: immutable `paper_label_submissions`, `paper_label_approvals` (with a structural `correction_diff_json`), and final `paper_review_outcomes`. A `BEFORE INSERT/UPDATE` trigger refuses to attach work to a paper that isn't `human_review_ready` — a schema-level guard against routing bugs.
- **AI-routing layer** — `ai_extractions` (the full audit trail), `routing_stage_configs` (the **data-driven stage table** — thresholds, fallback models, input mode — so the pipeline's shape is data, not code), and `paper_stage_tasks` (the work queue).

**The security model** is least-privilege across all 31 tables: **75 RLS policies** built on six `SECURITY DEFINER` predicate functions. The elegant one: **`current_user_can_write() = NOT current_user_is_tester()`** — read-only training access falls out of a *single negation* instead of being re-encoded on every table. Because the predicates are `SECURITY DEFINER`, the RPCs can expose queue slices and aggregates without ever granting a browser user direct reads of `paper_stage_tasks`, `ai_extractions`, or other people's annotations. The **signup allowlist** is enforced by an auth hook granted only to `supabase_auth_admin`, with all client privileges on the allowlist table revoked — so it can be neither read nor bypassed from the browser. And `upsert_reviewer_admin_config` refuses to complete if it would leave **zero** active cockpit-write reviewers: you cannot lock the whole team out.

Two pieces of the contract deserve singling out:
- **`claim_paper_stage_tasks`** — the concurrency primitive. It claims queued tasks `ORDER BY attempt_count ASC, priority DESC … FOR UPDATE SKIP LOCKED`. That one clause, `FOR UPDATE SKIP LOCKED`, is what lets five parallel GitHub Actions workers grab *disjoint* task sets with zero coordination and zero double-processing — the entire parallel design rests on it.
- **The deterministic payload builders** — `build_annotation_submission_payload` assembles the canonical submission JSON in SQL with the *same* whitespace-collapsing, `round(value,6)`, deterministic-ordering rules as the Python normalizer, so a human submission and an AI extraction of the same data **hash identically**. `build_label_payload_diff` is a full structural diff in SQL (anti-joins for added/missing foods and nutrient rows) whose output is the raw material for labeler-performance metrics.

**The hard part.** Making one file safe to re-apply forever, *and* giving labelers, testers, cockpit users, approvers and the service-role automation each exactly the right surface across 31 tables without leaking a single private row — while keeping AI and human payloads deterministic enough to compare by hash.

**Technologies.** PostgreSQL / Supabase, PL/pgSQL, Row-Level Security, `SECURITY DEFINER` functions, `FOR UPDATE SKIP LOCKED`, JSONB, SHA-256-comparable canonical payloads.

**Files & lines.** `apps/expert-annotator/migration.sql` (**5,396**). **43 commits.**

---

### 4.2 The paper-discovery crawler — *the front door of the system*

**Why it is needed.** If the crawler admits the wrong papers, scarce model quota and labeler time are wasted; if it's too strict, the pipeline never finds the real composition tables. The crawler **encodes the product's domain definition** into scoring, validation, and dedup. Most papers returned by broad nutrition queries are *not* direct food-composition tables — they're intervention studies, feed trials, reviews — so the crawler has to narrow candidates before any expensive work, **without** hard-rejecting a real paper over one stray word.

**How I did it.** `FoodCompositionCrawlerV2` is a ~2,200-line orchestrator (~70 methods) running **Search → Filter → Acquisition**, so the expensive step happens last:

1. **Search** — metadata-only retrieval from Europe PMC / OpenAlex / Semantic Scholar (DergiPark for Turkish), per-source query rendering.
2. **Filter** — a two-gate, purely **additive** relevance decision on title+abstract, **no PDF downloaded yet**. The rule (enforced in AGENTS) is *no hard-negative veto* — a negative phrase is a penalty, never an auto-reject, so one word like "clinical trial" can't kill a paper that also reports a composition table. The cheap search gate scores composition phrases, food/nutrient terms, a `mg/100g`-style unit regex, and food+nutrient combos against soft penalties; the richer metadata gate adds three **learned** signals — a per-source prior, a **sentence-embedding similarity** to language-scoped anchor phrases, and the **learned feedback n-gram score** (§4.5). Every contribution is logged as a `{code, text}` reason, so each decision is fully explainable in the run manifest.
3. **Acquisition** — only metadata-passers get their PDF fetched, then a **much stricter full-text gate** (`validate_pdf_text`): it strips reference sections so bibliographies don't inflate the score, counts AOAC/HPLC/GC/ICP method evidence and `mg/100g` units, and requires a strong score **and** a table signal **and** a food signal **and** an overlap of ≥4 with a proximate-nutrient panel (moisture/protein/fat/ash/fibre/carb/energy/minerals). Loose into download for recall, strict out of it for precision. Word-matching is Unicode word-boundary-aware so the Turkish word "et" (meat) matches as a word, not inside "diet".

**The genuinely hard part — PDF acquisition.** Publisher PDFs fight back. `_download_candidate` is a layered fallback ladder: PMC Open-Access package (parse the OA API XML, try the PDF links, else download the **`.tar.gz` and extract the largest `.pdf` member**); direct `urllib` fetch (verify the body starts with `%PDF`); on failure a **`curl` fallback with a full browser User-Agent** (many publishers block non-browser agents); and if the response is an HTML bot-wall, **solve a PMC proof-of-work** — `_solve_pmc_pow` parses the challenge out of the page and **brute-forces a hashcash nonce** (incrementing until `md5(challenge+nonce)` starts with N zeros), then retries with the solution cookie. A bot-wall defeated with an actual mining loop.

The crawler **never crawls the same paper twice**: before searching it builds a skip-set from every live `papers.canonical_key` (paged straight from the Supabase REST API) plus local terminal paper states (including search-gate rejects, so a metadata reject isn't re-fetched). Accepted PDFs are named by **identity** (`pmcid_*` / `doi_*` / hashed `canonical_key`), and the whole run is **wall-clock bounded** — when the 2,400-second deadline hits it stops cleanly and still writes every accepted partial result plus a self-documenting funnel manifest, so a GitHub timeout never loses work.

A small but load-bearing module, `models.py`, defines the **three deterministic identity keys** (`build_canonical_key`, `build_search_hit_key`, `build_search_batch_key`) that the crawler, every source adapter, the uploader, and the feedback exporter all import — so a paper computes the *same* identity everywhere, which is what makes the SQL `UNIQUE` indexes, the skip-set, and batch feedback all line up without a central coordinator.

**Technologies.** Python, Europe PMC / OpenAlex / Semantic Scholar / DergiPark, `urllib` + `curl`, `tarfile`, `pdftotext`, sentence-transformers embeddings, MD5 hashcash proof-of-work, Supabase REST.

**Files & lines.** `food_paper_crawler/crawler_v2.py` (**2,215**), `ranking.py` (485), `models.py` (374), `embeddings.py` (138), `dergipark_source.py` (687) and the other source adapters. **30 commits.**

---

### 4.3 The three-stage AI cascade — *Gemma → Gemini Flash-Lite → Gemini Flash*

**Why it is needed.** The final, strong Gemini extraction is the scarce, expensive resource — about **20 calls a day** on the free quota. Screening every candidate with the strongest model would burn that budget on mostly-useless papers. So every accepted paper passes a **three-stage funnel** that processes many candidates cheaply, then spends the expensive calls only on the **top-ranked** subset:

```
Small  — gemma_proof_extraction_v1   (gemma-4-31b-it, 26B fallback)  text mode    ~1,500/day
Medium — gemini_flash_lite_triage_v1 (gemini-3.1-flash-lite)                       ~500/day
Strong — gemini_flash_db_payload_v2  (gemini-3.5-flash)              native PDF    ~20/day
                                                                                     │
                                                                       human_review_ready
```

**How I did it.** All three stages run the *same* shared extraction contract against one prompt (`opennutri_evidence_payload_v2`). The prompt **is** the product's domain definition in code: it spends ~25 lines enumerating exactly what "useful OpenNutri data" is (direct food/product composition) versus what is **empty** (intervention/effect studies, one-off experimental formulations, digestibility, sensory, biomarkers, review aggregates) — the difference between a database of real foods and a pile of irrelevant agronomy papers. Each extracted row must carry **evidence-location metadata** — `table_label`, `page_hint`, a short verbatim `source_quote` (≤20 words), `source_location_type`, `section_heading`, `paragraph_hint` — so Ayşegül's frontend can later highlight it. The single most important instruction in the whole prompt: `page_hint` is the **1-based PDF page index from the `===== PDF PAGE N =====` markers, never the printed journal page** — because the printed-page mismatch is exactly what breaks highlighting.

Two robustness mechanisms make this survivable in production:
- **Surviving model JSON drift.** LLMs constantly return malformed or differently-shaped JSON; naively that's an infinite retry loop. The evaluator strips markdown fences, runs a **hand-written balanced-bracket scanner** that tracks string/escape/depth state to extract the first *balanced* JSON even when it's wrapped in prose, and accepts **four different shapes** (the requested object, a bare row array, a one-element-array-wrapped object, and nested `food → nutrients[]`), all coerced to one canonical root. A row missing a required field is dropped, not fatal. So valid-but-differently-shaped output is salvaged instead of triggering a retry.
- **Native PDF input + true page numbers.** For the strong stage the PDF is attached as a native document part (inline under 15 MB, otherwise via the Files API with a `finally` cleanup that deletes both the temp file and the remote upload), which gives the model rendered pages and tables and lets it report the true page. For text-mode stages, `pdftotext` output is split on form-feeds and injected with `===== PDF PAGE N =====` markers **before** any truncation, so surviving pages keep correct numbers. **Why Gemma stays text-mode:** a probe measured Gemma *accepting* PDF parts but **timing out past 600 s on a 5-page PDF** — fatal for a ~1,500/day stage — so it gets page-marked text, which already gives correct page numbers without image rendering. That decision is encoded and documented so it isn't naively reverted.

**The execution engine** (`process_stage_queue.py`, 1,560 lines) is built so **no single bad paper or quota blip can stall automation**: tasks are claimed atomically (`claim_paper_stage_tasks`); ordered **lowest-attempt-first** so a repeatedly-failing paper can't monopolize; stale `processing` rows older than 120 min are requeued; the model is constructed *before* any row is claimed so a missing key fails fast; a hard `SIGALRM` per-paper timeout (300 s) bounds one slow paper; and an **error taxonomy** routes failures correctly — non-retryable model-config errors fail and stop automation, retryable errors try the configured fallback model (Gemma 31B → 26B) **in the same attempt**, quota errors requeue but **decrement the attempt count** so a quota wait never looks like a paper failure, and anything past two non-quota attempts fails instead of looping forever.

**The hard part.** Making one contract work across three different models with different input modes and failure behaviors, keeping the output useful for *database insertion* (not just a plausible summary), and building error handling that correctly distinguishes quota from a retryable runtime failure from a non-retryable config error — because each one has to be handled differently or the unattended queue breaks.

**Technologies.** Python, Gemma + Gemini (Google GenAI SDK), native-PDF + text input modes, `pdftotext`, `SIGALRM` timeouts, a hand-written JSON-recovery parser, Supabase RPCs.

**Files & lines.** `evaluator/unified_evaluator.py` (687), `ai_routing.py` (842), `scripts/process_stage_queue.py` (1,560), plus `recover_gemini_candidates.py` (446) and `flash_lite_triage_experiment.py` (245). **34 commits.**

---

### 4.4 The deterministic normalizer & confidence-gated routing — *where a guess becomes trustworthy data, or a human's job*

**Why it is needed.** A model's raw output is not trustworthy database data. Two things have to happen before it can be kept: it must be converted into the **exact same normalized structure a human reviewer would submit** (so AI and human output are interchangeable and comparable), and the system must **decide, by confidence, whether to keep it automatically or send it to a human** — because checking every paper by hand is what *doesn't* scale, but auto-accepting everything is what produces wrong numbers. This is the heart of "AI proposes, a human verifies the ones it's unsure about."

**How I did it — the normalizer (`normalize_ai_payload_with_summary`).** Each model row runs a strict gauntlet:
1. **Required-field gate** — drop any row missing food/nutrient/amount (counted as `missing_required_field`).
2. **Unit standardization (`_standardize_unit`)** — the strict gatekeeper. Only seven standard units survive: `g/100g`, `mg/100g`, `μg/100g`, `kcal/100g`, `kJ/100g`, `IU/100g`, `%`. It handles `µ`-vs-`μ`, casefolding, every spelling of gram/milligram/microgram/mcg/kcal/kJ/IU, and a **basis policy**: per-100g required, **dry-matter rejected**, but fresh/wet/as-is/edible-portion accepted. Rejections counted as `unsupported_unit_or_basis`.
3. **Reference resolution (`_resolve_reference_row`)** — **ID-first** (verify the model's claimed `food_fdc_id`/`nutrient_id` against a live row *and* that the row's name matches), then exact name, then alias. The name resolver maps **ambiguous names to nothing** — if two DB rows share a name, neither matches — so it never makes a wrong link. Unresolved foods/nutrients are *kept* as explicit `is_custom_food`/`is_custom_nutrient` rows, not dropped.
4. **Deterministic grouping & ordering** — rows group by resolved food, sort by a long stable key, values `round(…, 6)`. This determinism is the whole point: the payload is **canonically serialized and SHA-256 hashed**, so two equal extractions hash identically and an AI extraction is byte-comparable to a human submission.
5. **Summary accounting** — accepted/rejected/unmapped counts and a `rejection_reasons` histogram are stored on every extraction, so the cockpit can show *why* rows were dropped.

**How I did it — the confidence gate (`ai_routing.py`).** After normalization the paper is bucketed and routed:
- **`classify_routing_bucket`** sorts each paper into **high/low × positive/negative** by comparing its `overall_confidence` against the stage's own `positive_threshold` / `negative_threshold` (separate thresholds for "has data" and "no data", read from the data-driven stage config).
- **`route_bucket`** is the actual gate: **low-confidence → `human_review_ready`** (it goes to Ayşegül's labeling queue); **high-confidence-positive → `ai_finalized_has_data`** (auto-kept); high-confidence-negative → finalized as no-data. A paper that already has human truth is never overwritten.
- **`stable_audit_sample`** is the quality check on the auto-accepted ones: `SHA256(paper|stage|model)` compared against `audit_rate × 2^64`. It's **deterministic** — the same paper always gets the same audit decision — and it forces a configurable fraction of even high-confidence auto-finalizations back to human review, so the auto-accept path is continuously sampled for correctness rather than trusted blindly.
- **Raw-positive rescue** — a Gemma output that looks positive but normalizes to *empty* still advances to the next stage if it had complete raw rows, or confidence ≥ 0.75, or ≥ 0.6 with composition language — so parser/normalizer drift never silently drops a likely-real paper, while strict normalization still gates final entry.

And the funnel's engine, **`score_followup_priority`**: every useful output gets an integer score (clamped −1000…1000) from confidence, accepted/evidence/per-100g/table row counts, a direct-fit bonus for composition language, and **soft penalties** that mirror the prompt's "empty" definition (review/meta-analysis, feed/digestibility, sensory/biomarker, one-off formulation, treatment/extract). The next stage claims tasks *ordered by this score*, so Flash-Lite processes the best 500 of Gemma's output and the final Gemini the best 20 of that. The "what is useful" judgment is encoded twice on purpose — once in the prompt for the model, once in the priority for the ranker — so the screener's ranking stays aligned with the extractor's decision.

**The hard part.** Determinism across the human/AI boundary: getting a Python normalizer and a SQL builder to produce **byte-identical** structure so the two producers of truth can be compared by hash — and designing a confidence gate that is *reproducible* (same paper, same decision, every time), *auditable* (you can always see why), and *self-checking* (a sampled fraction of auto-accepts is forced back to humans), rather than a black-box "the model seemed confident."

**Technologies.** Python, SHA-256 canonical hashing, deterministic JSON serialization, threshold-based bucketing, reproducible hash-based audit sampling, PL/pgSQL mirror builders.

**Files & lines.** `ai_routing.py` (842) with `test_ai_routing.py` (**2,469 lines, 60 tests** — the most heavily tested file in the project, because this is where a bug silently corrupts the database). **34 commits across the cascade.**

---

### 4.5 The feedback-learning loop — *human approvals teach the next crawl*

**Why it is needed.** This is what makes OpenNutri an *improving* pipeline instead of a static keyword crawler. Every paper a human approves or rejects is evidence about which words and phrases predict a genuinely useful paper — and that evidence should change how the crawler scores candidates next time.

**How I did it.** `update_terms.py` (1,219 lines) closes the loop:
```
human approvals (paper_review_outcomes) ─▶ log-odds n-gram scoring ─▶ latest.json ─▶ next crawl ranks better
```
- **Truth selection is deliberately conservative.** Positives/negatives come from `paper_review_outcomes` **only when `truth_source_kind = 'human_review'`** — AI-finalized outcomes are stored for provenance but **excluded**, so *the model never trains on itself*. Open conflicts are removed (ambiguous truth doesn't teach); pending/superseded submissions never count; legacy labels are a fallback only for old papers with no resolved outcome.
- **The scorer is smoothed log-odds over three buckets** — good, bad, and **background** (everything else). For every n-gram, document frequencies are counted in each bucket, **separately for title-only and title+abstract**, then informative Dirichlet log-odds (the Monroe et al. method) are computed with add-α smoothing. The net signals `title_net = title_good − title_bad` and `ta_net` are exactly what the crawler multiplies in. The **background bucket is the key to specificity**: scoring good-vs-bad alone just rewards common words; scoring each against the large background corpus surfaces terms that are genuinely *distinctive* of useful papers. Title and title+abstract are kept separate because a high-signal phrase in a *title* is stronger evidence than the same phrase buried in an abstract. Seed composition phrases get a *soft* prior that learned evidence can override over time.
- **It produces seven per-language pools** into `latest.json`: `weighted_terms` (the soft filter score), `query_phrases` (to build new searches), `anchor_phrases` (the embedding anchors), `pair_scores`, `batch_scores`, `source_priors`, and `concept_scores` — so three distinct learned signals reach the crawler from one labeled corpus: n-gram filter scores, embedding anchors, and query-generation/ranking scores.

**The hard part.** Making sure the system **doesn't train on itself** and **doesn't learn from ambiguous truth** — and keeping feedback a *soft* score that can lower a rank but never hard-reject a paper a human might still want, consistent with the crawler's no-veto rule. Plus the statistics: the background-corpus log-odds and add-α smoothing are what keep a small, noisy early label set from producing garbage weights.

**Technologies.** Python, smoothed/informative-Dirichlet log-odds (Monroe et al.), n-gram document-frequency counting, per-language weight pools, Supabase truth export.

**Files & lines.** `food_paper_crawler/feedback/update_terms.py` (**1,219**), with `feedback_config.py`, `supabase_terms.py` (481), `feedback_terms.py`.

---

### 4.6 The daily-ops automation — *a real pipeline that runs itself, for free*

**Why it is needed.** All of the above has to actually *run* — crawl, upload, screen ~1,500 papers/day, triage, extract — continuously, with no dedicated server and no budget. Every architectural choice here is downstream of one constraint: do it on GitHub-hosted runners with a per-job time cap, against the Gemini free-tier daily quota.

**How I did it.** `.github/workflows/daily-ops.yml` runs on a **5-minute cron** and launches two kinds of job:
- **One serialized `refill-controller`** — the *only* job allowed to crawl/upload/refill, under a `concurrency` group with `cancel-in-progress: false`, so at most one ever runs and a new tick never kills an in-flight crawl.
- **Five parallel `drain-workers`** (`matrix: worker:[1..5]`) that only drain already-queued model tasks, are **not gated on the controller** ("draining must continue even if the controller fails"), and install a lightweight dependency set. Five can run safely in parallel **only because** claiming goes through `FOR UPDATE SKIP LOCKED` — each grabs a disjoint task set with zero coordination.

The **controller** is a single tick, not a loop: requeue stale tasks → count completed-today per stage → count *active* screening work → compute a deficit against an **active target of 150** (kept low on purpose so each crawl benefits from newer feedback) → then an explicit stop/refill decision tree (daily target reached, or enough active work, or the 75-minute deadline, or a storage limit → stop; else crawl the deficit in bounded 30-paper chunks and detect source exhaustion). The **drain** tick drains a Gemma slice if screening is below its 1,500/day target, **interleaves** the downstream triage + final-Gemini slices (so Gemini keeps flowing even when there's nothing left to screen), and when screening hits its target, drains the final Gemini up to 20/day and assigns freshly human-ready papers into the labeling queue immediately.

What makes it survive the free-tier ceiling: **quota-day accounting across two timezones** (Gemma counts a UTC day, both Gemini stages count an `America/Los_Angeles` day to match Google's reset), **lazy module loading** so drain workers never pay the crawler's import cost, and **three nested wall-clock budgets** (controller 75 min, crawler 2,400 s with partial-result writes, each model call 300 s) so one slow paper or a long crawl can never blow the job cap. Paper PDFs are kept **source-URL/on-demand** (`OPENNUTRI_STORE_PDFS_IN_SUPABASE=0`) because storing them would blow the Supabase free storage/egress caps — and a **same-origin PDF proxy** (`api/pdf.js`, a Vercel serverless function) fetches CORS-unfriendly publisher PDFs server-side with real hardening: https-only, **SSRF protection** (rejects localhost/internal hosts and IP literals), a 25 MB cap, a **`%PDF-` magic-byte check** so it can't be abused as an open proxy, a 25-second timeout, and a **1-year immutable cache** so each paper is fetched upstream at most once.

**The hard part.** Building a tick state machine that is **resumable and idempotent inside a 5-minute window** — surviving killed runners, overlapping ticks, two quota timezones, and the controller/drain split — instead of the easy long-running daemon I couldn't afford to host. GitHub jobs get killed and overlap; DB claiming has to be atomic; one failing paper must never monopolize a worker; and draining must continue even when the controller dies.

**Technologies.** GitHub Actions (cron, matrix, concurrency groups), Supabase RPCs with `FOR UPDATE SKIP LOCKED`, Vercel serverless, `SIGALRM`/wall-clock budgets, quota-day accounting, Python orchestration.

**Files & lines.** `scripts/daily_ops_orchestrator.py` (**2,358**), `.github/workflows/daily-ops.yml` (148), `scripts/ensure_paper_stock.py` (573), `scripts/upload_to_supabase.py` (774), `apps/expert-annotator/api/pdf.js` (102). **27 commits on the orchestrator alone.**

---

### 4.7 Reference data, PDF/egress hardening, tests & documentation — *the layer that makes it a system, not a demo*

**Why it is needed.** The AI normalizer and the autocomplete both need **stable IDs** for known foods and nutrients, or every paper would create uncontrolled strings; the dangerous logic needs tests, because a bug here silently corrupts a database or burns quota; and a six-month project needs documentation, or undocumented decisions get accidentally reverted.

**How I did it.**
- **Reference-data ETL** — two idempotent loaders (`etl_usda_to_opennutri.py`, `etl_sr_legacy_to_opennutri.py`) stream USDA FoodData Central CSVs into the canonical `entities` / `entity_aliases` / `master_nutrients` / `sources` / `claims` layer over the Supabase REST API. They **derive preparation state from the food description text**, **upsert on a conflict column** so re-running updates rather than duplicates, and use **deterministic UUIDs** so the same source row always maps to the same `entities.id` — keeping the reference IDs that every foreign key points at stable.
- **A test suite weighted toward the dangerous code** — **128 Python test functions + 35 frontend blocks, ~5,617 lines**, concentrated on what can silently corrupt data or burn quota: `test_ai_routing.py` (60 tests, 2,469 lines — normalization determinism, the unit policy, ID-resolution safety, threshold routing, **deterministic audit sampling**, retry classification, "the model never trains on itself"), `test_bilingual_pipeline.py` (32, 1,120), `test_daily_ops.py` (30, 983), `test_pdf_page_markers.py`. The test names read like a specification of the invariants — e.g. `rejects_stale_or_mismatched_db_ids`, `threshold_one_disables_ai_auto_finalization`, `build_labels_excludes_ai_model_outcomes`.
- **Documentation as operational infrastructure** — the README, AGENTS rules, the reviewer-workflow map, and a live handoff STATE document capture *why* Gemma is text-mode, *why* no hard-negative crawler vetoes are allowed, *why* PDFs are source-URL by default, *why* the cockpit AI lists must stay egress-slim, and *why* final truth comes from approval outcomes — so future contributors (and AI agents) don't re-derive or revert load-bearing decisions.

There is also an **honest lineage** here: the current crawler-v2 + cascade is the *second* full pipeline architecture in the repo. The earlier v1 harvester (`pipeline.py`, the `harvester/`, `core/`, and `extraction/` packages, ~2,800 lines) is retained, not deleted — it shipped and worked, and its better ideas carried forward. Keeping it costs repo size; the trade-off is an auditable record of how the system evolved.

**The hard part.** Discipline, mostly — making the ETL idempotent so a re-run never duplicates a food, weighting tests toward the few hundred lines where a bug is catastrophic rather than chasing coverage everywhere, and keeping documentation accurate enough that it actually prevents regressions instead of misleading.

**Technologies.** Python ETL over Supabase REST, deterministic UUIDs, idempotent upserts, `pytest`, Markdown + DOCX/PDF export tooling.

**Files & lines.** `etl_usda_to_opennutri.py` (227), `etl_sr_legacy_to_opennutri.py` (343), the test suite (~5,617 lines), README / AGENTS / STATE / workflow-map docs, plus the retained v1 pipeline (~2,800 lines).

---

## 5. Closing summary

I built the **entire backend of OpenNutri** — the system that turns "the whole scientific literature" into "a clean queue of trustworthy, evidence-located, citation-backed candidate values," and runs itself to do it. In numbers:

- **~31,800 lines** of backend / ops / schema code across **216 commits**; the database contract alone is **5,396 lines** (31 tables, 75 RLS policies, 26 RPCs), and the dangerous logic is pinned by **~5,600 lines of tests**.
- A **three-model cascade** that screens ~1,500 papers/day and spends its ~20 expensive extractions on the best of them; a **deterministic normalizer** whose output is **hash-identical** to a human submission; and a **confidence gate** that auto-keeps the trustworthy results, routes the uncertain ones to a human, and forces a sampled fraction of even the confident ones back to review as a quality check.
- A **crawler** that defeats publisher bot-walls with an actual proof-of-work solver, a **feedback loop** that learns from every human decision without ever training on itself, and an **automation layer** that runs all of it on a 5-minute GitHub Actions cron, inside the Supabase and Gemini free tiers, with five parallel workers coordinated by a single `FOR UPDATE SKIP LOCKED`.

And it isn't a prototype. It is **live**: a continuous pipeline that has been **operated, migrated, and recovered in production over six months**, under a least-privilege security model where a broken policy would leak data, a stalled worker would stop everything, and a wrong auto-accept would corrupt a food database — so every one of those had to be designed not to happen.

Every food database in the world is still built by experts typing numbers out of papers by hand. **My backend is the machine that finds the papers, reads them, decides what's trustworthy, and keeps only the rest for a human — cheaply enough to run every day and honestly enough to trust on a food label.** That is what lets OpenNutri do at scale what manual curation never could.
