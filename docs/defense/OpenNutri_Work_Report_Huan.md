# OpenNutri — Work Report: Duc Huan Ngo (221229075)

*Self-contained account of Huan's contributions to OpenNutri. Companion to the master report; numbers re-derived from git on 2026-06-05, HEAD `ac8bf72`.*

## At a glance

- **23 commits** under the `landeryt` identity, **2026-03-16 → 2026-05-20**.
- **+2,188 / −582 lines** (net **+1,606**), excluding generated artifacts.
- **Attribution rule:** every `landeryt` commit is credited to Huan in full, whether it touched React, SQL, RLS, or Storage. Huan's hallmark is **full-stack features** — most of his work spans the UI, a database table, its RLS policies, and (for suggestions) a Storage bucket. Line counts undersell this: a correct private-bucket RLS policy is a handful of lines but a security-sensitive design decision.

Huan owns four user-facing features plus several UX/auth refinements. Each is described below with what it is, why it was needed, how it works, what made it non-trivial, and when it landed.

---

## 1. Suggestions system — Huan's flagship feature
**Commits:** `2fcdc55`, `81d96af`, `4db6334`, `bd29ab5`, `0a5fdd6`, `967c927`, `8dc6771`, `528848c`, `ebe2a3d` — 2026-04-21 → 04-25. Largest single commit: image attachments `0a5fdd6` (+445/−4).

