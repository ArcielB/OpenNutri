import 'package:flutter/foundation.dart';

import '../models/diary.dart';
import '../models/personalization.dart';
import '../services/local_store.dart';

class AppController extends ChangeNotifier {
  AppController(this._store);

  final LocalStore _store;
  List<DiaryEntry> _entries = const [];
  List<DiaryEntry> _persistedEntries = const [];
  DateTime _selectedDate = DateTime.now();
  NutritionTargets _targets = const NutritionTargets();
  bool _voiceDisclosureAccepted = false;
  bool _voiceFeedbackConsent = false;
  bool _voiceFastLogging = true;
  UserNutritionProfile _profile = const UserNutritionProfile();
  DailyCoachBrief? _dailyCoachBrief;
  Future<void> _entryWriteTail = Future<void>.value();
  int _coachContextRevision = 0;

  DateTime get selectedDate => _selectedDate;
  NutritionTargets get targets => _targets;
  List<DiaryEntry> get entries => List.unmodifiable(_entries);
  bool get voiceDisclosureAccepted => _voiceDisclosureAccepted;
  bool get voiceFeedbackConsent => _voiceFeedbackConsent;
  bool get voiceFastLogging => _voiceFastLogging;
  UserNutritionProfile get profile => _profile;
  int get coachContextRevision => _coachContextRevision;
  DailyCoachBrief? get dailyCoachBrief =>
      _profile.coachEnabled &&
          _dailyCoachBrief?.dateKey == dateKeyFor(_selectedDate)
      ? _dailyCoachBrief
      : null;

  Future<void> initialize() async {
    _entries = await _store.loadEntries();
    _persistedEntries = _entries;
    _targets = await _store.loadTargets();
    _voiceDisclosureAccepted = await _store.loadVoiceDisclosureAccepted();
    _voiceFeedbackConsent = await _store.loadVoiceFeedbackConsent();
    _voiceFastLogging = await _store.loadVoiceFastLogging();
    _profile = await _store.loadProfile();
    _dailyCoachBrief = await _store.loadDailyCoachBrief();
  }

  List<DiaryEntry> entriesForSelectedDate() {
    final key = dateKeyFor(_selectedDate);
    return _entries
        .where((entry) => entry.dateKey == key)
        .toList(growable: false);
  }

  List<DiaryEntry> entriesForMeal(MealType meal) {
    return entriesForSelectedDate()
        .where((entry) => entry.meal == meal)
        .toList(growable: false);
  }

  DailyTotals get dailyTotals => DailyTotals(entriesForSelectedDate());

  List<DiaryEntry> recentEntries({int limit = 6}) {
    final seen = <String>{};
    final recent = <DiaryEntry>[];
    for (final entry in _entries.reversed) {
      if (!seen.add(entry.foodId)) continue;
      recent.add(entry);
      if (recent.length == limit) break;
    }
    return recent;
  }

  void selectDate(DateTime date) {
    _selectedDate = DateTime(date.year, date.month, date.day);
    _coachContextRevision++;
    notifyListeners();
  }

  void shiftDate(int days) {
    selectDate(_selectedDate.add(Duration(days: days)));
  }

  Future<void> addEntry(DiaryEntry entry) async {
    await addEntries([entry]);
  }

  Future<void> addEntries(List<DiaryEntry> entries) async {
    if (entries.isEmpty) return;
    final ids = _entries.map((entry) => entry.id).toSet();
    final additions = entries.where((entry) => ids.add(entry.id)).toList();
    if (additions.isEmpty) return;
    await _persistEntries([..._entries, ...additions]);
  }

  Future<DiaryEntry> repeatEntry(DiaryEntry source, {MealType? meal}) async {
    final entry = source.copyFor(date: _selectedDate, meal: meal);
    await addEntry(entry);
    return entry;
  }

  Future<void> removeEntry(String entryId) async {
    await removeEntries([entryId]);
  }

  Future<void> updateEntry(DiaryEntry updated) async {
    await updateEntries([updated]);
  }

  /// An edit replaces saved snapshots in one write. Opening/cancelling an editor
  /// never deletes them, and stale editors cannot resurrect removed entries.
  Future<void> updateEntries(List<DiaryEntry> updates) async {
    final byId = {for (final entry in updates) entry.id: entry};
    if (!_entries.any((entry) => byId.containsKey(entry.id))) return;
    await _persistEntries([
      for (final entry in _entries) byId[entry.id] ?? entry,
    ]);
  }

  Future<void> removeEntries(Iterable<String> entryIds) async {
    final ids = entryIds.toSet();
    if (ids.isEmpty) return;
    await _persistEntries(
      _entries.where((entry) => !ids.contains(entry.id)).toList(),
    );
  }

