# OpenNutri — Arciel Aliognis Baez Zamora — Defense Presentation (slide-ready, English)

> **What this document is.** A slide-by-slide script for Arciel Baez Zamora's individual defense presentation (the backend). It is derived from the full script `Arciel_Baez_Zamora_Presentation_EN.md`; the text here is lighter — main ideas plus the details worth saying out loud. The Turkish slide deck is a separate file: `Arciel_Baez_Zamora_Slides_TR.md`.
>
> **How to read it.** Bullets ≈ what goes on the slide (keep them short on the real slide; expand out loud). `🖼️ IMAGE` = a placeholder telling you exactly what diagram or screenshot to put there and what to point at. A backend deck is mostly **diagrams** plus the real cockpit screens you built (Pipeline funnel, Useful Papers + AI detail). Nothing here is a hidden notes track — the numbers and technique names are written into the slide content on purpose: they read as normal slide text and also happen to be what you want in your head if a teacher asks a follow-up.
>
> **Team split (say once, Slide 2):** Arciel — the entire backend (this talk); Ayşegül — the entire annotator frontend; Huan — reusable pieces (`fuzzyMatch`, suggestions, reset-password fix, theme centralization, infinite scroll).

---

## Slide 0 — Title

> 🖼️ **IMAGE — hero diagram:** the whole pipeline as one left-to-right flow — **Crawler → AI cascade → Normalizer + confidence gate → Database → (low-confidence) Human queue / (high-confidence) auto-finalized.** Everything except the human box is tinted as "mine." Title overlaid.
> *Caption:* "The backend that turns the whole literature into a clean queue of trustworthy candidates — and runs itself."

- **OpenNutri — The Backend**
- Arciel Aliognis Baez Zamora
- *"I built the system that finds the papers, reads them, decides what's trustworthy, and keeps only the rest for a human — running itself on free infrastructure, every five minutes."*

---

## Slide 1 — The problem: food data is still built by hand

> 🖼️ **IMAGE — split illustration:** left, a dense journal PDF table of numbers; right, a sparse database. Arrow between: "typed in by hand, one number at a time." Under it: "🐌 slow · 💸 expensive · 📉 narrow & out of date."
> *Caption:* "The data exists. Reading it out by hand doesn't scale; reading it with an unchecked AI isn't trustworthy."

- Every nutrition label, diet app and dietary guideline runs on **food-composition data** — protein, fat, iron, vitamin C…
- Today it's built **by hand**: read a paper, find the table, type each number into a database — one at a time.
- Slow and expensive → databases stay **narrow** and go **out of date**.
- The data already exists — published constantly — but it's locked inside unstructured PDFs.
- You can't just let an AI read it unchecked: **too many wrong numbers** to trust on a label.

---

## Slide 2 — How we solved it (as a team)

> 🖼️ **IMAGE — architecture diagram:** **[Backend pipeline] → [Database] → [Annotator frontend]**, with the AI box branching "low-confidence → human" and "high-confidence → auto-kept." Highlight that the backend + database are **mine**, the frontend is Ayşegül's.
> *Caption:* "AI proposes the numbers. A human verifies the ones it's unsure about."

- We flipped the work: **the AI reads the paper and proposes the numbers; a person verifies the ones the AI is unsure about** (the low-confidence ones).
- Three parts:
  - **Backend pipeline** (me) — finds papers, gets PDFs, runs the AI cascade → *candidate* values, and decides trustworthy-vs-uncertain.
  - **Database** (me) — stores everything, runs the review workflow.
  - **Annotator web app** (Ayşegül) — where a human checks the uncertain candidates.
- **My part is the entire backend — everything before and around the human. The rest of this talk is about it.**

---

## Slide 3 — My part, and why it's necessary

> 🖼️ **IMAGE:** the same pipeline as Slide 0, but the **human box is small at the end** and everything feeding it is labelled "mine." Add four small risk icons over the backend: 🔓 a leaked RLS policy · 🛑 a stalled worker · 💸 wasted model quota · ❌ a wrong auto-accept.
> *Caption:* "The frontend can only ever be as good as what reaches it. The backend is what reaches it."

