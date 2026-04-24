# OpenNutri Handoff — 2026-04-24 (Europe/Istanbul)

This is the current high-signal project state after the assignment-driven annotator workflow, reviewer-admin cockpit, bilingual queue repair, and staged AI routing implementation landed in code.

**Primary Goal**
- Finish Preliminary Study 3 as fast as possible so the benchmark-quality dataset supports both the TÜBİTAK application and the paper draft.
- Paper stock is intentionally kept low. Refill happens as labeling progresses so each crawl benefits from newer feedback.

**Research / Team Operating Model**
- Arciel: developer, official reviewer slot, project manager, cockpit/conflict resolver.
- Peri: official reviewer slot.
- Aleyna: official reviewer slot.
- Daine: English-only shadow helper inside the Arciel lane; cheap ops help, not a standalone official slot.
- Important implementation caveat:
  Daine only starts receiving queue items once her real reviewer profile is configured in `reviewer_profiles` + `reviewer_slot_members`.

**Workflow Now**
- New ingest gate:
  `crawl -> upload -> AI queue -> routing -> human_review_ready or AI finalization`.
- The active AI stage is `gemini_flash_db_payload_v2`.
- Upload no longer runs Gemini inline. It enqueues `paper_stage_tasks` and sets paper-level routing state instead.
- AI extraction remains blind to human labels. The scored AI artifact is now the deterministic DB-shaped `normalized_payload_json`, not the raw LLM JSON or raw `is_useful` boolean.
- The DB-shaped AI payload uses the same top-level contract as `build_annotation_submission_payload`: `decision_kind`, `food_items[].food_name`, `food_fdc_id`, `is_custom_food`, and `nutrients[].nutrient_id`, `nutrient_name`, `value`, `unit`.
- AI routing/finalization now follows the normalized payload decision. If the model says useful but all rows are rejected as unsupported or non-100g/non-composition data, the paper routes as `no_usable_data`.
- Humans may only be assigned papers whose `papers.routing_status = 'human_review_ready'`.
- High-confidence AI positives and negatives are finalized immediately unless they fall into the deterministic audit sample.
- Low-confidence papers always route to humans for now.
- The shared paper list is gone.
- Every paper is assigned to exactly 2 official reviewer slots:
  `arciel`, `peri`, `aleyna`.
- Users only see their own `paper_user_assignments`.
- Final submissions are frozen as canonical payload snapshots in `paper_assignment_submissions`.
- Exact raw match is based on deterministic payload serialization + `payload_hash`.
- Internal mismatch inside the Arciel lane creates `internal_slot_conflict`.
- Official-slot mismatch creates `external_slot_conflict`.
- Arciel resolves conflicts in the cockpit.
- `Definitely No Data` is now a slot-level global skip:
  one reviewer lane can mark the paper globally unusable, which cancels the other assignments and writes final negative truth immediately.
- Only final resolved paper truth in `paper_review_outcomes` feeds crawler feedback.

**Live Schema Status**
- `apps/expert-annotator/migration.sql` was applied successfully to the live Supabase DB again on April 22, 2026.
- Live verification confirmed these tables exist:
  - `reviewer_profiles`
  - `reviewer_slot_members`
  - `paper_slot_assignments`
  - `paper_user_assignments`
  - `paper_assignment_submissions`
  - `paper_conflicts`
  - `paper_review_outcomes`
- Live verification also confirmed these workflow RPCs exist:
  - `current_user_has_cockpit_access`
  - `current_user_can_write`
  - `current_user_has_cockpit_write_access`
  - `sync_reviewer_profile`
  - `touch_assignment_workspace`
  - `submit_assignment_review`
  - `mark_assignment_global_no_data`
  - `resolve_paper_conflict`
  - `refresh_paper_resolution_state`
  - `upsert_reviewer_admin_config`
- `reviewer_profiles` live verification now also confirms both access flags exist:
  - `tester_access`
  - `cockpit_access`
- Cockpit reads now allow active `cockpit_access` users even when `tester_access=true`.
- Cockpit writes, conflict resolution, suggestion-review status writes, and assignment RPC writes remain blocked for tester accounts through SQL guards.
- Code now also expects these additional routing tables/fields:
  - `routing_stage_configs`
  - `paper_stage_tasks`
  - paper-level routing columns on `papers`
  - AI provenance columns on `ai_extractions`
  - AI/human truth-source columns on `paper_review_outcomes`
