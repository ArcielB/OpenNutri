# OpenNutri Reviewer Workflow Map

Last verified: 2026-04-29 against `apps/expert-annotator/src/pages/Annotate.jsx`, `apps/expert-annotator/migration.sql`, `services/data-pipeline/scripts/process_stage_queue.py`, `services/data-pipeline/scripts/refill_assignment_queue.py`, `services/data-pipeline/ai_routing.py`, and `services/data-pipeline/food_paper_crawler/feedback/update_terms.py`.

This file is the maintained internal map for the reviewer workflow. Future reviewer docs should update this file instead of re-deriving the flow from scratch.

## End-to-end pipeline

Current live flow:

`crawl -> upload -> AI queue -> routing -> human_review_ready or AI-finalized outcome -> refill_assignment_queue -> paper_slot_assignments / paper_user_assignments -> reviewer UI -> paper_assignment_submissions -> conflict/global-skip resolution -> paper_review_outcomes -> feedback learning`

Important consequences:

- Reviewers never pull from a shared global paper list.
- Human assignment creation is gated on `papers.routing_status = 'human_review_ready'`.
- Final human truth is decided from exact canonical payload snapshots, not free-form reviewer notes.

## Account and reviewer modes

### Official reviewer

- Backed by `reviewer_profiles` plus an active `reviewer_slot_members` row with `member_role = 'primary'`.
- Non-tester accounts can write because `current_user_can_write()` returns `NOT current_user_is_tester()`.
- The current official slots are fixed in `reviewer_slots`:
  - `arciel`
  - `peri`
  - `aleyna`

### Independent full-coverage labeler

- `ayseguldogann99@gmail.com` is Aysegul, not Aleyna.
- Source schema models Aysegul with the non-official `aysegul` lane.
- `refill_assignment_queue.py` attaches the `aysegul` lane to each newly assigned paper in addition to the two official slots.
- The `aysegul` lane is excluded from the two-official-slot truth calculation; her work is independent review signal, not a substitute for Aleyna.
- `Definitely No Data` is limited to official reviewer lanes. Non-official lanes should use normal no-usable-data submission or `Ask for Help`.

### Shadow member

- Backed by `reviewer_slot_members.member_role = 'shadow'`.
- Shadow members receive `paper_user_assignments` for the slot when their language flags allow it.
- They do **not** count toward official slot membership because `counts_toward_official = false`.
- Shadow members do not receive the destructive `Definitely No Data` UI action, and `mark_assignment_global_no_data()` rejects shadow assignments. If they are unsure or the paper is confusing, they use `Ask for Help`, which keeps the assignment open and creates a cockpit review item.
- If a slot has multiple non-cancelled members and their latest submission hashes differ, `refresh_paper_resolution_state()` opens an `internal_slot_conflict`.
- When all members in a slot agree, the slot's `official_submission_id` prefers the primary member's latest submission.

Current shadow roster:

- `dainesalazarromero@gmail.com` (`Daine`) is an English-only shadow member of the `arciel` slot. She receives every English paper assigned to Arciel, but not Arciel's Turkish papers.

### Tester

- `reviewer_profiles.tester_access = true`.
- Always read-only because `current_user_can_write()` becomes false.
- In the UI, tester accounts are forced into local test mode.
- Non-cockpit testers get a virtual queue built from `papers.routing_status = 'human_review_ready'`, not real assignment rows.

### Developer training mode

- `tester_access = true` and `cockpit_access = true`.
- Read-only for annotation, admin, and conflict actions.
- Queue is virtual and bilingual, built from all `en`/`tr` papers plus representative live slot assignment state.
- Live slot assignments are prioritized in that training queue, but all actions stay local-only except suggestion submission.

## Queue population logic

The protected ops entry point is `services/data-pipeline/scripts/refill_assignment_queue.py`.

### Inputs and eligibility

`available_papers()` only returns papers that satisfy all of these:

- `papers.routing_status = 'human_review_ready'`
- `papers.workflow_language IN ('en', 'tr')`
- no unresolved `paper_slot_assignments` on the paper
- no existing `paper_review_outcomes` row on the paper
- no `paper_global_labels.label = 'definitely_no_data'` on the paper

This means queue stock is strictly "human-ready and not already resolved or blocked."

### Which reviewers count toward deficits

- Only active non-tester reviewer profiles inside active `reviewer_slot_members` rows are targetable.
- Deficits are computed from open personal backlog only.
- Open personal backlog means `paper_user_assignments.status IN ('assigned', 'draft')`.
- Default target is 50 open assignments per active reviewer profile.

