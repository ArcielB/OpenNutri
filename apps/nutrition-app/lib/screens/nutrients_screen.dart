import 'package:flutter/material.dart';

import '../models/diary.dart';
import '../state/app_controller.dart';
import '../utils/format.dart';
import '../widgets/day_header.dart';

class NutrientsScreen extends StatelessWidget {
  const NutrientsScreen({super.key, required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final totals = controller.dailyTotals;
    final nutrients = [...totals.nutrients]..sort(_sortNutrients);
    final sections = _groupNutrients(nutrients);
    return Scaffold(
      appBar: AppBar(title: const Text('Nutrition report')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: Column(
            children: [
              DayHeader(controller: controller),
              Expanded(
                child: nutrients.isEmpty
                    ? const _EmptyNutrients()
                    : ListView(
                        padding: const EdgeInsets.fromLTRB(16, 0, 16, 32),
                        children: [
                          _DailyTargetCard(
                            totals: totals,
                            targets: controller.targets,
                            foodCount: controller
                                .entriesForSelectedDate()
                                .length,
                            nutrientCount: nutrients.length,
                          ),
                          const SizedBox(height: 18),
                          for (final section in sections.entries) ...[
                            _SectionHeader(
                              title: section.key,
                              count: section.value.length,
                            ),
                            Card(
                              margin: const EdgeInsets.only(bottom: 16),
                              child: Column(
                                children: [
                                  for (
                                    var index = 0;
                                    index < section.value.length;
                                    index++
                                  ) ...[
                                    _NutrientRow(
                                      nutrient: section.value[index],
                                    ),
                                    if (index < section.value.length - 1)
                                      const Divider(
                                        height: 1,
                                        indent: 16,
                                        endIndent: 16,
                                      ),
                                  ],
                                ],
                              ),
                            ),
                          ],
                        ],
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  static Map<String, List<NutrientTotal>> _groupNutrients(
    List<NutrientTotal> nutrients,
  ) {
    final grouped = <String, List<NutrientTotal>>{
      'Energy & macros': [],
      'Vitamins': [],
      'Minerals': [],
      'Fats & fatty acids': [],
      'Other nutrients': [],
    };
    for (final nutrient in nutrients) {
      grouped[_sectionFor(nutrient.name)]!.add(nutrient);
    }
    grouped.removeWhere((_, values) => values.isEmpty);
    return grouped;
  }

  static String _sectionFor(String name) {
    final lower = name.toLowerCase();
    const mineralTerms = [
      'calcium',
      'iron',
      'magnesium',
      'phosphorus',
      'potassium',
      'sodium',
      'zinc',
      'copper',
      'manganese',
      'selenium',
    ];
    const vitaminTerms = [
      'vitamin',
      'thiamin',
      'riboflavin',
      'niacin',
      'folate',
      'folic acid',
      'choline',
      'carotene',
      'retinol',
      'lycopene',
      'tocopherol',
      'cryptoxanthin',
    ];
    const fatTerms = [
      'fatty acid',
      'cholesterol',
      'saturated',
      'monounsaturated',
      'polyunsaturated',
    ];
    const macroTerms = [
      'energy',
      'protein',
      'carbohydrate',
      'total lipid',
      'fiber',
      'sugar',
      'water',
    ];
    if (mineralTerms.any(lower.contains)) return 'Minerals';
    if (vitaminTerms.any(lower.contains)) return 'Vitamins';
    if (fatTerms.any(lower.contains)) return 'Fats & fatty acids';
    if (macroTerms.any(lower.contains)) return 'Energy & macros';
    return 'Other nutrients';
  }

  static int _sortNutrients(NutrientTotal left, NutrientTotal right) {
    const priority = {
      'Energy': 0,
      'Protein': 1,
      'Carbohydrate, by difference': 2,
      'Total lipid (fat)': 3,
      'Fiber, total dietary': 4,
      'Sugars, Total': 5,
      'Calcium, Ca': 6,
      'Iron, Fe': 7,
      'Sodium, Na': 8,
      'Potassium, K': 9,
    };
    final leftRank = priority[left.name] ?? 100;
    final rightRank = priority[right.name] ?? 100;
    if (leftRank != rightRank) return leftRank.compareTo(rightRank);
    if (left.name != right.name) return left.name.compareTo(right.name);
    return left.unit.compareTo(right.unit);
  }
}

class _DailyTargetCard extends StatelessWidget {
  const _DailyTargetCard({
    required this.totals,
    required this.targets,
    required this.foodCount,
    required this.nutrientCount,
  });

  final DailyTotals totals;
  final NutritionTargets targets;
  final int foodCount;
  final int nutrientCount;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      margin: EdgeInsets.zero,
      color: scheme.primaryContainer.withValues(alpha: 0.48),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Daily progress',
                        style: Theme.of(context).textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.w900),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        '$foodCount ${foodCount == 1 ? 'food' : 'foods'} · $nutrientCount nutrients tracked',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
                Icon(Icons.insights_rounded, color: scheme.primary, size: 30),
              ],
            ),
            const SizedBox(height: 18),
            _TargetProgress(
              label: 'Energy',
              amount: totals.calories,
              target: targets.calories,
              unit: 'kcal',
              color: scheme.tertiary,
            ),
            _TargetProgress(
              label: 'Protein',
              amount: totals.protein,
              target: targets.protein,
              unit: 'g',
              color: scheme.primary,
            ),
            _TargetProgress(
              label: 'Carbohydrate',
              amount: totals.carbs,
              target: targets.carbs,
              unit: 'g',
              color: scheme.secondary,
            ),
            _TargetProgress(
              label: 'Total fat',
              amount: totals.fat,
              target: targets.fat,
              unit: 'g',
              color: const Color(0xFF8B5FBF),
              isLast: true,
            ),
          ],
        ),
      ),
    );
  }
}

