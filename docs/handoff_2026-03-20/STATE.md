# OpenNutri Handoff - 2026-05-02 (Europe/Istanbul)

This is the current high-signal project state after the reviewer workflow moved from slot-based cross-checking to a shared general queue with Arciel approval.

## Primary Goal

- As of 2026-07-21, the near-term goal is the FNDDS Core dataset/API, measured food
  search, deployment, and the first consumer app vertical slice. Research-paper
  acquisition and extraction are preserved but dormant.
- GitHub workflow IDs `266228133` (`Daily OpenNutri Ops`) and `308071631`
  (`Supabase Watchdog`) were set to `disabled_manually`; both cron triggers were
  removed from the repository. No runs were active when they were stopped. The
  ordinary push/PR `Tests` workflow remains active. This pause supersedes later
  historical descriptions of scheduled research operations in this handoff.
- Existing Supabase, Vercel, and Cloudflare R2 resources were not deleted. R2 is the
  service with the 10 GB free storage allowance; retaining its existing objects does
  not run the crawler or model pipeline.
- Current acquisition mode is English-only. Turkish/DergiPark code remains available, but default refill and daily ops request `tr=0`, skip DergiPark, and use Europe PMC/OpenAlex/Semantic Scholar.
- 2026-06-21 operational audit: paper search and registration were still active, but no `ai_extractions` had been created since 2026-06-12. The outage began when new paper URLs moved to Cloudflare R2: drain workers did not receive R2 credentials or `boto3`, so they depended on the public `r2.dev` hostname and completed with zero model calls when that path was unreachable. Workers now read R2 objects through the authenticated S3-compatible endpoint and fall back to `source_pdf_url`; task claiming preserves prior `last_error`, blank evaluator exceptions retain their exception type, and the refill controller opens a circuit after at least 20 recent Gemma failures with zero completions in 6 hours. The circuit stops crawler/R2 growth while drain workers continue attempting queued work. Scheduled final Gemini settings are a 250-call Pacific-day safety ceiling with 5 tasks per worker tick, not the older 20/day target. Live verification run `27898052908` completed successfully after the repair: controller refill was blocked by the circuit, then one drain worker processed 20 Gemma tasks with zero failures, routed 2 to Flash-Lite, processed both Flash-Lite tasks, and processed both resulting final Gemini tasks. The 24 new extraction rows were the first since June 12; all 20 source papers ultimately resolved as provisional no-data, and 5 Gemma tasks remained queued with no stuck `processing` rows.
- Keep paper stock intentionally low and refresh feedback before crawler refill so later searches benefit from accepted human truth.
- 2026-06-04 live ops audit: the active new Supabase project had 3,849 papers, 11,422 `paper_search_hits`, 644 search batches with 12,170 total batch results, 5,188 `paper_stage_tasks`, and 4,604 `ai_extractions`. Final Gemini was meeting/overrunning the 20-per-Pacific-day target from backlog (29 completed in the current Pacific quota day at audit time; 20-21 on most prior days), but Gemma and Flash-Lite were idle because no Gemma/Flash-Lite tasks were queued and no crawler batch had completed since 2026-05-31. Recent GitHub Actions worker jobs succeeded, while `refill-controller` jobs were repeatedly cancelled at the 90-minute job cap after starting `crawler refill 1: EN=150 TR=0`; the controller was changed to bounded 30-paper crawler chunks with partial-manifest upload.
- Daily ops uses a 3-stage model cascade: `gemma_proof_extraction_v1` (`gemma-4-31b-it`, with `gemma-4-26b-a4b-it` as same-stage fallback) screens/ranks up to 1500 papers/day, `gemini_flash_lite_triage_v1` (`gemini-3.1-flash-lite`) re-ranks up to 500 top Gemma candidates/day, and `gemini_flash_db_payload_v2` (`gemini-3.5-flash`) has a 250-call Pacific-day safety ceiling. Scheduled ops run as recurring ticks keyed to stage-specific quota-day completion counts: Gemma defaults to UTC reset, Gemini-family stages default to `America/Los_Angeles` reset. The serialized controller tops up only enough queued/non-stale-processing Gemma work to keep about 150 active tasks using bounded 30-paper crawler chunks, unless the recent-failure circuit is open; scheduled crawler refills have a 2400-second wall-clock budget and write accepted partial results before upload. Drain workers process bounded Gemma slices of 20 tasks each, then interleave Flash-Lite slices of 10 and final Gemini slices of 5 so useful papers can reach humans before the full Gemma target completes. If Gemma source/refill is empty while queued downstream candidates and quota remain, workers still drain Flash-Lite/final Gemini instead of exiting early. Existing Gemma backlogs above the active target should drain naturally instead of triggering a new 1500-paper crawl.
- GitHub Actions daily ops is scheduled every 5 minutes. Each scheduled workflow invocation runs one `refill-controller` job under the `daily-ops-refill-controller` concurrency group alongside a 5-job drain-only worker matrix; the workers are no longer gated on the controller. Manual dispatches accept a `workers` input for smaller controlled bursts, and inactive worker entries skip checkout/setup/dependency work before the final drain step. Controller jobs are the only scheduled path allowed to crawl/upload/refill; workers run `daily_ops_orchestrator.py --drain-only --tick-mode --interleave-extraction`, install only `requirements-worker.txt`, avoid run-id keyed data/model caches, and only claim already-created model tasks. The controller installs full crawler dependencies and keeps only a stable HuggingFace/model cache. Overlapping worker matrices are allowed because DB task claiming prevents duplicate model work.
- The scheduled workflow sets `AI_MODEL_TASK_TIMEOUT_SECONDS=300`, `AI_STAGE_MAX_TASK_ATTEMPTS=2`, `GEMINI_REQUEST_TIMEOUT_SECONDS=300`, and `GEMMA_STAGE_TEXT_LIMIT_CHARS=24000`. Gemma receives a capped head/tail excerpt small enough to avoid repeated 300-second Gemma timeouts; Gemini extraction remains uncapped unless a Gemini-specific cap is set. The 300-second model timeout is intentional so one slow paper cannot consume a large fraction of the GitHub Actions job cap.
- Scheduled ops no longer stores paper PDFs in Supabase Storage. The crawler downloads and validates source PDFs locally, re-hosts accepted PDFs on R2, persists the R2 URL in `papers.pdf_url`, and preserves the publisher URL in `papers.source_pdf_url`. Model workers fetch R2 URLs through the authenticated S3-compatible endpoint and fall back to the source URL; the serialized controller skips Supabase paper-storage cleanup/soft-limit checks. Keep `OPENNUTRI_STORE_PDFS_IN_SUPABASE=0` unless an explicit legacy Storage run is reviewed; suggestion attachments still use their private Storage bucket.
- 2026-06-04 Supabase usage audit: live new-project SQL size was about 286 MB against the 500 MB Free database limit, with `public.claims` alone taking about 188 MB. Paper Storage held only 21 legacy `papers` objects, about 17 MB total. Cockpit AI list loading was reduced by replacing `ai_extractions.select('*').limit(5000)` with `get_cockpit_ai_extractions(5000)`, which returns normalized payloads and `raw_data.normalization_summary` while omitting raw model responses/reasoning; measured JSON dropped from about 82 MB to about 11 MB. Queue prefill now fetches only each paper's latest AI extraction row.

