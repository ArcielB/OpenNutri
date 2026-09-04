import 'package:flutter/foundation.dart';

import '../models/diary.dart';
import '../services/local_store.dart';

class AppController extends ChangeNotifier {
  AppController(this._store);

  final LocalStore _store;
  List<DiaryEntry> _entries = const [];
  DateTime _selectedDate = DateTime.now();
  NutritionTargets _targets = const NutritionTargets();
  bool _voiceDisclosureAccepted = false;
  bool _voiceFeedbackConsent = false;
  bool _voiceFastLogging = true;

  DateTime get selectedDate => _selectedDate;
  NutritionTargets get targets => _targets;
  List<DiaryEntry> get entries => List.unmodifiable(_entries);
  bool get voiceDisclosureAccepted => _voiceDisclosureAccepted;
  bool get voiceFeedbackConsent => _voiceFeedbackConsent;
  bool get voiceFastLogging => _voiceFastLogging;

  Future<void> initialize() async {
    _entries = await _store.loadEntries();
    _targets = await _store.loadTargets();
    _voiceDisclosureAccepted = await _store.loadVoiceDisclosureAccepted();
    _voiceFeedbackConsent = await _store.loadVoiceFeedbackConsent();
    _voiceFastLogging = await _store.loadVoiceFastLogging();
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
    _entries = [..._entries, ...entries];
    notifyListeners();
    await _store.saveEntries(_entries);
  }

  Future<DiaryEntry> repeatEntry(DiaryEntry source, {MealType? meal}) async {
    final entry = source.copyFor(date: _selectedDate, meal: meal);
    await addEntry(entry);
    return entry;
  }

  Future<void> removeEntry(String entryId) async {
    await removeEntries([entryId]);
  }

  Future<void> removeEntries(Iterable<String> entryIds) async {
    final ids = entryIds.toSet();
    if (ids.isEmpty) return;
    _entries = _entries.where((entry) => !ids.contains(entry.id)).toList();
    notifyListeners();
    await _store.saveEntries(_entries);
  }

  Future<void> clearEntries() async {
    _entries = const [];
    notifyListeners();
    await _store.saveEntries(_entries);
  }

  Future<void> updateTargets(NutritionTargets targets) async {
    _targets = targets;
    notifyListeners();
    await _store.saveTargets(targets);
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
}
