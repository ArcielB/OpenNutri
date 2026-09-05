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
- Flutter suite: **36 tests passed** (including new state, persistence, search,
  request coordination, edit cancellation and widget save-completion checks).
- Voice API suite: **56 tests passed**, including nullable measurements, bounded
  conversation/memory contracts, and rejection of non-chat memory output.
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

Prepared versions: app `1.1.1+3`, voice/coach API `0.4.1`. Deployment, configured
release APK, and final physical-device results will be recorded after validation.
Device: Android 16 `2409BRN2CA`, physical size 720×1640. Automation uses a separate
`.audit` application so the installed personal diary is not a test fixture.

Previous deployed release: app `1.1.0+2`, API `0.4.0`, Vercel deployment
`dpl_BfCTuBWN2XTBFjeEj4BMz4BLH41V`. Previous authenticated daily/chat/Oracle
fixture successes are historical smoke checks, not measurements for this release.

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
