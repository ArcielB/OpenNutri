# Consumer app audit — 2026-09-05

Scope: Flutter consumer app, native Android widget integration, authenticated
voice/coach API, public Core regression tests, and consumer-facing repository
documentation. Research/annotator runtime was not changed or reactivated.
Starting commit: `18fbecc`, verified equal to freshly fetched `origin/main`.
Unrelated local proposal/defense documents were preserved.

This is evidence of specific checks, not a claim that every device, voice input,
provider outage or nutrition recommendation works perfectly.

## Confirmed problems corrected

| Finding | Fix and regression evidence |
| --- | --- |
| Edit batch removed saved entries before editing, so cancelling lost the meal | Originals stay saved; Save changes replaces the batch in one write. The corrected expectation first failed against the original code, then passed |
| Optional feedback kept voice capture waiting after the diary save | Feedback runs best effort without delaying success or temporary WAV cleanup; blocked-feedback test |
| Replayed batches could duplicate entries; concurrent saves could finish out of order | Entry-ID deduplication and ordered disk snapshots; replay/overlap/failure tests |
| A wrong voice food could only have its amount/meal edited later | Added Replace food match through Core search and serving selection, preserving ID/date |
| Closing the amount dialog disposed its text controller before the reverse animation finished | Let TextFormField own its controller through unmount; cancellation and decimal-comma edit regressions reproduced the failure, then passed |
| Daily calories dropped foods using Atwater energy when other entries used Energy | Select energy per food before totaling; mixed-source regression |
| Applying a diet left old numeric targets in Settings | Synchronize fields only when targets change, preserving unrelated unsaved input; widget test |
| Profile/goal/diet changes only cleared daily advice in memory | Clear persistent cache too; restart tests for diet, goal, targets and memories |
| Advice could be labeled with a different date, or arrive after a profile change | Use selected-date keys, context revisions, disabled-state checks and app resume handling |
| Offscreen Oracle started AI calls and competed with daily coaching | Generate only when opened; reuse unchanged ideas; serialize all AI requests in the shared client |
| Coach follow-up questions lacked previous turns | Send up to six bounded conversation turns as context; current message remains separate |
| Missing micronutrient measurements appeared as zero intake | Send null plus source-coverage counts; distinguish zero and normalize microgram unit variants |
| Coach disclosure omitted unpaid-provider data use and had no off switch | Updated disclosure version, settings disable control, visible provider safety notes; old consent is not silently reused |
| Clearing/changing search did not invalidate all in-flight work | Generation guards for lexical and submitted semantic responses; delayed-search test |
| Numeric editors accepted non-finite values or rejected decimal commas inconsistently | Finite positive validation and decimal-comma support in serving/target editing |
| Multipart response timeout ended at headers, leaving body reads unbounded | Include body completion in the 30-second HTTP timeout; bounded shared token acquisition |
| Native tests competed with Flutter to consume one pending event and lost lifecycle tracking after Intent.action was cleared | Observe class-based cold launches and capture count, assert no replay; isolated audit application ID |

## Automated validation

Baseline: Flutter analysis clean, **22 Flutter tests**, **53 voice API tests**,
and **17 Core API tests** passed before changes. These passing tests did not cover
the regressions above.

Current validation:

- Flutter analysis: clean.
- Flutter suite: **39 tests passed** (including new state, persistence, search,
  request coordination, edit cancellation, food replacement and widget
  save-completion checks).
- Voice API suite: **59 tests passed**, including nullable measurements, bounded
  conversation/memory contracts, rejection of non-chat memory output, and smoke
  runner failure isolation/privacy.
- Core API suite: **17 tests passed**; Core API source/data unchanged.
- Native Android cold/warm widget-intent checks: **2/2 passed on Android 16**.
  Earlier runs exposed a locked screen and an ActivityScenario harness defect:
  clearing the consumed Intent action invalidated its lifecycle filter. The
  class-monitor harness now observes actual launches without changing the
  one-shot production behavior. This tests intent capture/replay, not live audio.

Commands are in the [app README](../apps/nutrition-app/README.md) and
[voice API README](../services/voice-api/README.md). Native reports are generated
under `apps/nutrition-app/build/app/reports/androidTests/connected/debug/`.

