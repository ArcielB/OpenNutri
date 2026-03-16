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

## 6. Implement both AI systems in a measurable test setup

### Problem
The project intends to use two AI systems, but there is not yet a repeatable setup to compare them.

### Goal
Create a test harness where both systems can be run and compared on:
- performance
- extraction quality
- effect on user experience

### Minimum outputs
- clear definition of both systems
- repeatable test setup
- per-run metrics
- summary comparison

### Suggested metrics
- latency
- success rate
- extraction precision and recall
- user time saved
- correction rate by annotators

### Done when
- both systems can be run through the same test path
- outputs can be compared side by side
- metrics are stored in a repeatable format
- contributors can rerun the comparison without manual spreadsheet work

## 7. Fix theme behavior

### Problems
- the app does not reliably follow system light or dark preference on login
- paper view can remain light while the rest of the app is dark

### Goal
Theme behavior should be consistent across:
- first load
- login
- refresh
- manual theme toggle
- PDF viewer

### Acceptance criteria
- default theme follows system preference when no saved override exists
- saved theme override is respected
- PDF area and app chrome stay visually in sync

### Likely technical area
- `apps/expert-annotator/src/hooks/useTheme.js`
- `apps/expert-annotator/src/index.css`
- PDF viewer styling

### Done when
- system preference is respected when no override exists
- saved override is respected after refresh and login
- app chrome and PDF area stay visually consistent

## 8. Fix reset password flow

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

## 9. (Arciel working on step 1) L1 discovery crawler with higher precision (paper extractor part 1)

### Problem
The current Europe PMC crawler finds useful food composition papers but still pulls too many related, non-usable papers.

### Goal
Build a simple-but-smart discovery crawler that raises precision without killing recall:
- tighten query templates and keep them few
- add journal/field filters where useful
- dedupe candidates and score consistently
- log per-query yield (results, accepted, rejected)
- prepare for multi-source inputs without exploding complexity

### Likely technical area
- `services/data-pipeline/food_paper_crawler/crawler_v2.py`
- `services/data-pipeline/food_paper_crawler/ranking.py`
- `services/data-pipeline/harvester/query_builder.py`
- `services/data-pipeline/harvester/relevance_filter.py`
- `services/data-pipeline/processing/validator.py`

### Sources to check when needed
- Europe PMC REST API: https://dev.europepmc.org/RestfulWebService
- OpenAlex API + data snapshots: https://docs.openalex.org/
- Semantic Scholar API + datasets: https://www.semanticscholar.org/product/api
- GROBID (structured PDF parsing): https://github.com/kermitt2/grobid
- pdfplumber (PDF text/tables): https://github.com/jsvine/pdfplumber
- Apache Tika (text/metadata extraction): https://tika.apache.org/

### Done when
- candidate pool precision improves vs the current baseline
- every run records per-query stats and acceptance rate
- the query budget is controlled and reproducible

## 10. (Depends on 9) L2 lightweight classifier for paper relevance (paper extractor part 2)

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

## 11. (Depends on 10) L3 feedback loop from UI labels to crawler/classifier (paper extractor part 3)

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

## 12. (Depends on 11) Add a global “definitely no data” red button (immediate skip + training)

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
