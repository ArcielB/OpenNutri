import 'package:flutter/material.dart';

import 'screens/home_shell.dart';
import 'services/core_api_client.dart';
import 'state/app_controller.dart';
import 'theme/app_theme.dart';

class OpenNutriApp extends StatelessWidget {
  const OpenNutriApp({super.key, required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'OpenNutri',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: ThemeMode.system,
      home: HomeShell(controller: controller, apiClient: CoreApiClient()),
    );
  }
}
