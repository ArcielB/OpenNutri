import 'dart:async';

import 'package:flutter/material.dart';

import '../models/diary.dart';
import '../models/food.dart';
import '../models/voice_resolution.dart';
import '../services/core_api_client.dart';
import '../services/voice_api_client.dart';
import '../services/voice_recorder.dart';
import '../state/app_controller.dart';
import 'food_search_screen.dart';

enum VoiceLogState {
  ready,
  recording,
  processing,
  review,
  manualSearch,
  permissionDenied,
  error,
}

class VoiceLogScreen extends StatefulWidget {
  const VoiceLogScreen({
    super.key,
    required this.controller,
    required this.coreApiClient,
    required this.voiceApiClient,
    this.autoStart = false,
    this.recorder,
  });

  final AppController controller;
  final CoreApiClient coreApiClient;
  final VoiceApiClient voiceApiClient;
  final bool autoStart;
  final VoiceRecorderSession? recorder;

  @override
  State<VoiceLogScreen> createState() => _VoiceLogScreenState();
}

class _VoiceLogScreenState extends State<VoiceLogScreen> {
  static const timezone = String.fromEnvironment(
    'OPENNUTRI_TIMEZONE',
    defaultValue: 'Europe/Istanbul',
  );

  late final VoiceRecorderSession _recorder;
  late final bool _ownsRecorder;
  VoiceLogState _state = VoiceLogState.ready;
  VoiceResolution? _resolution;
  List<_ReviewItem> _reviewItems = const [];
  String? _error;
  String? _processingPath;

