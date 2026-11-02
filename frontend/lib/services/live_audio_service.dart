import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:record/record.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as websocket_status;

enum LiveAudioConnectionState {
  idle,
  requestingPermission,
  connecting,
  connected,
  reconnecting,
  stopped,
  error,
}

class LiveAudioStatus {
  const LiveAudioStatus(this.state, {this.message});

  final LiveAudioConnectionState state;
  final String? message;
}

class LiveAudioException implements Exception {
  const LiveAudioException(this.message);

  final String message;

  @override
  String toString() => message;
}

class LiveAudioService {
  LiveAudioService({required this.apiBaseUrl, AudioRecorder? recorder})
    : _recorder = recorder ?? AudioRecorder();

  static const int sampleRate = 16000;
  static const int channels = 1;
  static const int bytesPerSample = 2;
  static const int chunkDurationMilliseconds = 100;
  static const int chunkSizeBytes =
      sampleRate *
      channels *
      bytesPerSample *
      chunkDurationMilliseconds ~/
      1000;
  static const int maxReconnectAttempts = 5;

  final String apiBaseUrl;
  final AudioRecorder _recorder;
  final StreamController<Map<String, dynamic>> _events =
      StreamController<Map<String, dynamic>>.broadcast();
  final StreamController<LiveAudioStatus> _statuses =
      StreamController<LiveAudioStatus>.broadcast();

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _socketSubscription;
  StreamSubscription<Uint8List>? _audioSubscription;
  final List<int> _pendingPcm = [];
  LiveAudioStatus _status = const LiveAudioStatus(
    LiveAudioConnectionState.idle,
  );
  String? _sessionId;
  String _language = 'auto';
  bool _isRecording = false;
  bool _manuallyStopped = false;
  bool _reconnectInProgress = false;
  bool _disposed = false;
  int _reconnectAttempts = 0;
  String? _fatalSessionError;
  Completer<void>? _sessionEnded;
  Completer<void>? _sessionReady;
  Future<void>? _recorderStopFuture;
  String _source = 'mic';
  String _platform = 'web';

  Stream<Map<String, dynamic>> get events => _events.stream;
  Stream<LiveAudioStatus> get statuses => _statuses.stream;
  LiveAudioStatus get status => _status;
  bool get isRecording => _isRecording;

  static Uri sessionUri(String apiBaseUrl, String sessionId) {
    final baseUri = Uri.parse(apiBaseUrl);
    final scheme = switch (baseUri.scheme) {
      'https' => 'wss',
      'http' => 'ws',
      'wss' => 'wss',
      'ws' => 'ws',
      _ => throw const LiveAudioException(
        'The backend URL must use HTTP or HTTPS.',
      ),
    };
    return baseUri.replace(
      scheme: scheme,
      path: '/ws/session/${Uri.encodeComponent(sessionId)}',
      query: null,
      fragment: null,
    );
  }

  Future<void> startSession({
    required String sessionId,
    required String language,
    required String source,
    required String platform,
  }) async {
    if (_isRecording || _channel != null) {
      throw const LiveAudioException('A live audio session is already active.');
    }

    _sessionId = sessionId;
    _language = language;
    _source = source;
    _platform = platform;
    _manuallyStopped = false;
    _fatalSessionError = null;
    _reconnectAttempts = 0;
    _pendingPcm.clear();
    _sessionEnded = Completer<void>();
    _setStatus(LiveAudioConnectionState.requestingPermission);

    try {
      final hasPermission = await _recorder.hasPermission();
      if (!hasPermission) {
        throw const LiveAudioException(
          'Microphone permission was denied. Allow microphone access in your '
          'browser or device settings, then try again.',
        );
      }

      await _openConnection(source: source, platform: platform);
      if (_manuallyStopped) {
        throw LiveAudioException(
          _fatalSessionError ?? 'The backend ended the live audio session.',
        );
      }

      final audioStream = await _recorder.startStream(
        const RecordConfig(
          encoder: AudioEncoder.pcm16bits,
          sampleRate: sampleRate,
          numChannels: channels,
          streamBufferSize: chunkSizeBytes,
        ),
      );
      if (_manuallyStopped) {
        await _recorder.stop();
        throw LiveAudioException(
          _fatalSessionError ?? 'The backend ended the live audio session.',
        );
      }
      _isRecording = true;
      _audioSubscription = audioStream.listen(
        _onAudioChunk,
        onError: (Object error, StackTrace stackTrace) {
          _setStatus(
            LiveAudioConnectionState.error,
            'Microphone audio stream failed. Check microphone access and try again.',
          );
        },
        onDone: _onAudioStreamDone,
      );
      if (!_manuallyStopped) {
        _setStatus(LiveAudioConnectionState.connected);
      }
    } on LiveAudioException catch (error) {
      await _cleanupConnection();
      _setStatus(LiveAudioConnectionState.error, error.message);
      rethrow;
    } catch (error) {
      await _cleanupConnection();
      final message = error.toString().toLowerCase().contains('permission')
          ? 'Microphone permission was denied. Allow microphone access, then try again.'
          : 'Could not start live audio. Check microphone permission and backend availability.';
      _setStatus(LiveAudioConnectionState.error, message);
      throw LiveAudioException(message);
    }
  }

