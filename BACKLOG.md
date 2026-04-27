# Backlog

This backlog is written so a new contributor can understand each item without extra context.

How to use this backlog:
- each item should be understandable without asking for hidden context
- if you take an item, reproduce the problem first
- prefer small, testable changes
- if you discover extra edge cases, add them under the item instead of rewriting its scope silently

## 10. Calibrate AI routing thresholds from audited human truth

### Problem
The new AI routing stage now stores confidence, routing bucket, audit sampling, and eventual paper outcomes, but the thresholds are still manual.

### Goal
Add a safe threshold-tuning workflow that uses only papers which eventually received human truth:
- recompute on a fixed cadence or batch size, not paper-by-paper
- keep separate positive and negative calibration
- optimize for precision floors, not raw accuracy
- require a minimum recent audited sample before any threshold move
- cap each move size to avoid oscillation

### Likely technical area
- `services/data-pipeline/scripts/`
- `services/data-pipeline/food_paper_crawler/feedback/`
- `apps/expert-annotator/src/pages/Annotate.jsx`

### Done when
- the tuner reads audited human-reviewed outcomes only
- thresholds stay scoped per stage/model
- every automatic threshold change is explainable from stored routing provenance

## 3. Train and integrate the L2 classifier (depends on label volume)

### Problem
Once labels exist, we need a trainable classifier so L2 can learn from feedback instead of only rules.

### Goal
Train a lightweight classifier on embeddings and integrate it into the pipeline:
- linear classifier (logistic regression) on top of embeddings
- probability output with configurable threshold
- model artifact versioned and reloadable
- evaluation on a fixed holdout split

### Likely technical area
- `services/data-pipeline/food_paper_crawler/`
- `services/data-pipeline/food_paper_crawler/training/`

### Sources to check when needed
- scikit-learn text classification pipeline: https://scikit-learn.org/1.3/tutorial/text_analytics/working_with_text_data.html
- fastText supervised classification: https://fasttext.cc/docs/en/supervised-tutorial.html

### Done when
- classifier training is repeatable from labeled data
- crawler uses the classifier before downloading PDFs
- per-run metrics include classifier precision/recall






## 4. (Later, depends on 3 + label volume) L2 fine-tuned multilingual transformer (XLM-R)


### Problem
The embedding + classifier baseline may miss nuanced language cues or underperform on multilingual edge cases once more labels accumulate.

### Goal
- optional upgrade for higher ceiling; not required for multilingual coverage
Fine-tune a multilingual transformer (XLM-R) for relevance classification and compare it against the embedding baseline:
- trained on the growing labeled set
- evaluated on a fixed holdout split
- only adopted if it improves precision/recall meaningfully

### Likely technical area
- `services/data-pipeline/food_paper_crawler/`
- new `services/data-pipeline/food_paper_crawler/training/` scripts

### Done when
- XLM-R beats the embedding baseline on the holdout set
- the model can be swapped in via config








## 7. Improve PDF highlight recall inside detected table regions

### Problem
PDF nutrient highlighting is now intentionally limited to detected table body/header cells and caption/title lines only. That fixed the false positives in nearby prose, but some legitimate table matches are still missed.

### Remaining limits to solve
- nutrient names split across multiple PDF text items inside the same detected table row do not reconstruct into one highlight
- captionless continuation pages are suppressed entirely, even when the next page is obviously the rest of the same table

### Likely technical area
- `apps/expert-annotator/src/components/PdfViewer.jsx`
- `apps/expert-annotator/src/utils/PdfTextScanner.js`

### Goal
Improve recall without undoing the precision-first rule that prose, footnotes, legends, and ambiguous pages must stay unhighlighted.

### Acceptance criteria
- cross-item nutrient phrases inside detected table regions can highlight cleanly
- safe continuation-page support is added only when the table region can still be identified confidently
- surrounding prose still never becomes highlight-eligible again
- click-to-open nutrient popover still works

### Notes
- keep the table-only allowlist model
- if a continuation-page heuristic is not clearly reliable, suppress highlights instead of expanding scope

### Done when
- detected table rows can highlight split nutrient phrases that currently fall between PDF text items
- clearly confident continuation pages can opt in without page-wide matching
- ambiguous pages still render with no nutrient highlights








## 8. Improve fuzzy matching logic

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








## 9. (Depends on 8) Use improved fuzzy matching in PDF highlighting

### Problem
PDF highlighting uses term matching that does not benefit from improved fuzzy logic, which can miss or mis-rank matches.

### Goal
Apply the improved fuzzy logic from item 6 to highlight matching in the PDF text layer.

### Likely technical area
- `apps/expert-annotator/src/components/PdfViewer.jsx`
- `apps/expert-annotator/src/utils/PdfTextScanner.js`
- `apps/expert-annotator/src/utils/fuzzyMatch.js`

### Done when
- PDF highlights align with improved fuzzy match ranking
- existing exact matches continue to work










## 13. Add conflict resolution table + view

### Problem
Conflicting labels can be derived from existing tables, but there is no place to store a reviewer decision, status, or notes.

### Goal
Add a lightweight resolution table (plus a conflict view/query) so conflicts are reviewable and resolvable without mutating label history.

### Likely technical area
- `apps/expert-annotator/migration.sql`
- Supabase views / queries for conflict detection
- UI (admin or reviewer view)

### Done when
- conflicts are derivable via a consistent query or view
- a reviewer decision can be stored per paper (with resolved_by + timestamp)
- the decision can be read without scanning past label events

