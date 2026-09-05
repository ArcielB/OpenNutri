# Consumer app: implementation and handoff

Current implementation: Flutter app **1.1.1+3**, Core API **0.4.0** / USDA Core
**0.3.0**, and voice/coach API **0.4.1**. This document describes current behavior;
dated measurements and the latest validation are in the
[consumer audit](consumer_app_audit_2026-09-05.md). Earlier handoff notes describe
historical releases, including the superseded confidence-gated confirmation UI.

## Architecture

```text
Android widget -> MainActivity action -> Flutter voice screen
                                          |
                         temporary WAV -> voice-api -> Gemini extraction
                                          |               |
                              exact Core candidates <------+
                                          |
Public Core search/detail ----------------+--> local diary nutrient snapshot
                                                       |
                           goal + diet + saved facts + selected-day totals
                                                       |
                            opt-in coach-api -> daily / chat / Oracle ideas
                                                                   |
                                                        Core search -> serving -> diary
```

The consumer app uses an isolated Supabase project (`xktsqscshecpnfvlqtoy`) for
anonymous authentication, atomic request quotas, optional correction feedback,
and a private semantic food index. It does not use either research Supabase
project. Core is read-only SQLite behind HTTP; its database schema is not the
Flutter API contract. Gemini never supplies the nutrient values saved in a diary.

| Area | Source and responsibility |
| --- | --- |
| Startup and navigation | `apps/nutrition-app/lib/main.dart`, `screens/home_shell.dart`; local initialization, non-blocking auth warm-up, five tabs, app resume and widget actions |
| Diary mutations | `lib/state/app_controller.dart`; optimistic display, ordered persistence, ID deduplication, batch updates and Undo |
| Stored nutrition | `lib/models/diary.dart`; per-food energy selection, edible-weight scaling, stored snapshots, review flags |
| Local persistence | `lib/services/local_store.dart`; SharedPreferences JSON and disclosure flags |
| Voice capture/review | `lib/services/voice_recorder.dart`, `screens/voice_log_screen.dart`; bounded temporary WAV, selected detail loading, estimates, safe batch editing |
| Personalization | `lib/models/personalization.dart`, `services/coach_service.dart`; presets, shared profile and bounded context payloads |
| Coach and Oracle UI | `lib/screens/{coach,oracle,diets}_screen.dart`; consent, chat, removable facts, ideas and diet customization |
| HTTP | `lib/services/{core_api_client,voice_api_client}.dart`; source lookup, token reuse, serial AI requests and response deadlines |
| Native widget | `android/app/src/main/kotlin/org/opennutri/opennutri_app/`; launcher intent, pinning request and success toast/task closure |
| AI service | `services/voice-api/opennutri_voice/`; `main.py` routes/quotas, `models.py` bounds, `gemini.py` provider contracts, `pipeline.py` source candidate selection |

Paths beginning `lib/` or `android/` in the table are relative to `apps/nutrition-app/`.

## Logging and corrections

1. After voice disclosure and microphone permission, capture starts visibly.
   No audio is uploaded during recording. Recording stops manually, after 1.6
   seconds of trailing silence, or at the 30-second timer.
2. Gemini returns a literal transcript and up to ten food concepts. Exact lexical
   matches bypass vector search and selection. Ambiguous lexical matches can use
   a constrained selector; no-lexical-match concepts can use query repair and
   embeddings. Returned food IDs must belong to the retrieved Core candidate set.
3. Flutter loads selected Core food details. If all items are usable, it saves
   the batch immediately. Missing quantity becomes 100 g; missing basis becomes
   edible weight. This is a provisional default, not a measured serving. Existing
   quantities are never replaced merely because a match is uncertain.
4. Uncertainty is represented by `logged_by_voice` and `needs_review`, displayed
   as Quick estimate. Confidence, unresolved fields, alternatives, and defaults
   influence that flag. Server `auto_log_eligible=false` means uncertainty; the
   Android client can still save a valid selection as an estimate.
5. If an item has no selected food or lacks a required as-purchased factor, the
   whole batch currently opens review. A failed detail request can be retried
   without recording again. A recovered transcript can seed manual search.

`DiaryEntry.grams` is edible weight; `inputGrams` preserves entered weight.
As-purchased conversion requires a usable factor linked to that exact food.
Source refuse values, conflicts and correction provenance are retained in Core.
Never borrow a factor from a similar food. Nutrients are scaled only from rows
whose basis is `per_100g_edible_portion`.