- Live migration was applied again on April 24, 2026 for the standardized AI DB-payload stage.
- Live schema verification now confirms `gemini_flash_db_payload_v2` is the only active `routing_stage_configs` row, while `gemini_flash_triage_v1` is preserved inactive for audit.

**Live Data Repair Status**
- On April 22, 2026, `papers.workflow_language IS NULL` was backfilled from `12` to `0` using `services/data-pipeline/scripts/backfill_paper_workflow_language.py`.
- All 12 legacy null-language rows inferred to English during the live repair.
- Immediately after the backfill, available paper stock changed from `EN 0 / TR 0 / unscoped 12` to `EN 12 / TR 0 / unscoped 0`.
- A live bilingual refill then added 12 Turkish papers:
  - cycle 1 accepted/uploaded 11 Turkish PDFs
  - cycle 2 accepted/uploaded 1 Turkish PDF
- Post-refill stock reached the target floor at `EN 12 / TR 10`.

**Frontend Status**
- `apps/expert-annotator/src/pages/Annotate.jsx` is now role-aware:
  - `My Queue`
  - `Cockpit`
  - `Conflicts`
- Mode split is now:
  - normal reviewer mode: real `paper_user_assignments`, live writes
  - generic tester mode: local-only virtual queue
  - developer-training mode (`tester_access && cockpit_access`): local-only admin/annotation/conflict actions plus a virtual bilingual `My Queue`
- Queue saves drafts to the workspace tables, then uses RPC submission for final snapshots.
- Cockpit shows reviewer queue/accuracy summaries, resolved source-yield breakdowns, reviewer-admin controls, and expandable AI details in the cockpit-only `All Papers` screen.
- The AI detail panel shows model decision, confidence, routing bucket, reasoning, normalized DB payload, rejected/custom row counts, raw response metadata, and later human-outcome comparison status.
- Reviewer-admin controls can:
  - create a reviewer profile by email
  - allowlist the reviewer for auth
  - assign or remove an official slot
  - add or remove shadow slot memberships
  - change language permissions, active state, and cockpit access
- Developer-training suggestion submissions still persist to `backlog_review_items`, while suggestion-review status edits remain local-only in training mode.
- Queue view again exposes `Definitely No Data`, now routed through the assignment-safe global-skip RPC.
- Conflicts view compares frozen payload snapshots side by side and lets Arciel choose the winning submission.
- Frontend build currently passes.
- `mcraft160105@gmail.com` and `ayseguldogan2706@gmail.com` are now live read-only developer-training accounts:
  - `tester_access=true`
  - `cockpit_access=true`
  - no official slot membership

**Queue Status**
- Live official open queues now contain both languages:
  - Arciel: `EN 9 / TR 1`
  - Peri: `EN 8 / TR 2`
  - Aleyna: `EN 7 / TR 3`
- `services/data-pipeline/scripts/refill_assignment_queue.py` was executed live on April 22, 2026 and brought every official reviewer lane to `10` open assignments.
- Read-only developer-training queue inspection now reports a 25-paper bilingual pool:
  - 15 live-slot-priority papers
  - 10 paper-pool backlog papers
  - EN and TR are interleaved at the front of the queue when both are present

**Crawler / Feedback Status**
- `update_terms.py` now prefers resolved `paper_review_outcomes`, with legacy label events as fallback only for older papers that have no resolved outcome yet.
- `update_terms.py` now excludes `paper_review_outcomes.truth_source_kind = 'ai_model'` from the current human-truth feedback export.
- `ensure_paper_stock.py` now treats only `papers.routing_status = 'human_review_ready'` papers as available reviewer stock, and drains the AI queue after upload.
- New protected queue job:
  - `services/data-pipeline/scripts/refill_assignment_queue.py`
  - keeps each active reviewer’s personal open backlog at the target level
  - creates slot assignments + user assignments only from `human_review_ready` papers
  - assigns older waiting `human_review_ready` papers first by `routing_updated_at` / creation order
  - reuses cancelled slot/user assignment rows when reset papers return from AI, because live uniqueness constraints are `(paper_id, slot_key)` and `(paper_slot_assignment_id, reviewer_profile_id)`
  - drains queued AI tasks before triggering crawler refill when the human-ready pool is exhausted
