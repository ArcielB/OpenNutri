# OpenNutri Work Report v2 - Arciel Aliognis Baez Zamora

Prepared: 2026-06-05
Repository snapshot: `1a8d1cf0394d2c86ba31604888969c30a9a47d32`
Contributor identities used for direct evidence: `baezarciel <baezarciel@gmail.com>` and initial `ArcielB` commit
Student: Arciel Aliognis Baez Zamora (`221229078`)

## Evidence Rule

This report credits Arciel with:

- Direct `baezarciel` commits.
- The initial `ArcielB` repository commit.
- Backend/schema/AI/crawler/ops/deployment/docs ownership under the team split.
- Backend-driven frontend integrations such as cockpit RPC consumption, queue performance redesign, PDF delivery/cache hardening, and AI details surfaces.

Current direct metrics:

| Evidence | Value |
| --- | ---: |
| `baezarciel` commits | 211 |
| Initial `ArcielB` commit | 1 |
| Filtered `baezarciel` churn | `+67,971/-17,639` |
| Backend/ops/schema active lines | 31,796 |
| Schema/RPC/RLS file | `migration.sql`, 5,396 lines |

Filtered churn excludes USDA dumps, legacy archive, `package-lock.json`, and proposal appendix drafts.

## 1. Supabase Schema, RLS, and Reviewer Truth

Evidence file:

- `apps/expert-annotator/migration.sql` (5,396 lines)

Current object counts:

| Object type | Count |
| --- | ---: |
| Tables | 31 |
| Functions/RPCs | 26 |
| RLS policies | 75 |
| RLS-enabled tables | 32 |
| Indexes | 69 |
| Triggers | 2 |
| `SECURITY DEFINER` functions | 22 |

What Arciel built:

- Canonical food/nutrient/provenance tables: `entities`, `entity_aliases`, `master_nutrients`, `sources`, `claims`.
- Paper discovery ledger: `papers`, `paper_search_hits`, `paper_search_batches`, `paper_search_batch_hits`.
- Annotation data model: `annotations`, `food_items`, `annotation_nutrient_values`, `paper_label_events`, `paper_global_labels`.
- Current general queue/approval truth model: `paper_label_submissions`, `paper_label_approvals`, `paper_review_outcomes`.
- AI routing model: `routing_stage_configs`, `paper_stage_tasks`, `ai_extractions`.
- Reviewer profiles and role flags: cockpit, tester, approver, active/inactive.
- Signup allowlist hardening through a private auth hook and revoked client table privileges.
- RLS policies and `SECURITY DEFINER` RPCs for controlled browser access.

Important RPCs:

- `claim_paper_stage_tasks`: service-role atomic task claiming with `FOR UPDATE SKIP LOCKED`.
- `get_general_queue_cards`: lean queue card projection with latest AI prefill and user's annotation status.
- `submit_general_label`: creates immutable label submissions.
- `approve_label_submission`: stores final reviewer payload, correction diff, and final outcome.
- `get_cockpit_ai_extractions`: egress-slim cockpit AI list.
- `get_pipeline_ops_snapshot`: stage/human/crawler funnel aggregation without direct task-table exposure.

Hard parts:

- A single convergent migration file has to be safe to re-run against the live database.
- RLS must allow labelers, testers, cockpit users, approvers, and service-role automation to do different things without leaking private rows.
- Legacy workflow tables remain for audit, while the active product logic uses general queue plus approval.
- AI and human payloads must be deterministic enough to compare by hash.

Assessment value:

This schema is the contract between every other part of OpenNutri. The frontend cannot submit labels, the crawler cannot register papers, the model workers cannot claim tasks, and the dashboard cannot display truth without these tables/RPCs/policies.

## 2. AI Extraction Cascade

Evidence files:

- `services/data-pipeline/evaluator/unified_evaluator.py` (687)
- `services/data-pipeline/ai_routing.py` (842)
- `services/data-pipeline/scripts/process_stage_queue.py` (1,560)
- `services/data-pipeline/scripts/recover_gemini_candidates.py`
- `services/data-pipeline/scripts/flash_lite_triage_experiment.py`

What Arciel built:

- Shared extraction contract for all models.
- Three-stage AI cascade:
  - Small model: `gemma_proof_extraction_v1`, `gemma-4-31b-it`, 26B fallback, text mode, about 1,500/day.
  - Medium model: `gemini_flash_lite_triage_v1`, `gemini-3.1-flash-lite`, about 500/day.
  - Strong model: `gemini_flash_db_payload_v2`, `gemini-3.5-flash`, PDF mode, about 20/day.