  @override
  void initState() {
    super.initState();
    _ownsRecorder = widget.recorder == null;
    _recorder = widget.recorder ?? OpenNutriVoiceRecorder();
    _recorder.addListener(_onRecorderChanged);
    if (widget.autoStart) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _startRecording());
    }
  }

  @override
  void dispose() {
    _recorder.removeListener(_onRecorderChanged);
    unawaited(_recorder.deleteTemporaryFile());
    if (_ownsRecorder) _recorder.dispose();
    for (final item in _reviewItems) {
      item.dispose();
    }
    super.dispose();
  }

  void _onRecorderChanged() {
    if (_state == VoiceLogState.recording &&
        _recorder.state == VoiceRecorderState.stopped &&
        _recorder.currentPath != null) {
      unawaited(_processRecording(_recorder.currentPath!));
    }
  }

  Future<bool> _ensureDisclosure() async {
    if (widget.controller.voiceDisclosureAccepted) return true;
    var feedback = false;
    final accepted = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Before voice logging'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Your recording is sent transiently to Google Gemini to '
                  'transcribe and match foods. OpenNutri deletes the temporary '
                  'audio after the request and never stores it in your diary or '
                  'Supabase.',
                ),
                const SizedBox(height: 12),
                const Text(
                  'This beta uses Gemini’s free tier. Google states that '
                  'free-tier data may be used to improve its products.',
                ),
                const SizedBox(height: 12),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  value: feedback,
                  onChanged: (value) =>
                      setDialogState(() => feedback = value ?? false),
                  title: const Text('Share correction feedback'),
                  subtitle: const Text(
                    'Optional. Sends only short food phrases, proposed/final '
                    'Core IDs, correction status, and version metadata.',
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('Not now'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: const Text('Continue'),
            ),
          ],
        ),
      ),
    );
    if (accepted != true) return false;
    await widget.controller.acceptVoiceDisclosure(feedbackConsent: feedback);
    return true;
  }

  Future<void> _startRecording() async {
    if (!widget.voiceApiClient.isConfigured) {
      setState(() {
        _state = VoiceLogState.manualSearch;
        _error = 'Voice service is not configured in this build.';
      });
      return;
    }
    if (!await _ensureDisclosure() || !mounted) return;
    setState(() {
      _error = null;
      _state = VoiceLogState.recording;
    });
    final started = await _recorder.start();
    if (!mounted || started) return;
    setState(() {
      _state = _recorder.state == VoiceRecorderState.permissionDenied
          ? VoiceLogState.permissionDenied
          : VoiceLogState.error;
      _error = _recorder.errorMessage ?? 'Could not start the microphone.';
    });
  }

  Future<void> _stopRecording() async {
    final path = await _recorder.stop();
    if (path != null) await _processRecording(path);
  }

  Future<void> _cancelRecording() async {
    await _recorder.cancel();
    if (!mounted) return;
    setState(() => _state = VoiceLogState.ready);
  }

  Future<void> _processRecording(String path) async {
    if (_processingPath == path) return;
    _processingPath = path;
    setState(() => _state = VoiceLogState.processing);
    try {
      final response = await widget.voiceApiClient.resolveVoice(
        wavPath: path,
        languageHint: 'auto',
        localTimestamp: DateTime.now(),
        timezone: timezone,
      );
      if (!mounted) return;
      _resolution = response;
      if (response.requiresManualSearch) {
        setState(() {
          _state = VoiceLogState.manualSearch;
          _error = _fallbackMessage(response.errorCode);
        });
        return;
      }
      await _prepareReview(response);
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _state = VoiceLogState.manualSearch;
        _error =
            'Voice matching is temporarily unavailable. You can still search '
            'manually.';
      });
    } finally {
      await _recorder.deleteTemporaryFile(path);
      _processingPath = null;
    }
  }

  Future<void> _prepareReview(VoiceResolution response) async {
    final ids = response.items
        .expand((item) => item.candidates)
        .map((candidate) => candidate.foodId)
        .toSet();
    final details = <String, FoodDetail>{};
    await Future.wait(
      ids.map((id) async {
        details[id] = await widget.coreApiClient.foodDetail(id);
      }),
    );
    for (final item in _reviewItems) {
      item.dispose();
    }
    _reviewItems = response.items
        .map(
          (item) => _ReviewItem(
            resolution: item,
            details: details,
            onChanged: () {
              if (mounted) setState(() {});
            },
          ),
        )
        .toList(growable: false);
    if (!mounted) return;
    setState(() => _state = VoiceLogState.review);
  }

  String _fallbackMessage(String? errorCode) {
    return switch (errorCode) {
      'request_in_progress' => 'Another food resolution is still in progress.',
      'user_minute_limit' =>
        'Too many requests. Try manual search for a moment.',
      'user_daily_limit' => 'Today’s free voice limit has been reached.',
      'global_daily_limit' =>
        'Today’s shared free voice limit has been reached.',
      'supabase_unavailable' =>
        'The private resolver is temporarily unavailable.',
      'gemini_unavailable' => 'Gemini is temporarily unavailable.',
      _ => 'Voice matching is unavailable. You can still search manually.',
    };
  }

  bool get _canLogAll =>
      _reviewItems.isNotEmpty && _reviewItems.every((item) => item.isValid);

  Future<void> _logAll() async {
    if (!_canLogAll || _resolution == null) return;
    final entries = <DiaryEntry>[];
    final feedback = <VoiceFeedbackItem>[];
    for (final item in _reviewItems) {
      final detail = item.selectedDetail!;
      final inputGrams = item.grams!;
      final basis = item.weightBasis!;
      var edibleGrams = inputGrams;
      if (basis == LoggedWeightBasis.asPurchased) {
        edibleGrams = detail.asPurchasedFactor!.edibleGramsFor(inputGrams);
      }
      entries.add(
        DiaryEntry.fromFood(
          food: detail,
          date: widget.controller.selectedDate,
          meal: item.meal,
          grams: edibleGrams,
          inputGrams: inputGrams,
          weightBasis: basis,
          servingLabel: item.servingLabel,
          id:
              '${_resolution!.metadata.requestId}-'
              '${item.resolution.conceptIndex}',
        ),
      );
      feedback.add(
        VoiceFeedbackItem(
          sourcePhrase: item.resolution.sourcePhrase,
          proposedFoodId: item.resolution.selectedCandidate?.foodId,
          finalFoodId: detail.foodId,
          corrected: detail.foodId != item.resolution.selectedCandidate?.foodId,
        ),
      );
    }
    await widget.controller.addEntries(entries);
    if (widget.controller.voiceFeedbackConsent) {
      try {
        await widget.voiceApiClient.sendFeedback(
          metadata: _resolution!.metadata,
          items: feedback,
        );
      } catch (_) {
        // Optional feedback never blocks local diary logging.
      }
    }
    if (!mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    final ids = entries.map((entry) => entry.id).toList(growable: false);
    Navigator.of(context).pop();
    messenger.showSnackBar(
      SnackBar(
        content: Text('${entries.length} foods logged'),
        action: SnackBarAction(
          label: 'Undo',
          onPressed: () => widget.controller.removeEntries(ids),
        ),
      ),
    );
  }

  Future<void> _openManualSearch() async {
    final entry = await Navigator.of(context).push<DiaryEntry>(
      MaterialPageRoute(
        builder: (context) => FoodSearchScreen(
          apiClient: widget.coreApiClient,
          resolver: widget.voiceApiClient,
          meal: _reviewItems.isEmpty
              ? MealType.snacks
              : _reviewItems.first.meal,
          date: widget.controller.selectedDate,
        ),
      ),
    );
    if (entry != null) await widget.controller.addEntry(entry);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Voice log')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: AnimatedSwitcher(
            duration: const Duration(milliseconds: 200),
            child: switch (_state) {
              VoiceLogState.ready => _ReadyView(onStart: _startRecording),
              VoiceLogState.recording => _RecordingView(
                onStop: _stopRecording,
                onCancel: _cancelRecording,
              ),
              VoiceLogState.processing => const _ProcessingView(),
              VoiceLogState.review => _ReviewView(
                transcript: _resolution?.transcript ?? '',
                items: _reviewItems,
                canLogAll: _canLogAll,
                onLogAll: _logAll,
                onManualSearch: _openManualSearch,
              ),
              VoiceLogState.manualSearch => _FallbackView(
                message: _error,
                icon: Icons.manage_search,
                onRetry: _startRecording,
                onManualSearch: _openManualSearch,
              ),
              VoiceLogState.permissionDenied => _FallbackView(
                message:
                    'Microphone permission is required. Allow it in Android '
                    'settings, then try again.',
                icon: Icons.mic_off_outlined,
                onRetry: _startRecording,
                onManualSearch: _openManualSearch,
              ),
              VoiceLogState.error => _FallbackView(
                message: _error ?? 'Voice logging failed.',
                icon: Icons.error_outline,
                onRetry: _startRecording,
                onManualSearch: _openManualSearch,
              ),
            },
          ),
        ),
      ),
    );
  }
}

