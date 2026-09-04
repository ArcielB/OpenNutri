# OpenNutri Android beta

The Flutter diary keeps all diary entries on-device. Voice logging records a
temporary 16 kHz mono PCM16 WAV, sends it only to the authenticated resolver,
and deletes the file after success, failure, or cancellation. By default, a
fully resolved high-confidence batch is written automatically; the app keeps an
immediate Edit batch and Undo batch action on the success screen. Any missing or
ambiguous Core food, quantity, weight basis, preparation distinction, or
unspecified food opens the review screen instead. A selector-provided alternative
also counts as ambiguity, so it never bypasses review.

The 1.0 beta diary surface is organized around a glanceable daily energy/macro
card and one primary action: speak a whole meal. Typed search remains beside it,
each meal has an explicit add control, and recently used foods can be repeated
with one tap and immediately undone. Tapping any logged food opens a provenance
sheet with the source publisher/dataset/code, logged versus edible weight,
per-100 g calculation basis, and the exact stored nutrient snapshot. The
Nutrition report groups that snapshot into energy/macros, vitamins, minerals,
fatty acids, and other values instead of presenting one undifferentiated list.

Recording permits a 30-second whole-day list and waits for 1.6 seconds of trailing
silence, so a normal pause between foods does not cut the list off. The resolver
returns the literal transcript and structured concepts in one audio-model call.
Exact source-backed
matches take a deterministic fast path; ambiguous lexical matches skip vector
retrieval but still receive constrained selection and visual review. Semantic search
is reserved for a phrase with no lexical candidates.

Gemini 3.1 Flash-Lite performs the one-pass English/auto transcription and
extraction; Turkish prefers Gemini 3.5 Flash-Lite for quantity accuracy. Ambiguous
candidate selection and difficult query repair also use a low-latency Flash-Lite
model. If the language-primary call exceeds its 12-second provider deadline or is
rate-limited, the other model gets one review-only attempt. That fallback forces
visible transcript confirmation and disables automatic logging for the request;
both attempts fit inside the app's 30-second request budget.

The voice screen shows a responsive recording waveform and actual elapsed time,
distinguishes timeout/network/auth/service failures, clears stale route snackbars,
preserves any returned transcript for fallback search, and can retry Core nutrition
detail loading without asking the person to record the meal again. Food details are
cached in memory for repeat logs.

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
provider disclosure are satisfied.

One recording can contain up to ten foods. The extractor preserves an explicitly
spoken meal grouping (for example, `Breakfast: ...` / `akşam yemeğinde ...`);
otherwise it uses the local-time meal default. `Log confident foods automatically`
is enabled by default in Settings and uses a 0.92 confidence threshold alongside
the non-negotiable resolved-field checks above.

App launch initializes Supabase in parallel with the local diary and warms
anonymous auth plus the resolver health endpoint after the home shell appears.
Recording can therefore reuse that work; the warm-up remains non-blocking and
never uploads audio before Stop is pressed.

If anonymous sign-in or a voice provider is unavailable, the app does not expose
provider error details. It returns to a safe Manual search fallback, and any
temporary recording is still deleted.