- New AI routing ops scripts:
  - `services/data-pipeline/scripts/process_stage_queue.py`
  - `services/data-pipeline/scripts/backfill_ai_routing.py`
  - `process_stage_queue.py` now claims one queued batch per run and returns AI processing errors to `queued_for_ai` with `last_error` instead of routing them to humans
  - `backfill_ai_routing.py --reset-open-human-assignments` is the safe reroute path for existing papers: it refuses submitted/human-truth work, cancels unresolved assignment rows, and queues existing papers for AI without draining by default
- Dry-run check works after a one-pass preview fix.

**What Still Needs Attention**
- Daine’s real email/profile still needs to be entered through the cockpit if she should receive English queue items.
- Peri and Aleyna do not need to log in before the first refill; assignments can be created now and linked to their auth users when they log in later.
- PDF nutrient highlights are now precision-first and table-only:
  the annotator builds a page-local allowlist from PDF.js text content and only highlights detected table body/header cells plus caption/title lines.
  Nearby prose, legends, and ambiguous pages stay unhighlighted, and captionless continuation pages are intentionally suppressed until a safer continuation heuristic exists.
- L2 classifier training is still deferred until more resolved labels exist.

**Useful Commands**
- Apply schema migration:
  - `cd apps/expert-annotator && DATABASE_URL=... node run-migration.js`
- Verify live workflow schema:
  - `cd apps/expert-annotator && DATABASE_URL=... node check-workflow-schema.mjs`
- Refresh feedback terms:
  - `python3 services/data-pipeline/food_paper_crawler/feedback/update_terms.py`
- Backfill legacy paper languages:
  - `python3 services/data-pipeline/scripts/backfill_paper_workflow_language.py [--dry-run]`
- Refill crawler stock:
  - `python3 services/data-pipeline/scripts/ensure_paper_stock.py --threshold 0`
- Drain the AI routing queue:
  - `python3 services/data-pipeline/scripts/process_stage_queue.py`
- Backfill the active AI routing stage:
  - `python3 services/data-pipeline/scripts/backfill_ai_routing.py`
- Reset existing unresolved human assignments back through the active AI gate:
  - `python3 services/data-pipeline/scripts/backfill_ai_routing.py --reset-open-human-assignments`
- Top up reviewer queues:
  - `python3 services/data-pipeline/scripts/refill_assignment_queue.py`
- Inspect the developer-training queue pool:
  - `python3 services/data-pipeline/scripts/seed_training_stock.py [--dry-run]`

**Live Reroute State - April 24, 2026**
- Before the v2 reroute reset, live checks found:
  - `0` assignment submissions
  - `0` human-review outcomes
  - `30` open unsubmitted user/slot assignments
- Existing papers were reset through `backfill_ai_routing.py --reset-open-human-assignments` against Supabase for `gemini_flash_db_payload_v2`.
- The reset queued `25` papers for v2 and cancelled `30` open slot assignments plus `30` open user assignments.
- The v2 AI drain processed one 25-paper batch:
  - `1` paper reached `human_review_ready`
  - `24` papers remain `queued_for_ai` / `blocked` because Gemini returned free-tier quota errors
  - queued v2 papers now have stale old-stage `latest_ai_extraction_id` cleared until a v2 extraction exists
- The single successful v2 extraction stored `normalized_payload_json.decision_kind = no_usable_data`, zero accepted rows, normalization summary metadata, and `papers.latest_ai_extraction_id` points to the v2 extraction row.
- `refill_assignment_queue.py --max-cycles 1` assigned the one available human-ready English paper:
  - Arciel: 1 open EN assignment
  - Peri: 1 open EN assignment
  - Aleyna: 0 open assignments
  - full 10-open backlog refill is blocked until the 24 queued AI papers are retried or new human-ready stock exists
- Verified invariant:
  no open human assignments exist on `queued_for_ai`, `ai_processing`, AI-finalized, or null-routed papers.

**Immediate Next Step**
- After Gemini quota resets, rerun `python3 services/data-pipeline/scripts/process_stage_queue.py --max-tasks 24` to retry the queued v2 AI failures, then run `python3 services/data-pipeline/scripts/refill_assignment_queue.py`.