class _ReviewItem {
  _ReviewItem({
    required this.resolution,
    required this.details,
    required this.onChanged,
  }) : selectedFoodId = resolution.selectedCandidate?.foodId,
       meal = resolution.mealDefault,
       weightBasis = resolution.weightBasis.value,
       unresolved = resolution.unresolvedFields.toSet(),
       selectedPortionId = resolution.quantity.sourcePortionId,
       gramsController = TextEditingController(
         text: resolution.quantity.grams?.toStringAsFixed(
           resolution.quantity.grams! % 1 == 0 ? 0 : 1,
         ),
       ) {
    gramsController.addListener(_handleGrams);
  }

  final ResolvedVoiceItem resolution;
  final Map<String, FoodDetail> details;
  final VoidCallback onChanged;
  final TextEditingController gramsController;
  final Set<String> unresolved;
  String? selectedFoodId;
  String? selectedPortionId;
  LoggedWeightBasis? weightBasis;
  late MealType meal;

  FoodDetail? get selectedDetail => details[selectedFoodId];
  double? get grams {
    final value = double.tryParse(gramsController.text.replaceAll(',', '.'));
    return value != null && value > 0 ? value : null;
  }

  bool get isValid =>
      selectedDetail != null &&
      grams != null &&
      weightBasis != null &&
      unresolved.isEmpty &&
      (weightBasis != LoggedWeightBasis.asPurchased ||
          selectedDetail!.asPurchasedFactor != null);

