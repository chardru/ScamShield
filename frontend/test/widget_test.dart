import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:frontend/api/api_models.dart';
import 'package:frontend/api/scamshield_api.dart';
import 'package:frontend/main.dart';
import 'package:frontend/screens/trusted_contacts_screen.dart';

void main() {
  test('analysis response parser keeps risk and tactic details', () {
    final result = AnalysisResult.fromJson({
      'report_id': 'report-1',
      'is_suspicious': true,
      'risk_score': 84,
      'risk_level': 'DANGER',
      'detected_tactics': ['authority impersonation', 'OTP request'],
      'tactic_details': [
        {
          'tactic': 'authority impersonation',
          'severity': 'high',
          'evidence': 'Claims to be police.',
        },
      ],
      'explanation': 'The sender impersonates the police.',
      'recommended_action': 'Do not share codes; verify independently.',
      'confidence': 0.93,
      'ai_provider': 'gemini',
      'source': 'text_input',
    });

    expect(result.riskScore, 84);
    expect(result.riskLevel, 'DANGER');
    expect(result.tacticDetails.single.evidence, 'Claims to be police.');
    expect(result.aiProvider, 'gemini');
  });

  testWidgets('dashboard renders and navigation opens the analyzer', (
    tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [apiProvider.overrideWithValue(_FakeApi())],
        child: const ScamShieldApp(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Your conversations, protected.'), findsOneWidget);
    await tester.tap(find.text('Analyze').last);
    await tester.pumpAndSettle();
    expect(find.text('Analyze a conversation'), findsOneWidget);
    expect(find.text('Text'), findsOneWidget);
    expect(find.text('Audio'), findsOneWidget);
  });

  testWidgets('trusted contacts validates input and accepts a family member', (
    tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [apiProvider.overrideWithValue(_FakeApi())],
        child: const MaterialApp(home: TrustedContactsScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Before adding family'), findsOneWidget);
    expect(find.text('No family members added'), findsOneWidget);
    await tester.tap(find.byTooltip('Add family member'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Add member'));
    await tester.pumpAndSettle();
    expect(find.text('Enter a family member name.'), findsOneWidget);

    await tester.enterText(find.byType(TextFormField).at(0), 'Mom');
    await tester.enterText(find.byType(TextFormField).at(1), '123456789');
    await tester.tap(find.text('Add member'));
    await tester.pumpAndSettle();
    expect(find.text('Trusted family member added.'), findsOneWidget);
  });
}

class _FakeApi extends ScamShieldApi {
  @override
  Future<List<ReportSummary>> getReports({
    int limit = 50,
    int offset = 0,
  }) async => const [];

  @override
  Future<Map<String, dynamic>> getTranscriptionStatus() async => const {
    'sarvam_configured': false,
    'supported_formats': ['wav', 'mp3', 'ogg', 'm4a', 'flac', 'webm'],
    'max_size_mb': 25,
  };

  @override
  Future<Map<String, dynamic>> getNotificationStatus() async => const {
    'telegram': {'configured': false},
  };

  @override
  Future<List<TrustedContact>> getTrustedContacts() async => const [];

  @override
  Future<TrustedContact> createTrustedContact({
    required String name,
    required String chatId,
    required bool enabled,
  }) async =>
      TrustedContact(id: 1, name: name, chatId: chatId, enabled: enabled);
}
