# OpenNutri Android beta

The Flutter diary keeps all diary entries on-device. Voice logging records a
temporary 16 kHz mono PCM16 WAV, sends it only to the authenticated resolver,
and deletes the file after success, failure, or cancellation. By default, a
fully resolved high-confidence batch is written automatically; the app keeps an
immediate Edit batch and Undo batch action on the success screen. Any missing or
ambiguous Core food, quantity, weight basis, preparation distinction, or
unspecified food opens the review screen instead.

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

Starting a recording also non-blockingly warms anonymous auth and the resolver
health endpoint while the person is speaking. This overlaps first-use/serverless
startup work with recording; it never uploads audio before Stop is pressed.

If anonymous sign-in or a voice provider is unavailable, the app does not expose
provider error details. It returns to a safe Manual search fallback, and any
temporary recording is still deleted.
