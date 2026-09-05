import 'dart:ui';

import '../models/diary.dart';
import '../models/personalization.dart';
import '../state/app_controller.dart';
import 'voice_api_client.dart';

enum CoachMode { daily, chat, oracle, dietPlan }

extension on CoachMode {
  String get wireName => switch (this) {
    CoachMode.daily => 'daily',
    CoachMode.chat => 'chat',
    CoachMode.oracle => 'oracle',
    CoachMode.dietPlan => 'diet_plan',
  };
}

class CoachService {
  CoachService(this._client);

  final VoiceApiClient _client;

  Future<CoachReply> respond({
    required AppController controller,
    required CoachMode mode,
    String? message,
    List<Map<String, String>> conversation = const [],
  }) {
    return _client.coach(
      requestPayload(
        controller: controller,
        mode: mode,
        message: message,
        conversation: conversation,
      ),
    );
  }

  Future<CoachReply> respondVoice({
    required AppController controller,
    required String wavPath,
    required String languageHint,
    List<Map<String, String>> conversation = const [],
  }) => _client.coachVoice(
    wavPath: wavPath,
    languageHint: languageHint,
    context: requestPayload(
      controller: controller,
      mode: CoachMode.chat,
      conversation: conversation,
    ),
  );

  Map<String, dynamic> requestPayload({
    required AppController controller,
    required CoachMode mode,
    String? message,
    List<Map<String, String>> conversation = const [],
  }) {
    final totals = controller.dailyTotals;
    final profile = controller.profile;
    return {
      'mode': mode.wireName,
      'locale': PlatformDispatcher.instance.locale.toLanguageTag(),
      'local_date': dateKeyFor(controller.selectedDate),
      'goal': profile.goal.label,
      'diet': profile.diet.name,
      'diet_notes': profile.dietNotes,
      'memories': profile.memories.map((memory) => memory.fact).toList(),
      'daily_totals': _metrics(
        totals,
        controller.targets,
        controller.entriesForSelectedDate(),
      ),
      if (mode == CoachMode.chat) 'conversation': conversation,
      'recent_foods': controller
          .entriesForSelectedDate()
          .reversed
          .take(30)
          .map(
            (entry) => {
              'name': entry.foodName.length <= 160
                  ? entry.foodName
                  : entry.foodName.substring(0, 160),
              'grams': entry.grams,
              'meal': entry.meal.name,
            },
          )
          .toList(),
      if (message != null && message.trim().isNotEmpty)
        'user_message': message.trim(),
    };
  }

  /// FDA label Daily Values for adults and children 4+, used as broad reference
  /// points rather than individualized medical targets.
  List<Map<String, dynamic>> _metrics(
    DailyTotals totals,
    NutritionTargets targets,
    List<DiaryEntry> entries,
  ) {
    return [
      _metric('Energy', totals.calories, 'kcal', targets.calories),
      _metric('Protein', totals.protein, 'g', targets.protein),
      _metric('Carbohydrate', totals.carbs, 'g', targets.carbs),
      _metric('Total fat', totals.fat, 'g', targets.fat),
      _nutrientMetric(
        entries,
        'Dietary fiber',
        ['Fiber, total dietary'],
        'g',
        28,
      ),
      _nutrientMetric(entries, 'Calcium', ['Calcium, Ca'], 'mg', 1300),
      _nutrientMetric(entries, 'Iron', ['Iron, Fe'], 'mg', 18),
      _nutrientMetric(entries, 'Potassium', ['Potassium, K'], 'mg', 4700),
      _nutrientMetric(entries, 'Magnesium', ['Magnesium, Mg'], 'mg', 420),
      _nutrientMetric(
        entries,
        'Vitamin C',
        ['Vitamin C, total ascorbic acid'],
        'mg',
        90,
      ),
      _nutrientMetric(
        entries,
        'Vitamin D',
        ['Vitamin D (D2 + D3)', 'Vitamin D'],
        'mcg',
        20,
      ),
    ];
  }

  Map<String, dynamic> _metric(
    String name,
    double amount,
    String unit,
    double target,
  ) => {'name': name, 'amount': amount, 'unit': unit, 'target': target};

  Map<String, dynamic> _nutrientMetric(
    List<DiaryEntry> entries,
    String label,
    List<String> names,
    String unit,
    double target,
  ) {
    var known = 0;
    var amount = 0.0;
    for (final entry in entries) {
      final value = entry.nutrients
          .where(
            (nutrient) =>
                names.contains(nutrient.name) &&
                _unit(nutrient.unit) == _unit(unit),
          )
          .firstOrNull;
      if (value == null) continue;
      known++;
      amount += value.amount;
    }
    return {
      'name': label,
      'amount': known == 0 ? null : amount,
      'unit': unit,
      'target': target,
      'logged_foods_with_value': known,
      'logged_food_count': entries.length,
    };
  }

  String _unit(String value) => switch (value.toLowerCase().trim()) {
    'µg' || 'μg' || 'ug' || 'mcg' => 'mcg',
    final unit => unit,
  };

  DailyCoachBrief localDailyFallback(AppController controller) {
    final totals = controller.dailyTotals;
    final targets = controller.targets;
    final progress = <(String, double, String)>[
      (
        'energy',
        totals.calories / targets.calories,
        'Plan the next meal around foods you genuinely enjoy.',
      ),
      (
        'protein',
        totals.protein / targets.protein,
        'Add a clear protein source to the next meal.',
      ),
      (
        'carbohydrate',
        totals.carbs / targets.carbs,
        'Choose a fiber-rich carbohydrate and a colorful plant.',
      ),
      (
        'fat',
        totals.fat / targets.fat,
        'Use a measured portion of an unsaturated fat source.',
      ),
    ]..sort((a, b) => a.$2.compareTo(b.$2));
    final opportunity = progress.first;
    return DailyCoachBrief(
      dateKey: dateKeyFor(controller.selectedDate),
      generatedByAi: false,
      reply: CoachReply(
        headline: controller.entriesForSelectedDate().isEmpty
            ? 'Start with one honest meal'
            : 'Your clearest opportunity: ${opportunity.$1}',
        message: controller.entriesForSelectedDate().isEmpty
            ? 'Log what you eat and OpenNutri will turn today’s real data into a focused suggestion.'
            : opportunity.$3,
        actions: const [],
        memoryUpdates: const [],
        model: 'on-device gap analysis',
      ),
    );
  }
}
