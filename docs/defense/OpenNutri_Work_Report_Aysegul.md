# OpenNutri — Work Report: Ayşegül Doğan (221229031)

*Self-contained, code-grounded account of the annotator frontend work, written after reading the actual source files (named at the top of each section). Companion to the master report; numbers re-derived from git on 2026-06-05, HEAD `ac8bf72`.*

## At a glance

- **Area:** the entire annotator frontend — `apps/expert-annotator/src/**` (React 19 + Vite, deployed on Vercel).
- **~13,500 lines** of frontend ship in production today; **+22,681 / −7,581** lines of frontend churn over the project (net **+15,100**). The PDF viewer + scanner alone span **27 commits**.
- **Attribution rule:** Ayşegül authored the original MVP and core frontend under her own `ayseguldogan2706-cpu` identity; after the March reorganization into `apps/expert-annotator/`, most frontend evolution was committed through the team's shared integration machine, and by the team's standing division of labor **the frontend area is hers**. The ~450 lines that belong to Huan's features (fuzzy-match engine, reset-password, suggestion attachments) are excluded and covered in his report.
- **The headline finding from reading the code:** the frontend is **not** a thin layer. Its hardest subsystem — making a browser reconstruct table/column/paragraph structure from raw PDF glyphs and paint coordinate-accurate evidence overlays — is ~4,050 lines of genuine document-layout-analysis and is as substantial as any single backend subsystem. The two sections below were written after reading every substantive frontend file in full (~9,000 lines).

---
## PDF evidence subsystem — table detection, overlays, durable cache *(Ayşegül / frontend)*

**Files read in full for this section:** `utils/PdfTextScanner.js` (2,323), `components/PdfViewer.jsx` (939), `utils/EvidenceLocations.js` (439), `utils/pdfCache.js` (107), `hooks/useEvidenceStatusCache.js` (101), `utils/evidenceStatusCache.js` (139), `utils/evidenceDedupStorage.js` (44). **27 commits** to the viewer + scanner. ~4,050 lines that do **document layout analysis in the browser** — the single hardest piece of code in the project, frontend or backend.

### The core problem
PDF.js hands you a flat list of positioned glyphs — `{str, x, y, width, height}` — with no notion of a table, column, or paragraph. To (a) make nutrient names *inside tables* clickable and (b) paint an overlay over exactly the table/paragraph an AI value came from, the scanner must **reconstruct page structure from geometry**. `PdfTextScanner.js` is ~70 functions of computational geometry; `PdfViewer.jsx` renders and scales it; three cache layers make it fast and durable.

### Pipeline (`buildPageEvidenceHighlightPlan`)
Per page: `extractPositionedTextItems → buildPageMetrics → detectColumnGutters → groupItemsIntoRows(gutter-aware) → finalizeRow→createFragment → buildTableRegionsAndCaptionFallbacks → buildParagraphBlocks`, then an ordered **matcher cascade** per AI evidence location.

### Hard problem 1 — adaptive metrics (`buildPageMetrics`)
Every threshold derives from the page's own typography. `medianHeight` (glyph size) and `medianRowGap` drive `rowTolerance`, `fragmentGapThreshold`, `captionMergeGap`, `bodyGapThreshold`, `paragraphGapThreshold`, `bandMargin` — each `clamp()`-ed. The same code works on a 7 pt dense table and a 12 pt abstract with no hardcoded pixels.

### Hard problem 2 — column detection by projection profile (`detectColumnGutters`)
Multi-column journals merged columns into one "paragraph." The fix is a classic **vertical projection profile**, hand-written: bin the x-axis at **2 pt**, record which y-bands have ink per bin; a **gutter** is a run of bins where ≤ 8 % of bands have content, ≥ 6 pt wide; keep only gutters with **content on *both* sides** (distinguishing a real inter-column gutter from page margins). `finalizeRow` then splits a row into fragments whenever the inter-glyph gap exceeds `fragmentGapThreshold` **or crosses a gutter**, so a left-column and right-column line at the same y never fuse.

