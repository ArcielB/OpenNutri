# OpenNutri Handoff — 2026-04-22 (Europe/Istanbul)

This is the current high-signal project state after the assignment-driven annotator workflow, reviewer-admin cockpit, and bilingual queue repair landed.

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
- Cockpit shows reviewer queue/accuracy summaries, resolved source-yield breakdowns, and reviewer-admin controls.
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
- `ensure_paper_stock.py` now treats already-assigned or already-resolved papers as unavailable stock.
- New protected queue job:
  - `services/data-pipeline/scripts/refill_assignment_queue.py`
  - keeps each active reviewer’s personal open backlog at the target level
  - creates slot assignments + user assignments
  - triggers stock refill when the unassigned queue is exhausted
- Dry-run check works after a one-pass preview fix.

**What Still Needs Attention**
- Daine’s real email/profile still needs to be entered through the cockpit if she should receive English queue items.
- Peri and Aleyna do not need to log in before the first refill; assignments can be created now and linked to their auth users when they log in later.
- The current UI still carries existing PDF-highlighting limitations.
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
- Top up reviewer queues:
  - `python3 services/data-pipeline/scripts/refill_assignment_queue.py`
- Inspect the developer-training queue pool:
  - `python3 services/data-pipeline/scripts/seed_training_stock.py [--dry-run]`

**Immediate Next Step**
- Open the cockpit reviewer-admin section and configure Daine’s reviewer profile if her email is known.
- Then keep consuming the assignment queues and rerun `ensure_paper_stock.py` plus `refill_assignment_queue.py` as stock drops, instead of returning to the old shared-paper assumption.
