# OpenNutri Voice Resolver

This private FastAPI service implements the bounded beta pipeline:

```text
audio -> structured concepts -> lexical + semantic retrieval
      -> constrained candidate selection -> Flutter review
```

The service never returns invented nutrient data. Gemini can select only a Core food
ID supplied in that concept's retrieved candidate set, and every returned ID is
validated again. Flutter obtains nutrients from the public Core API after review.

## Provider boundary

- Supabase anonymous access tokens are verified against the app project's JWKS.
- The service role key is present only in this backend.
- Atomic database functions enforce one active request per subject, 10 requests per
  minute, 50 AI resolutions per subject/day, and 200 globally/day by default.
- Each voice request makes at most one audio extraction call, one batched embedding
  call, and one constrained selector call.
- Provider or quota failures return `status=manual_search`; there is no paid fallback.
- Audio is held only in request memory and is never written to Supabase or logs.
- Feedback accepts only short source phrases, proposed/final Core IDs, correction
  status, and model/index/Core versions.

## Local setup

Apply `supabase/migrations/001_voice_beta.sql` to a new app-only Supabase project,
enable anonymous sign-ins, and configure the variables shown in `.env.example`.

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m uvicorn opennutri_voice.main:app --reload
python3 -m pytest tests -q
```

The source-term and primary-name retrieval reads Core `v0.3.0` SQLite directly.
Override the database with `OPENNUTRI_CORE_DB_PATH`.

Build or resume the 768-dimensional private semantic index with:

```bash
python3 scripts/build_embeddings.py --batch-size 100
```

Each input is a deterministic composition of food name, category, source terms, and
preparation description. Its SHA-256 hash lets repeated runs skip unchanged rows.
The default builder waits 65 seconds between batches and retries HTTP 429 responses,
so a Free-tier build is slow but resumable rather than abandoning the index.

## API

- `POST /v1/voice/resolve`: authenticated multipart PCM WAV plus `language_hint`,
  `local_timestamp`, and `timezone`.
- `POST /v1/foods/resolve-text`: authenticated submitted text resolution. This route
  is for explicit Search submission, never per-keystroke calls.
- `POST /v1/voice/feedback`: privacy-limited optional confirmation feedback.
- `DELETE /v1/voice/feedback`: remove every feedback row for the token subject.

WAV input must be 16 kHz, mono, signed 16-bit PCM, no longer than 20 seconds, and no
larger than 1 MB.

## Benchmark

`../../benchmarks/voice-v0.1.0/` contains 240 balanced English/Turkish text and
audio cases. Its validator checks every gold food ID against Core `v0.3.0`, verifies
committed WAV format/hash/limits, and guards the required scenario coverage.
`evaluate.py --enforce` applies the rollout thresholds. Live metrics must only be
published after running the complete private semantic index; the manifest validator
alone is not a quality result.

The production beta deployment is
`https://opennutri-voice-beta.vercel.app`. Its unauthenticated health endpoint can
be used for configuration smoke tests. It uses an isolated app-only Free Supabase
organization, so dormant research traffic cannot consume this beta's egress quota;
there is intentionally no billed fallback.
