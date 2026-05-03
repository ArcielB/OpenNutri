# OpenNutri Reviewer Workflow Map

Last verified: 2026-05-02 against `apps/expert-annotator/src/pages/Annotate.jsx`, `apps/expert-annotator/migration.sql`, `services/data-pipeline/scripts/refill_assignment_queue.py`, `services/data-pipeline/scripts/daily_ops_orchestrator.py`, and `services/data-pipeline/scripts/ensure_paper_stock.py`.

This is the maintained internal map for the active reviewer workflow. The old slot/cross-check workflow remains in historical tables only; do not use it as the source of truth for new work.

## End-to-End Flow

Current live flow:

`crawl -> upload -> AI queue -> routing -> human_review_ready shared queue -> paper_label_submissions -> Arciel approval -> paper_label_approvals -> paper_review_outcomes -> feedback learning`

Important consequences:

- Labelers pull from a shared general queue, not personal slot assignments.
- A paper is visible in the queue only while it is `human_review_ready`, unresolved, and has no pending/accepted general submission.
- Queue eligibility also requires a latest AI extraction whose normalized payload has a DB-compliant decision. Both `has_data` and `no_usable_data` AI decisions are labeler work while thresholds require human validation; only above-threshold AI outcomes bypass humans.
- Submitting creates an immutable `paper_label_submissions` row and removes the paper from the visible queue on refresh.
- Drafts do not claim a paper. If two labelers already have a paper open, both can submit before final approval; all submissions are retained for audit/performance.
- Arciel's own submission auto-accepts. Other labelers' submissions wait for approval.
- Final human truth is only `paper_review_outcomes`.

## Roles

- **General labeler**: active non-tester reviewer profile. Sees the shared Queue, can save drafts, submit usable-data or no-usable-data labels, and ask for help.
- **Approver**: reviewer profile with `can_approve_labels = true`. Currently Arciel only. Can approve/edit pending submissions and write final human truth.
- **Cockpit/tester/developer viewer**: `cockpit_access = true`, often with `tester_access = true`. Can inspect Approval, Dashboard, Suggestions, and All Papers, but tester accounts cannot mutate because SQL write guards call `current_user_can_write()`.

Legacy concepts:

- `reviewer_slots`, `reviewer_slot_members`, `paper_slot_assignments`, `paper_user_assignments`, `paper_assignment_submissions`, and `paper_conflicts` are preserved for old audit data.
- New work must not create slot/user assignments.

## Key Tables And RPCs

Active workflow tables:

- `reviewer_profiles`
  - `tester_access`: read-only account.
  - `cockpit_access`: can inspect cockpit/dashboard surfaces.
  - `can_approve_labels`: can approve final labels; currently Arciel.
- `paper_label_submissions`
  - Immutable labeler payload snapshot.
  - Stores submitter profile/auth user, annotation id, decision, `payload_json`, `payload_text`, `payload_hash`, and status.
  - Status values: `pending_approval`, `accepted`, `superseded`.
- `paper_label_approvals`
  - One accepted approval per paper.
  - Stores original submission id, approver profile/auth user, accepted/corrected payload, `correction_diff_json`, note, and timestamp.
- `paper_review_outcomes`
  - Final paper truth row.
  - New general workflow uses `resolution_source = reviewer_direct_submit | reviewer_approval`.
  - Links back through `label_submission_id` and `label_approval_id`.

Core RPCs:

- `sync_reviewer_profile()`: links auth users to reviewer profiles.
- `get_general_queue_papers(p_limit)`: security-definer queue query that returns only available shared-queue papers.
- `submit_general_label(p_annotation_id, p_decision_kind, p_submission_metadata)`: freezes a labeler payload. If the caller can approve labels, it also creates approval and final outcome.
- `approve_label_submission(p_label_submission_id, p_approval_annotation_id, p_decision_kind, p_approval_note)`: approver-only finalization. It preserves the original labeler payload, stores the corrected reviewer payload, supersedes other pending submissions for the paper, and writes `paper_review_outcomes`.
- `build_label_payload_diff(original, final)`: deterministic correction summary used for dashboard mistake detail.

## UI Behavior

### Queue