## Documentation Pointers

- `docs/reviewer_workflow_map.md`: source of truth for reviewer UI, schema, RPCs, approval, and ops behavior.
- `docs/reviewer_sop_en.md`: worker-facing labeler SOP.
- `docs/opennutri_core_fndds.md`: FNDDS product-dataset source verification,
  canonical table contract, build command, quality rules, and measured `v0.0.1` release.
- `AGENTS.md`: standing coding-agent instructions and current product truths.

## OpenNutri Core Product Dataset

- The consumer dataset is a separate versioned package under
  `services/data-pipeline/opennutri_core/`; do not load it through the annotator's
  legacy `entities` / `claims` model.
- `scripts/build_core_dataset.py` builds combined USDA Core `v0.2.0` from FNDDS
  2021-2023, Foundation 2025-12-18, SR Legacy 2018-04, and SR28 food descriptions
  into normalized CSV/Parquet, SQLite with FTS5 search, `manifest.json`, and
  `quality_report.json`.
  Local release output is gitignored under `services/data-pipeline/data/core/releases/`.
- The repo source files were compared byte-for-byte with the official USDA archive.
  Strict builds enforce the verified source-tree hash and official row counts.
- Measured combined release: 13,590 foods, 13,537 searchable foods, 246 nutrients,
  1,012,681 nutrient observations, 36,619 portions, and 1,943 SR28
  as-purchased-to-edible factors. Of those factors, 1,937 are usable; 883 usable
  factors apply to raw foods. Six overlapping poultry bone-component records remain
  auditable but unusable.
