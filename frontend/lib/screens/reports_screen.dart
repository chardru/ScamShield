import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../main.dart';
import '../theme.dart';
import '../widgets/common_widgets.dart';
import 'dashboard_screen.dart';

class ReportsScreen extends ConsumerWidget {
  const ReportsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final reports = ref.watch(reportsProvider);
    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(reportsProvider);
        await ref.read(reportsProvider.future);
      },
      child: ListView(
        padding: const EdgeInsets.fromLTRB(24, 10, 24, 36),
        children: [
          Text(
            'Report history',
            style: Theme.of(context).textTheme.headlineLarge,
          ),
          const SizedBox(height: 7),
          Text(
            'Review your saved conversation analyses.',
            style: Theme.of(context).textTheme.bodyLarge
                ?.copyWith(color: ScamColors.muted),
          ),
          const SizedBox(height: 22),
          reports.when(
            loading: () => const Center(
              child: Padding(
                padding: EdgeInsets.all(32),
                child: CircularProgressIndicator(),
              ),
            ),
            error: (error, _) => ErrorNotice(
              message: error.toString(),
              onRetry: () => ref.invalidate(reportsProvider),
            ),
            data: (items) => items.isEmpty
                ? const EmptyNotice(
                    title: 'Nothing in your history yet',
                    message:
                        'Analyze a conversation to create your first report.',
                    icon: Icons.receipt_long_outlined,
                  )
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${items.length} recent ${items.length == 1 ? 'report' : 'reports'}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 11),
                      for (final report in items) ...[
                        ReportListTile(
                          report: report,
                          onTap: () => _openDetail(context, ref, report.id),
                        ),
                        const SizedBox(height: 10),
                      ],
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  Future<void> _openDetail(
    BuildContext context,
    WidgetRef ref,
    String id,
  ) async {
    try {
      final detail = await ref.read(apiProvider).getReport(id);
      if (context.mounted) {
        await showModalBottomSheet<void>(
          context: context,
          isScrollControlled: true,
          backgroundColor: ScamColors.panel,
          builder: (_) => ReportDetailSheet(report: detail),
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
