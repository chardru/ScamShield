import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/services/live_audio_service.dart';

void main() {
  test('builds a local live session WebSocket URI', () {
    final uri = LiveAudioService.sessionUri(
      'http://127.0.0.1:8000',
      'local-session',
    );

    expect(uri.scheme, 'ws');
    expect(uri.host, '127.0.0.1');
    expect(uri.port, 8000);
    expect(uri.path, '/ws/session/local-session');
  });

  test('uses secure WebSockets for an HTTPS backend URL', () {
    final uri = LiveAudioService.sessionUri(
      'https://scamshield.example:8443/api',
      'session 1',
    );

    expect(uri.scheme, 'wss');
    expect(uri.host, 'scamshield.example');
    expect(uri.port, 8443);
    expect(uri.path, '/ws/session/session%201');
  });

  test('rejects a backend URL with an unsupported scheme', () {
    expect(
      () => LiveAudioService.sessionUri('ftp://localhost:8000', 'session'),
      throwsA(isA<LiveAudioException>()),
    );
  });
}
