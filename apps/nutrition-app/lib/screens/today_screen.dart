import 'package:flutter/material.dart';

import '../models/diary.dart';
import '../services/core_api_client.dart';
import '../services/voice_api_client.dart';
import '../state/app_controller.dart';
import '../widgets/daily_summary.dart';
import '../widgets/day_header.dart';
import '../widgets/meal_section.dart';
import 'food_search_screen.dart';

class TodayScreen extends StatelessWidget {
  const TodayScreen({
    super.key,
    required this.controller,
    required this.apiClient,
    required this.voiceApiClient,
    required this.onVoice,
  });

  final AppController controller;
  final CoreApiClient apiClient;
  final VoiceApiClient voiceApiClient;
  final Future<void> Function({bool autoStart}) onVoice;

  Future<void> _addFood(BuildContext context, MealType meal) async {
    final entry = await Navigator.of(context).push<DiaryEntry>(
      MaterialPageRoute(
        builder: (context) => FoodSearchScreen(
          apiClient: apiClient,
          resolver: voiceApiClient,
          meal: meal,
          date: controller.selectedDate,
        ),
      ),
    );
    if (entry != null) await controller.addEntry(entry);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 30,
              height: 30,
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.primary,
                borderRadius: BorderRadius.circular(7),
              ),
              child: const Icon(Icons.eco, size: 19, color: Colors.white),
            ),
            const SizedBox(width: 10),
            const Text('OpenNutri'),
          ],
        ),
        actions: [
          IconButton(
            tooltip: 'Voice log',
            onPressed: () => onVoice(autoStart: false),
            icon: const Icon(Icons.mic_none),
          ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: CustomScrollView(
            slivers: [
              SliverToBoxAdapter(child: DayHeader(controller: controller)),
              SliverToBoxAdapter(
                child: DailySummary(
                  totals: controller.dailyTotals,
                  targets: controller.targets,
                ),
              ),
              SliverList(
                delegate: SliverChildListDelegate([
                  for (final meal in MealType.values)
                    MealSection(
                      meal: meal,
                      entries: controller.entriesForMeal(meal),
                      onAdd: () => _addFood(context, meal),
                      onRemove: controller.removeEntry,
                    ),
                  const SizedBox(height: 24),
                ]),
              ),
            ],
          ),
        ),
      ),
      floatingActionButton: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          FloatingActionButton.small(
            heroTag: 'voice-log',
            tooltip: 'Voice log',
            onPressed: () => onVoice(autoStart: false),
            child: const Icon(Icons.mic),
          ),
          const SizedBox(width: 12),
          FloatingActionButton.extended(
            heroTag: 'add-food',
            onPressed: () => _addFood(context, MealType.snacks),
            icon: const Icon(Icons.add),
            label: const Text('Add food'),
          ),
        ],
      ),
    );
  }
}
