import 'package:flutter/material.dart';

import '../api/api_models.dart';
import '../theme.dart';

Color riskColor(String level) => switch (level.toUpperCase()) {
  'CAUTION' => ScamColors.caution,
  'WARNING' => ScamColors.warning,
  'DANGER' => ScamColors.danger,
  _ => ScamColors.safe,
};

String riskLabel(String level) => switch (level.toUpperCase()) {
  'CAUTION' => 'CAUTION',
  'WARNING' => 'WARNING',
  'DANGER' => 'DANGER',
  _ => 'SAFE',
};

class RiskPill extends StatelessWidget {
  const RiskPill({super.key, required this.level});

  final String level;

  @override
  Widget build(BuildContext context) {
    final color = riskColor(level);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
      decoration: BoxDecoration(
        color: color.withValues(alpha: .11),
        borderRadius: BorderRadius.circular(30),
        border: Border.all(color: color.withValues(alpha: .38)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(_riskIcon(level), size: 14, color: color),
          const SizedBox(width: 6),
          Text(
            riskLabel(level),
            style: TextStyle(
              fontSize: 10,
              letterSpacing: .6,
              fontWeight: FontWeight.w900,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}

IconData _riskIcon(String level) => switch (level.toUpperCase()) {
  'CAUTION' => Icons.info_outline,
  'WARNING' => Icons.warning_amber_rounded,
  'DANGER' => Icons.gpp_bad_outlined,
  _ => Icons.verified_user_outlined,
};

class SectionHeading extends StatelessWidget {
  const SectionHeading({
    super.key,
    required this.title,
    this.subtitle,
    this.trailing,
  });

  final String title;
  final String? subtitle;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.end,
    children: [
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleLarge),
            if (subtitle != null) ...[
              const SizedBox(height: 4),
              Text(subtitle!, style: Theme.of(context).textTheme.bodySmall),
            ],
          ],
        ),
      ),
      ?trailing,
    ],
  );
}

class Panel extends StatelessWidget {
  const Panel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(20),
  });

  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: padding,
    decoration: BoxDecoration(
      color: ScamColors.panel,
      borderRadius: BorderRadius.circular(18),
      border: Border.all(color: ScamColors.line),
    ),
    child: child,
  );
}

class ErrorNotice extends StatelessWidget {
  const ErrorNotice({super.key, required this.message, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) => Panel(
    child: Row(
      children: [
        const Icon(Icons.cloud_off_outlined, color: ScamColors.warning),
        const SizedBox(width: 12),
        Expanded(child: Text(message)),
        ?(onRetry == null
            ? null
            : TextButton(onPressed: onRetry, child: const Text('Retry'))),
      ],
    ),
  );
}

class EmptyNotice extends StatelessWidget {
  const EmptyNotice({
    super.key,
    required this.title,
    required this.message,
    this.icon = Icons.inbox_outlined,
  });

  final String title;
  final String message;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Panel(
    child: Column(
      children: [
        Icon(icon, size: 34, color: ScamColors.muted),
        const SizedBox(height: 12),
        Text(title, style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 5),
        Text(
          message,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
    ),
  );
}

class RiskScoreGauge extends StatelessWidget {
  const RiskScoreGauge({
    super.key,
    required this.score,
    required this.level,
    this.size = 120,
  });

  final int score;
  final String level;
  final double size;

  @override
  Widget build(BuildContext context) {
    final color = riskColor(level);
    return SizedBox(
      width: size,
      height: size,
      child: Stack(
        alignment: Alignment.center,
        children: [
          SizedBox(
            width: size,
            height: size,
            child: CircularProgressIndicator(
              value: (score.clamp(0, 100)) / 100,
              strokeWidth: 9,
              strokeCap: StrokeCap.round,
              backgroundColor: color.withValues(alpha: .12),
              valueColor: AlwaysStoppedAnimation(color),
            ),
          ),
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                '$score',
                style: TextStyle(
                  fontSize: size * .29,
                  fontWeight: FontWeight.w900,
                  color: color,
                ),
              ),
              Text('/ 100', style: Theme.of(context).textTheme.bodySmall),
            ],
          ),
        ],
      ),
    );
  }
}

class ReportListTile extends StatelessWidget {
  const ReportListTile({super.key, required this.report, required this.onTap});

  final ReportSummary report;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = riskColor(report.riskLevel);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(15),
      child: Container(
        padding: const EdgeInsets.all(15),
        decoration: BoxDecoration(
          color: ScamColors.panel,
          borderRadius: BorderRadius.circular(15),
          border: Border.all(color: ScamColors.line),
        ),
        child: Row(
          children: [
            Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(
                color: color.withValues(alpha: .11),
                borderRadius: BorderRadius.circular(13),
              ),
              child: Icon(Icons.shield_outlined, color: color),
            ),
            const SizedBox(width: 13),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    report.conversationText,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 5),
                  Text(
                    '${report.source.replaceAll('_', ' ')}  ·  ${_formatDate(report.createdAt)}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 10),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  '${report.riskScore}',
                  style: TextStyle(fontWeight: FontWeight.w900, color: color),
                ),
                const SizedBox(height: 5),
                RiskPill(level: report.riskLevel),
              ],
            ),
            const SizedBox(width: 5),
            const Icon(Icons.chevron_right, color: ScamColors.muted),
          ],
        ),
      ),
    );
  }
}

String _formatDate(String? value) {
  if (value == null) return 'Recently';
  final date = DateTime.tryParse(value)?.toLocal();
  if (date == null) return 'Recently';
  return '${date.day.toString().padLeft(2, '0')}/${date.month.toString().padLeft(2, '0')}/${date.year}';
}

Widget buildTacticChips(List<String> tactics) {
  if (tactics.isEmpty) {
    return const Text(
      'No scam tactics detected.',
      style: TextStyle(color: ScamColors.muted),
    );
  }
  return Wrap(
    spacing: 8,
    runSpacing: 8,
    children: tactics
        .map(
          (tactic) => Chip(
            label: Text(tactic, style: const TextStyle(fontSize: 11)),
            side: const BorderSide(color: ScamColors.line),
            backgroundColor: ScamColors.panelRaised,
            visualDensity: VisualDensity.compact,
          ),
        )
        .toList(growable: false),
  );
}
