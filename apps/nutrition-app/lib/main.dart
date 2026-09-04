import 'dart:async';

import 'package:flutter/material.dart';

import 'app.dart';
import 'services/local_store.dart';
import 'services/supabase_config.dart';
import 'state/app_controller.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  unawaited(SupabaseConfig.initialize().catchError((Object _) {}));
  final controller = AppController(LocalStore());
  await controller.initialize();
  runApp(OpenNutriApp(controller: controller));
}