## Release and device evidence

Released versions: app `1.1.1+4`, voice/coach API `0.4.1`. Build 4 includes
the final amount-dialog lifecycle correction; build 3 was installed and tested
earlier in this audit. The final configured release APK built successfully and
was installed using `adb install -r`, without clearing the existing diary.
Android package metadata confirms `versionName=1.1.1`, `versionCode=4`.

- APK: `apps/nutrition-app/build/app/outputs/flutter-apk/app-release.apk`
- Size: 54,868,226 bytes; local debug signing key for the personal beta.
- SHA-256: `fff464747a4894ba58f7ec0f7872caa439038233b287661b8882d792864cebf1`
- The final build was installed without launching/tapping the personal app;
  the late dialog correction is covered by automated widget tests.

Device: Android 16 `2409BRN2CA`, physical size 720×1640. Automation uses a separate
`.audit` application so the installed personal diary is not a test fixture.

Production API deployment: `dpl_3MuY9C9bmrMyTMYJ3WPCQgKfHyDi`, region `iad1`,
stable alias `https://opennutri-voice-beta.vercel.app`, health reports `0.4.1`.
It contains the bounded same-model coach retry backoff. No schema changes were
required. Public Core health checks also passed with API `0.4.0` / Core `0.3.0`.

Physical checks in the isolated audit app: Today rendered; public Core search
returned raw apple records; selecting a source-backed Fuji apple showed 31
nutrient rows and 58.2 kcal/100 g; logging saved one Lunch entry; editing 100 g to
150 g kept one entry and updated its displayed calories to 87. Food replacement
and amount-cancel behavior were subsequently verified by automated widget tests,
not claimed as completed physical-device trials.

Screen automation stopped when another application was foreground. The temporary
audit app and its synthetic diary were removed, the temporary UI dump and unrelated
screen capture were deleted, and the phone's original USB stay-awake setting was
restored. The personal diary was not cleared or used as an AI fixture. Future
device taps must verify the foreground package and use a current screen state.

Previous deployed release: app `1.1.0+2`, API `0.4.0`, Vercel deployment
`dpl_BfCTuBWN2XTBFjeEj4BMz4BLH41V`. Previous authenticated daily/chat/Oracle
fixture successes are historical smoke checks, not measurements for this release.

