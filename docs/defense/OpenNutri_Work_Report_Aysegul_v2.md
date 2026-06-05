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
