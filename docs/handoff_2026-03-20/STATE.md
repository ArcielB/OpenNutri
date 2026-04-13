# OpenNutri Handoff — 2026-04-14 (Europe/Istanbul)

This is the current high-signal project state after the assignment-driven annotator workflow and reviewer-admin cockpit landed.

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
- Only final resolved paper truth in `paper_review_outcomes` feeds crawler feedback.

**Live Schema Status**
- `apps/expert-annotator/migration.sql` was applied successfully to the live Supabase DB again on April 14, 2026 for reviewer-admin support.
- Live verification confirmed these tables exist:
  - `reviewer_profiles`
  - `reviewer_slot_members`
  - `paper_slot_assignments`
  - `paper_user_assignments`
  - `paper_assignment_submissions`
  - `paper_conflicts`
  - `paper_review_outcomes`
- Live verification also confirmed these workflow RPCs exist:
  - `sync_reviewer_profile`
  - `touch_assignment_workspace`
  - `submit_assignment_review`
  - `resolve_paper_conflict`
  - `refresh_paper_resolution_state`
  - `upsert_reviewer_admin_config`

**Frontend Status**
- `apps/expert-annotator/src/pages/Annotate.jsx` is now role-aware:
  - `My Queue`
  - `Cockpit`
  - `Conflicts`
- Queue saves drafts to the workspace tables, then uses RPC submission for final snapshots.
- Cockpit shows reviewer queue/accuracy summaries, resolved source-yield breakdowns, and reviewer-admin controls.
- Reviewer-admin controls can:
  - create a reviewer profile by email
  - allowlist the reviewer for auth
  - assign or remove an official slot
  - add or remove shadow slot memberships
  - change language permissions, active state, and cockpit access
- Conflicts view compares frozen payload snapshots side by side and lets Arciel choose the winning submission.
- Frontend build currently passes.

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
- The queue refill job has only been dry-run validated so far; it has not yet been executed live to write assignments.
- The current UI still carries existing PDF-highlighting limitations.
- L2 classifier training is still deferred until more resolved labels exist.

**Useful Commands**
- Apply schema migration:
  - `cd apps/expert-annotator && DATABASE_URL=... node run-migration.js`
- Verify live workflow schema:
  - `cd apps/expert-annotator && DATABASE_URL=... node check-workflow-schema.mjs`
- Refresh feedback terms:
  - `python3 services/data-pipeline/food_paper_crawler/feedback/update_terms.py`
- Refill crawler stock:
  - `python3 services/data-pipeline/scripts/ensure_paper_stock.py --threshold 0`
- Top up reviewer queues:
  - `python3 services/data-pipeline/scripts/refill_assignment_queue.py`

**Immediate Next Step**
- Open the cockpit reviewer-admin section and configure Daine’s reviewer profile if her email is known.
- Then run the queue top-up job live so Peri, Aleyna, and Arciel start from personal assigned backlogs instead of the old shared-paper assumption.
