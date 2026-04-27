# OpenNutri Reviewer SOP (English)

Last verified: 2026-04-27 against the live reviewer surfaces in `apps/expert-annotator/src/pages/Annotate.jsx`, `apps/expert-annotator/src/components/PdfViewer.jsx`, `apps/expert-annotator/src/components/FoodItemForm.jsx`, `apps/expert-annotator/src/components/FoodAutocomplete.jsx`, `apps/expert-annotator/src/components/NutrientAutocomplete.jsx`, `apps/expert-annotator/src/components/NutrientPopover.jsx`, `apps/expert-annotator/migration.sql`, `services/data-pipeline/scripts/refill_assignment_queue.py`, and `services/data-pipeline/ai_routing.py`.

## What this work is

OpenNutri is building benchmark-quality food composition truth from scientific papers.

AI does not replace you. The live system still routes many papers to humans because benchmark truth depends on exact, database-shaped extraction payloads, not "close enough" interpretation. Final agreement is decided from exact canonical submission payloads, so small mistakes create real disagreements.

When a paper reaches your queue, it is already `human_review_ready`. That means it has passed ingest and AI routing and is waiting for human review.

You do **not** work from a shared global paper list. You work only from your personal `My Queue`.

## Non-negotiable rules

- Extract only what the paper explicitly reports.
- Keep the paper's real food groupings. Do not silently merge, split, or rename foods beyond what the table supports.
- Prefer matched foods and matched nutrients from autocomplete. Use custom names only when the exact catalog entry is missing.
- Do not silently convert unsupported bases such as `per serving`, `per 100 mL`, dry-weight basis, wet-weight basis, or similar alternate bases into `per 100g`.
- If you submit usable data, include real numeric nutrient rows. Do not send a "useful" submission that only has food names.
- Use `Definitely No Data` only when you are confident the whole paper is globally unusable for every reviewer lane.
- If you are unsure about policy, ask the owner instead of inventing a rule.

## Queue walkthrough

### `My Queue`

- `My Queue` is your personal assignment list.
- Assignment statuses in the live UI are `Assigned`, `Draft`, `Submitted`, `Conflict`, `Resolved`, and `Cancelled`.
- `Assigned` and `Draft` are editable.
- `Submitted`, `Conflict`, `Resolved`, and `Cancelled` are not editable in normal live review.

### PDF pane and nutrient popover

- The PDF pane shows the paper PDF and a page counter.
- Nutrient highlighting is precision-first and table-only. Some real nutrient mentions will intentionally **not** highlight, especially on continuation pages or prose-heavy pages.
- Click a highlighted nutrient name to open the popover.
- In the popover, enter the value, choose the unit, and click `+ Add`.
- Missing highlight is **not** proof that the row should be ignored. Read the table manually when needed.

### Food and nutrient entry

- Each `Food Item` card should represent one real food or table line grouping.
- The food search box is `Search food name...`.
- `✓ Matched` means the food is linked to a catalog food.
- `Custom` means you are using free text.
- Use `+ Add Another Food Item` only for a genuinely separate food item.
- Use `🔍 Add nutrient...` to add a nutrient row.
- If nutrient autocomplete has no correct option, pressing Enter creates a custom nutrient.
- Every nutrient row should end with a numeric `Value` and a valid unit.

### Save and final actions

- `Save Draft`: saves editable work and keeps the assignment open.
- `No Usable Data`: sends a final negative submission for your lane only.
- `Definitely No Data`: sends a global paper-level negative decision, requires a reason, cancels the other assignments, and finalizes negative truth immediately.
- `Submit Final Extraction`: sends a final usable extraction.

If the UI shows `This assignment is finalized. You can inspect it here, but new edits will not be saved.`, treat the paper as read-only.

If the UI shows `Developer training mode is read-only for annotation and admin actions.`, you are not in live reviewer mode.

## Practical submission contract

The live system stores reviewer truth in a strict payload shape. In practical reviewer terms:

### `decision_kind`

- `has_data` means the paper produced a usable extraction.
- `no_usable_data` means the paper did not produce a usable extraction.
- `No Usable Data` and `Definitely No Data` both end as `decision_kind = no_usable_data`.

### `food_items`

- A usable submission must contain one or more real food items.
- Each food item stores:
  - `food_name`
  - optional matched `food_fdc_id`
  - `is_custom_food`
  - a list of nutrient rows
- If you select a food from autocomplete, it becomes a matched food.
- If you leave it as free text, it becomes a custom food.

### Nutrient rows

- Each nutrient row stores:
  - `nutrient_name`
  - optional matched `nutrient_id`
  - numeric `value`
  - `unit`
- If you select a nutrient from autocomplete, it becomes a matched nutrient.
- If you use free text, it becomes a custom nutrient.
- Use one row per real food-nutrient value reported in the paper.

### Allowed units in the live UI

Use only these units:

- `g/100g`
- `mg/100g`
- `μg/100g`
- `kcal/100g`
- `kJ/100g`
- `IU/100g`
- `%`

### Basis rule

The reviewer UI does **not** have a separate basis field. The stored contract assumes the basis is already encoded in the unit.

