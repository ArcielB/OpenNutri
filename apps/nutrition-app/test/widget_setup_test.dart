import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:opennutri_app/screens/settings_screen.dart';
import 'package:opennutri_app/services/core_api_client.dart';
import 'package:opennutri_app/services/local_store.dart';
import 'package:opennutri_app/services/voice_api_client.dart';
import 'package:opennutri_app/state/app_controller.dart';

void main() {
  const channel = MethodChannel('org.opennutri.app/voice_widget');
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets(
    'offscreen health failure is handled and remains visible on scroll',
    (tester) async {
      SharedPreferences.setMockInitialValues({});
      final controller = AppController(LocalStore());
      await controller.initialize();
      await tester.pumpWidget(
        MaterialApp(
          home: SettingsScreen(
            controller: controller,
            apiClient: OfflineCore(),
            voiceApiClient: VoiceApiClient(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      await tester.scrollUntilVisible(
        find.byTooltip('Check connection'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      expect(find.text('Unavailable'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  for (final outcome in ['requested', 'unsupported', 'platform_error']) {
    testWidgets(
      'widget setup explains $outcome without claiming it was placed',
      (tester) async {
        SharedPreferences.setMockInitialValues({});
        var calls = 0;
        final messenger =
            TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
        messenger.setMockMethodCallHandler(channel, (call) async {
          expect(call.method, 'requestPinVoiceWidget');
          calls++;
          if (outcome == 'platform_error') {
            throw PlatformException(code: 'launcher_unavailable');
          }
          return outcome == 'requested';
        });
        addTearDown(() => messenger.setMockMethodCallHandler(channel, null));
        final controller = AppController(LocalStore());
        await controller.initialize();
        await tester.pumpWidget(
          MaterialApp(
            home: SettingsScreen(
              controller: controller,
              apiClient: FixtureCore(),
              voiceApiClient: VoiceApiClient(),
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(
          find.text('Add microphone widget').hitTestable(),
          findsOneWidget,
        );
        await tester.tap(find.text('Add microphone widget'));
        await tester.pumpAndSettle();
        expect(calls, 1);
        if (outcome == 'requested') {
          expect(
            find.textContaining('Confirm Add in your launcher'),
            findsOneWidget,
          );
        } else {
          expect(find.text('Add from your home screen'), findsOneWidget);
          expect(
            find.textContaining('Touch and hold an empty space'),
            findsOneWidget,
          );
        }
        expect(tester.takeException(), isNull);
      },
    );
  }
}

class FixtureCore extends CoreApiClient {
  @override
  Future<Map<String, dynamic>> health() async => {'status': 'ok'};
}

class OfflineCore extends CoreApiClient {
  @override
  Future<Map<String, dynamic>> health() async =>
      throw StateError('fixture offline');
}
