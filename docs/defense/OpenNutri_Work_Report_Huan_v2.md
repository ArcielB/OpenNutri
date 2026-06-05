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
