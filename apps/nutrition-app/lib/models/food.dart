class FoodSearchResults {
  const FoodSearchResults({
    required this.items,
    required this.matchMode,
    required this.matchedTerms,
  });

  factory FoodSearchResults.fromJson(Map<String, dynamic> json) {
    return FoodSearchResults(
      items: (json['items'] as List<dynamic>)
          .map((value) => FoodSearchItem.fromJson(value as Map<String, dynamic>))
          .toList(growable: false),
      matchMode: json['match_mode'] as String,
      matchedTerms: (json['matched_terms'] as List<dynamic>).cast<String>(),
    );
  }

  final List<FoodSearchItem> items;
  final String matchMode;
  final List<String> matchedTerms;

  bool get isPartial => matchMode == 'partial_terms';
}

class FoodSearchItem {
  const FoodSearchItem({
    required this.foodId,
    required this.name,
    required this.categoryName,
    required this.publisher,
    required this.datasetName,
    required this.qualityStatus,
    required this.nutrientCount,
    required this.portionCount,
  });

  factory FoodSearchItem.fromJson(Map<String, dynamic> json) {
    final category = json['category'] as Map<String, dynamic>;
    final source = json['source'] as Map<String, dynamic>;
    final quality = json['quality'] as Map<String, dynamic>;
    return FoodSearchItem(
      foodId: json['food_id'] as String,
      name: json['name'] as String,
      categoryName: category['name'] as String,
      publisher: source['publisher'] as String,
      datasetName: source['dataset_name'] as String,
      qualityStatus: quality['status'] as String,
      nutrientCount: quality['nutrient_count'] as int,
      portionCount: quality['portion_count'] as int,
    );
  }

  final String foodId;
  final String name;
  final String categoryName;
  final String publisher;
  final String datasetName;
  final String qualityStatus;
  final int nutrientCount;
  final int portionCount;
}

class FoodDetail {
  const FoodDetail({
    required this.foodId,
    required this.name,
    required this.categoryName,
    required this.publisher,
    required this.datasetName,
    required this.sourceFoodCode,
    required this.qualityStatus,
    required this.nutrients,
    required this.portions,
  });

  factory FoodDetail.fromJson(Map<String, dynamic> json) {
    final category = json['category'] as Map<String, dynamic>;
    final source = json['source'] as Map<String, dynamic>;
    final quality = json['quality'] as Map<String, dynamic>;
    return FoodDetail(
      foodId: json['food_id'] as String,
      name: json['name'] as String,
      categoryName: category['name'] as String,
      publisher: source['publisher'] as String,
      datasetName: source['dataset_name'] as String,
      sourceFoodCode: source['source_food_code'] as String,
      qualityStatus: quality['status'] as String,
      nutrients: (json['nutrients'] as List<dynamic>)
          .map((value) => FoodNutrient.fromJson(value as Map<String, dynamic>))
          .toList(growable: false),
      portions: (json['portions'] as List<dynamic>)
          .map((value) => FoodPortion.fromJson(value as Map<String, dynamic>))
          .toList(growable: false),
    );
  }

  final String foodId;
  final String name;
  final String categoryName;
  final String publisher;
  final String datasetName;
  final String sourceFoodCode;
  final String qualityStatus;
  final List<FoodNutrient> nutrients;
  final List<FoodPortion> portions;

  double nutrientAmount(String name, String unit) {
    for (final nutrient in nutrients) {
      if (nutrient.name == name &&
          nutrient.unit.toLowerCase() == unit.toLowerCase()) {
        return nutrient.amount;
      }
    }
    return 0;
  }

  double get caloriesPer100g {
    final direct = nutrientAmount('Energy', 'kcal');
    if (direct > 0) return direct;
    final specific = nutrientAmount('Energy (Atwater Specific Factors)', 'kcal');
    if (specific > 0) return specific;
    return nutrientAmount('Energy (Atwater General Factors)', 'kcal');
  }
}

class FoodNutrient {
  const FoodNutrient({
    required this.nutrientId,
    required this.name,
    required this.amount,
    required this.unit,
    this.basis = 'per_100g_edible_portion',
  });

  factory FoodNutrient.fromJson(Map<String, dynamic> json) {
    return FoodNutrient(
      nutrientId: json['nutrient_id'] as String,
      name: json['name'] as String,
      amount: (json['amount'] as num).toDouble(),
      unit: json['unit'] as String,
      basis: json['basis'] as String,
    );
  }

  final String nutrientId;
  final String name;
  final double amount;
  final String unit;
  final String basis;
}

class FoodPortion {
  const FoodPortion({
    required this.portionId,
    required this.description,
    required this.gramWeight,
  });

  factory FoodPortion.fromJson(Map<String, dynamic> json) {
    return FoodPortion(
      portionId: json['portion_id'] as String,
      description: json['description'] as String,
      gramWeight: (json['gram_weight'] as num).toDouble(),
    );
  }

  final String portionId;
  final String description;
  final double gramWeight;
}