- Deterministic normalization from model rows to human-submission-shaped `normalized_payload_json`.
- Unit/basis standardization and rejection accounting.
- DB food/nutrient ID verification with exact/alias/custom fallback.
- Follow-up priority scoring so scarce downstream model calls process top candidates.
- Raw-positive rescue for Gemma outputs that indicate data even if strict normalization is empty.
- Provisional no-data routing that keeps likely-useless papers out of default human queues.

Reliability features:

- Model JSON parser accepts the requested object, top-level row arrays, one-element array-wrapped results, and nested food -> nutrients rows.
- Balanced JSON extraction recovers valid JSON from model responses wrapped in prose.
- Stage workers validate model runtime before claiming tasks, preventing credential/config failures from stranding rows.
- Stale `processing` rows are requeued before queue decisions.
- Quota/rate-limit requeues undo the claim attempt count.
- Non-quota task errors past `AI_STAGE_MAX_TASK_ATTEMPTS=2` fail instead of looping forever.
- Gemma 31B retryable failures can fall back to configured 26B in the same task attempt.
- Gemini stages can receive native PDF parts; Gemma remains text-mode because PDF mode timed out in probes.

Hard parts:

- The AI output must be useful for database insertion, not just a plausible summary.
- The final extraction quota is small, so the system must rank and drain rather than simply process old tasks.
- Page/evidence metadata has to support frontend highlighting.
- Error handling must distinguish quota, retryable runtime failure, and non-retryable model configuration errors.

## 3. Paper Discovery Crawler

Evidence files:

- `services/data-pipeline/food_paper_crawler/crawler_v2.py` (2,215)
- `services/data-pipeline/food_paper_crawler/ranking.py` (486)
- source adapters for Europe PMC, OpenAlex, Semantic Scholar, DergiPark
- `services/data-pipeline/scripts/upload_to_supabase.py`

What Arciel built:

- Search -> filter -> acquisition architecture.
- Multi-source metadata acquisition.
- Language-aware English/Turkish support, with current ops set to English-only.
- Additive metadata relevance scoring with lexical, food, nutrient, unit, method, embedding, source-prior, batch, concept, and learned feedback signals.
- Full-text PDF validation after download.
- Dedup by canonical keys and local terminal paper state.
- Identity-based accepted PDF names.
- Partial accepted-result manifest writing when the crawler wall-clock limit is reached.
- Upload behavior that preserves closed AI/human routes when known papers reappear.
- Duplicate-key race recovery during concurrent uploads.

Hard parts:

- PDF acquisition is unreliable: the crawler uses open-access package lookup, direct fetch, curl fallback, HTML PDF-link scraping, and PMC proof-of-work handling.
- The filter must avoid hard negative vetoes. Negative phrases are penalties so one stray term does not kill a relevant composition paper.
- The metadata gate is recall-oriented; the PDF/full-text gate is precision-oriented.
- Crawler batches must respect remaining English/Turkish targets and avoid over-downloading.

Assessment value:

The crawler is the front door of the system. If it admits the wrong papers, model quota and labeler time are wasted. If it is too strict, the pipeline never finds useful composition tables. Arciel encoded the product's domain definition into scoring, validation, dedup, and audit manifests.

## 4. Feedback Learning Loop

Evidence files:

- `services/data-pipeline/food_paper_crawler/feedback/update_terms.py` (1,219)
- `feedback_config.py`
- `feedback_terms.py`
- `supabase_terms.py`

What Arciel built:

- Human-truth export from `paper_review_outcomes`.
- Exclusion of pending/superseded submissions.
- Exclusion of AI-only truth (`truth_source_kind='ai_model'`) from current feedback learning.
- Legacy label-event/global-label fallback only for older papers without resolved outcomes.
- Good/bad/background document buckets.
- Smoothed log-odds scoring for title and title+abstract n-grams.
- Seed phrase priors that are soft, not permanent winners.
- Source priors, source-term pair scores, batch scores, and concept scores.
- Output to generated `feedback/latest.json`, loaded by crawler v2.

Hard parts:

- The model must not train on itself.
- Open conflicts and unresolved labels should not teach the crawler.
- Title-only evidence and title+abstract evidence have different predictive value, so the scorer keeps them separate.
- Feedback is a soft score and cannot become a hard rejection rule.