  Future<void> clearEntries() async {
    await _persistEntries(const []);
  }

  Future<void> _persistEntries(List<DiaryEntry> entries) async {
    _entries = entries;
    _coachContextRevision++;
    notifyListeners();
    // Keep optimistic rendering, but serialize disk snapshots so a slow earlier
    // save cannot overwrite a later correction or Undo.
    final write = _entryWriteTail.then((_) async {
      await _store.saveEntries(entries);
      _persistedEntries = entries;
    });
    _entryWriteTail = write.catchError((Object _) {});
    try {
      await write;
    } catch (_) {
      if (identical(_entries, entries)) {
        _entries = _persistedEntries;
        _coachContextRevision++;
        notifyListeners();
      }
      rethrow;
    }
  }

  Future<void> updateTargets(NutritionTargets targets) async {
    final values = [
      targets.calories,
      targets.protein,
      targets.carbs,
      targets.fat,
    ];
    if (values.any((value) => !value.isFinite || value <= 0)) {
      throw ArgumentError('Targets must be finite and greater than zero');
    }
    _targets = targets;
    _dailyCoachBrief = null;
    _coachContextRevision++;
    notifyListeners();
    await Future.wait([
      _store.saveTargets(targets),
      _store.clearDailyCoachBrief(),
    ]);
  }

  Future<void> acceptVoiceDisclosure({required bool feedbackConsent}) async {
    _voiceDisclosureAccepted = true;
    _voiceFeedbackConsent = feedbackConsent;
    notifyListeners();
    await Future.wait([
      _store.saveVoiceDisclosureAccepted(true),
      _store.saveVoiceFeedbackConsent(feedbackConsent),
    ]);
  }

  Future<void> updateVoiceFeedbackConsent(bool enabled) async {
    _voiceFeedbackConsent = enabled;
    notifyListeners();
    await _store.saveVoiceFeedbackConsent(enabled);
  }

  Future<void> updateVoiceFastLogging(bool enabled) async {
    _voiceFastLogging = enabled;
    notifyListeners();
    await _store.saveVoiceFastLogging(enabled);
  }

  Future<void> updateProfile(UserNutritionProfile profile) async {
    _profile = profile;
    _dailyCoachBrief = null;
    _coachContextRevision++;
    notifyListeners();
    await Future.wait([
      _store.saveProfile(profile),
      _store.clearDailyCoachBrief(),
    ]);
  }

  Future<void> enableCoach() async {
    await updateProfile(_profile.copyWith(coachEnabled: true));
  }

  Future<void> updateGoal(NutritionGoal goal) async {
    _profile = _profile.copyWith(goal: goal);
    _targets = _profile.diet.targetsForCalories(_targets.calories, goal: goal);
    _dailyCoachBrief = null;
    _coachContextRevision++;
    notifyListeners();
    await Future.wait([
      _store.saveProfile(_profile),
      _store.saveTargets(_targets),
      _store.clearDailyCoachBrief(),
    ]);
  }

  Future<void> applyDiet(DietPreset diet, {String? notes}) async {
    _profile = _profile.copyWith(
      dietId: diet.id,
      dietNotes: notes ?? _profile.dietNotes,
    );
    _targets = diet.targetsForCalories(_targets.calories, goal: _profile.goal);
    _dailyCoachBrief = null;
    _coachContextRevision++;
    notifyListeners();
    await Future.wait([
      _store.saveProfile(_profile),
      _store.saveTargets(_targets),
      _store.clearDailyCoachBrief(),
    ]);
  }

  Future<void> addCoachMemories(Iterable<CoachMemory> updates) async {
    final merged = <CoachMemory>[..._profile.memories];
    for (final update in updates) {
      final normalized = update.fact.trim().toLowerCase();
      if (normalized.isEmpty ||
          merged.any((item) => item.fact.trim().toLowerCase() == normalized)) {
        continue;
      }
      merged.add(update);
    }
    if (merged.length == _profile.memories.length) return;
    await updateProfile(_profile.copyWith(memories: merged.take(30).toList()));
  }

  Future<void> removeCoachMemory(CoachMemory memory) async {
    await updateProfile(
      _profile.copyWith(
        memories: _profile.memories
            .where(
              (item) =>
                  item.fact != memory.fact || item.category != memory.category,
            )
            .toList(growable: false),
      ),
    );
  }

  Future<void> saveDailyCoachBrief(DailyCoachBrief brief) async {
    _dailyCoachBrief = brief;
    notifyListeners();
    await _store.saveDailyCoachBrief(brief);
  }
}
