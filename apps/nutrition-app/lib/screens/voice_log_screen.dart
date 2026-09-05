import 'dart:async';

import 'package:flutter/material.dart';

import '../models/diary.dart';
import '../models/food.dart';
import '../models/voice_resolution.dart';
import '../services/core_api_client.dart';
import '../services/android_widget_bridge.dart';
import '../services/voice_api_client.dart';
import '../services/voice_recorder.dart';
import '../state/app_controller.dart';
import 'food_search_screen.dart';

enum VoiceLogState {
  ready,
  recording,
  processing,
  review,
  logged,
  manualSearch,
  permissionDenied,
  error,
}

String voiceLanguageHintForLocale(Locale locale) {
  return switch (locale.languageCode.toLowerCase()) {
    'en' || 'tr' => locale.toLanguageTag(),
    _ => 'auto',
  };
}

class VoiceLogScreen extends StatefulWidget {
  const VoiceLogScreen({
    super.key,
    required this.controller,
    required this.coreApiClient,
    required this.voiceApiClient,
    this.autoStart = false,
    this.quickCapture = false,
    this.recorder,
  });

  final AppController controller;
  final CoreApiClient coreApiClient;
  final VoiceApiClient voiceApiClient;
  final bool autoStart;
  final bool quickCapture;
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
  List<String> _autoLoggedEntryIds = const [];
  String? _error;
  String? _processingPath;
  bool _saving = false;
  String _processingMessage = 'Understanding your meal…';

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
    } else if (_state == VoiceLogState.recording && mounted) {
      setState(() {});
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
    ScaffoldMessenger.of(context).clearSnackBars();
    unawaited(widget.voiceApiClient.warmUp());
    setState(() {
      _error = null;
      _resolution = null;
      _processingMessage = 'Understanding your meal…';
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
    final stopwatch = Stopwatch()..start();
    setState(() {
      _processingMessage = 'Understanding your meal…';
      _state = VoiceLogState.processing;
    });
    try {
      final response = await widget.voiceApiClient.resolveVoice(
        wavPath: path,
        languageHint: voiceLanguageHintForLocale(
          WidgetsBinding.instance.platformDispatcher.locale,
        ),
        localTimestamp: DateTime.now(),
        timezone: timezone,
      );
      if (!mounted) return;
      _resolution = response;
      debugPrint(
        'Voice resolver completed in ${stopwatch.elapsedMilliseconds} ms; '
        'server timings=${response.metadata.timingsMs}',
      );
      if (response.requiresManualSearch) {
        setState(() {
          _state = VoiceLogState.manualSearch;
          _error = _fallbackMessage(response.errorCode);
        });
        return;
      }
      setState(() => _processingMessage = 'Loading trusted nutrition data…');
      // Load only the selected Core foods first. This keeps the common
      // high-confidence path fast: alternatives are fetched only when the
      // person needs to review or edit the result.
      await _prepareReview(response, selectedOnly: true, showReview: false);
      if (!mounted) return;
      if (_canInstantLog) {
        await _logAll(automatic: true);
        return;
      }
      await _prepareReview(response);
    } on VoiceApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _state = VoiceLogState.manualSearch;
        _error = _voiceFailureMessage(error);
      });
    } catch (error) {
      if (!mounted) return;
      debugPrint('Voice result preparation failed: $error');
      setState(() {
        _state = _resolution == null
            ? VoiceLogState.manualSearch
            : VoiceLogState.error;
        _error = _resolution == null
            ? 'We could not finish that voice request. Your diary was not changed.'
            : 'Your meal was understood, but its nutrition details did not finish loading.';
      });
    } finally {
      await _recorder.deleteTemporaryFile(path);
      _processingPath = null;
    }
  }

  String _voiceFailureMessage(VoiceApiException error) {
    return switch (error.kind) {
      VoiceApiFailureKind.timeout =>
        'That took longer than expected. Your diary was not changed.',
      VoiceApiFailureKind.network =>
        'You appear to be offline. Reconnect or use food search.',
      VoiceApiFailureKind.authentication =>
        'A private voice session could not be started. Try again in a moment.',
      VoiceApiFailureKind.rateLimited =>
        'The AI request limit has been reached. Try again later or use food search.',
      VoiceApiFailureKind.service =>
        'The voice service is taking a break. Your diary was not changed.',
      VoiceApiFailureKind.invalidResponse =>
        'The voice service returned an incomplete result. Your diary was not changed.',
      VoiceApiFailureKind.unknown =>
        'We could not finish that voice request. Your diary was not changed.',
    };
  }

  Future<void> _retryDetails() async {
    final response = _resolution;
    if (response == null) {
      await _startRecording();
      return;
    }
    setState(() {
      _error = null;
      _processingMessage = 'Loading trusted nutrition data…';
      _state = VoiceLogState.processing;
    });
    try {
      await _prepareReview(response, selectedOnly: true, showReview: false);
      if (!mounted) return;
      if (_canInstantLog) {
        await _logAll(automatic: true);
      } else {
        await _prepareReview(response);
      }
    } catch (error) {
      if (!mounted) return;
      debugPrint('Voice detail retry failed: $error');
      setState(() {
        _error =
            'Nutrition details are still unavailable. You can retry or search manually.';
        _state = VoiceLogState.error;
      });
    }
  }

  Future<void> _prepareReview(
    VoiceResolution response, {
    bool selectedOnly = false,
    bool showReview = true,
  }) async {
    final candidates = selectedOnly
        ? response.items
              .map((item) => item.selectedCandidate)
              .whereType<VoiceFoodCandidate>()
        : response.items.expand((item) => item.candidates);
    final ids = candidates.map((candidate) => candidate.foodId).toSet();
    final details = <String, FoodDetail>{};
    await Future.wait(
      ids.map((id) async {
        details[id] = await widget.coreApiClient.foodDetail(id);
      }),
    );
    if (!mounted) return;
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
    if (!mounted || !showReview) return;
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
      'gemini_rate_limited' =>
        'Voice understanding is busy right now. Your diary was not changed.',
      'gemini_invalid_output' =>
        'I heard the recording, but could not turn it into a safe food log.',
      'gemini_request_rejected' || 'gemini_configuration_error' =>
        'The voice service needs attention. Your diary was not changed.',
      'gemini_unavailable' =>
        'Voice understanding could not finish this time. Your diary was not changed.',
      'no_foods_detected' =>
        'I could not identify a food in that recording. Check what I heard or try again.',
      _ => 'Voice matching is unavailable. You can still search manually.',
    };
  }

  bool get _canLogAll =>
      _reviewItems.isNotEmpty && _reviewItems.every((item) => item.isValid);

  // Voice logging is deliberately optimistic: when the resolver supplies a
  // usable Core food, it is written immediately. Any inferred amount or
  // ambiguous match is marked for review in the diary instead of blocking the
  // capture flow with a confirmation form.
  bool get _canInstantLog => _canLogAll;

  Future<void> _logAll({bool automatic = false}) async {
    if (!_canLogAll || _resolution == null || _saving) return;
    setState(() => _saving = true);
    final editing = _autoLoggedEntryIds.isNotEmpty;
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
          loggedByVoice: true,
          needsReview: automatic && item.wasEstimated,
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
    try {
      if (editing) {
        await widget.controller.updateEntries(entries);
      } else {
        await widget.controller.addEntries(entries);
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Could not save foods. Please try again.'),
          ),
        );
        setState(() => _state = VoiceLogState.review);
      }
      return;
    } finally {
      if (mounted) setState(() => _saving = false);
    }
    if (widget.controller.voiceFeedbackConsent) {
      unawaited(
        _sendFeedback(metadata: _resolution!.metadata, items: feedback),
      );
    }
    if (!mounted) return;
    final ids = entries.map((entry) => entry.id).toList(growable: false);
    if (automatic) {
      setState(() {
        _autoLoggedEntryIds = ids;
        _state = VoiceLogState.logged;
      });
      if (widget.quickCapture) {
        await Future<void>.delayed(const Duration(milliseconds: 550));
        if (!mounted ||
            _state != VoiceLogState.logged ||
            !identical(_autoLoggedEntryIds, ids)) {
          return;
        }
        await AndroidWidgetBridge.finishQuickCapture(
          foodCount: entries.length,
          needsReview: entries.any((entry) => entry.needsReview),
        );
      }
      return;
    }
    final messenger = ScaffoldMessenger.of(context);
    Navigator.of(context).pop();
    messenger.showSnackBar(
      SnackBar(
        content: Text(
          editing ? 'Foods updated' : '${entries.length} foods logged',
        ),
        action: editing
            ? null
            : SnackBarAction(
                label: 'Undo',
                onPressed: () => widget.controller.removeEntries(ids),
              ),
      ),
    );
  }

  Future<void> _sendFeedback({
    required ResolutionMetadata metadata,
    required List<VoiceFeedbackItem> items,
  }) async {
    try {
      await widget.voiceApiClient.sendFeedback(
        metadata: metadata,
        items: items,
      );
    } catch (_) {
      // Best effort: feedback must never delay success or widget completion.
    }
  }

  Future<void> _undoAutomaticLog() async {
    final ids = _autoLoggedEntryIds;
    if (ids.isEmpty) return;
    await widget.controller.removeEntries(ids);
    if (!mounted) return;
    setState(() {
      _autoLoggedEntryIds = const [];
      _state = VoiceLogState.ready;
    });
  }

  Future<void> _editAutomaticLog() async {
    final resolution = _resolution;
    final ids = _autoLoggedEntryIds;
    if (resolution == null || ids.isEmpty) return;
    // Keep the original diary entries until Save changes succeeds.
    setState(() => _state = VoiceLogState.review);
    try {
      await _prepareReview(resolution);
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Alternatives are unavailable. You can still edit the saved match.',
          ),
        ),
      );
    }
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
          initialQuery:
              _resolution?.items.firstOrNull?.sourcePhrase ??
              _resolution?.manualSearchQuery,
        ),
      ),
    );
    if (entry != null) await widget.controller.addEntry(entry);
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Log with voice')),
      body: DecoratedBox(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              scheme.primaryContainer.withValues(alpha: 0.22),
              scheme.surface,
              scheme.surface,
            ],
            stops: const [0, 0.38, 1],
          ),
        ),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760),
            child: AnimatedSwitcher(
              duration: const Duration(milliseconds: 280),
              switchInCurve: Curves.easeOutCubic,
              child: switch (_state) {
                VoiceLogState.ready => _ReadyView(onStart: _startRecording),
                VoiceLogState.recording => _RecordingView(
                  amplitudeDbfs: _recorder.amplitudeDbfs,
                  elapsed: _recorder.elapsed,
                  onStop: _stopRecording,
                  onCancel: _cancelRecording,
                ),
                VoiceLogState.processing => _ProcessingView(
                  message: _processingMessage,
                ),
                VoiceLogState.review => _ReviewView(
                  transcript: _resolution?.transcript ?? '',
                  items: _reviewItems,
                  canLogAll: _canLogAll && !_saving,
                  editing: _autoLoggedEntryIds.isNotEmpty,
                  onLogAll: () => _logAll(),
                  onManualSearch: _openManualSearch,
                ),
                VoiceLogState.logged => _AutoLoggedView(
                  items: _reviewItems,
                  onUndo: _undoAutomaticLog,
                  onEdit: _editAutomaticLog,
                  onDone: () => Navigator.of(context).pop(),
                ),
                VoiceLogState.manualSearch => _FallbackView(
                  message: _error,
                  icon: Icons.manage_search,
                  onRetry: _startRecording,
                  onManualSearch: _openManualSearch,
                  transcript: _resolution?.transcript,
                ),
                VoiceLogState.permissionDenied => _FallbackView(
                  message:
                      'Microphone permission is required. Allow it in Android '
                      'settings, then try again.',
                  icon: Icons.mic_off_outlined,
                  onRetry: _startRecording,
                  onManualSearch: _openManualSearch,
                  retryLabel: 'Check permission again',
                ),
                VoiceLogState.error => _FallbackView(
                  message: _error ?? 'Voice logging failed.',
                  icon: Icons.cloud_sync_outlined,
                  onRetry: _retryDetails,
                  onManualSearch: _openManualSearch,
                  retryLabel: _resolution == null
                      ? 'Try voice again'
                      : 'Reload nutrition details',
                  transcript: _resolution?.transcript,
                ),
              },
            ),
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
       weightBasis = resolution.weightBasis.value ?? LoggedWeightBasis.edible,
       unresolved = resolution.unresolvedFields.toSet(),
       selectedPortionId = resolution.quantity.sourcePortionId,
       gramsController = TextEditingController(
         text: (resolution.quantity.grams ?? 100).toStringAsFixed(
           (resolution.quantity.grams ?? 100) % 1 == 0 ? 0 : 1,
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

  bool get wasEstimated =>
      resolution.quantity.grams == null ||
      resolution.weightBasis.value == null ||
      resolution.unresolvedFields.isNotEmpty ||
      resolution.alternatives.isNotEmpty ||
      resolution.isUnspecified ||
      !resolution.autoLogEligible;

  FoodDetail? get selectedDetail => details[selectedFoodId];
  double? get grams {
    final value = double.tryParse(gramsController.text.replaceAll(',', '.'));
    return value != null && value.isFinite && value > 0 && value <= 10000
        ? value
        : null;
  }

  bool get isValid =>
      selectedDetail != null &&
      grams != null &&
      weightBasis != null &&
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
    return LayoutBuilder(
      key: const ValueKey('voice-ready'),
      builder: (context, constraints) => SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: ConstrainedBox(
          constraints: BoxConstraints(
            minHeight: (constraints.maxHeight - 64).clamp(0, double.infinity),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 7,
                ),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  'VOICE MEAL LOG',
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: Theme.of(context).colorScheme.onPrimaryContainer,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 1.2,
                  ),
                ),
              ),
              const SizedBox(height: 28),
              Container(
                width: 104,
                height: 104,
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.primary,
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: Theme.of(
                        context,
                      ).colorScheme.primary.withValues(alpha: 0.24),
                      blurRadius: 30,
                      spreadRadius: 6,
                    ),
                  ],
                ),
                child: Icon(
                  Icons.mic_rounded,
                  size: 48,
                  color: Theme.of(context).colorScheme.onPrimary,
                ),
              ),
              const SizedBox(height: 28),
              Text(
                'Say it. See it logged.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                  letterSpacing: -0.7,
                ),
              ),
              const SizedBox(height: 10),
              const Text(
                'Speak naturally and log up to 10 foods in one go.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surface,
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(
                    color: Theme.of(context).colorScheme.outlineVariant,
                  ),
                ),
                child: const Text(
                  '“Breakfast: two eggs, one banana, and a glass of milk.”',
                  textAlign: TextAlign.center,
                ),
              ),
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: onStart,
                  style: FilledButton.styleFrom(
                    minimumSize: const Size.fromHeight(56),
                  ),
                  icon: const Icon(Icons.mic_rounded),
                  label: const Text('Start speaking'),
                ),
              ),
              const SizedBox(height: 12),
              Text(
                'Include amounts and words like raw, cooked, or drained.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RecordingView extends StatelessWidget {
  const _RecordingView({
    required this.amplitudeDbfs,
    required this.elapsed,
    required this.onStop,
    required this.onCancel,
  });
  final double amplitudeDbfs;
  final Duration elapsed;
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
          Text(
            _formatElapsed(elapsed),
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
          const SizedBox(height: 22),
          _VoiceWave(amplitudeDbfs: amplitudeDbfs),
          const SizedBox(height: 28),
          Text(
            'I’m listening',
            style: Theme.of(context).textTheme.headlineMedium?.copyWith(
              fontWeight: FontWeight.w800,
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 8),
          const Text('Pause between foods. Tap done when you finish.'),
          const SizedBox(height: 32),
          SizedBox(
            width: 190,
            child: FilledButton.icon(
              onPressed: onStop,
              style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(56),
              ),
              icon: const Icon(Icons.stop_rounded),
              label: const Text('Done speaking'),
            ),
          ),
          TextButton(onPressed: onCancel, child: const Text('Cancel')),
        ],
      ),
    );
  }

  String _formatElapsed(Duration value) {
    final seconds = value.inSeconds.clamp(0, 30);
    return '0:${seconds.toString().padLeft(2, '0')} / 0:30';
  }
}

