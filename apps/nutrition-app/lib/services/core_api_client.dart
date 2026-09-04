import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/food.dart';

class CoreApiClient {
  CoreApiClient({http.Client? client}) : _client = client ?? http.Client();

  static const baseUrl = String.fromEnvironment(
    'OPENNUTRI_API_BASE_URL',
    defaultValue: 'https://open-nutri-baezarciel-5941s-projects.vercel.app',
  );

  final http.Client _client;
  final Map<String, FoodDetail> _detailCache = {};

  Future<FoodSearchResults> searchFoods(String query, {int limit = 30}) async {
    final normalized = query.trim();
    if (normalized.isEmpty) {
      return const FoodSearchResults(
        items: [],
        matchMode: 'all_terms',
        matchedTerms: [],
      );
    }
    final uri = Uri.parse(
      '$baseUrl/v1/foods/search',
    ).replace(queryParameters: {'q': normalized, 'limit': '$limit'});
    final response = await _client
        .get(uri)
        .timeout(const Duration(seconds: 30));
    final payload = _decode(response);
    return FoodSearchResults.fromJson(payload);
  }

  Future<FoodDetail> foodDetail(String foodId) async {
    final cached = _detailCache[foodId];
    if (cached != null) return cached;
    final uri = Uri.parse('$baseUrl/v1/foods/$foodId');
    final response = await _client
        .get(uri)
        .timeout(const Duration(seconds: 30));
    final detail = FoodDetail.fromJson(_decode(response));
    _detailCache[foodId] = detail;
    return detail;
  }

  Future<Map<String, dynamic>> health() async {
    final uri = Uri.parse('$baseUrl/health');
    final response = await _client
        .get(uri)
        .timeout(const Duration(seconds: 30));
    return _decode(response);
  }

  Map<String, dynamic> _decode(http.Response response) {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw CoreApiException('OpenNutri API returned ${response.statusCode}');
    }
    try {
      return jsonDecode(response.body) as Map<String, dynamic>;
    } on FormatException catch (error) {
      throw CoreApiException('OpenNutri API returned invalid data', error);
    }
  }
}

class CoreApiException implements Exception {
  const CoreApiException(this.message, [this.cause]);

  final String message;
  final Object? cause;

  @override
  String toString() => message;
}
