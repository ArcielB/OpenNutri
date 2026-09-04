import 'package:flutter/material.dart';

import '../models/diary.dart';
import '../models/personalization.dart';
import '../services/core_api_client.dart';
import '../services/voice_api_client.dart';
import '../state/app_controller.dart';
import '../utils/format.dart';
import '../widgets/daily_summary.dart';
import '../widgets/daily_coach_card.dart';
import '../widgets/day_header.dart';
import '../widgets/entry_detail_sheet.dart';
import '../widgets/meal_section.dart';
import 'food_search_screen.dart';

class TodayScreen extends StatelessWidget {
  const TodayScreen({
    super.key,
    required this.controller,
    required this.apiClient,
    required this.voiceApiClient,
    required this.onVoice,
    required this.dailyCoachBrief,
    required this.coachEnabled,
    required this.coachLoading,
    required this.onOpenCoach,
  });

  final AppController controller;
  final CoreApiClient apiClient;
  final VoiceApiClient voiceApiClient;
  final Future<void> Function({bool autoStart}) onVoice;
  final DailyCoachBrief? dailyCoachBrief;
  final bool coachEnabled;
  final bool coachLoading;
  final VoidCallback onOpenCoach;

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

  Future<void> _repeatFood(BuildContext context, DiaryEntry source) async {
    final repeated = await controller.repeatEntry(source);
    if (!context.mounted) return;
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(
        SnackBar(
          content: Text('${source.foodName} added to ${source.meal.label}'),
          action: SnackBarAction(
            label: 'Undo',
            onPressed: () => controller.removeEntry(repeated.id),
          ),
        ),
      );
  }

  Future<void> _showEntry(BuildContext context, DiaryEntry entry) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      builder: (context) => EntryDetailSheet(
        entry: entry,
        apiClient: apiClient,
        onUpdate: controller.updateEntry,
      ),
    );
  }

  MealType get _suggestedMeal {
    final hour = DateTime.now().hour;
    if (hour < 11) return MealType.breakfast;
    if (hour < 16) return MealType.lunch;
    if (hour < 21) return MealType.dinner;
    return MealType.snacks;
  }

  @override
  Widget build(BuildContext context) {
    final recent = controller.recentEntries(limit: 5);
    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.primary,
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.eco, size: 20, color: Colors.white),
            ),
            const SizedBox(width: 10),
            const Text('OpenNutri'),
          ],
        ),
        actions: [
          IconButton.filledTonal(
            tooltip: 'Voice log',
            onPressed: () => onVoice(autoStart: true),
            icon: const Icon(Icons.mic_rounded),
          ),
          const SizedBox(width: 12),
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
              SliverToBoxAdapter(
                child: DailyCoachCard(
                  enabled: coachEnabled,
                  brief: dailyCoachBrief,
                  loading: coachLoading,
                  onOpen: onOpenCoach,
                ),
              ),
              SliverToBoxAdapter(
                child: _QuickLogCard(
                  onVoice: () => onVoice(autoStart: true),
                  onSearch: () => _addFood(context, _suggestedMeal),
                ),
              ),
              if (recent.isNotEmpty)
                SliverToBoxAdapter(
                  child: _RecentFoods(
                    entries: recent,
                    onRepeat: (entry) => _repeatFood(context, entry),
                  ),
                ),
              SliverToBoxAdapter(
                child: Padding(
                  padding: EdgeInsets.fromLTRB(
                    20,
                    recent.isEmpty ? 16 : 4,
                    20,
                    6,
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Your meals',
                          style: Theme.of(context).textTheme.titleLarge
                              ?.copyWith(fontWeight: FontWeight.w900),
                        ),
                      ),
                      Text(
                        '${controller.entriesForSelectedDate().length} logged',
                        style: Theme.of(context).textTheme.labelMedium
                            ?.copyWith(
                              color: Theme.of(
                                context,
                              ).colorScheme.onSurfaceVariant,
                            ),
                      ),
                    ],
                  ),
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
                      onEntryTap: (entry) => _showEntry(context, entry),
                    ),
                  const SizedBox(height: 28),
                ]),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _QuickLogCard extends StatelessWidget {
  const _QuickLogCard({required this.onVoice, required this.onSearch});

  final VoidCallback onVoice;
  final VoidCallback onSearch;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 4, 16, 14),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: scheme.secondaryContainer.withValues(alpha: 0.65),
        borderRadius: BorderRadius.circular(22),
      ),
      child: Row(
        children: [
          Container(
            width: 54,
            height: 54,
            decoration: BoxDecoration(
              color: scheme.secondary,
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.graphic_eq_rounded, color: Colors.white),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'What did you eat?',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  'Say the whole meal. We’ll find the foods and amounts.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: scheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    FilledButton.icon(
                      onPressed: onVoice,
                      icon: const Icon(Icons.mic_rounded, size: 19),
                      label: const Text('Speak meal'),
                    ),
                    TextButton.icon(
                      onPressed: onSearch,
                      icon: const Icon(Icons.search, size: 19),
                      label: const Text('Type instead'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _RecentFoods extends StatelessWidget {
  const _RecentFoods({required this.entries, required this.onRepeat});

  final List<DiaryEntry> entries;
  final ValueChanged<DiaryEntry> onRepeat;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
            child: Text(
              'Quick repeat',
              style: Theme.of(
                context,
              ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w800),
            ),
          ),
          SizedBox(
            height: 86,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: entries.length,
              separatorBuilder: (_, _) => const SizedBox(width: 9),
              itemBuilder: (context, index) {
                final entry = entries[index];
                return Material(
                  color: scheme.surfaceContainerLow,
                  shape: RoundedRectangleBorder(
                    side: BorderSide(color: scheme.outlineVariant),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  clipBehavior: Clip.antiAlias,
                  child: InkWell(
                    onTap: () => onRepeat(entry),
                    child: SizedBox(
                      width: 172,
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(13, 11, 8, 10),
                        child: Row(
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Text(
                                    entry.foodName,
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                    style: Theme.of(context)
                                        .textTheme
                                        .labelLarge
                                        ?.copyWith(fontWeight: FontWeight.w700),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    '${formatAmount(entry.calories, maximumDecimals: 0)} kcal · ${entry.meal.label}',
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: Theme.of(
                                      context,
                                    ).textTheme.labelSmall,
                                  ),
                                ],
                              ),
                            ),
                            Icon(Icons.add_circle, color: scheme.primary),
                          ],
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
