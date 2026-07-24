import 'package:flutter/material.dart';

import '../services/core_api_client.dart';
import '../services/android_widget_bridge.dart';
import '../services/voice_api_client.dart';
import '../state/app_controller.dart';
import 'nutrients_screen.dart';
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
  bool _openingVoice = false;

  @override
  void initState() {
    super.initState();
    _voiceApiClient = widget.voiceApiClient ?? VoiceApiClient();
    AndroidWidgetBridge.listenForVoiceActions(
      () => _openVoice(autoStart: true),
    );
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (await AndroidWidgetBridge.consumePendingVoiceAction()) {
        await _openVoice(autoStart: true);
      }
    });
  }

  @override
  void dispose() {
    AndroidWidgetBridge.stopListening();
    super.dispose();
  }

  Future<void> _openVoice({bool autoStart = false}) async {
    if (!mounted || _openingVoice) return;
    _openingVoice = true;
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (context) => VoiceLogScreen(
          controller: widget.controller,
          coreApiClient: widget.apiClient,
          voiceApiClient: _voiceApiClient,
          autoStart: autoStart,
        ),
      ),
    );
    _openingVoice = false;
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
          ),
          NutrientsScreen(controller: widget.controller),
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
