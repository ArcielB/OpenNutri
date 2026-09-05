import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:opennutri_app/models/diary.dart';
import 'package:opennutri_app/models/food.dart';
import 'package:opennutri_app/models/personalization.dart';
import 'package:opennutri_app/screens/food_search_screen.dart';
import 'package:opennutri_app/screens/home_shell.dart';
import 'package:opennutri_app/screens/oracle_screen.dart';
import 'package:opennutri_app/screens/settings_screen.dart';
import 'package:opennutri_app/services/coach_service.dart';
import 'package:opennutri_app/services/core_api_client.dart';
import 'package:opennutri_app/services/local_store.dart';
import 'package:opennutri_app/services/voice_api_client.dart';
import 'package:opennutri_app/state/app_controller.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test(
    'diet, targets and memories invalidate advice on disk, not just in memory',
    () async {
      final controller = AppController(LocalStore());
      await controller.initialize();
      await controller.enableCoach();
      for (final change in <Future<void> Function()>[
        () => controller.applyDiet(dietPresetById('keto')),
        () => controller.updateGoal(NutritionGoal.buildMuscle),
        () => controller.updateTargets(const NutritionTargets(protein: 130)),
        () => controller.addCoachMemories([
          const CoachMemory(fact: 'Avoids peanuts', category: 'avoidance'),
        ]),
      ]) {
        await controller.saveDailyCoachBrief(
          DailyCoachBrief(
            dateKey: dateKeyFor(controller.selectedDate),
            reply: reply,
          ),
        );
        await change();
        final restarted = AppController(LocalStore());
        await restarted.initialize();
        expect(restarted.dailyCoachBrief, isNull);
      }
    },
  );

  test('cached advice never appears under a different diary date', () async {
    final controller = AppController(LocalStore());
    await controller.initialize();
    await controller.enableCoach();
    await controller.saveDailyCoachBrief(
      DailyCoachBrief(
        dateKey: dateKeyFor(controller.selectedDate),
        reply: reply,
      ),
    );
    controller.shiftDate(-1);
    expect(controller.dailyCoachBrief, isNull);
  });

  test('old coach consent requires the fuller provider disclosure', () {
    expect(
      UserNutritionProfile.fromJson({'coach_enabled': true}).coachEnabled,
      isFalse,
    );
    expect(
      UserNutritionProfile.fromJson(
        const UserNutritionProfile(coachEnabled: true).toJson(),
      ).coachEnabled,
      isTrue,
    );
  });

  test(
    'missing micronutrients stay unknown; microgram spellings and zero are preserved',
    () async {
      final controller = AppController(LocalStore());
      await controller.initialize();
      await controller.addEntries([
        foodEntry('one', [
          const FoodNutrient(
            nutrientId: 'd',
            name: 'Vitamin D (D2 + D3)',
            amount: 5,
            unit: 'µg',
          ),
        ]),
        foodEntry('two', [
          const FoodNutrient(
            nutrientId: 'd',
            name: 'Vitamin D (D2 + D3)',
            amount: 0,
            unit: 'ug',
          ),
        ]),
        foodEntry('three', []),
      ]);
      final payload = CoachService(
        VoiceApiClient(),
      ).requestPayload(controller: controller, mode: CoachMode.oracle);
      final metrics = (payload['daily_totals'] as List)
          .cast<Map<String, dynamic>>();
      final vitamin = metrics.singleWhere(
        (item) => item['name'] == 'Vitamin D',
      );
      expect(vitamin['amount'], 5);
      expect(vitamin['logged_foods_with_value'], 2);
      expect(vitamin['logged_food_count'], 3);
      expect(
        metrics.singleWhere((item) => item['name'] == 'Calcium')['amount'],
        isNull,
      );
    },
  );

  test(
    'daily energy sums mixed USDA fields without dropping or double counting foods',
    () {
      final totals = DailyTotals([
        foodEntry('one', [
          const FoodNutrient(
            nutrientId: 'e',
            name: 'Energy',
            amount: 52,
            unit: 'kcal',
          ),
        ]),
        foodEntry('two', [
          const FoodNutrient(
            nutrientId: 'es',
            name: 'Energy (Atwater Specific Factors)',
            amount: 80,
            unit: 'kcal',
          ),
          const FoodNutrient(
            nutrientId: 'eg',
            name: 'Energy (Atwater General Factors)',
            amount: 90,
            unit: 'kcal',
          ),
        ]),
      ]);
      expect(totals.calories, 132);
    },
  );

  test('replaying a voice batch cannot double-count it', () async {
    final controller = AppController(LocalStore());
    await controller.initialize();
    final entry = foodEntry('voice-one', []);
    await controller.addEntries([entry, entry]);
    await controller.addEntry(entry);
    expect(controller.entries, hasLength(1));
    expect(await LocalStore().loadEntries(), hasLength(1));
  });

  test(
    'overlapping diary saves preserve edit order and roll back a failed save',
    () async {
      final store = BlockingStore();
      final controller = AppController(store);
      final entry = foodEntry('voice-one', []);
      final add = controller.addEntry(entry);
      final edit = controller.updateEntry(
        entry.withEditedServing(inputGrams: 200, meal: MealType.lunch),
      );
      await Future<void>.delayed(Duration.zero);
      expect(store.writes, hasLength(1));
      store.pending.removeAt(0).complete();
      await add;
      await Future<void>.delayed(Duration.zero);
      expect(store.writes.last.single.grams, 200);
      final failed = expectLater(edit, throwsStateError);
      store.pending.removeAt(0).completeError(StateError('disk full'));
      await failed;
      expect(controller.entries.single.grams, 100);
    },
  );

  test(
    'AI requests serialize and a failed request does not block the next one',
    () async {
      final first = Completer<http.Response>();
      var calls = 0;
      final client = VoiceApiClient(
        tokenProvider: () async => 'fixture',
        client: MockClient((request) async {
          calls++;
          if (calls == 1) return first.future;
          return http.Response(jsonEncode(replyJson), 200);
        }),
      );
      final daily = client.coach({'mode': 'daily'});
      final failure = expectLater(daily, throwsA(isA<VoiceApiException>()));
      final oracle = client.coach({'mode': 'oracle'});
      await Future<void>.delayed(Duration.zero);
      expect(calls, 1);
      first.complete(http.Response('{}', 503));
      await failure;
      expect((await oracle).headline, reply.headline);
      expect(calls, 2);
    },
  );

  testWidgets(
    'Settings follows a diet change without overwriting unsaved text on unrelated updates',
    (tester) async {
      final controller = AppController(LocalStore());
      await controller.initialize();
      await tester.pumpWidget(
        MaterialApp(
          home: SettingsScreen(
            controller: controller,
            apiClient: FakeCore(),
            voiceApiClient: VoiceApiClient(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await controller.applyDiet(dietPresetById('keto'));
      await tester.pump();
      final fields = tester
          .widgetList<TextField>(find.byType(TextField))
          .toList();
      expect(
        fields[2].controller!.text,
        controller.targets.carbs.toStringAsFixed(0),
      );
      await tester.enterText(find.byType(TextField).first, '2100');
      controller.shiftDate(-1);
      await tester.pump();
      expect(fields.first.controller!.text, '2100');
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'Oracle stays idle offscreen and loads when opened after opt-in',
    (tester) async {
      final controller = AppController(LocalStore());
      await controller.initialize();
      final client = CapturingCoach();
      await tester.pumpWidget(
        MaterialApp(
          home: HomeShell(
            controller: controller,
            apiClient: FakeCore(),
            voiceApiClient: client,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(client.modes, isEmpty);
      await controller.enableCoach();
      await tester.pumpAndSettle();
      expect(client.modes, ['daily']);
      await tester.tap(find.text('Oracle').last);
      await tester.pumpAndSettle();
      expect(client.modes, ['daily', 'oracle']);
      expect(find.text(reply.headline), findsOneWidget);
      expect(find.text(reply.sourceLabel), findsOneWidget);
      await tester.tap(find.text('Today').last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Oracle').last);
      await tester.pumpAndSettle();
      expect(client.modes, ['daily', 'oracle']);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('clearing search invalidates a response already in flight', (
    tester,
  ) async {
    final api = DelayedSearchCore();
    await tester.pumpWidget(
      MaterialApp(
        home: FoodSearchScreen(
          apiClient: api,
          date: DateTime.now(),
          meal: MealType.lunch,
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'apple');
    await tester.pump(const Duration(milliseconds: 500));
    await tester.enterText(find.byType(TextField), '');
    api.pending.complete(
      const FoodSearchResults(
        items: [
          FoodSearchItem(
            foodId: 'apple',
            name: 'Late apple result',
            categoryName: 'Fruit',
            publisher: 'USDA',
            datasetName: 'Fixture',
            qualityStatus: 'complete',
            nutrientCount: 1,
            portionCount: 0,
          ),
        ],
        matchMode: 'all_terms',
        matchedTerms: [],
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Late apple result'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Oracle distinguishes an HTTP 429 from a connection failure', (
    tester,
  ) async {
    final controller = AppController(LocalStore());
    await controller.initialize();
    await controller.enableCoach();
    final client = VoiceApiClient(
      tokenProvider: () async => 'fixture-token',
      client: MockClient((_) async => http.Response('{}', 429)),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: OracleScreen(
          controller: controller,
          coachService: CoachService(client),
          apiClient: FakeCore(),
          voiceApiClient: client,
          onOpenCoach: () {},
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(
      find.textContaining('AI request limit has been reached'),
      findsOneWidget,
    );
    expect(find.textContaining('could not reach'), findsNothing);
    expect(controller.entries, isEmpty);
    expect(tester.takeException(), isNull);
  });
}

const reply = CoachReply(
  headline: 'A test insight',
  message: 'A test response',
  actions: [],
  memoryUpdates: [],
  model: 'fixture',
);
const replyJson = {
  'headline': 'A test insight',
  'message': 'A test response',
  'actions': [],
  'memory_updates': [],
  'model': 'fixture',
};

DiaryEntry foodEntry(String id, List<FoodNutrient> nutrients) =>
    DiaryEntry.fromFood(
      food: FoodDetail(
        foodId: id,
        name: id,
        categoryName: 'Fixture',
        publisher: 'USDA',
        datasetName: 'Fixture',
        sourceFoodCode: id,
        qualityStatus: 'complete',
        nutrients: nutrients,
        portions: [],
      ),
      date: DateTime.now(),
      meal: MealType.breakfast,
      grams: 100,
      servingLabel: 'Edible weight',
      id: id,
    );

class FakeCore extends CoreApiClient {
  @override
  Future<Map<String, dynamic>> health() async => {'status': 'ok'};
}

class DelayedSearchCore extends FakeCore {
  final pending = Completer<FoodSearchResults>();
  @override
  Future<FoodSearchResults> searchFoods(String query, {int limit = 30}) =>
      pending.future;
}

class CapturingCoach extends VoiceApiClient {
  final modes = <String>[];
  @override
  Future<void> warmUp() async {}
  @override
  Future<CoachReply> coach(Map<String, dynamic> request) async {
    modes.add(request['mode'] as String);
    return reply;
  }
}

class BlockingStore extends LocalStore {
  final pending = <Completer<void>>[];
  final writes = <List<DiaryEntry>>[];
  @override
  Future<void> saveEntries(List<DiaryEntry> entries) {
    writes.add(entries);
    final completer = Completer<void>();
    pending.add(completer);
    return completer.future;
  }
}