- The Queue calls `get_general_queue_papers()`.
- Labelers only see available papers and their own draft content.
- Labelers do not see other labeler names, submission counts, or approval status.
- Every visible queue paper must already have a latest AI extraction with normalized output. If a paper has no saved annotation, the form initializes from that `ai_extractions.normalized_payload_json`: `has_data` decisions preload editable DB-compliant food/nutrient rows, and `no_usable_data` decisions preload an empty review state. AI reasoning is not shown in the labeling queue.
- `Save Draft` writes only the user's annotation/food/nutrient rows.
- `Submit Final Extraction` or `No Usable Data` writes annotation rows, inserts a `paper_label_events` audit row, then calls `submit_general_label()`.
- `Ask for Help` inserts a `backlog_review_items` row with `context.request_kind = general_queue_help_request`.

### Approval

- Visible to cockpit/approver accounts; write buttons are enabled only when `can_approve_labels = true` and the account is not a tester.
- Shows pending `paper_label_submissions` with PDF, original submitter payload, and editable final reviewer payload.
- Arciel can approve as-is or edit before approval; both paths call `approve_label_submission()`.
- The original submission is never overwritten.
- Other pending submissions for that paper become `superseded` after final approval.

### Dashboard

- Built from `paper_label_submissions`, `paper_label_approvals`, and `paper_review_outcomes`.
- Summarizes submitted, pending, accepted, corrected, superseded, and correction-item counts per labeler.
- Detail rows show the original decision/payload count, final decision/payload count, correction count, decision changes, and approval notes.

### All Papers

- Cockpit viewers can inspect the latest AI extraction for each paper from the `Latest AI` column.
- The `Details` affordance must show the normalized DB-compliant AI payload and normalization row summary. Do not replace it with raw model reasoning or hide the extracted rows.

## Truth And Feedback Rules

- Human truth is final only after an approver-created or approver-direct `paper_review_outcomes` row exists.
- Pending and superseded submissions are audit/performance data only; they must not feed crawler feedback.
- AI-finalized outcomes keep `truth_source_kind = ai_model` and remain excluded from human-truth feedback learning.
- Exact payload comparison uses deterministic canonical JSON and SHA-256 hashes.
- Correction detail compares the submitted payload against the accepted reviewer payload via `correction_diff_json`.

## Ops

`services/data-pipeline/scripts/refill_assignment_queue.py` is retained under its old filename for compatibility, but it no longer creates assignments.

Shared-stock logic:

- Available stock is `papers.routing_status = human_review_ready`.
- Available stock requires `papers.latest_ai_extraction_id` to point to an AI extraction with normalized `decision_kind IN ('has_data', 'no_usable_data')`.
- Supported languages are English and Turkish.
- Exclude papers with final `paper_review_outcomes`.
- Exclude papers with `paper_label_submissions.status IN ('pending_approval', 'accepted')`.
- Exclude legacy unresolved slot assignments and legacy global no-data labels.
- Default target is 50 visible shared-queue papers, split roughly EN/TR.

Daily ops:

- `daily_ops_orchestrator.py` maximizes daily Gemini usage instead of stopping on shared queue stock.
- It drains queued AI first, crawls/uploads when no queued AI work is available, then processes the new AI queue.
- GitHub Actions starts at `00:05` America/Los_Angeles and loops every 5 minutes until 20 Gemini calls are used, the first AI task is quota-limited, or a crawl/AI pass produces no useful work.
- Feedback refresh happens only when crawler refill is reached, not for queued-AI draining.

## Operational Invariants

- New user-facing work must use `paper_label_submissions` / `paper_label_approvals`, not slot/user assignment rows.
- Never overwrite a labeler's original submission payload.
- Tester accounts must remain read-only even when they can see cockpit/approval pages.
- Only accepted `paper_review_outcomes.truth_source_kind = human_review` rows feed current feedback learning.
- Keep AI prefill payloads DB-aligned: custom foods/nutrients must be explicit, and row context such as raw names, basis, confidence, source citation, and metadata belongs in the canonical payload hash.
- Keep the AI prompt focused on direct food composition extraction. Effect/intervention/outcome papers are empty unless they contain direct food composition tables.
