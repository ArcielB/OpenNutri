import 'package:flutter_test/flutter_test.dart';
import 'package:opennutri_app/models/diary.dart';
import 'package:opennutri_app/models/personalization.dart';
import 'package:opennutri_app/services/coach_service.dart';
import 'package:opennutri_app/services/local_store.dart';
import 'package:opennutri_app/services/voice_api_client.dart';
import 'package:opennutri_app/state/app_controller.dart';

void main() {
  test('diet targets adapt to the selected goal and remain editable', () async {
    final store = _ProfileStore();
    final controller = AppController(store);
    await controller.initialize();

    await controller.updateGoal(NutritionGoal.buildMuscle);
    await controller.applyDiet(
      dietPresetById('mediterranean'),
      notes: 'No fish; keep it affordable',
    );

    expect(controller.profile.goal, NutritionGoal.buildMuscle);
    expect(controller.profile.dietId, 'mediterranean');
    expect(controller.profile.dietNotes, 'No fish; keep it affordable');
    expect(controller.targets.calories, 2000);
    expect(controller.targets.protein, 125);
    expect(controller.targets.carbs, 200);
    expect(controller.targets.fat, closeTo(77.78, 0.01));
    expect(store.savedProfile?.dietId, 'mediterranean');
  });

  test(
    'coach memory stores explicit unique facts and can forget them',
    () async {
      final store = _ProfileStore();
      final controller = AppController(store);
      await controller.initialize();
      const memory = CoachMemory(
        fact: 'Avoids shellfish',
        category: 'avoidance',
      );

      await controller.addCoachMemories([memory, memory]);
      expect(controller.profile.memories, hasLength(1));

      await controller.removeCoachMemory(memory);
      expect(controller.profile.memories, isEmpty);
    },
  );

  test(
    'coach receives the real profile, diary totals, and FDA references',
    () async {
      final store = _ProfileStore(
        profile: const UserNutritionProfile(
          goal: NutritionGoal.moreEnergy,
          dietId: 'plant_powered',
          memories: [
            CoachMemory(fact: 'Avoids peanuts', category: 'avoidance'),
          ],
          coachEnabled: true,
        ),
      );
      final controller = AppController(store);
      await controller.initialize();
      final client = _CapturingCoachClient();

      await CoachService(
        client,
      ).respond(controller: controller, mode: CoachMode.oracle);

      expect(client.request?['goal'], 'More energy');
      expect(client.request?['diet'], 'Plant powered');
      expect(client.request?['memories'], ['Avoids peanuts']);
      final metrics = client.request?['daily_totals'] as List<dynamic>;
      expect(
        metrics.cast<Map<String, dynamic>>().singleWhere(
          (value) => value['name'] == 'Calcium',
        )['target'],
        1300,
      );
    },
  );
}

class _CapturingCoachClient extends VoiceApiClient {
  Map<String, dynamic>? request;

  @override
  Future<CoachReply> coach(Map<String, dynamic> request) async {
    this.request = request;
    return const CoachReply(
      headline: 'Test',
      message: 'Test',
      actions: [],
      memoryUpdates: [],
      model: 'fixture',
    );
  }
}

class _ProfileStore extends LocalStore {
  _ProfileStore({this.profile = const UserNutritionProfile()});

  final UserNutritionProfile profile;
  UserNutritionProfile? savedProfile;

  @override
  Future<List<DiaryEntry>> loadEntries() async => const [];
  @override
  Future<NutritionTargets> loadTargets() async => const NutritionTargets();
  @override
  Future<bool> loadVoiceDisclosureAccepted() async => false;
  @override
  Future<bool> loadVoiceFeedbackConsent() async => false;
  @override
  Future<bool> loadVoiceFastLogging() async => true;
  @override
  Future<UserNutritionProfile> loadProfile() async => profile;
  @override
  Future<DailyCoachBrief?> loadDailyCoachBrief() async => null;
  @override
  Future<void> saveEntries(List<DiaryEntry> entries) async {}
  @override
  Future<void> saveTargets(NutritionTargets targets) async {}
  @override
  Future<void> saveProfile(UserNutritionProfile profile) async {
    savedProfile = profile;
  }

  @override
  Future<void> saveDailyCoachBrief(DailyCoachBrief brief) async {}

  @override
  Future<void> clearDailyCoachBrief() async {}
}