  String get servingLabel {
    if (selectedPortionId != null) {
      return selectedDetail?.portions
              .where((portion) => portion.portionId == selectedPortionId)
              .firstOrNull
              ?.description ??
          'Source portion';
    }
    return weightBasis == LoggedWeightBasis.asPurchased
        ? 'As purchased'
        : 'Edible weight';
  }

  void _handleGrams() {
    if (grams != null) unresolved.remove('quantity');
    onChanged();
  }

  void selectFood(String? foodId) {
    selectedFoodId = foodId;
    unresolved.remove('food');
    selectedPortionId = null;
    if (weightBasis == LoggedWeightBasis.asPurchased &&
        selectedDetail?.asPurchasedFactor == null) {
      weightBasis = null;
      unresolved.add('weight_basis');
    }
    onChanged();
  }

  void selectPortion(String? portionId) {
    selectedPortionId = portionId;
    if (portionId != null) {
      final portion = selectedDetail!.portions.firstWhere(
        (value) => value.portionId == portionId,
      );
      gramsController.text = portion.gramWeight.toStringAsFixed(
        portion.gramWeight % 1 == 0 ? 0 : 1,
      );
    }
    onChanged();
  }

  void selectWeightBasis(LoggedWeightBasis? basis) {
    weightBasis = basis;
    if (basis != null) unresolved.remove('weight_basis');
    onChanged();
  }

  void confirm(String field) {
    unresolved.remove(field);
    onChanged();
  }

  void dispose() {
    gramsController
      ..removeListener(_handleGrams)
      ..dispose();
  }
}

class _ReadyView extends StatelessWidget {
  const _ReadyView({required this.onStart});
  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) {
    return Padding(
      key: const ValueKey('voice-ready'),
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.mic_none,
            size: 72,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(height: 20),
          Text(
            'Describe your meal',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 8),
          const Text(
            'Include amounts and details such as raw, cooked, drained, '
            'skin, bone, or as-purchased weight.',
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: onStart,
            icon: const Icon(Icons.mic),
            label: const Text('Start recording'),
          ),
        ],
      ),
    );
  }
}

class _RecordingView extends StatelessWidget {
  const _RecordingView({required this.onStop, required this.onCancel});
  final VoidCallback onStop;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    return Padding(
      key: const ValueKey('voice-recording'),
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const SizedBox.square(
            dimension: 88,
            child: CircularProgressIndicator(strokeWidth: 7),
          ),
          const SizedBox(height: 24),
          Text('Listening…', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8),
          const Text('Stops automatically after you finish speaking.'),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: onStop,
            icon: const Icon(Icons.stop),
            label: const Text('Stop'),
          ),
          TextButton(onPressed: onCancel, child: const Text('Cancel')),
        ],
      ),
    );
  }
}

class _ProcessingView extends StatelessWidget {
  const _ProcessingView();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      key: ValueKey('voice-processing'),
      padding: EdgeInsets.all(32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircularProgressIndicator(),
          SizedBox(height: 20),
          Text('Matching foods…'),
          SizedBox(height: 8),
          Text('Your recording will be deleted when this request finishes.'),
        ],
      ),
    );
  }
}

class _ReviewView extends StatelessWidget {
  const _ReviewView({
    required this.transcript,
    required this.items,
    required this.canLogAll,
    required this.onLogAll,
    required this.onManualSearch,
  });

  final String transcript;
  final List<_ReviewItem> items;
  final bool canLogAll;
  final VoidCallback onLogAll;
  final VoidCallback onManualSearch;

