import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:opennutri_app/models/diary.dart';
import 'package:opennutri_app/models/food.dart';
import 'package:opennutri_app/services/core_api_client.dart';
import 'package:opennutri_app/widgets/entry_detail_sheet.dart';

void main() {
  final original = DiaryEntry.fromFood(
    food: fixtureFood('apple'),
    date: DateTime(2026, 9, 4),
    meal: MealType.lunch,
    grams: 100,
    servingLabel: 'Edible weight',
    id: 'original-entry',
    loggedByVoice: true,
  );

  Future<void> openSheet(WidgetTester tester, List<DiaryEntry> updates) async {
    tester.view.physicalSize = const Size(900, 1400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => TextButton(
              onPressed: () => showModalBottomSheet<void>(
                context: context,
                isScrollControlled: true,
                builder: (_) => EntryDetailSheet(
                  entry: original,
                  apiClient: FixtureCore(),
                  onUpdate: (entry) async => updates.add(entry),
                ),
              ),
              child: const Text('Open entry'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Open entry'));
    await tester.pumpAndSettle();
  }

  testWidgets('cancelling an amount edit leaves the saved entry untouched', (
    tester,
  ) async {
    final updates = <DiaryEntry>[];
    await openSheet(tester, updates);
    await tester.tap(find.byTooltip('Edit amount and meal'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '250');
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(updates, isEmpty);
    expect(find.byType(EntryDetailSheet), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('amount editing accepts decimal commas and keeps identity', (
    tester,
  ) async {
    final updates = <DiaryEntry>[];
    await openSheet(tester, updates);
    await tester.tap(find.byTooltip('Edit amount and meal'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '150,5');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();
    expect(updates.single.id, original.id);
    expect(updates.single.dateKey, original.dateKey);
    expect(updates.single.grams, 150.5);
    expect(updates.single.calories, closeTo(78.26, 0.001));
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'food replacement preserves entry identity and uses new nutrients',
    (tester) async {
      final updates = <DiaryEntry>[];
      await openSheet(tester, updates);
      await tester.tap(find.text('Replace food match'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Banana fixture'));
      // The covered search row keeps its loading spinner until the serving
      // sheet returns, so do not wait for every animation to settle here.
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));
      await tester.tap(find.widgetWithText(FilledButton, 'Add to Lunch'));
      await tester.pumpAndSettle();
      expect(updates, hasLength(1));
      expect(updates.single.id, original.id);
      expect(updates.single.dateKey, original.dateKey);
      expect(updates.single.loggedByVoice, isTrue);
      expect(updates.single.foodId, 'banana');
      expect(updates.single.calories, 89);
      expect(tester.takeException(), isNull);
    },
  );
}

FoodDetail fixtureFood(String id) => FoodDetail(
  foodId: id,
  name: id == 'banana' ? 'Banana fixture' : 'Apple fixture',
  categoryName: 'Fruit',
  publisher: 'USDA',
  datasetName: 'Fixture',
  sourceFoodCode: id,
  qualityStatus: 'complete',
  nutrients: [
    FoodNutrient(
      nutrientId: 'energy',
      name: 'Energy',
      amount: id == 'banana' ? 89 : 52,
      unit: 'kcal',
    ),
  ],
  portions: [],
);

class FixtureCore extends CoreApiClient {
  @override
  Future<FoodDetail> foodDetail(String foodId) async => fixtureFood(foodId);

  @override
  Future<FoodSearchResults> searchFoods(String query, {int limit = 30}) async =>
      const FoodSearchResults(
        items: [
          FoodSearchItem(
            foodId: 'banana',
            name: 'Banana fixture',
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
      );
}
