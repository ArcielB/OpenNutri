import 'package:flutter/material.dart';

import '../models/diary.dart';
import '../models/personalization.dart';
import '../services/coach_service.dart';
import '../services/core_api_client.dart';
import '../services/voice_api_client.dart';
import '../state/app_controller.dart';
import 'diets_screen.dart';
import 'food_search_screen.dart';

class OracleScreen extends StatefulWidget {
  const OracleScreen({
    super.key,
    required this.controller,
    required this.coachService,
    required this.apiClient,
    required this.voiceApiClient,
    required this.onOpenCoach,
    this.isActive = true,
  });

  final AppController controller;
  final CoachService coachService;
  final CoreApiClient apiClient;
  final VoiceApiClient voiceApiClient;
  final VoidCallback onOpenCoach;
  final bool isActive;

  @override
  State<OracleScreen> createState() => _OracleScreenState();
}

class _OracleScreenState extends State<OracleScreen> {
  CoachReply? _reply;
  bool _loading = false;
  String? _error;
  int? _contextRevision;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && widget.isActive) _generate();
    });
  }

  @override
  void didUpdateWidget(covariant OracleScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    final changed = _contextRevision != widget.controller.coachContextRevision;
    if (changed) _reply = null;
    if (widget.isActive &&
        (changed || (!oldWidget.isActive && _reply == null)) &&
        !_loading) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && widget.isActive) _generate();
      });
    }
  }

  Future<void> _generate() async {
    if (_loading || !widget.controller.profile.coachEnabled) return;
    final revision = widget.controller.coachContextRevision;
    _contextRevision = revision;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final reply = await widget.coachService.respond(
        controller: widget.controller,
        mode: CoachMode.oracle,
      );
      if (!mounted ||
          !widget.controller.profile.coachEnabled ||
          revision != widget.controller.coachContextRevision) {
        return;
      }
      setState(() => _reply = reply);
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error =
            'The Oracle could not reach the AI service. Your diary and profile were not changed.';
      });
    } finally {
      if (mounted) setState(() => _loading = false);
      if (mounted &&
          widget.isActive &&
          revision != widget.controller.coachContextRevision) {
        await _generate();
      }
    }
  }

  MealType get _suggestedMeal {
    final hour = DateTime.now().hour;
    if (hour < 11) return MealType.breakfast;
    if (hour < 16) return MealType.lunch;
    if (hour < 21) return MealType.dinner;
    return MealType.snacks;
  }

  Future<void> _findAndAdd(CoachAction action) async {
    final query = action.searchQuery;
    if (query == null || query.isEmpty) return;
    final entry = await Navigator.of(context).push<DiaryEntry>(
      MaterialPageRoute(
        builder: (context) => FoodSearchScreen(
          apiClient: widget.apiClient,
          resolver: widget.voiceApiClient,
          meal: _suggestedMeal,
          date: widget.controller.selectedDate,
          initialQuery: query,
        ),
      ),
    );
    if (entry == null) return;
    await widget.controller.addEntry(entry);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('${entry.foodName} logged'),
        action: SnackBarAction(
          label: 'Undo',
          onPressed: () => widget.controller.removeEntry(entry.id),
        ),
      ),
    );
    await _generate();
  }

  @override
  Widget build(BuildContext context) {
    final profile = widget.controller.profile;
    final totals = widget.controller.dailyTotals;
    final targets = widget.controller.targets;
    return Scaffold(
      appBar: AppBar(
        title: const Text('The Oracle'),
        actions: [
          IconButton(
            tooltip: 'Choose a diet',
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (context) =>
                    DietsScreen(controller: widget.controller),
              ),
            ),
            icon: const Icon(Icons.restaurant_menu),
          ),
          IconButton(
            tooltip: 'Recalculate',
            onPressed: profile.coachEnabled && !_loading ? _generate : null,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _generate,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.inverseSurface,
                borderRadius: BorderRadius.circular(26),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        Icons.visibility_outlined,
                        color: Theme.of(context).colorScheme.onInverseSurface,
                      ),
                      const SizedBox(width: 9),
                      Text(
                        'BEST NEXT FOODS',
                        style: Theme.of(context).textTheme.labelMedium
                            ?.copyWith(
                              color: Theme.of(
                                context,
                              ).colorScheme.onInverseSurface,
                              fontWeight: FontWeight.w900,
                              letterSpacing: 1.1,
                            ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  Text(
                    'Make your next meal count.',
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      color: Theme.of(context).colorScheme.onInverseSurface,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'Ideas based on your logged day, ${profile.goal.label.toLowerCase()}, your ${profile.diet.name} plan, and your saved preferences.',
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.onInverseSurface,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),
            _GapStrip(
              calories: totals.calories / targets.calories,
              protein: totals.protein / targets.protein,
              carbs: totals.carbs / targets.carbs,
              fat: totals.fat / targets.fat,
            ),
            const SizedBox(height: 18),
            if (!profile.coachEnabled)
              _EnableOracle(onOpenCoach: widget.onOpenCoach)
            else if (_loading && _reply == null)
              const _OracleLoading()
            else if (_error != null && _reply == null)
              _OracleError(message: _error!, onRetry: _generate)
            else ...[
              if (_reply != null) ...[
                Text(
                  _reply!.headline,
                  style: Theme.of(
                    context,
                  ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
                ),
                const SizedBox(height: 4),
                Text(_reply!.message),
                if (_reply!.safetyNote?.isNotEmpty ?? false) ...[
                  const SizedBox(height: 8),
                  Text(_reply!.safetyNote!),
                ],
                const SizedBox(height: 12),
                for (var index = 0; index < _reply!.actions.length; index++)
                  _OracleFoodCard(
                    rank: index + 1,
                    action: _reply!.actions[index],
                    onTap: () => _findAndAdd(_reply!.actions[index]),
                  ),
                if (_loading) const LinearProgressIndicator(),
                if (_error != null) ...[
                  const SizedBox(height: 8),
                  Text(_error!, style: Theme.of(context).textTheme.bodySmall),
                ],
                const SizedBox(height: 12),
                Text(
                  'AI chooses the search strategy; OpenNutri Core verifies the food and supplies every nutrient value before logging.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ],
          ],
        ),
      ),
    );
  }
}

class _GapStrip extends StatelessWidget {
  const _GapStrip({
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
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(15),
      child: Row(
        children: [
          _item(context, 'Energy', calories),
          _item(context, 'Protein', protein),
          _item(context, 'Carbs', carbs),
          _item(context, 'Fat', fat),
        ],
      ),
    ),
  );

  Widget _item(BuildContext context, String name, double value) => Expanded(
    child: Column(
      children: [
        Text(
          '${(value * 100).clamp(0, 999).round()}%',
          style: Theme.of(
            context,
          ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w900),
        ),
        const SizedBox(height: 3),
        Text(name, style: Theme.of(context).textTheme.labelSmall),
      ],
    ),
  );
}

class _OracleFoodCard extends StatelessWidget {
  const _OracleFoodCard({
    required this.rank,
    required this.action,
    required this.onTap,
  });
  final int rank;
  final CoachAction action;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Card(
    margin: const EdgeInsets.symmetric(vertical: 5),
    clipBehavior: Clip.antiAlias,
    child: InkWell(
      onTap: action.searchQuery == null ? null : onTap,
      child: Padding(
        padding: const EdgeInsets.all(15),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            CircleAvatar(
              backgroundColor: Theme.of(context).colorScheme.primaryContainer,
              child: Text(
                '$rank',
                style: const TextStyle(fontWeight: FontWeight.w900),
              ),
            ),
            const SizedBox(width: 13),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    action.title,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(action.detail),
                  if (action.searchQuery != null) ...[
                    const SizedBox(height: 7),
                    Text(
                      'Find verified ${action.searchQuery}',
                      style: Theme.of(context).textTheme.labelMedium?.copyWith(
                        color: Theme.of(context).colorScheme.primary,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            if (action.searchQuery != null) const Icon(Icons.arrow_forward),
          ],
        ),
      ),
    ),
  );
}

class _EnableOracle extends StatelessWidget {
  const _EnableOracle({required this.onOpenCoach});
  final VoidCallback onOpenCoach;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          const Icon(Icons.lock_open, size: 42),
          const SizedBox(height: 10),
          const Text('Activate the coach to personalize the Oracle'),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: onOpenCoach,
            child: const Text('Set up my coach'),
          ),
        ],
      ),
    ),
  );
}

class _OracleLoading extends StatelessWidget {
  const _OracleLoading();
  @override
  Widget build(BuildContext context) => const Padding(
    padding: EdgeInsets.symmetric(vertical: 50),
    child: Column(
      children: [
        CircularProgressIndicator(),
        SizedBox(height: 14),
        Text('Ranking the best next foods for this exact day…'),
      ],
    ),
  );
}

class _OracleError extends StatelessWidget {
  const _OracleError({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          const Icon(Icons.cloud_off_outlined, size: 38),
          const SizedBox(height: 10),
          Text(message, textAlign: TextAlign.center),
          const SizedBox(height: 12),
          FilledButton.tonal(
            onPressed: onRetry,
            child: const Text('Try again'),
          ),
        ],
      ),
    ),
  );
}
