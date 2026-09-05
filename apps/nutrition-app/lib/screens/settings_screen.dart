import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/diary.dart';
import '../models/personalization.dart';
import '../services/core_api_client.dart';
import '../services/android_widget_bridge.dart';
import '../services/voice_api_client.dart';
import '../state/app_controller.dart';
import 'diets_screen.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({
    super.key,
    required this.controller,
    required this.apiClient,
    required this.voiceApiClient,
  });

  final AppController controller;
  final CoreApiClient apiClient;
  final VoiceApiClient voiceApiClient;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _calories;
  late final TextEditingController _protein;
  late final TextEditingController _carbs;
  late final TextEditingController _fat;
  late Future<Map<String, dynamic>> _health;
  late NutritionTargets _displayedTargets;

  @override
  void initState() {
    super.initState();
    final targets = widget.controller.targets;
    _displayedTargets = targets;
    _calories = TextEditingController(
      text: targets.calories.toStringAsFixed(0),
    );
    _protein = TextEditingController(text: targets.protein.toStringAsFixed(0));
    _carbs = TextEditingController(text: targets.carbs.toStringAsFixed(0));
    _fat = TextEditingController(text: targets.fat.toStringAsFixed(0));
    _health = widget.apiClient.health();
    widget.controller.addListener(_syncTargets);
  }

  void _syncTargets() {
    final targets = widget.controller.targets;
    if (identical(targets, _displayedTargets)) return;
    _displayedTargets = targets;
    _calories.text = targets.calories.toStringAsFixed(0);
    _protein.text = targets.protein.toStringAsFixed(0);
    _carbs.text = targets.carbs.toStringAsFixed(0);
    _fat.text = targets.fat.toStringAsFixed(0);
  }

  @override
  void dispose() {
    widget.controller.removeListener(_syncTargets);
    _calories.dispose();
    _protein.dispose();
    _carbs.dispose();
    _fat.dispose();
    super.dispose();
  }

  Future<void> _saveTargets() async {
    final values = [_calories, _protein, _carbs, _fat]
        .map(
          (controller) => double.tryParse(controller.text.replaceAll(',', '.')),
        )
        .toList();
    if (values.any((value) => value == null || !value.isFinite || value <= 0)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Targets must be greater than zero')),
      );
      return;
    }
    await widget.controller.updateTargets(
      NutritionTargets(
        calories: values[0]!,
        protein: values[1]!,
        carbs: values[2]!,
        fat: values[3]!,
      ),
    );
    if (!mounted) return;
    FocusScope.of(context).unfocus();
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('Targets saved')));
  }

  Future<void> _clearDiary() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Clear diary?'),
        content: const Text(
          'All locally stored diary entries will be removed.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Clear'),
          ),
        ],
      ),
    );
    if (confirmed == true) await widget.controller.clearEntries();
  }

  Future<void> _pinWidget() async {
    final requested = await AndroidWidgetBridge.requestPinWidget();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          requested
              ? 'Widget request opened'
              : 'Widget pinning is unavailable on this launcher',
        ),
      ),
    );
  }

  Future<void> _deleteVoiceFeedback() async {
    try {
      await widget.voiceApiClient.deleteFeedback();
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Voice feedback deleted')));
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not delete voice feedback')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
            children: [
              _heading(context, 'Daily targets'),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: _TargetField(
                      controller: _calories,
                      label: 'Energy',
                      unit: 'kcal',
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _TargetField(
                      controller: _protein,
                      label: 'Protein',
                      unit: 'g',
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: _TargetField(
                      controller: _carbs,
                      label: 'Carbs',
                      unit: 'g',
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _TargetField(
                      controller: _fat,
                      label: 'Fat',
                      unit: 'g',
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              FilledButton.icon(
                onPressed: _saveTargets,
                icon: const Icon(Icons.save_outlined),
                label: const Text('Save targets'),
              ),
              const SizedBox(height: 30),
              _heading(context, 'Personalization'),
              const SizedBox(height: 8),
              DropdownButtonFormField<NutritionGoal>(
                initialValue: widget.controller.profile.goal,
                decoration: const InputDecoration(
                  labelText: 'Primary goal',
                  prefixIcon: Icon(Icons.flag_outlined),
                ),
                items: [
                  for (final goal in NutritionGoal.values)
                    DropdownMenuItem(value: goal, child: Text(goal.label)),
                ],
                onChanged: (goal) {
                  if (goal != null) widget.controller.updateGoal(goal);
                },
              ),
              const SizedBox(height: 10),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.restaurant_menu),
                title: Text(widget.controller.profile.diet.name),
                subtitle: const Text('Active diet framework'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (context) =>
                        DietsScreen(controller: widget.controller),
                  ),
                ),
              ),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.memory_outlined),
                title: const Text('Coach memory'),
                subtitle: Text(
                  widget.controller.profile.memories.isEmpty
                      ? 'No saved personal facts'
                      : '${widget.controller.profile.memories.length} on-device facts · manage in Coach',
                ),
                trailing: widget.controller.profile.coachEnabled
                    ? const Chip(label: Text('Active'))
                    : null,
              ),
              if (widget.controller.profile.coachEnabled)
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  value: true,
                  title: const Text('AI coaching'),
                  subtitle: const Text(
                    'Turn off future AI advice. Saved facts stay on this phone.',
                  ),
                  onChanged: (_) => widget.controller.updateProfile(
                    widget.controller.profile.copyWith(coachEnabled: false),
                  ),
                ),
              const SizedBox(height: 32),
              _heading(context, 'Data'),
              const SizedBox(height: 8),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.dataset_outlined),
                title: const Text('USDA FNDDS 2021-2023'),
                subtitle: const Text('OpenNutri Core v0.3.0 · API v0.4.0'),
              ),
              FutureBuilder<Map<String, dynamic>>(
                future: _health,
                builder: (context, snapshot) {
                  final online =
                      snapshot.hasData && snapshot.data?['status'] == 'ok';
                  return ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(
                      online
                          ? Icons.cloud_done_outlined
                          : Icons.cloud_off_outlined,
                      color: online
                          ? Theme.of(context).colorScheme.primary
                          : Theme.of(context).colorScheme.error,
                    ),
                    title: const Text('Core API'),
                    subtitle: Text(online ? 'Online' : 'Unavailable'),
                    trailing: IconButton(
                      tooltip: 'Check connection',
                      onPressed: () =>
                          setState(() => _health = widget.apiClient.health()),
                      icon: const Icon(Icons.refresh),
                    ),
                  );
                },
              ),
              const SizedBox(height: 24),
              _heading(context, 'Voice logging'),
              const SizedBox(height: 8),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.bolt_rounded),
                title: const Text('Instant voice logging'),
                subtitle: const Text(
                  'Usable matches are logged immediately. Uncertain amounts '
                  'or matches are marked as estimates so you can edit them later.',
                ),
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                value: widget.controller.voiceFeedbackConsent,
                onChanged: widget.controller.updateVoiceFeedbackConsent,
                title: const Text('Share correction feedback'),
                subtitle: const Text(
                  'Optional. Audio, transcripts, quantities, meals, dates, and '
                  'nutrients are never included.',
                ),
              ),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.widgets_outlined),
                title: const Text('Add microphone widget'),
                subtitle: const Text('Android home screen · 1×1'),
                trailing: const Icon(Icons.add_to_home_screen),
                onTap: _pinWidget,
              ),
              TextButton.icon(
                onPressed: widget.voiceApiClient.isConfigured
                    ? _deleteVoiceFeedback
                    : null,
                icon: const Icon(Icons.delete_sweep_outlined),
                label: const Text('Delete my voice feedback'),
              ),
              const SizedBox(height: 24),
              _heading(context, 'On-device data'),
              const SizedBox(height: 8),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.phone_android_outlined),
                title: const Text('Diary storage'),
                subtitle: Text('${widget.controller.entries.length} entries'),
              ),
              OutlinedButton.icon(
                onPressed: widget.controller.entries.isEmpty
                    ? null
                    : _clearDiary,
                icon: const Icon(Icons.delete_outline),
                label: const Text('Clear diary'),
              ),
              const SizedBox(height: 28),
              Text(
                'OpenNutri 1.1.0 beta',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _heading(BuildContext context, String text) {
    return Text(
      text,
      style: Theme.of(context).textTheme.titleMedium?.copyWith(
        fontWeight: FontWeight.w800,
        letterSpacing: 0,
      ),
    );
  }
}

class _TargetField extends StatelessWidget {
  const _TargetField({
    required this.controller,
    required this.label,
    required this.unit,
  });

  final TextEditingController controller;
  final String label;
  final String unit;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))],
      decoration: InputDecoration(labelText: label, suffixText: unit),
    );
  }
}
