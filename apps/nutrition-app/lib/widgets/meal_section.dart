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
  });

  final MealType meal;
  final List<DiaryEntry> entries;
  final VoidCallback onAdd;
  final ValueChanged<String> onRemove;

  @override
  Widget build(BuildContext context) {
    final calories = entries.fold<double>(
      0,
      (total, entry) => total + entry.calories,
    );
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 10, 10, 8),
          child: Row(
            children: [
              Icon(
                _iconFor(meal),
                size: 20,
                color: Theme.of(context).colorScheme.primary,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  meal.label,
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0,
                  ),
                ),
              ),
              Text(
                '${formatAmount(calories, maximumDecimals: 0)} kcal',
                style: Theme.of(context).textTheme.labelMedium,
              ),
              IconButton(
                tooltip: 'Add ${meal.label.toLowerCase()} food',
                onPressed: onAdd,
                icon: const Icon(Icons.add_circle_outline),
              ),
            ],
          ),
        ),
        for (final entry in entries)
          Dismissible(
            key: ValueKey(entry.id),
            direction: DismissDirection.endToStart,
            onDismissed: (_) => onRemove(entry.id),
            background: Container(
              alignment: Alignment.centerRight,
              color: Theme.of(context).colorScheme.errorContainer,
              padding: const EdgeInsets.only(right: 22),
              child: Icon(
                Icons.delete_outline,
                color: Theme.of(context).colorScheme.error,
              ),
            ),
            child: ListTile(
              contentPadding: const EdgeInsets.only(left: 50, right: 12),
              title: Text(
                entry.foodName,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              subtitle: Text(
                '${entry.servingLabel} - ${formatAmount(entry.grams)} g',
              ),
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    formatAmount(entry.calories, maximumDecimals: 0),
                    style: Theme.of(context).textTheme.labelLarge,
                  ),
                  PopupMenuButton<void>(
                    tooltip: 'Entry actions',
                    itemBuilder: (context) => [
                      PopupMenuItem<void>(
                        onTap: () => onRemove(entry.id),
                        child: const ListTile(
                          contentPadding: EdgeInsets.zero,
                          leading: Icon(Icons.delete_outline),
                          title: Text('Remove'),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        const Divider(indent: 20, endIndent: 20),
      ],
    );
  }

  IconData _iconFor(MealType value) => switch (value) {
    MealType.breakfast => Icons.wb_sunny_outlined,
    MealType.lunch => Icons.light_mode_outlined,
    MealType.dinner => Icons.nights_stay_outlined,
    MealType.snacks => Icons.cookie_outlined,
  };
}
