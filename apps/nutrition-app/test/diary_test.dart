import 'package:flutter_test/flutter_test.dart';
import 'package:opennutri_app/models/diary.dart';
import 'package:opennutri_app/models/food.dart';

void main() {
  const food = FoodDetail(
    foodId: 'food-apple',
    name: 'Apple, raw',
    categoryName: 'Fruit',
    publisher: 'USDA Agricultural Research Service',
    datasetName: 'FNDDS',
    sourceFoodCode: '90010000',
    qualityStatus: 'complete',
    nutrients: [
      FoodNutrient(
        nutrientId: 'energy',
        name: 'Energy',
        amount: 52,
        unit: 'kcal',
      ),
      FoodNutrient(
        nutrientId: 'protein',
        name: 'Protein',
        amount: 0.26,
        unit: 'g',
      ),
      FoodNutrient(
        nutrientId: 'carbs',
        name: 'Carbohydrate, by difference',
        amount: 13.81,
        unit: 'g',
      ),
      FoodNutrient(
        nutrientId: 'fat',
        name: 'Total lipid (fat)',
        amount: 0.17,
        unit: 'g',
      ),
    ],
    portions: [],
  );
  const rawDrumstick = FoodDetail(
    foodId: 'food-drumstick',
    name: 'Chicken, broilers or fryers, drumstick, meat and skin, raw',
    categoryName: 'Poultry Products',
    publisher: 'USDA Agricultural Research Service',
    datasetName: 'USDA SR Legacy',
    sourceFoodCode: '05066',
    qualityStatus: 'complete',
    nutrients: [
      FoodNutrient(
        nutrientId: 'energy',
        name: 'Energy',
        amount: 161,
        unit: 'kcal',
      ),
      FoodNutrient(
        nutrientId: 'protein',
        name: 'Protein',
        amount: 18.08,
        unit: 'g',
      ),
    ],
    portions: [],
    weightFactors: [
      EdiblePortionFactor(
        factorId: 'factor-drumstick',
        factorType: 'as_purchased_to_edible',
        edibleFraction: 0.67,
        refusePercent: 33,
        refuseDescription: 'Bone and cartilage 33%',
        sourceDataset: 'USDA SR28',
        sourceUrl: 'https://example.test/sr28.zip',
        sourceFoodCode: '05066',
        sourceRefusePercent: 66,
        derivation: 'reviewed_component_crosscheck',
        reviewStatus: 'reviewed',
        isUsable: true,
        notes: null,
      ),
    ],
  );

  test('scales per-100 g nutrients to the logged weight', () {
    final entry = DiaryEntry.fromFood(
      food: food,
      date: DateTime(2026, 7, 22),
      meal: MealType.breakfast,
      grams: 182,
      servingLabel: '1 medium',
      id: 'entry-1',
    );

    expect(entry.calories, closeTo(94.64, 0.001));
    expect(entry.protein, closeTo(0.4732, 0.001));
    expect(entry.carbs, closeTo(25.1342, 0.001));
    expect(entry.dateKey, '2026-07-22');
  });

  test('aggregates nutrients across diary entries', () {
    final entries = [
      DiaryEntry.fromFood(
        food: food,
        date: DateTime(2026, 7, 22),
        meal: MealType.breakfast,
        grams: 100,
        servingLabel: '100 g',
        id: 'entry-1',
      ),
      DiaryEntry.fromFood(
        food: food,
        date: DateTime(2026, 7, 22),
        meal: MealType.snacks,
        grams: 50,
        servingLabel: '50 g',
        id: 'entry-2',
      ),
    ];

    final totals = DailyTotals(entries);

    expect(totals.calories, closeTo(78, 0.001));
    expect(totals.carbs, closeTo(20.715, 0.001));
  });

  test('scales as-purchased weight through the reviewed edible fraction', () {
    final factor = rawDrumstick.asPurchasedFactor!;
    final edibleGrams = factor.edibleGramsFor(500);
    final entry = DiaryEntry.fromFood(
      food: rawDrumstick,
      date: DateTime(2026, 7, 23),
      meal: MealType.dinner,
      grams: edibleGrams,
      inputGrams: 500,
      weightBasis: LoggedWeightBasis.asPurchased,
      servingLabel: 'As purchased',
      id: 'entry-drumstick',
    );

    expect(edibleGrams, 335);
    expect(entry.calories, closeTo(539.35, 0.001));
    expect(entry.protein, closeTo(60.568, 0.001));
    expect(entry.inputGrams, 500);
    expect(entry.grams, 335);
    expect(entry.weightBasis, LoggedWeightBasis.asPurchased);

    final restored = DiaryEntry.fromJson(entry.toJson());
    expect(restored.inputGrams, 500);
    expect(restored.grams, 335);
    expect(restored.weightBasis, LoggedWeightBasis.asPurchased);
  });

  test('diary entries survive JSON persistence round trip', () {
    final original = DiaryEntry.fromFood(
      food: food,
      date: DateTime(2026, 7, 22),
      meal: MealType.lunch,
      grams: 125,
      servingLabel: '125 g',
      id: 'entry-1',
    );

    final restored = DiaryEntry.fromJson(original.toJson());

    expect(restored.id, original.id);
    expect(restored.meal, MealType.lunch);
    expect(restored.grams, 125);
    expect(restored.nutrients.length, original.nutrients.length);
    expect(restored.calories, closeTo(original.calories, 0.001));
  });

  test('copyFor keeps the exact nutrition snapshot on a new day', () {
    final original = DiaryEntry.fromFood(
      food: food,
      date: DateTime(2026, 7, 22),
      meal: MealType.lunch,
      grams: 125,
      servingLabel: '125 g',
      id: 'entry-original',
    );

    final repeated = original.copyFor(
      date: DateTime(2026, 7, 25),
      meal: MealType.dinner,
      id: 'entry-repeat',
    );

    expect(repeated.id, 'entry-repeat');
    expect(repeated.dateKey, '2026-07-25');
    expect(repeated.meal, MealType.dinner);
    expect(repeated.foodId, original.foodId);
    expect(repeated.grams, original.grams);
    expect(repeated.nutrients, same(original.nutrients));
  });

  test('uses Foundation Atwater energy and excludes physical properties', () {
    const foundationFood = FoodDetail(
      foodId: 'foundation-apple',
      name: 'Apples, red delicious, with skin, raw',
      categoryName: 'Fruits and Fruit Juices',
      publisher: 'USDA Agricultural Research Service',
      datasetName: 'USDA FoodData Central Foundation Foods',
      sourceFoodCode: '',
      qualityStatus: 'complete',
      nutrients: [
        FoodNutrient(
          nutrientId: 'energy-specific',
          name: 'Energy (Atwater Specific Factors)',
          amount: 55.6,
          unit: 'kcal',
        ),
        FoodNutrient(
          nutrientId: 'specific-gravity',
          name: 'Specific Gravity',
          amount: 1.04,
          unit: 'ratio',
          basis: 'physical_property',
        ),
      ],
      portions: [],
    );

    final entry = DiaryEntry.fromFood(
      food: foundationFood,
      date: DateTime(2026, 7, 22),
      meal: MealType.snacks,
      grams: 150,
      servingLabel: '150 g',
    );

    expect(foundationFood.caloriesPer100g, 55.6);
    expect(entry.calories, closeTo(83.4, 0.001));
    expect(entry.nutrients, hasLength(1));
  });
}
