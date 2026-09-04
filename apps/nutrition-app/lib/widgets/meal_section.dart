import 'package:flutter/material.dart';

import '../models/diary.dart';
import '../utils/format.dart';

class MealSection extends StatelessWidget {
  const MealSection({
    super.key,
    required this.meal,
    required this.entries,
    required this.onAdd,
    required this.onRemove,
    required this.onEntryTap,
  });

  final MealType meal;
  final List<DiaryEntry> entries;
  final VoidCallback onAdd;
  final ValueChanged<String> onRemove;
  final ValueChanged<DiaryEntry> onEntryTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final calories = entries.fold<double>(
      0,
      (total, entry) => total + entry.calories,
    );
    return Card(
      margin: const EdgeInsets.fromLTRB(16, 6, 16, 6),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 8, 10),
            child: Row(
              children: [
                Container(
                  width: 38,
                  height: 38,
                  decoration: BoxDecoration(
                    color: _colorFor(meal, scheme).withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(
                    _iconFor(meal),
                    size: 20,
                    color: _colorFor(meal, scheme),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        meal.label,
                        style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                          letterSpacing: 0,
                        ),
                      ),
                      Text(
                        entries.isEmpty
                            ? 'Nothing logged yet'
                            : '${entries.length} ${entries.length == 1 ? 'item' : 'items'} · ${formatAmount(calories, maximumDecimals: 0)} kcal',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
                IconButton.filledTonal(
                  tooltip: 'Add ${meal.label.toLowerCase()} food',
                  onPressed: onAdd,
                  icon: const Icon(Icons.add, size: 20),
                ),
              ],
            ),
          ),
          if (entries.isNotEmpty) const Divider(height: 1),
          for (final entry in entries)
            Dismissible(
              key: ValueKey(entry.id),
              direction: DismissDirection.endToStart,
              onDismissed: (_) => onRemove(entry.id),
              background: Container(
                alignment: Alignment.centerRight,
                color: scheme.errorContainer,
                padding: const EdgeInsets.only(right: 22),
                child: Icon(Icons.delete_outline, color: scheme.error),
              ),
              child: InkWell(
                onTap: () => onEntryTap(entry),
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(18, 13, 10, 13),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              entry.foodName,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context).textTheme.bodyLarge
                                  ?.copyWith(fontWeight: FontWeight.w700),
                            ),
                            const SizedBox(height: 3),
                            Text(
                              entry.weightBasis == LoggedWeightBasis.asPurchased
                                  ? '${entry.servingLabel} · ${formatAmount(entry.inputGrams)} g bought · ${formatAmount(entry.grams)} g edible'
                                  : '${entry.servingLabel} · ${formatAmount(entry.grams)} g',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context).textTheme.bodySmall
                                  ?.copyWith(color: scheme.onSurfaceVariant),
                            ),
                            if (entry.needsReview) ...[
                              const SizedBox(height: 4),
                              Row(
                                children: [
                                  Icon(
                                    Icons.auto_awesome,
                                    size: 13,
                                    color: scheme.tertiary,
                                  ),
                                  const SizedBox(width: 4),
                                  Text(
                                    'Quick estimate · tap to edit',
                                    style: Theme.of(context)
                                        .textTheme
                                        .labelSmall
                                        ?.copyWith(
                                          color: scheme.tertiary,
                                          fontWeight: FontWeight.w700,
                                        ),
                                  ),
                                ],
                              ),
                            ],
                          ],
                        ),
                      ),
                      const SizedBox(width: 12),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text(
                            formatAmount(entry.calories, maximumDecimals: 0),
                            style: Theme.of(context).textTheme.titleMedium
                                ?.copyWith(fontWeight: FontWeight.w800),
                          ),
                          Text(
                            'kcal',
                            style: Theme.of(context).textTheme.labelSmall,
                          ),
                        ],
                      ),
                      const SizedBox(width: 4),
                      Icon(Icons.chevron_right, color: scheme.outline),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Color _colorFor(MealType value, ColorScheme scheme) => switch (value) {
    MealType.breakfast => const Color(0xFFC66A24),
    MealType.lunch => scheme.primary,
    MealType.dinner => scheme.secondary,
    MealType.snacks => const Color(0xFF8B5FBF),
  };

  IconData _iconFor(MealType value) => switch (value) {
    MealType.breakfast => Icons.wb_sunny_outlined,
    MealType.lunch => Icons.light_mode_outlined,
    MealType.dinner => Icons.nights_stay_outlined,
    MealType.snacks => Icons.cookie_outlined,
  };
}
