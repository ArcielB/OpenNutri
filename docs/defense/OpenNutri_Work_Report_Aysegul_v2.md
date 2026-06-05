# OpenNutri Work Report v2 - Ayşegül Doğan

Prepared: 2026-06-05
Repository snapshot: `1a8d1cf0394d2c86ba31604888969c30a9a47d32`
Contributor: Ayşegül Doğan (`221229031`)

## Evidence Rule

Ayşegül has direct git-author evidence on `origin/master`, where the original annotator MVP/frontend commits are preserved under `ayseguldogan2706-cpu`. The current `main` branch later imported and reorganized that work through integration commits, so this report uses both:

- **Direct all-ref git evidence:** `git log --all --author=ayseguldogan2706-cpu`.
- **Subsystem ownership:** the current frontend area that grew from the original MVP and remains Ayşegül's assessment surface.

The ownership split used here matches the team split recorded in the master report:

- Ayşegül: core user-facing annotator frontend, annotation UI, PDF viewer/highlighting UX, autocomplete surfaces, and workflow views.
- Huan: direct `landeryt` commits, especially suggestions, fuzzy-match utility, reset password, conflict flow, theme/tester changes.
- Arciel: backend/schema/RPCs, AI pipeline, crawler, daily ops, deployment, and backend-driven cockpit/frontend integrations.

This report distinguishes direct historical commits from later integrated frontend work so the attribution is defensible instead of relying on current-mainline author history alone.

## At a Glance

| Evidence | Value |
| --- | ---: |
| Direct all-ref commits | 7 |
| Direct all-ref filtered git-author churn | `+6,624/-88` |
| Current frontend tracked lines | 13,788 |
| Principal queue/PDF/autocomplete/view files listed below | 10,334 lines |
| Core frontend source churn by path, excluding Huan-specific files | `+20,820/-7,891` |
| Current-mainline-only `ayseguldogan2706-cpu` churn | `+2/-2` because MVP commits are on `origin/master` |

Principal files:

- `apps/expert-annotator/src/pages/Annotate.jsx` (1,163)
- `apps/expert-annotator/src/views/QueueView.jsx`, `ApprovalView.jsx`, `DashboardView.jsx`, `AllPapersView.jsx`, `PipelineOpsView.jsx`
- `apps/expert-annotator/src/components/PdfViewer.jsx` (939)
- `apps/expert-annotator/src/utils/PdfTextScanner.js` (2,323)
- `apps/expert-annotator/src/utils/EvidenceLocations.js` (439)
- `apps/expert-annotator/src/components/FoodAutocomplete.jsx` (664)
- `apps/expert-annotator/src/components/NutrientAutocomplete.jsx` (334)
- `apps/expert-annotator/src/components/NutrientPopover.jsx`, `FoodItemForm.jsx`, `EvidenceStrip.jsx`, `PayloadSummary.jsx`, `AiDetailPanel.jsx`

Direct all-ref commit evidence:

| Date | Commit | Work |
| --- | --- | --- |
| 2026-03-02 | `7c2d372` | Initial OpenNutri annotation tool MVP. |
| 2026-03-02 | `614a82c` | Google OAuth login button. |
| 2026-03-02 | `6245a17` | Light/dark theme toggle, forgot-password affordance, suggestion feedback modal. |
| 2026-03-03 | `00fd645` | Flexible nutrient model, food autocomplete, PDF highlight redesign. |
| 2026-03-03 | `8a29dcb` | Dynamic Supabase Storage URL fetch for PDFs. |
| 2025-12-19 | `969c902`, `fb33626` | Push-access test file add/remove. |

## 1. Annotator Workspace

Evidence files:

- `Annotate.jsx`
- `QueueView.jsx`
- `FoodItemForm.jsx`
- `annotateHelpers.js`
- `testMode.js`

Work owned by the frontend area:

- The main labeler workspace where papers open with PDF on one side and editable food/nutrient rows on the other.
- Food item creation/removal and nutrient row editing.
- Save draft and submit reviewed data actions.
- "No usable data" path.
- Help request flow that includes the current paper, AI context, reviewer, and draft rows.
- Test mode/read-only behavior that lets training users exercise the UI without writing database rows.

Why it matters:

The project's data quality depends on this surface. The AI cascade only produces a normalized draft; the human labeler must be able to correct it accurately and submit a stable payload. The frontend is where "AI output" becomes "reviewed food-composition truth."

Hard parts:

