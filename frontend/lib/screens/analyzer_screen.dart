import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_models.dart';
import '../main.dart';
import '../theme.dart';
import '../widgets/common_widgets.dart';

class AnalyzerScreen extends ConsumerStatefulWidget {
  const AnalyzerScreen({super.key});

  @override
  ConsumerState<AnalyzerScreen> createState() => _AnalyzerScreenState();
}

class _AnalyzerScreenState extends ConsumerState<AnalyzerScreen> {
  final _textController = TextEditingController();
  AnalysisResult? _analysis;
  TranscriptionResult? _transcription;
  String? _selectedFileName;
  String? _selectedLanguage;
  bool _isAnalyzing = false;
  bool _isTranscribing = false;
  String? _error;

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final status = ref.watch(transcriptionStatusProvider).asData?.value;
    final maxAudioSizeMb = (status?['max_size_mb'] as num?)?.toInt() ?? 25;
    return ListView(
      padding: const EdgeInsets.fromLTRB(24, 10, 24, 36),
      children: [
        Text(
          'Analyze a conversation',
          style: Theme.of(context).textTheme.headlineLarge,
        ),
        const SizedBox(height: 7),
        Text(
          'Check a message or a recording you choose to upload. ScamShield never records calls.',
          style: Theme.of(context).textTheme.bodyLarge
              ?.copyWith(color: ScamColors.muted),
        ),
        const SizedBox(height: 22),
        DefaultTabController(
          length: 2,
          child: Column(
            children: [
              const TabBar(
                tabs: [
                  Tab(icon: Icon(Icons.chat_bubble_outline), text: 'Text'),
                  Tab(icon: Icon(Icons.audio_file_outlined), text: 'Audio'),
                ],
              ),
              SizedBox(
                height: 515,
                child: TabBarView(
                  children: [
                    _buildTextPanel(context),
                    _buildAudioPanel(context, maxAudioSizeMb: maxAudioSizeMb),
                  ],
                ),
              ),
            ],
          ),
        ),
        if (_error != null) ...[
          const SizedBox(height: 13),
          ErrorNotice(message: _error!),
        ],
        if (_analysis != null) ...[
          const SizedBox(height: 20),
          _AnalysisResultPanel(result: _analysis!),
        ],
      ],
    );
  }

  Widget _buildTextPanel(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 16),
    child: Panel(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Paste a message or conversation',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          Text(
            'Include as much context as you can. Avoid sharing sensitive details you do not need analyzed.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 15),
          Expanded(
            child: TextField(
              controller: _textController,
              enabled: !_isAnalyzing,
              maxLines: null,
              expands: true,
              maxLength: 10000,
              textAlignVertical: TextAlignVertical.top,
              decoration: const InputDecoration(
                hintText: 'Example: “This is your bank. Tell me the one-time code we just sent to verify your account...”',
                alignLabelWithHint: true,
              ),
            ),
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: _isAnalyzing ? null : _analyzeText,
              icon: _isAnalyzing
                  ? const SizedBox.square(
                      dimension: 17,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.radar),
              label: Text(_isAnalyzing ? 'Analyzing…' : 'Analyze conversation'),
            ),
          ),
        ],
      ),
    ),
  );

  Widget _buildAudioPanel(
    BuildContext context, {
    required int maxAudioSizeMb,
  }) => Padding(
    padding: const EdgeInsets.only(top: 16),
    child: Panel(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Transcribe an audio file',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          Text(
            'Choose a recording yourself. Supported: WAV, MP3, OGG, M4A, FLAC, WebM (up to $maxAudioSizeMb MB).',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 15),
          OutlinedButton.icon(
            onPressed: _isTranscribing ? null : _chooseAudioFile,
            icon: const Icon(Icons.folder_open),
            label: Text(_selectedFileName ?? 'Choose an audio file'),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String?>(
            initialValue: _selectedLanguage,
            decoration: const InputDecoration(labelText: 'Audio language'),
            items: const [
              DropdownMenuItem<String?>(
                value: null,
                child: Text('Auto-detect'),
              ),
              DropdownMenuItem<String?>(
                value: 'en-IN',
                child: Text('English (India)'),
              ),
              DropdownMenuItem<String?>(value: 'ta-IN', child: Text('Tamil')),
            ],
            onChanged: _isTranscribing
                ? null
                : (value) => setState(() => _selectedLanguage = value),
          ),
          const SizedBox(height: 13),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: _isTranscribing || _selectedFileName == null
                  ? null
                  : _transcribe,
              icon: _isTranscribing
                  ? const SizedBox.square(
                      dimension: 17,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.graphic_eq),
              label: Text(
                _isTranscribing ? 'Transcribing…' : 'Transcribe audio',
              ),
            ),
          ),
          if (_transcription != null) ...[
            const SizedBox(height: 16),
            Text(
              'Transcript · ${_transcription!.provider}',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 7),
            Expanded(
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(13),
                decoration: BoxDecoration(
                  color: ScamColors.background,
                  borderRadius: BorderRadius.circular(13),
                  border: Border.all(color: ScamColors.line),
                ),
                child: SingleChildScrollView(
                  child: SelectableText(_transcription!.transcript),
                ),
              ),
            ),
            const SizedBox(height: 11),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed:
                    _transcription!.transcript.trim().isEmpty || _isAnalyzing
                    ? null
                    : () => _analyzeText(source: 'audio'),
                icon: const Icon(Icons.shield_outlined),
                label: const Text('Analyze transcript'),
              ),
            ),
          ],
        ],
      ),
    ),
  );

  Future<void> _analyzeText({String source = 'text_input'}) async {
    final text = source == 'audio'
        ? _transcription?.transcript.trim() ?? ''
        : _textController.text.trim();
    if (text.isEmpty) {
      setState(() => _error = 'Enter a conversation before analyzing.');
      return;
    }
    setState(() {
      _isAnalyzing = true;
      _error = null;
      _analysis = null;
    });
    try {
      final result = await ref.read(apiProvider).analyze(text, source: source);
      if (!mounted) return;
      setState(() => _analysis = result);
      ref.invalidate(reportsProvider);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _isAnalyzing = false);
    }
  }

  Future<void> _chooseAudioFile() async {
    setState(() => _error = null);
    try {
      final file = await FilePicker.pickFile(
        type: FileType.custom,
        allowedExtensions: const ['wav', 'mp3', 'ogg', 'm4a', 'flac', 'webm'],
      );
      if (file == null) return;
      final size = await file.length();
      if (size == null) {
        setState(
          () => _error = 'Could not determine the selected audio file size.',
        );
        return;
      }
      final maxSizeMb =
          (ref.read(transcriptionStatusProvider).asData?.value['max_size_mb']
                  as num?)
              ?.toInt() ??
          25;
      if (size > maxSizeMb * 1024 * 1024) {
        setState(
          () => _error = 'Audio file exceeds the $maxSizeMb MB upload limit.',
        );
        return;
      }
      setState(() {
        _selectedFileName = file.name;
        _pendingFile = file;
        _transcription = null;
        _analysis = null;
      });
    } catch (error) {
      if (mounted) {
        setState(() => _error = 'Could not open the file picker: $error');
      }
    }
  }

  PlatformFile? _pendingFile;

  Future<void> _transcribe() async {
    final file = _pendingFile;
    final filename = _selectedFileName;
    if (file == null || filename == null) {
      setState(() => _error = 'Choose an audio file before transcribing.');
      return;
    }
    setState(() {
      _isTranscribing = true;
      _error = null;
      _analysis = null;
    });
    try {
      final bytes = await file.readAsBytes();
      final result = await ref
          .read(apiProvider)
          .transcribe(
            filename: filename,
            bytes: bytes,
            language: _selectedLanguage,
          );
      if (mounted) setState(() => _transcription = result);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _isTranscribing = false);
    }
  }
}

