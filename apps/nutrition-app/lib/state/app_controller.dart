import 'package:flutter/foundation.dart';

import '../models/diary.dart';
import '../services/local_store.dart';

class AppController extends ChangeNotifier {
  AppController(this._store);

  final LocalStore _store;
  List<DiaryEntry> _entries = const [];
  DateTime _selectedDate = DateTime.now();
  NutritionTargets _targets = const NutritionTargets();

  DateTime get selectedDate => _selectedDate;
  NutritionTargets get targets => _targets;
  List<DiaryEntry> get entries => List.unmodifiable(_entries);

  Future<void> initialize() async {
    _entries = await _store.loadEntries();
    _targets = await _store.loadTargets();
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

  void selectDate(DateTime date) {
    _selectedDate = DateTime(date.year, date.month, date.day);
    notifyListeners();
  }

  void shiftDate(int days) {
    selectDate(_selectedDate.add(Duration(days: days)));
  }

  Future<void> addEntry(DiaryEntry entry) async {
    _entries = [..._entries, entry];
    notifyListeners();
    await _store.saveEntries(_entries);
  }

  Future<void> removeEntry(String entryId) async {
    _entries = _entries.where((entry) => entry.id != entryId).toList();
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
}
