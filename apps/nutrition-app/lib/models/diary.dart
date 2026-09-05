import 'food.dart';

enum MealType { breakfast, lunch, dinner, snacks }

enum LoggedWeightBasis { edible, asPurchased }

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
    required this.inputGrams,
    required this.weightBasis,
    required this.servingLabel,
    required this.nutrients,
    this.loggedByVoice = false,
    this.needsReview = false,
  });

  factory DiaryEntry.fromFood({
    required FoodDetail food,
    required DateTime date,
    required MealType meal,
    required double grams,
    required String servingLabel,
    double? inputGrams,
    LoggedWeightBasis weightBasis = LoggedWeightBasis.edible,
    String? id,
    bool loggedByVoice = false,
    bool needsReview = false,
  }) {
    final multiplier = grams / 100;
    return DiaryEntry(
      id: id ?? DateTime.now().microsecondsSinceEpoch.toString(),
      dateKey: dateKeyFor(date),
      meal: meal,
      foodId: food.foodId,
      foodName: food.name,
      grams: grams,
      inputGrams: inputGrams ?? grams,
      weightBasis: weightBasis,
      servingLabel: servingLabel,
      nutrients: food.nutrients
          .where((nutrient) => nutrient.basis == 'per_100g_edible_portion')
          .map(
            (nutrient) => NutrientAmount(
              nutrientId: nutrient.nutrientId,
              name: nutrient.name,
              amount: nutrient.amount * multiplier,
              unit: nutrient.unit,
            ),
          )
          .toList(growable: false),
      loggedByVoice: loggedByVoice,
      needsReview: needsReview,
    );
  }

  factory DiaryEntry.fromJson(Map<String, dynamic> json) {
    final grams = (json['grams'] as num).toDouble();
    return DiaryEntry(
      id: json['id'] as String,
      dateKey: json['date_key'] as String,
      meal: MealType.values.byName(json['meal'] as String),
      foodId: json['food_id'] as String,
      foodName: json['food_name'] as String,
      grams: grams,
      inputGrams: (json['input_grams'] as num?)?.toDouble() ?? grams,
      weightBasis: LoggedWeightBasis.values.byName(
        json['weight_basis'] as String? ?? LoggedWeightBasis.edible.name,
      ),
      servingLabel: json['serving_label'] as String,
      nutrients: (json['nutrients'] as List<dynamic>)
          .map(
            (value) => NutrientAmount.fromJson(value as Map<String, dynamic>),
          )
          .toList(growable: false),
      loggedByVoice: json['logged_by_voice'] as bool? ?? false,
      needsReview: json['needs_review'] as bool? ?? false,
    );
  }

  final String id;
  final String dateKey;
  final MealType meal;
  final String foodId;
  final String foodName;

  /// Edible grams used to scale the per-100 g nutrient profile.
  final double grams;
  final double inputGrams;
  final LoggedWeightBasis weightBasis;
  final String servingLabel;
  final List<NutrientAmount> nutrients;
  final bool loggedByVoice;
  final bool needsReview;

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
    final specific = nutrientAmount(
      'Energy (Atwater Specific Factors)',
      'kcal',
    );
    if (specific > 0) return specific;
    return nutrientAmount('Energy (Atwater General Factors)', 'kcal');
  }

  double get protein => nutrientAmount('Protein', 'g');
  double get carbs => nutrientAmount('Carbohydrate, by difference', 'g');
  double get fat => nutrientAmount('Total lipid (fat)', 'g');

  DiaryEntry copyFor({required DateTime date, MealType? meal, String? id}) {
    return DiaryEntry(
      id: id ?? DateTime.now().microsecondsSinceEpoch.toString(),
      dateKey: dateKeyFor(date),
      meal: meal ?? this.meal,
      foodId: foodId,
      foodName: foodName,
      grams: grams,
      inputGrams: inputGrams,
      weightBasis: weightBasis,
      servingLabel: servingLabel,
      nutrients: nutrients,
      loggedByVoice: loggedByVoice,
      needsReview: needsReview,
    );
  }

  DiaryEntry withEditedServing({
    required double inputGrams,
    required MealType meal,
    bool needsReview = false,
  }) {
    if (!inputGrams.isFinite || inputGrams <= 0 || inputGrams > 10000) {
      throw ArgumentError.value(
        inputGrams,
        'inputGrams',
        'Invalid serving weight',
      );
    }
    final safeOriginalInput = this.inputGrams > 0 ? this.inputGrams : grams;
    final ratio = inputGrams / safeOriginalInput;
    return DiaryEntry(
      id: id,
      dateKey: dateKey,
      meal: meal,
      foodId: foodId,
      foodName: foodName,
      grams: grams * ratio,
      inputGrams: inputGrams,
      weightBasis: weightBasis,
      servingLabel: servingLabel,
      nutrients: nutrients
          .map(
            (nutrient) => NutrientAmount(
              nutrientId: nutrient.nutrientId,
              name: nutrient.name,
              amount: nutrient.amount * ratio,
              unit: nutrient.unit,
            ),
          )
          .toList(growable: false),
      loggedByVoice: loggedByVoice,
      needsReview: needsReview,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'date_key': dateKey,
    'meal': meal.name,
    'food_id': foodId,
    'food_name': foodName,
    'grams': grams,
    'input_grams': inputGrams,
    'weight_basis': weightBasis.name,
    'serving_label': servingLabel,
    'nutrients': nutrients.map((value) => value.toJson()).toList(),
    'logged_by_voice': loggedByVoice,
    'needs_review': needsReview,
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
  DailyTotals(List<DiaryEntry> entries)
    : nutrients = _aggregate(entries),
      _calories = entries.fold(0, (sum, entry) => sum + entry.calories);

  final double _calories;

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
    var total = 0.0;
    for (final nutrient in nutrients) {
      if (nutrient.name == name &&
          nutrient.unit.toLowerCase() == unit.toLowerCase()) {
        total += nutrient.amount;
      }
    }
    return total;
  }

  // Pick each food's authoritative energy field before adding foods together;
  // choosing once after aggregation loses foods using a different USDA field.
  double get calories => _calories;

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
