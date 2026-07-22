import 'package:intl/intl.dart';

String formatAmount(double value, {int maximumDecimals = 1}) {
  if (value.abs() >= 100) {
    return value.toStringAsFixed(0);
  }
  if (value.abs() >= 10) {
    return value.toStringAsFixed(maximumDecimals.clamp(0, 1));
  }
  return value.toStringAsFixed(maximumDecimals);
}

String dayTitle(DateTime date) {
  final now = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);
  final value = DateTime(date.year, date.month, date.day);
  if (value == today) {
    return 'Today';
  }
  if (value == today.subtract(const Duration(days: 1))) {
    return 'Yesterday';
  }
  if (value == today.add(const Duration(days: 1))) {
    return 'Tomorrow';
  }
  return DateFormat('EEEE').format(value);
}

String daySubtitle(DateTime date) => DateFormat('MMM d, yyyy').format(date);
