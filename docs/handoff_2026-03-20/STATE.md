# OpenNutri Handoff - 2026-05-02 (Europe/Istanbul)

This is the current high-signal project state after the reviewer workflow moved from slot-based cross-checking to a shared general queue with Arciel approval.

## Primary Goal

- Preliminary Study 3 is skipped. The near-term goal is high-precision discovery of papers with useful direct food-composition data, accepting lower recall for now and preserving skipped candidates for a later pass.
- Keep paper stock intentionally low and refresh feedback before crawler refill so later searches benefit from accepted human truth.
- Daily ops now uses Gemma proof extraction before Gemini: cheap Gemma calls screen/extract broadly, Gemma-positive papers enqueue Gemini by priority, and the Gemini budget remains 20 calls/day.

## Documentation Pointers

- `docs/reviewer_workflow_map.md`: source of truth for reviewer UI, schema, RPCs, approval, and ops behavior.
- `docs/reviewer_sop_en.md`: worker-facing labeler SOP.
- `AGENTS.md`: standing coding-agent instructions and current product truths.

## Team / Roles

- Arciel: developer, configured label approver, final reviewer, dashboard reviewer.
- Peri, Aleyna, Aysegul, Daine: general-queue labelers unless access flags are changed.
- Approval authority is stored as `reviewer_profiles.can_approve_labels`; currently Arciel is seeded as `true`.
- `tester_access=true` keeps an account read-only even if it has cockpit visibility.

## Active Workflow

Pipeline:

`crawl -> upload -> Gemma proof extraction -> Gemini extraction -> human_review_ready shared queue -> paper_label_submissions -> Arciel approval -> paper_label_approvals -> paper_review_outcomes -> feedback learning`

Important rules:

- Labelers see a shared Queue of available papers.
- A paper is available to labelers only after the model cascade creates a latest normalized `has_data` decision payload. AI `no_usable_data` decisions are provisional skips by default and remain inspectable in cockpit/All Papers, not the labeler queue.
- A paper leaves the visible Queue as soon as any pending/accepted general submission exists.
- Drafts do not claim papers. If two people already have the same paper open, both can still submit before final approval.
- Every submitted payload is immutable in `paper_label_submissions`.
- Arciel's own submissions auto-accept and immediately write `paper_label_approvals` plus `paper_review_outcomes`.
- Non-Arciel submissions wait in Approval. Arciel can edit before accepting final truth.
- Original labeler payloads are never overwritten; accepted reviewer payloads are stored separately.
- `paper_label_approvals.correction_diff_json` records what changed for performance/mistake review.
- Labelers do not see the approval page or other labelers' submissions.
- Cockpit/tester/developer accounts can inspect Approval/Dashboard/All Papers, but tester accounts cannot mutate live data.

## Active Schema / RPCs

New active tables:

- `paper_label_submissions`
- `paper_label_approvals`
- `paper_review_outcomes` with `label_submission_id` and `label_approval_id`
- `routing_stage_configs` now orders model stages. `gemma_proof_extraction_v1` is the active entry stage; `gemini_flash_db_payload_v2` is the second extraction stage.

Important access flags:

- `reviewer_profiles.tester_access`
- `reviewer_profiles.cockpit_access`
- `reviewer_profiles.can_approve_labels`

Important RPCs/functions:

- `sync_reviewer_profile()`
- `get_general_queue_papers(p_limit)`
- `submit_general_label(p_annotation_id, p_decision_kind, p_submission_metadata)`
- `approve_label_submission(p_label_submission_id, p_approval_annotation_id, p_decision_kind, p_approval_note)`
- `build_label_payload_diff(original, final)`
- `current_user_can_approve_labels()`

Legacy tables preserved for audit/history:

- `reviewer_slots`
- `reviewer_slot_members`
- `paper_slot_assignments`
- `paper_user_assignments`
- `paper_assignment_submissions`
- `paper_conflicts`

The migration clean-breaks unresolved legacy slot/user assignment rows to `cancelled`; new workflow code must not create new slot/user assignments.

## Frontend Status

`apps/expert-annotator/src/pages/Annotate.jsx` now exposes:

- `Queue`: shared available paper list, AI prefill from latest Gemini `has_data` `ai_extractions.normalized_payload_json`, draft save, final submit, no-usable-data submit, ask-for-help. Queue papers already have normalized useful AI output; AI `no_usable_data` decisions are provisional skips outside the labeler queue, and AI reasoning is not shown to labelers.
- `Approval`: cockpit-visible; editable only for `can_approve_labels` non-testers.
- `Dashboard`: labeler performance and detailed correction history.
- `All Papers`: global paper/submission/approval/outcome state plus a `Latest AI` Details affordance for the normalized DB-compliant extraction payload.
- `Reviewers`: admin table for active/tester/cockpit/approval flags.
- `Suggestions`: suggestion and general queue help triage.

Frontend validation currently passes with:

- `npm run build`
- `npm run lint` with only pre-existing hook warnings in `App.jsx` and `ResetPassword.jsx`.

## AI Routing

