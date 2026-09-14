# OpenNutri staj defteri paketi

Start with [KISA_OZET.md](KISA_OZET.md). This is an original Turkish, app-only
30-day draft, not a completed attendance record or an approved institutional form.
The detailed revision follows the PDF example's first-person daily-learning style:
the task, implementation steps, a concrete example or check, and the lesson learned.
First-person contribution statements are proposed wording for student review, not
verified authorship. No undocumented meetings, mentors or workplace events were added.
The two user-supplied examples remain unmodified and are not included in Git.

## Deliverables and sources

- [Editable Word](OpenNutri_Staj_Defteri_30_Gun.docx)
- [Printable PDF](OpenNutri_Staj_Defteri_30_Gun.pdf): 2 front pages + 30 daily pages.
- [Daily source text](gunlukler.md): 6,620 body words, 203–242 per entry, four paragraphs each.
- [Personal information](bilgiler.json): deliberately unfilled.
- [Evidence map](KANIT_HARITASI.md): app paths and verification boundaries.
- [Rendering checks](validation.json): generated from the actual PDF.

The 30-day PDF example contains 5,667 daily-page words including its repeated
frames; this detailed draft has 7,435 with frames and the two technical tables
(about 31% more, still 30 daily pages). Main narrative grew about 32% from the first
5,009-word draft, without reducing its 12-point font or changing page dimensions.
The other example has 40 daily entries, approximately 3,811 XML-extracted
words including duplicated text-box labels, and renders to 43 PDF pages in
LibreOffice. Its rendered text count is 3,685. Counts depend on extraction and
include labels, so neither count measures student effort.

The layout follows the examples' A4 frame, workplace/page header, daily title,
paragraphs and date/approver/signature footer. It uses original text and native
Word tables, not copied logos, signatures, personal details or invented screenshots.
Institution, student, workplace, approver and dates require confirmation. No
automatic weekday schedule is generated. If real dates are supplied, exactly 30
unique chronological entries and matching start/end values are required; formal
attendance, holidays and eligibility still need human confirmation.

Concrete additions include 350 ms search debounce and stale-response tokens;
182 g / 94.64 kcal scaling and 500 g / 335 g edible-weight test examples;
the 52 + 80 = 132 kcal mixed-source regression; serialized save rollback;
audio thresholds and the detector-test/runtime distinction; native Intent
consumption; cached-advice invalidation; and offscreen Future error handling.
Examples describe actual implementation or controlled fixtures, not user data,
newly measured performance, or proof of the student's individual work.

## Rebuild

Required: Python 3, `python-docx`, LibreOffice Writer and Poppler (`pdfinfo`,
`pdftotext`). Install missing dependencies instead of silently skipping PDF checks.

```bash
python3 -m pip install python-docx
# Debian/Ubuntu, if the system tools are missing:
sudo apt install libreoffice-writer poppler-utils fonts-liberation
python3 apps/nutrition-app/docs/staj_defteri/build_report.py
```

Run the last command from the repository root; the script locates its own inputs.
It uses a separate temporary LibreOffice profile so it does not control an open
personal office session. It overwrites only its named DOCX, PDF and validation
outputs. Edit `gunlukler.md` and `bilgiler.json` for durable changes. A manual edit
to the generated Word file will be overwritten on the next build.

The draft deliberately labels the day allocation and individual attribution as
unverified, including its first-person wording. Confirm both before submission.
The source and printed information page identify AI-assisted drafting; follow the
institution's disclosure requirements. Private
filled-in copies should remain outside the public repository. Do not commit
student identifiers, workplace signatures or the supplied examples accidentally.

Application/backend source, installed APK and deployments are unchanged by this
documentation task. App analysis and all 44 Flutter tests passed again on
2026-09-14; the backend and physical phone were not retested. The product backlog
was reviewed and remains unchanged because no product scope was completed or added.