  @override
  Widget build(BuildContext context) {
    return Column(
      key: const ValueKey('voice-review'),
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
            children: [
              if (transcript.isNotEmpty)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Heard',
                          style: Theme.of(context).textTheme.labelLarge,
                        ),
                        const SizedBox(height: 4),
                        Text(transcript),
                      ],
                    ),
                  ),
                ),
              for (final item in items) _ReviewItemCard(item: item),
              TextButton.icon(
                onPressed: onManualSearch,
                icon: const Icon(Icons.search),
                label: const Text('Use manual search'),
              ),
            ],
          ),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
            child: SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: canLogAll ? onLogAll : null,
                icon: const Icon(Icons.check),
                label: Text('Log all (${items.length})'),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _ReviewItemCard extends StatelessWidget {
  const _ReviewItemCard({required this.item});
  final _ReviewItem item;

  @override
  Widget build(BuildContext context) {
    final detail = item.selectedDetail;
    final candidateIds = item.resolution.candidates
        .map((candidate) => candidate.foodId)
        .where(item.details.containsKey)
        .toList(growable: false);
    return Card(
      margin: const EdgeInsets.only(top: 12),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '“${item.resolution.sourcePhrase}”',
              style: Theme.of(context).textTheme.labelLarge,
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: candidateIds.contains(item.selectedFoodId)
                  ? item.selectedFoodId
                  : null,
              decoration: const InputDecoration(labelText: 'Core food'),
              items: [
                for (final foodId in candidateIds)
                  DropdownMenuItem(
                    value: foodId,
                    child: Text(
                      item.details[foodId]!.name,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
              ],
              onChanged: item.selectFood,
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String?>(
              initialValue: item.selectedPortionId,
              decoration: const InputDecoration(labelText: 'Amount source'),
              items: [
                const DropdownMenuItem<String?>(
                  value: null,
                  child: Text('Enter grams'),
                ),
                for (final portion in detail?.portions ?? const <FoodPortion>[])
                  DropdownMenuItem<String?>(
                    value: portion.portionId,
                    child: Text(
                      '${portion.description} (${portion.gramWeight} g)',
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
              ],
              onChanged: detail == null ? null : item.selectPortion,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: item.gramsController,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: const InputDecoration(
                labelText: 'Weight',
                suffixText: 'g',
              ),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<LoggedWeightBasis>(
              initialValue: item.weightBasis,
              decoration: const InputDecoration(labelText: 'Weight basis'),
              items: [
                const DropdownMenuItem(
                  value: LoggedWeightBasis.edible,
                  child: Text('Edible weight'),
                ),
                if (detail?.asPurchasedFactor != null)
                  const DropdownMenuItem(
                    value: LoggedWeightBasis.asPurchased,
                    child: Text('As-purchased weight'),
                  ),
              ],
              onChanged: detail == null ? null : item.selectWeightBasis,
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<MealType>(
              initialValue: item.meal,
              decoration: const InputDecoration(labelText: 'Meal'),
              items: [
                for (final meal in MealType.values)
                  DropdownMenuItem(value: meal, child: Text(meal.label)),
              ],
              onChanged: (meal) {
                if (meal != null) {
                  item.meal = meal;
                  item.onChanged();
                }
              },
            ),
            if (item.unresolved.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text(
                'Needs confirmation',
                style: Theme.of(context).textTheme.labelLarge,
              ),
              const SizedBox(height: 6),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                children: [
                  for (final field in item.unresolved)
                    if (!{'food', 'quantity', 'weight_basis'}.contains(field))
                      InputChip(
                        label: Text(_clarificationLabel(field)),
                        onPressed: () => item.confirm(field),
                        avatar: const Icon(Icons.check, size: 18),
                      ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  String _clarificationLabel(String field) {
    return switch (field) {
      'preparation' =>
        'Confirm ${item.resolution.preparation.join(', ').isEmpty ? 'preparation' : item.resolution.preparation.join(', ')}',
      'unspecified_food' => 'Use unspecified food',
      _ => 'Confirm $field',
    };
  }
}

class _FallbackView extends StatelessWidget {
  const _FallbackView({
    required this.message,
    required this.icon,
    required this.onRetry,
    required this.onManualSearch,
  });
  final String? message;
  final IconData icon;
  final VoidCallback onRetry;
  final VoidCallback onManualSearch;

  @override
  Widget build(BuildContext context) {
    return Padding(
      key: const ValueKey('voice-fallback'),
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 58, color: Theme.of(context).colorScheme.error),
          const SizedBox(height: 16),
          Text(
            message ?? 'Voice logging is unavailable.',
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: onManualSearch,
            icon: const Icon(Icons.search),
            label: const Text('Manual search'),
          ),
          TextButton(onPressed: onRetry, child: const Text('Try voice again')),
        ],
      ),
    );
  }
}
