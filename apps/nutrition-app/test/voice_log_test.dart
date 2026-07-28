import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:opennutri_app/models/diary.dart';
import 'package:opennutri_app/models/food.dart';
import 'package:opennutri_app/models/voice_resolution.dart';
import 'package:opennutri_app/screens/voice_log_screen.dart';
import 'package:opennutri_app/services/core_api_client.dart';
import 'package:opennutri_app/services/local_store.dart';
import 'package:opennutri_app/services/voice_api_client.dart';
import 'package:opennutri_app/services/voice_recorder.dart';
import 'package:opennutri_app/state/app_controller.dart';

void main() {
  test(
    'silence detector waits for speech opportunity and trailing silence',
    () {
      final detector = SilenceStopDetector();

      expect(
        detector.observe(dbfs: -60, elapsed: const Duration(milliseconds: 700)),
        isFalse,
      );
      expect(
        detector.observe(dbfs: -60, elapsed: const Duration(milliseconds: 800)),
        isFalse,
      );
      expect(
        detector.observe(
          dbfs: -20,
          elapsed: const Duration(milliseconds: 1500),
        ),
        isFalse,
      );
      expect(
        detector.observe(
          dbfs: -60,
          elapsed: const Duration(milliseconds: 1600),
        ),
        isFalse,
      );
      expect(
        detector.observe(
          dbfs: -60,
          elapsed: const Duration(milliseconds: 2800),
        ),
        isTrue,
      );
    },
  );

  testWidgets(
    'voice review disables batch logging until quantity is resolved',
    (tester) async {
      final store = _MemoryStore(disclosureAccepted: true);
      final controller = AppController(store);
      await controller.initialize();
      final recorder = _FakeRecorder();
      final voiceClient = _FakeVoiceClient();

      await tester.pumpWidget(
        MaterialApp(
          home: VoiceLogScreen(
            controller: controller,
            coreApiClient: _FakeCoreClient(),
            voiceApiClient: voiceClient,
            recorder: recorder,
          ),
        ),
      );

      await tester.tap(find.text('Start recording'));
      await tester.pump();
      expect(find.text('Listening…'), findsOneWidget);
      expect(voiceClient.warmUpCalls, 1);

      await tester.tap(find.text('Stop'));
      await tester.pumpAndSettle();

      final logButton = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Log all (1)'),
      );
      expect(logButton.onPressed, isNull);

      await tester.enterText(find.widgetWithText(TextField, 'Weight'), '125');
      await tester.pump();
      final enabledButton = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Log all (1)'),
      );
      expect(enabledButton.onPressed, isNotNull);

      await tester.tap(find.text('Log all (1)'));
      await tester.pumpAndSettle();

      expect(controller.entries, hasLength(1));
      expect(controller.entries.single.grams, 125);
      expect(store.entrySaveCount, 1);
      expect(recorder.deletedPaths, contains('/tmp/fake.wav'));
    },
  );

  testWidgets('first-use disclosure leaves feedback optional', (tester) async {
    final store = _MemoryStore();
    final controller = AppController(store);
    await controller.initialize();
    final recorder = _FakeRecorder();

    await tester.pumpWidget(
      MaterialApp(
        home: VoiceLogScreen(
          controller: controller,
          coreApiClient: _FakeCoreClient(),
          voiceApiClient: _FakeVoiceClient(),
          recorder: recorder,
        ),
      ),
    );
    await tester.tap(find.text('Start recording'));
    await tester.pumpAndSettle();

    expect(find.text('Before voice logging'), findsOneWidget);
    await tester.tap(find.text('Share correction feedback'));
    await tester.tap(find.text('Continue'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(controller.voiceDisclosureAccepted, isTrue);
    expect(controller.voiceFeedbackConsent, isTrue);
    expect(find.text('Listening…'), findsOneWidget);
  });

  testWidgets(
    'a fully resolved high-confidence batch logs automatically and can be edited',
    (tester) async {
      final store = _MemoryStore(disclosureAccepted: true);
      final controller = AppController(store);
      await controller.initialize();
      final recorder = _FakeRecorder();

      await tester.pumpWidget(
        MaterialApp(
          home: VoiceLogScreen(
            controller: controller,
            coreApiClient: _FakeCoreClient(),
            voiceApiClient: _ResolvedVoiceClient(),
            recorder: recorder,
          ),
        ),
      );

      await tester.tap(find.text('Start recording'));
      await tester.pump();
      await tester.tap(find.text('Stop'));
      await tester.pumpAndSettle();

      expect(find.text('Logged automatically'), findsOneWidget);
      expect(controller.entries, hasLength(1));
      expect(controller.entries.single.grams, 100);
      expect(store.entrySaveCount, 1);

      await tester.tap(find.text('Edit batch'));
      await tester.pumpAndSettle();
      expect(controller.entries, isEmpty);
      expect(find.widgetWithText(FilledButton, 'Log all (1)'), findsOneWidget);

      await tester.tap(find.text('Log all (1)'));
      await tester.pumpAndSettle();
      expect(controller.entries, hasLength(1));
      expect(store.entrySaveCount, 3);
    },
  );

  testWidgets('provider failures use the safe manual-search fallback', (
    tester,
  ) async {
    final store = _MemoryStore(disclosureAccepted: true);
    final controller = AppController(store);
    await controller.initialize();
    final recorder = _FakeRecorder();

    await tester.pumpWidget(
      MaterialApp(
        home: VoiceLogScreen(
          controller: controller,
          coreApiClient: _FakeCoreClient(),
          voiceApiClient: _FailingVoiceClient(),
          recorder: recorder,
        ),
      ),
    );

    await tester.tap(find.text('Start recording'));
    await tester.pump();
    await tester.tap(find.text('Stop'));
    await tester.pumpAndSettle();

    expect(
      find.text(
        'Voice matching is temporarily unavailable. You can still search '
        'manually.',
      ),
      findsOneWidget,
    );
    expect(find.textContaining('AuthApiException'), findsNothing);
    expect(recorder.deletedPaths, contains('/tmp/fake.wav'));
  });
}

class _FakeRecorder extends ChangeNotifier implements VoiceRecorderSession {
  @override
  VoiceRecorderState state = VoiceRecorderState.idle;
  @override
  String? errorMessage;
  @override
  String? currentPath;
  final List<String> deletedPaths = [];

  @override
  Future<bool> start() async {
    currentPath = '/tmp/fake.wav';
    state = VoiceRecorderState.recording;
    notifyListeners();
    return true;
  }

  @override
  Future<String?> stop() async {
    state = VoiceRecorderState.stopped;
    notifyListeners();
    return currentPath;
  }

  @override
  Future<void> cancel() async {
    state = VoiceRecorderState.idle;
    if (currentPath != null) deletedPaths.add(currentPath!);
    currentPath = null;
    notifyListeners();
  }

  @override
  Future<void> deleteTemporaryFile([String? path]) async {
    final target = path ?? currentPath;
    if (target != null) deletedPaths.add(target);
    if (path == null || path == currentPath) currentPath = null;
  }
}

class _FakeVoiceClient extends VoiceApiClient {
  int warmUpCalls = 0;

  @override
  bool get isConfigured => true;

  @override
  Future<void> warmUp() async {
    warmUpCalls += 1;
  }

  @override
  Future<VoiceResolution> resolveVoice({
    required String wavPath,
    required String languageHint,
    required DateTime localTimestamp,
    required String timezone,
  }) async {
    return const VoiceResolution(
      status: 'resolved',
      metadata: ResolutionMetadata(
        requestId: 'request-1',
        coreVersion: '0.3.0',
        indexVersion: 'index-1',
        selectorModel: 'selector-1',
      ),
      transcript: 'apple',
      detectedLanguage: 'en',
      items: [
        ResolvedVoiceItem(
          conceptIndex: 0,
          sourcePhrase: 'apple',
          selectedCandidate: VoiceFoodCandidate(
            foodId: 'food-apple',
            name: 'Apple, raw',
            category: 'Fruit',
            qualityStatus: 'complete',
            sourceReleaseId: 'fixture',
            portions: [],
            hasUsableWeightFactor: false,
            matchedChannels: ['primary'],
            retrievalScore: 1,
          ),
          alternatives: [],
          confidence: 0.95,
          preparation: ['raw'],
          weightBasis: VoiceWeightBasis(
            status: 'resolved',
            value: LoggedWeightBasis.edible,
          ),
          quantity: VoiceQuantity(status: 'unresolved'),
          mealDefault: MealType.snacks,
          unresolvedFields: ['quantity'],
          isUnspecified: false,
        ),
      ],
      manualSearchCandidates: [],
    );
  }
}

class _FailingVoiceClient extends VoiceApiClient {
  @override
  bool get isConfigured => true;

  @override
  Future<VoiceResolution> resolveVoice({
    required String wavPath,
    required String languageHint,
    required DateTime localTimestamp,
    required String timezone,
  }) => throw const VoiceApiException(
    'AuthApiException(message: provider implementation detail)',
  );
}

class _ResolvedVoiceClient extends _FakeVoiceClient {
  @override
  Future<VoiceResolution> resolveVoice({
    required String wavPath,
    required String languageHint,
    required DateTime localTimestamp,
    required String timezone,
  }) async {
    return const VoiceResolution(
      status: 'resolved',
      metadata: ResolutionMetadata(
        requestId: 'request-2',
        coreVersion: '0.3.0',
        indexVersion: 'index-1',
        selectorModel: 'selector-1',
      ),
      transcript: '100 grams raw apple',
      detectedLanguage: 'en',
      items: [
        ResolvedVoiceItem(
          conceptIndex: 0,
          sourcePhrase: '100 grams raw apple',
          selectedCandidate: VoiceFoodCandidate(
            foodId: 'food-apple',
            name: 'Apple, raw',
            category: 'Fruit',
            qualityStatus: 'complete',
            sourceReleaseId: 'fixture',
            portions: [],
            hasUsableWeightFactor: false,
            matchedChannels: ['primary'],
            retrievalScore: 1,
          ),
          alternatives: [],
          confidence: 0.95,
          preparation: ['raw'],
          weightBasis: VoiceWeightBasis(
            status: 'resolved',
            value: LoggedWeightBasis.edible,
          ),
          quantity: VoiceQuantity(
            status: 'resolved',
            grams: 100,
            spokenValue: 100,
            spokenUnit: 'g',
          ),
          mealDefault: MealType.breakfast,
          unresolvedFields: [],
          isUnspecified: false,
        ),
      ],
      manualSearchCandidates: [],
    );
  }
}

class _FakeCoreClient extends CoreApiClient {
  @override
  Future<FoodDetail> foodDetail(String foodId) async => _apple;
}

const _apple = FoodDetail(
  foodId: 'food-apple',
  name: 'Apple, raw',
  categoryName: 'Fruit',
  publisher: 'USDA',
  datasetName: 'Fixture',
  sourceFoodCode: '1',
  qualityStatus: 'complete',
  nutrients: [
    FoodNutrient(
      nutrientId: 'energy',
      name: 'Energy',
      amount: 52,
      unit: 'kcal',
    ),
  ],
  portions: [],
);

class _MemoryStore extends LocalStore {
  _MemoryStore({this.disclosureAccepted = false});
  bool disclosureAccepted;
  bool feedbackConsent = false;
  bool fastLogging = true;
  int entrySaveCount = 0;

  @override
  Future<List<DiaryEntry>> loadEntries() async => const [];
  @override
  Future<NutritionTargets> loadTargets() async => const NutritionTargets();
  @override
  Future<bool> loadVoiceDisclosureAccepted() async => disclosureAccepted;
  @override
  Future<bool> loadVoiceFeedbackConsent() async => feedbackConsent;
  @override
  Future<bool> loadVoiceFastLogging() async => fastLogging;
  @override
  Future<void> saveEntries(List<DiaryEntry> entries) async {
    entrySaveCount += 1;
  }

  @override
  Future<void> saveVoiceDisclosureAccepted(bool accepted) async {
    disclosureAccepted = accepted;
  }

  @override
  Future<void> saveVoiceFeedbackConsent(bool enabled) async {
    feedbackConsent = enabled;
  }

  @override
  Future<void> saveVoiceFastLogging(bool enabled) async {
    fastLogging = enabled;
  }
}
