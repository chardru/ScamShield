class TacticDetail {
  const TacticDetail({
    required this.tactic,
    required this.severity,
    required this.evidence,
  });

  final String tactic;
  final String severity;
  final String evidence;

  factory TacticDetail.fromJson(Map<String, dynamic> json) => TacticDetail(
    tactic: json['tactic'] as String? ?? 'Unknown tactic',
    severity: json['severity'] as String? ?? 'medium',
    evidence: json['evidence'] as String? ?? '',
  );
}

class AnalysisResult {
  const AnalysisResult({
    required this.reportId,
    required this.isSuspicious,
    required this.riskScore,
    required this.riskLevel,
    required this.detectedTactics,
    required this.tacticDetails,
    required this.explanation,
    required this.recommendedAction,
    required this.confidence,
    required this.aiProvider,
    required this.source,
  });

  final String reportId;
  final bool isSuspicious;
  final int riskScore;
  final String riskLevel;
  final List<String> detectedTactics;
  final List<TacticDetail> tacticDetails;
  final String explanation;
  final String recommendedAction;
  final double confidence;
  final String aiProvider;
  final String source;

  factory AnalysisResult.fromJson(Map<String, dynamic> json) => AnalysisResult(
    reportId: json['report_id'] as String? ?? '',
    isSuspicious: json['is_suspicious'] as bool? ?? false,
    riskScore: (json['risk_score'] as num?)?.toInt() ?? 0,
    riskLevel: json['risk_level'] as String? ?? 'SAFE',
    detectedTactics: _stringList(json['detected_tactics']),
    tacticDetails: _mapList(json['tactic_details'])
        .map(TacticDetail.fromJson)
        .toList(growable: false),
    explanation: json['explanation'] as String? ?? '',
    recommendedAction: json['recommended_action'] as String? ?? '',
    confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
    aiProvider: json['ai_provider'] as String? ?? 'demo',
    source: json['source'] as String? ?? 'text_input',
  );
}

class ReportSummary {
  const ReportSummary({
    required this.id,
    required this.conversationText,
    required this.riskScore,
    required this.riskLevel,
    required this.isSuspicious,
    required this.detectedTactics,
    required this.source,
    required this.aiProvider,
    this.createdAt,
  });

  final String id;
  final String conversationText;
  final int riskScore;
  final String riskLevel;
  final bool isSuspicious;
  final List<String> detectedTactics;
  final String source;
  final String aiProvider;
  final String? createdAt;

  factory ReportSummary.fromJson(Map<String, dynamic> json) => ReportSummary(
    id: json['id'] as String? ?? '',
    conversationText: json['conversation_text'] as String? ?? '',
    riskScore: (json['risk_score'] as num?)?.toInt() ?? 0,
    riskLevel: json['risk_level'] as String? ?? 'SAFE',
    isSuspicious: json['is_suspicious'] as bool? ?? false,
    detectedTactics: _stringList(json['detected_tactics']),
    source: json['source'] as String? ?? 'text_input',
    aiProvider: json['ai_provider'] as String? ?? 'demo',
    createdAt: json['created_at'] as String?,
  );
}

class ReportDetail extends ReportSummary {
  const ReportDetail({
    required super.id,
    required super.conversationText,
    required super.riskScore,
    required super.riskLevel,
    required super.isSuspicious,
    required super.detectedTactics,
    required super.source,
    required super.aiProvider,
    super.createdAt,
    required this.explanation,
    required this.recommendedAction,
    required this.confidence,
    this.languageDetected,
  });

  final String explanation;
  final String recommendedAction;
  final double confidence;
  final String? languageDetected;

  factory ReportDetail.fromJson(Map<String, dynamic> json) => ReportDetail(
    id: json['id'] as String? ?? '',
    conversationText: json['conversation_text'] as String? ?? '',
    riskScore: (json['risk_score'] as num?)?.toInt() ?? 0,
    riskLevel: json['risk_level'] as String? ?? 'SAFE',
    isSuspicious: json['is_suspicious'] as bool? ?? false,
    detectedTactics: _stringList(json['detected_tactics']),
    source: json['source'] as String? ?? 'text_input',
    aiProvider: json['ai_provider'] as String? ?? 'demo',
    createdAt: json['created_at'] as String?,
    explanation: json['explanation'] as String? ?? '',
    recommendedAction: json['recommended_action'] as String? ?? '',
    confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
    languageDetected: json['language_detected'] as String?,
  );
}

class TranscriptionResult {
  const TranscriptionResult({
    required this.transcript,
    required this.provider,
    this.languageDetected,
    this.durationSeconds,
  });

  final String transcript;
  final String provider;
  final String? languageDetected;
  final double? durationSeconds;

  factory TranscriptionResult.fromJson(Map<String, dynamic> json) =>
      TranscriptionResult(
        transcript: json['transcript'] as String? ?? '',
        provider: json['provider'] as String? ?? 'demo',
        languageDetected: json['language_detected'] as String?,
        durationSeconds: (json['duration_seconds'] as num?)?.toDouble(),
      );
}

class TrustedContact {
  const TrustedContact({
    required this.id,
    required this.name,
    required this.chatId,
    required this.enabled,
  });

  final int id;
  final String name;
  final String chatId;
  final bool enabled;

  factory TrustedContact.fromJson(Map<String, dynamic> json) => TrustedContact(
    id: (json['id'] as num?)?.toInt() ?? 0,
    name: json['name'] as String? ?? '',
    chatId: json['chat_id'] as String? ?? '',
    enabled: json['enabled'] as bool? ?? false,
  );
}

class ContactTestResult {
  const ContactTestResult({
    required this.contactId,
    required this.name,
    required this.success,
    required this.message,
  });

  final int contactId;
  final String name;
  final bool success;
  final String message;

  factory ContactTestResult.fromJson(Map<String, dynamic> json) =>
      ContactTestResult(
        contactId: (json['contact_id'] as num?)?.toInt() ?? 0,
        name: json['name'] as String? ?? '',
        success: json['success'] as bool? ?? false,
        message: json['message'] as String? ?? '',
      );
}

class ContactTestBatch {
  const ContactTestBatch({
    required this.total,
    required this.successCount,
    required this.failureCount,
    required this.results,
  });

  final int total;
  final int successCount;
  final int failureCount;
  final List<ContactTestResult> results;

  factory ContactTestBatch.fromJson(Map<String, dynamic> json) =>
      ContactTestBatch(
        total: (json['total'] as num?)?.toInt() ?? 0,
        successCount: (json['success_count'] as num?)?.toInt() ?? 0,
        failureCount: (json['failure_count'] as num?)?.toInt() ?? 0,
        results: _mapList(json['results'])
            .map(ContactTestResult.fromJson)
            .toList(growable: false),
      );
}

List<String> _stringList(dynamic value) {
  if (value is! List) return const [];
  return value.whereType<String>().toList(growable: false);
}

List<Map<String, dynamic>> _mapList(dynamic value) {
  if (value is! List) return const [];
  return value.whereType<Map<String, dynamic>>().toList(growable: false);
}
