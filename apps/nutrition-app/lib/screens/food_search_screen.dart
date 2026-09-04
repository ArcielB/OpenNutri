import 'dart:async';

import 'package:flutter/material.dart';

import '../models/diary.dart';
import '../models/food.dart';
import '../services/core_api_client.dart';
import '../services/voice_api_client.dart';
import '../widgets/serving_sheet.dart';

class FoodSearchScreen extends StatefulWidget {
  const FoodSearchScreen({
    super.key,
    required this.apiClient,
    required this.meal,
    required this.date,
    this.resolver,
    this.initialQuery,
  });

  final CoreApiClient apiClient;
  final MealType meal;
  final DateTime date;
  final VoiceApiClient? resolver;
  final String? initialQuery;

  @override
  State<FoodSearchScreen> createState() => _FoodSearchScreenState();
}

class _FoodSearchScreenState extends State<FoodSearchScreen> {
  static const _suggestions = [
    'raw apple',
    'chicken breast',
    'cooked rice',
    'whole milk',
  ];

  late final TextEditingController _searchController;
  final _focusNode = FocusNode();
  Timer? _debounce;
  List<FoodSearchItem> _results = const [];
  List<String> _matchedTerms = const [];
  bool _partialMatch = false;
  bool _searching = false;
  String? _loadingFoodId;
  String? _error;
  int _requestId = 0;
  String? _semanticFoodId;
  String? _semanticFoodName;
  bool _resolvingSemantic = false;

