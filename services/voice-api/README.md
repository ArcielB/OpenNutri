# OpenNutri Voice Resolver

This private FastAPI service implements the bounded beta pipeline:

```text
audio -> one-pass literal transcript + structured concepts -> lexical retrieval
      -> exact-match fast path OR semantic retrieval + constrained selection
      -> automatic log or Flutter review
```

The service never returns invented nutrient data. Gemini can select only a Core food
ID supplied in that concept's retrieved candidate set, and every returned ID is
validated again. Flutter obtains nutrients from the public Core API after review.

## Provider boundary

- Supabase anonymous access tokens are verified against the app project's JWKS.
- The service role key is present only in this backend.
- Atomic database functions enforce one active request per subject, 10 requests per
  minute, 50 AI resolutions per subject/day, and 200 globally/day by default.
- English and Turkish voice use one structured `gemini-3.8-flash` audio call with
  `thinkingLevel=low`, returning both the literal transcript and food concepts. The
  Flutter client supplies its English/Turkish device locale as a hint. Direct
  two-food smoke tests completed in 2.78 seconds for English and 7.41 seconds for
  Turkish with both quantities exact.
- If the primary model is temporarily unavailable, rate-limited, or returns
  malformed/schema-invalid structured output, `gemini-3.1-flash-lite` gets one
  review-only attempt. Every fallback item is marked `transcription` unresolved and
  can never auto-log until the person confirms it. If both attempts fail, any safe
  transcript recovered from the response is returned for editable manual search.
  A successful audio fallback never starts a third provider call: lexical candidates
  are returned for safe review. Later query-rewrite, embedding, or selector failures
  also degrade to review instead of discarding an otherwise valid transcript.
  Each provider attempt has a 12-second deadline, keeping the primary plus fallback
  inside the Flutter client's 30-second request budget. Per-stage server timings and
  privacy-safe error classifications support production diagnosis without logging
  audio or transcript text.
- Exact, unambiguous lexical matches are selected deterministically and make no
  embedding or selector request. Ambiguous lexical matches use the constrained
  Flash-Lite selector without a vector call. Concepts with no viable lexical
  candidate first receive one batched English translation/synonym rewrite and retry
  lexical search. Only phrases that still have no candidate use a batched embedding
  call.
  The literal transcript and extracted amount stay separately represented, and normalized
  matches always require review. This keeps the ordinary path fast and minimizes
  private-index egress.
- A recording may contain up to ten foods. Explicit spoken meal groups are returned
  per concept; meal is otherwise left unset for Flutter's local-time default.
- Provider, contract, no-food, or quota failures before transcription return
  `status=manual_search` with a specific safe error code. Matching-stage provider
  failures after transcription return a conservative review result; there is no
  paid fallback.
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
so a Free-tier build is slow but resumable rather than abandoning the index. Resume
state is read in ordered 1,000-row pages; Supabase's response cap must never silently
truncate the completed-hash set.

The app-only `.github/workflows/voice-semantic-index.yml` extends the index by at
most 900 foods after the daily Pacific-time quota reset. It leaves 100 observed
free-tier embedding requests for rare live zero-lexical-candidate queries. Once all
13,537 searchable foods exist, the scheduled run stops after a count-only health
check and does not download hashes or call Gemini.

## API

- `POST /v1/voice/resolve`: authenticated multipart PCM WAV plus `language_hint`,
  `local_timestamp`, and `timezone`.
- `POST /v1/foods/resolve-text`: authenticated submitted text resolution. This route
  is for explicit Search submission, never per-keystroke calls.
- `POST /v1/voice/feedback`: privacy-limited optional confirmation feedback.
- `DELETE /v1/voice/feedback`: remove every feedback row for the token subject.

WAV input must be 16 kHz, mono, signed 16-bit PCM, no longer than 30 seconds, and no
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
there is intentionally no billed fallback. The Vercel function is pinned to
Washington, D.C. (`iad1`): measured Gemini audio latency from that runtime matters
more than the small extra round trip to the EU quota store, and matching itself is
local SQLite.