First 0.4.1 production probe: daily advice succeeded in 4.88 seconds on
gemini-3.8-flash. Follow-up chat then failed with HTTP 503. Privacy-safe server
logs confirmed successful JWT lookup and quota reservation, followed by two
upstream Gemini 503 responses and successful quota release. This was not a
client/server schema mismatch or an authentication failure. Added bounded retry
backoff with jitter, following
[Google's retry guidance](https://ai.google.dev/gemini-api/docs/troubleshooting).
Keep this failed probe in the record even if a later smoke run succeeds.

Later bounded probes on the backoff deployment still failed for chat, Oracle and
voice chat with HTTP 503; voice chat took 11.52 seconds. Backoff has not solved
current provider availability. The food-logging audio fixture
`voice-v0.1.0-en-081.wav` did resolve two items in 6.22 seconds wall time, using
the existing `gemini-3.1-flash-lite` fallback. Server pipeline time was 4.632
seconds (audio extraction 4.623 seconds). These are single-fixture contract
checks, not speech/matching accuracy measurements. No coach model downgrade or
provider switch was made. Coach/Oracle reliability remains an open release risk.

The smoke runner now completes independent selected modes after a failure and
returns nonzero if any failed. `--modes --wav <fixture.wav>` checks voice chat
alone. No private user diary, live microphone recording, tokens or raw provider
bodies were printed by these probes.

## Documentation audit

The old root/service READMEs and handoff described forced review even though the
Android client had switched to immediate estimated logging. Some text claimed
every usable item logged independently, although one unusable item still holds
the batch. Widget wording overstated the implemented background capability.

The new [consumer implementation guide](consumer_app.md) maps source files,
explains storage/nutrient calculations, models/retries/request limits, disclosure,
cache behavior, templates, Oracle limitations, and a presentation walkthrough.
The app README provides current build/test instructions; the service README adds
bounded coach request/response examples. Root README, agent guidance, backlog and
handoff link to this current behavior map. Older release evidence is labeled as
historical instead of mixing multiple “latest APK” claims.

Checked 18 relative links across the root/app/service READMEs, consumer guide,
audit and handoff: none were broken.

## Remaining limits and useful next work

1. **Widget background completion and a review inbox.** Capture still opens the
   activity and waits for save. No durable job survives closing/process death,
   and mixed usable/unmatched batches do not partially save.
2. **A source-scored Oracle.** Current ranking is qualitative AI food ideas. It
   does not optimize verified candidate nutrient vectors or guarantee allergy
   filtering/optimal nutrition. Source verification happens when selecting a food.
3. **Backup and storage resilience.** No export/restore/cloud sync. Corrupt JSON,
   disk exhaustion and abrupt termination need broader recovery testing.
4. **Full plans/personalized energy needs.** Diet presets are adjustable ratio
   templates at an existing calorie target, not generated weekly menus or
   biometric energy calculations. No sourced celebrity templates exist.
5. **Broader validation.** The 240-case live voice benchmark, real human speech in
   noise, exact recording-limit behavior, multiple launchers, rotation, large
   text, long-session memory corrections and provider failure matrices remain
   outside the completed smoke/regression checks. App-store signing and release
   CI are also unfinished.

These items are actionable in [BACKLOG](../BACKLOG.md). For the next substantial
product work, prioritize durable widget capture/review and then a demonstrably
source-scored Oracle; both address the original product requests directly.

## Follow-up: widget placement and Oracle failures

Read-only Android inspection confirmed that VoiceLogWidgetProvider is registered
but no OpenNutri widget is bound to the home screen. Installation does not place
it automatically. The existing Settings pin action requires launcher confirmation;
manual placement is also available through the launcher's Widgets picker. No
phone taps or launcher navigation were performed during this follow-up.

Production logs confirmed repeated daily/Oracle upstream 503s on service 0.4.1.
A tiny synthetic local request succeeded on both Google's generateContent and
Interactions endpoints, but the full local Oracle comparison hit provider 429s
on both and could not establish an endpoint-specific cause. Vercel's secret
environment values cannot be pulled; the local key comparison was therefore
inconclusive, not proof of a different production key.

Service 0.4.2 adds one same-model Interactions retry for 5xx/transport failures,
with `store=false`, unchanged prompt/input/schema, and completed final-text-only
parsing. The total stays at two provider attempts; quota failures do not switch
endpoints and long Retry-After hints prevent an early retry. The expanded backend
suite passes all 68 tests. Live deployment outcomes will be recorded below;
this change is not yet evidence that the production failure has been resolved.

Service 0.4.2 deployment `dpl_6aBNbDZdisTyMoAF8fhRGGHpoDaA` completed in iad1.
Four live modes failed in 3.08/1.86/2.03/2.15 seconds (daily/chat/Oracle/voice chat).
Logs exposed upstream 429 rate limits, incorrectly mapped to public HTTP 503 by
both coach handlers. The alternate endpoint was therefore not exercised: quota
retries correctly stayed on generateContent. Live 3.8 probes were stopped.

After the proposed labeled Flash-Lite fallback, the user said "continue" and the
assistant explicitly proceeded on that basis. A direct synthetic Oracle call to
`gemini-3.5-flash-lite` succeeded in 1.97 seconds, with four searchable actions and
no non-chat memory updates. Service 0.4.3 adds that configured model as the one
fallback, preserves actual transport model attribution privately, and maps
unresolved rate limits to HTTP 429. No provider, credential, billing or app-quota
change was made. Total provider attempts remain bounded at two.

App 1.1.2+5 moves widget setup to the top of Settings, explains launcher approval
and manual placement, labels actual AI models in Oracle/daily cards/chat, and
distinguishes Oracle quota errors. Moving the settings tile exposed a separate
offscreen FutureBuilder issue: Core health could fail before its listener was
mounted. The original future's error is now handled immediately and still reaches
the status tile when visible. Flutter analysis is clean; all 44 Flutter and 79
backend tests pass. Remaining device checks stay read-only; no phone taps occur.
