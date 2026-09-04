import 'package:flutter/material.dart';

class AppTheme {
  static const _lightScheme = ColorScheme(
    brightness: Brightness.light,
    primary: Color(0xFF0A6C4F),
    onPrimary: Colors.white,
    primaryContainer: Color(0xFFD8F3E6),
    onPrimaryContainer: Color(0xFF0B3D2C),
    secondary: Color(0xFF2B617A),
    onSecondary: Colors.white,
    secondaryContainer: Color(0xFFD8EEF7),
    onSecondaryContainer: Color(0xFF173A61),
    tertiary: Color(0xFFC66A24),
    onTertiary: Colors.white,
    tertiaryContainer: Color(0xFFFFE2C5),
    onTertiaryContainer: Color(0xFF582D06),
    error: Color(0xFFBA1A1A),
    onError: Colors.white,
    errorContainer: Color(0xFFFFDAD6),
    onErrorContainer: Color(0xFF410002),
    surface: Color(0xFFF8F9F4),
    onSurface: Color(0xFF1A1C1A),
    surfaceContainerHighest: Color(0xFFE3E8E3),
    onSurfaceVariant: Color(0xFF424944),
    outline: Color(0xFF727973),
    outlineVariant: Color(0xFFC2C9C3),
    shadow: Colors.black,
    scrim: Colors.black,
    inverseSurface: Color(0xFF2F312F),
    onInverseSurface: Color(0xFFF0F1EF),
    inversePrimary: Color(0xFF8DD5B1),
  );

  static const _darkScheme = ColorScheme(
    brightness: Brightness.dark,
    primary: Color(0xFF8DD5B1),
    onPrimary: Color(0xFF003824),
    primaryContainer: Color(0xFF005137),
    onPrimaryContainer: Color(0xFFA9F2CC),
    secondary: Color(0xFFAFCBF0),
    onSecondary: Color(0xFF143154),
    secondaryContainer: Color(0xFF2D486C),
    onSecondaryContainer: Color(0xFFD6E4FF),
    tertiary: Color(0xFFFFB875),
    onTertiary: Color(0xFF512400),
    tertiaryContainer: Color(0xFF743700),
    onTertiaryContainer: Color(0xFFFFDCC0),
    error: Color(0xFFFFB4AB),
    onError: Color(0xFF690005),
    errorContainer: Color(0xFF93000A),
    onErrorContainer: Color(0xFFFFDAD6),
    surface: Color(0xFF111411),
    onSurface: Color(0xFFE2E3E0),
    surfaceContainerHighest: Color(0xFF414844),
    onSurfaceVariant: Color(0xFFC1C9C2),
    outline: Color(0xFF8B938C),
    outlineVariant: Color(0xFF414844),
    shadow: Colors.black,
    scrim: Colors.black,
    inverseSurface: Color(0xFFE2E3E0),
    onInverseSurface: Color(0xFF2F312F),
    inversePrimary: Color(0xFF146B4D),
  );

  static ThemeData get light => _theme(_lightScheme);
  static ThemeData get dark => _theme(_darkScheme);

  static ThemeData _theme(ColorScheme scheme) {
    final base = ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: scheme.surface,
    );
    return base.copyWith(
      textTheme: base.textTheme.apply(
        bodyColor: scheme.onSurface,
        displayColor: scheme.onSurface,
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: scheme.surface,
        foregroundColor: scheme.onSurface,
        elevation: 0,
        scrolledUnderElevation: 1,
        centerTitle: false,
        titleTextStyle: base.textTheme.titleLarge?.copyWith(
          color: scheme.onSurface,
          fontWeight: FontWeight.w800,
          letterSpacing: -0.4,
        ),
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: BorderSide(
            color: scheme.outlineVariant.withValues(alpha: 0.72),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surfaceContainerHighest.withValues(alpha: 0.38),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        height: 74,
        indicatorColor: scheme.primaryContainer,
        labelTextStyle: WidgetStatePropertyAll(
          base.textTheme.labelMedium?.copyWith(letterSpacing: 0),
        ),
      ),
      dividerTheme: DividerThemeData(color: scheme.outlineVariant, space: 1),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(0, 50),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(0, 50),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
    );
  }
}
