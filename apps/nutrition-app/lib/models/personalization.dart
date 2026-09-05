import 'diary.dart';

enum NutritionGoal { eatWell, loseFat, buildMuscle, moreEnergy, performance }

extension NutritionGoalLabel on NutritionGoal {
  String get label => switch (this) {
    NutritionGoal.eatWell => 'Eat well',
    NutritionGoal.loseFat => 'Lose fat',
    NutritionGoal.buildMuscle => 'Build muscle',
    NutritionGoal.moreEnergy => 'More energy',
    NutritionGoal.performance => 'Perform better',
  };
}

class DietPreset {
  const DietPreset({
    required this.id,
    required this.name,
    required this.tagline,
    required this.description,
    required this.iconName,
    required this.carbsShare,
    required this.proteinShare,
    required this.fatShare,
    required this.principles,
  });

  final String id;
  final String name;
  final String tagline;
  final String description;
  final String iconName;
  final double carbsShare;
  final double proteinShare;
  final double fatShare;
  final List<String> principles;

  NutritionTargets targetsForCalories(
    double calories, {
    NutritionGoal goal = NutritionGoal.eatWell,
  }) {
    var carbs = carbsShare;
    var protein = proteinShare;
    var fat = fatShare;
    if (goal == NutritionGoal.buildMuscle || goal == NutritionGoal.loseFat) {
      final shift = carbs >= 0.20 ? 0.05 : 0.0;
      carbs -= shift;
      protein += shift;
    } else if (goal == NutritionGoal.performance && id != 'keto') {
      final shift = fat >= 0.20 ? 0.05 : 0.0;
      fat -= shift;
      carbs += shift;
    }
    return NutritionTargets(
      calories: calories,
      protein: calories * protein / 4,
      carbs: calories * carbs / 4,
      fat: calories * fat / 9,
    );
  }
}

const dietPresets = <DietPreset>[
  DietPreset(
    id: 'balanced',
    name: 'Flexible balance',
    tagline: 'Simple, varied, sustainable',
    description:
        'A practical baseline with room for every food group and personal taste.',
    iconName: 'balance',
    carbsShare: 0.45,
    proteinShare: 0.25,
    fatShare: 0.30,
    principles: [
      'Build meals around minimally processed foods',
      'Include a protein source at each main meal',
      'Use variety instead of rigid exclusions',
    ],
  ),
  DietPreset(
    id: 'mediterranean',
    name: 'Mediterranean',
    tagline: 'Plants, olive oil, fish, legumes',
    description:
        'A produce-forward pattern inspired by traditional Mediterranean eating.',
    iconName: 'sun',
    carbsShare: 0.45,
    proteinShare: 0.20,
    fatShare: 0.35,
    principles: [
      'Favor vegetables, fruit, legumes, and whole grains',
      'Use olive oil and nuts as common fat sources',
      'Choose fish regularly and keep red meat occasional',
    ],
  ),
  DietPreset(
    id: 'high_protein',
    name: 'High protein',
    tagline: 'Training and satiety focused',
    description:
        'A protein-forward template with carbohydrates retained for training and daily life.',
    iconName: 'fitness',
    carbsShare: 0.35,
    proteinShare: 0.35,
    fatShare: 0.30,
    principles: [
      'Distribute protein across the day',
      'Pair training meals with useful carbohydrates',
      'Keep fruit, vegetables, and fiber visible',
    ],
  ),
  DietPreset(
    id: 'plant_powered',
    name: 'Plant powered',
    tagline: 'Legumes, grains, seeds, color',
    description:
        'A plant-centered pattern that can be customized as vegan or simply plant-forward.',
    iconName: 'plant',
    carbsShare: 0.55,
    proteinShare: 0.20,
    fatShare: 0.25,
    principles: [
      'Rotate legumes, tofu, nuts, seeds, and whole grains',
      'Prioritize iron, calcium, vitamin B12, and protein planning',
      'Use a wide variety of vegetables and fruit',
    ],
  ),
  DietPreset(
    id: 'keto',
    name: 'Low-carb keto',
    tagline: 'Very low carbohydrate template',
    description:
        'A restrictive low-carbohydrate template that should be adapted carefully to the person.',
    iconName: 'bolt',
    carbsShare: 0.10,
    proteinShare: 0.25,
    fatShare: 0.65,
    principles: [
      'Keep carbohydrates deliberately low',
      'Choose unsaturated fats and varied protein sources',
      'Plan fiber-rich low-carbohydrate plants',
    ],
  ),
  DietPreset(
    id: 'blue_zones',
    name: 'Blue Zones inspired',
    tagline: 'Plant-forward meals built around everyday staples',
    description:
        'A mostly plant-based pattern inspired by common themes reported in long-lived communities—not a guarantee of longevity.',
    iconName: 'public',
    carbsShare: 0.60,
    proteinShare: 0.15,
    fatShare: 0.25,
    principles: [
      'Make beans, vegetables, and whole grains routine',
      'Use nuts and minimally processed staples',
      'Treat the pattern as inspiration, not a medical promise',
    ],
  ),
];

