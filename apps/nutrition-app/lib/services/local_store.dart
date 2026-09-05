import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/diary.dart';
import '../models/personalization.dart';

class LocalStore {
  static const _entriesKey = 'opennutri.diary.entries.v1';
  static const _targetsKey = 'opennutri.targets.v1';
  static const _voiceDisclosureKey = 'opennutri.voice.disclosure.v1';
  static const _voiceFeedbackConsentKey = 'opennutri.voice.feedback_consent.v1';
  static const _voiceFastLoggingKey = 'opennutri.voice.fast_logging.v1';
  static const _profileKey = 'opennutri.profile.v1';
  static const _dailyCoachKey = 'opennutri.coach.daily.v1';

  Future<List<DiaryEntry>> loadEntries() async {
    final preferences = await SharedPreferences.getInstance();
    final raw = preferences.getString(_entriesKey);
    if (raw == null) return const [];
    final values = jsonDecode(raw) as List<dynamic>;
    return values
        .map((value) => DiaryEntry.fromJson(value as Map<String, dynamic>))
        .toList();
  }

  Future<void> saveEntries(List<DiaryEntry> entries) async {
    final preferences = await SharedPreferences.getInstance();
    final saved = await preferences.setString(
      _entriesKey,
      jsonEncode(entries.map((entry) => entry.toJson()).toList()),
    );
    if (!saved) throw StateError('Could not persist diary');
  }

  Future<NutritionTargets> loadTargets() async {
    final preferences = await SharedPreferences.getInstance();
    final raw = preferences.getString(_targetsKey);
    if (raw == null) return const NutritionTargets();
    return NutritionTargets.fromJson(jsonDecode(raw) as Map<String, dynamic>);
  }

  Future<void> saveTargets(NutritionTargets targets) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(_targetsKey, jsonEncode(targets.toJson()));
  }

  Future<bool> loadVoiceDisclosureAccepted() async {
    final preferences = await SharedPreferences.getInstance();
    return preferences.getBool(_voiceDisclosureKey) ?? false;
  }

  Future<void> saveVoiceDisclosureAccepted(bool accepted) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setBool(_voiceDisclosureKey, accepted);
  }

  Future<bool> loadVoiceFeedbackConsent() async {
    final preferences = await SharedPreferences.getInstance();
    return preferences.getBool(_voiceFeedbackConsentKey) ?? false;
  }

  Future<void> saveVoiceFeedbackConsent(bool enabled) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setBool(_voiceFeedbackConsentKey, enabled);
  }

  Future<bool> loadVoiceFastLogging() async {
    final preferences = await SharedPreferences.getInstance();
    // Legacy stored preference, retained for migration compatibility only.
    // Since 1.1, usable voice batches always log and this value is not a UI gate.
    return preferences.getBool(_voiceFastLoggingKey) ?? true;
  }

  Future<void> saveVoiceFastLogging(bool enabled) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setBool(_voiceFastLoggingKey, enabled);
  }

  Future<UserNutritionProfile> loadProfile() async {
    final preferences = await SharedPreferences.getInstance();
    final raw = preferences.getString(_profileKey);
    if (raw == null) return const UserNutritionProfile();
    return UserNutritionProfile.fromJson(
      jsonDecode(raw) as Map<String, dynamic>,
    );
  }

  Future<void> saveProfile(UserNutritionProfile profile) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(_profileKey, jsonEncode(profile.toJson()));
  }

  Future<DailyCoachBrief?> loadDailyCoachBrief() async {
    final preferences = await SharedPreferences.getInstance();
    final raw = preferences.getString(_dailyCoachKey);
    if (raw == null) return null;
    return DailyCoachBrief.fromJson(jsonDecode(raw) as Map<String, dynamic>);
  }

  Future<void> saveDailyCoachBrief(DailyCoachBrief brief) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(_dailyCoachKey, jsonEncode(brief.toJson()));
  }

  Future<void> clearDailyCoachBrief() async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.remove(_dailyCoachKey);
  }
}
