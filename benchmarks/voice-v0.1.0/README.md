# OpenNutri voice benchmark v0.1.0

This versioned beta benchmark contains 240 balanced English/Turkish cases:

- 120 English and 120 Turkish cases;
- 48 committed 16 kHz mono PCM16 WAV fixtures and 192 submitted-text cases;
- colloquial names, multiple foods, source portions, missing quantities,
  cooking state, skin/bone, drained foods, as-purchased weights, transcription
  errors, recipe/no-match dishes, and raw/cooked ambiguity.

Every supported target is an exact searchable OpenNutri Core `v0.3.0` food ID.
Recipe cases intentionally require no match rather than decomposition. Missing
quantities and material preparation distinctions explicitly require clarification.
The audio set is deterministic eSpeak NG speech so regressions are repeatable; it
does not substitute for the later on-device human-speaker acceptance pass.

Validate the committed manifest and audio:

```bash
python3 validate.py \
  --manifest cases.jsonl \
  --core-db ../../services/data-pipeline/data/core/releases/opennutri-core-usda-v0.3.0/opennutri-core.sqlite
```

Rebuild it using eSpeak NG:

```bash
python3 build_benchmark.py \
  --core-db ../../services/data-pipeline/data/core/releases/opennutri-core-usda-v0.3.0/opennutri-core.sqlite \
  --output cases.jsonl \
  --render-audio \
  --espeak /usr/bin/espeak-ng
```

`evaluate.py` consumes one JSON object per case. Each prediction provides
`case_id`, `latency_ms`, and `items`; each item provides its ordered
`retrieved_candidate_ids`, selected/alternative IDs, unresolved fields, and
quantity status. `--enforce` requires top-12 recall ≥95%, correct selection or
explicit clarification ≥90%, 100% candidate-ID validity, no silent defaults, p50
under 5 seconds, and p95 under 12 seconds.

Live threshold results are not claimed until the private semantic index is built
and the free-tier Supabase project can serve anonymous sessions.
