import 'package:flutter/material.dart';

import '../models/personalization.dart';
import '../state/app_controller.dart';

class DietsScreen extends StatelessWidget {
  const DietsScreen({super.key, required this.controller});

  final AppController controller;

  Future<void> _openDiet(BuildContext context, DietPreset diet) async {
    final notes = TextEditingController(
      text: controller.profile.dietId == diet.id
          ? controller.profile.dietNotes
          : '',
    );
    final apply = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      builder: (context) => Padding(
        padding: EdgeInsets.fromLTRB(
          22,
          4,
          22,
          MediaQuery.viewInsetsOf(context).bottom + 24,
        ),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                children: [
                  _DietIcon(diet: diet, size: 52),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          diet.name,
                          style: Theme.of(context).textTheme.headlineSmall
                              ?.copyWith(fontWeight: FontWeight.w900),
                        ),
                        Text(diet.tagline),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 18),
              Text(diet.description),
              const SizedBox(height: 18),
              _MacroSplit(diet: diet),
              const SizedBox(height: 20),
              Text(
                'The idea',
                style: Theme.of(
                  context,
                ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 8),
              for (final principle in diet.principles)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 5),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.check_circle_outline, size: 20),
                      const SizedBox(width: 9),
                      Expanded(child: Text(principle)),
                    ],
                  ),
                ),
              const SizedBox(height: 16),
              TextField(
                controller: notes,
                maxLines: 3,
                decoration: const InputDecoration(
                  labelText: 'Make it yours',
                  hintText:
                      'Example: no fish, cheap student meals, two meals per day…',
                  alignLabelWithHint: true,
                ),
              ),
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: () => Navigator.pop(context, true),
                  icon: const Icon(Icons.auto_awesome),
                  label: Text(
                    controller.profile.dietId == diet.id
                        ? 'Update my plan'
                        : 'Use and personalize this plan',
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Macro targets adapt to your current energy target. You can fine-tune every number in Settings.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
      ),
    );
    if (apply == true) {
      await controller.applyDiet(diet, notes: notes.text.trim());
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('${diet.name} is now your active plan')),
        );
      }
    }
    notes.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Choose a food philosophy')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
        children: [
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.primaryContainer,
              borderRadius: BorderRadius.circular(22),
            ),
            child: const Text(
              'Start with a proven pattern, then change anything. OpenNutri adapts the targets and your AI suggestions—the preset never becomes a rigid rulebook.',
            ),
          ),
          const SizedBox(height: 12),
          for (final diet in dietPresets)
            Card(
              clipBehavior: Clip.antiAlias,
              child: InkWell(
                onTap: () => _openDiet(context, diet),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      _DietIcon(diet: diet),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Flexible(
                                  child: Text(
                                    diet.name,
                                    style: Theme.of(context)
                                        .textTheme
                                        .titleMedium
                                        ?.copyWith(fontWeight: FontWeight.w800),
                                  ),
                                ),
                                if (controller.profile.dietId == diet.id) ...[
                                  const SizedBox(width: 8),
                                  const Chip(
                                    visualDensity: VisualDensity.compact,
                                    label: Text('Active'),
                                  ),
                                ],
                              ],
                            ),
                            Text(
                              diet.tagline,
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                            const SizedBox(height: 7),
                            _MacroSplit(diet: diet, compact: true),
                          ],
                        ),
                      ),
                      const Icon(Icons.chevron_right),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _DietIcon extends StatelessWidget {
  const _DietIcon({required this.diet, this.size = 48});
  final DietPreset diet;
  final double size;

  @override
  Widget build(BuildContext context) => Container(
    width: size,
    height: size,
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.secondaryContainer,
      borderRadius: BorderRadius.circular(size * 0.3),
    ),
    child: Icon(switch (diet.iconName) {
      'sun' => Icons.wb_sunny_outlined,
      'fitness' => Icons.fitness_center,
      'plant' => Icons.eco_outlined,
      'bolt' => Icons.bolt,
      'public' => Icons.public,
      _ => Icons.balance,
    }, color: Theme.of(context).colorScheme.secondary),
  );
}

class _MacroSplit extends StatelessWidget {
  const _MacroSplit({required this.diet, this.compact = false});
  final DietPreset diet;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    String percent(double value) => '${(value * 100).round()}%';
    return Row(
      children: [
        _split(context, 'C', percent(diet.carbsShare)),
        _split(context, 'P', percent(diet.proteinShare)),
        _split(context, 'F', percent(diet.fatShare)),
      ],
    );
  }

  Widget _split(BuildContext context, String label, String value) => Expanded(
    child: Text(
      '$label $value',
      style: compact
          ? Theme.of(context).textTheme.labelSmall
          : Theme.of(context).textTheme.labelLarge,
    ),
  );
}
