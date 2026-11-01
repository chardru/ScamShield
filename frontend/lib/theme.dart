import 'package:flutter/material.dart';

class ScamColors {
  static const background = Color(0xFF0B1118);
  static const panel = Color(0xFF111B24);
  static const panelRaised = Color(0xFF17232E);
  static const line = Color(0xFF253541);
  static const mint = Color(0xFF58E0B0);
  static const text = Color(0xFFEAF2F4);
  static const muted = Color(0xFF8A9AA4);
  static const safe = Color(0xFF58D6A4);
  static const caution = Color(0xFFE8C55D);
  static const warning = Color(0xFFFF9A4D);
  static const danger = Color(0xFFFF626E);
}

ThemeData buildScamShieldTheme() {
  final scheme = ColorScheme.fromSeed(
    seedColor: ScamColors.mint,
    brightness: Brightness.dark,
    surface: ScamColors.panel,
  );
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    colorScheme: scheme,
    scaffoldBackgroundColor: ScamColors.background,
    canvasColor: ScamColors.background,
    dividerColor: ScamColors.line,
    textTheme: const TextTheme(
      headlineLarge: TextStyle(
        fontSize: 34,
        fontWeight: FontWeight.w800,
        letterSpacing: -.8,
      ),
      headlineMedium: TextStyle(
        fontSize: 27,
        fontWeight: FontWeight.w800,
        letterSpacing: -.5,
      ),
      titleLarge: TextStyle(fontSize: 19, fontWeight: FontWeight.w700),
      titleMedium: TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
      bodyLarge: TextStyle(fontSize: 15, height: 1.5),
      bodyMedium: TextStyle(fontSize: 13, height: 1.45),
      bodySmall: TextStyle(fontSize: 11, color: ScamColors.muted, height: 1.4),
    ).apply(bodyColor: ScamColors.text, displayColor: ScamColors.text),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: ScamColors.background,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: ScamColors.line),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: ScamColors.line),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: ScamColors.mint, width: 1.4),
      ),
      hintStyle: const TextStyle(color: ScamColors.muted),
    ),
    cardTheme: CardThemeData(
      color: ScamColors.panel,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: const BorderSide(color: ScamColors.line),
      ),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: ScamColors.panel,
      indicatorColor: ScamColors.mint.withValues(alpha: .14),
      labelTextStyle: WidgetStateProperty.resolveWith(
        (states) => TextStyle(
          color: states.contains(WidgetState.selected)
              ? ScamColors.mint
              : ScamColors.muted,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    ),
    navigationRailTheme: const NavigationRailThemeData(
      backgroundColor: ScamColors.background,
      selectedIconTheme: IconThemeData(color: ScamColors.mint),
      unselectedIconTheme: IconThemeData(color: ScamColors.muted),
      selectedLabelTextStyle: TextStyle(color: ScamColors.mint),
      unselectedLabelTextStyle: TextStyle(color: ScamColors.muted),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: ScamColors.mint,
        foregroundColor: ScamColors.background,
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(13)),
        textStyle: const TextStyle(fontWeight: FontWeight.w800),
      ),
    ),
  );
}
