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
  }) {
    return _client.coach(
      requestPayload(controller: controller, mode: mode, message: message),
    );
  }

  Future<CoachReply> respondVoice({
    required AppController controller,
    required String wavPath,
    required String languageHint,
  }) => _client.coachVoice(
    wavPath: wavPath,
    languageHint: languageHint,
    context: requestPayload(controller: controller, mode: CoachMode.chat),
  );

  Map<String, dynamic> requestPayload({
    required AppController controller,
    required CoachMode mode,
    String? message,
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
      'daily_totals': _metrics(totals, controller.targets),
      'recent_foods': controller
          .entriesForSelectedDate()
          .take(30)
          .map(
            (entry) => {
              'name': entry.foodName,
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
  ) {
    return [
      _metric('Energy', totals.calories, 'kcal', targets.calories),
      _metric('Protein', totals.protein, 'g', targets.protein),
      _metric('Carbohydrate', totals.carbs, 'g', targets.carbs),
      _metric('Total fat', totals.fat, 'g', targets.fat),
      _metric(
        'Dietary fiber',
        _amount(totals, ['Fiber, total dietary'], 'g'),
        'g',
        28,
      ),
      _metric('Calcium', _amount(totals, ['Calcium, Ca'], 'mg'), 'mg', 1300),
      _metric('Iron', _amount(totals, ['Iron, Fe'], 'mg'), 'mg', 18),
      _metric('Potassium', _amount(totals, ['Potassium, K'], 'mg'), 'mg', 4700),
      _metric('Magnesium', _amount(totals, ['Magnesium, Mg'], 'mg'), 'mg', 420),
      _metric(
        'Vitamin C',
        _amount(totals, ['Vitamin C, total ascorbic acid'], 'mg'),
        'mg',
        90,
      ),
      _metric(
        'Vitamin D',
        _amount(totals, ['Vitamin D (D2 + D3)', 'Vitamin D'], 'mcg'),
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

  double _amount(DailyTotals totals, List<String> names, String unit) {
    for (final name in names) {
      final amount = totals.amountFor(name, unit);
      if (amount > 0) return amount;
    }
    return 0;
  }

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
