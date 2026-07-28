import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/diary.dart';

class LocalStore {
  static const _entriesKey = 'opennutri.diary.entries.v1';
  static const _targetsKey = 'opennutri.targets.v1';
  static const _voiceDisclosureKey = 'opennutri.voice.disclosure.v1';
  static const _voiceFeedbackConsentKey = 'opennutri.voice.feedback_consent.v1';
  static const _voiceFastLoggingKey = 'opennutri.voice.fast_logging.v1';

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
    await preferences.setString(
      _entriesKey,
      jsonEncode(entries.map((entry) => entry.toJson()).toList()),
    );
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
    // Fast logging is the beta default. A person can opt into review-everything
    // from Settings without losing the bounded resolver safeguards.
    return preferences.getBool(_voiceFastLoggingKey) ?? true;
  }

  Future<void> saveVoiceFastLogging(bool enabled) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setBool(_voiceFastLoggingKey, enabled);
  }
}
