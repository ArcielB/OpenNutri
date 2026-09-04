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
      });
      return;
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
                ListTile(
                  leading: const Icon(Icons.auto_awesome),
                  title: Text(_semanticFoodName ?? 'Semantic match'),
                  subtitle: const Text(
                    'Submitted search match — review before logging',
                  ),
                  trailing: _loadingFoodId == _semanticFoodId
                      ? const SizedBox.square(
                          dimension: 22,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.chevron_right),
                  onTap: _loadingFoodId == _semanticFoodId
                      ? null
                      : () => _selectFoodId(_semanticFoodId!),
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
      return Center(
        child: Icon(
          Icons.manage_search,
          size: 48,
          color: Theme.of(context).colorScheme.outline,
        ),
      );
    }
    if (!_searching && _results.isEmpty) {
      return const Center(child: Text('No foods found'));
    }
    final headerCount = _partialMatch ? 1 : 0;
    return ListView.separated(
      padding: const EdgeInsets.only(bottom: 24),
      itemCount: _results.length + headerCount,
      separatorBuilder: (_, _) => const Divider(indent: 16, endIndent: 16),
      itemBuilder: (context, index) {
        if (_partialMatch && index == 0) {
          return Padding(
            padding: const EdgeInsets.fromLTRB(20, 10, 20, 6),
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
        return ListTile(
          contentPadding: const EdgeInsets.symmetric(
            horizontal: 20,
            vertical: 4,
          ),
          onTap: loading ? null : () => _selectFood(item),
          title: Text(item.name, maxLines: 2, overflow: TextOverflow.ellipsis),
          subtitle: Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              '${item.categoryName} - ${item.nutrientCount} nutrients',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          leading: _QualityMark(status: item.qualityStatus),
          trailing: loading
              ? const SizedBox.square(
                  dimension: 24,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.chevron_right),
        );
      },
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