- FNDDS `food_nutrient.nutrient_id` maps through `nutrient.nutrient_nbr`, not
  `nutrient.id`. Keep this source adapter rule and its regression test intact.
- `services/core-api/` provides API `v0.3.0` over the
  release: `/health`, `/v1/releases/current`, `/v1/foods/search`, and
  `/v1/foods/{food_id}`. It validates the artifact at startup, uses read-only SQLite
  connections, and returns source/quality metadata with nutrients, portions, and
  source-linked weight factors.
- The Flutter diary can log edible grams or, when a usable factor exists,
  as-purchased grams. It stores entered and converted edible weights separately and
  scales all nutrients from edible grams.
- Raw skin-on drumstick FDC `172373` uses a reviewed `0.67` edible fraction. SR28's
  reported `66%` refuse double-counts overlapping 33% bone descriptions; the reviewed
  correction uses sibling raw meat-only record `05071`, which separates 33% bone
  from 9% skin and fat. Preserve both source and corrected values.
- Next product work is the reviewed common-query ranking benchmark and measured
  coverage audit for the as-purchased factors. Never blend nutrient values or copy
  weight factors between merely similar foods silently.

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
- `routing_stage_configs` now orders model stages and stores `fallback_model_names`. `gemma_proof_extraction_v1` is the active entry stage using `gemma-4-31b-it` with `gemma-4-26b-a4b-it` fallback; `gemini_flash_db_payload_v2` is the second extraction stage using stable `gemini-3.5-flash`.

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

- `Queue`: shared available paper list, quiet AI prefill from latest Gemini `has_data` `ai_extractions.normalized_payload_json`, compact Sources strip for table/paragraph/page navigation, draft save, final submit, no-usable-data submit, ask-for-help. Queue papers already have normalized useful AI output and a non-empty `papers.pdf_url` so labelers can open the source PDF; AI `no_usable_data` decisions are provisional skips outside the labeler queue, and AI reasoning or AI-prefill status banners are not shown to labelers. Source navigation maps printed journal page hints to actual PDF pages when header/footer page labels are detectable.
- `Approval`: cockpit-visible; editable only for `can_approve_labels` non-testers. The editable final payload uses the same compact Sources strip so approvers can jump to matched PDF table overlays, expanded paragraph overlays, or page hints.
- `Dashboard`: labeler performance and detailed correction history.
- `Pipeline`: cockpit-only operational view for crawler search, PDF acquisition, the three model stages, and human review. It uses the `get_pipeline_ops_snapshot` RPC to show a simple "Right Now" queue block plus an all-time-by-default funnel with a time filter. The UI labels the cascade by stable role names, with the current model spec in parentheses: `Small model (...)`, `Medium model (...)`, and `Strong model (...)`. Funnel counters are role/stage counters, not model-name counters; historical direct Small -> Strong tasks from before Medium existed are backfilled into Medium-entered and Medium-kept counts.
- `Useful Papers`: useful paper/submission/approval/outcome state plus a `Latest AI` Details affordance for the normalized DB-compliant extraction payload. The cockpit uses `get_cockpit_ai_extractions` for this list so raw model responses are not sent to the browser by default; Details still include normalization summary and the normalized payload. Provisional AI no-data skips are hidden from this default overview.
- `Reviewers`: admin table for active/tester/cockpit/approval flags.
- `Suggestions`: cockpit/admin-only suggestion and general queue help triage.
- `My Suggestions`: regular-labeler view that shows each of their submitted suggestion/help-request statuses; the `Suggest` submit button is hidden for cockpit/admin users.
- Suggestion attachments are previewed from per-file signed storage URLs in both `Suggestions` (cockpit/admin) and `My Suggestions` (regular labeler) views, with an `Open full image` link per attachment.

Frontend validation currently passes with:

- `npm run build`
- `npm run lint` with only pre-existing hook warnings in `App.jsx` and `ResetPassword.jsx`.

## AI Routing

