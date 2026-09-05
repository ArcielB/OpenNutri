import 'package:flutter/services.dart';

class AndroidWidgetBridge {
  static const MethodChannel _channel = MethodChannel(
    'org.opennutri.app/voice_widget',
  );

  static Future<bool> consumePendingVoiceAction() async {
    try {
      return await _channel.invokeMethod<bool>('consumePendingVoiceAction') ??
          false;
    } on MissingPluginException {
      return false;
    }
  }

  static void listenForVoiceActions(Future<void> Function() onVoiceAction) {
    _channel.setMethodCallHandler((call) async {
      if (call.method == 'voiceLogRequested') {
        await consumePendingVoiceAction();
        await onVoiceAction();
      }
    });
  }

  static void stopListening() {
    _channel.setMethodCallHandler(null);
  }

  static Future<bool> requestPinWidget() async {
    try {
      return await _channel.invokeMethod<bool>('requestPinVoiceWidget') ??
          false;
    } on MissingPluginException {
      return false;
    } on PlatformException {
      // The widget remains available in the launcher's manual widget picker.
      return false;
    }
  }

  static Future<void> finishQuickCapture({
    required int foodCount,
    required bool needsReview,
  }) async {
    try {
      await _channel.invokeMethod<void>('finishQuickCapture', {
        'foodCount': foodCount,
        'needsReview': needsReview,
      });
    } on MissingPluginException {
      // Widget-only Android behavior; Flutter tests and other platforms no-op.
    }
  }
}
