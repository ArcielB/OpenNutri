# OpenNutri Work Report v2 - Duc Huan Ngo

Prepared: 2026-06-05
Repository snapshot: `1a8d1cf0394d2c86ba31604888969c30a9a47d32`
Contributor identity used for direct evidence: `landeryt <mcraft160105@gmail.com>`
Student: Duc Huan Ngo (`221229075`)

## Evidence Rule

Every `landeryt` commit is credited to Huan in full. This is the cleanest attribution case in the repository because his work appears directly under his git identity.

Current direct metrics:

| Evidence | Value |
| --- | ---: |
| Direct commits | 24 |
| Date range | 2026-03-16 to 2026-05-20 |
| Filtered line churn | `+2,188/-582` |
| Main source files | `SuggestionModal.jsx`, `fuzzyMatch.js`, `ResetPassword.jsx`, parts of `migration.sql`, `Annotate.jsx`, `index.css`, `PdfViewer.jsx` |

Filtered churn excludes USDA dumps, legacy archive, `package-lock.json`, and proposal appendix drafts. It is intentionally direct git-author evidence, not subsystem reassignment.

## Timeline of Direct Work

| Date | Commits | Work |
| --- | --- | --- |
| 2026-03-16 | `cbf61ad`, `341b40e` | Centralized theme state and followed system/browser theme preference. |
| 2026-03-19 | `4e208a5` | Reset-password recovery page and route behavior. |
| 2026-04-21 to 2026-04-25 | `2fcdc55`, `4db6334`, `ebe2a3d`, `bd29ab5`, `0a5fdd6` | Suggestion review flow, `backlog_review_items`, image attachment schema/storage, UI attachment upload. |
| 2026-04-26 | `4ade833` | Infinite PDF scrolling. |
| 2026-04-27 to 2026-04-28 | `a979d3f`, `2121663`, `f54f2fb`, `d02c6fe` | Conflict table/view/UI and supervisor suggestion backlog item. |
| 2026-05-07 | `967c927` | User/cockpit split for suggestions and user-visible status list. |
| 2026-05-09 | `e3971b2` | Fuzzy-match engine. |
| 2026-05-12 | `8dc6771`, `528848c` | Suggestion photo viewing hotfix and admin dropdown CSS. |
| 2026-05-19 | `de13677`, `d671914`, `9f18a56` | Dual-login experiment and revert; developer/tester read-only access fix. |
| 2026-05-20 | `0c1d334` | Backlog cleanup after fuzzy matching. |

## 1. Suggestion and Review Flow

Evidence files:

- `apps/expert-annotator/src/components/SuggestionModal.jsx` (279 lines)
- `apps/expert-annotator/src/views/SuggestionsReviewView.jsx`
- `apps/expert-annotator/src/views/MySuggestionsView.jsx`
- `apps/expert-annotator/migration.sql` sections for `backlog_review_items` and `suggestion-attachments`

What Huan built:

- A labeler-facing suggestion modal with title, message, context metadata, and optional image attachments.
- A cockpit review surface where reviewer/admin users can triage submitted suggestions.
- A user "My Suggestions" view so non-cockpit users can track status.
- Database table `backlog_review_items` for the suggestion/review queue.
- Private Supabase Storage bucket `suggestion-attachments`, with attachment metadata stored in the suggestion row.
- Role split: regular labelers submit and track suggestions; cockpit users review them.

Engineering details:

- Image upload is constrained by MIME type, count, and size: max 5 images, 10 MB each, image MIME allowlist.
- Filenames are sanitized before upload.
- Storage paths are scoped to the submitting user (`user_id/...`), matching the storage policy model.
- Uploaded storage objects are tracked during submission; if the database insert fails, the modal removes already-uploaded objects so the bucket does not accumulate orphans.
- Test mode avoids Supabase writes and records a local event instead.
- Later hotfixes restored photo viewing and improved the admin dropdown presentation.

Why it matters:

This was not only a modal. It was a vertical feature crossing React UI, Supabase table design, private Storage, RLS/storage policies, cockpit review UX, and failure cleanup. That is a full-stack contribution with security implications.

## 2. Fuzzy Matching

Evidence file:

- `apps/expert-annotator/src/utils/fuzzyMatch.js` (162 lines)

What Huan built:

- Shared token normalization and approximate matching utility used by food and nutrient autocomplete.
- Inflection handling: plural/singular normalization and irregular token map.
- Derived-prefix matching.
- Fuzzy token matching with allowed distance scaled by token length.
- Adjacent transposition detection.
- Token variant generation for broader Supabase/local search.

Hard part:

The file is small, but it is algorithmic. It implements bounded edit-distance matching rather than a one-off string contains check, and it gives the autocomplete components reusable relation types: exact, derived, fuzzy, and prefix.

Assessment value:

This code became load-bearing infrastructure. The higher-level food/nutrient ranking functions sit on top of Huan's token relation engine, so its contribution is larger than its line count suggests.

## 3. Reset Password

Evidence files:

- `apps/expert-annotator/src/pages/ResetPassword.jsx` (145 lines)
- `apps/expert-annotator/src/App.jsx`
- `apps/expert-annotator/.env.example`

What Huan fixed:

- Supabase password recovery links previously risked routing users into a confusing authenticated session.
- The reset page parses recovery tokens from the URL, establishes the recovery session, validates password rules, calls Supabase `updateUser`, and clears tokens from the URL after use.
- The app shell routes recovery URLs to the reset screen instead of the normal logged-in annotator flow.

Why it matters:

Password recovery is a security and usability path. A broken implementation locks users out or leaks auth state into the wrong screen. This was a real bug fix, not a cosmetic page.

## 4. Conflict System

Evidence files:

- `apps/expert-annotator/migration.sql` sections for `paper_conflicts`, `paper_conflict_resolutions`, and `paper_conflict_candidates`
- `apps/expert-annotator/src/pages/Annotate.jsx`
- `apps/expert-annotator/src/index.css`

What Huan built:

- SQL-backed conflict resolution infrastructure for the earlier assignment-based workflow.
- A view that detected papers with multiple reviewer submissions that disagreed by decision or payload.
- UI support for showing candidates and choosing the preferred submission.
- CSS fix so reviewer names and action controls rendered correctly.

Current status:

The conflict system is now legacy because the project moved to a general queue plus Arciel approval workflow. That does not erase the contribution: it shipped for the workflow generation that existed at the time and remains preserved as audit/history.

## 5. Theme, Infinite Scroll, and Tester Visibility

Theme:

- Huan centralized theme state in `App.jsx`.
- The app follows system/browser preference when no explicit override exists.
- The PDF viewer was adjusted to behave with theme changes.

Infinite scroll:

- Huan replaced page-by-page PDF navigation with continuous scroll.
- This touched both rendering behavior and scanner assumptions, because highlighting must still align across pages.

Developer/tester access:

- Huan changed access behavior so developer/tester accounts can view admin/cockpit tabs for review/training.
- Tester accounts remain read-only because mutation RPCs and frontend guards still block writes.

## Assessment Summary

Huan's work is best characterized as compact full-stack and algorithmic work:

- Suggestion system: table, Storage bucket, RLS-aligned upload paths, cockpit/user views, rollback cleanup.
- Fuzzy match: reusable approximate matching engine used by both autocompletes.
- Reset password: correct recovery-session handling.
- Conflict workflow: legacy but real SQL/UI workflow support.
- Access/theme/PDF UX improvements.

Direct git evidence supports **24 commits** and **`+2,188/-582` filtered churn**. The qualitative weight is higher than the line count because the suggestion and fuzzy-match features became infrastructure for other surfaces.

## Expanded Feature Ledger

This section expands the short assessment into a feature-by-feature list of what Huan did, why the work was needed, how it was implemented, and which technologies were involved.

### A. Theme Centralization and System Preference

**When:** 2026-03-16.
**Commits:** `cbf61ad`, `341b40e`.
**Technology:** React state, browser `prefers-color-scheme`, session storage, CSS theme variables.

What was done:

- Theme state was lifted into `App.jsx` so the login screen and authenticated annotator chrome used one source of truth.
- The app follows the user's system/browser preference when there is no explicit override.
- If a user changes theme during the session, the override is respected.
- PDF display behavior was adjusted so dark/light theme changes did not leave the viewer visually inconsistent.

Why it was needed:

The annotator is used for long labeling sessions. A mismatched login/app theme or a PDF viewer that does not follow the rest of the app creates fatigue and makes the interface feel broken. A shared theme state also prevents different components from inventing separate theme logic.