- The editor must preserve normalized DB-aligned data while still allowing custom foods/nutrients.
- Existing drafts must not be overwritten by AI prefill.
- Final submit must validate that a useful-data decision contains at least one valid food item and nutrient row.
- The UI must remain usable for cockpit/tester accounts that can see the workflow but cannot mutate the database.

## 2. AI Prefill and Payload Shape

Evidence files:

- `Annotate.jsx`
- `annotateHelpers.js`
- `AiDetailPanel.jsx`
- `PayloadSummary.jsx`

Work owned by the frontend area:

- Queue papers with no saved annotation are initialized from the latest Gemini `normalized_payload_json`.
- Normalized payloads are converted into editable food item rows.
- Submitted and approved payloads are summarized for reviewers.
- AI Details show normalized payload and normalization summary, not raw model reasoning.

Hard part:

The same logical payload exists in three places:

- Python AI normalization (`normalize_ai_payload_with_summary`)
- SQL submission payload builders (`build_annotation_submission_payload`)
- JavaScript editor helpers (`buildFoodItemsFromPayload`, `normalizeFoodItem`)

The frontend has to match the backend contract closely. If one side drifts, exact comparison and reviewer correction metrics stop being reliable.

## 3. PDF Viewer and Evidence Highlighting UX

Evidence files:

- `PdfViewer.jsx` (939)
- `PdfTextScanner.js` (2,323)
- `EvidenceLocations.js` (439)
- `EvidenceStrip.jsx`
- `NutrientPopover.jsx`
- `pdfCache.js`
- evidence status cache utilities

Work owned by the frontend area:

- Continuous PDF viewer with nutrient click interactions.
- Evidence source strip built from normalized payload metadata.
- Coordinate overlays for matched table/paragraph evidence.
- Page navigation to evidence locations.
- Nutrient popover that inserts a clicked PDF nutrient into the active food item.
- Browser-side PDF byte cache and next-paper prefetch.

Why this is a major technical subsystem:

PDF.js returns positioned text fragments, not semantic tables. The scanner reconstructs structure from geometry:

- Page metrics and row grouping.
- Column gutter detection.
- Fragment classification into table-like/prose/caption-like text.
- Caption-anchored table region growth.
- Paragraph block construction and clipping.
- Source-quote matching across paragraphs, rows, and fragments.
- Whole-block overlay generation.
- Deduplication of sources that resolve to the same table or paragraph.

Hard parts:

- Evidence must be precise enough for reviewers to trust it.
- AI `page_hint` values can be printed journal pages instead of PDF page indexes, so the viewer must not blindly gate matching to invalid pages.
- Nutrient names in narrative prose should not become random clickable highlights.
- Multi-column journal pages can merge visually unrelated text into one row unless the scanner detects gutters.

Assessment value:

This is not ordinary frontend form work. It is browser-side document layout analysis plus reviewer UX. At 2,323 lines, `PdfTextScanner.js` is one of the largest and hardest single files in the repository.

## 4. Food and Nutrient Autocomplete UX

Evidence files:

- `FoodAutocomplete.jsx`
- `NutrientAutocomplete.jsx`
- `fuzzyMatch.js` (Huan's shared utility used by these components)
- `searchSessionLogger.js`

Work owned by the frontend area:

- Food catalog search with canonical names, base names, aliases, whole-food preference, custom-food fallback, keyboard navigation, and async query fallback when local catalog is not loaded.
- Nutrient search with aliases, categories, preferred units, and custom-nutrient support.
- Search session logging for query/result/resolution telemetry.

Hard parts:

- Food names are ambiguous. The scorer must prefer a useful generic food when the user types "apple" rather than a processed or unrelated variant.
- Autocomplete has to work before the full food catalog finishes loading.
- Custom rows must be allowed without breaking normalized payload structure.

## 5. Workflow Views and Cockpit Surfaces

Evidence files:

- `QueueView.jsx`
- `ApprovalView.jsx`
- `DashboardView.jsx`
- `AllPapersView.jsx`
- `PipelineOpsView.jsx`
- `ReviewerAdminView.jsx`
- `SuggestionsReviewView.jsx`
- `MySuggestionsView.jsx`

Work owned by the frontend area:

- Queue view for active labeling.
- Approval view with original labeler payload and editable final reviewer payload.
- Dashboard view for labeler performance and correction details.
- Useful Papers view with AI Details.
- Pipeline view showing crawler/model/human funnel state.
- Reviewer admin and suggestion review screens.

Hard parts:

- Each view has different permission semantics: labeler, tester, cockpit, approver, and developer accounts see different controls.
- Approval must preserve the original submission while allowing final reviewer correction.
- Pipeline labels must remain role-stable even when underlying model names change.
- The UI must hide provisional AI no-data skips from default useful-paper overview.

## 6. Performance and Usability Constraints

Evidence files:

- `Annotate.jsx`
- `QueueView.jsx`
- `PdfViewer.jsx`
- `pdfCache.js`
- `annotateHelpers.js`

Frontend design constraints:

- Supabase free-tier egress made raw `select('*')` patterns unacceptable for cockpit lists.
- The queue should load without waiting for heavy cockpit dashboards.
- Food catalog loading should happen in idle time.
- PDF rendering should prioritize page 1 and evidence pages before rendering the entire document.
- The next papers' PDFs should prefetch during idle time to reduce labeler waiting.

Assessment value:

This frontend is production-shaped. It is not a demo page: it has permissions, caching, lazy loading, test mode, editor validation, source evidence, reviewer correction, and operational cockpit views.

## Assessment Summary

Ayşegül's assessable contribution is the user-facing frontend:

- Queue and annotation editor.
- PDF viewer and evidence UX.
- Food/nutrient form and autocomplete workflow.
- Reviewer approval/user dashboard/cockpit surfaces.
- Frontend behavior needed to turn AI prefill into reviewed human truth.

The defensible quantitative evidence is **7 all-ref commits**, **`+6,624/-88` direct all-ref filtered churn**, **13,788 current frontend lines**, **10,334 lines in the principal frontend files listed here**, and **`+20,820/-7,891` core frontend path churn** after excluding Huan-specific direct files. The current `main` branch alone under-represents her authorship because the original MVP/frontend commits are preserved on `origin/master`.

## Expanded Frontend Work Ledger

This section expands the frontend work into concrete deliverables, with "what, why, how, technology, and evidence" for each area.

### A. Original Annotator MVP

**When:** 2026-03-02.
**Direct commits:** `7c2d372`, `614a82c`, `6245a17`.
**Technology:** React, Vite, Supabase client, Supabase Auth, CSS.

What was built:

- Initial OpenNutri annotation tool.
- Vite/React project setup.
- Supabase client connection.
- Login page.
- Annotate page.
- Basic PDF viewer.
- Food item form.
- Application styling.
- Google OAuth button.
- Light/dark theme toggle.
- Forgot-password affordance.
- First suggestion feedback modal.

Why it was needed:

OpenNutri needed a usable human labeling interface before a sophisticated backend would be useful. The original MVP established the core product concept: a reviewer opens a paper, reads the PDF, and enters food composition rows.

How it was implemented:

- React components were organized around `App`, `Login`, `Annotate`, `FoodItemForm`, and `PdfViewer`.
- Supabase was used for auth and backend access.
- CSS implemented the first app shell and theme.
- The MVP was later imported/reorganized into `apps/expert-annotator/` on `main`.

Assessment value:

This was the first concrete user-facing application. Later work replaced and expanded many internals, but the core annotator surface started here.

### B. Flexible Nutrient Model, Food Autocomplete, and PDF Highlight Redesign

**When:** 2026-03-03.
**Direct commit:** `00fd645`.
**Technology:** React forms, SQL schema changes, PDF viewer/text scanning, autocomplete components.

What was built:

- Flexible nutrient rows rather than a rigid fixed nutrient list.
- Food autocomplete component.
- Nutrient autocomplete component.
- Nutrient popover component.
- PDF highlight redesign.
- Schema changes to support the frontend data model.

Why it was needed:

Food composition papers do not all report the same nutrients. A rigid form would fail immediately. Reviewers needed flexible nutrient rows and search-based resolution. The PDF highlight redesign made the paper reading task more connected to data entry.

How it was implemented:

- `FoodItemForm.jsx` gained dynamic nutrient row behavior.
- `FoodAutocomplete.jsx` and `NutrientAutocomplete.jsx` provided search/select interactions.
- `NutrientPopover.jsx` connected PDF clicks to nutrient entry.
- `PdfViewer.jsx` and `PdfTextScanner.js` started the path toward PDF text matching.
- SQL was adjusted for nutrient values.

Evidence:

- Direct commit `00fd645` added 1,242 lines and modified 9 files.
- Current descendant files: `FoodAutocomplete.jsx` (664), `NutrientAutocomplete.jsx` (334), `NutrientPopover.jsx` (128), `FoodItemForm.jsx` (110), `PdfViewer.jsx` (939), `PdfTextScanner.js` (2,323).

### C. Dynamic PDF URL Handling

**When:** 2026-03-03.
**Direct commit:** `8a29dcb`.
**Technology:** Supabase Storage URL retrieval, React page state.

What was built:

- Dynamic Supabase storage URL fetch for PDFs.

Why it was needed:

Hardcoded PDF URLs are brittle. A labeler queue needs to load whichever paper is selected, and the frontend should derive or fetch the correct PDF URL rather than requiring manual environment updates.

Current evolution:

The project later moved away from storing paper PDFs in Supabase by default, but the same user-facing requirement remained: the PDF viewer should load the paper associated with the current queue item without manual URL management.

### D. Queue View and Main Annotation Workspace

**When:** Initial MVP March; major current form May/June.
**Technology:** React state/hooks, Supabase RPCs, Vite, CSS.

What was built:

- Paper list/queue selection.
- PDF + editor workspace layout.
- Food item and nutrient row editor.
- Add/remove food items.
- Save draft.
- Submit reviewed data.
- No usable data action.
- Ask for Help action.
- Test-mode/read-only UI messages.
- Source/evidence strip.
- Next-paper PDF prefetch.

Why it was needed:

This is the core work screen for labelers. It had to be dense enough for repeated use but not so complex that labelers could not review papers efficiently.

How it was implemented:

- `QueueView.jsx` composes the PDF viewer, evidence strip, food item forms, and action buttons.
- `Annotate.jsx` owns the selected queue item, food item state, save/submit actions, help request, and queue refresh.
- `get_general_queue_cards` feeds the view with a lean card plus latest AI payload.
- `getPublicPdfUrl` chooses direct/proxied PDF URL.

Evidence:

- `QueueView.jsx`: 227 lines.
- `Annotate.jsx`: 1,163 lines.
- `annotateHelpers.js`: 574 lines.

### E. AI Prefill Editing Experience

**When:** April/May 2026 after AI extraction integration; refined through June.
**Technology:** JSONB normalized payloads, React form conversion, Supabase RPCs.

What was built:

- Queue papers open with latest Gemini normalized payload prefilled into editable rows when no draft exists.
- Existing user drafts/submissions are preserved and not overwritten.
- Source metadata from normalized payload rows feeds the evidence strip/PDF viewer.
- AI Details panel shows normalized rows and normalization summary without exposing raw reasoning.

Why it was needed:

The AI cascade should reduce human labor, not replace human review. Prefill turns the final Gemini extraction into a draft the reviewer can correct. Quiet prefill was important: labelers should review rows directly rather than interpret AI reasoning banners.

How it was implemented:

- `Annotate.jsx` checks for saved annotation; if none exists, it calls `buildFoodItemsFromPayload` on the latest AI payload.
- `aiPrefillSources` records which extraction initialized the rows.
- `EvidenceStrip` and `PdfViewer` receive evidence locations from current rows or fallback AI payload.
- Details panels use normalized payload summaries.

Assessment value:

This is one of the project's key UX wins: reviewers correct structured draft rows instead of starting from a blank form.

### F. PDF Evidence UX

**When:** March start; major evidence overlay work April 22 to June 5.
**Technology:** PDF.js/react-pdf, PDF text layer, geometry heuristics, coordinate overlays, browser cache.

What was built:

- Continuous/scanned PDF viewer.
- Nutrient click marks.
- Table-scoped highlighting.
- Source/evidence overlays.
- Table/paragraph block overlays.
- Evidence page navigation.
- Printed-page fallback handling.
- Auto-open/highlight first evidence page.
- Durable PDF caching and idle prefetch.

Why it was needed:

Reviewers need to verify source evidence rapidly. Scientific papers frequently contain dense tables, multi-column layouts, printed page numbers that do not match PDF indexes, and split text fragments. The frontend had to make the source evidence visible and navigable.

How it was implemented:

- `PdfTextScanner.js` turns flat PDF.js text items into rows, fragments, table regions, paragraph regions, and source matches.
- `PdfViewer.jsx` renders overlays by scaling PDF coordinates to screen coordinates.
- `EvidenceLocations.js` deduplicates source locations.
- Caches persist evidence and PDF bytes to reduce reload time.

Hard parts:

- PDF.js does not give semantic tables.
- Multi-column papers need gutter-aware row splitting.
- AI page hints can be printed journal pages, so over-range hints must not block text matching.
- Overlays must be stable and not flicker.

Evidence:

- `PdfTextScanner.js`: 2,323 lines.
- `PdfViewer.jsx`: 939 lines.
- `EvidenceLocations.js`: 439 lines.
- Frontend PDF/evidence tests: 972 lines total.

### G. Autocomplete and Search UX

**When:** Initial direct work on 2026-03-03; expanded in current frontend.
**Technology:** React autocomplete components, Supabase queries, local ranking, Huan's fuzzy matcher, search telemetry.

What was built:

- Food search over canonical names, aliases, base names, and custom entries.
- Nutrient search over standard names/aliases/categories.
- Keyboard navigation and custom entry fallback.
- Debounced queries.
- Local full-catalog ranking when loaded.
- Supabase fallback search before full catalog load.
- Search session logging.

Why it was needed:

Fast, accurate catalog resolution affects every submitted food/nutrient row. If autocomplete is slow or imprecise, labelers either make wrong mappings or create too many custom rows.

How it was implemented:

- `FoodAutocomplete.jsx` computes weighted scores for exact, prefix, base-name, alias, token, and fuzzy relations.
- It penalizes processed variants for generic whole-food queries.
- `NutrientAutocomplete.jsx` ranks nutrient names/aliases and formats units.
- `searchSessionLogger.js` records query behavior for later UX analysis.

### H. Approval, Dashboard, and Cockpit Views

**When:** April/May 2026 onward.
**Technology:** React views, Supabase RPCs, JSON payload summaries, CSS.

What was built:

- `ApprovalView`: pending submissions, original labeler payload, editable final reviewer payload.
- `DashboardView`: labeler metrics, pending/accepted/corrected/superseded counts, correction items.
- `AllPapersView`: Useful Papers list and Latest AI detail affordance.
- `PipelineOpsView`: crawler/model/human funnel and current queue status.
- `ReviewerAdminView`: reviewer profile/admin controls.
- Suggestion views: cockpit review and user status.

Why it was needed:

The frontend had to support more than one labeler screen. Arciel needed approval and operations views; team members needed performance/correction feedback; cockpit users needed a view into useful papers and pipeline health.

How it was implemented:

- The monolithic annotator was refactored into smaller view components on 2026-05-16.
- `annotateHelpers.js` centralizes status formatting, model-stage labels, payload summaries, and pipeline funnel construction.
- Views consume slim RPC projections instead of raw large tables.

Assessment value:

These views are a complete operational UI, not a single-form demo.

### I. Performance and Production Usability

**When:** May/June 2026.
**Technology:** requestIdleCallback, Cache Storage, localStorage LRU, Vite self-hosted worker, lean RPCs.

What was built:

- Food catalog loads during idle time.
- Cockpit data loads only when cockpit tabs open.
- Queue loads in parallel with profile sync.
- PDF worker is self-hosted/bundled.
- PDF bytes are cached durably.
- Next two queue PDFs are prefetched during idle time.
- Evidence pages render before the rest of the PDF.

Why it was needed:

The app is used for repeated labeling. Slow startup, repeated PDF downloads, and heavy Supabase payloads waste reviewer time and burn free-tier egress. The frontend had to become production-efficient.

How it was implemented:

- `Annotate.jsx` parallelizes queue/profile boot and lazy-loads cockpit data.
- `QueueView.jsx` prefetches next PDFs.
- `PdfViewer.jsx` scans evidence pages headlessly and prioritizes rendering.
- `pdfCache.js` stores PDF bytes in Cache Storage.

## Frontend Evidence Summary

| Area | Current source evidence | Why it matters |
| --- | ---: | --- |
| App orchestration | `Annotate.jsx` 1,163 lines | Queue, save, submit, approval, cockpit loading. |
| PDF scanner/viewer | `PdfTextScanner.js` 2,323 + `PdfViewer.jsx` 939 | Evidence verification and nutrient click UX. |
| Food/nutrient forms | `FoodAutocomplete.jsx` 664, `NutrientAutocomplete.jsx` 334, form/popover components | Accurate data entry. |
| Views | Queue/Approval/Dashboard/AllPapers/Pipeline/Admin/Suggestions views | Complete workflow UI. |
| Frontend tests | 972 PDF/evidence/cache lines | Regression coverage for high-risk PDF evidence behavior. |
