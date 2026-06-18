# Working On

This file narrows context for agents working on the current OpenNutri task. Read it after the mandatory startup files and fresh `git fetch` / `git status` check.

## Active Task

Current task: strengthen the TUBITAK 1005 main application form content without changing the official template structure.

The immediate work is point 2 from the grant review discussion: use the remaining page budget in the main form for the highest-ROI content improvements, mainly in feasibility, validation/statistics, Turkish food-data gap evidence, and commercialization/pilot clarity.

## Always Read First

These are mandatory for every OpenNutri task, before task-specific exploration:

- `/home/arciel/#AgentFiles/INSTRUCTIONS.md`
- `/home/arciel/#AgentFiles/AGENTS.md`
- `INSTRUCTIONS.md`
- `AGENTS.md`
- Run `git fetch origin` and check `git status --short --branch`

## Read For This 1005 Grant Task

Read these files for the current proposal/doc-template work:

- `working_on.md`: this scope guide.
- `/home/arciel/#AgentFiles/findings_2026-06-18_1005_template_package.md`: current verified template/export facts.
- `OpenNutriLatestVersion.md`: source of the main application narrative. Edit this for main-form content.
- `docs/export_1005_application_template.py`: source-to-template mapping and export behavior. Read before changing output structure.
- `docs/proposal-sections/template_1005_reference.md`: concise reference for official 1005 section requirements.
- `docs/handoff_2026-03-20/STATE.md`: read only the high-signal project/prototype evidence sections, especially Primary Goal, Active Workflow, Frontend Status, AI Routing, and Ops.
- `README.md`: read only the pipeline/current ops section around the staged model cascade if current implementation evidence is needed.

## Read Only If Needed

- `OpenNutri_EK2_Butce.md`: budget narrative source; only needed for EK-2 or budget consistency.
- `docs/proposal-sections/*.md`: older draft material; useful for comparison, but much of it has placeholders or English scaffold text. Do not restore wholesale.
- `FoodData_Central_*/food.csv`: only for cautious local string checks when adding Turkish food-gap examples.
- Official untracked templates:
  - `1005_basvuru_formu (7).doc`
  - `1005_basvuru_formu_ek1_kaynaklar_31.07.2018 (4).doc`
  - `ek-2_butce_ve_gerekcesi_tablosu_1005.docx`

## Do Not Read By Default

Do not spend context on these unless the user explicitly redirects to app/pipeline work:

- `apps/expert-annotator/**`
- `services/data-pipeline/**`
- `docs/defense/**`
- `legacy/**`
- `FoodData_Central_*` beyond targeted `food.csv` string checks
- generated DOCX/PDF outputs, except for validation/spot checks

## Current Verified Facts

- Correct upload package is three separate files: main form, EK-1 references, EK-2 budget/justification.
- Main form must stay in the official template structure, Arial 9, A4, under 22 pages excluding EK-1/EK-2.
- Current generated main form renders at 18 pages after preserving official margins and using 9 pt filled text.
- Main/EK1/EK2 currently preserve official template table counts.
- Main form still has two content blockers:
  - host institution placeholder
  - team-credentials placeholder
- The 18-page count is not itself a bug. It comes from separating EK-1/EK-2 correctly and not adding non-template tables.

## Editing Rules For This Task

- Edit source markdown and exporter code, not generated DOCX/PDF by hand.
- Do not add extra tables to the main template. The exporter intentionally converts non-template narrative markdown tables to compact bullet text.
- Keep additions evidence-based and reviewer-facing. Avoid padding to fill pages.
- After edits, regenerate DOCX/PDF, verify page count, placeholder scan, and obvious PDF rendering.
- Commit and push validated changes.

## Highest-ROI Main Form Edits

Prioritize these if continuing content work:

- Section 4.6: make feasibility stronger with concrete current prototype facts: staged AI routing, normalized payloads, PDF/source evidence, reviewer queue, approval workflow, correction diffs, and scheduled automation.
- Section 4.6.1: add cautious, verifiable Turkish food-data gap examples. Phrase as preliminary/gap-candidate evidence unless fully verified against USDA/EuroFIR/TurKomp.
- Section 4.7: add stronger validation/statistical audit design: locked test set, stratified audit, confidence intervals for the `<0.5%` error target, and escalation rules when a stratum fails.
- Section 2: sharpen scale-target wording so reviewers do not read `100,000 papers` as `100,000 fully expert-verified papers`.
- Section 6.3: define pilot acceptance criteria and expected evidence from pilots without inventing partner commitments.