How it was implemented:

- App-level theme state was passed to the annotator surface.
- The hook detects system preference through `matchMedia`.
- Session storage is used for override persistence, keeping behavior local and lightweight.

Assessment value:

This is a small feature in code size, but it touches the whole app shell and improves the daily usability of the tool.

### B. Reset Password Recovery

**When:** 2026-03-19.
**Commit:** `4e208a5`.
**Technology:** Supabase Auth, React recovery route, browser URL hash parsing, session management.

What was done:

- Added a dedicated password recovery page.
- Routed recovery links to a password reset screen instead of dropping users into the normal logged-in annotator.
- Parsed Supabase recovery tokens from the URL.
- Established a Supabase recovery session.
- Validated password length and confirmation.
- Updated the user password through Supabase Auth.
- Removed tokens from the URL after use.

Why it was needed:

Password recovery is a trust/security feature. The previous behavior could confuse users by logging them in directly from the recovery link. Users needed a clear "set a new password" screen that handled expired links and did not leave tokens visible in the address bar.

How it was implemented:

- `ResetPassword.jsx` handles the token/session flow and form state.
- `App.jsx` detects recovery URLs/events and routes into the reset page.
- `.env.example` was updated for the redirect URL requirement.

Assessment value:

This is a correctness fix in the authentication flow, not a cosmetic page. It required understanding Supabase's recovery session behavior and the app's route/session state.

### C. Suggestion Review System

**When:** 2026-04-21 to 2026-05-12.
**Commits:** `2fcdc55`, `4db6334`, `ebe2a3d`, `bd29ab5`, `0a5fdd6`, `967c927`, `8dc6771`, `528848c`.
**Technology:** React, Supabase Postgres, Supabase Storage, RLS policies, signed URLs, CSS.

What was done:

- Added a user-facing suggestion workflow.
- Added cockpit/admin review of suggestions.
- Added user-side tracking of submitted suggestions and status.
- Created `backlog_review_items`.
- Added private image attachments through the `suggestion-attachments` bucket.
- Added attachment metadata to the suggestion row.
- Hid the suggestion button from cockpit/admin users where it was not appropriate.
- Fixed image viewing for both user and admin suggestion pages.
- Improved admin dropdown styling.

Why it was needed:

The app was being used by multiple people, and feedback could not stay only in chat. Users needed a structured way to report UI issues, ask for improvements, or submit supervisor-requested changes. Cockpit users needed to review those requests without giving normal users broad admin access.

How it was implemented:

- `SuggestionModal.jsx` validates title/message and attachment files.
- Images are limited to allowed MIME types, at most five files, and 10 MB per image.
- File names are sanitized before upload.
- Files are uploaded under a user-scoped path.
- Attachment metadata is included in `backlog_review_items.attachments`.
- If the database insert fails after one or more uploads, the modal deletes those uploaded objects so storage does not accumulate orphans.
- Supabase Storage policies restrict access to the correct bucket/path.
- Review views fetch signed URLs when images need to be displayed.

Why these technology choices:

- Supabase Storage was already used in the stack and provided private buckets, path-based policies, and signed URLs.
- JSONB attachment metadata kept the schema simple while still preserving multiple images.
- Client-side validation prevented obviously invalid files from consuming storage/bandwidth.

Assessment value:

This is Huan's strongest full-stack contribution. It spans UI, table design, private object storage, security policy alignment, error cleanup, and review workflow.

### D. Conflict Resolution System

**When:** 2026-04-27.
**Commits:** `a979d3f`, `2121663`, `f54f2fb`.
**Technology:** SQL tables/views, React UI, CSS.

What was done:

- Added a table for paper conflict resolutions.
- Added a conflict candidate view.
- Added UI support for displaying conflicting submissions.
- Added a "Choose This" style resolution affordance.
- Fixed CSS so reviewer names and buttons did not overlap.

Why it was needed:

The earlier assignment workflow allowed multiple reviewer submissions for the same paper. When reviewers disagreed, the app needed a structured way to identify those cases and choose the accepted submission. Otherwise conflicting labels would either be ignored or require ad hoc manual inspection.

How it was implemented:

