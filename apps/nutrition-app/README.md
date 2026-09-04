# OpenNutri Android beta

The Flutter diary keeps all diary entries on-device. Voice logging records a
temporary 16 kHz mono PCM16 WAV, sends it only to the authenticated resolver,
and deletes the file after success, failure, or cancellation. Any resolver result
with a usable selected Core food is written immediately. When the amount, weight
basis, or match is uncertain, the app uses a neutral 100 g/edible-weight default
and marks the entry as a Quick estimate instead of blocking capture with a
confirmation screen. The success screen keeps Edit batch and Undo batch actions;
tapping an entry later edits its amount and meal in place while preserving its
source-backed nutrient snapshot. Results with no usable Core food still fall back
to search.

The 1.0 beta diary surface is organized around a glanceable daily energy/macro
card and one primary action: speak a whole meal. Typed search remains beside it,
each meal has an explicit add control, and recently used foods can be repeated
with one tap and immediately undone. Tapping any logged food opens a provenance
sheet with the source publisher/dataset/code, logged versus edible weight,
per-100 g calculation basis, and the exact stored nutrient snapshot. The
Nutrition report groups that snapshot into energy/macros, vitamins, minerals,
fatty acids, and other values instead of presenting one undifferentiated list.

## Personal coach, Oracle, and diets

OpenNutri 1.1 adds one on-device personalization profile shared by three surfaces:

- Coach creates one cached daily signal from the selected goal, active diet,
  today's actual nutrient totals, and explicit saved facts. The first activation
  explains that this compact context is sent transiently to Gemini. Text and
  bounded temporary voice messages are supported. Gemini may return memory updates
  only for durable facts the person explicitly said; those facts remain on-device,
  are shown as removable chips, and are never stored by the resolver.
- The Oracle asks Gemini to rank practical foods for the current day's largest
  opportunities while respecting that same profile. Gemini returns ordinary
  English food search queries, never nutrient numbers or invented IDs. Tapping an
  idea opens OpenNutri Core search, and only a verified Core food can be logged.
- Diets provides Flexible balance, Mediterranean, High protein, Plant powered,
  Low-carb keto, and Blue Zones-inspired starting patterns. Choosing one adjusts
  macro targets to the current energy target and goal; the person can add arbitrary
  constraints and still edit the resulting numeric targets in Settings.

The gap context uses current FDA Nutrition Facts Daily Values for adults and
children age 4+ as general comparison references. It is not an individualized
clinical assessment. A deterministic on-device macro observation is shown if the
daily coach is unavailable; it is labeled as a fallback rather than AI output.

Recording permits a 30-second whole-day list and waits for 1.6 seconds of trailing
silence, so a normal pause between foods does not cut the list off. The resolver
returns the literal transcript and structured concepts in one audio-model call.
Exact source-backed
matches take a deterministic fast path; ambiguous lexical matches skip vector
retrieval but still receive constrained selection and visual review. Semantic search
is reserved for a phrase with no lexical candidates.

Gemini 3.8 Flash performs the one-pass English/Turkish transcription and extraction
with its supported `low` thinking level. The phone sends its English or Turkish
device locale as a language hint and uses `auto` for other locales. Ambiguous
candidate selection and difficult query repair still use a low-latency Flash-Lite
model. If the primary call exceeds its 12-second provider deadline, is rate-limited,
or returns malformed structured output, Gemini 3.1 Flash-Lite gets one review-only
attempt. That fallback lowers confidence for the request. It never starts a third
provider call for semantic matching; the resolver presents lexical candidates and
the app stores a usable selected candidate as a marked estimate, keeping both
attempts inside the app's 30-second request budget.

The voice screen shows a responsive recording waveform and actual elapsed time,
distinguishes timeout/network/auth/service/provider-contract failures, clears stale
route snackbars, preserves any usable transcript even when structured extraction
fails, and can retry Core nutrition detail loading without asking the person to
record the meal again. Food details are cached in memory for repeat logs.

The production resolver URL and isolated Voice Beta Supabase project URL have
non-secret defaults. The app's public client key is project-specific, so supply
the current key at build time:

```bash
flutter build apk --debug \
  --dart-define=OPENNUTRI_APP_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
```

`OPENNUTRI_VOICE_API_BASE_URL`, `OPENNUTRI_APP_SUPABASE_URL`, and
`OPENNUTRI_TIMEZONE` remain overrideable Dart defines. Never put the Supabase
secret/service-role key or Gemini key in a Flutter build.

Run the local verification suite with:

```bash
flutter analyze
flutter test
flutter build apk --debug
android/gradlew -p android :app:assembleDebugAndroidTest
```

The home-screen widget starts `MainActivity` with `ACTION_VOICE_LOG`; recording
begins only after Flutter is visible and microphone permission plus the first-use
provider disclosure are satisfied. A successful widget capture persists the
entry, shows a native Android confirmation, and closes its task back to the
launcher. This is the shortest flow Android permits while keeping microphone use
visible to the user.

One recording can contain up to ten foods. The extractor preserves an explicitly
spoken meal grouping (for example, `Breakfast: ...` / `akşam yemeğinde ...`);
otherwise it uses the local-time meal default. Instant voice logging is always
enabled. Uncertainty is visible and editable after capture rather than becoming a
mandatory pre-save step.

App launch initializes Supabase in parallel with the local diary and warms
anonymous auth plus the resolver health endpoint after the home shell appears.
Recording can therefore reuse that work; the warm-up remains non-blocking and
never uploads audio before Stop is pressed.

If anonymous sign-in or a voice provider is unavailable, the app does not expose
provider error details. It returns to a safe Manual search fallback, and any
temporary recording is still deleted.