- My part is the **entire backend** — database, AI pipeline, crawler, learning loop, and the automation that runs it all unattended, on free infrastructure, every 5 minutes.
- **Why it's necessary:** someone has to *find* the right papers, *get* the PDFs out of hostile publisher sites, *read* them cheaply, *decide* trustworthy-vs-uncertain, *store* it under a security model, and *keep the machine running* with no server and no budget.
- It carries the project's real risk: a wrong auto-accept corrupts a food database; a broken policy leaks data; a stalled worker stops everything. **"Correct, cheap, and unattended" all have to be true at once.**

---

## Slide 4 — What I built: seven pieces

> 🖼️ **IMAGE — "map" slide:** seven numbered tiles arranged along the pipeline flow (front door → … → runs-itself). Doubles as the agenda.
> *Caption:* "A self-running research pipeline, on the Supabase and GitHub free tiers."

1. **Database & security contract** — 31 tables, 75 RLS policies, the RPCs everyone calls.
2. **Paper-discovery crawler** — the front door: search → filter → acquisition.
3. **Three-stage AI cascade** — Gemma → Flash-Lite → Flash, one shared contract.
4. **Deterministic normalizer & confidence gate** — guess → trustworthy data, or a human's job.
5. **Feedback-learning loop** — human approvals re-score the next crawl.
6. **Daily-ops automation** — a controller + 5 parallel workers on a 5-min cron.
7. **Reference data, hardening, tests & docs** — what makes it a system, not a demo.

---

## Slide 5 — 1) The database & security contract

> 🖼️ **IMAGE — layered schema diagram:** five stacked layers — **Reference (foods/nutrients) · Discovery (papers/search ledger) · Annotation · Workflow engine · AI routing** — with a side badge: **31 tables · 75 RLS policies · 26 RPCs · 22 SECURITY DEFINER.** Inset the one-liner `current_user_can_write() = NOT current_user_is_tester()`.
> *Caption:* "`migration.sql` — 5,396 lines: the contract between the Python pipeline and the React app."

- **One file, the spine of the project** — without it nothing can submit a label, register a paper, claim a task, or show truth.
- **One convergent, idempotent migration** — safe to re-run on the live DB forever (`ADD COLUMN IF NOT EXISTS`, constraints rebuilt inside `DO` blocks that check `information_schema` first).
- **Least-privilege security: 75 RLS policies** on 6 `SECURITY DEFINER` predicates — read-only training access falls out of a *single negation*, `NOT is_tester()`.
- **You can't lock the team out:** the admin RPC refuses to leave zero active cockpit-write reviewers; the signup allowlist is enforced by an auth hook the browser can neither read nor bypass.

---

## Slide 6 — 1) The contract: atomic claiming + hash-identical truth

> 🖼️ **IMAGE — two-panel:** (left) the `claim_paper_stage_tasks` SQL highlighting **`FOR UPDATE SKIP LOCKED`** with five worker arrows each grabbing a disjoint task set; (right) **Human submission** and **AI extraction** both flowing into "canonical JSON → SHA-256" and producing the **same hash**.
> *Caption:* "One clause makes 5 parallel workers safe. One discipline makes AI output comparable to a human's."

- **`claim_paper_stage_tasks`** claims queued tasks `ORDER BY attempt_count ASC, priority DESC … FOR UPDATE SKIP LOCKED` — that one clause lets **5 parallel GitHub workers** grab disjoint tasks with zero coordination, zero double-processing.
- **Deterministic payload builders:** a SQL builder assembles a human submission with the *same* ordering + `round(value,6)` rules as the Python normalizer, so a human submission and an AI extraction of the same data **hash identically**.
- **`build_label_payload_diff`** — a full structural diff in SQL (anti-joins for added/missing rows) → the raw material for labeler-performance metrics.

---

## Slide 7 — 2) The paper-discovery crawler (front door)

> 🖼️ **IMAGE — funnel diagram:** **Search (Europe PMC / OpenAlex / Semantic Scholar / DergiPark) → Filter (additive, no hard veto, on title+abstract) → Acquisition (download → strict full-text gate).** Mark "cheap metadata first, expensive PDF last." Add a red "no hard-negative veto" stamp on the Filter stage.
> *Caption:* "Encode the product's domain definition into scoring — without killing a real paper over one stray word."

