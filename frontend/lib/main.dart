import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api/api_models.dart';
import 'api/scamshield_api.dart';
import 'screens/analyzer_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/reports_screen.dart';
import 'screens/settings_screen.dart';
import 'theme.dart';

final apiProvider = Provider<ScamShieldApi>((ref) => ScamShieldApi());

final reportsProvider = FutureProvider(
  (ref) => ref.watch(apiProvider).getReports(),
);
final transcriptionStatusProvider = FutureProvider(
  (ref) => ref.watch(apiProvider).getTranscriptionStatus(),
);
final notificationStatusProvider = FutureProvider(
  (ref) => ref.watch(apiProvider).getNotificationStatus(),
);
final trustedContactsProvider = FutureProvider<List<TrustedContact>>(
  (ref) => ref.watch(apiProvider).getTrustedContacts(),
);

void main() {
  runApp(const ProviderScope(child: ScamShieldApp()));
}

class ScamShieldApp extends StatelessWidget {
  const ScamShieldApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'ScamShield',
    debugShowCheckedModeBanner: false,
    theme: buildScamShieldTheme(),
    home: const ScamShieldShell(),
  );
}

class ScamShieldShell extends StatefulWidget {
  const ScamShieldShell({super.key});

  @override
  State<ScamShieldShell> createState() => _ScamShieldShellState();
}

class _ScamShieldShellState extends State<ScamShieldShell> {
  int _selectedIndex = 0;

  static const _destinations = [
    NavigationDestination(
      icon: Icon(Icons.space_dashboard_outlined),
      selectedIcon: Icon(Icons.space_dashboard),
      label: 'Overview',
    ),
    NavigationDestination(
      icon: Icon(Icons.radar_outlined),
      selectedIcon: Icon(Icons.radar),
      label: 'Analyze',
    ),
    NavigationDestination(
      icon: Icon(Icons.receipt_long_outlined),
      selectedIcon: Icon(Icons.receipt_long),
      label: 'Reports',
    ),
    NavigationDestination(
      icon: Icon(Icons.settings_outlined),
      selectedIcon: Icon(Icons.settings),
      label: 'Settings',
    ),
  ];

  static const _railDestinations = [
    NavigationRailDestination(
      icon: Icon(Icons.space_dashboard_outlined),
      selectedIcon: Icon(Icons.space_dashboard),
      label: Text('Overview'),
    ),
    NavigationRailDestination(
      icon: Icon(Icons.radar_outlined),
      selectedIcon: Icon(Icons.radar),
      label: Text('Analyze'),
    ),
    NavigationRailDestination(
      icon: Icon(Icons.receipt_long_outlined),
      selectedIcon: Icon(Icons.receipt_long),
      label: Text('Reports'),
    ),
    NavigationRailDestination(
      icon: Icon(Icons.settings_outlined),
      selectedIcon: Icon(Icons.settings),
      label: Text('Settings'),
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 900;
    final pages = [
      DashboardScreen(onAnalyze: () => _select(1), onReports: () => _select(2)),
      const AnalyzerScreen(),
      const ReportsScreen(),
      const SettingsScreen(),
    ];

    return Scaffold(
      body: SafeArea(
        child: Row(
          children: [
            if (wide)
              NavigationRail(
                selectedIndex: _selectedIndex,
                onDestinationSelected: _select,
                labelType: NavigationRailLabelType.all,
                leading: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 22),
                  child: Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      color: ScamColors.mint.withValues(alpha: .12),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: const Icon(
                      Icons.shield_moon,
                      color: ScamColors.mint,
                    ),
                  ),
                ),
                destinations: _railDestinations,
              ),
            Expanded(
              child: Column(
                children: [
                  _TopBar(wide: wide, onSettings: () => _select(3)),
                  Expanded(
                    child: IndexedStack(index: _selectedIndex, children: pages),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: wide
          ? null
          : NavigationBar(
              selectedIndex: _selectedIndex,
              onDestinationSelected: _select,
              destinations: _destinations,
            ),
    );
  }

  void _select(int index) => setState(() => _selectedIndex = index);
}

class _TopBar extends StatelessWidget {
  const _TopBar({required this.wide, required this.onSettings});

  final bool wide;
  final VoidCallback onSettings;

  @override
  Widget build(BuildContext context) => Padding(
    padding: EdgeInsets.fromLTRB(wide ? 30 : 20, 17, wide ? 30 : 20, 13),
    child: Row(
      children: [
        if (!wide) ...[
          const Icon(Icons.shield_moon, color: ScamColors.mint, size: 25),
          const SizedBox(width: 10),
        ],
        Text(
          'SCAMSHIELD',
          style: Theme.of(context).textTheme.titleMedium
              ?.copyWith(fontWeight: FontWeight.w900, letterSpacing: 1.3),
        ),
        const Spacer(),
        const _ConnectionPill(),
        const SizedBox(width: 12),
        IconButton(
          tooltip: 'Settings',
          onPressed: onSettings,
          icon: const Icon(Icons.settings_outlined),
        ),
      ],
    ),
  );
}

class _ConnectionPill extends ConsumerWidget {
  const _ConnectionPill();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final health = ref.watch(apiHealthProvider);
    final connected = health.asData?.value == true;
    final unavailable = health.asData?.value == false;
    final statusColor = connected
        ? ScamColors.mint
        : unavailable
        ? ScamColors.warning
        : ScamColors.muted;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 8),
      decoration: BoxDecoration(
        color: connected
            ? ScamColors.mint.withValues(alpha: .1)
            : unavailable
            ? ScamColors.warning.withValues(alpha: .1)
            : ScamColors.panel,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: connected
              ? ScamColors.mint.withValues(alpha: .3)
              : unavailable
              ? ScamColors.warning.withValues(alpha: .3)
              : ScamColors.line,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 7,
            height: 7,
            decoration: BoxDecoration(
              color: statusColor,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 7),
          Text(
            connected
                ? 'API connected'
                : unavailable
                ? 'API unavailable'
                : 'Connecting',
          ),
        ],
      ),
    );
  }
}

final apiHealthProvider = FutureProvider<bool>((ref) async {
  try {
    await ref.watch(apiProvider).getTranscriptionStatus();
    return true;
  } catch (_) {
    return false;
  }
});
