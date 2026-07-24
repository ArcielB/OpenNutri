import 'package:flutter/material.dart';

import '../services/core_api_client.dart';
import '../state/app_controller.dart';
import 'nutrients_screen.dart';
import 'settings_screen.dart';
import 'today_screen.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({
    super.key,
    required this.controller,
    required this.apiClient,
  });

  final AppController controller;
  final CoreApiClient apiClient;

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.controller,
      builder: (context, _) {
        final screens = [
          TodayScreen(
            controller: widget.controller,
            apiClient: widget.apiClient,
          ),
          NutrientsScreen(controller: widget.controller),
          SettingsScreen(
            controller: widget.controller,
            apiClient: widget.apiClient,
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