### Hard problem 3 — a per-fragment table/prose/narrative classifier (`createFragment`)
This is the engine's brain and was nowhere in my first pass. For each text fragment it computes a feature vector: numeric-token count, **sample-code** tokens (e.g. "T1", "Cv3"), abbreviation tokens, letter/lowercase/digit ratios, all-caps tokens, caption-prefix match ("Table N"), header tokens, unit labels, **major-cluster count** (`countMajorClusters`: gaps > 12 pt or wide whitespace), sentence punctuation, narrative connectors. From those it derives `looksProseLike`, `looksNarrativeLike`, and an integer **`tableScore`** (header +3, unit +2, all-caps-short +2, ≥2 numerics +2, digit-ratio +1, sample-code +1, ≥2 abbreviations +2, …) → `isTableLike = tableScore ≥ 2`. So each fragment is classified as table-cell vs prose vs caption from its own shape — a hand-built text classifier running per glyph-run.

### Hard problem 4 — caption-anchored table-region growth (`buildCaptionBlocks` → `buildTableRegionForCaptionBlock` → `selectFragmentsForTableRow`)
Tables are found from their captions: caption-anchor fragments ("Table N") are merged across continuation lines (`extendCaptionBlock`), then the region grows **downward** row by row while rows overlap the caption band and stay within `bodyGapThreshold`. `selectFragmentsForTableRow` decides per row which fragments are body cells: it keeps `isTableLike` fragments, recognizes **header-like rows** (all short-header fragments under a word limit), and — crucially — once a data-like row is accepted it **keeps accepting later data-like rows even if they don't individually score `isTableLike`** ("Nd" or a lone "1.50" only scores 1 alone but is plainly table body in context). A region is `isConfident` only with ≥ 2 body rows OR bodyScore ≥ 4 OR a data-like fragment; otherwise it degrades to a **caption-only fallback** so a table-cited source still highlights *something* (the caption line) instead of nothing.

### Hard problem 5 — paragraph blocks + interleaved-data merging (`buildParagraphBlocks`, `mergeAdjacentParagraphBlocks`)
Prose lines (excluding table items and document chrome via `isDocumentChromeFragment`) become paragraph candidates (`isParagraphCandidateSegment`: ≥ 5 words, ≥ 8 letters, lowercase ratio ≥ 0.35, punctuation, no sample codes), grown greedily into blocks then **clipped to the dominant column**. A second pass (`mergeAdjacentParagraphBlocks`) re-joins blocks that a stray interleaved numeric line split apart — it walks the rows between two same-column blocks and merges only if every gap is small and each intervening row is a `isParagraphInternalDataRow` (not a table, header, or chrome). This is why a paragraph quoting "22.04 ± 1.25 g/100 g" mid-sentence still resolves to one overlay.

### Hard problem 6 — robust column clipping with MAD (`clipEntriesToDominantColumn`)
Even with gutters, PDF.js sometimes fuses two columns into one wide fragment. The clipper computes the **median** left/right edge and a **median absolute deviation (MAD)** spread, fences outliers at `3×MAD` (asymmetric — looser lower-right fence because paragraph last lines are legitimately short), and the code comments justify MAD over IQR ("IQR would absorb the outlier into q3"). Textbook robust statistics applied to layout.

### Hard problem 7 — the source-quote matcher (3-tier cascade, `findSourceQuoteTextMatch`)
The AI's verbatim `source_quote` is located by: **paragraph-fragment match** → **search-fragment match** (`groupFragmentsByColumn` clusters fragments into columns so a windowed scan of up to 6 adjacent fragments is actually visually adjacent) → **row-window match** (up to 4 rows). Each tier falls back through `expandFragmentsToParagraph` / `expandRowsToParagraph` + `clipEntriesToDominantColumn` + `snapToNearestParagraphBlock` (reuse the nearest same-column block's id/bounds within 60 pt, so near-misses share a stable dedup identity). `normalizeSearchText` inserts whitespace at **digit↔letter boundaries** (Unicode-aware) on both sides so "10.80g/100 g" matches "10.80 g/100 g".

### Hard problem 8 — the lying `page_hint` (`buildPageEvidenceHighlightPlan` + `resolvePrintedPageHint`)
The AI reports `page_hint` from extracted text, so on an offprint it gives the *printed* page (e.g. 1217 on a 5-page file). When `hintExceedsPages` (`pageHint > numPages`) the hint is made **non-gating** so caption/quote matchers can locate evidence on any page. And `PdfViewer.resolvePrintedPageHint` builds a **histogram of printed-vs-PDF page offsets** across every scanned page and maps the hint via the *modal* offset — so even a page whose header wasn't detected resolves to the right PDF page (`mapped_page_hint`).