- Active entry stage is `gemma_proof_extraction_v1` with `gemma-4-31b-it` and `gemma-4-26b-a4b-it` fallback; second stage is `gemini_flash_db_payload_v2` with `gemini-3.5-flash`.
- Active shared prompt contract is `opennutri_evidence_payload_v1` for Gemma, Flash-Lite, and final Gemini.
- Upload enqueues `paper_stage_tasks` instead of running models inline.
- AI extraction stores deterministic `normalized_payload_json` using the same top-level contract as human payloads, including DB/custom food identity, raw food name, preparation state, DB/custom nutrient identity, raw nutrient name, value, unit, basis, sample size, confidence, source citation, and row metadata. Evidence metadata now preserves `table_label`, `page_hint`, `source_quote`, `source_location_type`, `section_heading`, and `paragraph_hint` for reviewer PDF navigation.
- The annotator treats that payload as the reviewer-facing AI output: it silently preloads editable queue rows when there is no saved annotation, and cockpit Details shows the normalized payload/normalization summary without model reasoning.
- The AI prompt target is useful OpenNutri food composition data only. Intervention/effect/outcome papers about nutrient doses, supplements, extracts, diets, biomarkers, cells, animals, microbes, health effects, processing outcomes, sensory scores, or similar responses are empty unless they also report useful direct food/product composition tables. One-off treatment/formulation variants are no usable data unless they represent stable real-world foods/products worth adding to the DB.
- `UnifiedEvaluator` accepts requested JSON object output, top-level candidate-row arrays, and nested `food -> nutrients[]` arrays.
- The prompt requires broad evidence locations per extracted row. Shared table-level evidence is preferred for rows from the same table; paragraph/section evidence uses short exact source quotes and metadata hints rather than stored coordinates.
- Prompt should include the full nutrient catalog plus high-signal food candidates matched from the paper text, but not the full food catalog.
- AI-provided DB IDs are verified against current DB rows before acceptance.
- Gemma `has_data` outputs enqueue Gemini with a computed priority from confidence, raw and normalized row counts, table/evidence/per-100g signals, unsupported-unit rows, direct composition language, source quality, and soft penalties for review/database aggregate, feed/digestibility, sensory/outcome, supplement, extract, or one-off formulation signals. Raw-positive normalized-empty Gemma outputs can enqueue Gemini when Gemma returned candidate rows or a clear `has_data` decision; unsupported-unit rows raise screening value but remain rejected by strict final normalization. Gemma/Gemini `no_usable_data` outputs become `ai_provisional_no_usable_data` with `route_destination = provisional_skip`; the stage processor keeps DB routing/audit rows and fetches paper text from the source URL instead of retaining PDFs in Supabase Storage. Retryable 31B timeout/quota/transient/blank SDK failures attempt the configured 26B fallback in the same task; blank exceptions are stored with type, `repr`, and traceback tail. Non-retryable 31B model-configuration failures surface as permanent configuration errors instead of silently looping through the queue. Model runtime initialization now happens before task claiming, so missing API-key/config failures do not leave rows stuck in `processing`. Gemini `has_data` outputs with normalized rows become `human_review_ready`.
- Upload/re-upload preserves closed routing state: papers that already have a closed AI route or human outcome can refresh metadata/search-hit audit rows without being sent back through the active model stage. Concurrent upload workers can race on the same `papers.canonical_key`; uploader duplicate-key recovery should reuse the existing paper row, keep search-hit audit links, and enqueue the active stage only when that row is still open.
- Oversized PDFs are not allowed to abort an ops batch. Crawler v2 treats PDFs above the shared limit as `pdf_fetch` failures before counting them accepted. The shared limit defaults to 50 MiB and can be overridden with `OPENNUTRI_MAX_PAPER_PDF_BYTES` or `SUPABASE_PAPER_MAX_UPLOAD_BYTES`; Supabase Storage 413 handling remains only for explicit legacy paper-Storage runs.
- AI-finalized outcomes use `truth_source_kind = ai_model` and remain excluded from human-truth feedback.
- `process_stage_queue.py` requeues stale `processing` tasks before claiming new work, which lets the next run recover papers left by cancelled GitHub runners or interrupted local workers. Daily ops queue/refill decisions count executable queued `paper_stage_tasks` rows, not paper routing rows alone, so stale historical `queued_for_ai` paper summaries cannot block a same-run refill. Supabase paper-PDF cleanup is legacy opt-in only.
- Crawler batch acquisition respects remaining per-language targets, so one strong search batch should not download far beyond the requested English refill size. Before acquisition, crawler v2 merges local terminal crawl state with live `papers.canonical_key` rows from Supabase so already queued, provisional-skipped, human-ready, or finalized papers are not downloaded again; metadata-only `paper_search_hits` rejects are not global skip memory.

## Ops

`services/data-pipeline/scripts/refill_assignment_queue.py` is retained under the old filename for compatibility. It now:

- reports shared general queue stock;
- excludes papers with final outcomes or pending/accepted general submissions;
- excludes unresolved legacy slot assignments and legacy global no-data rows;
- drains queued Gemma, Flash-Lite, and final Gemini stage tasks before requesting crawler refill;
- triggers English-only crawler refill when visible stock is below `--target-open`.