DietPreset dietPresetById(String id) => dietPresets.firstWhere(
  (preset) => preset.id == id,
  orElse: () => dietPresets.first,
);

class CoachMemory {
  const CoachMemory({required this.fact, required this.category});

  factory CoachMemory.fromJson(Map<String, dynamic> json) => CoachMemory(
    fact: json['fact'] as String,
    category: json['category'] as String? ?? 'context',
  );

  final String fact;
  final String category;

  Map<String, dynamic> toJson() => {'fact': fact, 'category': category};
}

class UserNutritionProfile {
  const UserNutritionProfile({
    this.goal = NutritionGoal.eatWell,
    this.dietId = 'balanced',
    this.dietNotes = '',
    this.memories = const [],
    this.coachEnabled = false,
  });

  factory UserNutritionProfile.fromJson(Map<String, dynamic> json) =>
      UserNutritionProfile(
        goal:
            NutritionGoal.values
                .where((value) => value.name == json['goal'])
                .firstOrNull ??
            NutritionGoal.eatWell,
        dietId: json['diet_id'] as String? ?? 'balanced',
        dietNotes: json['diet_notes'] as String? ?? '',
        memories: ((json['memories'] as List<dynamic>?) ?? const [])
            .map((value) => CoachMemory.fromJson(value as Map<String, dynamic>))
            .toList(growable: false),
        coachEnabled:
            json['coach_enabled'] == true &&
            json['coach_disclosure_version'] == 2,
      );

  final NutritionGoal goal;
  final String dietId;
  final String dietNotes;
  final List<CoachMemory> memories;
  final bool coachEnabled;

  DietPreset get diet => dietPresetById(dietId);

  UserNutritionProfile copyWith({
    NutritionGoal? goal,
    String? dietId,
    String? dietNotes,
    List<CoachMemory>? memories,
    bool? coachEnabled,
  }) => UserNutritionProfile(
    goal: goal ?? this.goal,
    dietId: dietId ?? this.dietId,
    dietNotes: dietNotes ?? this.dietNotes,
    memories: memories ?? this.memories,
    coachEnabled: coachEnabled ?? this.coachEnabled,
  );

  Map<String, dynamic> toJson() => {
    'goal': goal.name,
    'diet_id': dietId,
    'diet_notes': dietNotes,
    'memories': memories.map((memory) => memory.toJson()).toList(),
    'coach_enabled': coachEnabled,
    'coach_disclosure_version': 2,
  };
}

class CoachAction {
  const CoachAction({
    required this.title,
    required this.detail,
    this.searchQuery,
  });

  factory CoachAction.fromJson(Map<String, dynamic> json) => CoachAction(
    title: json['title'] as String,
    detail: json['detail'] as String,
    searchQuery: json['search_query'] as String?,
  );

  final String title;
  final String detail;
  final String? searchQuery;

  Map<String, dynamic> toJson() => {
    'title': title,
    'detail': detail,
    'search_query': searchQuery,
  };
}

class CoachReply {
  const CoachReply({
    required this.headline,
    required this.message,
    required this.actions,
    required this.memoryUpdates,
    required this.model,
    this.safetyNote,
    this.transcript,
  });

  factory CoachReply.fromJson(Map<String, dynamic> json) => CoachReply(
    headline: json['headline'] as String,
    message: json['message'] as String,
    actions: (json['actions'] as List<dynamic>? ?? const [])
        .map((value) => CoachAction.fromJson(value as Map<String, dynamic>))
        .toList(growable: false),
    memoryUpdates: (json['memory_updates'] as List<dynamic>? ?? const [])
        .map((value) => CoachMemory.fromJson(value as Map<String, dynamic>))
        .toList(growable: false),
    model: json['model'] as String? ?? 'unknown',
    safetyNote: json['safety_note'] as String?,
    transcript: json['transcript'] as String?,
  );

  final String headline;
  final String message;
  final List<CoachAction> actions;
  final List<CoachMemory> memoryUpdates;
  final String model;
  final String? safetyNote;
  final String? transcript;
}

class DailyCoachBrief {
  const DailyCoachBrief({
    required this.dateKey,
    required this.reply,
    this.generatedByAi = true,
  });

  factory DailyCoachBrief.fromJson(Map<String, dynamic> json) =>
      DailyCoachBrief(
        dateKey: json['date_key'] as String,
        reply: CoachReply.fromJson(json['reply'] as Map<String, dynamic>),
        generatedByAi: json['generated_by_ai'] as bool? ?? true,
      );

  final String dateKey;
  final CoachReply reply;
  final bool generatedByAi;

  Map<String, dynamic> toJson() => {
    'date_key': dateKey,
    'reply': {
      'headline': reply.headline,
      'message': reply.message,
      'actions': reply.actions.map((action) => action.toJson()).toList(),
      'memory_updates': reply.memoryUpdates
          .map((memory) => memory.toJson())
          .toList(),
      'model': reply.model,
      'safety_note': reply.safetyNote,
      'transcript': reply.transcript,
    },
    'generated_by_ai': generatedByAi,
  };
}
