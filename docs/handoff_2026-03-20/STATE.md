# OpenNutri Handoff - 2026-05-02 (Europe/Istanbul)

This is the current high-signal project state after the reviewer workflow moved from slot-based cross-checking to a shared general queue with Arciel approval.

## Primary Goal

- Preliminary Study 3 is skipped. The near-term goal is high-precision discovery of papers with useful direct food-composition data, accepting lower recall for now and preserving skipped candidates for a later pass.
- Current acquisition mode is English-only. Turkish/DergiPark code remains available, but default refill and daily ops request `tr=0`, skip DergiPark, and use Europe PMC/OpenAlex/Semantic Scholar.
- Keep paper stock intentionally low and refresh feedback before crawler refill so later searches benefit from accepted human truth.
- Daily ops uses `gemma_proof_extraction_v1` with `gemma-4-31b-it` before Gemini, with `gemma-4-26b-a4b-it` configured as a same-stage fallback for retryable 31B failures. Gemma-positive papers enqueue Gemini by priority, and scheduled ops now run as recurring ticks keyed to UTC-day completion counts: top up queued Gemma papers only for the next immediate 15-paper processing slice, drain bounded Gemma slices, and interleave a small Gemini slice from already-ranked candidates so useful papers can reach humans before the full Gemma target completes. If Gemma source/refill is empty while queued Gemini candidates and daily Gemini quota remain, the tick still drains Gemini instead of exiting early. Existing Gemma backlogs above the slice target should drain naturally without a new 1500-paper crawl.
- GitHub Actions daily ops is scheduled every 5 minutes. Each scheduled workflow invocation fans out to 20 independent workers, while manual dispatches accept a `workers` input for smaller controlled bursts. Each active worker runs one `daily_ops_orchestrator.py --tick-mode --interleave-extraction` pass and exits, so delayed or cancelled runners are recovered by later workers instead of relying on one long daily job. The workflow intentionally allows overlapping scheduled ticks; DB task claiming prevents duplicate model work, and one serialized runner was too slow for the 1500/day Gemma target.
- The scheduled workflow sets `AI_MODEL_TASK_TIMEOUT_SECONDS=300`, `AI_STAGE_MAX_TASK_ATTEMPTS=2`, `GEMINI_REQUEST_TIMEOUT_SECONDS=300`, and `GEMMA_STAGE_TEXT_LIMIT_CHARS=24000`. Gemma receives a capped head/tail excerpt small enough to avoid repeated 300-second Gemma timeouts; Gemini extraction remains uncapped unless a Gemini-specific cap is set. The 300-second model timeout is intentional so one slow paper cannot consume a large fraction of the GitHub Actions job cap.
- Scheduled ops runs storage hygiene from matrix worker 1 using `cleanup_paper_storage.py --apply`. It deletes orphan paper bucket objects and PDFs for failed/provisional/final no-data AI routes, but preserves queued Gemini, model-processing, and `human_review_ready` PDFs needed for extraction and labeling.

## Documentation Pointers

- `docs/reviewer_workflow_map.md`: source of truth for reviewer UI, schema, RPCs, approval, and ops behavior.
- `docs/reviewer_sop_en.md`: worker-facing labeler SOP.
- `AGENTS.md`: standing coding-agent instructions and current product truths.

## Team / Roles

- Arciel: developer, configured label approver, final reviewer, dashboard reviewer.
- Peri, Aleyna, Aysegul, Daine, and the `f221229078@ktun.edu.tr` account: general-queue labelers unless access flags are changed.
- Approval authority is stored as `reviewer_profiles.can_approve_labels`; currently Arciel is seeded as `true`.
- `tester_access=true` keeps an account read-only even if it has cockpit visibility.
- Signup allowlist data lives in `allowed_auth_emails`; it is not client-readable/writable. RLS is enabled, direct `anon`/`authenticated`/`public` table grants are revoked, and signup checks run through the security-definer auth hook.

## Active Workflow

Pipeline:

`crawl -> upload -> Gemma proof extraction -> Gemini extraction -> human_review_ready shared queue -> paper_label_submissions -> Arciel approval -> paper_label_approvals -> paper_review_outcomes -> feedback learning`

Important rules:

- Labelers see a shared Queue of available papers.
- A paper is available to labelers only after the model cascade creates a latest normalized `has_data` decision payload. AI `no_usable_data` decisions are provisional skips by default and stay out of the labeler queue and default cockpit paper overview.
- A paper leaves the visible Queue as soon as any pending/accepted general submission exists.
- Drafts do not claim papers. If two people already have the same paper open, both can still submit before final approval.
- Every submitted payload is immutable in `paper_label_submissions`.
- Arciel's own submissions auto-accept and immediately write `paper_label_approvals` plus `paper_review_outcomes`.
- Non-Arciel submissions wait in Approval. Arciel can edit before accepting final truth.
- Original labeler payloads are never overwritten; accepted reviewer payloads are stored separately.
- `paper_label_approvals.correction_diff_json` records what changed for performance/mistake review.
- Labelers do not see the approval page or other labelers' submissions.
- Cockpit/tester/developer accounts can inspect Approval/Dashboard/Useful Papers, but tester accounts cannot mutate live data.

