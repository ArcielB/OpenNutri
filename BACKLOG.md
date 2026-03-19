# Backlog

This backlog is written so a new contributor can understand each item without extra context.

How to use this backlog:
- each item should be understandable without asking for hidden context
- if you take an item, reproduce the problem first
- prefer small, testable changes
- if you discover extra edge cases, add them under the item instead of rewriting its scope silently

## 1. Route user suggestions into the backlog review queue

### Problem
The UI has a suggestion button, but suggestions are not flowing into an internal review workflow that is easy to track, triage, or follow up on.

### Goal
Store each suggestion as a backlog review item that supports:
- easy review
- status tracking
- optional follow-up
- low operational overhead

### Notes
- Do not send suggestions to Google Keep or another external note app.
- Suggestions should be saved as review items in the project backlog or a backlog-backed store.
- Each suggestion should record who submitted it and that it is a `suggestion to review`, not an approved backlog task.
- If image attachments are added, the destination must support files as well as text.

### Good candidate solutions
- Supabase table plus internal backlog-review view
- file or JSON-backed review queue that can be synced into `BACKLOG.md`
- GitHub Issues only if they are clearly marked as unreviewed suggestions

### Done when
- a suggestion is saved in a reviewable destination
- the destination records submitter identity and timestamp
- the record is marked as a suggestion to review, not a confirmed task
- reviewers can change status later without losing the original suggestion text

## 2. (Depends on 1) Add image attachments to the suggestion flow

### Problem
Users can submit text suggestions, but they cannot attach screenshots. That makes bug reports slower to understand and reproduce.

### Goal
Allow one or more image attachments in the suggestion modal.

### Requirements
- image upload from the UI
- file validation
- upload success and failure feedback
- suggestion record linked to uploaded files

### Dependency
- This may change the best implementation choice for item 1.

### Done when
- a user can attach at least one image
- invalid files are rejected clearly
- uploaded images remain linked to the suggestion record
- failure states are visible to the user

## 3. Fix PDF nutrient highlighting errors

### Problem
The nutrient highlighting feature works for many terms but fails for some words or phrases. In some PDFs it highlights partial words, the wrong word, or a broken segment inside a word.

### Known bad example
- `glucose`
- `sucrose`
- `maltose`
- `lactose`

Observed behavior:
- highlight does not always cover the full visible nutrient token cleanly

### Likely technical area
- `apps/expert-annotator/src/components/PdfViewer.jsx`
- `apps/expert-annotator/src/utils/PdfTextScanner.js`

### Goal
Make nutrient highlighting reliable in PDF text layers, even when PDF.js splits visible text into awkward spans or text nodes.

### Acceptance criteria
- highlight covers the intended nutrient word only
- no matching inside injected markup
- no broken partial-word highlight
- click-to-open nutrient popover still works
- no regression on already-working nutrient names

### Notes
- This is harder than it looks because PDF text layers are not normal HTML text flows.
- A rewrite of the highlight algorithm is acceptable if needed.

### Done when
- the known bad examples highlight correctly
- already-working nutrient terms still highlight correctly
- no highlight is created inside injected markup
- popover interaction still works

## 4. Improve the crawler so it collects the right papers (Arciel working)

### Problem
The crawler should collect food composition papers, but it currently pulls many irrelevant papers or fails during live retrieval.

### Wanted papers
- food composition papers
- nutrient composition papers
- proximate composition papers
- fatty acid, mineral, or vitamin content papers
- database or table papers that report nutrient values for foods

### Unwanted papers
- health effect papers
- supplementation or intervention studies
- reviews without usable composition data
- packaging, materials, sensor, and veterinary feed papers

### Goal
Build a crawler that:
- retrieves candidate papers reliably
- filters for food composition relevance
- stores paper artifacts consistently
- records why a paper was accepted or rejected

### Implementation direction
- Use foods already known in the project catalog as search anchors, but do not restrict the system to only those foods forever.
- Use a food-composition nutrient panel as search guidance: proximate nutrients, minerals, vitamins, fatty acids, amino acids.
- Keep query templates small and high-precision instead of exploding into too many weak combinations.
- Use a two-stage decision flow:
  - metadata ranking to shortlist likely papers
  - PDF full-text validation before saving a paper
- Reject papers whose main contribution is not food composition data:
  - body composition / physiology
  - functional properties / rheology / viscosity / processing behavior
  - extracts / essential oils / bioactivity
  - materials / packaging / environmental chemistry
- Accept papers only when they contain meaningful nutrient data that could plausibly map into the OpenNutri schema.
- Record acceptance and rejection reasons so future feedback learning can be added on top of a stable baseline.
- Pass through a small, deterministic slice of rejects (every 100th) for audit/recall checks.

### Current technical area
- `services/data-pipeline/main.py`
- `services/data-pipeline/food_paper_crawler/`

### Known blocker
- live paper retrieval has been unreliable in the current environment

### Status
- Arciel is currently working on the crawler.

### Done when
- the crawler keeps papers that clearly contain food composition data
- obvious junk classes are rejected consistently
- saved papers are manually inspectable and defensible
- the crawler records why each kept or rejected paper was classified that way

## 5. Add a safe test mode that does not write to production data

### Problem
People need to test flows and extraction behavior, but test actions can currently look too similar to real actions and may write into the main database.

### Goal
Add a clear test mode where users can exercise the app without updating production records.

### Requirements
- visible indication that test mode is active
- annotation saves and similar actions do not write to the real DB
- test-mode output should go to either:
  - no persistence
  - a separate test table / namespace
  - a clearly isolated local artifact
- switching between normal mode and test mode must be deliberate

### Good use cases
- checking whether a feature works
- validating annotation UX
- reproducing bugs
- trying extraction changes without polluting real data

