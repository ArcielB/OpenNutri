import 'food.dart';

enum MealType { breakfast, lunch, dinner, snacks }

extension MealTypeLabel on MealType {
  String get label => switch (this) {
    MealType.breakfast => 'Breakfast',
    MealType.lunch => 'Lunch',
    MealType.dinner => 'Dinner',
    MealType.snacks => 'Snacks',
  };
}

class NutrientAmount {
  const NutrientAmount({
    required this.nutrientId,
    required this.name,
    required this.amount,
    required this.unit,
  });

  factory NutrientAmount.fromJson(Map<String, dynamic> json) {
    return NutrientAmount(
      nutrientId: json['nutrient_id'] as String,
      name: json['name'] as String,
      amount: (json['amount'] as num).toDouble(),
      unit: json['unit'] as String,
    );
  }

  final String nutrientId;
  final String name;
  final double amount;
  final String unit;

  Map<String, dynamic> toJson() => {
    'nutrient_id': nutrientId,
    'name': name,
    'amount': amount,
    'unit': unit,
  };
}

class DiaryEntry {
  const DiaryEntry({
    required this.id,
    required this.dateKey,
    required this.meal,
    required this.foodId,
    required this.foodName,
    required this.grams,
    required this.servingLabel,
    required this.nutrients,
  });

  factory DiaryEntry.fromFood({
    required FoodDetail food,
    required DateTime date,
    required MealType meal,
    required double grams,
    required String servingLabel,
    String? id,
  }) {
    final multiplier = grams / 100;
    return DiaryEntry(
      id: id ?? DateTime.now().microsecondsSinceEpoch.toString(),
      dateKey: dateKeyFor(date),
      meal: meal,
      foodId: food.foodId,
      foodName: food.name,
      grams: grams,
      servingLabel: servingLabel,
      nutrients: food.nutrients
          .where(
            (nutrient) => nutrient.basis == 'per_100g_edible_portion',
          )
          .map(
            (nutrient) => NutrientAmount(
              nutrientId: nutrient.nutrientId,
              name: nutrient.name,
              amount: nutrient.amount * multiplier,
              unit: nutrient.unit,
            ),
          )
          .toList(growable: false),
    );
  }

  factory DiaryEntry.fromJson(Map<String, dynamic> json) {
    return DiaryEntry(
      id: json['id'] as String,
      dateKey: json['date_key'] as String,
      meal: MealType.values.byName(json['meal'] as String),
      foodId: json['food_id'] as String,
      foodName: json['food_name'] as String,
      grams: (json['grams'] as num).toDouble(),
      servingLabel: json['serving_label'] as String,
      nutrients: (json['nutrients'] as List<dynamic>)
          .map(
            (value) => NutrientAmount.fromJson(value as Map<String, dynamic>),
          )
          .toList(growable: false),
    );
  }

  final String id;
  final String dateKey;
  final MealType meal;
  final String foodId;
  final String foodName;
  final double grams;
  final String servingLabel;
  final List<NutrientAmount> nutrients;

  double nutrientAmount(String name, String unit) {
    for (final nutrient in nutrients) {
      if (nutrient.name == name &&
          nutrient.unit.toLowerCase() == unit.toLowerCase()) {
        return nutrient.amount;
      }
    }
    return 0;
  }

  double get calories {
    final direct = nutrientAmount('Energy', 'kcal');
    if (direct > 0) return direct;
    final specific = nutrientAmount('Energy (Atwater Specific Factors)', 'kcal');
    if (specific > 0) return specific;
    return nutrientAmount('Energy (Atwater General Factors)', 'kcal');
  }
  double get protein => nutrientAmount('Protein', 'g');
  double get carbs => nutrientAmount('Carbohydrate, by difference', 'g');
  double get fat => nutrientAmount('Total lipid (fat)', 'g');

  Map<String, dynamic> toJson() => {
    'id': id,
    'date_key': dateKey,
    'meal': meal.name,
    'food_id': foodId,
    'food_name': foodName,
    'grams': grams,
    'serving_label': servingLabel,
    'nutrients': nutrients.map((value) => value.toJson()).toList(),
  };
}

class NutrientTotal {
  const NutrientTotal({
    required this.nutrientId,
    required this.name,
    required this.amount,
    required this.unit,
  });

  final String nutrientId;
  final String name;
  final double amount;
  final String unit;
}

class DailyTotals {
  DailyTotals(List<DiaryEntry> entries) : nutrients = _aggregate(entries);

  final List<NutrientTotal> nutrients;

  static List<NutrientTotal> _aggregate(List<DiaryEntry> entries) {
    final totals = <String, NutrientTotal>{};
    for (final entry in entries) {
      for (final nutrient in entry.nutrients) {
        final key = '${nutrient.nutrientId}|${nutrient.unit}';
        final current = totals[key];
        totals[key] = NutrientTotal(
          nutrientId: nutrient.nutrientId,
          name: nutrient.name,
          amount: (current?.amount ?? 0) + nutrient.amount,
          unit: nutrient.unit,
        );
      }
    }
    return totals.values.toList(growable: false);
  }

  double amountFor(String name, String unit) {
    for (final nutrient in nutrients) {
      if (nutrient.name == name &&
          nutrient.unit.toLowerCase() == unit.toLowerCase()) {
        return nutrient.amount;
      }
    }
    return 0;
  }

  double get calories {
    final direct = amountFor('Energy', 'kcal');
    if (direct > 0) return direct;
    final specific = amountFor('Energy (Atwater Specific Factors)', 'kcal');
    if (specific > 0) return specific;
    return amountFor('Energy (Atwater General Factors)', 'kcal');
  }
  double get protein => amountFor('Protein', 'g');
  double get carbs => amountFor('Carbohydrate, by difference', 'g');
  double get fat => amountFor('Total lipid (fat)', 'g');
}

class NutritionTargets {
  const NutritionTargets({
    this.calories = 2000,
    this.protein = 100,
    this.carbs = 250,
    this.fat = 70,
  });

  factory NutritionTargets.fromJson(Map<String, dynamic> json) {
    return NutritionTargets(
      calories: (json['calories'] as num?)?.toDouble() ?? 2000,
      protein: (json['protein'] as num?)?.toDouble() ?? 100,
      carbs: (json['carbs'] as num?)?.toDouble() ?? 250,
      fat: (json['fat'] as num?)?.toDouble() ?? 70,
    );
  }

  final double calories;
  final double protein;
  final double carbs;
  final double fat;

  Map<String, dynamic> toJson() => {
    'calories': calories,
    'protein': protein,
    'carbs': carbs,
    'fat': fat,
  };
}

String dateKeyFor(DateTime date) {
  final local = date.toLocal();
  return '${local.year.toString().padLeft(4, '0')}-'
      '${local.month.toString().padLeft(2, '0')}-'
      '${local.day.toString().padLeft(2, '0')}';
}