## Active Schema / RPCs

New active tables:

- `paper_label_submissions`
- `paper_label_approvals`
- `paper_review_outcomes` with `label_submission_id` and `label_approval_id`
- `routing_stage_configs` now orders model stages and stores `fallback_model_names`. `gemma_proof_extraction_v1` is the active entry stage using `gemma-4-31b-it` with `gemma-4-26b-a4b-it` fallback; `gemini_flash_db_payload_v2` is the second extraction stage.

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
- `get_pipeline_ops_snapshot(p_start_at, p_end_at, p_workflow_language, p_paper_id)`: cockpit-only aggregate endpoint for the Pipeline tab. It is security-definer because `paper_stage_tasks` remains service-role managed.

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

- `Queue`: shared available paper list, quiet AI prefill from latest Gemini `has_data` `ai_extractions.normalized_payload_json`, compact Sources strip for table/paragraph/page navigation, draft save, final submit, no-usable-data submit, ask-for-help. Queue papers already have normalized useful AI output; AI `no_usable_data` decisions are provisional skips outside the labeler queue, and AI reasoning or AI-prefill status banners are not shown to labelers. Source navigation maps printed journal page hints to actual PDF pages when header/footer page labels are detectable.
- `Approval`: cockpit-visible; editable only for `can_approve_labels` non-testers. The editable final payload uses the same compact Sources strip so approvers can jump to matched PDF table overlays, expanded paragraph overlays, or page hints.
- `Dashboard`: labeler performance and detailed correction history.
- `Pipeline`: cockpit-only operational view for crawler search, PDF acquisition, Gemma screening, Gemini extraction, and human review. It uses the `get_pipeline_ops_snapshot` RPC to show a simple "Right Now" queue block plus an all-time-by-default funnel with a time filter.
- `Useful Papers`: useful paper/submission/approval/outcome state plus a `Latest AI` Details affordance for the normalized DB-compliant extraction payload. Provisional AI no-data skips are hidden from this default overview.
- `Reviewers`: admin table for active/tester/cockpit/approval flags.
- `Suggestions`: cockpit/admin-only suggestion and general queue help triage.
- `My Suggestions`: regular-labeler view that shows each of their submitted suggestion/help-request statuses; the `Suggest` submit button is hidden for cockpit/admin users.
- Suggestion attachments are previewed from per-file signed storage URLs in both `Suggestions` (cockpit/admin) and `My Suggestions` (regular labeler) views, with an `Open full image` link per attachment.

Frontend validation currently passes with:

- `npm run build`
- `npm run lint` with only pre-existing hook warnings in `App.jsx` and `ResetPassword.jsx`.

## AI Routing