`services/data-pipeline/scripts/daily_ops_orchestrator.py` treats `--target-open` as compatibility/reporting only. Scheduled ops do not stop when the human queue is full. The workflow now splits the tick into `--controller-only` and `--drain-only` roles: the controller is the single writer/refiller, and workers only claim/drain already-created model tasks.

Daily ops order:

1. Controller skips paper Storage cleanup/soft-limit checks in the scheduled path.
2. Controller requeues stale Gemma, Flash-Lite, and final Gemini `processing` tasks before making refill decisions.
3. Controller counts completed Gemma `paper_stage_tasks` since the configured Gemma quota-day start (default UTC) and completed Flash-Lite/final Gemini tasks since their configured quota-day starts (default `America/Los_Angeles`).
4. Controller counts active Gemma work from `paper_stage_tasks.status IN ('queued', 'processing')`, excluding stale processing rows. Before refill it checks the prior 6 hours; at least 20 failed Gemma tasks with zero completions opens `screening_failure_circuit_open` and skips crawling. Otherwise, if today's completed Gemma count is below 1500 and active Gemma work is below `--screening-active-target 150`, it crawls/registers English papers in 30-paper chunks with `--crawler-max-wallclock-seconds 2400` and `--refill-step-tr 0`. If the crawler wall-clock limit is reached, crawler v2 writes a partial manifest and upload still registers accepted papers from that partial run. The controller also reports the soft downstream reservoir target of 500 candidates but does not evict existing tasks.
5. Workers drain at most `--screening-tick-tasks 20` Gemma tasks each, bounded by the remaining daily Gemma target and queued count. Workers never crawl/upload/refill.
6. Workers in interleaved mode drain Flash-Lite at highest-priority order for at most `--triage-tick-tasks 10`, bounded by `--triage-daily-target 500`, then final Gemini for at most `--extraction-tick-tasks 5`, bounded by the `--extraction-daily-target 250` safety ceiling; assign any new `human_review_ready` papers immediately.
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

The JSON summary reports `mode`, `day_start_utc`, per-stage `quota_day_starts` / `quota_timezones`, completed counts, screened calls, candidates routed to Gemini, Gemini calls used, new human-ready papers, quota-exhausted stages, per-stage windows, and remaining queued candidates.

Feedback refresh is intentionally tied to crawler refill only; queued-AI draining does not refresh feedback. DergiPark refresh/search is skipped unless Turkish is explicitly re-enabled with a positive Turkish target and a DergiPark source list.

## Feedback / Benchmark Boundary

- Feedback learning reads `paper_review_outcomes` first.
- Only `truth_source_kind = human_review` accepted outcomes feed current human-truth feedback.
- Pending and superseded `paper_label_submissions` are excluded from feedback learning.
- Legacy `paper_label_events` / `paper_global_labels` remain fallback only for older papers without resolved outcomes.
- Unapproved submissions are performance/audit data, not benchmark truth.

## Useful Commands

- Build the FNDDS OpenNutri Core release:
  - `python3 services/data-pipeline/scripts/build_core_dataset.py --overwrite`
- Run the local OpenNutri Core API:
  - `cd services/core-api && python3 -m uvicorn opennutri_api.main:app --reload`
- Test the OpenNutri Core API:
  - `cd services/core-api && python3 -m unittest discover -s tests -p 'test_*.py' -v`
- Apply schema migration:
  - `cd apps/expert-annotator && DATABASE_URL=... node run-migration.js`
- Verify live workflow schema:
  - `cd apps/expert-annotator && DATABASE_URL=... node check-workflow-schema.mjs`
- Frontend validation:
  - `cd apps/expert-annotator && npm run build && npm run lint`
- Python tests:
  - `cd services/data-pipeline && python3 -m unittest tests.test_ai_routing tests.test_daily_ops`
- Refresh feedback terms:
  - `python3 services/data-pipeline/food_paper_crawler/feedback/update_terms.py`
- Refill crawler stock:
  - `python3 services/data-pipeline/scripts/ensure_paper_stock.py --threshold 0`
- Drain AI routing queue:
  - `python3 services/data-pipeline/scripts/process_stage_queue.py`
