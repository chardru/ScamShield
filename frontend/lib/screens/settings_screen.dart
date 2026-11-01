import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../main.dart';
import 'trusted_contacts_screen.dart';
import '../theme.dart';
import '../widgets/common_widgets.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final transcription = ref.watch(transcriptionStatusProvider);
    final notifications = ref.watch(notificationStatusProvider);
    final api = ref.watch(apiProvider);
    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(transcriptionStatusProvider);
        ref.invalidate(notificationStatusProvider);
        await Future.wait([
          ref.read(transcriptionStatusProvider.future),
          ref.read(notificationStatusProvider.future),
        ]);
      },
      child: ListView(
        padding: const EdgeInsets.fromLTRB(24, 10, 24, 36),
        children: [
          Text(
            'Settings & status',
            style: Theme.of(context).textTheme.headlineLarge,
          ),
          const SizedBox(height: 7),
          Text(
            'Check connected services and supported audio formats.',
            style: Theme.of(context).textTheme.bodyLarge
                ?.copyWith(color: ScamColors.muted),
          ),
          const SizedBox(height: 22),
          const SectionHeading(
            title: 'Backend connection',
            subtitle: 'API base URL for this device',
          ),
          const SizedBox(height: 11),
          Panel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const _StatusRow(
                  label: 'Base URL',
                  value: null,
                  icon: Icons.link,
                ),
                const SizedBox(height: 7),
                SelectableText(
                  api.baseUrl,
                  style: const TextStyle(color: ScamColors.mint),
                ),
                const SizedBox(height: 9),
                Text(
                  'Android emulator: http://10.0.2.2:8000  ·  Web/desktop: http://127.0.0.1:8000',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          const SectionHeading(
            title: 'Audio transcription',
            subtitle: 'Live status from GET /api/transcription-status',
          ),
          const SizedBox(height: 11),
          transcription.when(
            loading: () => const _LoadingPanel(),
            error: (error, _) => ErrorNotice(
              message: error.toString(),
              onRetry: () => ref.invalidate(transcriptionStatusProvider),
            ),
            data: (status) => Panel(
              child: Column(
                children: [
                  _StatusRow(
                    label: 'Sarvam AI',
                    value: status['sarvam_configured'] == true
                        ? 'Configured'
                        : 'Demo mode',
                    icon: Icons.graphic_eq,
                    good: status['sarvam_configured'] == true,
                  ),
                  const Divider(height: 24),
                  _StatusRow(
                    label: 'Upload limit',
                    value: '${status['max_size_mb'] ?? 25} MB',
                    icon: Icons.upload_file,
                  ),
                  const SizedBox(height: 10),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      'Formats: ${_formats(status['supported_formats'])}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),
          const SectionHeading(
            title: 'Trusted contact notifications',
            subtitle: 'Live status from GET /api/notifications/status',
          ),
          const SizedBox(height: 11),
          notifications.when(
            loading: () => const _LoadingPanel(),
            error: (error, _) => ErrorNotice(
              message: error.toString(),
              onRetry: () => ref.invalidate(notificationStatusProvider),
            ),
            data: (status) {
              final telegram = status['telegram'] is Map
                  ? status['telegram'] as Map
                  : const <String, dynamic>{};
              return Panel(
                child: Column(
                  children: [
                    _StatusRow(
                      label: 'Telegram Bot API',
                      value: telegram['configured'] == true
                          ? 'Connected'
                          : 'Not configured',
                      icon: Icons.send_outlined,
                      good: telegram['configured'] == true,
                    ),
                    const SizedBox(height: 11),
                    Text(
                      'High-risk alerts contain a risk summary and do not include full private transcripts.',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              );
            },
          ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => const TrustedContactsScreen(),
              ),
            ),
            icon: const Icon(Icons.family_restroom),
            label: const Text('Manage trusted family members'),
          ),
          const SizedBox(height: 20),
          const Panel(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.privacy_tip_outlined, color: ScamColors.mint),
                SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'ScamShield analyzes content you choose to submit. It does not record calls or access your microphone in the background.',
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

String _formats(dynamic value) => value is List
    ? value.map((item) => item.toString().toUpperCase()).join(', ')
    : 'Not available';

class _StatusRow extends StatelessWidget {
  const _StatusRow({
    required this.label,
    required this.value,
    required this.icon,
    this.good,
  });

  final String label;
  final String? value;
  final IconData icon;
  final bool? good;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Icon(
        icon,
        size: 19,
        color: good == null
            ? ScamColors.muted
            : good!
            ? ScamColors.safe
            : ScamColors.caution,
      ),
      const SizedBox(width: 10),
      Expanded(
        child: Text(label, style: Theme.of(context).textTheme.titleMedium),
      ),
      if (value != null)
        Text(
          value!,
          style: TextStyle(
            color: good == null
                ? ScamColors.text
                : good!
                ? ScamColors.safe
                : ScamColors.caution,
            fontWeight: FontWeight.w700,
          ),
        ),
    ],
  );
}

class _LoadingPanel extends StatelessWidget {
  const _LoadingPanel();

  @override
  Widget build(BuildContext context) =>
      const Panel(child: Center(child: CircularProgressIndicator()));
}
