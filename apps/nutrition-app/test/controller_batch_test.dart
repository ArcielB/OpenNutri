import 'package:flutter_test/flutter_test.dart';
import 'package:opennutri_app/models/diary.dart';
import 'package:opennutri_app/models/food.dart';
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

  test(
    'voice disclosure and feedback consent are persisted independently',
    () async {
      final store = _CountingStore();
      final controller = AppController(store);
      await controller.initialize();

      await controller.acceptVoiceDisclosure(feedbackConsent: true);
      expect(controller.voiceDisclosureAccepted, isTrue);
      expect(controller.voiceFeedbackConsent, isTrue);
      expect(store.disclosureAccepted, isTrue);
      expect(store.feedbackConsent, isTrue);

      await controller.updateVoiceFeedbackConsent(false);
      expect(controller.voiceDisclosureAccepted, isTrue);
      expect(controller.voiceFeedbackConsent, isFalse);
      expect(store.feedbackConsent, isFalse);
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
  int entrySaveCount = 0;
  List<DiaryEntry> lastSaved = const [];
  bool disclosureAccepted = false;
  bool feedbackConsent = false;

  @override
  Future<List<DiaryEntry>> loadEntries() async => const [];

  @override
  Future<NutritionTargets> loadTargets() async => const NutritionTargets();

  @override
  Future<bool> loadVoiceDisclosureAccepted() async => disclosureAccepted;

  @override
  Future<bool> loadVoiceFeedbackConsent() async => feedbackConsent;

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
}