### Slot-pair selection

Each paper is assigned to exactly two official slots, chosen from:

- `('arciel', 'peri')`
- `('arciel', 'aleyna')`
- `('peri', 'aleyna')`

`choose_slot_pair()` is soft-scored, not hard-coded:

- English gets a preference bonus whenever the pair includes `arciel`.
- Turkish gets a preference bonus for the `peri` + `aleyna` pair.
- Higher current slot load increases penalty.
- Assignments that help more reviewer deficits get a strong reward.
- Overflow beyond a reviewer's target open backlog adds penalty.

After the two official slots are selected, the non-official `aysegul` lane is added to the same paper when its active profile can review that paper's language.

### Row creation and reuse

For each selected paper:

- `paper_slot_assignments` rows are inserted or reset to `status = 'pending'`.
- `paper_user_assignments` rows are inserted or reset to `status = 'assigned'` for every active eligible slot member, including shadows.
- `auth_user_id` may stay null until first login.
- Cancelled rows are reused when a paper later returns from AI routing, because uniqueness is enforced on `(paper_id, slot_key)` and `(paper_slot_assignment_id, reviewer_profile_id)`.

### When stock is empty

The script does **not** stop at "no human-ready papers."

Safe top-up order:

1. Assign existing `human_review_ready` stock.
2. If deficits remain and queued AI work exists, run `process_stage_queue.py` first.
3. If deficits still remain, run `ensure_paper_stock.py` to crawl/upload more papers.
4. Repeat until satisfied or cycle limit is hit.

This is why reviewer queue filling is tightly coupled to AI routing and crawler refill.

## AI routing and human handoff

The AI queue entry point is `services/data-pipeline/scripts/process_stage_queue.py`.

### Task claiming

- Tasks live in `paper_stage_tasks`.
- `claim_paper_stage_tasks()` is service-role only.
- Claim order is retry-fair:
  - lower `attempt_count`
  - then higher `priority`
  - then older `created_at`
  - then lower `id`

This avoids one repeatedly failing paper monopolizing automation.

### What routing stores

For each paper, AI routing:

- extracts PDF text
- runs `UnifiedEvaluator`
- normalizes the result into DB-shaped `normalized_payload_json`
- inserts `ai_extractions`
- updates paper-level routing summary fields
- either finalizes a high-confidence AI outcome or releases the paper to `human_review_ready`

Relevant tables:

- `routing_stage_configs`: active stage, thresholds, audit rate
- `paper_stage_tasks`: queued/processing/completed AI work
- `ai_extractions`: raw AI output plus normalized payload and routing provenance

`UnifiedEvaluator` receives the full `master_nutrients` catalog in the prompt so it can emit exact nutrient IDs and standard names when confident. It does **not** receive the full food catalog; food IDs are enforced deterministically after extraction from the DB reference lookup, with optional prompt-side food candidates reserved for future high-signal narrowing.

### Normalization contract

`services/data-pipeline/ai_routing.py` normalizes AI rows into the same logical payload contract used by human submissions:

- `decision_kind`
- `food_items[].food_name`
- `food_items[].food_fdc_id`
- `food_items[].is_custom_food`
- `food_items[].nutrients[].nutrient_id`
- `food_items[].nutrients[].nutrient_name`
- `food_items[].nutrients[].value`
- `food_items[].nutrients[].unit`

Supported normalized units are:

- `g/100g`
- `mg/100g`
- `μg/100g`
- `kcal/100g`
- `kJ/100g`
- `IU/100g`
- `%`

Unsupported rows are dropped before routing. If every candidate row is dropped, the normalized payload becomes:

- `decision_kind = no_usable_data`
- `food_items = []`

The normalizer accepts an AI-provided food or nutrient DB ID only when that ID exists in the fetched reference rows and the row name exactly matches the canonical/standard name or configured aliases. Stale or mismatched IDs are ignored and the normalizer falls back to exact/alias name matching, then custom rows. Raw paper names, source citations, confidence scores, and candidate DB IDs stay in `ai_extractions.raw_data`; they do not enter `normalized_payload_json`.

### AI outcomes versus human truth

- High-confidence AI finalization writes `paper_review_outcomes` with `resolution_source = 'ai_high_confidence'` and `truth_source_kind = 'ai_model'`.
- Human review-ready papers do **not** get a resolved outcome yet.
- Current feedback export excludes `truth_source_kind = 'ai_model'`.

