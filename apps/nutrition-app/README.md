# OpenNutri Android beta

The Flutter diary keeps all diary entries on-device. Voice logging records a
temporary 16 kHz mono PCM16 WAV, sends it only to the authenticated resolver,
requires review of every item, and deletes the file after success, failure, or
cancellation.

The production resolver URL and Supabase project URL have non-secret defaults.
Supply the app project's public client key at build time:

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
