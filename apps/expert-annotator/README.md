# OpenNutri Expert Annotator

This app is the manual review interface for OpenNutri paper annotation.

Annotators use it to:
- open a paper PDF
- highlight nutrient mentions
- add food items and nutrient values
- save usable or unusable paper outcomes

## UI Notes

- Queue AI prefill is intentionally quiet: normalized Gemini rows are loaded directly into editable food/nutrient fields without a visible AI-prefill banner.
- Queue and Approval source navigation use the compact `Sources` strip; selected sources draw visible overlays for matched table/paragraph evidence and map printed journal page numbers to actual PDF pages when page labels can be detected.
- Avoid emoji-dependent controls in the main workflow. Use stable text labels or icon-only buttons with accessible labels.

## Stack

- React
- Vite
- `react-pdf`
- Supabase
- Vercel

## Local Development

```bash
npm install
npm run dev
```

## Production Build

```bash
npm run build
```

## Key Source Files

- `src/pages/Annotate.jsx`
  - main annotation workflow
- `src/components/PdfViewer.jsx`
  - PDF rendering and text-layer integration
- `src/utils/PdfTextScanner.js`
  - nutrient matching and highlight rendering
- `src/components/FoodAutocomplete.jsx`
  - food lookup and matching
- `src/components/NutrientAutocomplete.jsx`
  - nutrient lookup and matching
- `src/hooks/useTheme.js`
  - theme initialization and persistence

## Known Tricky Area

PDF text highlighting is not normal DOM text rendering.

`react-pdf` / PDF.js may:
- split a visible word into multiple spans
- create unexpected text boundaries
- make click handling harder than normal HTML text

The current viewer uses `react-pdf` `customTextRenderer` plus a page-local text-content analysis step.
Only detected table body/header cells and table caption/title lines are eligible for nutrient highlights.
Nearby prose, footnotes, legends, and pages without a confident local table anchor render with no nutrient highlights at all.
Cross-item phrase reconstruction is still not implemented, so matches split across multiple PDF text items inside a detected table will not highlight as one combined phrase.

If you change highlighting behavior:
- test simple words
- test comma-separated nutrient lists
- test words near punctuation
- preserve printed-page mapping for AI page hints such as `Page 95` in a six-page PDF
- test across several PDFs, not only one

## Cockpit Ops

The cockpit `Pipeline` tab is backed by `get_pipeline_ops_snapshot`. It displays the model cascade as stable role names with the current model spec in parentheses: `Small model (...)`, `Medium model (...)`, and `Strong model (...)`. Funnel counters are role/stage counters, not model-name counters; historical direct Small -> Strong tasks are backfilled into Medium-entered and Medium-kept counts. After schema changes, apply `migration.sql` before deploying the frontend so the tab can read crawler, stage-task, AI, and human-review aggregates.

## Deployment

This app is linked to a Vercel project through `.vercel/project.json`.

Typical production deploy:

```bash
npx vercel deploy --prod
```