- **What:** an end-to-end feedback channel inside the annotator. Regular labelers submit suggestions from a `Suggest` button and follow their status in a `My Suggestions` view; cockpit/admin users triage every incoming suggestion (and help request) in a cockpit `Suggestions` tab. Suggestions can carry **image attachments**.
- **Why:** labelers kept hitting confusing papers and edge cases with no structured way to report them; the supervisor explicitly asked for this. It turns ad-hoc complaints into a reviewable queue.
- **How it works (full stack):**
  - **Frontend:** `SuggestionModal.jsx` for submission, `SuggestionsReviewView.jsx` (cockpit triage), `MySuggestionsView.jsx` (labeler tracking), `SuggestionAttachmentsCell.jsx` (83 lines) for image preview. Images open from **signed Storage URLs at view time**, so private files are never exposed by a public link.
  - **Backend (Huan's SQL):** the **`backlog_review_items`** table for the review queue, with role-based read/write RLS keyed on `current_user_has_cockpit_access()`; attachment metadata stored in `backlog_review_items.attachments`.
  - **Storage (Huan's SQL):** a **private `suggestion-attachments` bucket** with a 10 MiB size cap, an image-MIME allowlist, and **four `storage.objects` policies** (view/upload/update/delete) that use `storage.foldername(name)` to enforce **per-user folder containment**.
- **What made it hard:** the security boundary. Getting private-bucket RLS right — so a labeler can upload and see *their own* images, cockpit can see all, and nobody can read someone else's files — is exact, security-sensitive work where a wrong predicate silently leaks data. The role-split (`967c927`) also had to hide the `Suggest` button from admins while giving them the triage list, without breaking either path.
- **Closure:** Huan closed the whole feature in `ebe2a3d` ("suggestion section fully finished").

---

## 2. Conflicts system — table, view, and UI
**Commits:** `a979d3f` (schema), `f54f2fb`, `2121663` (UI + CSS) — 2026-04-27.

- **What:** a way to resolve disagreements when two labelers produced different labels for the same paper — a `paper_conflict_resolutions` table plus a `paper_conflict_candidates` SQL **view** (joining the assignment/submission tables), surfaced in `Annotate.jsx` with a "Choose This" picker.
- **Why:** under the original slot-assignment model, two reviewers could disagree and there was no resolution path.
- **How:** the view computed candidate conflicts from existing assignment data; the UI let an admin pick the correct version; CSS fixes (`2121663`) kept names readable without obscuring the "Choose This" button.
- **Honest note (shows maturity, not a defect):** this feature was later **superseded** by Arciel's general approval queue (`fc67b30`, 2026-05-02), which replaced slot assignments wholesale. Huan's conflict tables remain in the schema as legacy audit history. Being replaced by a later architecture is normal evolution — the feature shipped and worked for the model that existed at the time.

---

## 3. Reset-password page
**Commit:** `4e208a5` — 2026-03-19 (+175/−1).

- **What:** `src/pages/ResetPassword.jsx` (145 lines today) + routing in `App.jsx`.
- **Why / the bug it fixed:** Supabase's recovery email link previously **silently logged the user straight in** instead of letting them set a new password — a real auth-UX defect. Huan routed the recovery link to a dedicated "set a new password" page.
- **How:** detects the recovery session on landing and renders the password-set form instead of the normal authenticated app.

---

## 4. Fuzzy match utility
**Commit:** `e3971b2` — 2026-05-09 (+203/−100). Closed backlog §8 (and the dependent §9).

- **What:** `src/utils/fuzzyMatch.js` (162 lines), integrated into `FoodAutocomplete` and `NutrientAutocomplete`.
- **Why:** exact-string autocomplete misses near-matches (typos, spacing, accents), which slows labeling.
- **How:** approximate string scoring so the autocomplete ranks close matches, not just prefix hits.

---

## 5. Infinite PDF scrolling
**Commit:** `4ade833` — 2026-04-26 (+108/−74). Closed the old backlog §10.

- **What:** replaced the previous/next page buttons in `PdfViewer.jsx` with **continuous scrolling**.
- **Why:** paging through a multi-page paper one click at a time is slow and loses context.
- **What made it non-trivial:** the change had to reach into `PdfTextScanner.js` so that **highlight matching stayed correct across scrolled pages** — the highlight layer assumed discrete pages, so continuous scroll required keeping page-local matching consistent as pages stream in.

---

## 6. Theme system + auth/UX refinements
- **Theme centralization** — `cbf61ad`, `341b40e` (2026-03-16): lifted theme state into `App.jsx` so the login screen and the app share one source; theme **follows the OS/browser preference when no explicit override exists**; fixed the PDF viewer's dark-mode chrome.
- **Dev/Tester read-only access** — `9f18a56` (2026-05-19, 4 files, +13/−6): Developer/Tester accounts can **read** admin/cockpit tabs (all except Pipeline) while every DB mutation stays blocked, so they can safely click through the whole workflow without being able to break live data. Tiny in lines, but it required getting the read predicate right across multiple policies so `tester_access=TRUE` rows show up alongside `cockpit_access=TRUE`.
- **Dual admin/labeler login** — `de13677` (2026-05-19): a separate admin vs. regular login with redirection. Implemented, then **reverted the same day** (`d671914`) on the supervisor's instruction — included here because the work was done.
- **Suggestion photo-view hotfix** (`8dc6771`) and **dropdown CSS polish** (`528848c`).

---

## Backlog items Huan closed end-to-end

| # | Item | Huan's commits |
| --- | --- | --- |
| 1 | Reset-password proper page | `4e208a5` |
| 2 | Theme system + PDF dark-mode | `cbf61ad`, `341b40e` |
| 3 | Infinite scrolling (old §10) | `4ade833` |
| 4 | Conflict resolution (UI + schema + view) | `a979d3f`, `f54f2fb`, `2121663` |
| 5 | Suggestions (modal + role-split + cockpit review + image attachments + private bucket + RLS) | `2fcdc55`, `4db6334`, `81d96af`, `0a5fdd6`, `bd29ab5`, `967c927`, `8dc6771`, `528848c`, `ebe2a3d` |
| 6 | Fuzzy matching (§8) + PDF-highlight fuzzy (§9) | `e3971b2`, `0c1d334` |

## Why the line count understates the contribution

Huan's 1,606 net lines are concentrated in **complete vertical features** rather than spread across large files. Three of his deliverables — suggestions, conflicts, and tester access — required **database tables, SQL views, RLS policies, and (for suggestions) a private Storage bucket with four security policies**, in addition to the React UI. That kind of full-stack feature, where a single wrong RLS predicate leaks private data, is a different and in places harder category of work than adding lines to an existing component. He also fixed two genuine auth-UX defects (silent reset-password login; dark-mode) that affected every user.
