# OpenNutri Labeler Quick Guide

Use this guide while reviewing papers in the OpenNutri annotator.

Your job is simple: read the paper, review the prefilled AI extraction when it appears, correct it, and keep only the values that the paper clearly reports.

## The Standard

- Extract exact food names, nutrients, values, and units from the paper.
- Do not guess missing values.
- Do not calculate or convert values unless Arciel has explicitly told you to.
- Do not use outside sources to add data.
- If the table is unclear, ask instead of improvising.

Everyone works from the same available paper list. Once someone submits a paper, it leaves the visible queue and Arciel reviews the submitted result.

## Basic Workflow

1. Open a paper from `Queue`.
2. Read the title, abstract if needed, and the PDF tables.
3. Decide whether the paper has usable food composition data.
4. If AI-prefilled food items and nutrient rows appear, review and edit them. If no AI rows appear, enter the usable rows yourself.
5. Use `Save Draft` if you are not finished.
6. Use `Submit Final Extraction` only when the extraction is complete.
7. Use `No Usable Data` only when the paper has no usable rows.
8. After you submit, Arciel reviews and accepts the final version. Your original submission is kept for performance review.

You do not need to cross-check another labeler. Arciel handles final approval and corrections.

## What Counts as Usable Data

A row is usable when all of these are true:

- It is about a real food or food product.
- It reports a real food composition value.
- The food and nutrient are clearly connected.
- The value is numeric.
- The unit and basis fit the allowed options below.

Common usable nutrients include:

- protein, fat, carbohydrate, ash, moisture
- energy
- vitamins
- minerals
- fatty acids
- amino acids

## Allowed Units

Only use these units in the app:

- `g/100g`
- `mg/100g`
- `μg/100g`
- `kcal/100g`
- `kJ/100g`
- `IU/100g`
- `%`

Use `%` only for real composition percentages such as moisture, ash, protein, fat, carbohydrate, or similar composition values.

## Basis Rule

Only enter values that are already reported as per 100 g, per 100g, per 100 grams, or as a valid composition percentage.

Do not enter rows reported as:

- per serving
- per portion
- per sample
- per 100 mL
- dry-weight basis
- wet-weight basis
- any basis you would need to convert

If the paper has both supported and unsupported rows, enter only the supported rows.

## Food Items

Create one `Food Item` for each food, cultivar, treatment, sample type, or product that the table reports separately.

Use the food search first. If the correct food appears, select it. If it does not appear, type the paper's food name as a custom food.

Do not merge different rows just to simplify the work. For example, do not combine raw apple, dried apple, apple peel, and apple pulp unless the paper itself reports them as one food.

## Nutrient Rows

For each food item, add every usable nutrient value that belongs to that food.

Each nutrient row needs:

- nutrient name
- value
- unit

Use nutrient search first. If the correct nutrient appears, select it. If it does not appear, use the paper's nutrient name as a custom nutrient.

Do not enter a nutrient row if the value is missing, unclear, only shown as a range without a single usable value, or not tied to a specific food.

## PDF Highlights

Highlighted nutrient names are only a helper.

Use them when they are correct, but still read the table yourself. A missing highlight does not mean the row should be skipped.

## Do Not Extract

Do not enter these as nutrient rows:

- clinical outcomes
- blood markers
- digestibility or bioavailability results
- antioxidant assays such as DPPH, FRAP, ORAC, IC50
- pH
- color values such as L*, a*, b*
- texture, viscosity, hardness, yield, or sensory scores
- microbial counts
- processing losses
- values from another source cited by the paper
- values you calculated yourself

## Button Meanings

`Save Draft`

Use this when you are still working. Drafts can be edited later.

`Submit Final Extraction`

Use this when the paper has usable data and all usable rows have been entered.

`No Usable Data`

Use this when the paper does not contain any rows you can safely enter.

If you are unsure, use `Save Draft` and ask.

## When to Ask

Use `Ask for Help` before submitting when:

- you would need to convert units or basis
- you are unsure whether a table is food composition data
- a table continues across pages and the mapping is unclear
- a food grouping is unclear
- a nutrient name is unfamiliar and search does not help
- supported and unsupported data are mixed in a confusing way
- the PDF or UI appears broken

## Examples

### Good

Table reports:

- Apple peel
- Vitamin C: 12.4 mg/100g
- Iron: 0.3 mg/100g
- Moisture: 81.2%

Enter one food item for `Apple peel` and three nutrient rows.

### Not Usable

Table reports:

- pH: 3.4
- L* color: 65.2
- DPPH inhibition: 82%

Do not enter these rows. If the paper has nothing else, use `No Usable Data`.

### Mixed

Table reports:

- Banana flour protein: 6.2 g/serving
- Banana flour iron: 1.1 mg/100g

Enter only `iron 1.1 mg/100g`. Do not convert `protein 6.2 g/serving`.

## Final Check Before Submitting

Before `Submit Final Extraction`, confirm:

- every food item is a real row or group from the paper
- every nutrient value is numeric and visible in the paper
- every unit is one of the allowed units
- no unsupported basis was converted
- no pH, color, texture, assay, clinical, or sensory values were entered
- all usable rows were included