## Reviewer UI data flow

The main frontend surface is `apps/expert-annotator/src/pages/Annotate.jsx`.

### Bootstrap and queue loading

On load, the app calls `sync_reviewer_profile()`.

`sync_reviewer_profile()`:

- requires authenticated email
- inserts or updates a `reviewer_profiles` row by email
- backfills `reviewer_profiles.auth_user_id`
- backfills `paper_user_assignments.auth_user_id` for that reviewer profile

This is what lets Peri and Aleyna receive assignments before first login.

Queue loading then splits by mode:

- normal reviewer:
  - select from `paper_user_assignments` where `reviewer_profile_id = current profile`
  - fetch linked `papers`, `paper_slot_assignments`, `paper_review_outcomes`, and latest `ai_extractions`
- tester:
  - build a virtual queue from `human_review_ready` papers and attach latest `ai_extractions`
- developer training:
  - build a virtual bilingual queue from papers plus representative live slot assignments and attach latest `ai_extractions`

When an editable assignment has no saved annotation/draft, the edit form initializes from the latest AI `normalized_payload_json`. If the AI payload is `no_usable_data`, the form stays blank but the AI extraction ID is still tracked as the initialization source. Existing drafts, submitted annotations, resolved/cancelled assignments, and any paper/user annotation rows are never overwritten by AI prefill.

The normal labeler queue shows only compact AI-prefill badges: loaded/available status, AI decision, accepted/rejected row counts, and matched/custom food/nutrient counts. AI reasoning and raw response details remain in cockpit/developer audit views.

### Worker-facing live actions

Normal live save flow:

1. Upsert `annotations`.
2. Replace `food_items`.
3. Replace `annotation_nutrient_values`.
4. Insert `paper_label_events`.
5. Call an assignment RPC:
   - `touch_assignment_workspace()` for drafts
   - `submit_assignment_review()` for final submit

Final submissions that began from AI prefill pass `submission_metadata.initialized_from_ai_extraction_id` to `submit_assignment_review()`. That metadata is outside the canonical payload, so reviewer edits alone determine `payload_json`, `payload_text`, and `payload_hash`.

Help request flow:

1. Labeler clicks `Ask for Help` and enters a short note.
2. UI inserts a `backlog_review_items` row with `item_kind = 'suggestion_review'` and `context.request_kind = 'assignment_help_request'`.
3. Context stores paper ID/title, assignment ID, slot, member role, workflow language, latest AI extraction ID, and any valid draft food rows.
4. UI calls `touch_assignment_workspace(..., p_status = 'draft')` so the assignment remains open but visibly started.
5. Cockpit users triage the request from the Suggestions review queue.

Global negative flow:

1. Call `mark_assignment_global_no_data()`.
2. RPC writes the global label, cancels related assignments, and writes final negative truth.

Cockpit conflict flow:

1. Cockpit user picks one side in `Conflicts`.
2. UI calls `resolve_paper_conflict()`.
3. RPC marks the conflict resolved and re-runs `refresh_paper_resolution_state()`.

### Editability rules

In the UI, only `assigned` and `draft` are editable.

Server-side guards match that intent:

- `submit_assignment_review()` rejects `resolved` and `cancelled`
- `mark_assignment_global_no_data()` rejects `resolved` and `cancelled`
- `touch_assignment_workspace()` preserves final statuses instead of reopening them

Resolved or cancelled assignments are inspectable but not writable.

## Key tables and their roles

### Reviewer identity and membership

- `reviewer_profiles`
  - one row per reviewer account identity
  - language flags
  - `tester_access`
  - `cockpit_access`
  - `official_slot`
- `reviewer_slot_members`
  - actual slot membership rows
  - `member_role = primary | shadow`
  - per-language eligibility flags
  - `counts_toward_official`

### Queue and submission state

- `paper_slot_assignments`
  - one paper-to-slot row
  - slot-level status:
    - `pending`
    - `submitted`
    - `conflict`
    - `resolved`
    - `cancelled`
  - stores the slot's chosen `official_submission_id`
- `paper_user_assignments`
  - one paper-to-reviewer row
  - personal queue item shown in `My Queue`
  - statuses:
    - `assigned`
    - `draft`
    - `submitted`
    - `conflict`
    - `resolved`
    - `cancelled`
- `paper_assignment_submissions`
  - immutable final payload snapshots per reviewer submission
  - stores `payload_json`, `payload_text`, and `payload_hash`

