# OpenNutri — Work Report: Duc Huan Ngo (221229075)

*Self-contained, code-grounded account of Huan's contributions, written after reading his actual source files. Companion to the master report; numbers re-derived from git on 2026-06-05, HEAD `ac8bf72`.*

## At a glance

- **23 commits** under the `landeryt` identity, 2026-03-16 → 2026-05-20; **+2,188 / −582 lines** (net **+1,606**).
- **Attribution rule:** every `landeryt` commit is credited to Huan in full, whether it touched React, SQL, RLS, or Storage.
- **Headline:** Huan's hallmark is **full-stack vertical features** and **reusable algorithm code**. Reading his files (rather than counting lines) shows two of them are infrastructure other features depend on — the fuzzy-match engine behind both autocompletes, and a suggestion feature with its own table, Storage bucket, and four security policies — plus a real auth-bug fix.

---
## Huan's features — read at the source *(Duc Huan Ngo)*

**Files read for this section:** `utils/fuzzyMatch.js` (162), `components/SuggestionModal.jsx` (279), `pages/ResetPassword.jsx` (145), plus his SQL in `migration.sql` (`backlog_review_items`, the `suggestion-attachments` bucket policies, `paper_conflict_resolutions` + `paper_conflict_candidates`). **23 `landeryt` commits.** Reading the actual code raises the assessment of his work above what the raw line count (~1,600 net) suggests — two of his files are *infrastructure that other features depend on*.

### 1. `fuzzyMatch.js` — a real fuzzy-match library that powers both autocompletes
This is the most undervalued Huan file. It is the shared tokenization + approximate-matching engine that **`FoodAutocomplete` and `NutrientAutocomplete` both import** — the ranking described in the frontend app section sits on top of it. It contains genuine algorithm work:
- **Banded Levenshtein** (`levenshteinDistance`) — two-row rolling arrays, an early-exit `Math.abs(aLen-bLen) > maxDistance` guard, and a per-row `minInRow > maxDistance` bail-out so it stops as soon as the edit distance provably exceeds the allowed band. O(n·band) instead of O(n·m).
- **Damerau adjacent transposition** (`isSingleAdjacentTransposition`) — catches "abc"↔"acb" typos that plain Levenshtein scores as distance 2.
- **Length-scaled tolerance** (`getAllowedFuzzyDistance`) — 0 edits under 4 chars, 1 under 8, 2 at 8+, so short words aren't over-matched.
- **Inflection/stemming** (`normalizeToken`) — `ies→y`, `oes→o`, trailing-`s` removal with `ss`/`us`/`is` guards, plus an `IRREGULAR_TOKEN_MAP` (mice→mouse, feet→foot…).
- **A relation cascade** (`findTokenRelationIndex`) returning `exact → derived → fuzzy`, which is exactly the relation tiering the food/nutrient scorers weight differently.
This closed BACKLOG §8 and the dependent §9 (fuzzy in PDF highlight). It is small in lines because it is dense, reusable algorithm code.

### 2. Suggestions system — a careful full-stack feature
`SuggestionModal.jsx` plus his SQL is a complete vertical slice with real engineering judgment:
- **Client-side validation:** a 7-type image MIME allowlist, max 5 images, 10 MB each, dedup by `name+size+lastModified`, filename sanitization.
- **RLS-aligned storage paths:** files upload to `${user.id}/${timestamp}-${i}-${name}` — a **per-user folder**, which is precisely what his four `storage.objects` policies enforce via `storage.foldername(name)`. The UI and the security policy were designed together.
- **Transactional upload-then-insert with rollback:** uploaded storage objects are tracked in `uploadedStorageObjects`; if the subsequent `backlog_review_items` insert throws, the modal **deletes the already-uploaded files** so a failed submission never leaves orphaned objects in the bucket. That is the kind of cleanup most student code skips.
- **Test-mode aware:** in local-only mode it records the suggestion to `appendTestEvent` instead of touching Supabase.
- **His backend:** the `backlog_review_items` table (role-based RLS via `current_user_has_cockpit_access()`), the **private `suggestion-attachments` bucket** (10 MiB limit, image-MIME allowlist, four view/upload/update/delete policies with per-user containment), and the role-split (labelers submit + track in `My Suggestions`; cockpit triages in `Suggestions`, opening images from **signed URLs at view time**).

### 3. Reset-password page — a real auth-bug fix
`ResetPassword.jsx` fixes a genuine defect: Supabase recovery links used to silently log the user in. His version parses `access_token`/`refresh_token` **out of the URL hash**, calls `supabase.auth.setSession`, validates the recovery session (clear error if expired), enforces password rules (match + ≥8 chars), calls `updateUser`, and **cleans the tokens out of the URL** with `history.replaceState` before returning to login. Correct session handling, not a toy form.

### 4. Conflicts system (legacy) — table + SQL view + UI
He built `paper_conflict_resolutions` and the `paper_conflict_candidates` **view** (a CTE that aggregates the latest submission per assignment and flags `decision_mismatch` / `payload_mismatch` / `decision_and_payload_mismatch`), wired into `Annotate.jsx` with a "Choose This" picker. Fully delivered; later superseded by Arciel's general approval queue — normal architecture evolution, the feature shipped and worked for the model that existed then.

### 5. Theme system, infinite scroll, dev/tester read-only
- **Theme centralization** (`cbf61ad`, `341b40e`): lifted theme into `App.jsx`, follows OS/browser preference when no override, fixed PDF dark mode.
- **Infinite PDF scrolling** (`4ade833`): replaced prev/next paging with continuous scroll, touching `PdfTextScanner.js` so highlight matching stayed correct across streamed pages.
- **Dev/Tester read-only access** (`9f18a56`): a small (+13/−6) but correctness-critical predicate change so `tester_access=TRUE` accounts can read admin/cockpit tabs (except Pipeline) while every mutation stays blocked.

### Honest assessment
Huan's ~1,600 net lines under-represent the contribution because two of his files are **load-bearing infrastructure** (the fuzzy-match engine powering both autocompletes; the suggestion vertical with its own table, bucket, and four security policies) and one is a real **auth-bug fix**. Full-stack features where a wrong RLS predicate leaks private data — and where the code actually rolls back partial failures — are a harder category than the line count shows.
