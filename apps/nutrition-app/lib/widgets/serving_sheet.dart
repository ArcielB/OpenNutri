import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/diary.dart';
import '../models/food.dart';
import '../utils/format.dart';

enum ServingMode { grams, portion }

class ServingSheet extends StatefulWidget {
  const ServingSheet({
    super.key,
    required this.food,
    required this.meal,
    required this.date,
  });

  final FoodDetail food;
  final MealType meal;
  final DateTime date;

  @override
  State<ServingSheet> createState() => _ServingSheetState();
}

class _ServingSheetState extends State<ServingSheet> {
  final _gramsController = TextEditingController(text: '100');
  ServingMode _mode = ServingMode.grams;
  FoodPortion? _portion;
  double _servings = 1;

  @override
  void initState() {
    super.initState();
    _portion = widget.food.portions.firstOrNull;
    _gramsController.addListener(_refresh);
  }

  @override
  void dispose() {
    _gramsController
      ..removeListener(_refresh)
      ..dispose();
    super.dispose();
  }

  void _refresh() => setState(() {});

  double get _grams {
    if (_mode == ServingMode.portion && _portion != null) {
      return _portion!.gramWeight * _servings;
    }
    return double.tryParse(_gramsController.text) ?? 0;
  }

  String get _servingLabel {
    if (_mode == ServingMode.portion && _portion != null) {
      return '${formatAmount(_servings)} x ${_portion!.description}';
    }
    return '${formatAmount(_grams)} g';
  }

  double _scaled(String name, String unit) {
    return widget.food.nutrientAmount(name, unit) * _grams / 100;
  }

  void _add() {
    if (_grams <= 0 || _grams > 10000) return;
    Navigator.of(context).pop(
      DiaryEntry.fromFood(
        food: widget.food,
        date: widget.date,
        meal: widget.meal,
        grams: _grams,
        servingLabel: _servingLabel,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final viewInsets = MediaQuery.viewInsetsOf(context);
    return Padding(
      padding: EdgeInsets.only(bottom: viewInsets.bottom),
      child: FractionallySizedBox(
        heightFactor: 0.9,
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 12, 14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.food.name,
                          style: Theme.of(context).textTheme.titleLarge
                              ?.copyWith(
                                fontWeight: FontWeight.w700,
                                letterSpacing: 0,
                              ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '${widget.food.categoryName} - ${widget.food.datasetName}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    tooltip: 'Close',
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.close),
                  ),
                ],
              ),
            ),
            const Divider(),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 18, 20, 24),
                children: [
                  SegmentedButton<ServingMode>(
                    segments: [
                      const ButtonSegment(
                        value: ServingMode.grams,
                        icon: Icon(Icons.scale_outlined),
                        label: Text('Grams'),
                      ),
                      ButtonSegment(
                        value: ServingMode.portion,
                        enabled: widget.food.portions.isNotEmpty,
                        icon: const Icon(Icons.restaurant_outlined),
                        label: const Text('Portion'),
                      ),
                    ],
                    selected: {_mode},
                    showSelectedIcon: false,
                    onSelectionChanged: (values) =>
                        setState(() => _mode = values.first),
                  ),
                  const SizedBox(height: 20),
                  if (_mode == ServingMode.grams)
                    TextField(
                      controller: _gramsController,
                      keyboardType: const TextInputType.numberWithOptions(
                        decimal: true,
                      ),
                      inputFormatters: [
                        FilteringTextInputFormatter.allow(RegExp(r'[0-9.]')),
                      ],
                      decoration: const InputDecoration(
                        labelText: 'Weight',
                        suffixText: 'g',
                      ),
                    )
                  else ...[
                    DropdownButtonFormField<FoodPortion>(
                      initialValue: _portion,
                      isExpanded: true,
                      decoration: const InputDecoration(labelText: 'Portion'),
                      items: widget.food.portions
                          .map(
                            (portion) => DropdownMenuItem(
                              value: portion,
                              child: Text(
                                '${portion.description} (${formatAmount(portion.gramWeight)} g)',
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          )
                          .toList(),
                      onChanged: (value) => setState(() => _portion = value),
                    ),
                    const SizedBox(height: 14),
                    Row(
                      children: [
                        Text(
                          'Servings',
                          style: Theme.of(context).textTheme.titleSmall,
                        ),
                        const Spacer(),
                        IconButton.outlined(
                          tooltip: 'Decrease servings',
                          onPressed: _servings <= 0.5
                              ? null
                              : () => setState(() => _servings -= 0.5),
                          icon: const Icon(Icons.remove),
                        ),
                        SizedBox(
                          width: 58,
                          child: Text(
                            formatAmount(_servings),
                            textAlign: TextAlign.center,
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                        ),
                        IconButton.outlined(
                          tooltip: 'Increase servings',
                          onPressed: () => setState(() => _servings += 0.5),
                          icon: const Icon(Icons.add),
                        ),
                      ],
                    ),
                  ],
                  const SizedBox(height: 24),
                  Text(
                    '${formatAmount(_grams)} g',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0,
                    ),
                  ),
                  const SizedBox(height: 14),
                  _MacroPreview(
                    calories: widget.food.caloriesPer100g * _grams / 100,
                    protein: _scaled('Protein', 'g'),
                    carbs: _scaled('Carbohydrate, by difference', 'g'),
                    fat: _scaled('Total lipid (fat)', 'g'),
                  ),
                  const SizedBox(height: 24),
                  Row(
                    children: [
                      Icon(
                        widget.food.qualityStatus == 'complete'
                            ? Icons.verified_outlined
                            : Icons.info_outline,
                        size: 18,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          '${widget.food.publisher} - food code ${widget.food.sourceFoodCode}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(20, 10, 20, 14),
                child: FilledButton.icon(
                  onPressed: _grams > 0 && _grams <= 10000 ? _add : null,
                  style: FilledButton.styleFrom(
                    minimumSize: const Size.fromHeight(52),
                  ),
                  icon: const Icon(Icons.add),
                  label: Text('Add to ${widget.meal.label}'),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MacroPreview extends StatelessWidget {
  const _MacroPreview({
    required this.calories,
    required this.protein,
    required this.carbs,
    required this.fat,
  });

  final double calories;
  final double protein;
  final double carbs;
  final double fat;

  @override
  Widget build(BuildContext context) {
    final values = [
      ('Energy', calories, 'kcal'),
      ('Protein', protein, 'g'),
      ('Carbs', carbs, 'g'),
      ('Fat', fat, 'g'),
    ];
    return Row(
      children: [
        for (var index = 0; index < values.length; index++) ...[
          if (index > 0) const SizedBox(width: 8),
          Expanded(
            child: Column(
              children: [
                Text(
                  values[index].$1,
                  style: Theme.of(context).textTheme.labelSmall,
                ),
                const SizedBox(height: 4),
                FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Text(
                    '${formatAmount(values[index].$2)} ${values[index].$3}',
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}
