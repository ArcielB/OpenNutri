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
    return Scaffold(
      appBar: AppBar(title: const Text('Nutrients')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: Column(
            children: [
              DayHeader(controller: controller),
              Expanded(
                child: nutrients.isEmpty
                    ? const Center(child: Text('No nutrients logged'))
                    : ListView(
                        padding: const EdgeInsets.only(bottom: 28),
                        children: [
                          _SectionHeader(title: 'Daily targets'),
                          _TargetRow(
                            name: 'Energy',
                            amount: totals.calories,
                            target: controller.targets.calories,
                            unit: 'kcal',
                          ),
                          _TargetRow(
                            name: 'Protein',
                            amount: totals.protein,
                            target: controller.targets.protein,
                            unit: 'g',
                          ),
                          _TargetRow(
                            name: 'Carbohydrate',
                            amount: totals.carbs,
                            target: controller.targets.carbs,
                            unit: 'g',
                          ),
                          _TargetRow(
                            name: 'Total fat',
                            amount: totals.fat,
                            target: controller.targets.fat,
                            unit: 'g',
                          ),
                          const SizedBox(height: 16),
                          _SectionHeader(title: 'All nutrients'),
                          for (final nutrient in nutrients)
                            _NutrientRow(nutrient: nutrient),
                        ],
                      ),
              ),
            ],
          ),
        ),
      ),
    );
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

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
      child: Text(
        title,
        style: Theme.of(context).textTheme.titleSmall?.copyWith(
          fontWeight: FontWeight.w800,
          letterSpacing: 0,
        ),
      ),
    );
  }
}

class _TargetRow extends StatelessWidget {
  const _TargetRow({
    required this.name,
    required this.amount,
    required this.target,
    required this.unit,
  });

  final String name;
  final double amount;
  final double target;
  final String unit;

  @override
  Widget build(BuildContext context) {
    final progress = target <= 0 ? 0.0 : (amount / target).clamp(0.0, 1.0);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 10),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(child: Text(name)),
              Text(
                '${formatAmount(amount)} / ${formatAmount(target)} $unit',
                style: Theme.of(context).textTheme.labelLarge,
              ),
            ],
          ),
          const SizedBox(height: 7),
          ClipRRect(
            borderRadius: BorderRadius.circular(3),
            child: LinearProgressIndicator(
              value: progress,
              minHeight: 6,
              backgroundColor: Theme.of(context).colorScheme.outlineVariant,
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
    return Column(
      children: [
        ListTile(
          contentPadding: const EdgeInsets.symmetric(horizontal: 20),
          title: Text(nutrient.name),
          trailing: Text(
            '${formatAmount(nutrient.amount, maximumDecimals: 2)} ${nutrient.unit}',
            style: Theme.of(context).textTheme.labelLarge,
          ),
        ),
        const Divider(indent: 20, endIndent: 20),
      ],
    );
  }
}