### Done when
- a tester can clearly tell they are in test mode
- production records are untouched during test-mode actions
- test-mode behavior is easy to turn on and off deliberately

## 6. Fix reset password flow

### Problem
The reset password email arrives, but the link opens the app and logs the user in instead of taking them to a dedicated password reset screen.

### Goal
Make password reset behave like a standard recovery flow:
- user clicks email link
- app recognizes recovery state
- user lands on reset-password screen
- user sets a new password

### Acceptance criteria
- recovery links open the correct route
- password update UI appears automatically
- session handling does not skip the reset step
- user sees a clear success or failure state

### Done when
- the recovery link lands on the reset-password flow
- the user can set a new password without manual workaround
- the app shows a clear success or failure message

## 8. (Arciel working) L2 lightweight classifier for paper relevance (paper extractor part 2)

### Problem
Relevance scoring is currently heuristic and static, so it cannot improve from labeling feedback.

### Goal
Train a fast, cheap classifier that predicts whether a paper has composition data using title/abstract/journal signals:
- probability output with a configurable threshold
- feature logging for quick debugging
- model artifact can be versioned and reloaded

### Likely technical area
- `services/data-pipeline/food_paper_crawler/`
- `services/data-pipeline/food_paper_crawler/ranking.py`

### Sources to check when needed
- scikit-learn text classification pipeline: https://scikit-learn.org/1.3/tutorial/text_analytics/working_with_text_data.html
- fastText supervised classification: https://fasttext.cc/docs/en/supervised-tutorial.html

### Done when
- a classifier can be trained from label data
- crawler uses it before downloading PDFs
- per-run metrics include classifier precision/recall

## 9. (Depends on 8) L3 feedback loop from UI labels to crawler/classifier (paper extractor part 3)

### Problem
Annotator decisions are not feeding back into the crawler or the classifier.

### Goal
Create a feedback pipeline that:
- stores global paper labels with provenance
- exports labeled data for model training
- updates query term weights from good/bad examples

### Likely technical area
- `apps/expert-annotator/src/pages/Annotate.jsx`
- `apps/expert-annotator/migration.sql`
- `services/data-pipeline/food_paper_crawler/`
- `services/data-pipeline/core/knowledge.py`

### Sources to check when needed
- Snorkel weak supervision (optional): https://docs.snorkel.ai/docs/25.2/user-guide/intro/what-is-snorkel-flow

### Done when
- labels flow from UI to a training dataset
- classifier retrain is repeatable
- crawler term weights update from the label stats

## 10. (Depends on 9) Add a global “definitely no data” red button (immediate skip + training)

### Problem
The current “No Usable Data” button is per-user, so obvious junk still shows up for others and does not become an immediate global negative label.

### Goal
Add a red button that marks a paper as definitely no-data for everyone and sends it directly to training data.

### Requirements
- explicit confirmation to avoid accidental global skips
- global label stored with user, timestamp, and reason
- paper removed from every annotator queue
- label appears immediately in training export

### Likely technical area
- `apps/expert-annotator/src/pages/Annotate.jsx`
- `apps/expert-annotator/migration.sql`
- `apps/expert-annotator/src/index.css`

### Done when
- the global no-data label hides the paper for all users
- the label is immediately used by the training pipeline

## 12. Improve fuzzy matching logic

### Problem
Fuzzy matching can be too loose or too strict, which affects the quality of nutrient suggestions and matching confidence.

### Goal
Improve fuzzy scoring and normalization so suggestions are ranked more accurately and consistently.

### Likely technical area
- `apps/expert-annotator/src/utils/fuzzyMatch.js`
- `apps/expert-annotator/src/components/NutrientAutocomplete.jsx`

### Done when
- top suggestions match expected nutrients for common user inputs
- typo tolerance improves without causing irrelevant matches
- scoring/ranking is stable across similar inputs

## 13. (Depends on 12) Use improved fuzzy matching in PDF highlighting

### Problem
PDF highlighting uses term matching that does not benefit from improved fuzzy logic, which can miss or mis-rank matches.

### Goal
Apply the improved fuzzy logic from item 12 to highlight matching in the PDF text layer.

### Likely technical area
- `apps/expert-annotator/src/components/PdfViewer.jsx`
- `apps/expert-annotator/src/utils/PdfTextScanner.js`
- `apps/expert-annotator/src/utils/fuzzyMatch.js`

### Done when
- PDF highlights align with improved fuzzy match ranking
- existing exact matches continue to work

## 14. Add limitless scrolling for papers list (no page clicks)

### Problem
The papers list requires clicking across pages, which slows navigation and interrupts flow.

### Goal
Replace paginated navigation with infinite/limitless scrolling.

### Likely technical area
- `apps/expert-annotator/src/pages/Annotate.jsx`
- `apps/expert-annotator/src/components/PaperList.jsx` (if present)

### Done when
- new papers load seamlessly as the user scrolls
- the current selection state remains stable while loading
- pagination controls are no longer required

## 15. Hide papers list popover when clicking outside

### Problem
The papers list dropdown/popup remains open when clicking elsewhere on the page.

### Goal
Dismiss the papers list popover on outside click.

### Likely technical area
- `apps/expert-annotator/src/pages/Annotate.jsx`
- `apps/expert-annotator/src/components/Dropdown.jsx` (if present)

### Done when
- popover closes on any click outside the popover
- clicking inside the popover does not close it

## 16. Remove the “Trabzon Ekmeği” example text

### Problem
An example like “Trabzon Ekmeği” is shown, but no example is needed in that spot.

### Goal
Remove the example text so the UI is cleaner.

### Likely technical area
- `apps/expert-annotator/src/components/FoodAutocomplete.jsx`
- `apps/expert-annotator/src/pages/Annotate.jsx`

### Done when
- the example text is no longer displayed