### Hard problem 9 — stable overlays + de-duplication (union-find, twice)
`unifyOverlappingParagraphMatches` runs **union-find with path compression** over a page's paragraph matches, collapsing any pair with ≥ 50 % horizontal overlap and a small vertical gap into one `regionKey` + unioned bounds. `buildStableRegionKey` keys by a stable `regionId` (else rounded bounds) so overlays don't flicker between renders. `EvidenceLocations.mergeQuoteOverlappingLocations` does a *second* union-find at the source level, merging two sources whose quotes share a **longest-common-substring ≥ 40 chars or ≥ 60 % of the shorter** (`longestCommonSubstringLength`, a two-row DP) — so three AI rows citing the same paragraph become one chip and one overlay.

### `PdfViewer.jsx` (939) — headless scan + evidence-first rendering
Far more than a `<Document>` wrapper:
- **Self-hosted PDF.js worker** via `new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url)` — a Vite-bundled, content-hashed, same-origin asset instead of an unpkg-CDN serial dependency on the critical path.
- **Headless evidence scan:** a `useEffect` reads each page's text + intrinsic size straight from the parsed `PDFDocumentProxy` **without rendering its canvas**, yielding between pages with `requestIdleCallback`. This precomputes highlight plans for every page, sizes placeholders so scroll is stable before anything rasterizes, and learns which pages hold evidence.
- **Evidence-first rendering:** `activePages` = page 1 ∪ evidence pages ∪ (all pages once the scan completes), so page 1 paints instantly, evidence pages render next, the rest backfill — while DOM order stays 1..N with placeholders.
- **Coordinate transform:** `buildOverlayForRegionBounds` scales PDF bounds to rendered pixels (`scaleX = pageWidth/originalWidth`), **flips the Y axis** (PDF origin bottom-left → screen top-left via `originalHeight - pdfTop`), and applies type-specific padding (table 14 px, paragraph 6/2 px). `mergeNearbyOverlays` is a third merge pass at the pixel level. `scrollPageRegionIntoView` centers the overlay region in the viewport with exact scroll math.
- **`customTextRenderer`** injects clickable nutrient `<mark>`s only on items inside a detected table **and not inside a matched evidence region**; `bindNutrientHighlightInteractions` resolves the clicked mark through **three strategies** (`closest` → `elementsFromPoint` → `caretPositionFromPoint`) so clicks land even through overlapping text layers.

### Three cache layers — durable, instant, shared
- **`pdfCache.js`** — PDF bytes in the **Cache Storage API** (not the volatile HTTP cache, which evicts 25 MB PDFs and which Supabase serves `no-cache`), keyed by URL, with an **LRU index in localStorage** (cap 40), a fresh `ArrayBuffer` per call (safe against PDF.js detaching on transfer), and `prefetchPdf` for idle warming. `QueueView` prefetches the **next two** queue papers during idle.
- **`evidenceStatusCache.js` + `evidenceDedupStorage.js` + `useEvidenceStatusCache.js`** — the resolved match for each source (regionKey + bounds + page) is cached **per paper, locally (localStorage, LRU 64) *and* remotely** in a Supabase `paper_evidence_dedup` table via the `merge_paper_evidence_dedup` RPC. On re-open, `applyCachedDedup` collapses sources that previously resolved to the same region **without re-scanning**, and `buildCachedEvidenceOverlays` paints overlays from cache **before** the headless scan even finishes — so a paper anyone has reviewed opens with overlays already in place.

### Trade-offs
- **Precision over recall:** suppress highlighting rather than guess (a nutrient word in prose never becomes a stray click target); multi-item-fused table cells are a known follow-up.
- **All geometry client-side:** ~2,300 lines of layout analysis run in the browser — no server round-trip, works on any open-access PDF.
- **Heuristic, but adaptive:** thresholds are tuned against real journal PDFs across 27 commits, clamped and median-derived rather than fixed.
## Annotator app — orchestration, autocomplete, workflow, cockpit *(Ayşegül / frontend)*

**Files read in full for this section:** `pages/Annotate.jsx` (1,163), `utils/annotateHelpers.js` (574), `components/FoodAutocomplete.jsx` (664), `components/NutrientAutocomplete.jsx` (334), `components/NutrientPopover.jsx` (128), `components/FoodItemForm.jsx` (110), `components/AiDetailPanel.jsx` (118), `components/EvidenceStrip.jsx` (54), `views/{QueueView,ApprovalView,DashboardView,AllPapersView,PipelineOpsView}.jsx`, `utils/searchSessionLogger.js` (110), `hooks/useTheme.js` (75), `App.jsx`, `pages/Login.jsx`. ~4,300 lines.