- Active entry stage is `gemma_proof_extraction_v1` with `gemma-4-31b-it` and `gemma-4-26b-a4b-it` fallback; second stage is `gemini_flash_db_payload_v2`.
- Active shared prompt contract is `opennutri_evidence_payload_v1` for Gemma and Gemini.
- Upload enqueues `paper_stage_tasks` instead of running models inline.
- AI extraction stores deterministic `normalized_payload_json` using the same top-level contract as human payloads, including DB/custom food identity, raw food name, preparation state, DB/custom nutrient identity, raw nutrient name, value, unit, basis, sample size, confidence, source citation, and row metadata. Evidence metadata now preserves `table_label`, `page_hint`, `source_quote`, `source_location_type`, `section_heading`, and `paragraph_hint` for reviewer PDF navigation.
- The annotator treats that payload as the reviewer-facing AI output: it silently preloads editable queue rows when there is no saved annotation, and cockpit Details shows the normalized payload/normalization summary without model reasoning.
- The AI prompt target is useful OpenNutri food composition data only. Intervention/effect/outcome papers about nutrient doses, supplements, extracts, diets, biomarkers, cells, animals, microbes, health effects, processing outcomes, sensory scores, or similar responses are empty unless they also report useful direct food/product composition tables. One-off treatment/formulation variants are no usable data unless they represent stable real-world foods/products worth adding to the DB.
- `UnifiedEvaluator` accepts requested JSON object output, top-level candidate-row arrays, and nested `food -> nutrients[]` arrays.
- The prompt requires broad evidence locations per extracted row. Shared table-level evidence is preferred for rows from the same table; paragraph/section evidence uses short exact source quotes and metadata hints rather than stored coordinates.
- Prompt should include the full nutrient catalog plus high-signal food candidates matched from the paper text, but not the full food catalog.
- AI-provided DB IDs are verified against current DB rows before acceptance.
- Gemma `has_data` outputs enqueue Gemini with a computed priority from model confidence, accepted row count, evidence quality, and normalization quality. Gemma/Gemini `no_usable_data` outputs become `ai_provisional_no_usable_data` with `route_destination = provisional_skip`; the stage processor keeps the DB routing/audit rows but deletes the skipped paper's PDF from Supabase Storage after the task completes so rejected papers do not accumulate file storage. Retryable 31B timeout/quota/transient model failures attempt the configured 26B fallback in the same task; non-retryable 31B model-configuration failures surface as permanent configuration errors instead of silently looping through the queue. Model runtime initialization now happens before task claiming, so missing API-key/config failures do not leave rows stuck in `processing`. Gemini `has_data` outputs with normalized rows become `human_review_ready`.
- Upload/re-upload preserves closed routing state: papers that already have a closed AI route or human outcome can refresh metadata/search-hit audit rows without being sent back through the active model stage, and those closed-route repeats skip Supabase Storage upload so deleted provisional-skip PDFs are not recreated. Concurrent upload workers can race on the same `papers.canonical_key`; uploader duplicate-key recovery should reuse the existing paper row, keep search-hit audit links, and enqueue the active stage only when that row is still open.
- Oversized PDFs are not allowed to abort an ops batch. Crawler v2 treats PDFs above the shared upload limit as `pdf_fetch` failures before counting them accepted, and `upload_to_supabase.py` skips any oversized local file or Supabase Storage 413 while continuing to persist the rest of the batch. The shared limit defaults to 50 MiB and can be overridden with `OPENNUTRI_MAX_PAPER_PDF_BYTES` or `SUPABASE_PAPER_MAX_UPLOAD_BYTES`.
- AI-finalized outcomes use `truth_source_kind = ai_model` and remain excluded from human-truth feedback.
- `process_stage_queue.py` requeues stale `processing` tasks before claiming new work, which lets the next run recover papers left by cancelled GitHub runners or interrupted local workers. Daily ops queue/refill decisions count executable queued `paper_stage_tasks` rows, not paper routing rows alone, so stale historical `queued_for_ai` paper summaries cannot block a same-run refill. The stage processor also reports `storage_pdf_deleted` / `storage_cleanup_failed` in stage summaries when provisional no-data skips trigger PDF cleanup.
- Crawler batch acquisition respects remaining per-language targets, so one strong search batch should not download far beyond the requested English refill size. Before acquisition, crawler v2 merges local terminal crawl state with live `papers.canonical_key` rows from Supabase so already queued, provisional-skipped, human-ready, or finalized papers are not downloaded again; metadata-only `paper_search_hits` rejects are not global skip memory.

## Ops

`services/data-pipeline/scripts/refill_assignment_queue.py` is retained under the old filename for compatibility. It now:

- reports shared general queue stock;
- excludes papers with final outcomes or pending/accepted general submissions;
- excludes unresolved legacy slot assignments and legacy global no-data rows;
- drains queued Gemma and Gemini stage tasks before requesting crawler refill;
- triggers English-only crawler refill when visible stock is below `--target-open`.

`services/data-pipeline/scripts/daily_ops_orchestrator.py` treats `--target-open` as compatibility/reporting only. Scheduled ops do not stop when the human queue is full; in `--tick-mode --interleave-extraction`, each run requeues stale stage tasks, checks UTC-day completed task counts, tops up Gemma stock only to the next immediate slice target when the queued count is below that slice, drains one bounded Gemma slice, drains a small Gemini slice when ranked candidates exist, and exits for the next cron recall.

Daily ops order:

1. Count completed Gemma and Gemini `paper_stage_tasks` since UTC midnight.
2. If today's completed Gemma count is below `--screening-daily-target 1500`, requeue stale Gemma `processing` tasks.
3. Count queued Gemma work from `paper_stage_tasks.status = 'queued'`. If executable queued work is below the next bounded slice target, crawl/upload only the immediate English deficit using 15-paper refill batch/chunk settings and `--refill-step-tr 0`; if queued task work is already above the slice target, do not crawl.
4. Drain at most `--screening-tick-tasks 15` Gemma tasks, bounded by the remaining daily Gemma target and queued count, then exit.
5. Once today's completed Gemma count is at least 1500, requeue stale Gemini `processing` tasks.
6. In scheduled interleaved mode, drain Gemini at highest-priority order for at most `--extraction-tick-tasks 2`, bounded by `--extraction-daily-target 20`, after each Gemma slice when ranked candidates exist; assign any new `human_review_ready` papers immediately.
7. Fail non-quota task errors past `AI_STAGE_MAX_TASK_ATTEMPTS=2` instead of retrying forever; quota/rate-limit errors continue to requeue without consuming meaningful attempts.
8. Stop on daily targets reached, stage quota, source exhaustion/no candidates, model configuration error, dry-run, or GitHub Actions job termination. The next 5-minute tick resumes from database state.