### Conflict and truth state

- `paper_conflicts`
  - open/resolved/cancelled internal or external disagreements
  - `internal_slot_conflict` means disagreement inside one slot
  - `external_slot_conflict` means disagreement between the two official slots
- `paper_review_outcomes`
  - single resolved paper truth row
  - stores final payload, hash, resolution source, truth source kind, and provenance

### Routing and AI state

- `routing_stage_configs`
  - stage config and active thresholds
- `paper_stage_tasks`
  - per-paper AI queue tasks
- `ai_extractions`
  - AI raw response plus normalized payload and routing metadata

## Truth-generation rules

### Canonical payload building

Human final submissions are canonicalized in SQL by `build_annotation_submission_payload()`:

- whitespace is normalized via `normalize_submission_text()`
- nutrient values are rounded to 6 decimals
- nutrients inside each food are sorted by:
  - `nutrient_id`
  - normalized nutrient name
  - normalized unit
  - rounded value
  - row id
- foods are sorted by:
  - normalized food name
  - `food_fdc_id`
  - `is_custom_food`
  - row id

`submit_assignment_review()` then stores:

- `payload_json`
- `payload_text = payload_json::text`
- `payload_hash = sha256(payload_text)`

The AI normalizer in `ai_routing.py` mirrors the same ordering and rounding contract so human and AI payloads can be compared directly.
AI prefill metadata is stored only in `paper_assignment_submissions.submission_metadata`; it is not part of the canonical `payload_hash`.

### Internal slot agreement

Inside each slot, `refresh_paper_resolution_state()` checks all non-cancelled member assignments:

- if not all slot members have submitted, slot stays `pending`
- if all latest submission hashes match, slot becomes `submitted`
- if hashes differ, slot becomes `conflict` and an `internal_slot_conflict` is opened or refreshed
- if a resolved internal conflict exists for the same submission pair, that chosen submission becomes the slot's `official_submission_id`

### Official slot agreement

After both official slots have an `official_submission_id`:

- if the two official submission hashes match, `paper_review_outcomes` is written with:
  - `resolution_source = 'slot_agreement'`
  - `truth_source_kind = 'human_review'`
- if the hashes differ, both slots become `conflict` and an `external_slot_conflict` is opened or refreshed
- if that external conflict was manually resolved, the winning submission is written as:
  - `resolution_source = 'conflict_resolution'`
  - `truth_source_kind = 'human_review'`

### Global skip

`mark_assignment_global_no_data()` is stronger than a normal negative submit:

- requires a non-empty reason
- inserts `paper_global_labels(label = 'definitely_no_data')`
- cancels open conflicts on the paper
- cancels all non-cancelled slot assignments
- cancels all non-cancelled user assignments
- writes `paper_review_outcomes` with:
  - `decision_kind = 'no_usable_data'`
  - `resolution_source = 'global_skip'`
  - `truth_source_kind = 'human_review'`

### Exact agreement rule

Agreement is **not** subjective. It is exact payload equality through deterministic serialization and `payload_hash`.

The UI's reviewer-accuracy summary also compares `paper_assignment_submissions.payload_hash` against `paper_review_outcomes.payload_hash`.

## Operational invariants

- Only `human_review_ready` papers may be assigned to humans.
  - enforced by `enforce_human_review_ready_assignment()` triggers on both assignment tables
- Reviewers work from `paper_user_assignments`, not from a global paper list.
- Official resolved truth uses only `reviewer_slots.is_official = true` lanes; the `aysegul` independent lane does not decide `paper_review_outcomes`.
- Drafts stay editable; resolved/cancelled assignments do not.
- Tester accounts are read-only.
- Cockpit writes require both `cockpit_access` and non-tester status.
- Unresolved disagreements do not create resolved truth.
- Current feedback export uses human truth only.
- `paper_review_outcomes.truth_source_kind = 'ai_model'` is preserved for provenance but excluded from the current human-truth feedback learning path.

## Feedback-learning boundary

`services/data-pipeline/food_paper_crawler/feedback/update_terms.py` now builds labels from:

1. `paper_review_outcomes` with `truth_source_kind = 'human_review'`
2. legacy `paper_label_events` / `paper_global_labels` only for older unresolved papers without a resolved assignment outcome

This means:

- resolved human truth feeds learning
- unresolved reviewer conflicts do not
- AI-finalized outcomes do not

That boundary is important for benchmark validity. Do not weaken it casually.