- If the crawler admits the wrong papers, **model quota and labeler time are wasted**; too strict and it never finds the real tables.
- **Search → Filter → Acquisition** — filter on cheap metadata first; download the PDF (slow, failure-prone) only for passers.
- **Purely additive scoring, never a hard veto:** a negative phrase ("clinical trial") is a *penalty*, not an auto-reject — one word can't kill a paper that also has a composition table.
- **Loose in, strict out:** the metadata gate maximizes recall; the full-text gate is strict — needs method evidence (AOAC/HPLC/GC/ICP), `mg/100g` units, a table signal, a food signal, and ≥4 overlap with a proximate panel.
- Word-matching is Unicode word-boundary-aware — Turkish "et" (meat) matches as a word, not inside "diet".

---

## Slide 8 — 2) PDF acquisition: defeating publisher bot-walls

> 🖼️ **IMAGE — fallback ladder:** numbered steps cascading down — **1. PMC OA package (extract largest .pdf from .tar.gz) → 2. direct fetch (verify `%PDF`) → 3. curl with a browser User-Agent → 4. solve a PMC proof-of-work → 5. scrape an HTML .pdf link.** Highlight step 4 with a tiny "mining loop" icon.
> *Caption:* "A bot-wall, beaten with an actual MD5 proof-of-work solver."

- Publisher PDFs fight back — so acquisition is a **layered fallback ladder** (5 steps), each catching what the previous can't.
- **The hard one:** when a publisher returns an HTML bot-wall, `_solve_pmc_pow` parses the challenge and **brute-forces a hashcash nonce** — incrementing until `md5(challenge+nonce)` starts with N zeros — then retries with the solution cookie.
- **Never crawls the same paper twice:** a skip-set from every live `canonical_key` + local terminal states (including metadata rejects).
- **Wall-clock bounded (2,400 s):** on timeout it stops cleanly and still writes every accepted paper + a funnel manifest — a GitHub timeout never loses work.

---

## Slide 9 — 3) The three-stage AI cascade

> 🖼️ **IMAGE — funnel:** three shrinking bars — **Small / Gemma ~1,500/day → Medium / Flash-Lite ~500/day → Strong / Gemini Flash ~20/day → human_review_ready.** Label each with model name + input mode. Show a "priority score picks the top-N" arrow between stages.
> *Caption:* "Spend the ~20 expensive extractions/day on the best of ~1,500 screened — not on whatever arrived first."

- The final Gemini extraction is **scarce (~20/day on free quota)** — screening everything with it would waste the budget on useless papers.
- So a **three-stage funnel:** cheap screener (Gemma ~1,500/day) → mid re-ranker (Flash-Lite ~500/day) → expensive extractor (Gemini ~20/day).
- **A priority score makes it a funnel:** each stage processes the **top-N** by usefulness, not oldest-first — so the 20 calls land on the best candidates.
- The pipeline's shape is **data, not code** — thresholds, fallback models and input mode live in a `routing_stage_configs` table; a model can be swapped without a code change.

---

## Slide 10 — 3) One contract across three models — surviving reality

> 🖼️ **IMAGE — code/JSON illustration:** one **shared prompt** feeding three model icons; below, four differently-shaped JSON blobs (object · bare array · 1-element array · nested food→nutrients) all collapsing into **one canonical root**. Inset: "Gemma + PDF mode → ⏱️ timed out >600 s on 5 pages → text mode."
> *Caption:* "Valid-but-differently-shaped output is salvaged, not retried into a loop."

- All three stages run the **same prompt** (`opennutri_evidence_payload_v2`) — ~25 lines that *define the product*: what "useful composition data" is vs. what's empty (interventions, one-off formulations, reviews).
- Every row carries **evidence metadata** (`table_label`, `page_hint`, a ≤20-word verbatim `source_quote`) so the frontend can highlight it — and `page_hint` is the **PDF page index, never the printed page** (the instruction that makes highlighting work).
- **JSON drift survived:** strip markdown fences, a hand-written balanced-bracket scanner, **4 accepted shapes** → one root; a bad row is dropped, not fatal.
- **Native PDF for the strong stage** (true page numbers); **Gemma stays text-mode** because it was measured to **time out >600 s on a 5-page PDF** — fatal at ~1,500/day. Decision encoded + documented so it isn't reverted.

---

## Slide 11 — 4) The deterministic normalizer