class _AnalysisResultPanel extends StatelessWidget {
  const _AnalysisResultPanel({required this.result});

  final AnalysisResult result;

  @override
  Widget build(BuildContext context) {
    final color = riskColor(result.riskLevel);
    return Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'Analysis result',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
              RiskPill(level: result.riskLevel),
            ],
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              RiskScoreGauge(
                score: result.riskScore,
                level: result.riskLevel,
                size: 108,
              ),
              const SizedBox(width: 19),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      result.riskLevel.toUpperCase(),
                      style: TextStyle(
                        color: color,
                        fontSize: 20,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 5),
                    Text(
                      '${result.aiProvider.toUpperCase()} analysis · ${(result.confidence * 100).round()}% confidence',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 22),
          _ResultSection(title: 'Explanation', body: result.explanation),
          const SizedBox(height: 15),
          _ResultSection(
            title: 'Recommended action',
            body: result.recommendedAction,
          ),
          const SizedBox(height: 15),
          Text(
            'Detected tactics',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          buildTacticChips(result.detectedTactics),
          if (result.tacticDetails.isNotEmpty) ...[
            const SizedBox(height: 13),
            for (final tactic in result.tacticDetails)
              Padding(
                padding: const EdgeInsets.only(bottom: 9),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      margin: const EdgeInsets.only(top: 5),
                      width: 7,
                      height: 7,
                      decoration: BoxDecoration(
                        color: color,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 9),
                    Expanded(
                      child: Text(
                        '${tactic.tactic} (${tactic.severity}): ${tactic.evidence}',
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ],
      ),
    );
  }
}

class _ResultSection extends StatelessWidget {
  const _ResultSection({required this.title, required this.body});

  final String title;
  final String body;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(title, style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: 6),
      Text(body.isEmpty ? 'No details provided.' : body),
    ],
  );
}
