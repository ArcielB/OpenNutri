import 'package:flutter_test/flutter_test.dart';
import 'package:opennutri_app/models/diary.dart';
import 'package:opennutri_app/models/food.dart';
import 'package:opennutri_app/models/personalization.dart';
import 'package:opennutri_app/services/local_store.dart';
import 'package:opennutri_app/state/app_controller.dart';

void main() {
  test(
    'addEntries persists a voice batch once and removeEntries undoes it once',
    () async {
      final store = _CountingStore();
      final controller = AppController(store);
      await controller.initialize();
      final entries = [
        _entry('one', MealType.breakfast),
        _entry('two', MealType.breakfast),
      ];

      await controller.addEntries(entries);

      expect(controller.entries, hasLength(2));
      expect(store.entrySaveCount, 1);
      expect(store.lastSaved.map((entry) => entry.id), ['one', 'two']);

      await controller.removeEntries(entries.map((entry) => entry.id));

      expect(controller.entries, isEmpty);
      expect(store.entrySaveCount, 2);
    },
  );

  test('an estimated voice entry can be corrected in place', () async {
    final store = _CountingStore();
    final controller = AppController(store);
    await controller.initialize();
    final estimated = DiaryEntry.fromFood(
      food: _apple,
      date: DateTime(2026, 7, 24),
      meal: MealType.snacks,
      grams: 100,
      servingLabel: 'Edible weight',
      id: 'voice-apple',
      loggedByVoice: true,
      needsReview: true,
    );
    await controller.addEntry(estimated);

    await controller.updateEntry(
      estimated.withEditedServing(inputGrams: 150, meal: MealType.breakfast),
    );

    final corrected = controller.entries.single;
    expect(corrected.id, 'voice-apple');
    expect(corrected.grams, 150);
    expect(corrected.calories, 78);
    expect(corrected.meal, MealType.breakfast);
    expect(corrected.needsReview, isFalse);
    expect(store.entrySaveCount, 2);
  });

  test(
    'voice disclosure and feedback consent are persisted independently',
    () async {
      final store = _CountingStore();
      final controller = AppController(store);
      await controller.initialize();

      await controller.acceptVoiceDisclosure(feedbackConsent: true);
      expect(controller.voiceDisclosureAccepted, isTrue);
      expect(controller.voiceFeedbackConsent, isTrue);
      expect(controller.voiceFastLogging, isTrue);
      expect(store.disclosureAccepted, isTrue);
      expect(store.feedbackConsent, isTrue);

      await controller.updateVoiceFeedbackConsent(false);
      expect(controller.voiceDisclosureAccepted, isTrue);
      expect(controller.voiceFeedbackConsent, isFalse);
      expect(store.feedbackConsent, isFalse);

      await controller.updateVoiceFastLogging(false);
      expect(controller.voiceFastLogging, isFalse);
      expect(store.fastLogging, isFalse);
    },
  );

  test(
    'recent foods are unique and can be repeated on the selected day',
    () async {
      final store = _CountingStore(
        initialEntries: [
          _entry('older-apple', MealType.breakfast),
          _entry('newer-apple', MealType.snacks),
        ],
      );
      final controller = AppController(store);
      await controller.initialize();
      controller.selectDate(DateTime(2026, 7, 25));

      expect(controller.recentEntries(), hasLength(1));
      expect(controller.recentEntries().single.id, 'newer-apple');

      final repeated = await controller.repeatEntry(
        controller.recentEntries().single,
        meal: MealType.lunch,
      );

      expect(repeated.dateKey, '2026-07-25');
      expect(repeated.meal, MealType.lunch);
      expect(repeated.id, isNot('newer-apple'));
      expect(controller.entriesForMeal(MealType.lunch), [repeated]);
      expect(store.entrySaveCount, 1);
    },
  );
}

DiaryEntry _entry(String id, MealType meal) {
  return DiaryEntry.fromFood(
    food: _apple,
    date: DateTime(2026, 7, 24),
    meal: meal,
    grams: 100,
    servingLabel: 'Edible weight',
    id: id,
  );
}

const _apple = FoodDetail(
  foodId: 'food-apple',
  name: 'Apple, raw',
  categoryName: 'Fruit',
  publisher: 'USDA',
  datasetName: 'Fixture',
  sourceFoodCode: '1',
  qualityStatus: 'complete',
  nutrients: [
    FoodNutrient(
      nutrientId: 'energy',
      name: 'Energy',
      amount: 52,
      unit: 'kcal',
    ),
  ],
  portions: [],
);

class _CountingStore extends LocalStore {
  _CountingStore({this.initialEntries = const []});

  final List<DiaryEntry> initialEntries;
  int entrySaveCount = 0;
  List<DiaryEntry> lastSaved = const [];
  bool disclosureAccepted = false;
  bool feedbackConsent = false;
  bool fastLogging = true;

  @override
  Future<List<DiaryEntry>> loadEntries() async => initialEntries;

  @override
  Future<NutritionTargets> loadTargets() async => const NutritionTargets();

  @override
  Future<bool> loadVoiceDisclosureAccepted() async => disclosureAccepted;

  @override
  Future<bool> loadVoiceFeedbackConsent() async => feedbackConsent;

  @override
  Future<bool> loadVoiceFastLogging() async => fastLogging;

  @override
  Future<UserNutritionProfile> loadProfile() async =>
      const UserNutritionProfile();

  @override
  Future<DailyCoachBrief?> loadDailyCoachBrief() async => null;

  @override
  Future<void> saveProfile(UserNutritionProfile profile) async {}

  @override
  Future<void> saveDailyCoachBrief(DailyCoachBrief brief) async {}

  @override
  Future<void> saveEntries(List<DiaryEntry> entries) async {
    entrySaveCount += 1;
    lastSaved = List.of(entries);
  }

  @override
  Future<void> saveVoiceDisclosureAccepted(bool accepted) async {
    disclosureAccepted = accepted;
  }

  @override
  Future<void> saveVoiceFeedbackConsent(bool enabled) async {
    feedbackConsent = enabled;
  }

  @override
  Future<void> saveVoiceFastLogging(bool enabled) async {
    fastLogging = enabled;
  }
}