Assessment value:

This closes the human-in-the-loop system: accepted reviewer truth changes the next crawl's scoring. That is the difference between a static keyword crawler and an improving research pipeline.

## 5. Daily Ops and Queue Automation

Evidence files:

- `.github/workflows/daily-ops.yml` (148)
- `services/data-pipeline/scripts/daily_ops_orchestrator.py`
- `services/data-pipeline/scripts/ensure_paper_stock.py`
- `services/data-pipeline/scripts/refill_assignment_queue.py`
- README/STATE ops sections

What Arciel built:

- Scheduled GitHub Actions run every 5 minutes.
- Serialized `refill-controller` job that can crawl/upload/refill.
- Five parallel `drain-workers` jobs that only claim and process existing model tasks.
- Manual dispatch worker count.
- Stage-specific daily quota accounting.
- Stale task requeue before queue/refill decisions.
- Active Gemma work counted from executable `paper_stage_tasks` rows.
- Downstream drain continues even when Gemma source/refill is empty.
- Controller wall-clock and crawler wall-clock bounds.
- JSON summaries for operational observability.

Hard parts:

- GitHub jobs can be killed or overlap; DB task claiming must be atomic.
- The controller must not block model draining during crawl/refill work.
- Daily quota limits differ by model family and reset timezone.
- One failing paper must not monopolize worker time.

Assessment value:

This is production operations, not a local script. The pipeline can run unattended, recover from runner interruption, and keep model quota pointed at the most promising papers.

## 6. Storage, Egress, and PDF Delivery Hardening

Evidence files:

- `upload_to_supabase.py`
- `process_stage_queue.py`
- `apps/expert-annotator/api/pdf.js`
- `apps/expert-annotator/src/utils/pdfCache.js`
- `PdfViewer.jsx`
- README and handoff state notes

What Arciel built:

- Paper PDFs are source-URL/on-demand by default.
- `OPENNUTRI_STORE_PDFS_IN_SUPABASE=0` in scheduled ops.
- Upload preserves `papers.pdf_url` as durable location for workers and annotator.
- Same-origin PDF proxy for publisher PDFs that are not browser-CORS friendly.
- Long-lived browser Cache Storage layer for PDF bytes.
- Prefetch of next queue papers.
- Egress-slim queue/cockpit RPCs, especially `get_cockpit_ai_extractions`.

Hard parts:

- Supabase free-tier storage and egress constraints materially affect architecture.
- Model workers still need reliable PDF access even when paper files are not stored in Supabase.
- Browser PDF loading needs CORS-safe URLs and cache durability.

Assessment value:

These changes prevented the system from failing because of storage/egress economics. They also improved reviewer load time.

## 7. Frontend Integration and Project Management

Evidence files:

- `Annotate.jsx`
- `annotateHelpers.js`
- `views/PipelineOpsView.jsx`
- `views/AllPapersView.jsx`
- `README.md`
- `AGENTS.md`
- `docs/handoff_2026-03-20/STATE.md`
- `docs/reviewer_workflow_map.md`

What Arciel built or integrated:

- General queue plus Arciel approval workflow.
- Backend-driven cockpit projections and pipeline funnel.
- AI Details panels based on normalized payload summaries.
- Lazy cockpit loading and lean queue RPC consumption.
- Refactor of `Annotate.jsx` into helpers and eight views.
- Documentation of reviewer workflow, ops model, storage policy, feedback truth, and future-agent constraints.
- Report packages for defense/evaluation.

Hard parts:

- Workflow changes affected database, frontend, docs, and daily ops at the same time.
- User-visible behavior had to preserve AI prefill, Details panels, tester read-only mode, approval visibility, and queue removal rules.
- Later agents need accurate state documents to avoid re-deriving or reverting key decisions.

## Assessment Summary

Arciel's work is the system backbone:

- Database/schema/RLS/RPCs and reviewer truth.
- AI cascade and deterministic normalization.
- Paper crawler and feedback learning.
- Daily ops automation and queue draining.
- Storage/egress/PDF delivery hardening.
- Backend-driven frontend integration, documentation, and project management.

Direct evidence supports **211 `baezarciel` commits**, **the initial `ArcielB` commit**, **`+67,971/-17,639` filtered churn**, and **31,796 backend/ops/schema lines** at the current snapshot. The work also carries the highest operational risk: live database security, model quota reliability, unattended GitHub Actions, and data-quality truth all depend on it.

