import 'dart:async';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../services/live_audio_service.dart';
import '../theme.dart';
import 'common_widgets.dart';

class LiveAudioPanel extends StatefulWidget {
  const LiveAudioPanel({super.key, required this.apiBaseUrl});

  final String apiBaseUrl;

  @override
  State<LiveAudioPanel> createState() => _LiveAudioPanelState();
}

class _LiveAudioPanelState extends State<LiveAudioPanel> {
  late final LiveAudioService _service;
  StreamSubscription<Map<String, dynamic>>? _eventSubscription;
  StreamSubscription<LiveAudioStatus>? _statusSubscription;

  LiveAudioStatus _status = const LiveAudioStatus(
    LiveAudioConnectionState.idle,
  );
  String _language = 'ta-IN';
  String _transcript = '';
  String _partialTranscript = '';
  String _riskLevel = 'SAFE';
  String _recommendedAction = '';
  String _explanation = '';
  String? _errorMessage;
  int _riskScore = 0;
  List<String> _detectedTactics = const [];
  bool _isStarting = false;
  bool _isMonitoring = false;
  bool _hasLiveAnalysis = false;

  @override
  void initState() {
    super.initState();
    _service = LiveAudioService(apiBaseUrl: widget.apiBaseUrl);
    _statusSubscription = _service.statuses.listen((status) {
      if (!mounted) return;
      setState(() {
        _status = status;
        if (status.state == LiveAudioConnectionState.error) {
          _errorMessage = status.message;
          _isMonitoring = _service.isRecording;
        }
      });
    });
    _eventSubscription = _service.events.listen(_handleEvent);
  }