> 🖼️ **IMAGE — gauntlet diagram:** a model row passing through gates left→right — **required-field → unit policy (7 units; dry-matter rejected) → reference resolution (ID→name→alias; ambiguous→none) → deterministic order + round(6) → SHA-256.** Then a real screenshot of the **AI Extraction Detail** panel (Confidence, Rows accepted/input, rejection-reason badges).
> *Caption:* "Model output, converted into the exact shape a human would submit — and a record of why each row was dropped."

- A model's raw output isn't database data — it must become the **exact same normalized shape a human submits**.
- **Strict unit gatekeeper:** only `g/100g · mg/100g · μg/100g · kcal/100g · kJ/100g · IU/100g · %` survive; per-100g required, **dry-matter rejected**, fresh/wet/as-is accepted.
- **Safe reference resolution:** verify a claimed DB id *and* that its name matches; **ambiguous names resolve to nothing** (never a wrong link); unresolved foods/nutrients kept as explicit *custom* rows.
- **Deterministic order + `round(6)` → SHA-256** — so an AI extraction is byte-comparable to a human submission, and a `rejection_reasons` histogram shows *why* rows dropped.

---

## Slide 12 — 4) The confidence gate — keep, or send to a human?

> 🖼️ **IMAGE — gate diagram:** confidence on an axis with two thresholds; arrows — **low-confidence → Human queue · high-positive → auto-finalized · a sampled slice of auto-finalized → forced back to Human (AUDIT).** Real screenshot: a **Useful Papers** row showing `conf 0.xx` + the **LIVE / AUDIT** badge.
> *Caption:* "This is 'AI proposes, a human verifies the ones it's unsure about' — made precise, reproducible, and self-checking."

- **How confidence decides:** each paper is bucketed high/low × positive/negative against the stage's own thresholds.
- **The gate:** **low-confidence → the human labeling queue**; **high-confidence-positive → auto-finalized**; a paper with existing human truth is never overwritten.
- **Auto-accepts are audited, not trusted:** `stable_audit_sample` (`SHA256(paper|stage|model)` vs `audit_rate·2⁶⁴`) is **deterministic** and forces a sampled fraction of even high-confidence finalizations back to a human — continuous quality control on the auto path.
- **Fully reproducible + auditable:** same paper → same decision, every time, and you can always see why. *(This is the part of the system that scales — the human only sees the uncertain papers.)*

---

## Slide 13 — 5) The feedback-learning loop

> 🖼️ **IMAGE — loop diagram:** **human approvals (paper_review_outcomes) → log-odds n-gram scoring (good / bad / background) → latest.json → crawler ranks better next time → more good papers → more approvals.** Stamp "never trains on itself" on the AI-outcomes node (crossed out into the loop).
> *Caption:* "The difference between a static keyword crawler and an improving research pipeline."

- Every human approve/reject is evidence about which words predict a *useful* paper — and it re-scores the **next crawl**.
- **Never trains on itself:** only `truth_source_kind = 'human_review'` outcomes count; AI-finalized ones are excluded; open conflicts and pending submissions don't teach.
- **Smoothed log-odds over good / bad / background** — the **background bucket** is the trick: it surfaces terms *distinctive* of useful papers, not just common words. Title vs. title+abstract scored separately (a title phrase is stronger evidence).
- Produces **seven learned per-language pools** (filter weights, query phrases, embedding anchors, source/pair/batch/concept scores) — and feedback is a **soft score**, never a hard reject.

---

## Slide 14 — 6) Daily-ops automation — it runs itself, for free

> 🖼️ **IMAGE — ops diagram:** a 5-minute clock driving **one serialized `refill-controller`** (crawl/upload/refill) + a **matrix of 5 parallel `drain-workers`**; all five point at the DB through one **`FOR UPDATE SKIP LOCKED`** box. Real inset: a GitHub Actions run list, or the **Pipeline → "Right Now"** cockpit grid.
> *Caption:* "A real continuous pipeline on GitHub-hosted runners and a free Gemini quota — no server."