- Active entry stage is `gemma_proof_extraction_v1`; second stage is `gemini_flash_db_payload_v2`.
- Active shared prompt contract is `opennutri_master_payload_v1` for Gemma and `gemini_flash_db_payload_v3` for Gemini until the Gemini config is renamed.
- Upload enqueues `paper_stage_tasks` instead of running models inline.
- AI extraction stores deterministic `normalized_payload_json` using the same top-level contract as human payloads, including DB/custom food identity, raw food name, preparation state, DB/custom nutrient identity, raw nutrient name, value, unit, basis, sample size, confidence, source citation, and row metadata.
- The annotator treats that payload as the reviewer-facing AI output: it preloads editable queue rows when there is no saved annotation, and cockpit Details shows the normalized payload/normalization summary without model reasoning.
- The AI prompt target is useful OpenNutri food composition data only. Intervention/effect/outcome papers about nutrient doses, supplements, extracts, diets, biomarkers, cells, animals, microbes, health effects, processing outcomes, sensory scores, or similar responses are empty unless they also report useful direct food/product composition tables. One-off treatment/formulation variants are no usable data unless they represent stable real-world foods/products worth adding to the DB.
- `UnifiedEvaluator` accepts requested JSON object output, top-level candidate-row arrays, and nested `food -> nutrients[]` arrays.
- Prompt should include the full nutrient catalog plus high-signal food candidates matched from the paper text, but not the full food catalog.
- AI-provided DB IDs are verified against current DB rows before acceptance.
- Gemma `has_data` outputs enqueue Gemini with a computed priority from model confidence, accepted row count, evidence quality, and normalization quality. Gemma/Gemini `no_usable_data` outputs become `ai_provisional_no_usable_data` with `route_destination = provisional_skip`. Gemini `has_data` outputs with normalized rows become `human_review_ready`.
- AI-finalized outcomes use `truth_source_kind = ai_model` and remain excluded from human-truth feedback.

## Ops

`services/data-pipeline/scripts/refill_assignment_queue.py` is retained under the old filename for compatibility. It now:

- reports shared general queue stock;
- excludes papers with final outcomes or pending/accepted general submissions;
- excludes unresolved legacy slot assignments and legacy global no-data rows;
- drains queued Gemma and Gemini stage tasks before requesting crawler refill;
- triggers crawler refill when visible stock is below `--target-open`.

`services/data-pipeline/scripts/daily_ops_orchestrator.py` now treats `--target-open` as compatibility/reporting only. Scheduled ops spend cheap Gemma calls to fill the Gemini queue and maximize the 20-call Gemini budget instead of stopping when the human queue is full.

Daily ops order:

1. Drain queued Gemini extraction work within the daily Gemini budget.
2. Drain queued Gemma proof-extraction work when Gemini has no ready tasks.
3. Crawl/upload when no queued model work is available.
4. Process new Gemma work, then newly queued Gemini work.
5. Sleep 5 minutes in GitHub Actions after non-terminal per-invocation budget stops.
6. Repeat until terminal.

Terminal stop reasons:

- `daily_ai_call_budget_exhausted`: 20 Gemini calls consumed for the day.
- `ai_first_task_quota_limited`
- `no_progress`: crawler/AI pass produced no queued or processed work.
- `dry_run`

Non-terminal reasons include:

- `ai_run_budget_exhausted`
- `ai_quota_limited_after_progress`
- `max_cycles`

Feedback refresh is intentionally tied to crawler refill only; queued-AI draining does not refresh feedback.

## Feedback / Benchmark Boundary

- Feedback learning reads `paper_review_outcomes` first.
- Only `truth_source_kind = human_review` accepted outcomes feed current human-truth feedback.
- Pending and superseded `paper_label_submissions` are excluded from feedback learning.
- Legacy `paper_label_events` / `paper_global_labels` remain fallback only for older papers without resolved outcomes.
- Unapproved submissions are performance/audit data, not benchmark truth.

## Useful Commands

- Apply schema migration:
  - `cd apps/expert-annotator && DATABASE_URL=... node run-migration.js`
- Verify live workflow schema:
  - `cd apps/expert-annotator && DATABASE_URL=... node check-workflow-schema.mjs`
- Frontend validation:
  - `cd apps/expert-annotator && npm run build && npm run lint`
- Python tests:
  - `python3 -m unittest services.data-pipeline.tests.test_ai_routing services.data-pipeline.tests.test_daily_ops`
- Refresh feedback terms:
  - `python3 services/data-pipeline/food_paper_crawler/feedback/update_terms.py`
- Refill crawler stock:
  - `python3 services/data-pipeline/scripts/ensure_paper_stock.py --threshold 0`
- Drain AI routing queue:
  - `python3 services/data-pipeline/scripts/process_stage_queue.py`
- Run daily ops:
  - `python3 services/data-pipeline/scripts/daily_ops_orchestrator.py --daily-ai-call-budget 20 --max-ai-tasks 5`
- Check shared queue stock / trigger refill loop:
  - `python3 services/data-pipeline/scripts/refill_assignment_queue.py --target-open 50`

## Live Migration Status

- The general queue + approval migration was applied to the live Supabase DB on 2026-05-02.
- The DB-aligned AI payload migration was applied to the live Supabase DB on 2026-05-02; verification confirmed the new raw/custom/basis/source metadata columns on `food_items` and `annotation_nutrient_values`.
- Live verification confirmed the new `paper_label_submissions` and `paper_label_approvals` tables, approval RPCs, `can_approve_labels`, and `paper_review_outcomes` provenance columns.
- Live clean-break verification found `0` unresolved legacy slot assignments and `0` unresolved legacy user assignments.
- Live reviewer config currently has `1` active approver.
- Current visible general queue stock was `0` immediately after migration, so daily ops/crawler refill needs to add human-ready papers.

## Still Needs Attention

- L2 classifier training is still deferred until more accepted human-review outcomes exist.
- PDF nutrient highlights remain precision-first/table-only; continuation-page recall and cross-text-item matching are still future work.