  @override
  void initState() {
    super.initState();
    _searchController = TextEditingController(text: widget.initialQuery ?? '');
    _searchController.addListener(_scheduleSearch);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _focusNode.requestFocus();
      if (_searchController.text.trim().isNotEmpty) {
        _search(_searchController.text.trim());
      }
    });
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController
      ..removeListener(_scheduleSearch)
      ..dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _scheduleSearch() {
    _debounce?.cancel();
    final query = _searchController.text.trim();
    if (query.isEmpty) {
      setState(() {
        _results = const [];
        _matchedTerms = const [];
        _partialMatch = false;
        _searching = false;
        _error = null;
        _semanticFoodId = null;
        _semanticFoodName = null;
      });
      return;
    }
    if (_semanticFoodId != null || _semanticFoodName != null) {
      setState(() {
        _semanticFoodId = null;
        _semanticFoodName = null;
      });
    }
    _debounce = Timer(const Duration(milliseconds: 350), () => _search(query));
  }

  Future<void> _search(String query) async {
    final requestId = ++_requestId;
    setState(() {
      _searching = true;
      _error = null;
    });
    try {
      final result = await widget.apiClient.searchFoods(query);
      if (!mounted || requestId != _requestId) return;
      setState(() {
        _results = result.items;
        _matchedTerms = result.matchedTerms;
        _partialMatch = result.isPartial;
        _searching = false;
      });
    } catch (_) {
      if (!mounted || requestId != _requestId) return;
      setState(() {
        _searching = false;
        _error = 'Could not reach OpenNutri';
      });
    }
  }

  Future<void> _submitSearch(String query) async {
    _debounce?.cancel();
    await _search(query);
    final resolver = widget.resolver;
    if (resolver == null || !resolver.isConfigured || query.trim().isEmpty) {
      return;
    }
    setState(() {
      _resolvingSemantic = true;
      _semanticFoodId = null;
      _semanticFoodName = null;
    });
    try {
      final response = await resolver.resolveText(
        query.trim(),
        localTimestamp: DateTime.now(),
        timezone: const String.fromEnvironment(
          'OPENNUTRI_TIMEZONE',
          defaultValue: 'Europe/Istanbul',
        ),
      );
      final candidate =
          response.items.firstOrNull?.selectedCandidate ??
          response.manualSearchCandidates.firstOrNull;
      if (!mounted) return;
      setState(() {
        _semanticFoodId = candidate?.foodId;
        _semanticFoodName = candidate?.name;
        _resolvingSemantic = false;
      });
    } catch (_) {
      if (mounted) setState(() => _resolvingSemantic = false);
    }
  }

  void _useSuggestion(String query) {
    _searchController.value = TextEditingValue(
      text: query,
      selection: TextSelection.collapsed(offset: query.length),
    );
    _submitSearch(query);
  }

  Future<void> _selectFood(FoodSearchItem item) async {
    await _selectFoodId(item.foodId);
  }

  Future<void> _selectFoodId(String foodId) async {
    setState(() => _loadingFoodId = foodId);
    try {
      final detail = await widget.apiClient.foodDetail(foodId);
      if (!mounted) return;
      final entry = await showModalBottomSheet<DiaryEntry>(
        context: context,
        isScrollControlled: true,
        useSafeArea: true,
        showDragHandle: true,
        builder: (context) =>
            ServingSheet(food: detail, meal: widget.meal, date: widget.date),
      );
      if (entry != null && mounted) Navigator.of(context).pop(entry);
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Could not load this food')));
    } finally {
      if (mounted) setState(() => _loadingFoodId = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Add to ${widget.meal.label}')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
                child: TextField(
                  controller: _searchController,
                  focusNode: _focusNode,
                  textInputAction: TextInputAction.search,
                  onSubmitted: _submitSearch,
                  decoration: InputDecoration(
                    hintText: 'Search foods',
                    prefixIcon: const Icon(Icons.search),
                    suffixIcon: _searchController.text.isEmpty
                        ? null
                        : IconButton(
                            tooltip: 'Clear search',
                            onPressed: _searchController.clear,
                            icon: const Icon(Icons.clear),
                          ),
                  ),
                ),
              ),
              if (_searching) const LinearProgressIndicator(minHeight: 2),
              if (_resolvingSemantic)
                const LinearProgressIndicator(minHeight: 2),
              if (_semanticFoodId != null)
                _SemanticMatchCard(
                  foodName: _semanticFoodName ?? 'Semantic match',
                  loading: _loadingFoodId == _semanticFoodId,
                  onTap: () => _selectFoodId(_semanticFoodId!),
                ),
              Expanded(child: _buildResults(context)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildResults(BuildContext context) {
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.cloud_off_outlined,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(height: 10),
            Text(_error!),
            const SizedBox(height: 8),
            TextButton.icon(
              onPressed: () => _search(_searchController.text.trim()),
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      );
    }
    if (_searchController.text.trim().isEmpty) {
      return ListView(
        padding: const EdgeInsets.fromLTRB(24, 40, 24, 24),
        children: [
          Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.primaryContainer,
              shape: BoxShape.circle,
            ),
            child: Icon(
              Icons.manage_search,
              size: 36,
              color: Theme.of(context).colorScheme.primary,
            ),
          ),
          const SizedBox(height: 18),
          Text(
            'Search verified foods',
            textAlign: TextAlign.center,
            style: Theme.of(
              context,
            ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 7),
          Text(
            'Search by food and preparation. Specific phrases give better matches.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 24),
          Text(
            'Try an example',
            style: Theme.of(
              context,
            ).textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final suggestion in _suggestions)
                ActionChip(
                  avatar: const Icon(Icons.north_west, size: 16),
                  label: Text(suggestion),
                  onPressed: () => _useSuggestion(suggestion),
                ),
            ],
          ),
        ],
      );
    }
    if (!_searching && _results.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.search_off_rounded,
                size: 42,
                color: Theme.of(context).colorScheme.outline,
              ),
              const SizedBox(height: 12),
              Text(
                'No foods found',
                style: Theme.of(
                  context,
                ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 5),
              const Text(
                'Try a simpler food name or remove brand words.',
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      );
    }
    final headerCount = _partialMatch ? 1 : 0;
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 24),
      itemCount: _results.length + headerCount,
      separatorBuilder: (_, _) => const SizedBox(height: 7),
      itemBuilder: (context, index) {
        if (_partialMatch && index == 0) {
          return Container(
            margin: const EdgeInsets.only(bottom: 3),
            padding: const EdgeInsets.fromLTRB(14, 11, 14, 11),
            decoration: BoxDecoration(
              color: Theme.of(
                context,
              ).colorScheme.tertiaryContainer.withValues(alpha: 0.5),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Row(
              children: [
                Icon(
                  Icons.info_outline,
                  size: 18,
                  color: Theme.of(context).colorScheme.tertiary,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'No exact match. Showing ${_matchedTerms.join(' ')}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
              ],
            ),
          );
        }
        final item = _results[index - headerCount];
        final loading = _loadingFoodId == item.foodId;
        return Card(
          margin: EdgeInsets.zero,
          child: ListTile(
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 14,
              vertical: 7,
            ),
            onTap: loading ? null : () => _selectFood(item),
            title: Text(
              item.name,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            subtitle: Padding(
              padding: const EdgeInsets.only(top: 5),
              child: Text(
                '${item.categoryName} · ${item.nutrientCount} nutrients\n${item.datasetName}',
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            isThreeLine: true,
            leading: _QualityMark(status: item.qualityStatus),
            trailing: loading
                ? const SizedBox.square(
                    dimension: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.chevron_right),
          ),
        );
      },
    );
  }
}

class _SemanticMatchCard extends StatelessWidget {
  const _SemanticMatchCard({
    required this.foodName,
    required this.loading,
    required this.onTap,
  });

  final String foodName;
  final bool loading;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 10),
      decoration: BoxDecoration(
        color: scheme.primaryContainer.withValues(alpha: 0.55),
        borderRadius: BorderRadius.circular(16),
      ),
      child: ListTile(
        leading: Icon(Icons.auto_awesome, color: scheme.primary),
        title: Text(
          foodName,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontWeight: FontWeight.w800),
        ),
        subtitle: const Text(
          'Best meaning-based match · review before logging',
        ),
        trailing: loading
            ? const SizedBox.square(
                dimension: 22,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : const Icon(Icons.chevron_right),
        onTap: loading ? null : onTap,
      ),
    );
  }
}

class _QualityMark extends StatelessWidget {
  const _QualityMark({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final color = switch (status) {
      'complete' => scheme.primary,
      'ambiguous' => scheme.tertiary,
      _ => scheme.outline,
    };
    return Semantics(
      label: 'Data quality: $status',
      child: Container(
        width: 34,
        height: 34,
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Icon(Icons.restaurant_outlined, size: 19, color: color),
      ),
    );
  }
}
