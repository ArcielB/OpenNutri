# OpenNutri Expert Annotator

This app is the manual review interface for OpenNutri paper annotation.

Annotators use it to:
- open a paper PDF
- highlight nutrient mentions
- add food items and nutrient values
- save usable or unusable paper outcomes

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

If you change highlighting behavior:
- test simple words
- test comma-separated nutrient lists
- test words near punctuation
- test across several PDFs, not only one

## Deployment

This app is linked to a Vercel project through `.vercel/project.json`.

Typical production deploy:

```bash
npx vercel deploy --prod
```