  Future<void> _openConnection({
    required String source,
    required String platform,
  }) async {
    final sessionId = _sessionId;
    if (sessionId == null || _manuallyStopped) return;

    _setStatus(
      _reconnectInProgress
          ? LiveAudioConnectionState.reconnecting
          : LiveAudioConnectionState.connecting,
      _reconnectInProgress
          ? 'Reconnecting. Audio may be missed while the backend reconnects.'
          : null,
    );

    _sessionReady = Completer<void>();
    final channel = WebSocketChannel.connect(sessionUri(apiBaseUrl, sessionId));
    _channel = channel;
    await channel.ready.timeout(const Duration(seconds: 15));
    _socketSubscription = channel.stream.listen(
      _onSocketMessage,
      onDone: _onSocketDone,
      onError: _onSocketError,
      cancelOnError: true,
    );
    channel.sink.add(
      jsonEncode({
        'type': 'start',
        'call_language': _language,
        'alert_langs': ['ta', 'en'],
        'source': source,
        'platform': platform,
      }),
    );
    await _sessionReady!.future.timeout(const Duration(seconds: 20));
  }

  void _onAudioChunk(Uint8List chunk) {
    if (!_isRecording) return;
    _pendingPcm.addAll(chunk);

    while (_pendingPcm.length >= chunkSizeBytes) {
      final packet = Uint8List.fromList(
        _pendingPcm.take(chunkSizeBytes).toList(),
      );
      _pendingPcm.removeRange(0, chunkSizeBytes);
      _sendPcm(packet);
    }
  }

  void _sendPcm(Uint8List packet) {
    final channel = _channel;
    if (channel == null ||
        _status.state != LiveAudioConnectionState.connected) {
      return;
    }
    try {
      channel.sink.add(packet);
    } catch (_) {
      _scheduleReconnect();
    }
  }

  void _onAudioStreamDone() {
    if (!_manuallyStopped && _isRecording) {
      _setStatus(
        LiveAudioConnectionState.error,
        'The microphone audio stream ended unexpectedly.',
      );
    }
  }

  void _onSocketMessage(dynamic rawMessage) {
    if (rawMessage is! String) {
      _setStatus(
        LiveAudioConnectionState.error,
        'The backend sent an unsupported live-session message.',
      );
      return;
    }

    try {
      final decoded = jsonDecode(rawMessage);
      if (decoded is! Map<String, dynamic>) {
        throw const FormatException('Expected an object.');
      }
      if (decoded['type'] == 'session_started' &&
          !(_sessionReady?.isCompleted ?? true)) {
        _sessionReady!.complete();
      }
      if (decoded['type'] == 'session_ended') {
        _manuallyStopped = true;
        _stopRecorderAfterFailure();
        _setStatus(LiveAudioConnectionState.stopped);
        if (!(_sessionEnded?.isCompleted ?? true)) {
          _sessionEnded!.complete();
        }
      }
      if (decoded['type'] == 'session_error') {
        _manuallyStopped = true;
        _fatalSessionError =
            decoded['message'] as String? ?? 'Live audio session failed.';
        _stopRecorderAfterFailure();
        if (!(_sessionReady?.isCompleted ?? true)) {
          _sessionReady!.completeError(LiveAudioException(_fatalSessionError!));
        }
        _setStatus(LiveAudioConnectionState.error, _fatalSessionError);
      } else if (decoded['type'] == 'stt_error' && decoded['fatal'] == true) {
        _manuallyStopped = true;
        _fatalSessionError =
            decoded['message'] as String? ??
            'Speech recognition is unavailable.';
        _stopRecorderAfterFailure();
        if (!(_sessionReady?.isCompleted ?? true)) {
          _sessionReady!.completeError(LiveAudioException(_fatalSessionError!));
        }
        _setStatus(LiveAudioConnectionState.error, _fatalSessionError);
      }
      _events.add(decoded);
    } on FormatException {
      _events.add({
        'type': 'error',
        'message': 'The backend sent an invalid live-session message.',
      });
    }
  }

  void _onSocketDone() {
    if (!(_sessionReady?.isCompleted ?? true)) {
      _sessionReady!.completeError(
        const LiveAudioException('The backend closed the live session.'),
      );
    }
    if (_manuallyStopped || !_isRecording) return;
    _scheduleReconnect();
  }

