# OpenNutri AI / Algorithm Master Defense Notes

## Slide 01 — Title and role framing
Start with the system claim, not with models. Say that the project already runs as one loop: search, filtering, acquisition, annotation, and feedback reuse.

## Slide 02 — Problem definition
Three pressures define the problem: the literature is distributed, acquisition is expensive, and Turkish coverage is weaker. This is why retrieval quality matters before annotation.

## Slide 03 — System identity
Use this slide to say what you are presenting and what you are not. The best line is: we are presenting a retrieval system that feeds and learns from expert annotation.

## Slide 04 — Architecture map
Walk this figure slowly from left to right and then close the loop. Refer back to it when later slides get detailed.

## Slide 05 — Database slice for AI
Emphasize that the AI layer does not only consume papers. It also depends on search-evidence tables and label-evidence tables.

## Slide 06 — Source strategy
Say explicitly that each source fills a different gap. The language split is not cosmetic; it changes source priors, query phrases, and search order.

## Slide 07 — Query generation logic
The committee should hear that queries are partly seeded and partly learned. The phrase pool keeps a tiny exploration slice so the system does not get trapped in one phrase set.

## Slide 08 — Task ranking
Pair scores capture source-template-term performance. Batch scores capture the exact query batch. Static bias is the explicit language-policy layer on top of learned feedback.

## Slide 09 — First-pass filter
Stress that the search gate is intentionally cheap and tolerant. The threshold is negative because this gate is not the final decision layer.

## Slide 10 — Main ranking layer
This is the core ranking story: additive scoring from several evidence families. No single signal decides the paper alone.

## Slide 11 — Embedding design
If asked which embeddings are used, answer exactly: English all-MiniLM-L6-v2, Turkish/multilingual paraphrase-multilingual-MiniLM-L12-v2. Then say embeddings support metadata scoring; they do not replace the rest of the ranking logic.

## Slide 12 — Label semantics
This slide answers what exactly becomes training data. Emphasize latest visible state, not raw counts, and say conflicts are excluded on purpose.

## Slide 13 — Active feedback loop
If asked whether the loop is implemented or only collecting signals, answer: implemented, batch-updated, and already changing later runs.

## Slide 14 — Operational loop
Use this slide to prove the project can run as a process, not only as code modules.

## Slide 15 — Why the UI matters to AI
The UI is where human evidence becomes structured data. The three strongest implementation details are regex-based PDF matching, click fallback logic, and search-session telemetry.

## Slide 16 — Scope discipline
This is your protection slide. The safest line is: the current system learns through feedback-driven statistical adaptation, but it is not yet a trained classifier.

## Slide 17 — Main defense claims
If discussion becomes broad or chaotic, come back to these three claims. Then answer with one concrete implementation detail.

## Slide 18 — Appendix divider
Use this slide only as a transition. You do not need to speak on it for long.

## Slide 19 — Language strategy detail
The short answer is that sources, phrasing, and priors differ enough that merging EN and TR would reduce control and likely hurt Turkish coverage.

## Slide 20 — Exact thresholds
Only use this slide if the committee asks for exact constants. Otherwise summarize the system as additive and threshold-based.

## Slide 21 — Search-term ranking answer
If asked whether the search terms are ranked by ML or LLM, say no: they are ranked by feedback-driven statistical scoring and hand-designed ranking formulas.

## Slide 22 — Non-phrase feedback
If asked what learns besides terms, answer: pair scores, batch scores, concept scores, and source priors.

## Slide 23 — Acquisition path
If asked how you know a paper is really usable, answer: metadata accept is not enough; the project fetches the PDF and validates the full text before final acceptance.

## Slide 24 — UI detail
The best AI-facing sentence here is: the UI is where human evidence becomes structured data and telemetry.

## Slide 25 — Run-summary caveat
Use this slide to show rigor, not to defend raw counts. Stage counts are real up to metadata_pass, but this manifest leaves 12 metadata-pass candidates without terminal outcomes.

## Slide 26 — Final Q&A slide
The three safest sentences are: the feedback loop is implemented but batch-updated; search-term ranking is statistical not LLM-based; and the ranking layer is additive.
