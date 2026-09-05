# OpenNutri Voice Resolver

This private FastAPI service implements the bounded beta pipeline:

```text
audio -> one-pass literal transcript + structured concepts -> lexical retrieval
      -> exact-match fast path OR semantic retrieval + constrained selection
      -> automatic log or Flutter review
```

The service never returns invented nutrient data. Gemini can select only a Core food
ID supplied in that concept's retrieved candidate set, and every returned ID is
validated again. Flutter obtains nutrients from the public Core API before saving.
Android 1.1 saves a batch immediately when every item has a usable selection;
uncertainty is marked as an editable estimate. `auto_log_eligible` remains a
server confidence signal, not a mandatory client confirmation policy. See the
[consumer guide](../../docs/consumer_app.md) for the distinction.

The same authenticated service also provides stateless structured coaching.
`gemini-3.8-flash` receives a compact client-supplied profile/diary snapshot and
returns daily guidance, chat replies, or Oracle food search queries. Coach requests,
responses, and audio are not written to Supabase. Voice coach input is handled in
one audio request that returns the literal transcript, reply, and only explicit
durable memory candidates; Flutter decides what to store on-device. Oracle output
cannot log directly: Flutter resolves its plain-English query against Core first.
Coach requests use the configured Flash model and make at most one same-model
retry for a transient provider/transport failure; this avoids reporting an older
model while absorbing occasional Gemini 5xx responses. The retry waits roughly
one second with jitter; short Retry-After hints are respected. A hint longer than
two seconds ends the request rather than retrying too early or extending the
mobile budget. Since service 0.4.2, a 5xx/transport failure retries once through
Google's Interactions endpoint with the **same model, prompt, input and schema**,
rather than repeating only the failing generateContent endpoint. `store=false`
is mandatory: no stored conversation or previous interaction ID is used. Only
completed final model text is parsed; thoughts and partial output are excluded.
429/quota errors do not switch endpoints. This cannot guarantee availability
during a provider outage or exhausted quota. See Google's
[stateless Interactions guidance](https://ai.google.dev/gemini-api/docs/interactions-overview)
and [structured output contract](https://ai.google.dev/gemini-api/docs/structured-output).

## Provider boundary

- Supabase anonymous access tokens are verified against the app project's JWKS.
- The service role key is present only in this backend.
- Atomic database functions enforce one active request per subject, 10 requests per
  minute, 50 AI resolutions per subject/day, and 200 globally/day by default.
- English and Turkish voice use one structured `gemini-3.8-flash` audio call with
  `thinkingLevel=low`, returning both the literal transcript and food concepts. The
  Flutter client supplies its English/Turkish device locale as a hint. Direct
  two-food smoke tests completed in 2.78 seconds for English and 7.41 seconds for
  Turkish with both quantities exact. Final authenticated production checks on
  service `0.3.5` completed the same English and Turkish fixtures in 3.49 and 2.70
  seconds of pipeline time respectively; both foods and quantities were exact and
  auto-log eligible.
- If the primary model is temporarily unavailable, rate-limited, or returns
  malformed/schema-invalid structured output, `gemini-3.1-flash-lite` gets one
  uncertainty-marked attempt. Every fallback item is marked `transcription` unresolved
  and is not server auto-log eligible; Android can save a usable selected result
  as a Quick estimate. If both attempts fail, any safe
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
  matches retain uncertainty metadata for later correction. This keeps the ordinary path fast and minimizes
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
- Coach prompts prohibit diagnosis and treat one-day diaries as potentially
  incomplete. FDA adult Daily Values supplied by Flutter are broad comparison
  references, not individualized clinical targets. Memory updates are limited to
  facts explicitly stated in chat and are never persisted by this service.
  Since 0.4.1, missing metric amounts may be null with source-coverage counts;
  prompts must not interpret unknown or partially covered nutrients as zero intake.
  Chat can include at most six prior turns as conversation context, never as new
  personal facts. Non-chat Gemini output has memory updates stripped server-side.

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
- `POST /v1/coach/respond`: authenticated structured daily/chat/Oracle/diet response.
- `POST /v1/coach/voice`: authenticated multipart voice chat plus compact JSON
  context; returns transcript, response, and explicit memory candidates.

WAV input must be 16 kHz, mono, signed 16-bit PCM, no longer than 30 seconds, and no
larger than 1 MB.

### Coach contract (0.4.1)

All routes require `Authorization: Bearer <app anonymous access token>`. JSON
example for `POST /v1/coach/respond`:

```json
{
  "mode": "chat",
  "locale": "en-US",
  "local_date": "2026-09-05",
  "goal": "Eat well",
  "diet": "Flexible balance",
  "diet_notes": "Simple meals",
  "memories": ["Prefers lentils"],
  "daily_totals": [{
    "name": "Vitamin D", "amount": null, "unit": "mcg", "target": 20,
    "logged_foods_with_value": 0, "logged_food_count": 2
  }],
  "recent_foods": [],
  "conversation": [{"role": "assistant", "text": "Would you like dinner ideas?"}],
  "user_message": "Yes, something quick."
}
```

Response shape (illustrative, not a live result):

```json
{
  "headline": "A simple dinner",
  "message": "Try a lentil bowl with vegetables you enjoy.",
  "actions": [{"title": "Lentil bowl", "detail": "Use cooked lentils as a starting point.", "search_query": "cooked lentils"}],
  "memory_updates": [],
  "safety_note": null,
  "model": "gemini-3.8-flash"
}
```

Modes: `daily`, `chat`, `oracle`, `diet_plan` (last is backend-only for now).
Bounds: 30 facts of 180 characters, 500-character diet notes, 40 metrics,
30 foods with 160-character names, a 1,000-character current message, and six
conversation turns of at most 1,000 characters each. Metric amounts are finite,
nonnegative or null; targets, when present, are finite and positive. Coverage is
optional for older clients. `POST /v1/coach/voice` uses multipart fields `audio`,
`language_hint`, and `context` (this same JSON, mode `chat`, up to 32,000
characters), and additionally returns the current recording's literal `transcript`.

Authentication errors return 401, invalid contracts 422, request/quota conflicts
429, and provider/store failures 503. Voice resolve routes have their separate
safe `manual_search` response contract. The Flutter client serializes AI requests
to avoid simultaneous calls competing for the per-subject slot.

The resolver does not store coaching content; that is not a statement about
Google's retention or data use. The beta's unpaid provider processing is governed
by [Gemini API terms](https://ai.google.dev/gemini-api/terms#data-use-unpaid).

### Deployment

The linked Vercel project uses `vercel.json`, installs runtime requirements, and
fetches/verifies Core SQLite with `scripts/fetch_core_release.py`. After tests:

```bash
npx vercel deploy --prod --yes
curl --fail https://opennutri-voice-beta.vercel.app/health
```

Use the existing project link and configured server environment. No schema
migration is required for 0.4.1. Health confirms service configuration/version,
not successful authentication or AI quality; run a bounded authenticated fixture
probe separately. Do not log tokens, private profile text, audio, or raw provider
errors. Deployment and validation evidence belong in the current consumer audit.

`scripts/smoke_coach.py --live` performs three sequential synthetic coach contract
checks (daily, follow-up chat, Oracle). Optional `--wav <committed-fixture.wav>`
adds one voice-coach check. Supply `OPENNUTRI_APP_ACCESS_TOKEN`, or the isolated
`OPENNUTRI_APP_SUPABASE_PUBLISHABLE_KEY` to create a new anonymous test session.
This consumes shared quota and, with a public key, leaves a test auth subject;
prefer reusing a dedicated test access token. Output includes only versions,
timings and counts. This is a contract smoke test, not a recommendation-quality
or speech-accuracy benchmark.
Use `--modes chat oracle` to rerun only those checks after a transient failure.
Use `--modes --wav <committed-fixture.wav>` for a voice-only check. A failed mode
does not skip later independent checks; the script reports each failure safely
and exits nonzero if any selected check failed.

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
