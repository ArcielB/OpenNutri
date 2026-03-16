# OpenNutri — Feature Explanations

## Short (High-Level)

1. PDF handling + storage
What it is: PDFs are stored in Supabase Storage and shown in the app.
How it works: The UI builds a public URL and renders the file with React PDF (PDF.js).

2. Nutrient highlighting in PDFs
What it is: Nutrient names are highlighted directly inside the PDF text.
How it works: The app scans the PDF text layer and wraps matches with highlight markup.

3. Fuzzy nutrient matching
What it is: Nutrient search tolerates imperfect input.
How it works: The matcher normalizes tokens and scores exact, prefix, and derived matches.

4. Nutrient popover quick-add
What it is: A click-to-add panel for nutrient values.
How it works: Clicking a highlight opens a popover to enter value/unit and add it to the current food item.

## Medium (Teacher-Level)

1. PDF handling + storage
What it is: The system stores PDFs centrally and streams them in the annotator UI.
How it works: The `papers` table stores filenames. The UI builds a public URL from Supabase Storage (bucket: `papers`) and passes it to `PdfViewer`.
The PDF is rendered using `react-pdf` (PDF.js). Wiring is in `apps/expert-annotator/src/pages/Annotate.jsx` and `apps/expert-annotator/src/components/PdfViewer.jsx`.

2. Nutrient highlighting in PDFs
What it is: Visual highlights on nutrient terms inside the PDF.
How it works: When a page renders, the app inspects PDF.js text layer spans and runs a nutrient matcher.
Matched substrings are wrapped with `<mark>` elements and dataset attributes for nutrient metadata.
Logic is in `apps/expert-annotator/src/utils/PdfTextScanner.js` with boundary-safe regex to avoid partial-word errors.

3. Fuzzy nutrient matching
What it is: A tolerant search that finds nutrients even with small variations.
How it works: The search normalizes case/punctuation, handles singular/plural forms, checks aliases in parentheses, and scores exact/prefix/derived matches. This scoring controls the order of suggestions shown in the dropdown.
The logic is in `apps/expert-annotator/src/components/NutrientAutocomplete.jsx`.

4. Nutrient popover quick-add
What it is: A small input panel for adding nutrient values quickly.
How it works: Clicking a highlighted nutrient opens a popover positioned near the clicked text.
The user enters value/unit and adds it to the current food item.
UI logic is in `apps/expert-annotator/src/components/NutrientPopover.jsx` and state updates are wired in `apps/expert-annotator/src/pages/Annotate.jsx`.

## Long (Full Explanation)

1. PDF handling + storage
What it is: A storage + rendering pipeline so annotators can view PDFs in-browser.
How it works: PDFs are stored in Supabase Storage (bucket: `papers`) and referenced in the `papers` table by filename.
In `apps/expert-annotator/src/pages/Annotate.jsx`, the filename is converted to a public URL via `supabase.storage.from('papers').getPublicUrl(...)`.
That URL is passed into `apps/expert-annotator/src/components/PdfViewer.jsx`, which renders the document using `react-pdf` (PDF.js).
The PDF.js text layer is required so the app can inspect and highlight text spans.

2. Nutrient highlighting in PDFs
What it is: In-PDF highlighting of nutrient terms.
How it works: The core logic is in `apps/expert-annotator/src/utils/PdfTextScanner.js`.
`buildNutrientMatcher` creates regex patterns for each nutrient, skipping generic groups like “proximates” and “minerals”.
`buildBoundaryRegex` enforces word boundaries to prevent partial-word highlights.
`highlightNutrientsInTextLayer` scans each text span (including `span[role="presentation"]`), collects matches, and replaces span content with a fragment.
Matched ranges are wrapped in `<mark>` elements; overlaps are resolved so longer matches win.
Click handling uses `pointerup`/`click` plus fallbacks (`elementsFromPoint`, caret APIs) to resolve which highlight was clicked reliably.

3. Fuzzy nutrient matching
What it is: Search that stays accurate for spelling/inflection variants.
How it works: The ranking logic is in `apps/expert-annotator/src/components/NutrientAutocomplete.jsx`.
`normalizeText` and `tokenize` standardize case, punctuation, and spacing.
`normalizeToken` handles pluralization and irregular forms (for example, mice → mouse).
Aliases in parentheses are extracted and scored in addition to the main name.
`scoreNutrientMatch` assigns weights for exact, alias, prefix, and derived token matches and penalizes missing tokens.
This yields robust matching without external libraries or ML models and determines the ordering of suggestion options shown to the user.

4. Nutrient popover quick-add
What it is: A lightweight data-entry panel tied to highlighted text.
How it works: The popover UI is in `apps/expert-annotator/src/components/NutrientPopover.jsx`.
It positions itself near the clicked highlight using `getBoundingClientRect()`.
It focuses the input on open, closes on outside click or Escape, and formats default units for display.
On confirm, it returns `{id, name, value, unit}`.
In `apps/expert-annotator/src/pages/Annotate.jsx`, `handlePdfNutrientAdd` inserts the nutrient into the current food item and prevents duplicates.
