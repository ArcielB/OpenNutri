import 'package:flutter/material.dart';

import 'app.dart';
import 'services/local_store.dart';
import 'state/app_controller.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final controller = AppController(LocalStore());
  await controller.initialize();
  runApp(OpenNutriApp(controller: controller));
}