## Expanded Backend / Ops / Integration Ledger

### A. Repository Reorganization and Baseline Pipeline

**When:** 2026-03-09 to 2026-03-15.
**Commits:** `8728564`, `ed58f87`, `76e2c06`, `24c1755`, `c859acb`, `e303f40`.
**Technology:** Git repository reorganization, Python service layout, React app placement, README/docs.

What was done:

- Imported the prior Tubitak/OpenNutri codebase snapshot into the current repository.
- Preserved a Vercel production frontend build under `legacy/` for recovery.
- Reorganized crawler files under `services/data-pipeline/`.
- Added a README and clarified repo structure.
- Ignored local keys.

Why it was needed:

The project needed a stable shared repository rather than scattered local/private code. Reorganization made the active surfaces clear: expert annotator app, Python data pipeline, SQL schema, docs, and legacy archive.

How it was implemented:

- Existing code was snapshotted and then split into current service/app directories.
- Legacy artifacts were kept for recovery but excluded from normal work.
- README and later AGENTS files documented which areas future agents should touch.

Caveat:

The snapshot imported earlier work. This report treats later active development separately from the imported foundation.

### B. USDA and Reference Data Layer

**When:** March 2026 baseline and later schema integration.
**Technology:** Python ETL, Supabase/Postgres, USDA FoodData Central CSVs, SQL reference tables.

What was done:

- Retained USDA FoodData Central CSV dumps as source/reference data.
- Added ETL scripts for SR Legacy and USDA-to-OpenNutri conversion.
- Defined canonical `entities`, `entity_aliases`, `master_nutrients`, `sources`, and `claims`.

Why it was needed:

AI and human labelers need stable IDs for known foods and nutrients. Without a canonical reference layer, every paper would create uncontrolled strings and the database would not be useful for nutrition applications.

How it was implemented:

- ETL scripts map external USDA rows into OpenNutri's reference schema.
- The annotator can select canonical foods/nutrients or mark custom entries when a paper reports something not yet in the reference set.
- Claims store normalized `entity x nutrient x source` facts with amount, unit, basis, confidence, and provenance.

Evidence:

- `etl_sr_legacy_to_opennutri.py`
- `etl_usda_to_opennutri.py`
- `create_opennutri_schema.sql`
- `migration.sql` reference table definitions.

### C. Reviewer Workflow Generations

**When:** April to May 2026.
**Technology:** Supabase schema/RPCs, React views, RLS, JSONB payloads.

What was done:

1. Assignment/slot workflow:
   - Reviewer slots.
   - Slot memberships.
   - Paper assignments.
   - User assignment rows.
   - Official/shadow reviewer distinction.

2. Conflict workflow:
   - Huan's conflict tables/view integrated into schema.
   - Resolution functions retained.

3. General queue plus approval:
   - Shared `human_review_ready` queue.
   - Immutable `paper_label_submissions`.
   - Reviewer approval and correction.
   - Final `paper_review_outcomes`.

Why it changed:

The slot model provided structure but slowed throughput. The general queue made labeling faster: all active labelers see available useful papers, and submission removes a paper from the queue. Approval preserves final truth quality.

How it was implemented:

- Arciel kept legacy tables for audit rather than deleting history.
- `get_general_queue_cards` encodes visibility rules.
- `submit_general_label` freezes a submission and auto-accepts when the caller can approve.
- `approve_label_submission` writes correction diff and final outcome.
- Dashboard and feedback learning use approved truth rather than drafts.

Evidence:

- `migration.sql`: legacy and current workflow tables.
- `docs/reviewer_workflow_map.md`.
- `README.md` reviewer workflow section.

### D. AI Normalization and Routing Details

**When:** April to June 2026.
**Technology:** Python dataclasses, JSON, SHA-256, Supabase client, PL/pgSQL support tables.

What was done:

- Defined routing statuses and destinations.
- Classified high/low positive/negative buckets.
- Implemented deterministic audit sampling.
- Implemented AI normalized payload generation.
- Implemented supported unit/basis policy.
- Implemented food/nutrient ID verification and exact/alias fallback.
- Stored normalization summary and rejection histogram.
- Stored threshold snapshots and route decisions.

Why it was needed:

The model's raw output is not trustworthy database data. It must be converted into the same normalized structure a human reviewer would submit, and the system must record why rows were rejected.

How it was implemented:

- `normalize_ai_payload_with_summary` iterates model rows, drops incomplete rows, standardizes units, resolves references, groups by food, sorts deterministically, and returns counts.
- `_standardize_unit` accepts only supported units such as `g/100g`, `mg/100g`, `ug/100g`, energy units, IU, and percent.
- Dry-matter or unsupported bases are rejected so final human/AI payloads stay DB-compliant.
- `PayloadNormalizationResult.summary` feeds cockpit AI details and debugging.

Evidence:

- `ai_routing.py`: 842 lines.
- `test_ai_routing.py`: 2,469 lines.

### E. Model Worker Reliability

**When:** May 2026, hardened repeatedly.
**Technology:** Python CLI, Unix alarms/timeouts, Supabase RPCs, subprocess `pdftotext`, model SDK calls.

What was done:

- Model runtime validation before task claiming.
- Atomic task claiming.
- Stale processing requeue.
- Claim attempt accounting.
- Quota-safe requeue.
- Retryable/non-retryable error classification.
- Same-attempt fallback model use.
- Timeout around model calls.
- Failure after non-quota retry ceiling.

Why it was needed:

Unattended workers fail in practical ways: missing secrets, timed-out models, cancelled GitHub runners, quota errors, SDK exceptions, and repeatedly bad papers. The queue must recover without losing tasks or letting one paper monopolize automation.

How it was implemented:

- `claim_paper_stage_tasks` claims with `FOR UPDATE SKIP LOCKED`.
- `process_stage_queue.py` constructs evaluator before claiming to catch config errors early.
- `requeue_stale_processing_tasks` returns old `processing` tasks to `queued`.
- Quota errors decrement/undo meaningful attempt count.
- Non-retryable model configuration errors mark the task failed and stop automation.
- `AI_STAGE_MAX_TASK_ATTEMPTS=2` prevents endless loops for non-quota failures.

Evidence:

- `process_stage_queue.py`: 1,560 lines.
- `test_daily_ops.py`: 983 lines.
- AGENTS/README daily ops notes.

### F. Three-Stage Cascade Rationale

**When:** Gemma stage on 2026-05-03; daily ops drain by quota on 2026-05-11; Flash-Lite on 2026-05-29; PDF-mode final Gemini on 2026-05-31.
**Technology:** Data-driven stage configs, Gemini/Gemma model calls, PDF/text input modes.

Why not one model:

- Strong final Gemini extraction is limited and more valuable.
- Screening every candidate with the strongest model would waste quota on mostly-useless papers.
- A staged funnel processes many candidates cheaply, then spends expensive calls on the top-ranked subset.

How the cascade works:

- Gemma screens many papers/day with page-marked text.
- Flash-Lite re-ranks the strongest useful Gemma outputs.
- Final Gemini receives native PDF where possible and produces the DB payload.
- Each stage writes `ai_extractions` and may enqueue the next `paper_stage_tasks` row.
- Stage priority makes downstream tasks top-N by usefulness, not oldest-first.

Why Gemma remains text-mode:

- Probe results showed Gemma accepted PDF parts but timed out on a 5-page PDF.
- For a high-volume stage, this would collapse throughput.
- Text mode with inserted PDF page markers gives adequate page references without image rendering.

Evidence:

- `routing_stage_configs` seed/update rows in `migration.sql`.
- `unified_evaluator.py`.
- `process_stage_queue.py`.
- `probe_model_file_input.py`.

### G. Crawler v2 Mechanics

**When:** March 2026 onward.
**Technology:** Python, Europe PMC/OpenAlex/Semantic Scholar, DergiPark support, urllib/curl, tarfile, PDF validation, embeddings.

What was done:

- Built query tasks per source/language.
- Built language-specific concept pools.
- Added source-term and batch feedback.
- Built search gate and metadata decision functions.
- Added live Supabase canonical-key skip memory.
- Added local terminal paper state.
- Added acquisition fallback ladder.
- Added audit sampling for rejects.
- Added partial output on wall-clock stop.

Why it was needed:

Most papers returned by broad food/nutrition queries are not direct food-composition tables. The crawler must narrow candidates before expensive model/human work, but without hard-rejecting potentially useful papers due to one negative phrase.

How it was implemented:

- Additive scoring combines composition phrases, food/nutrient terms, units, methods, embeddings, learned feedback, and soft penalties.
- `validate_pdf_text` strips reference sections and requires strong full-text evidence.
- `_fetch_pdf_with_oa` tries PMC OA PDFs and tarballs.
- `_fetch_pdf` falls back through direct fetch, curl, HTML PDF link scraping, and PMC proof-of-work solving.
- Accepted outputs are recorded with reasons and funnel counters.

