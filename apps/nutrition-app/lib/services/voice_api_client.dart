import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../models/voice_resolution.dart';
import 'supabase_config.dart';

class VoiceApiClient {
  VoiceApiClient({http.Client? client}) : _client = client ?? http.Client();

  static const baseUrl = String.fromEnvironment(
    'OPENNUTRI_VOICE_API_BASE_URL',
    defaultValue: 'https://opennutri-voice-beta.vercel.app',
  );

  final http.Client _client;

  bool get isConfigured => baseUrl.isNotEmpty && SupabaseConfig.isConfigured;

  /// Starts anonymous auth and the resolver's cold function while recording begins.
  /// Failures stay non-blocking: the actual resolution path retains its normal
  /// manual-search fallback.
  Future<void> warmUp() async {
    if (!isConfigured) return;
    try {
      await Future.wait<void>([
        _accessToken(),
        _client
            .get(Uri.parse('$baseUrl/health'))
            .timeout(const Duration(seconds: 8))
            .then<void>((_) {}),
      ]);
    } catch (_) {
      // Recording must remain available when auth or the resolver is offline.
    }
  }

  Future<String> _accessToken() async {
    if (!SupabaseConfig.isConfigured) {
      throw const VoiceApiException('Voice sign-in is not configured');
    }
    final auth = Supabase.instance.client.auth;
    var session = auth.currentSession;
    if (session == null) {
      final response = await auth.signInAnonymously();
      session = response.session;
    }
    final token = session?.accessToken;
    if (token == null || token.isEmpty) {
      throw const VoiceApiException('Could not start an anonymous session');
    }
    return token;
  }

  Future<VoiceResolution> resolveVoice({
    required String wavPath,
    required String languageHint,
    required DateTime localTimestamp,
    required String timezone,
  }) async {
    if (!isConfigured) {
      throw const VoiceApiException('Voice logging is not configured');
    }
    final file = File(wavPath);
    final bytes = await file.length();
    if (bytes > 1024 * 1024) {
      throw const VoiceApiException('Recording is larger than 1 MB');
    }
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/v1/voice/resolve'),
    );
    request.headers['authorization'] = 'Bearer ${await _accessToken()}';
    request.fields.addAll({
      'language_hint': languageHint,
      'local_timestamp': localTimestamp.toIso8601String(),
      'timezone': timezone,
    });
    request.files.add(
      await http.MultipartFile.fromPath(
        'audio',
        wavPath,
        filename: 'meal.wav',
        contentType: MediaType('audio', 'wav'),
      ),
    );
    final streamed = await _client
        .send(request)
        .timeout(const Duration(seconds: 45));
    final response = await http.Response.fromStream(streamed);
    return VoiceResolution.fromJson(_decode(response));
  }

  Future<VoiceResolution> resolveText(
    String query, {
    DateTime? localTimestamp,
    String timezone = 'UTC',
  }) async {
    if (!isConfigured) {
      throw const VoiceApiException('Semantic search is not configured');
    }
    final response = await _client
        .post(
          Uri.parse('$baseUrl/v1/foods/resolve-text'),
          headers: {
            'authorization': 'Bearer ${await _accessToken()}',
            'content-type': 'application/json',
          },
          body: jsonEncode({
            'query': query,
            'local_timestamp': (localTimestamp ?? DateTime.now())
                .toIso8601String(),
            'timezone': timezone,
          }),
        )
        .timeout(const Duration(seconds: 30));
    return VoiceResolution.fromJson(_decode(response));
  }

  Future<void> sendFeedback({
    required ResolutionMetadata metadata,
    required List<VoiceFeedbackItem> items,
  }) async {
    if (!isConfigured || items.isEmpty) return;
    final response = await _client
        .post(
          Uri.parse('$baseUrl/v1/voice/feedback'),
          headers: {
            'authorization': 'Bearer ${await _accessToken()}',
            'content-type': 'application/json',
          },
          body: jsonEncode({
            'request_id': metadata.requestId,
            'core_version': metadata.coreVersion,
            'index_version': metadata.indexVersion,
            'model_version': metadata.selectorModel ?? 'unknown',
            'items': items.map((value) => value.toJson()).toList(),
          }),
        )
        .timeout(const Duration(seconds: 15));
    _decode(response);
  }

  Future<void> deleteFeedback() async {
    if (!isConfigured) return;
    final response = await _client
        .delete(
          Uri.parse('$baseUrl/v1/voice/feedback'),
          headers: {'authorization': 'Bearer ${await _accessToken()}'},
        )
        .timeout(const Duration(seconds: 15));
    _decode(response);
  }

  Map<String, dynamic> _decode(http.Response response) {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw VoiceApiException('Voice service returned ${response.statusCode}');
    }
    try {
      return jsonDecode(response.body) as Map<String, dynamic>;
    } on FormatException catch (error) {
      throw VoiceApiException('Voice service returned invalid data', error);
    }
  }
}

class VoiceApiException implements Exception {
  const VoiceApiException(this.message, [this.cause]);

  final String message;
  final Object? cause;

  @override
  String toString() => message;
}