class _TargetProgress extends StatelessWidget {
  const _TargetProgress({
    required this.label,
    required this.amount,
    required this.target,
    required this.unit,
    required this.color,
    this.isLast = false,
  });

  final String label;
  final double amount;
  final double target;
  final String unit;
  final Color color;
  final bool isLast;

  @override
  Widget build(BuildContext context) {
    final progress = target <= 0 ? 0.0 : (amount / target).clamp(0.0, 1.0);
    return Padding(
      padding: EdgeInsets.only(bottom: isLast ? 0 : 13),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  label,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
              Text(
                '${formatAmount(amount)} / ${formatAmount(target)} $unit',
                style: Theme.of(context).textTheme.labelMedium,
              ),
            ],
          ),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: progress,
              minHeight: 7,
              color: color,
              backgroundColor: Colors.white.withValues(alpha: 0.65),
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, required this.count});

  final String title;
  final int count;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 0, 4, 8),
      child: Row(
        children: [
          Expanded(
            child: Text(
              title,
              style: Theme.of(
                context,
              ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
            ),
          ),
          Text(
            '$count',
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }
}

class _NutrientRow extends StatelessWidget {
  const _NutrientRow({required this.nutrient});

  final NutrientTotal nutrient;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
      child: Row(
        children: [
          Expanded(child: Text(nutrient.name)),
          const SizedBox(width: 12),
          Text(
            '${formatAmount(nutrient.amount, maximumDecimals: 2)} ${nutrient.unit}',
            style: Theme.of(
              context,
            ).textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w700),
          ),
        ],
      ),
    );
  }
}

class _EmptyNutrients extends StatelessWidget {
  const _EmptyNutrients();

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 76,
              height: 76,
              decoration: BoxDecoration(
                color: scheme.primaryContainer,
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.insights_outlined, color: scheme.primary),
            ),
            const SizedBox(height: 18),
            Text(
              'Your nutrition picture starts here',
              textAlign: TextAlign.center,
              style: Theme.of(
                context,
              ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 8),
            Text(
              'Log a food on Today to see macros, vitamins, minerals, and the full nutrient record.',
              textAlign: TextAlign.center,
              style: Theme.of(
                context,
              ).textTheme.bodyMedium?.copyWith(color: scheme.onSurfaceVariant),
            ),
          ],
        ),
      ),
    );
  }
}
