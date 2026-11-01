import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import 'api_models.dart';

const apiBaseUrlOverride = String.fromEnvironment('API_BASE_URL');

String defaultApiBaseUrl() {
  if (apiBaseUrlOverride.isNotEmpty) return apiBaseUrlOverride;
  if (kIsWeb) return 'http://127.0.0.1:8000';
  return switch (defaultTargetPlatform) {
    TargetPlatform.android => 'http://10.0.2.2:8000',
    _ => 'http://127.0.0.1:8000',
  };
}

class ScamShieldApiException implements Exception {
  const ScamShieldApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

class ScamShieldApi {
  ScamShieldApi({Dio? dio, String? baseUrl})
    : _dio =
          dio ??
          Dio(
            BaseOptions(
              baseUrl: baseUrl ?? defaultApiBaseUrl(),
              connectTimeout: const Duration(seconds: 5),
              sendTimeout: const Duration(seconds: 30),
              receiveTimeout: const Duration(seconds: 45),
              headers: const {'Accept': 'application/json'},
            ),
          );

  final Dio _dio;

  String get baseUrl => _dio.options.baseUrl;

  Future<AnalysisResult> analyze(
    String text, {
    String source = 'text_input',
  }) async {
    final response = await _request(
      () => _dio.post<Map<String, dynamic>>(
        '/api/analyze',
        data: {'text': text, 'source': source},
      ),
    );
    return AnalysisResult.fromJson(_asMap(response.data));
  }

  Future<List<ReportSummary>> getReports({
    int limit = 50,
    int offset = 0,
  }) async {
    final response = await _request(
      () => _dio.get<Map<String, dynamic>>(
        '/api/reports',
        queryParameters: {'limit': limit, 'offset': offset},
      ),
    );
    return _asMapList(response.data?['reports'])
        .map(ReportSummary.fromJson)
        .toList(growable: false);
  }

  Future<ReportDetail> getReport(String reportId) async {
    final response = await _request(
      () => _dio.get<Map<String, dynamic>>('/api/reports/$reportId'),
    );
    return ReportDetail.fromJson(_asMap(response.data));
  }

  Future<TranscriptionResult> transcribe({
    required String filename,
    required Uint8List bytes,
    String? language,
  }) async {
    final form = FormData.fromMap({
      'file': MultipartFile.fromBytes(bytes, filename: filename),
      if (language != null && language.isNotEmpty) 'language': language,
    });
    final response = await _request(
      () => _dio.post<Map<String, dynamic>>(
        '/api/transcribe',
        data: form,
        options: Options(
          contentType: Headers.multipartFormDataContentType,
          sendTimeout: const Duration(minutes: 2),
          receiveTimeout: const Duration(minutes: 2),
        ),
      ),
    );
    return TranscriptionResult.fromJson(_asMap(response.data));
  }

  Future<Map<String, dynamic>> getTranscriptionStatus() async {
    final response = await _request(
      () => _dio.get<Map<String, dynamic>>('/api/transcription-status'),
    );
    return _asMap(response.data);
  }

  Future<Map<String, dynamic>> getNotificationStatus() async {
    final response = await _request(
      () => _dio.get<Map<String, dynamic>>('/api/notifications/status'),
    );
    return _asMap(response.data);
  }

  Future<List<TrustedContact>> getTrustedContacts() async {
    final response = await _request(
      () => _dio.get<Map<String, dynamic>>('/api/notifications/contacts'),
    );
    return _asMapList(response.data?['contacts'])
        .map(TrustedContact.fromJson)
        .toList(growable: false);
  }

  Future<TrustedContact> createTrustedContact({
    required String name,
    required String chatId,
    required bool enabled,
  }) async {
    final response = await _request(
      () => _dio.post<Map<String, dynamic>>(
        '/api/notifications/contacts',
        data: {'name': name, 'chat_id': chatId, 'enabled': enabled},
      ),
    );
    return TrustedContact.fromJson(_asMap(response.data));
  }

  Future<TrustedContact> updateTrustedContact({
    required int contactId,
    required String name,
    required String chatId,
    required bool enabled,
  }) async {
    final response = await _request(
      () => _dio.put<Map<String, dynamic>>(
        '/api/notifications/contacts/$contactId',
        data: {'name': name, 'chat_id': chatId, 'enabled': enabled},
      ),
    );
    return TrustedContact.fromJson(_asMap(response.data));
  }

  Future<void> deleteTrustedContact(int contactId) async {
    await _request(
      () => _dio.delete<void>('/api/notifications/contacts/$contactId'),
    );
  }

  Future<ContactTestResult> testTrustedContact(int contactId) async {
    final response = await _request(
      () => _dio.post<Map<String, dynamic>>(
        '/api/notifications/contacts/$contactId/test',
      ),
    );
    return ContactTestResult.fromJson(_asMap(response.data));
  }

  Future<ContactTestBatch> testEnabledTrustedContacts() async {
    final response = await _request(
      () => _dio.post<Map<String, dynamic>>('/api/notifications/contacts/test'),
    );
    return ContactTestBatch.fromJson(_asMap(response.data));
  }

  Future<Response<T>> _request<T>(
    Future<Response<T>> Function() request,
  ) async {
    try {
      return await request();
    } on DioException catch (error) {
      final statusCode = error.response?.statusCode;
      final data = error.response?.data;
      final detail = data is Map ? data['detail'] : null;
      final validationMessage = _validationMessage(detail);
      final message = switch (error.type) {
        DioExceptionType.connectionTimeout => 'Could not connect to ScamShield. Check the backend address and try again.',
        DioExceptionType.sendTimeout || DioExceptionType.receiveTimeout =>
          'The request timed out. Please try again.',
        DioExceptionType.connectionError => 'ScamShield backend is unreachable. Confirm the API server is running.',
        _ => validationMessage ?? _responseError(detail, statusCode),
      };
      throw ScamShieldApiException(message, statusCode: statusCode);
    }
  }
}

String _responseError(dynamic detail, int? statusCode) => detail is String
    ? detail
    : 'Request failed${statusCode == null ? '' : ' (HTTP $statusCode)'}.';

String? _validationMessage(dynamic detail) {
  if (detail is! List || detail.isEmpty || detail.first is! Map) return null;
  final first = detail.first as Map;
  final location = first['loc'];
  final field = location is List && location.isNotEmpty
      ? location.last.toString()
      : 'input';
  final message = first['msg'];
  if (message is! String) return null;
  if (field == 'chat_id') {
    return 'Enter a valid numeric Telegram Chat ID (5–20 digits; a leading minus is allowed for groups).';
  }
  if (field == 'name') {
    return 'Enter a family member name between 1 and 80 characters.';
  }
  return 'Invalid $field: $message';
}

Map<String, dynamic> _asMap(dynamic value) =>
    value is Map<String, dynamic> ? value : const <String, dynamic>{};

List<Map<String, dynamic>> _asMapList(dynamic value) {
  if (value is! List) return const [];
  return value.whereType<Map<String, dynamic>>().toList(growable: false);
}