### `App.jsx` + `useTheme` — shell, auth, theme
`App` checks the Supabase session, detects a **recovery URL** (`type=recovery` in hash/query or `/reset` path, or a `PASSWORD_RECOVERY` auth event) and routes to `ResetPassword`, else `Login`, else `Annotate`. `useTheme` resolves `override || systemTheme`, listens to `prefers-color-scheme` via `matchMedia`, writes `data-theme` in a `useLayoutEffect` (no flash), and persists the override in **`sessionStorage` only when it differs from the system theme** — clearing it otherwise, so the app follows the OS by default and the override is per-session. `Login` does email/password, **Google OAuth**, and `resetPasswordForEmail`.

### `Annotate.jsx` (1,163) — the orchestrator
Owns ~30 state hooks, all data fetching, view routing, and every labeling action. Its design is shaped by the same free-tier egress limit as the backend:
- **Parallel boot, no waterfall:** the queue loads on mount in parallel with the reviewer-profile sync (`sync_reviewer_profile` RPC) rather than after it; the shell paints immediately (no full-screen gate).
- **One-RPC queue with a versioned fallback:** `refreshQueue` calls `get_general_queue_cards` (lean cards + latest AI payload + this user's annotation status in one round-trip); if the RPC isn't deployed (`PGRST202`) it transparently falls back to `loadQueueItemsLegacy` (three queries: papers RPC + AI extractions + annotations).
- **Lazy cockpit:** `refreshCockpit` (10 parallel queries) runs **only on first visit to a cockpit tab** (`COCKPIT_DATA_VIEWS`), not on login, so cockpit accounts still get a fast Queue.
- **Idle food-catalog load:** the full `entities` catalog is fetched **paginated (1,000-row batches) during `requestIdleCallback`**, so the heavy autocomplete data never blocks first paint.
- **AI-prefill without overwrite (`loadAnnotation`):** a queue paper with no saved draft opens with its latest `normalized_payload_json` converted to editable rows via `buildFoodItemsFromPayload`, recording the source extraction id in `aiPrefillSources`; an existing draft/submission is loaded from the DB instead and **never overwritten**.
- **Submit + approve paths:** `saveAnnotation` validates (≥ 1 food item; ≥ 1 nutrient row for a final submit), writes annotation + food/nutrient rows (`saveAnnotationRows`: upsert annotation, delete-then-insert children), logs a `paper_label_events` row, and calls `submit_general_label`. `approveSelectedSubmission` (approvers only) writes the corrected rows and calls `approve_label_submission`. Every write is **test-mode aware** — in test mode it appends to a local event log instead of touching Supabase.
- **Help + suggestions:** `submitHelpRequest` builds a `buildGeneralHelpContext` record (paper + AI + reviewer + draft food items) into `backlog_review_items`.

### `annotateHelpers.js` (574) — the shared brain
Two pieces are substantial:
- **Payload normalization** (`normalizeFoodItem`, `buildFoodItemsFromPayload`, `isValidFoodItem`, `normalizeOptional*`) — the client-side mirror of the SQL `build_annotation_submission_payload` and the Python `normalize_ai_payload`. The **same shape on all three sides** is what makes AI output, human drafts, and stored truth interchangeable and hash-comparable.
- **The pipeline funnel** (`buildPipelineSteps`, `formatModelSpecification`, `getPipelineModelStageViews`) — builds the cockpit's 10-stage funnel (search → filter → upload → small/medium/strong start+kept → human) with **role-stable labels** (`Small model (Gemma 31B)`), choosing batch counts over hit counts when available, and applying the **legacy Medium-stage backfill** (`legacy_direct_strong_without_medium`) so historical Small→Strong papers don't make the middle stage start at zero. `formatModelSpecification` maps model ids to display names with regex fallbacks so a model swap changes only the spec in parentheses. Plus `getPublicPdfUrl` (routes every external PDF through the `/api/pdf` proxy for CORS + immutable cache), `getAiPrefillStats`/`getNormalizationSummary`, `countCorrectionItems` (renders `correction_diff_json`), and the status/routing formatters.

### `FoodAutocomplete` + `NutrientAutocomplete` — domain-tuned IR on top of Huan's fuzzy engine
Both import Huan's `fuzzyMatch` (tokenizer, inflection, banded Levenshtein) and add a weighted scorer. `scoreFoodMatch` (664-line component) ranks over canonical name, an extracted base name, and aliases:
- Exact = +2000/+1700/+1600; prefix = +900/+1200/+800; first-token = +180/+260/+180.
- **Per-token relation scoring** — `exact`/`derived`(stem)/`fuzzy`(edit-distance) at different weights, **boosted for single-word "generic" queries**.
- Coverage +260 if all tokens match, −180 per unmatched, −35 × earliest position; length penalties to prefer concise base names.
- **Whole-food disambiguation:** for generic queries, penalize `PROCESSING_WORDS` (canned/dried, −55 each), processed-primary pairs (−180), `babyfood`/`restaurant` (−180), derived-prefix false friends (−140); reward `WHOLE_FOOD_HINTS` and base-name matches (+220) — so "apple" surfaces *Apple, raw* over *Apple juice, canned*. A generic query with no useful token overlap is hard-rejected (−9999).
- **Data path:** when the in-memory catalog is loaded it ranks locally; before that it runs a **two-query Supabase strategy** (a prefix `ilike` of token variants + a broad `ilike`) merged and ranked. Debounced 250 ms, full keyboard nav, custom-food on blur/Enter. `NutrientAutocomplete` mirrors this (alias-weighted, skips "proximates"/"minerals"/"do not use") and maps units via `formatUnit`. Both log resolution to `search_sessions`.
- **`searchSessionLogger`** records each query step + a snapshot of shown options, persists a session on resolve/abandon to `search_sessions` (or a local event in test mode), and **self-disables** if the table is missing (`PGRST205`). This is the search-UX telemetry feeding model/UI work.

### The clickable bridge (`NutrientPopover`, `FoodItemForm`)
A click on a highlighted nutrient in the PDF opens `NutrientPopover`, which **positions itself viewport-aware** (below the anchor, clamped to the viewport, flipped above if no room), focuses the value input, closes on Escape/outside-click, and emits a nutrient row that `handlePdfNutrientAdd` appends to the first food item (deduped by id). `FoodItemForm` composes `FoodAutocomplete` + dynamic nutrient rows + `NutrientAutocomplete` into one food card.

### The views (8, extracted from a once-monolithic `Annotate.jsx`)
- **`QueueView`** — the labeler workspace: `PdfViewer` + `FoodItemForm`s + `EvidenceStrip`, builds evidence locations from the current rows (falling back to the AI payload), drives the durable evidence-status cache, auto-focuses the first evidence on load, **prefetches the next two PDFs on idle**, and the action bar (Ask for Help / No Usable Data / Save Draft / Submit Reviewed Data) with a read-only banner for testers.
- **`ApprovalView`** — side-by-side `PayloadSummary` (original labeler submission) vs an **editable** Reviewer Final Payload, decision select, approval note, gated to approvers (read-only preview otherwise).
- **`DashboardView`** — labeler-performance metrics computed client-side from submissions + approvals (submitted/pending/accepted/**corrected**/superseded/**correction items** via `countCorrectionItems(correction_diff_json)`), plus a per-submission "mistake detail" table.
- **`AllPapersView`** ("Useful Papers") — routing/AI/submission/approval/outcome table filtered by `shouldShowPaperInUsefulOverview` (hides provisional skips), with an expandable **`AiDetailPanel`** showing confidence, accepted/input rows, DB-vs-custom food/nutrient counts, the **rejection-reason histogram**, the DB-compliant rows, and the normalized JSON — exactly the normalization summary, *not* the model's reasoning.
- **`PipelineOpsView`** — renders `buildPipelineSteps` as a funnel (bars, % retained, dropped counts) plus a "Right Now" grid of per-stage queued/processing counts and human-ready/approval/failed, with a time-range filter.
- Plus `ReviewerAdminView`, `SuggestionsReviewView`, `MySuggestionsView`.

### Trade-offs
- **Triple-encoded payload shape** (JS + SQL + Python): duplicated normalization kept in lockstep so the three producers of truth stay comparable.
- **Egress-driven architecture:** one-RPC queue + lazy cockpit + idle catalog load + slim cockpit projections — more client coordination in exchange for staying inside the Supabase free tier.
- **Heuristic, weight-tuned ranking:** the autocompletes are tuned constants rather than a learned model — fast and debuggable at this catalog size, hand-maintained.
