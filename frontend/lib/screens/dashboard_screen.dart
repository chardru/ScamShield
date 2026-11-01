import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_models.dart';
import '../main.dart';
import '../theme.dart';
import '../widgets/common_widgets.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({
    super.key,
    required this.onAnalyze,
    required this.onReports,
  });

  final VoidCallback onAnalyze;
  final VoidCallback onReports;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final reports = ref.watch(reportsProvider);
    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(reportsProvider);
        ref.invalidate(apiHealthProvider);
        await ref.read(reportsProvider.future);
      },
      child: ListView(
        padding: const EdgeInsets.fromLTRB(24, 10, 24, 36),
        children: [
          Text(
            'Your conversations, protected.',
            style: Theme.of(context).textTheme.headlineLarge,
          ),
          const SizedBox(height: 8),
          Text(
            'Check suspicious messages and calls with ScamShield AI.',
            style: Theme.of(context).textTheme.bodyLarge
                ?.copyWith(color: ScamColors.muted),
          ),
          const SizedBox(height: 25),
          _HeroCard(onAnalyze: onAnalyze),
          const SizedBox(height: 23),
          SectionHeading(
            title: 'Risk guide',
            subtitle: 'Understand what each level means',
          ),
          const SizedBox(height: 13),
          const _RiskGuide(),
          const SizedBox(height: 24),
          SectionHeading(
            title: 'Recent analyses',
            subtitle: 'Saved reports from your conversations',
            trailing: TextButton.icon(
              onPressed: onReports,
              icon: const Icon(Icons.arrow_forward, size: 16),
              label: const Text('All reports'),
            ),
          ),
          const SizedBox(height: 12),
          reports.when(
            loading: () => const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: CircularProgressIndicator(),
              ),
            ),
            error: (error, _) => ErrorNotice(
              message: error.toString(),
              onRetry: () => ref.invalidate(reportsProvider),
            ),
            data: (items) => items.isEmpty
                ? const EmptyNotice(
                    title: 'No reports yet',
                    message: 'Your analysis history will appear here.',
                  )
                : Column(
                    children: [
                      for (final report in items.take(4)) ...[
                        ReportListTile(
                          report: report,
                          onTap: () => _openReport(context, ref, report.id),
                        ),
                        const SizedBox(height: 9),
                      ],
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  Future<void> _openReport(
    BuildContext context,
    WidgetRef ref,
    String id,
  ) async {
    try {
      final report = await ref.read(apiProvider).getReport(id);
      if (context.mounted) {
        await showModalBottomSheet<void>(
          context: context,
          isScrollControlled: true,
          backgroundColor: ScamColors.panel,
          builder: (_) => ReportDetailSheet(report: report),
        );
      }
    } catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(error.toString())));
      }
    }
  }
}

class _HeroCard extends StatelessWidget {
  const _HeroCard({required this.onAnalyze});

  final VoidCallback onAnalyze;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(25),
    decoration: BoxDecoration(
      gradient: const LinearGradient(
        colors: [Color(0xFF142A30), Color(0xFF15202A), Color(0xFF172331)],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ),
      borderRadius: BorderRadius.circular(22),
      border: Border.all(color: ScamColors.mint.withValues(alpha: .24)),
    ),
    child: LayoutBuilder(
      builder: (context, constraints) {
        final compact = constraints.maxWidth < 590;
        final text = Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: ScamColors.mint.withValues(alpha: .12),
                borderRadius: BorderRadius.circular(30),
              ),
              child: const Text(
                'STAY ONE STEP AHEAD',
                style: TextStyle(
                  color: ScamColors.mint,
                  fontSize: 10,
                  fontWeight: FontWeight.w900,
                  letterSpacing: 1,
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              'Not sure about a conversation?',
              style: Theme.of(context).textTheme.headlineMedium
                  ?.copyWith(fontSize: compact ? 24 : 30),
            ),
            const SizedBox(height: 9),
            Text(
              'Analyze text or upload audio to spot common scam tactics before you act.',
              style: Theme.of(context).textTheme.bodyMedium
                  ?.copyWith(color: ScamColors.muted),
            ),
            const SizedBox(height: 19),
            FilledButton.icon(
              onPressed: onAnalyze,
              icon: const Icon(Icons.radar, size: 18),
              label: const Text('Analyze a conversation'),
            ),
          ],
        );
        if (compact) return text;
        return Row(
          children: [
            Expanded(child: text),
            const SizedBox(width: 20),
            const Icon(Icons.shield_moon, size: 102, color: ScamColors.mint),
          ],
        );
      },
    ),
  );
}

class _RiskGuide extends StatelessWidget {
  const _RiskGuide();

  static const levels = [
    (
      'SAFE',
      'No immediate concern detected',
      ScamColors.safe,
      Icons.verified_user_outlined,
    ),
    (
      'CAUTION',
      'A few signs deserve a closer look',
      ScamColors.caution,
      Icons.info_outline,
    ),
    (
      'WARNING',
      'Several suspicious patterns found',
      ScamColors.warning,
      Icons.warning_amber_rounded,
    ),
    (
      'DANGER',
      'Strong indicators — stop and verify',
      ScamColors.danger,
      Icons.gpp_bad_outlined,
    ),
  ];

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final columns = constraints.maxWidth >= 900
          ? 4
          : constraints.maxWidth >= 580
          ? 2
          : 1;
      final width = (constraints.maxWidth - ((columns - 1) * 11)) / columns;
      return Wrap(
        spacing: 11,
        runSpacing: 11,
        children: levels
            .map(
              (entry) => SizedBox(
                width: width,
                child: Container(
                  padding: const EdgeInsets.all(15),
                  decoration: BoxDecoration(
                    color: ScamColors.panel,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: ScamColors.line),
                  ),
                  child: Row(
                    children: [
                      Icon(entry.$4, color: entry.$3, size: 20),
                      const SizedBox(width: 11),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              entry.$1,
                              style: TextStyle(
                                color: entry.$3,
                                fontSize: 11,
                                fontWeight: FontWeight.w900,
                                letterSpacing: .5,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              entry.$2,
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            )
            .toList(growable: false),
      );
    },
  );
}

class ReportDetailSheet extends StatelessWidget {
  const ReportDetailSheet({super.key, required this.report});

  final ReportDetail report;

  @override
  Widget build(BuildContext context) => SafeArea(
    child: SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(22, 24, 22, 36),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'Analysis details',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
              IconButton(
                onPressed: () => Navigator.pop(context),
                icon: const Icon(Icons.close),
              ),
            ],
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              RiskScoreGauge(
                score: report.riskScore,
                level: report.riskLevel,
                size: 94,
              ),
              const SizedBox(width: 18),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  RiskPill(level: report.riskLevel),
                  const SizedBox(height: 8),
                  Text('Analysis by ${report.aiProvider.toUpperCase()}'),
                ],
              ),
            ],
          ),
          const SizedBox(height: 22),
          _DetailSection(title: 'Conversation', text: report.conversationText),
          _DetailSection(title: 'What we found', text: report.explanation),
          _DetailSection(
            title: 'Recommended action',
            text: report.recommendedAction,
          ),
          Text(
            'Detected tactics',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 10),
          buildTacticChips(report.detectedTactics),
          const SizedBox(height: 16),
          Text(
            'Confidence ${(report.confidence * 100).round()}%',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    ),
  );
}

class _DetailSection extends StatelessWidget {
  const _DetailSection({required this.title, required this.text});

  final String title;
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 17),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 7),
        Text(text.isEmpty ? 'No details provided.' : text),
      ],
    ),
  );
}
