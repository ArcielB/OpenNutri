import 'dart:async';

import 'package:flutter/material.dart';

import '../models/personalization.dart';
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

class _HomeShellState extends State<HomeShell> {
  int _index = 0;
  late final VoiceApiClient _voiceApiClient;
  late final CoachService _coachService;
  bool _openingVoice = false;
  bool _dailyCoachLoading = false;

  @override
  void initState() {
    super.initState();
    _voiceApiClient = widget.voiceApiClient ?? VoiceApiClient();
    _coachService = CoachService(_voiceApiClient);
    unawaited(_voiceApiClient.warmUp());
    AndroidWidgetBridge.listenForVoiceActions(
      () => _openVoice(autoStart: true, quickCapture: true),
    );
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (await AndroidWidgetBridge.consumePendingVoiceAction()) {
        await _openVoice(autoStart: true, quickCapture: true);
      }
      await _refreshDailyCoach();
    });
  }

  @override
  void dispose() {
    AndroidWidgetBridge.stopListening();
    super.dispose();
  }

  Future<void> _openVoice({
    bool autoStart = false,
    bool quickCapture = false,
  }) async {
    if (!mounted || _openingVoice) return;
    _openingVoice = true;
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
  }

  Future<void> _refreshDailyCoach({bool force = false}) async {
    if (!mounted ||
        !widget.controller.profile.coachEnabled ||
        _dailyCoachLoading) {
      return;
    }
    final now = DateTime.now();
    final key =
        '${now.year.toString().padLeft(4, '0')}-'
        '${now.month.toString().padLeft(2, '0')}-'
        '${now.day.toString().padLeft(2, '0')}';
    if (!force && widget.controller.dailyCoachBrief?.dateKey == key) return;
    setState(() => _dailyCoachLoading = true);
    try {
      final reply = await _coachService.respond(
        controller: widget.controller,
        mode: CoachMode.daily,
      );
      await widget.controller.saveDailyCoachBrief(
        DailyCoachBrief(dateKey: key, reply: reply),
      );
    } catch (_) {
      await widget.controller.saveDailyCoachBrief(
        _coachService.localDailyFallback(widget.controller),
      );
    } finally {
      if (mounted) setState(() => _dailyCoachLoading = false);
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
            onOpenCoach: () => setState(() => _index = 2),
          ),
          NutrientsScreen(controller: widget.controller),
          CoachScreen(
            controller: widget.controller,
            coachService: _coachService,
            refreshDaily: _refreshDailyCoach,
            dailyLoading: _dailyCoachLoading,
          ),
          OracleScreen(
            controller: widget.controller,
            coachService: _coachService,
            apiClient: widget.apiClient,
            voiceApiClient: _voiceApiClient,
            onOpenCoach: () => setState(() => _index = 2),
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
            onDestinationSelected: (value) => setState(() => _index = value),
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
