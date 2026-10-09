import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import 'auth_store.dart';

class AppException implements Exception {
  final String message;
  final int? statusCode;
  const AppException(this.message, {this.statusCode});
  @override
  String toString() => message;
}

class ErrorHandler {
  static String message(Object error) {
    if (error is AppException) return error.message;
    if (error is TimeoutException) return 'ارتباط با سرور طول کشید. دوباره تلاش کنید.';
    if (error is SocketException) return 'اتصال اینترنت در دسترس نیست. اطلاعات محلی همچنان قابل استفاده است.';
    return 'عملیات انجام نشد. لطفاً دوباره تلاش کنید.';
  }

  static String fromStatus(int status, String raw) {
    String? detail;
    try {
      final decoded = jsonDecode(raw);
      if (decoded is Map && decoded['detail'] != null) {
        detail = decoded['detail'].toString();
      }
    } catch (_) {}
    if (status == 400 || status == 422) return 'اطلاعات واردشده معتبر نیست${detail == null ? '.' : ': $detail'}';
    if (status == 401) return 'نشست شما منقضی شده است. دوباره وارد شوید.';
    if (status == 403) return 'اجازه انجام این عملیات را ندارید.';
    if (status == 404) return 'مورد موردنظر پیدا نشد.';
    if (status == 409) return 'این اطلاعات قبلاً ثبت شده است.';
    if (status >= 500) return 'خطایی در سرور رخ داد. کمی بعد دوباره تلاش کنید.';
    return 'عملیات انجام نشد. لطفاً دوباره تلاش کنید.';
  }
}

class Api {
  static const base = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://planner.datholding.ir/api',
  );

  static Future<dynamic> call(
    String path, {
    String method = 'GET',
    Object? body,
    bool retry = true,
  }) async {
    try {
      var t = await AuthStore.access();
      final req = http.Request(method, Uri.parse('$base$path'))
        ..headers['Content-Type'] = 'application/json'
        ..headers['Accept'] = 'application/json';
      if (t != null && t.isNotEmpty) req.headers['Authorization'] = 'Bearer $t';
      if (body != null) req.body = jsonEncode(body);
      final streamed = await req.send().timeout(const Duration(seconds: 20));
      final txt = await streamed.stream.bytesToString();
      if (streamed.statusCode == 401 && retry && await _refresh()) {
        return call(path, method: method, body: body, retry: false);
      }
      if (streamed.statusCode >= 400) {
        throw AppException(
          ErrorHandler.fromStatus(streamed.statusCode, txt),
          statusCode: streamed.statusCode,
        );
      }
      return txt.isEmpty ? null : jsonDecode(txt);
    } on AppException {
      rethrow;
    } on TimeoutException {
      throw const AppException('ارتباط با سرور طول کشید. دوباره تلاش کنید.');
    } on SocketException {
      throw const AppException('اتصال اینترنت در دسترس نیست. اطلاعات محلی همچنان قابل استفاده است.');
    } catch (_) {
      throw const AppException('عملیات انجام نشد. لطفاً دوباره تلاش کنید.');
    }
  }

  static Future<bool> _refresh() async {
    final r = await AuthStore.refresh();
    if (r == null || r.isEmpty) return false;
    try {
      final res = await http
          .post(
            Uri.parse('$base/auth/refresh'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'refresh_token': r, 'platform': 'android-ios'}),
          )
          .timeout(const Duration(seconds: 15));
      if (res.statusCode >= 400) return false;
      await AuthStore.save(Map<String, dynamic>.from(jsonDecode(res.body)));
      return true;
    } catch (_) {
      return false;
    }
  }
}