Saved entries keep exact nutrient snapshots. Amount edits scale the existing
snapshot and edible/input ratio. Replacing a food explicitly chooses a new Core
record and serving while retaining the diary entry's ID and date. Opening or
cancelling either editor does not remove the original entry. Saving a correction
clears its review marker. Batch changes persist in one write; they do not append
duplicates. Daily calories sum each food's chosen energy field, avoiding dropped
foods or double-counting when USDA Energy/Atwater fields differ.

The diary renders optimistically, but widget completion waits for persistence.
Writes are ordered, and an isolated failed write rolls the visible state back.
SharedPreferences is appropriate to this personal beta, not a transactional
database or a guarantee against power loss, corrupt storage, or simultaneous
processes. There is no user-facing export/restore yet.

## Widget limits

Settings requests a native 1×1 microphone widget. Its cold or warm intent opens
`MainActivity`, consumes the action once, selects today, and opens voice capture.
First-use permission and disclosure remain visible. On successful save, Flutter
waits 550 ms, then requests a native result toast and activity/task closure.
Editing or Undo during that interval cancels automatic closure. Optional feedback
is best effort and cannot hold the success screen open.

This implementation still opens a Flutter activity and waits for resolution. It
does not provide a floating recorder, background worker, notification inbox, or
durable failed-capture queue. Do not present it as “close immediately while the
meal is processed in the background.” Test actual launcher placement separately
from intent delivery; launchers vary.

## Coach, memory and daily advice

The shared profile contains one of five goals, a diet preset ID, free-form diet
notes, up to 30 saved facts, and coach consent. The app sends the selected diary
date, its totals, up to 30 recent food entries, the profile, and the current chat
message. Chat additionally sends at most six recent conversation turns. Chat
history is session-only; only accepted memory candidates survive a restart.

The prompt restricts memory candidates to explicit durable statements in the
current user message/recording. Assistant messages are context, never personal
facts. Daily/Oracle model responses cannot add memories. Chat candidates are
automatically merged case-insensitively and displayed for deletion; explicitness
is still prompt-enforced, not an independent semantic verifier. At 30 facts the
oldest retained facts take precedence; a user can remove obsolete facts.

Daily advice is one persisted snapshot keyed to the selected local date. It is
hidden on other dates and while coaching is disabled. Profile/goal/diet/target/
memory changes clear both the in-memory and stored advice. App open/resume or
opening Coach/Today generates missing advice; refresh requests a new snapshot.
Resuming after midnight moves a previously-current day to the new today while
preserving deliberate historical browsing. Responses for a changed context are
discarded. A diary edit does not trigger a paid/model request for every food;
existing advice remains a labeled snapshot until refreshed. A failed daily call
produces a labeled deterministic on-device observation. It does not silently
claim to be Gemini output.

Oracle only requests guidance while opened. Returning to an unchanged result
reuses it; a changed date/profile/diary invalidates it. Current Oracle ranking is
Gemini's qualitative ordering of food search ideas. It does not calculate a
global optimum or score actual candidate nutrient vectors. Tapping an idea opens
Core search and serving selection before adding a verified food.