- Run daily ops controller:
  - `OPENNUTRI_STORE_PDFS_IN_SUPABASE=0 python3 services/data-pipeline/scripts/daily_ops_orchestrator.py --json-summary --controller-only --tick-mode --stage-rpm gemma_proof_extraction_v1=20,gemini_flash_lite_triage_v1=20,gemini_flash_db_payload_v2=15 --max-wallclock-minutes 75 --crawler-max-wallclock-seconds 2400 --screening-daily-target 1500 --screening-active-target 150 --screening-failure-window-hours 6 --screening-failure-circuit-min-failures 20 --triage-daily-target 500 --extraction-daily-target 250 --screening-refill-batch-en 30 --screening-refill-chunk-en 30 --screening-prefill-stall-limit 3 --paper-bucket-soft-limit-mb 0 --skip-storage-cleanup --refill-step-tr 0`
- Run one drain worker:
  - `OPENNUTRI_STORE_PDFS_IN_SUPABASE=0 python3 services/data-pipeline/scripts/daily_ops_orchestrator.py --json-summary --drain-only --tick-mode --interleave-extraction --stage-rpm gemma_proof_extraction_v1=20,gemini_flash_lite_triage_v1=20,gemini_flash_db_payload_v2=15 --max-wallclock-minutes 0 --screening-daily-target 1500 --screening-tick-tasks 20 --triage-daily-target 500 --triage-tick-tasks 10 --extraction-daily-target 250 --extraction-tick-tasks 5 --refill-step-tr 0`
- Dry-run historical Gemini candidate recovery:
  - `python3 services/data-pipeline/scripts/recover_gemini_candidates.py --json-summary --limit 200`
- Flash-Lite holdout listing without model calls:
  - `python3 services/data-pipeline/scripts/flash_lite_triage_experiment.py --dry-run --json-summary`
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
- On 2026-05-29, live `routing_stage_configs` was updated and verified so `gemini_flash_db_payload_v2.model_name = 'gemini-3.5-flash'` while `gemma_proof_extraction_v1` remains active with `gemma-4-31b-it` and 26B fallback; `ai_extractions.model_name` default was also altered and verified as `gemini-3.5-flash`. Historical recovery dry-run scanned `3115` Gemma extraction rows plus `3334` failed Gemma tasks, found `190` high-priority raw-positive normalized-empty candidates, and observed `481` queued Gemini tasks against the 500 soft reservoir. The capped apply pass selected all 190, updated 188 queued priorities, and requeued 2 eligible target tasks; verification then showed `483` queued Gemini tasks with max priority `496`. Later the same day, `gemini_flash_lite_triage_v1` was promoted to production between Gemma and final Gemini. A manual 1-worker GitHub Actions run completed successfully and live DB verification showed 10 `gemini-3.1-flash-lite` extractions plus continuing `gemini-3.5-flash` final extractions. After that validation, 460 legacy queued final-Gemini tasks with no triage history were moved back to `gemini_flash_lite_triage_v1`, leaving 488 queued triage tasks and only 8 queued final-Gemini tasks that already have triage history. The Flash-Lite experiment script remains as a regression/quality harness for future triage changes.
- On 2026-05-29, the Pipeline UI was updated for the 3-stage model cascade: current queues and funnel rows now show `Small model (Gemma 31B)`, `Medium model (Gemini 3.1 Flash-Lite)`, and `Strong model (Gemini 3.5 Flash)` from live stage/extraction `model_name` values. Future model swaps should update the parenthesized spec only; the role names stay stable. The `get_pipeline_ops_snapshot` RPC exposes `model_stage_backfill.legacy_direct_strong_without_medium`, and the UI adds that count to Medium entered/kept so pre-Medium Small -> Strong history does not make the Medium stage look reset.

## Still Needs Attention

- L2 classifier training is still deferred until more accepted human-review outcomes exist.
- PDF nutrient-name click highlights remain precision-first/table-only; continuation-page recall and cross-text-item nutrient phrase matching are still future work. Compact AI source strips cover table/paragraph/page navigation separately, map printed page hints when possible, and draw visible overlays for every matched table or paragraph block, clicked or not. Evidence now snaps to whole detected tables or whole paragraph blocks before scaling from PDF.js text-coordinate bounds; sources in the same resolved block share one deduplicated overlay and one source chip instead of drawing overlapping partial boxes or repeated scroll targets. Paragraph matching ignores document chrome such as affiliations, article-history/keyword sidebars, and copyright rows; nutrient word click marks also reject narrative prose after tables. Table detection handles standalone `Table N` labels followed by long caption continuation rows and wide multi-column headers, which covers layouts like the oat germplasm Table 2 page.