Evidence:

- `crawler_v2.py`: 2,215 lines.
- `ranking.py`: 486 lines.
- `test_bilingual_pipeline.py`: 1,120 lines.

### H. Upload and Routing Integration

**When:** April to June 2026.
**Technology:** Python Supabase client, Postgres upserts, canonical keys, JSON manifests.

What was done:

- Register accepted papers in Supabase.
- Persist source PDF URLs.
- Upsert search-hit audit rows.
- Persist query-batch history.
- Enqueue active model stage tasks.
- Preserve closed AI/human routes when a known paper is re-uploaded.
- Recover duplicate-key races by reusing existing paper rows.

Why it was needed:

Crawler discovery and model processing are separate systems. Upload has to bridge them without corrupting already-finalized or human-ready papers. It also needs to preserve search evidence for feedback learning.

How it was implemented:

- `upload_to_supabase.py` maps manifest papers to `papers`.
- `canonical_key` deduplicates across providers/DOIs/missing DOI cases.
- Search hits use deterministic hit keys.
- Existing routed/finalized rows are not reset just because the active stage changed.

Evidence:

- README upload script section.
- `upload_to_supabase.py`.
- `paper_search_hits`, `paper_search_batches`, `paper_search_batch_hits`.

### I. Pipeline Cockpit

**When:** 2026-05-13 and refined 2026-05-29.
**Technology:** Postgres aggregate RPC, React view, role-stable model labels.

What was done:

- Added a Pipeline cockpit dashboard.
- Showed crawler-to-human funnel.
- Showed current stage queues/errors.
- Added time filters.
- Added stable role labels: Small model, Medium model, Strong model.
- Backfilled historical direct Small -> Strong data into Medium counters for display.

Why it was needed:

Daily ops is complex. The team needed a cockpit view that answered "where are papers stuck right now?" without requiring direct database inspection.

How it was implemented:

- `get_pipeline_ops_snapshot` aggregates search batches, stage tasks, AI extraction outcomes, submissions, approvals, and review outcomes.
- Frontend `PipelineOpsView` renders funnel bars and current queues.
- `annotateHelpers.js` maps model specs into stable role labels.

Evidence:

- `get_pipeline_ops_snapshot` in `migration.sql`.
- `PipelineOpsView.jsx`.
- `annotateHelpers.js`.

### J. Documentation, Agent Rules, and Live Ops State

**When:** March to June 2026.
**Technology:** Markdown, DOCX/PDF export scripts, repo instructions.

What was done:

- README updated repeatedly as architecture changed.
- BACKLOG maintained and completed items removed.
- AGENTS and INSTRUCTIONS written/updated.
- Reviewer SOP and workflow map created.
- Handoff state document maintained.
- Defense reports/decks generated.
- Runtime secret handling documented.

Why it was needed:

This project is large enough that undocumented decisions get accidentally undone. Documentation captures why Gemma is text-mode, why no hard-negative crawler vetoes are allowed, why source-URL PDFs are default, why cockpit AI lists must stay slim, and why final truth comes from approval outcomes.

Assessment value:

Documentation here is operational infrastructure. It keeps future agents and team members from breaking production assumptions.

## Arciel Evidence Summary by Area

| Area | Main files | Evidence |
| --- | --- | --- |
| Schema/RLS/RPC | `migration.sql` | 5,396 lines, 31 tables, 75 policies. |
| AI cascade | `unified_evaluator.py`, `ai_routing.py`, `process_stage_queue.py` | 3,089 core lines plus tests. |
| Crawler | `crawler_v2.py`, `ranking.py`, source adapters | 2,701 core crawler/ranking lines. |
| Feedback | `update_terms.py`, feedback modules | 1,219 main feedback lines. |
| Daily ops | `daily_ops_orchestrator.py`, workflow YAML, tests | GitHub Actions every 5 minutes, 5 workers. |
| Upload/storage | `upload_to_supabase.py`, `api/pdf.js`, `pdfCache.js` | Source-URL PDF architecture and egress control. |
| Tests | `test_ai_routing.py`, `test_daily_ops.py`, `test_bilingual_pipeline.py`, frontend scanner tests | 5,617 tracked test lines. |
| Docs/project management | README, AGENTS, STATE, workflow map, defense reports | Standing instructions and operational handoff. |