- SQL grouped latest submissions and identified mismatches by decision and payload.
- UI showed candidate submissions for resolution.
- CSS was adjusted so the conflict list was usable.

Current status:

The later general queue plus approval workflow superseded this conflict model. It remains legitimate delivered work for the earlier architecture and is retained in the schema for audit/history.

### E. Infinite PDF Scroll

**When:** 2026-04-26.
**Commit:** `4ade833`.
**Technology:** React PDF viewer state, PDF text scanner coordination, CSS.

What was done:

- Replaced previous/next PDF page navigation with continuous/infinite scrolling.
- Touched `PdfViewer.jsx`, `PdfTextScanner.js`, and CSS.
- Kept PDF text/highlight behavior aligned with streamed page rendering.

Why it was needed:

Reviewers inspect scientific papers as documents, not as isolated slides. Continuous scroll is faster for scanning tables, captions, and nearby context. It also reduces friction when evidence is spread across multiple pages.

Assessment value:

The change was a UX improvement, but it affected PDF rendering/highlight assumptions, so it required more care than changing a button label.

### F. Fuzzy Matching Engine

**When:** 2026-05-09 and backlog cleanup 2026-05-20.
**Commits:** `e3971b2`, `0c1d334`.
**Technology:** JavaScript token processing, bounded Levenshtein distance, adjacent transposition detection.

What was done:

- Implemented `normalizeText`, `normalizeToken`, `tokenize`, `extractAliasSegments`.
- Implemented singular/plural and irregular-token handling.
- Implemented derived-prefix matching.
- Implemented bounded edit distance with early exits.
- Implemented adjacent transposition detection.
- Implemented relation lookup functions used by food/nutrient search.
- Cleared related backlog items after delivery.

Why it was needed:

Food and nutrient names are easy to mistype and vary by pluralization or alias. Exact string matching would slow labelers down. At the same time, aggressive fuzzy matching can return dangerous false positives. Huan's utility gives the autocomplete components relation tiers so they can score exact, derived, and fuzzy matches differently.

How it was implemented:

- The edit-distance function returns early when distance cannot fit the allowed band.
- Short tokens allow zero fuzziness, longer tokens allow one or two edits.
- Adjacent transpositions catch common typing mistakes.
- Token variants support broader Supabase prefix/broad search fallback.

Assessment value:

The file is only 162 lines, but it is algorithmically dense and reused by both autocomplete components.

### G. Developer/Tester Visibility

**When:** 2026-05-19.
**Commit:** `9f18a56`.
**Technology:** React view gating, Supabase reviewer profile flags, SQL permission predicates.

What was done:

- Developer/tester accounts can view the workflow and most cockpit/admin tabs for training/review.
- Tester accounts remain read-only.
- Pipeline access still requires actual cockpit permissions where appropriate.

Why it was needed:

The team needed safe demonstration/training accounts. Testers should be able to click around and understand the workflow without accidentally mutating production data.

How it was implemented:

- Frontend view visibility was broadened for tester/developer roles.
- Mutations remained blocked by UI guards and backend RPC predicates.

Assessment value:

This is a small code change with high correctness value: it expands visibility without weakening write safety.

## Direct Evidence Summary

Huan's direct work is backed by a compact but clear git trail:

| Area | Main files/tables | Direct evidence |
| --- | --- | --- |
| Theme | `App.jsx`, `useTheme.js`, `PdfViewer.jsx`, CSS | `cbf61ad`, `341b40e` |
| Reset password | `ResetPassword.jsx`, `App.jsx`, `.env.example` | `4e208a5` |
| Suggestions | `SuggestionModal.jsx`, `backlog_review_items`, `suggestion-attachments`, review views | `2fcdc55`, `4db6334`, `bd29ab5`, `0a5fdd6`, `967c927`, `8dc6771` |
| Conflict resolution | `paper_conflict_resolutions`, `paper_conflict_candidates`, `Annotate.jsx`, CSS | `a979d3f`, `2121663`, `f54f2fb` |
| PDF scroll | `PdfViewer.jsx`, `PdfTextScanner.js`, CSS | `4ade833` |
| Fuzzy matching | `fuzzyMatch.js`, autocomplete integration | `e3971b2`, `0c1d334` |
| Tester visibility | `Annotate.jsx`, `migration.sql`, README | `9f18a56` |