- The whole pipeline has to *run* continuously — crawl, screen ~1,500/day, triage, extract — with **no server and no budget**.
- **One serialized controller** (the only job that may crawl; never killed mid-crawl) **+ five parallel drain workers** (ungated — "draining must continue even if the controller fails").
- Five workers are safe in parallel **only because** of `FOR UPDATE SKIP LOCKED` — each grabs a disjoint task set, no locks, no coordination.
- **A resumable tick, not a daemon:** stale-task requeue, lowest-attempt-first ordering, and an explicit stop/refill decision tree inside a 5-minute window — survives killed and overlapping runners.

---

## Slide 15 — 6) Engineered for the free-tier ceiling

> 🖼️ **IMAGE — constraints panel:** four labelled chips — **Quota-day across 2 timezones** (Gemma=UTC, Gemini=America/Los_Angeles) · **3 nested wall-clock budgets** (controller 75 min / crawler 2,400 s / model 300 s) · **source-URL PDFs** (no Supabase storage) · **same-origin PDF proxy** (SSRF-hardened). Optionally the **Pipeline funnel** screenshot.
> *Caption:* "Every architectural choice here is downstream of one constraint: do it for free."

- **Quota-day accounting across two timezones** — Gemma counts a UTC day; both Gemini stages count an `America/Los_Angeles` day to match Google's reset, so the funnel spends exactly the daily budget.
- **Three nested wall-clock budgets** (controller 75 min · crawler 2,400 s with partial-result writes · each model call 300 s via `SIGALRM`) — one slow paper can't blow the job cap.
- **PDFs kept source-URL/on-demand** (storing them would blow the Supabase free caps); a **same-origin PDF proxy** (`api/pdf.js`) fetches CORS-unfriendly publisher PDFs with **SSRF hardening, a `%PDF-` magic-byte check, a 25 MB cap, and a 1-year immutable cache** so each paper is fetched upstream at most once.

---

## Slide 16 — 7) Reference data, tests & documentation

> 🖼️ **IMAGE — three-panel:** (1) **USDA CSV → idempotent upsert → canonical foods/nutrients**; (2) a list of real test names reading like a spec (`rejects_stale_or_mismatched_db_ids`, `threshold_one_disables_ai_auto_finalization`, `build_labels_excludes_ai_model_outcomes`); (3) a docs stack (README · AGENTS · STATE · workflow map).
> *Caption:* "The unglamorous layer that's the difference between a demo and a system operated for six months."

- **Reference ETL:** idempotent loaders stream USDA FoodData Central into canonical foods/nutrients — upsert on conflict + **deterministic UUIDs** keep every reference ID stable for the foreign keys to point at.
- **Tests weighted on the dangerous code:** ~5,600 lines; `test_ai_routing.py` alone is **2,469 lines / 60 tests** — normalization determinism, the unit policy, audit-sampling determinism, "the model never trains on itself."
- **Docs as operational infrastructure:** the README / AGENTS / STATE capture *why* Gemma is text-mode, *why* no crawler vetoes, *why* source-URL PDFs — so load-bearing decisions don't get reverted.

---

## Slide 17 — Closing: what it adds up to

> 🖼️ **IMAGE — "by the numbers" card + the hero pipeline diagram from Slide 0:** big figures — **~31,800 backend lines · 216 commits · 5,396-line schema · ~5,600 test lines · 1,500 → 20/day cascade · live 6 months.**
> *Caption:* "Operated, migrated, and recovered in production — on free infrastructure."

- **~31,800 lines** of backend/ops/schema across **216 commits**; the database contract alone is **5,396 lines** (31 tables, 75 RLS policies), and the dangerous logic is pinned by **~5,600 lines of tests**.
- A **three-model cascade** that screens ~1,500/day and extracts the best ~20; a **deterministic normalizer** whose output is **hash-identical** to a human's; and a **confidence gate** that auto-keeps the trustworthy, routes the uncertain to a human, and audits a sampled slice of the rest.
- A **crawler** that beats bot-walls with a proof-of-work solver, a **feedback loop** that learns without training on itself, and **automation** running it all on a 5-minute cron inside the Supabase + Gemini free tiers.
- **Not a prototype — live, operated/migrated/recovered over six months**, where a broken policy would leak data and a wrong auto-accept would corrupt a database, so each was designed not to happen. **My backend is the machine that finds the papers, reads them, decides what's trustworthy, and keeps only the rest for a human — cheaply enough to run daily, honestly enough to trust on a food label.**