Only enter a row when the paper already supports one of these cases:

- true `100g` / `100 g` / `per 100g` composition reporting
- true composition percentage that belongs in `%`

Do **not** silently convert these into supported units:

- `per serving`
- `per portion`
- `per 100 mL`
- dry-weight basis
- wet-weight basis
- sample basis
- any other unsupported basis

If a conversion seems tempting, stop and ask first.

## What to extract

Extract rows that meet **all** of these conditions:

- They are real food composition values.
- The paper gives a clear food-to-nutrient mapping.
- The value is numeric.
- The row can be represented in one of the supported units above.

Typical extractable examples:

- protein, fat, carbohydrate, ash, moisture
- energy
- vitamins
- minerals
- fatty acids
- amino acids
- other genuine composition analytes that fit the supported unit contract

## What not to extract

Do **not** extract these as nutrient rows:

- clinical outcomes
- blood markers
- digestibility or bioavailability measures
- antioxidant assays such as DPPH, FRAP, ORAC, IC50
- pH
- color values
- texture values
- viscosity
- yield or process-loss metrics
- sensory scores
- microbial counts
- rows with unsupported units or unsupported bases
- any value you had to invent, infer, or derive off-paper

Important nuance:

- `Moisture %` can be valid because `%` is a supported composition unit.
- `pH 3.4` is **not** valid because it is not part of the accepted composition contract.

## Choosing between the main actions

### Use `Save Draft` when

- you are still working through the paper
- the table continues across pages
- you need time to verify the right food grouping
- you are unsure whether a match should be canonical or custom

### Use `No Usable Data` when

Use it for your assignment when the paper does not yield a valid extraction for this lane, for example:

- the paper has no supported composition rows
- the paper only reports unsupported bases
- the paper only has assay or quality metrics
- the food-to-nutrient mapping is too unclear to extract safely
- the usable data is not actually present in the PDF you received

### Use `Definitely No Data` when

Use it only when the entire paper is globally unusable and the other reviewer lane should be cancelled now, for example:

- wrong paper type
- clinical or health-outcome paper with no original food composition data
- review paper with no extractable primary composition table
- non-food material
- broken or irrelevant document that clearly cannot produce usable review truth

Because this action cancels the other assignments and writes final negative truth immediately, do **not** use it for borderline cases.

### Escalate instead of using a negative action when

- one part of the paper looks usable but the basis is awkward
- you would need a conversion rule
- a continuation page is hard to map
- you cannot tell whether a metric is composition or not
- the correct food or nutrient match is unclear
- the UI appears to be hiding a row because of a highlight bug

## Escalation and outside research rules

Ask the owner instead of improvising when any of these happen:

- you need a unit or basis conversion
- you want to merge or split foods beyond the paper's explicit structure
- the paper uses a strange nutrient term and you are not sure whether it belongs in the benchmark
- two tables in the same paper appear to conflict
- the table structure is ambiguous enough that another reviewer could reasonably build a different payload

Outside research is allowed only as a temporary reading aid for obvious abbreviations or common terminology.

Outside research is **not** allowed to:

- fill missing values
- create new rows
- override what the paper actually says
- justify a silent conversion
- create a new labeling policy without approval

If outside research changes your judgment in a way that would affect the payload, stop and ask first.

## Common failure modes

- Wrong basis: entering `mg/100g` when the paper really says `mg/serving`.
- Continuation-page confusion: assuming a row ended because the next page did not highlight.
- Custom-name overuse: using free text before checking autocomplete carefully.
- Missed rows: stopping after a few headline nutrients even though the same food has more supported rows.
- Wrong food grouping: collapsing multiple cultivars, treatments, or sample variants into one food item.
- Empty useful submission: sending a food card without real nutrient rows.
- Unsupported metrics: extracting pH, color, texture, assay scores, or yield as if they were nutrients.

## Worked examples

### Good example

Paper table:

- `Apple peel`
- `Vitamin C 12.4 mg/100g`
- `Iron 0.3 mg/100g`
- `Moisture 81.2%`

Correct action:

- Create one food item for `Apple peel`.
- Match the food if the exact catalog food exists; otherwise use custom food text.
- Add three nutrient rows with the exact paper values and supported units.
- Submit with `Submit Final Extraction`.

### Bad example

Paper table:

- `Apple juice pH 3.4`
- `L* color 65.2`
- `DPPH inhibition 82%`

Correct action:

- Do **not** enter these as nutrient rows.
- If the paper has nothing else usable, choose `No Usable Data` or `Definitely No Data` depending on whether the whole paper is globally unusable.

### Borderline example

Paper table:

- `Banana flour protein 6.2 g/serving`
- `Banana flour iron 1.1 mg/100g`

Correct action:

- Keep the supported `iron 1.1 mg/100g` row.
- Do **not** silently convert `protein 6.2 g/serving`.
- If enough supported rows remain to form a real extraction, submit usable data with only the supported rows.
- If every row in the paper is unsupported like `per serving`, use `No Usable Data`.

## Final reminder

Your job is not to be clever. Your job is to produce the exact supported extraction that the paper and the live contract can defend.

When in doubt, ask before you create a rule that could affect benchmark truth.
