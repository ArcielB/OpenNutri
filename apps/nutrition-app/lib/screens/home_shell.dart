import 'dart:async';

import 'package:flutter/material.dart';

import '../models/personalization.dart';
import '../models/diary.dart';
import '../services/coach_service.dart';
import '../services/core_api_client.dart';
import '../services/android_widget_bridge.dart';
import '../services/voice_api_client.dart';
import '../state/app_controller.dart';
import 'coach_screen.dart';
import 'nutrients_screen.dart';
import 'oracle_screen.dart';
import 'settings_screen.dart';
import 'today_screen.dart';
import 'voice_log_screen.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({
    super.key,
    required this.controller,
    required this.apiClient,
    this.voiceApiClient,
  });

  final AppController controller;
  final CoreApiClient apiClient;
  final VoiceApiClient? voiceApiClient;

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> with WidgetsBindingObserver {
  int _index = 0;
  late final VoiceApiClient _voiceApiClient;
  late final CoachService _coachService;
  bool _openingVoice = false;
  bool _dailyCoachLoading = false;
  late UserNutritionProfile _lastProfile;
  late NutritionTargets _lastTargets;
  String _calendarDay = dateKeyFor(DateTime.now());

  @override
  void initState() {
    super.initState();
    _voiceApiClient = widget.voiceApiClient ?? VoiceApiClient();
    _coachService = CoachService(_voiceApiClient);
    _lastProfile = widget.controller.profile;
    _lastTargets = widget.controller.targets;
    widget.controller.addListener(_onProfileChanged);
    WidgetsBinding.instance.addObserver(this);
    unawaited(_voiceApiClient.warmUp());
    AndroidWidgetBridge.listenForVoiceActions(
      () => _openVoice(autoStart: true, quickCapture: true),
    );
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (await AndroidWidgetBridge.consumePendingVoiceAction()) {
        await _openVoice(autoStart: true, quickCapture: true);
        return;
      }
      await _refreshDailyCoach();
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    widget.controller.removeListener(_onProfileChanged);
    AndroidWidgetBridge.stopListening();
    super.dispose();
  }

  void _onProfileChanged() {
    if (identical(_lastProfile, widget.controller.profile) &&
        identical(_lastTargets, widget.controller.targets)) {
      return;
    }
    _lastProfile = widget.controller.profile;
    _lastTargets = widget.controller.targets;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && !_openingVoice && (_index == 0 || _index == 2)) {
        unawaited(_refreshDailyCoach());
      }
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && !_openingVoice) {
      final today = dateKeyFor(DateTime.now());
      if (today != _calendarDay &&
          dateKeyFor(widget.controller.selectedDate) == _calendarDay) {
        widget.controller.selectDate(DateTime.now());
      }
      _calendarDay = today;
      unawaited(_refreshDailyCoach());
    }
  }

  void _selectTab(int value) {
    setState(() => _index = value);
    if (value == 0 || value == 2) unawaited(_refreshDailyCoach());
  }

  Future<void> _openVoice({
    bool autoStart = false,
    bool quickCapture = false,
  }) async {
    if (!mounted || _openingVoice) return;
    _openingVoice = true;
    if (quickCapture) widget.controller.selectDate(DateTime.now());
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (context) => VoiceLogScreen(
          controller: widget.controller,
          coreApiClient: widget.apiClient,
          voiceApiClient: _voiceApiClient,
          autoStart: autoStart,
          quickCapture: quickCapture,
        ),
      ),
    );
    _openingVoice = false;
    if (mounted && !quickCapture) unawaited(_refreshDailyCoach());
  }

  Future<void> _refreshDailyCoach({bool force = false}) async {
    if (!mounted ||
        !widget.controller.profile.coachEnabled ||
        _dailyCoachLoading) {
      return;
    }
    final key = dateKeyFor(widget.controller.selectedDate);
    final revision = widget.controller.coachContextRevision;
    if (!force && widget.controller.dailyCoachBrief?.dateKey == key) return;
    setState(() => _dailyCoachLoading = true);
    try {
      final reply = await _coachService.respond(
        controller: widget.controller,
        mode: CoachMode.daily,
      );
      if (!mounted ||
          !widget.controller.profile.coachEnabled ||
          revision != widget.controller.coachContextRevision) {
        return;
      }
      await widget.controller.saveDailyCoachBrief(
        DailyCoachBrief(dateKey: key, reply: reply),
      );
    } catch (_) {
      if (!mounted ||
          !widget.controller.profile.coachEnabled ||
          revision != widget.controller.coachContextRevision) {
        return;
      }
      await widget.controller.saveDailyCoachBrief(
        _coachService.localDailyFallback(widget.controller),
      );
    } finally {
      if (mounted) setState(() => _dailyCoachLoading = false);
      if (mounted &&
          !_openingVoice &&
          (_index == 0 || _index == 2) &&
          widget.controller.profile.coachEnabled &&
          widget.controller.dailyCoachBrief == null &&
          revision != widget.controller.coachContextRevision) {
        unawaited(_refreshDailyCoach());
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.controller,
      builder: (context, _) {
        final screens = [
          TodayScreen(
            controller: widget.controller,
            apiClient: widget.apiClient,
            voiceApiClient: _voiceApiClient,
            onVoice: _openVoice,
            dailyCoachBrief: widget.controller.dailyCoachBrief,
            coachEnabled: widget.controller.profile.coachEnabled,
            coachLoading: _dailyCoachLoading,
            onOpenCoach: () => _selectTab(2),
          ),
          NutrientsScreen(controller: widget.controller),
          CoachScreen(
            controller: widget.controller,
            coachService: _coachService,
            refreshDaily: _refreshDailyCoach,
            dailyLoading: _dailyCoachLoading,
            isActive: _index == 2,
          ),
          OracleScreen(
            controller: widget.controller,
            coachService: _coachService,
            apiClient: widget.apiClient,
            voiceApiClient: _voiceApiClient,
            onOpenCoach: () => _selectTab(2),
            isActive: _index == 3,
          ),
          SettingsScreen(
            controller: widget.controller,
            apiClient: widget.apiClient,
            voiceApiClient: _voiceApiClient,
          ),
        ];
        return Scaffold(
          body: IndexedStack(index: _index, children: screens),
          bottomNavigationBar: NavigationBar(
            selectedIndex: _index,
            onDestinationSelected: _selectTab,
            destinations: const [
              NavigationDestination(
                icon: Icon(Icons.today_outlined),
                selectedIcon: Icon(Icons.today),
                label: 'Today',
              ),
              NavigationDestination(
                icon: Icon(Icons.monitor_heart_outlined),
                selectedIcon: Icon(Icons.monitor_heart),
                label: 'Nutrients',
              ),
              NavigationDestination(
                icon: Icon(Icons.auto_awesome_outlined),
                selectedIcon: Icon(Icons.auto_awesome),
                label: 'Coach',
              ),
              NavigationDestination(
                icon: Icon(Icons.visibility_outlined),
                selectedIcon: Icon(Icons.visibility),
                label: 'Oracle',
              ),
              NavigationDestination(
                icon: Icon(Icons.tune_outlined),
                selectedIcon: Icon(Icons.tune),
                label: 'Settings',
              ),
            ],
          ),
        );
      },
    );
  }
}
