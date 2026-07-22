import 'package:flutter/material.dart';

import '../models/diary.dart';
import '../utils/format.dart';

class DailySummary extends StatelessWidget {
  const DailySummary({super.key, required this.totals, required this.targets});

  final DailyTotals totals;
  final NutritionTargets targets;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      color: scheme.surfaceContainerHighest.withValues(alpha: 0.25),
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 20),
      child: Column(
        children: [
          Row(
            children: [
              SizedBox(
                width: 80,
                height: 80,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    SizedBox.expand(
                      child: CircularProgressIndicator(
                        value: _progress(totals.calories, targets.calories),
                        strokeWidth: 7,
                        backgroundColor: scheme.outlineVariant,
                        color: scheme.tertiary,
                      ),
                    ),
                    Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          formatAmount(totals.calories, maximumDecimals: 0),
                          style: Theme.of(context).textTheme.titleLarge
                              ?.copyWith(
                                fontWeight: FontWeight.w800,
                                letterSpacing: 0,
                              ),
                        ),
                        Text(
                          'kcal',
                          style: Theme.of(context).textTheme.labelSmall,
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 20),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${formatAmount((targets.calories - totals.calories).clamp(0, double.infinity), maximumDecimals: 0)} kcal remaining',
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      '${formatAmount(totals.calories, maximumDecimals: 0)} of ${formatAmount(targets.calories, maximumDecimals: 0)} kcal',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              Expanded(
                child: _MacroProgress(
                  label: 'Protein',
                  value: totals.protein,
                  target: targets.protein,
                  color: scheme.primary,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: _MacroProgress(
                  label: 'Carbs',
                  value: totals.carbs,
                  target: targets.carbs,
                  color: scheme.secondary,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: _MacroProgress(
                  label: 'Fat',
                  value: totals.fat,
                  target: targets.fat,
                  color: scheme.tertiary,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  double _progress(double value, double target) {
    if (target <= 0) return 0;
    return (value / target).clamp(0, 1);
  }
}

class _MacroProgress extends StatelessWidget {
  const _MacroProgress({
    required this.label,
    required this.value,
    required this.target,
    required this.color,
  });

  final String label;
  final double value;
  final double target;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final progress = target <= 0 ? 0.0 : (value / target).clamp(0.0, 1.0);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: Theme.of(context).textTheme.labelMedium),
        const SizedBox(height: 5),
        ClipRRect(
          borderRadius: BorderRadius.circular(3),
          child: LinearProgressIndicator(
            value: progress,
            minHeight: 6,
            color: color,
            backgroundColor: Theme.of(context).colorScheme.outlineVariant,
          ),
        ),
        const SizedBox(height: 5),
        Text(
          '${formatAmount(value)} / ${formatAmount(target)} g',
          maxLines: 1,
          overflow: TextOverflow.fade,
          softWrap: false,
          style: Theme.of(context).textTheme.labelSmall,
        ),
      ],
    );
  }
}