Terminal stop reasons:

- `all_stage_quotas_exhausted`
- `daily_targets_reached`
- `screening_daily_target_reached`
- `extraction_daily_quota_exhausted`
- `max_wallclock_reached`
- `no_extraction_candidates`
- `source_exhausted`
- `ai_stage_configuration_error`
- `dry_run`

The JSON summary reports `mode`, `day_start_utc`, UTC-day completed counts, screened calls, candidates routed to Gemini, Gemini calls used, new human-ready papers, quota-exhausted stages, per-stage windows, and remaining queued candidates.

Feedback refresh is intentionally tied to crawler refill only; queued-AI draining does not refresh feedback. DergiPark refresh/search is skipped unless Turkish is explicitly re-enabled with a positive Turkish target and a DergiPark source list.

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
  - `python3 services/data-pipeline/scripts/daily_ops_orchestrator.py --json-summary --tick-mode --interleave-extraction --stage-rpm gemma_proof_extraction_v1=15,gemini_flash_db_payload_v2=15 --max-wallclock-minutes 0 --screening-daily-target 1500 --screening-tick-tasks 15 --extraction-daily-target 20 --extraction-tick-tasks 2 --screening-refill-batch-en 15 --screening-refill-chunk-en 15 --screening-prefill-stall-limit 3 --refill-step-tr 0`
- Check shared queue stock / trigger refill loop:
  - `python3 services/data-pipeline/scripts/refill_assignment_queue.py --target-open 50`

## Security / Secrets

- Runtime credentials are environment-only. Do not commit API keys, database URLs, Supabase service-role keys, personal access tokens, or test passwords.
- Legacy compatibility and DB utility scripts read credentials from `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_KEY`, `VITE_SUPABASE_ANON_KEY`, `DATABASE_URL`, `GEMINI_API_KEY`, `SIGNUP_EMAIL`, and `SIGNUP_PASSWORD` as needed, and fail fast when required values are missing.
- Public-repo secret alerts mean the provider secret is compromised. Remove current tracked occurrences immediately, rotate/revoke the provider secret, and treat historical git occurrences as compromised even after source cleanup.

## Live Migration Status

- The general queue + approval migration was applied to the live Supabase DB on 2026-05-02.
- The DB-aligned AI payload migration was applied to the live Supabase DB on 2026-05-02; verification confirmed the new raw/custom/basis/source metadata columns on `food_items` and `annotation_nutrient_values`.
- Live verification confirmed the new `paper_label_submissions` and `paper_label_approvals` tables, approval RPCs, `can_approve_labels`, and `paper_review_outcomes` provenance columns.
- Live clean-break verification found `0` unresolved legacy slot assignments and `0` unresolved legacy user assignments.
- Live reviewer config currently has `1` active approver.
- On 2026-05-09, manual live ops verified the English-only route end to end. The live DB had `49` English papers after crawl/upload, no Turkish papers from the run, `19` completed Gemma tasks, `3` completed Gemini tasks, no stuck `processing` tasks after cleanup, and `2` visible general-queue `human_review_ready` papers with normalized Gemini `has_data` payloads.
- On 2026-05-13, the Pipeline RPC/view migration was applied to the live Supabase DB and verified with a cockpit-profile claim. The view was later simplified to presentation-first current queues plus an all-time paper funnel.

## Still Needs Attention

- L2 classifier training is still deferred until more accepted human-review outcomes exist.
- PDF nutrient-name click highlights remain precision-first/table-only; continuation-page recall and cross-text-item nutrient phrase matching are still future work. Compact AI source strips cover table/paragraph/page navigation separately, map printed page hints when possible, and draw visible overlays for every matched table or paragraph block, clicked or not. Evidence now snaps to whole detected tables or whole paragraph blocks before scaling from PDF.js text-coordinate bounds; sources in the same resolved block share one deduplicated overlay and one source chip instead of drawing overlapping partial boxes or repeated scroll targets. Paragraph matching ignores document chrome such as affiliations, article-history/keyword sidebars, and copyright rows; nutrient word click marks also reject narrative prose after tables. Table detection handles standalone `Table N` labels followed by long caption continuation rows and wide multi-column headers, which covers layouts like the oat germplasm Table 2 page.
