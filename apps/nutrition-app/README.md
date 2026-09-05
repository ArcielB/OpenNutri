# OpenNutri Android beta

OpenNutri 1.1.1 is an Android-first Flutter food diary. It combines whole-meal
voice logging, source-backed USDA food search, editable nutrient snapshots,
personal goals and diet templates, an opt-in AI coach, and Oracle food ideas.
The diary, targets, profile, saved facts, and one daily advice snapshot live on
the phone. There is no diary cloud sync or backup/export UI yet.

Start with [the consumer app guide](../../docs/consumer_app.md) for architecture,
feature behavior, storage, API contracts, privacy, troubleshooting, and a demo
walkthrough. The [2026-09-05 audit](../../docs/consumer_app_audit_2026-09-05.md)
records tests, fixed regressions, device evidence, and remaining limitations.
[BACKLOG](../../BACKLOG.md) tracks unfinished product work.

## Run and build

Use the Flutter stable SDK and Android SDK configured on your machine:

```bash
flutter pub get
flutter run \
  --dart-define=OPENNUTRI_APP_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
flutter build apk --release \
  --dart-define=OPENNUTRI_APP_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
```

The key must belong to the isolated consumer app Supabase project. It is a public
client key, not a service-role or Gemini secret. Omitting it leaves local diary
and public Core search usable, but AI features cannot authenticate. Production
URLs have defaults; these Dart defines can override them:

| Define | Purpose |
| --- | --- |
| `OPENNUTRI_API_BASE_URL` | Public read-only Core API |
| `OPENNUTRI_VOICE_API_BASE_URL` | Authenticated voice/text/coach API |
| `OPENNUTRI_APP_SUPABASE_URL` | Isolated consumer authentication project |
| `OPENNUTRI_APP_SUPABASE_PUBLISHABLE_KEY` | Public client authentication key |
| `OPENNUTRI_TIMEZONE` | Resolver timezone; default Europe/Istanbul |

The current release build uses the local Android debug signing key for personal
beta installs. Configure a dedicated release key before store distribution.
An in-place `adb install -r build/app/outputs/flutter-apk/app-release.apk`
preserves the existing app's diary.

## Verify

```bash
flutter analyze --no-pub
flutter test --no-pub
# Native widget intent checks on an unlocked connected Android device:
cd android
./gradlew :app:connectedDebugAndroidTest -PauditBuild=true -Pdart-defines= --console=plain
```

The optional `auditBuild` property installs a separate
`org.opennutri.opennutri_app.audit` debug application, so instrumentation has its
own diary and consent state. Do not use a personal diary as a test fixture.
Backend and Core checks are documented in
[voice-api](../../services/voice-api/README.md) and
[core-api](../../services/core-api/README.md).

## Important behavior

- Voice records temporary 16 kHz mono PCM16 WAV audio, up to 30 seconds, and stops
  after 1.6 seconds of trailing silence. It supports up to ten foods and sends the
  English/Turkish device locale as a hint.
- A batch logs automatically once **every item** has a selected Core food, loaded
  nutrients, a valid amount, and a usable weight basis. Missing amounts default
  to 100 g and missing basis to edible weight. These defaults and uncertain
  matches are marked Quick estimate. Known amounts are preserved. An explicit
  as-purchased weight without an exact usable factor still needs correction.
- Edit batch keeps the original saved entries until Save changes succeeds.
  Cancelling leaves the diary intact. Individual entries support amount/meal
  editing and replacement through Core search. Local saves are serialized and
  repeated voice request IDs cannot duplicate entries. Optional feedback never
  delays the success screen.
  The amount dialog owns its text field state through the closing animation;
  cancellation, decimal-comma edits and food replacement have widget regressions.
- The widget opens visible capture, saves locally, shows an Android toast, and
  closes the activity after success. It logs to today even if the app was showing
  a historical date. It is **not background capture**: failed/unmatched requests
  still need the visible app, and closing before saving does not queue a job.
- Coach consent is separate from voice consent. The updated disclosure explains
  Gemini unpaid-service data use; old coach consent must be accepted again.
  Settings can disable coaching, and saved facts can be deleted individually.
- Daily advice is a cached snapshot for the selected diary date. Goal, diet,
  target, and memory changes invalidate it on disk. It refreshes on opening or
  resuming the app or Coach, with explicit refresh available. Changing food logs
  does not regenerate advice after every edit; Oracle refreshes when opened with
  changed context.
- Oracle loads only when opened. AI operations share a serialized request lane
  because the server permits one active request per subject. Advice generated
  against an obsolete date/profile is discarded.
- Oracle currently produces ranked **food ideas/search queries**, not a
  mathematical nutrition optimizer. Six diet presets adjust macro targets at the
  user's existing calorie target; they do not calculate energy needs or generate
  a complete meal plan. See the guide before presenting these as broader features.
