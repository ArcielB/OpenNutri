import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:opennutri_app/models/diary.dart';
import 'package:opennutri_app/models/food.dart';
import 'package:opennutri_app/screens/home_shell.dart';
import 'package:opennutri_app/services/core_api_client.dart';
import 'package:opennutri_app/services/local_store.dart';
import 'package:opennutri_app/state/app_controller.dart';

void main() {
  testWidgets('renders a logged food before persistence finishes', (
    tester,
  ) async {
    final store = _BlockingLocalStore();
    final controller = AppController(store);
    final entry = DiaryEntry.fromFood(
      food: _apple,
      date: controller.selectedDate,
      meal: MealType.breakfast,
      grams: 100,
      servingLabel: 'Edible weight',
      id: 'entry-apple',
    );

    await tester.pumpWidget(
      MaterialApp(
        home: HomeShell(
          controller: controller,
          apiClient: CoreApiClient(),
        ),
      ),
    );
    expect(find.text(_apple.name), findsNothing);

    final save = controller.addEntry(entry);
    await tester.pump();

    expect(find.text(_apple.name), findsOneWidget);
    expect(find.text('52'), findsNWidgets(2));

    store.finishSave();
    await save;
  });
}

const _apple = FoodDetail(
  foodId: 'food-apple',
  name: 'Apple, raw',
  categoryName: 'Fruit',
  publisher: 'USDA Agricultural Research Service',
  datasetName: 'USDA SR Legacy',
  sourceFoodCode: '09003',
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

class _BlockingLocalStore extends LocalStore {
  final _save = Completer<void>();

  @override
  Future<void> saveEntries(List<DiaryEntry> entries) => _save.future;

  void finishSave() => _save.complete();
}