  @override
  void dispose() {
    unawaited(_eventSubscription?.cancel());
    unawaited(_statusSubscription?.cancel());
    unawaited(_service.dispose());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Panel(
    padding: const EdgeInsets.all(16),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.mic, color: ScamColors.mint),
            const SizedBox(width: 9),
            Expanded(
              child: Text(
                'Live microphone monitoring',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            _ConnectionStatus(status: _status),
          ],
        ),
        const SizedBox(height: 7),
        Text(
          'Microphone audio is streamed only after you start monitoring and grant permission. '
          'Cellular call audio cannot be captured directly.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        const SizedBox(height: 10),
        Text(
          'For a call, place it on speaker and use a second device to monitor the audio.',
          style: Theme.of(context).textTheme.bodySmall
              ?.copyWith(color: ScamColors.muted),
        ),
        const SizedBox(height: 13),
        LayoutBuilder(
          builder: (context, constraints) {
            final compact = constraints.maxWidth < 560;
            final languageDropdown = DropdownButtonFormField<String>(
              initialValue: _language,
              isExpanded: true,
              decoration: const InputDecoration(
                labelText: 'Spoken language',
                isDense: true,
              ),
              items: const [
                DropdownMenuItem(value: 'ta-IN', child: Text('Tamil')),
                DropdownMenuItem(value: 'en-IN', child: Text('English')),
                DropdownMenuItem(value: 'auto', child: Text('Auto-detect')),
              ],
              onChanged: _isStarting || _isMonitoring
                  ? null
                  : (language) {
                      if (language != null) {
                        setState(() => _language = language);
                      }
                    },
            );
            final controls = Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _isStarting || _isMonitoring
                        ? null
                        : _startMonitoring,
                    icon: _isStarting
                        ? const SizedBox.square(
                            dimension: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.mic),
                    label: Text(_isStarting ? 'Starting…' : 'Start monitoring'),
                  ),
                ),
                const SizedBox(width: 9),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _isMonitoring ? _stopMonitoring : null,
                    icon: const Icon(Icons.stop_circle_outlined),
                    label: const Text('Stop'),
                  ),
                ),
              ],
            );
            if (compact) {
              return Column(
                children: [
                  languageDropdown,
                  const SizedBox(height: 9),
                  controls,
                ],
              );
            }
            return Row(
              children: [
                SizedBox(width: 170, child: languageDropdown),
                const SizedBox(width: 12),
                Expanded(child: controls),
              ],
            );
          },
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            const Icon(Icons.info_outline, size: 15, color: ScamColors.muted),
            const SizedBox(width: 7),
            Expanded(
              child: Text(
                _permissionStatus,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          ],
        ),
        if (_errorMessage != null) ...[
          const SizedBox(height: 9),
          _InlineMessage(message: _errorMessage!, isError: true),
        ],
        const SizedBox(height: 11),
        Expanded(
          child: ListView(
            padding: EdgeInsets.zero,
            children: [
              Text(
                'Live transcript',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: 7),
              Container(
                constraints: const BoxConstraints(
                  minHeight: 75,
                  maxHeight: 130,
                ),
                width: double.infinity,
                padding: const EdgeInsets.all(11),
                decoration: BoxDecoration(
                  color: ScamColors.background,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: ScamColors.line),
                ),
                child: SingleChildScrollView(
                  child: SelectableText(
                    _transcript.isEmpty
                        ? 'Final recognized speech will appear here.'
                        : _transcript,
                  ),
                ),
              ),
              if (_partialTranscript.isNotEmpty) ...[
                const SizedBox(height: 6),
                Text(
                  'Listening: $_partialTranscript',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: ScamColors.muted,
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ],
              if (_hasLiveAnalysis) ...[
                const SizedBox(height: 11),
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        'Current risk · $_riskScore / 100',
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                    ),
                    RiskPill(level: _riskLevel),
                  ],
                ),
                if (_detectedTactics.isNotEmpty) ...[
                  const SizedBox(height: 7),
                  buildTacticChips(_detectedTactics),
                ],
                if (_explanation.isNotEmpty) ...[
                  const SizedBox(height: 7),
                  Text(_explanation),
                ],
                if (_recommendedAction.isNotEmpty) ...[
                  const SizedBox(height: 7),
                  Text(
                    'Recommended: $_recommendedAction',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ],
            ],
          ),
        ),
      ],
    ),
  );

  String get _permissionStatus => switch (_status.state) {
    LiveAudioConnectionState.idle =>
      'Microphone permission has not been requested.',
    LiveAudioConnectionState.requestingPermission =>
      'Requesting microphone permission…',
    LiveAudioConnectionState.connecting =>
      'Microphone allowed; connecting to backend…',
    LiveAudioConnectionState.connected =>
      'Microphone permission granted · live session connected.',
    LiveAudioConnectionState.reconnecting =>
      _status.message ?? 'Backend disconnected; attempting to reconnect…',
    LiveAudioConnectionState.stopped =>
      'Monitoring stopped; microphone released.',
    LiveAudioConnectionState.error =>
      _status.message ?? 'Live monitoring error.',
  };

  Future<void> _startMonitoring() async {
    setState(() {
      _isStarting = true;
      _errorMessage = null;
      _transcript = '';
      _partialTranscript = '';
      _riskScore = 0;
      _riskLevel = 'SAFE';
      _hasLiveAnalysis = false;
      _detectedTactics = const [];
      _explanation = '';
      _recommendedAction = '';
    });

    final platform = kIsWeb
        ? 'web'
        : switch (defaultTargetPlatform) {
            TargetPlatform.android => 'android',
            TargetPlatform.iOS => 'ios',
            TargetPlatform.windows => 'windows',
            TargetPlatform.macOS => 'macos',
            TargetPlatform.linux => 'linux',
            TargetPlatform.fuchsia => 'fuchsia',
          };

    try {
      await _service.startSession(
        sessionId:
            'scamshield-${DateTime.now().microsecondsSinceEpoch}-${Random().nextInt(1 << 20)}',
        language: _language,
        source: 'mic',
        platform: platform,
      );
      if (mounted) setState(() => _isMonitoring = true);
    } catch (error) {
      if (mounted) {
        setState(() {
          _errorMessage = error.toString();
          _isMonitoring = false;
        });
      }
    } finally {
      if (mounted) setState(() => _isStarting = false);
    }
  }

  Future<void> _stopMonitoring() async {
    setState(() => _isMonitoring = false);
    await _service.stopSession();
  }

  void _handleEvent(Map<String, dynamic> event) {
    if (!mounted) return;
    final type = event['type'];
    setState(() {
      switch (type) {
        case 'transcript_partial':
          _partialTranscript = event['text'] as String? ?? '';
          break;
        case 'transcript_final':
          _transcript =
              event['transcript'] as String? ??
              [
                _transcript,
                event['text'] as String? ?? '',
              ].where((part) => part.isNotEmpty).join(' ');
          _partialTranscript = '';
          break;
        case 'analysis_update':
          _hasLiveAnalysis = true;
          _riskScore = (event['risk_score'] as num?)?.toInt() ?? _riskScore;
          _riskLevel = event['risk_level'] as String? ?? _riskLevel;
          _detectedTactics =
              (event['detected_tactics'] as List?)?.whereType<String>().toList(
                growable: false,
              ) ??
              _detectedTactics;
          _explanation = event['explanation'] as String? ?? '';
          _recommendedAction = event['recommended_action'] as String? ?? '';
          break;
        case 'analysis_error':
        case 'transcription_notice':
        case 'stt_error':
        case 'session_error':
        case 'error':
          _errorMessage =
              event['message'] as String? ??
              'The live audio service returned an error.';
          if (event['fatal'] == true || type == 'session_error') {
            _isMonitoring = false;
          }
          break;
        case 'session_ended':
          _isMonitoring = false;
          break;
        case 'session_started':
        case 'stt_ready':
        case 'pong':
          break;
        default:
          break;
      }
    });
  }
}

class _ConnectionStatus extends StatelessWidget {
  const _ConnectionStatus({required this.status});

  final LiveAudioStatus status;

  @override
  Widget build(BuildContext context) {
    final (label, color) = switch (status.state) {
      LiveAudioConnectionState.connected => ('Connected', ScamColors.mint),
      LiveAudioConnectionState.connecting ||
      LiveAudioConnectionState.requestingPermission => (
        'Connecting',
        ScamColors.caution,
      ),
      LiveAudioConnectionState.reconnecting => (
        'Reconnecting',
        ScamColors.warning,
      ),
      LiveAudioConnectionState.error => ('Error', ScamColors.danger),
      LiveAudioConnectionState.stopped => ('Stopped', ScamColors.muted),
      LiveAudioConnectionState.idle => ('Ready', ScamColors.muted),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: .1),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 7,
            height: 7,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 11,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _InlineMessage extends StatelessWidget {
  const _InlineMessage({required this.message, required this.isError});

  final String message;
  final bool isError;

  @override
  Widget build(BuildContext context) {
    final color = isError ? ScamColors.danger : ScamColors.caution;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(9),
      decoration: BoxDecoration(
        color: color.withValues(alpha: .08),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: .25)),
      ),
      child: Text(message, style: TextStyle(color: color, fontSize: 12)),
    );
  }
}
