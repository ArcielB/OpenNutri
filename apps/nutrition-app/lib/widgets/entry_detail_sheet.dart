import 'package:flutter/material.dart';

import '../models/diary.dart';
import '../models/food.dart';
import '../services/core_api_client.dart';
import '../utils/format.dart';

class EntryDetailSheet extends StatefulWidget {
  const EntryDetailSheet({
    super.key,
    required this.entry,
    required this.apiClient,
    required this.onUpdate,
  });

  final DiaryEntry entry;
  final CoreApiClient apiClient;
  final Future<void> Function(DiaryEntry entry) onUpdate;

  @override
  State<EntryDetailSheet> createState() => _EntryDetailSheetState();
}

class _EntryDetailSheetState extends State<EntryDetailSheet> {
  late final Future<FoodDetail> _detail;

  @override
  void initState() {
    super.initState();
    _detail = widget.apiClient.foodDetail(widget.entry.foodId);
  }

  Future<void> _editEntry() async {
    final amount = TextEditingController(
      text: widget.entry.inputGrams.toStringAsFixed(
        widget.entry.inputGrams % 1 == 0 ? 0 : 1,
      ),
    );
    var meal = widget.entry.meal;
    final updated = await showDialog<DiaryEntry>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Edit logged food'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: amount,
                autofocus: true,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: InputDecoration(
                  labelText: 'Amount',
                  suffixText: 'g',
                  helperText:
                      widget.entry.weightBasis == LoggedWeightBasis.asPurchased
                      ? 'As-purchased weight'
                      : 'Edible weight',
                ),
              ),
              const SizedBox(height: 14),
              DropdownButtonFormField<MealType>(
                initialValue: meal,
                decoration: const InputDecoration(labelText: 'Meal'),
                items: [
                  for (final value in MealType.values)
                    DropdownMenuItem(value: value, child: Text(value.label)),
                ],
                onChanged: (value) {
                  if (value != null) setDialogState(() => meal = value);
                },
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                final grams = double.tryParse(amount.text.replaceAll(',', '.'));
                if (grams == null || grams <= 0) return;
                Navigator.pop(
                  context,
                  widget.entry.withEditedServing(inputGrams: grams, meal: meal),
                );
              },
              child: const Text('Save'),
            ),
          ],
        ),
      ),
    );
    amount.dispose();
    if (updated == null || !mounted) return;
    await widget.onUpdate(updated);
    if (!mounted) return;
    Navigator.pop(context);
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('Food updated')));
  }

  @override
  Widget build(BuildContext context) {
    final entry = widget.entry;
    final scheme = Theme.of(context).colorScheme;
    final nutrients = [...entry.nutrients]
      ..sort((left, right) => left.name.compareTo(right.name));
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.78,
      minChildSize: 0.55,
      maxChildSize: 0.94,
      builder: (context, scrollController) => ListView(
        controller: scrollController,
        padding: const EdgeInsets.fromLTRB(20, 4, 20, 32),
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 46,
                height: 46,
                decoration: BoxDecoration(
                  color: scheme.primaryContainer,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(Icons.verified_outlined, color: scheme.primary),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      entry.foodName,
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${entry.meal.label} · ${entry.servingLabel}',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                    ),
                    if (entry.needsReview) ...[
                      const SizedBox(height: 5),
                      Text(
                        'Quick estimate · tap Edit to check',
                        style: Theme.of(context).textTheme.labelMedium
                            ?.copyWith(
                              color: scheme.tertiary,
                              fontWeight: FontWeight.w700,
                            ),
                      ),
                    ],
                  ],
                ),
              ),
              IconButton.filledTonal(
                tooltip: 'Edit amount and meal',
                onPressed: _editEntry,
                icon: const Icon(Icons.edit_outlined),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: scheme.primaryContainer.withValues(alpha: 0.55),
              borderRadius: BorderRadius.circular(18),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'How this was calculated',
                  style: Theme.of(
                    context,
                  ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 6),
                Text(
                  entry.weightBasis == LoggedWeightBasis.asPurchased
                      ? '${formatAmount(entry.inputGrams)} g as purchased was converted to ${formatAmount(entry.grams)} g edible weight. Nutrients were then scaled from the verified per-100 g edible profile.'
                      : '${formatAmount(entry.grams)} g edible weight × the verified per-100 g nutrient profile.',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),
          Text(
            'Source',
            style: Theme.of(
              context,
            ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 8),
          FutureBuilder<FoodDetail>(
            future: _detail,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: SizedBox.square(
                    dimension: 22,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                  title: Text('Checking source record…'),
                );
              }
              final food = snapshot.data;
              if (food == null) {
                return ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(
                    Icons.cloud_off_outlined,
                    color: scheme.outline,
                  ),
                  title: const Text('Saved OpenNutri Core record'),
                  subtitle: const Text(
                    'Live source details are unavailable. Logged nutrients remain stored on this device.',
                  ),
                );
              }
              return Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  border: Border.all(color: scheme.outlineVariant),
                  borderRadius: BorderRadius.circular(18),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.verified, size: 20, color: scheme.primary),
                        const SizedBox(width: 8),
                        Text(
                          'Verified food record',
                          style: Theme.of(context).textTheme.labelLarge
                              ?.copyWith(
                                color: scheme.primary,
                                fontWeight: FontWeight.w800,
                              ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Text(food.publisher),
                    Text(
                      food.sourceFoodCode.isEmpty
                          ? food.datasetName
                          : '${food.datasetName} · code ${food.sourceFoodCode}',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: 5),
                    Text(
                      '${food.nutrients.length} nutrients · ${food.portions.length} portions in source record',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              );
            },
          ),
          const SizedBox(height: 22),
          Row(
            children: [
              Expanded(
                child: Text(
                  'Logged nutrients',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              Text(
                '${nutrients.length} values',
                style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: scheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          for (final nutrient in nutrients)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 7),
              child: Row(
                children: [
                  Expanded(child: Text(nutrient.name)),
                  Text(
                    '${formatAmount(nutrient.amount, maximumDecimals: 2)} ${nutrient.unit}',
                    style: Theme.of(context).textTheme.labelLarge,
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
