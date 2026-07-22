import 'package:flutter/material.dart';

import '../models/diary.dart';
import '../services/core_api_client.dart';
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
  });

  final AppController controller;
  final CoreApiClient apiClient;

  Future<void> _addFood(BuildContext context, MealType meal) async {
    final entry = await Navigator.of(context).push<DiaryEntry>(
      MaterialPageRoute(
        builder: (context) => FoodSearchScreen(
          apiClient: apiClient,
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
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _addFood(context, MealType.snacks),
        icon: const Icon(Icons.add),
        label: const Text('Add food'),
      ),
    );
  }
}