FDA Nutrition Facts Daily Values supply broad comparison references: fiber 28 g,
calcium 1,300 mg, iron 18 mg, potassium 4,700 mg, magnesium 420 mg, vitamin C 90 mg,
and vitamin D 20 mcg. These are label references for adults and children age 4+,
not personalized deficiency diagnoses. Missing micronutrient values are sent as
null; coverage counts identify how many logged food snapshots actually report a
value. Source zero is distinct from missing. `µg`, `μg`, `ug`, and `mcg` are
recognized as equivalent microgram spellings. Partial source coverage and an
incomplete diary cannot establish actual dietary deficiency. See the
[FDA reference](https://www.fda.gov/files/food/published/DV-Percent-DV-Nutrition-Facts-Label_09072023.pdf).

## Diet templates

| Preset | Base carbohydrate / protein / fat energy share |
| --- | --- |
| Flexible balance | 45% / 25% / 30% |
| Mediterranean | 45% / 20% / 35% |
| High protein | 35% / 35% / 30% |
| Plant powered | 55% / 20% / 25% |
| Low-carb keto | 10% / 25% / 65% |
| Blue Zones-inspired | 60% / 15% / 25% |

These are app-authored starting templates, not validated prescriptions or claims
about a particular celebrity's diet. Build muscle/lose fat transfer five energy
percentage points from carbohydrate to protein when the starting carbohydrate
share is at least 20%. Performance transfers five points from fat to carbohydrate
except for the keto preset. Grams use 4 kcal/g for carbohydrate and protein and
9 kcal/g for fat at the user's existing calorie target. Settings remains editable
and immediately reflects applied diet changes. Notes influence AI suggestions;
they do not independently recalculate numeric targets. There is no age/weight/
height/activity energy-needs calculation, guaranteed ketosis, weekly menu,
shopping list, or celebrity attribution. The backend `diet_plan` mode exists but
the app does not currently call it.

## Privacy and provider behavior

Diary/profile data stay on-device until a person enables an AI feature that sends
its specified context. Coach consent is independent of voice consent. Disclosure
version 2 explains unpaid-provider data use, so older coach opt-in is not silently
carried forward. Coaching can be disabled in Settings; requests already started
may finish, but obsolete/disabled replies do not update the profile or daily card.
The saved facts remain local until explicitly removed.

The resolver does not persist coach context, chat replies or audio. Audio exists
in request memory server-side; local temporary WAV files are deleted after normal
success, failure or cancellation. Abrupt process death during capture is not a
verified cleanup guarantee. Optional voice correction feedback is separate and
contains short source phrases, proposed/final food IDs, correction status and
model/index/Core versions—not whole transcripts, meals or nutrient snapshots.

This beta uses Gemini's unpaid service. Google's processing is governed by
[Gemini API terms](https://ai.google.dev/gemini-api/terms#data-use-unpaid), including
possible product-improvement use and human review, with regional exceptions.
“Our server does not store it” does not mean Google does not process or retain it.
Do not place service-role credentials or a Gemini key in Flutter or in this repo.

## Reliability and troubleshooting

Voice primary is configured as `gemini-3.8-flash`, with `thinkingLevel=low`.
One `gemini-3.1-flash-lite` retry handles retryable audio/structured-output failure.
Fallback results are uncertain estimates, and no third matching-model call is
started after a successful audio fallback. Coaching uses the configured Flash
model and at most one same-model retry on transport/retryable provider failure;
schema-invalid coach output is still an error. Each provider attempt has a
12-second timeout. Coach retries wait about one second with jitter and respect
short Retry-After hints; hints over two seconds fail promptly for a later retry.
Keep models configurable; these are configured IDs, not a
permanent claim to be the newest available model.

The shared Flutter client serializes AI requests to respect the server's one
active request per subject. This prevents self-inflicted quota conflicts, but a
user request can wait behind an already-running request. Token acquisition is
shared while in flight and bounded to 10 seconds. HTTP response bodies, not just
headers, are included in the 30-second client request timeout. Auth, queue wait,
Core detail loading and local persistence are additional time: there is no
guaranteed 30-second end-to-end bound.

| Symptom | Check |
| --- | --- |
| Voice/auth unavailable | Correct isolated public client key, Supabase anonymous sign-in and project availability; never redirect to research |
| AI limit reached | Shared voice/text/coach quota; defaults are 10/minute, 50/user/day, 200/global/day and one active request |
| Transcript present but no diary entry | Core detail availability, all batch selections, valid amounts and exact as-purchased factors |
| Diet shown but wrong advice | Date and snapshot label, saved facts, explicit refresh; profile changes should remove stale disk cache |
| Oracle empty | Coach consent and visible Oracle tab; use retry on failure; verify server 0.4.1 accepts the new context fields |
| Old search results after editing | Request-generation guards; test both lexical and submitted semantic responses |

For release commands see the [app README](../apps/nutrition-app/README.md).
For request schemas/examples see the [service README](../services/voice-api/README.md).

## Short demo walkthrough

1. Show the selected day's macro card. Search a known food and open its USDA
   source/calculation sheet to explain where the numbers come from.
2. Speak a short, explicit two-food meal. Show immediate logging and Undo.
   Log an uncertain serving, then edit the Quick estimate; demonstrate cancelling
   an edit preserves the original and replacing a wrong food is possible.
3. Explain AI sharing and opt in on a demo profile. Choose a goal/diet, add a
   non-sensitive food preference, and show the visible saved fact and deletion.
4. Open Oracle and follow an idea through Core search. Describe it as personalized
   food suggestions; avoid claiming exact nutritional optimization.
5. Show the launcher widget. After a successful capture it saves and returns to
   the launcher. Keep manual search ready if the network or shared quota fails.

Use a separate audit build for synthetic entries. Do not invent nutrition or
benchmark performance for a presentation. The audit and backlog list remaining work.
