import 'package:supabase_flutter/supabase_flutter.dart';

class SupabaseConfig {
  static const url = String.fromEnvironment(
    'OPENNUTRI_APP_SUPABASE_URL',
    defaultValue: 'https://xktsqscshecpnfvlqtoy.supabase.co',
  );
  static const publishableKey = String.fromEnvironment(
    'OPENNUTRI_APP_SUPABASE_PUBLISHABLE_KEY',
  );

  static bool get isConfigured =>
      url.startsWith('https://') && publishableKey.isNotEmpty;

  static Future<void> initialize() async {
    if (!isConfigured) return;
    await Supabase.initialize(url: url, anonKey: publishableKey);
  }
}
