import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

enum VoiceRecorderState { idle, recording, stopped, permissionDenied, error }

class SilenceStopDetector {
  SilenceStopDetector({
    this.thresholdDbfs = -40,
    this.speechOpportunity = const Duration(milliseconds: 800),
    this.trailingSilence = const Duration(milliseconds: 1200),
  });

  final double thresholdDbfs;
  final Duration speechOpportunity;
  final Duration trailingSilence;
  Duration? _silenceStartedAt;

  bool observe({required double dbfs, required Duration elapsed}) {
    if (elapsed < speechOpportunity) return false;
    if (dbfs > thresholdDbfs) {
      _silenceStartedAt = null;
      return false;
    }
    _silenceStartedAt ??= elapsed;
    return elapsed - _silenceStartedAt! >= trailingSilence;
  }

  void reset() => _silenceStartedAt = null;
}

abstract class VoiceRecorderSession {
  VoiceRecorderState get state;
  String? get errorMessage;
  String? get currentPath;
  Future<bool> start();
  Future<String?> stop();
  Future<void> cancel();
  Future<void> deleteTemporaryFile([String? path]);
  void addListener(VoidCallback listener);
  void removeListener(VoidCallback listener);
  void dispose();
}

class OpenNutriVoiceRecorder extends ChangeNotifier
    implements VoiceRecorderSession {
  OpenNutriVoiceRecorder({AudioRecorder? recorder})
    : _recorder = recorder ?? AudioRecorder();

  static const silenceThresholdDbfs = -40.0;
  static const speechOpportunity = Duration(milliseconds: 800);
  static const trailingSilence = Duration(milliseconds: 1200);
  static const maximumDuration = Duration(seconds: 20);

  final AudioRecorder _recorder;
  StreamSubscription<Amplitude>? _amplitudeSubscription;
  Timer? _hardStopTimer;
  Stopwatch? _elapsed;
  final SilenceStopDetector _silenceDetector = SilenceStopDetector(
    thresholdDbfs: silenceThresholdDbfs,
    speechOpportunity: speechOpportunity,
    trailingSilence: trailingSilence,
  );
  bool _stopping = false;
  VoiceRecorderState _state = VoiceRecorderState.idle;
  String? _errorMessage;
  String? _currentPath;

  @override
  VoiceRecorderState get state => _state;
  @override
  String? get errorMessage => _errorMessage;
  @override
  String? get currentPath => _currentPath;

  @override
  Future<bool> start() async {
    if (_state == VoiceRecorderState.recording) return true;
    _errorMessage = null;
    try {
      if (!await _recorder.hasPermission()) {
        _state = VoiceRecorderState.permissionDenied;
        notifyListeners();
        return false;
      }
      final directory = await getTemporaryDirectory();
      _currentPath =
          '${directory.path}/opennutri-voice-'
          '${DateTime.now().microsecondsSinceEpoch}.wav';
      await _recorder.start(
        const RecordConfig(
          encoder: AudioEncoder.wav,
          sampleRate: 16000,
          numChannels: 1,
          bitRate: 256000,
        ),
        path: _currentPath!,
      );
      _elapsed = Stopwatch()..start();
      _state = VoiceRecorderState.recording;
      notifyListeners();
      _amplitudeSubscription = _recorder
          .onAmplitudeChanged(const Duration(milliseconds: 100))
          .listen(_handleAmplitude);
      _hardStopTimer = Timer(maximumDuration, stop);
      return true;
    } catch (error) {
      _errorMessage = error.toString();
      _state = VoiceRecorderState.error;
      await deleteTemporaryFile();
      notifyListeners();
      return false;
    }
  }

  void _handleAmplitude(Amplitude amplitude) {
    final elapsed = _elapsed?.elapsed ?? Duration.zero;
    if (_silenceDetector.observe(dbfs: amplitude.current, elapsed: elapsed)) {
      unawaited(stop());
    }
  }

  @override
  Future<String?> stop() async {
    if (_state != VoiceRecorderState.recording || _stopping) {
      return _currentPath;
    }
    _stopping = true;
    await _cancelTimers();
    try {
      final stoppedPath = await _recorder.stop();
      _currentPath = stoppedPath ?? _currentPath;
      _state = VoiceRecorderState.stopped;
      notifyListeners();
      return _currentPath;
    } catch (error) {
      _errorMessage = error.toString();
      _state = VoiceRecorderState.error;
      await deleteTemporaryFile();
      notifyListeners();
      return null;
    } finally {
      _stopping = false;
    }
  }

  @override
  Future<void> cancel() async {
    await _cancelTimers();
    if (_state == VoiceRecorderState.recording) {
      try {
        await _recorder.cancel();
      } catch (_) {
        // Temporary-file cleanup still runs when a platform recorder fails.
      }
    }
    await deleteTemporaryFile();
    _state = VoiceRecorderState.idle;
    notifyListeners();
  }

  Future<void> _cancelTimers() async {
    _hardStopTimer?.cancel();
    _hardStopTimer = null;
    _elapsed?.stop();
    _elapsed = null;
    _silenceDetector.reset();
    await _amplitudeSubscription?.cancel();
    _amplitudeSubscription = null;
  }

  @override
  Future<void> deleteTemporaryFile([String? path]) async {
    final target = path ?? _currentPath;
    if (target == null) return;
    final file = File(target);
    if (await file.exists()) {
      await file.delete();
    }
    if (target == _currentPath) _currentPath = null;
  }

  @override
  void dispose() {
    _hardStopTimer?.cancel();
    unawaited(_amplitudeSubscription?.cancel());
    unawaited(_recorder.dispose());
    super.dispose();
  }
}