class _ProcessingView extends StatelessWidget {
  const _ProcessingView({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) {
    return Padding(
      key: const ValueKey('voice-processing'),
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 88,
            height: 88,
            padding: const EdgeInsets.all(25),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.primaryContainer,
              shape: BoxShape.circle,
            ),
            child: CircularProgressIndicator(
              strokeWidth: 4,
              color: Theme.of(context).colorScheme.primary,
            ),
          ),
          const SizedBox(height: 26),
          Text(
            message,
            textAlign: TextAlign.center,
            style: Theme.of(
              context,
            ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          Text(
            'Matching against verified OpenNutri foods',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 18),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.lock_outline_rounded,
                size: 16,
                color: Theme.of(context).colorScheme.outline,
              ),
              const SizedBox(width: 6),
              Text(
                'Recording deleted after this request',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
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
    required this.editing,
    required this.onLogAll,
    required this.onManualSearch,
  });

  final String transcript;
  final List<_ReviewItem> items;
  final bool canLogAll;
  final bool editing;
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
                label: Text(
                  editing ? 'Save changes' : 'Log all (${items.length})',
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _AutoLoggedView extends StatelessWidget {
  const _AutoLoggedView({
    required this.items,
    required this.onUndo,
    required this.onEdit,
    required this.onDone,
  });

  final List<_ReviewItem> items;
  final VoidCallback onUndo;
  final VoidCallback onEdit;
  final VoidCallback onDone;

  @override
  Widget build(BuildContext context) {
    return Padding(
      key: const ValueKey('voice-auto-logged'),
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.check_circle_outline,
            size: 68,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(height: 16),
          Text(
            'Logged automatically',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 8),
          Text(
            '${items.length} ${items.length == 1 ? 'food was' : 'foods were'} added to Today.',
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          Flexible(
            child: ListView.separated(
              shrinkWrap: true,
              itemCount: items.length,
              separatorBuilder: (_, _) => const Divider(height: 1),
              itemBuilder: (context, index) {
                final item = items[index];
                final grams = item.grams;
                return ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(
                    item.selectedDetail?.name ?? item.resolution.sourcePhrase,
                  ),
                  subtitle: Text(
                    '${item.meal.label}${grams == null ? '' : ' · ${_formatGrams(grams)} g'}',
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: onEdit,
              icon: const Icon(Icons.edit_outlined),
              label: const Text('Edit batch'),
            ),
          ),
          TextButton.icon(
            onPressed: onUndo,
            icon: const Icon(Icons.undo),
            label: const Text('Undo batch'),
          ),
          TextButton(onPressed: onDone, child: const Text('Done')),
        ],
      ),
    );
  }

  String _formatGrams(double grams) =>
      grams % 1 == 0 ? grams.toStringAsFixed(0) : grams.toStringAsFixed(1);
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
              isExpanded: true,
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
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
              ],
              onChanged: item.selectFood,
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String?>(
              isExpanded: true,
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
                      maxLines: 1,
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
              isExpanded: true,
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
              isExpanded: true,
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
                'Check before logging',
                style: Theme.of(context).textTheme.labelLarge,
              ),
              const SizedBox(height: 2),
              Text(
                'Log all confirms these details.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 6),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                children: [
                  for (final field in item.unresolved)
                    InputChip(
                      label: Text(_clarificationLabel(field)),
                      onPressed: _canConfirm(field)
                          ? () => item.confirm(field)
                          : null,
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
      'food' =>
        item.selectedDetail == null ? 'Choose a Core food' : 'Check food match',
      'quantity' => item.grams == null ? 'Enter weight' : 'Check amount',
      'weight_basis' =>
        item.weightBasis == null ? 'Choose weight basis' : 'Check weight basis',
      'preparation' =>
        'Confirm ${item.resolution.preparation.join(', ').isEmpty ? 'preparation' : item.resolution.preparation.join(', ')}',
      'unspecified_food' => 'Use unspecified food',
      'transcription' => 'Confirm transcript',
      _ => 'Confirm $field',
    };
  }

  bool _canConfirm(String field) => switch (field) {
    'food' => item.selectedDetail != null,
    'quantity' => item.grams != null,
    'weight_basis' => item.weightBasis != null,
    _ => true,
  };
}

class _FallbackView extends StatelessWidget {
  const _FallbackView({
    required this.message,
    required this.icon,
    required this.onRetry,
    required this.onManualSearch,
    this.retryLabel = 'Try voice again',
    this.transcript,
  });
  final String? message;
  final IconData icon;
  final VoidCallback onRetry;
  final VoidCallback onManualSearch;
  final String retryLabel;
  final String? transcript;

  @override
  Widget build(BuildContext context) {
    return Padding(
      key: const ValueKey('voice-fallback'),
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 88,
            height: 88,
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.errorContainer,
              shape: BoxShape.circle,
            ),
            child: Icon(
              icon,
              size: 42,
              color: Theme.of(context).colorScheme.onErrorContainer,
            ),
          ),
          const SizedBox(height: 22),
          Text(
            'That didn’t finish',
            style: Theme.of(
              context,
            ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 10),
          Text(
            message ?? 'Voice logging is unavailable.',
            textAlign: TextAlign.center,
          ),
          if (transcript?.trim().isNotEmpty == true) ...[
            const SizedBox(height: 18),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Text('Heard: “${transcript!.trim()}”'),
            ),
          ],
          const SizedBox(height: 20),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: onManualSearch,
              icon: const Icon(Icons.search),
              label: Text(
                transcript?.trim().isNotEmpty == true
                    ? 'Continue with search'
                    : 'Search foods instead',
              ),
            ),
          ),
          TextButton(onPressed: onRetry, child: Text(retryLabel)),
        ],
      ),
    );
  }
}

class _VoiceWave extends StatelessWidget {
  const _VoiceWave({required this.amplitudeDbfs});

  final double amplitudeDbfs;

  @override
  Widget build(BuildContext context) {
    final signal = ((amplitudeDbfs + 55) / 45).clamp(0.08, 1.0);
    const weights = [0.42, 0.75, 1.0, 0.62, 0.9, 0.56, 0.8, 0.38];
    return Container(
      height: 112,
      width: 220,
      padding: const EdgeInsets.symmetric(horizontal: 22),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(32),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          for (final weight in weights)
            AnimatedContainer(
              duration: const Duration(milliseconds: 90),
              curve: Curves.easeOut,
              width: 8,
              height: 16 + (66 * signal * weight),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.primary,
                borderRadius: BorderRadius.circular(99),
              ),
            ),
        ],
      ),
    );
  }
}