  void _stopRecorderAfterFailure() {
    unawaited(
      _stopRecorder().catchError((_) {
        _setStatus(
          LiveAudioConnectionState.error,
          'Microphone could not be released after the session ended.',
        );
      }),
    );
  }

  void _onSocketError(Object error, StackTrace stackTrace) {
    if (!(_sessionReady?.isCompleted ?? true)) {
      _sessionReady!.completeError(
        const LiveAudioException(
          'Could not connect to the live audio session on the backend.',
        ),
      );
    }
    if (_manuallyStopped || !_isRecording) return;
    _scheduleReconnect();
  }

  void _scheduleReconnect() {
    if (_manuallyStopped || !_isRecording || _reconnectInProgress) return;
    unawaited(_reconnect());
  }

  Future<void> _reconnect() async {
    _reconnectInProgress = true;
    try {
      while (!_manuallyStopped &&
          _isRecording &&
          _reconnectAttempts < maxReconnectAttempts) {
        final delay = Duration(seconds: 1 << _reconnectAttempts.clamp(0, 4));
        _reconnectAttempts++;
        _setStatus(
          LiveAudioConnectionState.reconnecting,
          'Reconnecting to ScamShield ($_reconnectAttempts/$maxReconnectAttempts)…',
        );
        await Future<void>.delayed(delay);
        if (_manuallyStopped || !_isRecording) return;

        await _closeSocket();
        try {
          await _openConnection(source: _source, platform: _platform);
          _reconnectAttempts = 0;
          _setStatus(LiveAudioConnectionState.connected);
          return;
        } catch (_) {
          await _closeSocket();
        }
      }

      if (!_manuallyStopped && _isRecording) {
        _manuallyStopped = true;
        _setStatus(
          LiveAudioConnectionState.error,
          'Could not reconnect to the backend after several attempts. '
          'Stop monitoring and try again.',
        );
        await _stopRecorder();
        await _closeSocket();
      }
    } finally {
      _reconnectInProgress = false;
    }
  }

  Future<void> stopSession() async {
    if (_manuallyStopped && !_isRecording && _channel == null) return;
    _manuallyStopped = true;

    try {
      await _stopRecorder();
      if (_pendingPcm.isNotEmpty) {
        if (_pendingPcm.length.isEven) {
          _sendPcm(Uint8List.fromList(_pendingPcm));
        } else {
          _setStatus(
            LiveAudioConnectionState.error,
            'Discarded an incomplete PCM sample while stopping audio.',
          );
        }
        _pendingPcm.clear();
      }

      final channel = _channel;
      if (channel != null) {
        channel.sink.add(jsonEncode({'type': 'stop'}));
        await Future.any<void>([
          _sessionEnded?.future ?? Future<void>.value(),
          Future<void>.delayed(const Duration(seconds: 3)),
        ]);
      }
    } catch (_) {
      _setStatus(
        LiveAudioConnectionState.error,
        'Could not stop live audio cleanly.',
      );
    } finally {
      try {
        await _cleanupConnection();
      } catch (_) {
        _setStatus(
          LiveAudioConnectionState.error,
          'A microphone or socket resource could not be closed cleanly.',
        );
      }
      if (_status.state != LiveAudioConnectionState.error) {
        _setStatus(LiveAudioConnectionState.stopped);
      }
    }
  }

  Future<void> _stopRecorder() {
    final inProgress = _recorderStopFuture;
    if (inProgress != null) return inProgress;
    if (!_isRecording) return Future<void>.value();

    final stopFuture = _performRecorderStop();
    _recorderStopFuture = stopFuture;
    return stopFuture;
  }

  Future<void> _performRecorderStop() async {
    final subscription = _audioSubscription;
    try {
      await _recorder.stop();
    } finally {
      _isRecording = false;
      _audioSubscription = null;
      await subscription?.cancel();
      _recorderStopFuture = null;
    }
  }

  Future<void> _closeSocket() async {
    await _socketSubscription?.cancel();
    _socketSubscription = null;
    final channel = _channel;
    _channel = null;
    await channel?.sink.close(websocket_status.goingAway);
  }

  Future<void> _cleanupConnection() async {
    await _stopRecorder();
    await _closeSocket();
  }

  void _setStatus(LiveAudioConnectionState state, [String? message]) {
    _status = LiveAudioStatus(state, message: message);
    if (!_statuses.isClosed) _statuses.add(_status);
  }

  Future<void> dispose() async {
    if (_disposed) return;
    await stopSession();
    _disposed = true;
    await _recorder.dispose();
    await _events.close();
    await _statuses.close();
  }
}
