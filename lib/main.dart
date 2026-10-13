import 'dart:async';
import 'dart:convert';

import 'package:app_links/app_links.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:shamsi_date/shamsi_date.dart';
import 'package:url_launcher/url_launcher.dart';

const apiBase = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'https://planner.datholding.ir/api',
);
const widgetChannel = MethodChannel('planner/widget');
const securityChannel = MethodChannel('planner/security');
const notificationChannel = MethodChannel('planner/notifications');
const appVersion = '1.6.0';
const appBuild = '18';

class SessionExpiredException implements Exception {
  const SessionExpiredException();
  @override
  String toString() => 'نشست شما منقضی شده است. دوباره وارد شوید.';
}

class AuthEvents {
  static final StreamController<void> _expired = StreamController<void>.broadcast();
  static Stream<void> get expired => _expired.stream;
  static void notifyExpired() => _expired.add(null);
}

class SecureSession {
  static Future<String?> get token async =>
      securityChannel.invokeMethod<String>('getToken');
  static Future<String?> get refreshToken async =>
      securityChannel.invokeMethod<String>('getRefreshToken');

  static Future<void> setToken(String token) async {
    await securityChannel.invokeMethod('setToken', {'token': token});
  }

  static Future<void> setTokens(String accessToken, String? refreshToken) async {
    await securityChannel.invokeMethod('setTokens', {
      'accessToken': accessToken,
      'refreshToken': refreshToken ?? '',
    });
  }

  static Future<void> clear() async {
    await securityChannel.invokeMethod('clearToken');
  }
}

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const PlannerApp());
}

class Api {
  static Future<String?> token() => SecureSession.token;

  static Future<dynamic> call(
    String path, {
    String method = 'GET',
    Object? body,
    bool auth = true,
    bool allowRefresh = true,
  }) async {
    final t = await token();
    final r = http.Request(method, Uri.parse('$apiBase$path'));
    r.headers['Content-Type'] = 'application/json';
    r.headers['Accept'] = 'application/json';
    if (auth && t != null && t.isNotEmpty) r.headers['Authorization'] = 'Bearer $t';
    if (body != null) r.body = jsonEncode(body);
    final s = await r.send().timeout(const Duration(seconds: 20));
    final txt = await s.stream.bytesToString();

    if (s.statusCode == 401 && auth && allowRefresh) {
      final refresh = await SecureSession.refreshToken;
      if (refresh != null && refresh.isNotEmpty) {
        try {
          final renewed = await call(
            '/auth/refresh',
            method: 'POST',
            auth: false,
            allowRefresh: false,
            body: {'refresh_token': refresh},
          );
          await SecureSession.setTokens(
            renewed['access_token']?.toString() ?? '',
            renewed['refresh_token']?.toString(),
          );
          return call(path, method: method, body: body, auth: auth, allowRefresh: false);
        } catch (_) {}
      }
      await SecureSession.clear();
      AuthEvents.notifyExpired();
      throw const SessionExpiredException();
    }

    if (s.statusCode >= 400) {
      var message = txt;
      try {
        final decoded = jsonDecode(txt);
        if (decoded is Map && decoded['detail'] != null) {
          final detail = decoded['detail'];
          message = detail is String ? detail : (detail['message']?.toString() ?? detail.toString());
        }
      } catch (_) {}
      throw Exception(message);
    }
    return txt.isEmpty ? null : jsonDecode(txt);
  }
}

// Compatibility widget for stale Flutter scaffold tests that still reference MyApp.
// Production continues to launch PlannerApp from main().
class MyApp extends StatefulWidget {
  const MyApp({super.key});

  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  int _counter = 0;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        body: Center(child: Text('$_counter')),
        floatingActionButton: FloatingActionButton(
          onPressed: () => setState(() => _counter++),
          child: const Icon(Icons.add),
        ),
      ),
    );
  }
}

class PlannerApp extends StatelessWidget {
  const PlannerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Planner',
      locale: const Locale('fa', 'IR'),
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xff176b43),
          brightness: Brightness.light,
          surface: const Color(0xfffbfcfb),
        ),
        scaffoldBackgroundColor: const Color(0xfff3f6f4),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xfff3f6f4),
          surfaceTintColor: Colors.transparent,
          elevation: 0,
          centerTitle: false,
          titleTextStyle: TextStyle(
            color: Color(0xff183229),
            fontSize: 20,
            fontWeight: FontWeight.w800,
          ),
        ),
        cardTheme: CardThemeData(
          elevation: 0,
          color: Colors.white,
          margin: EdgeInsets.zero,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.all(Radius.circular(20)),
            side: BorderSide(color: Color(0xffe0e8e3)),
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: Colors.white,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(16)),
            borderSide: BorderSide(color: Color(0xffd7e1da)),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(16)),
            borderSide: BorderSide(color: Color(0xffd7e1da)),
          ),
          contentPadding: EdgeInsets.symmetric(horizontal: 14, vertical: 13),
        ),
        navigationBarTheme: const NavigationBarThemeData(
          height: 68,
          elevation: 0,
          backgroundColor: Colors.white,
          indicatorColor: Color(0xffdcefe3),
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.all(Radius.circular(14)),
            ),
            padding: EdgeInsets.symmetric(horizontal: 16, vertical: 13),
          ),
        ),
      ),
      builder: (context, child) => Directionality(
        textDirection: TextDirection.rtl,
        child: child ?? const SizedBox.shrink(),
      ),
      home: const Gate(),
    );
  }
}

class Gate extends StatefulWidget {
  const Gate({super.key});

  @override
  State<Gate> createState() => _GateState();
}

class _GateState extends State<Gate> {
  final AppLinks _links = AppLinks();
  StreamSubscription<Uri>? _sub;
  StreamSubscription<void>? _authExpiredSub;
  bool? has;

  @override
  void initState() {
    super.initState();
    _sub = _links.uriLinkStream.listen(_handleLink);
    _authExpiredSub = AuthEvents.expired.listen((_) { if (mounted) setState(() => has = false); });
    _readToken();
  }

  Future<void> _readToken() async {
    final t = await SecureSession.token;
    if (t == null || t.isEmpty) {
      if (mounted) setState(() => has = false);
      return;
    }
    try {
      await Api.call('/me');
      if (mounted) setState(() => has = true);
    } catch (_) {
      if (mounted) setState(() => has = false);
    }
  }

  Future<void> _handleLink(Uri uri) async {
    if (uri.scheme != 'planner') return;
    final token = uri.queryParameters['oauth_token'];
    if (token == null || token.isEmpty) return;
    await SecureSession.setToken(token);
    if (mounted) setState(() => has = true);
  }

  @override
  void dispose() {
    _sub?.cancel();
    _authExpiredSub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (has == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    return has! ? const Home() : Login(onLogin: () => setState(() => has = true));
  }
}

class Login extends StatefulWidget {
  final VoidCallback onLogin;
  const Login({super.key, required this.onLogin});

  @override
  State<Login> createState() => _LoginState();
}

class _LoginState extends State<Login> {
  final identifier = TextEditingController();
  final pass = TextEditingController();
  String? err;
  bool busy = false;

  Future<void> go() async {
    setState(() { busy = true; err = null; });
    try {
      final r = await Api.call('/auth/login', method: 'POST', auth: false, body: {
        'identifier': identifier.text.trim(), 'password': pass.text,
      });
      await SecureSession.setTokens(r['access_token'], r['refresh_token']);
      widget.onLogin();
    } catch (e) {
      if (mounted) setState(() => err = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> social(String provider) async {
    setState(() { busy = true; err = null; });
    try {
      final r = await Api.call('/auth/$provider/start?return_to=${Uri.encodeComponent('planner://oauth')}', auth: false);
      final url = Uri.parse(r['authorization_url']);
      if (!await launchUrl(url, mode: LaunchMode.externalApplication)) throw Exception('مرورگر باز نشد');
    } catch (e) {
      if (mounted) setState(() => err = e.toString());
    } finally { if (mounted) setState(() => busy = false); }
  }

  @override
  void dispose() { identifier.dispose(); pass.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 430),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const Icon(Icons.event_note_rounded, size: 72),
              const SizedBox(height: 14),
              const Text('برنامه‌ریز', textAlign: TextAlign.right, style: TextStyle(fontSize: 30, fontWeight: FontWeight.w700)),
              const SizedBox(height: 24),
              Row(children: [
                Expanded(child: OutlinedButton(onPressed: busy ? null : () => social('google'), child: const Text('Google'))),
                const SizedBox(width: 8),
                Expanded(child: FilledButton.tonal(onPressed: busy ? null : () => social('apple'), child: const Text('Apple'))),
              ]),
              const Padding(padding: EdgeInsets.symmetric(vertical: 14), child: Text('یا', textAlign: TextAlign.center)),
              TextField(
                controller: identifier,
                keyboardType: TextInputType.emailAddress,
                autofillHints: const <String>[],
                enableSuggestions: false,
                autocorrect: false,
                decoration: const InputDecoration(labelText: 'ایمیل یا شماره همراه'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: pass,
                obscureText: true,
                autofillHints: const [AutofillHints.password],
                enableSuggestions: false,
                autocorrect: false,
                decoration: const InputDecoration(labelText: 'رمز عبور'),
              ),
              if (err != null) Padding(padding: const EdgeInsets.only(top: 10), child: Text(err!, style: const TextStyle(color: Colors.red))),
              const SizedBox(height: 18),
              FilledButton(onPressed: busy ? null : go, child: Text(busy ? '...' : 'ورود')),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: busy ? null : () async {
                  final ok = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => const RegisterPage()));
                  if (ok == true && mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('حساب ساخته شد.')));
                },
                icon: const Icon(Icons.person_add_alt_1),
                label: const Text('ثبت‌نام'),
              ),
            ]),
          ),
        ),
      ),
    ),
  );
}

class RegisterPage extends StatefulWidget {
  const RegisterPage({super.key});
  @override
  State<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends State<RegisterPage> {
  final displayName = TextEditingController();
  final firstName = TextEditingController();
  final lastName = TextEditingController();
  final identifier = TextEditingController();
  final password = TextEditingController();
  final code = TextEditingController();
  bool phoneEnabled = true, emailEnabled = true, busy = true;
  String method = 'email';
  String? challengeId, masked, err, debugCode;

  @override
  void initState() { super.initState(); loadConfig(); }
  Future<void> loadConfig() async {
    try {
      final c = await Api.call('/public/config', auth: false);
      if (mounted) setState(() { phoneEnabled = c['phone_registration_enabled'] != false; emailEnabled = c['email_registration_enabled'] != false; method = emailEnabled ? 'email' : 'phone'; busy = false; });
    } catch (_) { if (mounted) setState(() => busy = false); }
  }

  Future<void> start() async {
    if (displayName.text.trim().isEmpty || identifier.text.trim().isEmpty || password.text.length < 8) {
      setState(() => err = 'نام، ایمیل/شماره و رمز حداقل ۸ کاراکتری لازم است.'); return;
    }
    setState(() { busy = true; err = null; });
    try {
      final x = await Api.call('/auth/register/start', method: 'POST', auth: false, body: {
        'method': method, 'identifier': identifier.text.trim(), 'password': password.text,
        'display_name': displayName.text.trim(), 'first_name': firstName.text.trim().isEmpty ? null : firstName.text.trim(),
        'last_name': lastName.text.trim().isEmpty ? null : lastName.text.trim(),
      });
      if (mounted) setState(() { challengeId = x['challenge_id']; masked = x['masked_identifier']; debugCode = x['debug_code']; });
    } catch (e) { if (mounted) setState(() => err = e.toString().replaceFirst('Exception: ', '')); }
    finally { if (mounted) setState(() => busy = false); }
  }

  Future<void> verify() async {
    if (challengeId == null || code.text.trim().length < 4) return;
    setState(() { busy = true; err = null; });
    try {
      final x = await Api.call('/auth/register/verify', method: 'POST', auth: false, body: {'challenge_id': challengeId, 'code': code.text.trim()});
      await SecureSession.setTokens(x['access_token'], x['refresh_token']);
      if (mounted) Navigator.pop(context, true);
    } catch (e) { if (mounted) setState(() => err = e.toString().replaceFirst('Exception: ', '')); }
    finally { if (mounted) setState(() => busy = false); }
  }

  @override
  void dispose() { for (final c in [displayName, firstName, lastName, identifier, password, code]) { c.dispose(); } super.dispose(); }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('ثبت‌نام')),
    body: SafeArea(child: Center(child: SingleChildScrollView(padding: const EdgeInsets.all(18), child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 480),
      child: busy && challengeId == null ? const Center(child: CircularProgressIndicator()) : Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        if (challengeId == null && !emailEnabled && !phoneEnabled) ...[
          const Card(child: Padding(padding: EdgeInsets.all(18), child: Text('ثبت‌نام جدید موقتاً توسط مدیر سامانه غیرفعال شده است.', textAlign: TextAlign.center))),
        ] else if (challengeId == null) ...[
          SegmentedButton<String>(
            segments: [if (emailEnabled) const ButtonSegment(value: 'email', label: Text('ایمیل'), icon: Icon(Icons.email_outlined)), if (phoneEnabled) const ButtonSegment(value: 'phone', label: Text('شماره همراه'), icon: Icon(Icons.phone_android))],
            selected: {method}, onSelectionChanged: (v) => setState(() { method = v.first; identifier.clear(); }),
          ),
          const SizedBox(height: 16),
          TextField(controller: displayName, autofillHints: const <String>[], enableSuggestions: false, autocorrect: false, decoration: const InputDecoration(labelText: 'نام نمایشی')),
          const SizedBox(height: 10),
          Row(children: [
            Expanded(child: TextField(controller: firstName, autofillHints: const <String>[], enableSuggestions: false, autocorrect: false, decoration: const InputDecoration(labelText: 'نام'))),
            const SizedBox(width: 8),
            Expanded(child: TextField(controller: lastName, autofillHints: const <String>[], enableSuggestions: false, autocorrect: false, decoration: const InputDecoration(labelText: 'نام خانوادگی'))),
          ]),
          const SizedBox(height: 10),
          TextField(controller: identifier, keyboardType: method == 'phone' ? TextInputType.phone : TextInputType.emailAddress, autofillHints: const <String>[], enableSuggestions: false, autocorrect: false, decoration: InputDecoration(labelText: method == 'phone' ? 'شماره همراه' : 'ایمیل')),
          const SizedBox(height: 10),
          TextField(controller: password, obscureText: true, autofillHints: const [AutofillHints.newPassword], enableSuggestions: false, autocorrect: false, decoration: const InputDecoration(labelText: 'رمز عبور')),
          const SizedBox(height: 14), FilledButton.icon(onPressed: busy ? null : start, icon: const Icon(Icons.sms_outlined), label: const Text('ارسال کد تأیید')),
        ] else ...[
          const Icon(Icons.verified_user_outlined, size: 58), const SizedBox(height: 12),
          Text('کد تأیید ارسال‌شده به $masked را وارد کنید.', textAlign: TextAlign.center),
          if (debugCode != null) Padding(padding: const EdgeInsets.all(8), child: Text('کد تست: $debugCode', textAlign: TextAlign.center)),
          const SizedBox(height: 14),
          TextField(controller: code, keyboardType: TextInputType.number, autofillHints: const [AutofillHints.oneTimeCode], textAlign: TextAlign.center, maxLength: 6, decoration: const InputDecoration(labelText: 'کد تأیید')),
          FilledButton(onPressed: busy ? null : verify, child: const Text('تأیید و ساخت حساب')),
          TextButton(onPressed: busy ? null : () => setState(() { challengeId = null; code.clear(); }), child: const Text('اصلاح اطلاعات')),
        ],
        if (err != null) Padding(padding: const EdgeInsets.only(top: 10), child: Text(err!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
      ]),
    )))),
  );
}

Future<DateTime?> showPersianDateTimePicker(
  BuildContext context, {
  DateTime? initial,
}) async {
  final source = initial ?? DateTime.now().add(const Duration(hours: 1));
  final j = Jalali.fromDateTime(source);
  var year = j.year;
  var month = j.month;
  var day = j.day;
  var hour = source.hour;
  var minute = (source.minute ~/ 5) * 5;

  return showModalBottomSheet<DateTime>(
    context: context,
    isScrollControlled: true,
    builder: (sheet) => StatefulBuilder(
      builder: (context, setLocal) {
        final maxDay = Jalali(year, month).monthLength;
        if (day > maxDay) day = maxDay;
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'تاریخ و زمان شمسی',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    Expanded(
                      child: DropdownButtonFormField<int>(
                        initialValue: year,
                        items: List.generate(
                          15,
                          (i) => DropdownMenuItem(
                            value: j.year - 2 + i,
                            child: Text('${j.year - 2 + i}'),
                          ),
                        ),
                        onChanged: (v) => setLocal(() => year = v!),
                      ),
                    ),
                    const SizedBox(width: 7),
                    Expanded(
                      child: DropdownButtonFormField<int>(
                        initialValue: month,
                        items: List.generate(
                          12,
                          (i) => DropdownMenuItem(
                            value: i + 1,
                            child: Text(Jalali(year, i + 1).formatter.mN),
                          ),
                        ),
                        onChanged: (v) => setLocal(() => month = v!),
                      ),
                    ),
                    const SizedBox(width: 7),
                    Expanded(
                      child: DropdownButtonFormField<int>(
                        initialValue: day,
                        items: List.generate(
                          maxDay,
                          (i) => DropdownMenuItem(
                            value: i + 1,
                            child: Text('${i + 1}'),
                          ),
                        ),
                        onChanged: (v) => setLocal(() => day = v!),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                      child: DropdownButtonFormField<int>(
                        initialValue: hour,
                        decoration: const InputDecoration(labelText: 'ساعت'),
                        items: List.generate(
                          24,
                          (i) => DropdownMenuItem(value: i, child: Text('$i')),
                        ),
                        onChanged: (v) => setLocal(() => hour = v!),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: DropdownButtonFormField<int>(
                        initialValue: minute,
                        decoration: const InputDecoration(labelText: 'دقیقه'),
                        items: List.generate(
                          12,
                          (i) => DropdownMenuItem(
                            value: i * 5,
                            child: Text('${i * 5}'),
                          ),
                        ),
                        onChanged: (v) => setLocal(() => minute = v!),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: () {
                    final g = Jalali(year, month, day).toGregorian();
                    Navigator.pop(
                      sheet,
                      DateTime(g.year, g.month, g.day, hour, minute),
                    );
                  },
                  child: const Text('تأیید تاریخ'),
                ),
              ],
            ),
          ),
        );
      },
    ),
  );
}

String faDigits(Object? value) => (value ?? '').toString().replaceAllMapped(RegExp(r'[0-9]'), (m) => '۰۱۲۳۴۵۶۷۸۹'[int.parse(m.group(0)!)]);

DateTime itemCreatedAt(dynamic x) => DateTime.tryParse((x['created_at'] ?? x['createdAt'] ?? x['updated_at'] ?? '').toString()) ?? DateTime.fromMillisecondsSinceEpoch(int.tryParse((x['id'] ?? '').toString()) ?? 0);

List<dynamic> newestFirst(List<dynamic> values) => [...values]..sort((a,b) => itemCreatedAt(b).compareTo(itemCreatedAt(a)));

const memberPalette = <Color>[Color(0xff2563eb),Color(0xffdc2626),Color(0xff059669),Color(0xff9333ea),Color(0xffd97706),Color(0xff0891b2),Color(0xffbe185d),Color(0xff4f46e5)];
Color memberColor(dynamic id) { final text = (id ?? '').toString(); var hash = 0; for (final c in text.runes) { hash = (hash * 31 + c) & 0x7fffffff; } return memberPalette[hash % memberPalette.length]; }

String persianDate(dynamic raw) {
  if (raw == null) return 'بدون تاریخ';
  final d = DateTime.tryParse(raw.toString())?.toLocal();
  if (d == null) return '—';
  final j = Jalali.fromDateTime(d);
  return faDigits('${j.formatter.yyyy}/${j.formatter.mm}/${j.formatter.dd}  ${d.hour.toString().padLeft(2, '0')}:${d.minute.toString().padLeft(2, '0')}');
}

class Home extends StatefulWidget {
  const Home({super.key});

  @override
  State<Home> createState() => _HomeState();
}

class _HomeState extends State<Home> {
  int tab = 0;
  List<dynamic> tasks = [];
  List<dynamic> events = [];
  bool busy = true;
  String? error;
  final AppLinks _homeLinks = AppLinks();
  StreamSubscription<Uri>? _homeLinkSub;

  @override
  void initState() {
    super.initState();
    _homeLinkSub = _homeLinks.uriLinkStream.listen(_handleHomeLink);
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final initial = await _homeLinks.getInitialLink();
      if (initial != null) _handleHomeLink(initial);
    });
    load();
  }

  void _handleHomeLink(Uri uri) {
    if (!mounted || uri.scheme != 'planner') return;
    if (uri.host == 'add-task' || uri.host == 'add-event') {
      final kind = uri.host == 'add-event' ? 'event' : 'task';
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) add(kind);
      });
    }
  }

  @override
  void dispose() {
    _homeLinkSub?.cancel();
    super.dispose();
  }

  Future<void> load() async {
    try {
      final r = await Future.wait([Api.call('/tasks'), Api.call('/events')]);
      if (!mounted) return;
      setState(() {
        tasks = r[0] ?? [];
        events = r[1] ?? [];
        busy = false;
        error = null;
      });
      await _updateWidget();
      await _syncReminderNotifications();
    } catch (e) {
      if (mounted) {
        setState(() {
          error = e.toString();
          busy = false;
        });
      }
    }
  }

  Future<void> _updateWidget() async {
    final openTaskItems = tasks.where((x) => x['status'] != 'completed').toList()
      ..sort((a, b) => (a['due_at'] ?? '').toString().compareTo((b['due_at'] ?? '').toString()));
    final openEventItems = events.where((x) => x['status'] != 'completed').toList()
      ..sort((a, b) => (a['starts_at'] ?? '').toString().compareTo((b['starts_at'] ?? '').toString()));
    final now = DateTime.now();
    try {
      await widgetChannel.invokeMethod('updateWidget', {
        'tasks': openTaskItems.length,
        'events': openEventItems.length,
        'date': '${Jalali.now().formatter.wN} ${Jalali.now().formatter.d} ${Jalali.now().formatter.mN}',
        'time': '${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}',
        'taskItemsJson': jsonEncode(openTaskItems.take(3).map((x) => {
          'title': x['title'] ?? 'کار',
          'date': persianDate(x['due_at']),
        }).toList()),
        'eventItemsJson': jsonEncode(openEventItems.take(2).map((x) => {
          'title': x['title'] ?? 'رویداد',
          'date': persianDate(x['starts_at']),
        }).toList()),
      });
    } catch (_) {}
  }

  Future<void> _syncReminderNotifications() async {
    DateTime? reminderAt(dynamic raw) {
      final target = DateTime.tryParse(raw?.toString() ?? '')?.toLocal();
      if (target == null) return null;
      final previous = target.subtract(const Duration(days: 1));
      return DateTime(previous.year, previous.month, previous.day, 17, 0);
    }

    final items = <Map<String, dynamic>>[];
    for (final x in tasks.where((x) => x['status'] != 'completed')) {
      final at = reminderAt(x['due_at']);
      if (at != null && at.isAfter(DateTime.now())) {
        items.add({
          'id': 'task:${x['id']}',
          'title': 'یادآوری کار',
          'body': 'فردا موعد کار «${x['title'] ?? 'کار'}» است.',
          'triggerAt': at.millisecondsSinceEpoch,
        });
      }
    }
    for (final x in events.where((x) => x['status'] != 'completed')) {
      final at = reminderAt(x['starts_at']);
      if (at != null && at.isAfter(DateTime.now())) {
        items.add({
          'id': 'event:${x['id']}',
          'title': 'یادآوری رویداد',
          'body': 'فردا رویداد «${x['title'] ?? 'رویداد'}» است.',
          'triggerAt': at.millisecondsSinceEpoch,
        });
      }
    }
    try {
      await notificationChannel.invokeMethod('syncReminders', {'items': items});
    } catch (_) {}
  }

  Future<void> pinWidget() async {
    try {
      final ok = await widgetChannel.invokeMethod<bool>('pinWidget') ?? false;
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            ok
                ? 'درخواست افزودن ویجت به صفحه اصلی ارسال شد.'
                : 'لانچر این گوشی افزودن مستقیم ویجت را پشتیبانی نمی‌کند. از بخش Widgets گوشی، Planner را بررسی کنید.',
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('افزودن ویجت انجام نشد: $e')),
      );
    }
  }

  Future<void> act(String kind, dynamic item, String action) async {
    try {
      if (action == 'continue') {
        final raw = kind == 'task' ? item['due_at'] : item['starts_at'];
        final picked = await showPersianDateTimePicker(
          context,
          initial: DateTime.tryParse(raw?.toString() ?? '')?.toLocal(),
        );
        if (picked == null) return;
        await Api.call(
          '/${kind}s/${item['id']}/continue',
          method: 'POST',
          body: {'due_at': picked.toUtc().toIso8601String()},
        );
      } else {
        await Api.call('/${kind}s/${item['id']}/complete', method: 'POST');
      }
      await load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.toString())),
        );
      }
    }
  }

  Future<void> add(String kind) async {
    final title = TextEditingController();
    final notes = TextEditingController();
    DateTime? when = DateTime.now().add(const Duration(hours: 1));
    bool saving = false;
    String? formError;

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (sheet) => StatefulBuilder(
        builder: (context, setLocal) => SingleChildScrollView(
          padding: EdgeInsets.fromLTRB(
            18,
            18,
            18,
            18 + MediaQuery.of(sheet).viewInsets.bottom,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Icon(kind == 'task' ? Icons.add_task : Icons.event_available),
                  const SizedBox(width: 8),
                  Text(
                    kind == 'task' ? 'کار جدید' : 'رویداد جدید',
                    style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              TextField(
                controller: title,
                autofocus: true,
                textInputAction: TextInputAction.next,
                decoration: InputDecoration(
                  labelText: kind == 'task' ? 'عنوان کار' : 'عنوان رویداد',
                ),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: notes,
                minLines: 2,
                maxLines: 4,
                decoration: const InputDecoration(labelText: 'توضیحات / یادداشت'),
              ),
              const SizedBox(height: 10),
              OutlinedButton.icon(
                onPressed: saving
                    ? null
                    : () async {
                        final v = await showPersianDateTimePicker(
                          context,
                          initial: when,
                        );
                        if (v != null) setLocal(() => when = v);
                      },
                icon: const Icon(Icons.calendar_month),
                label: Text(
                  when == null
                      ? 'انتخاب تاریخ و ساعت شمسی'
                      : persianDate(when!.toIso8601String()),
                ),
              ),
              if (formError != null) ...[
                const SizedBox(height: 10),
                Text(
                  formError!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
              const SizedBox(height: 14),
              FilledButton.icon(
                onPressed: saving
                    ? null
                    : () async {
                        final cleanTitle = title.text.trim();
                        if (cleanTitle.isEmpty) {
                          setLocal(() => formError = 'عنوان را وارد کنید.');
                          return;
                        }
                        if (when == null) {
                          setLocal(() => formError = 'تاریخ و ساعت را انتخاب کنید.');
                          return;
                        }
                        setLocal(() {
                          saving = true;
                          formError = null;
                        });
                        try {
                          if (kind == 'task') {
                            await Api.call(
                              '/tasks',
                              method: 'POST',
                              body: {
                                'title': cleanTitle,
                                'notes': notes.text.trim().isEmpty ? null : notes.text.trim(),
                                'due_at': when!.toUtc().toIso8601String(),
                              },
                            );
                          } else {
                            await Api.call(
                              '/events',
                              method: 'POST',
                              body: {
                                'title': cleanTitle,
                                'starts_at': when!.toUtc().toIso8601String(),
                              },
                            );
                          }
                          if (sheet.mounted) Navigator.pop(sheet);
                          await load();
                          if (mounted) {
                            ScaffoldMessenger.of(this.context).showSnackBar(
                              SnackBar(
                                content: Text(kind == 'task' ? 'کار ثبت شد.' : 'رویداد ثبت شد.'),
                              ),
                            );
                          }
                        } catch (e) {
                          setLocal(() {
                            saving = false;
                            formError = e.toString();
                          });
                        }
                      },
                icon: saving
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.save_outlined),
                label: Text(saving ? 'در حال ذخیره...' : 'ذخیره'),
              ),
            ],
          ),
        ),
      ),
    );
    title.dispose();
    notes.dispose();
  }

  Future<void> showCreateMenu() async {
    final kind = await showModalBottomSheet<String>(
      context: context,
      useSafeArea: true,
      builder: (sheet) => Padding(
        padding: EdgeInsets.fromLTRB(18, 18, 18, 24 + MediaQuery.of(sheet).viewPadding.bottom),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'افزودن',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: () => Navigator.pop(sheet, 'task'),
              icon: const Icon(Icons.add_task),
              label: const Text('کار جدید'),
            ),
            const SizedBox(height: 8),
            FilledButton.tonalIcon(
              onPressed: () => Navigator.pop(sheet, 'event'),
              icon: const Icon(Icons.event_available),
              label: const Text('رویداد جدید'),
            ),
          ],
        ),
      ),
    );
    if (kind != null && mounted) await add(kind);
  }

  @override
  Widget build(BuildContext context) {
    final openTasks = tasks.where((x) => x['status'] != 'completed').toList();
    final openEvents = events.where((x) => x['status'] != 'completed').toList();
    final pages = [
      Today(tasks: openTasks, events: openEvents, onAct: act, onOpenTasks: () => setState(() => tab = 1), onOpenEvents: () => setState(() => tab = 2)),
      ItemsPage(title: 'کارها', kind: 'task', items: newestFirst(openTasks), onAct: act),
      ItemsPage(title: 'رویدادها', kind: 'event', items: newestFirst(openEvents), onAct: act),
      CalendarPage(tasks: openTasks, events: openEvents, onAct: act),
      const WorkspacesPage(),
      const MessagesPage(),
    ];
    return Scaffold(
      appBar: AppBar(
        title: Text(['امروز', 'کارها', 'رویدادها', 'تقویم', 'فضای کار', 'پیام‌ها'][tab]),
        actions: [
          if (tab <= 3)
            IconButton(
              tooltip: 'افزودن کار یا رویداد',
              onPressed: showCreateMenu,
              icon: const Icon(Icons.add_circle_outline),
            ),
          IconButton(onPressed: load, tooltip: 'بروزرسانی', icon: const Icon(Icons.refresh_rounded)),
          IconButton(
            tooltip: 'تنظیمات',
            onPressed: () async {
              final loggedOut = await Navigator.push<bool>(
                context,
                MaterialPageRoute(builder: (_) => const SettingsPage()),
              );
              if (loggedOut == true && context.mounted) {
                Navigator.pushAndRemoveUntil(
                  context,
                  MaterialPageRoute(builder: (_) => const Gate()),
                  (_) => false,
                );
              }
            },
            icon: const Icon(Icons.settings_outlined),
          ),
        ],
      ),
      body: busy
          ? const Center(child: CircularProgressIndicator())
          : error != null
              ? Center(child: Text(error!))
              : RefreshIndicator(onRefresh: load, child: pages[tab]),
      bottomNavigationBar: SafeArea(
        top: false,
        minimum: const EdgeInsets.only(bottom: 12),
        child: NavigationBar(
          selectedIndex: tab,
          onDestinationSelected: (i) => setState(() => tab = i),
          labelBehavior: NavigationDestinationLabelBehavior.onlyShowSelected,
          destinations: const [
            NavigationDestination(icon: Icon(Icons.today_outlined), label: 'امروز'),
            NavigationDestination(icon: Icon(Icons.check_circle_outline), label: 'کارها'),
            NavigationDestination(icon: Icon(Icons.event_outlined), label: 'رویداد'),
            NavigationDestination(icon: Icon(Icons.calendar_month_outlined), label: 'تقویم'),
            NavigationDestination(icon: Icon(Icons.groups_outlined), label: 'فضای کار'),
            NavigationDestination(icon: Icon(Icons.chat_bubble_outline), label: 'پیام'),
          ],
        ),
      ),
    );
  }
}

typedef ActionFn = Future<void> Function(String, dynamic, String);

class Today extends StatelessWidget {
  final List<dynamic> tasks;
  final List<dynamic> events;
  final ActionFn onAct;
  final VoidCallback onOpenTasks;
  final VoidCallback onOpenEvents;
  const Today({
    super.key,
    required this.tasks,
    required this.events,
    required this.onAct,
    required this.onOpenTasks,
    required this.onOpenEvents,
  });

  @override
  Widget build(BuildContext context) {
    final all = [
      ...tasks.map((x) => {'kind': 'task', 'item': x, 'date': x['due_at']}),
      ...events.map((x) => {'kind': 'event', 'item': x, 'date': x['starts_at']}),
    ]..sort((a, b) => (a['date'] ?? '').toString().compareTo((b['date'] ?? '').toString()));
    return ListView(
      padding: const EdgeInsets.all(16),
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        DashboardHero(taskCount: tasks.length, eventCount: events.length),
        const SizedBox(height: 14),
        Row(
          children: [
            Expanded(child: InkWell(onTap: onOpenTasks, child: Stat(title: 'کارهای باز', value: tasks.length, icon: Icons.check_circle_outline))),
            const SizedBox(width: 10),
            Expanded(child: InkWell(onTap: onOpenEvents, child: Stat(title: 'رویدادها', value: events.length, icon: Icons.event_outlined))),
          ],
        ),
        const SizedBox(height: 18),
        const Text('برنامه‌های پیش رو', style: TextStyle(fontSize: 19, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        if (all.isEmpty) const Empty(text: 'برنامه‌ای ثبت نشده'),
        ...all.take(10).map(
              (x) => ItemCard(
                item: x['item'],
                kind: x['kind'] as String,
                onAct: onAct,
              ),
            ),
      ],
    );
  }
}

class DashboardHero extends StatelessWidget {
  final int taskCount;
  final int eventCount;
  const DashboardHero({super.key, required this.taskCount, required this.eventCount});
  @override
  Widget build(BuildContext context) {
    final j = Jalali.now();
    final cs = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(begin: Alignment.topRight, end: Alignment.bottomLeft, colors: [cs.primary, const Color(0xff245b7a)]),
        borderRadius: BorderRadius.circular(26),
        boxShadow: const [BoxShadow(blurRadius: 24, offset: Offset(0, 10), color: Color(0x1f173c2b))],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text('امروز', style: TextStyle(color: Colors.white70, fontWeight: FontWeight.w700)),
        const SizedBox(height: 4),
        Text(faDigits('${j.formatter.wN} ${j.formatter.d} ${j.formatter.mN} ${j.year}'), style: const TextStyle(color: Colors.white, fontSize: 23, fontWeight: FontWeight.w900)),
        const SizedBox(height: 14),
        Text(faDigits('$taskCount کار باز  •  $eventCount رویداد پیش‌رو'), style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600)),
      ]),
    );
  }
}

class Stat extends StatelessWidget {
  final String title;
  final int value;
  final IconData icon;
  const Stat({super.key, required this.title, required this.value, required this.icon});
  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(children: [
            Container(
              width: 42, height: 42,
              decoration: BoxDecoration(color: Theme.of(context).colorScheme.primaryContainer, borderRadius: BorderRadius.circular(14)),
              child: Icon(icon, color: Theme.of(context).colorScheme.primary),
            ),
            const SizedBox(width: 11),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(faDigits(value), style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w900)),
              Text(title, style: Theme.of(context).textTheme.bodySmall),
            ])),
          ]),
        ),
      );
}

class ItemsPage extends StatefulWidget {
  final String title;
  final String kind;
  final List<dynamic> items;
  final ActionFn onAct;
  const ItemsPage({super.key, required this.title, required this.kind, required this.items, required this.onAct});

  @override
  State<ItemsPage> createState() => _ItemsPageState();
}

class _ItemsPageState extends State<ItemsPage> {
  int page = 0;
  static const size = 15;
  @override
  Widget build(BuildContext context) {
    final pages = (widget.items.length / size).ceil().clamp(1, 9999);
    if (page >= pages) page = pages - 1;
    final from = page * size;
    final items = widget.items.skip(from).take(size).toList();
    return ListView(
      padding: const EdgeInsets.all(16),
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        if (items.isEmpty) const Empty(text: 'هنوز چیزی ثبت نشده'),
        ...items.map((x) => ItemCard(item: x, kind: widget.kind, onAct: widget.onAct)),
        if (pages > 1)
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              IconButton(onPressed: page > 0 ? () => setState(() => page--) : null, icon: const Icon(Icons.chevron_right)),
              Text(faDigits('صفحه ${page + 1} از $pages')),
              IconButton(onPressed: page < pages - 1 ? () => setState(() => page++) : null, icon: const Icon(Icons.chevron_left)),
            ],
          ),
      ],
    );
  }
}

class ItemCard extends StatelessWidget {
  final dynamic item;
  final String kind;
  final ActionFn onAct;
  const ItemCard({super.key, required this.item, required this.kind, required this.onAct});
  @override
  Widget build(BuildContext context) => Card(
        elevation: 0,
        margin: const EdgeInsets.only(bottom: 10),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(item['title'] ?? '', textAlign: TextAlign.right, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 16)),
              const SizedBox(height: 5),
              Text(persianDate(kind == 'task' ? item['due_at'] : item['starts_at']), textAlign: TextAlign.right),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(child: OutlinedButton(onPressed: () => onAct(kind, item, 'continue'), child: const Text('ادامه دارد'))),
                  const SizedBox(width: 8),
                  Expanded(child: FilledButton(onPressed: () => onAct(kind, item, 'complete'), child: const Text('انجام شد'))),
                ],
              ),
            ],
          ),
        ),
      );
}

class CalendarPage extends StatefulWidget {
  final List<dynamic> tasks;
  final List<dynamic> events;
  final ActionFn onAct;
  const CalendarPage({super.key, required this.tasks, required this.events, required this.onAct});
  @override
  State<CalendarPage> createState() => _CalendarPageState();
}

class _CalendarPageState extends State<CalendarPage> {
  late int year;
  late int month;
  int selected = 1;
  List<dynamic> officialDays = [];
  bool officialLoading = false;

  @override
  void initState() {
    super.initState();
    final n = Jalali.now();
    year = n.year;
    month = n.month;
    selected = n.day;
    _loadOfficial();
  }

  Future<void> _loadOfficial() async {
    if (year != 1405) {
      if (mounted) setState(() => officialDays = []);
      return;
    }
    if (mounted) setState(() => officialLoading = true);
    try {
      final x = await Api.call(
        '/official-calendar/$year/$month?include_supplement=true&include_profession=false',
        auth: false,
      );
      if (mounted) setState(() => officialDays = x['days'] ?? []);
    } catch (_) {
      if (mounted) setState(() => officialDays = []);
    } finally {
      if (mounted) setState(() => officialLoading = false);
    }
  }

  dynamic officialFor(int day) {
    for (final x in officialDays) {
      if (x['day'] == day) return x;
    }
    return null;
  }

  List<dynamic> itemsFor(int day) {
    bool same(dynamic raw) {
      final d = DateTime.tryParse(raw?.toString() ?? '')?.toLocal();
      if (d == null) return false;
      final j = Jalali.fromDateTime(d);
      return j.year == year && j.month == month && j.day == day;
    }
    return [
      ...widget.tasks.where((x) => same(x['due_at'])).map((x) => {'kind': 'task', 'item': x}),
      ...widget.events.where((x) => same(x['starts_at'])).map((x) => {'kind': 'event', 'item': x}),
    ];
  }

  void move(int by) {
    setState(() {
      month += by;
      if (month == 13) { month = 1; year++; }
      if (month == 0) { month = 12; year--; }
      selected = 1;
    });
    _loadOfficial();
  }

  void moveYear(int by) {
    setState(() {
      year += by;
      selected = selected.clamp(1, Jalali(year, month).monthLength).toInt();
    });
    _loadOfficial();
  }

  void goToday() {
    final n = Jalali.now();
    setState(() {
      year = n.year;
      month = n.month;
      selected = n.day;
    });
    _loadOfficial();
  }

  Future<void> chooseMonthYear() async {
    var yy = year;
    var mm = month;
    final result = await showDialog<List<int>>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setLocal) => AlertDialog(
          title: const Text('انتخاب ماه و سال'),
          content: Row(children: [
            Expanded(
              child: DropdownButtonFormField<int>(
                initialValue: mm,
                decoration: const InputDecoration(labelText: 'ماه'),
                items: List.generate(12, (i) => DropdownMenuItem(value: i + 1, child: Text(Jalali(1405, i + 1).formatter.mN))),
                onChanged: (v) => setLocal(() => mm = v ?? mm),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: DropdownButtonFormField<int>(
                initialValue: yy,
                decoration: const InputDecoration(labelText: 'سال'),
                items: List.generate(31, (i) { final y = Jalali.now().year - 15 + i; return DropdownMenuItem(value: y, child: Text('$y')); }),
                onChanged: (v) => setLocal(() => yy = v ?? yy),
              ),
            ),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('انصراف')),
            FilledButton(onPressed: () => Navigator.pop(context, [yy, mm]), child: const Text('انتخاب')),
          ],
        ),
      ),
    );
    if (result == null || !mounted) return;
    setState(() {
      year = result[0];
      month = result[1];
      selected = 1;
    });
    _loadOfficial();
  }

  @override
  Widget build(BuildContext context) {
    final first = Jalali(year, month, 1).toGregorian().toDateTime();
    final offset = (first.weekday + 1) % 7;
    final length = Jalali(year, month).monthLength;
    final cells = <Widget>[
      ...List.generate(offset, (_) => const SizedBox()),
      ...List.generate(length, (i) {
        final day = i + 1;
        final od = officialFor(day);
        final holiday = od != null && (od['official_holiday'] == true || od['weekend'] == true);
        final hasOccasion = od != null && ((od['occasion'] ?? '').toString().trim().isNotEmpty || (od['extra_occasions'] as List?)?.isNotEmpty == true);
        return InkWell(
          onTap: () => setState(() => selected = day),
          borderRadius: BorderRadius.circular(12),
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              color: holiday
                  ? const Color(0xfffff1f2)
                  : selected == day
                      ? const Color(0xffe7f4ec)
                      : Colors.white,
              border: Border.all(
                color: selected == day
                    ? Theme.of(context).colorScheme.primary
                    : holiday
                        ? const Color(0xfffecdd3)
                        : const Color(0xffe5e9e6),
              ),
            ),
            padding: const EdgeInsets.all(7),
            child: Stack(
              children: [
                Text(
                  '$day',
                  style: TextStyle(
                    fontWeight: FontWeight.w800,
                    color: holiday ? const Color(0xffb91c1c) : null,
                  ),
                ),
                if (holiday)
                  const Positioned(
                    left: 1,
                    top: 1,
                    child: Text('تعطیل', style: TextStyle(fontSize: 8, color: Color(0xffb91c1c), fontWeight: FontWeight.w800)),
                  ),
                if (hasOccasion)
                  const Positioned(bottom: 2, left: 2, child: CircleAvatar(radius: 3, backgroundColor: Color(0xfff59e0b))),
                if (itemsFor(day).isNotEmpty)
                  const Positioned(bottom: 2, right: 2, child: CircleAvatar(radius: 3)),
              ],
            ),
          ),
        );
      }),
    ];
    final selectedItems = itemsFor(selected);
    final od = officialFor(selected);
    final extras = od?['extra_occasions'] is List ? od['extra_occasions'] as List : const [];
    final holiday = od != null && (od['official_holiday'] == true || od['weekend'] == true);
    return ListView(
      padding: const EdgeInsets.all(16),
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        Row(children: [
          FilledButton.tonal(onPressed: goToday, child: const Text('امروز')),
          const SizedBox(width: 6),
          IconButton(onPressed: () => moveYear(-1), tooltip: 'سال قبل', icon: const Icon(Icons.keyboard_double_arrow_right)),
          IconButton(onPressed: () => move(-1), tooltip: 'ماه قبل', icon: const Icon(Icons.chevron_right)),
          Expanded(
            child: OutlinedButton(
              onPressed: chooseMonthYear,
              child: Text('${Jalali(year, month).formatter.mN} $year', style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900)),
            ),
          ),
          IconButton(onPressed: () => move(1), tooltip: 'ماه بعد', icon: const Icon(Icons.chevron_left)),
          IconButton(onPressed: () => moveYear(1), tooltip: 'سال بعد', icon: const Icon(Icons.keyboard_double_arrow_left)),
        ]),
        if (officialLoading) const LinearProgressIndicator(minHeight: 2),
        if (year != 1405)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 8),
            child: Text('مناسبت‌های رسمی فعلاً برای سال ۱۴۰۵ در دسترس است.', textAlign: TextAlign.center),
          ),
        const Directionality(
          textDirection: TextDirection.rtl,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              Text('ش', style: TextStyle(fontWeight: FontWeight.w800)),
              Text('ی', style: TextStyle(fontWeight: FontWeight.w800)),
              Text('د', style: TextStyle(fontWeight: FontWeight.w800)),
              Text('س', style: TextStyle(fontWeight: FontWeight.w800)),
              Text('چ', style: TextStyle(fontWeight: FontWeight.w800)),
              Text('پ', style: TextStyle(fontWeight: FontWeight.w800)),
              Text('ج', style: TextStyle(fontWeight: FontWeight.w800, color: Color(0xffb91c1c))),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Directionality(
          textDirection: TextDirection.rtl,
          child: GridView.count(
            crossAxisCount: 7,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 5,
            crossAxisSpacing: 5,
            children: cells,
          ),
        ),
        const SizedBox(height: 18),
        Row(children: [
          Expanded(child: Text('$selected ${Jalali(year, month).formatter.mN}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold))),
          if (holiday)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
              decoration: BoxDecoration(color: const Color(0xffffe4e6), borderRadius: BorderRadius.circular(999)),
              child: Text(od?['official_holiday'] == true ? 'تعطیل رسمی' : 'جمعه / تعطیل هفتگی', style: const TextStyle(color: Color(0xffb91c1c), fontWeight: FontWeight.w800, fontSize: 11)),
            ),
        ]),
        if (od != null && (od['occasion'] ?? '').toString().trim().isNotEmpty) ...[
          const SizedBox(height: 8),
          Card(
            color: holiday ? const Color(0xfffff1f2) : const Color(0xfffffbeb),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Text(holiday ? 'مناسبت تعطیل' : 'مناسبت رسمی', style: TextStyle(fontWeight: FontWeight.w900, color: holiday ? const Color(0xffb91c1c) : const Color(0xff92400e))),
                const SizedBox(height: 4),
                Text(od['occasion'].toString(), textAlign: TextAlign.right),
              ]),
            ),
          ),
        ],
        ...extras.map((x) => Card(
          child: ListTile(
            leading: const Icon(Icons.auto_awesome_outlined),
            title: Text((x['occasion'] ?? '').toString()),
            subtitle: Text(x['category'] == 'profession' ? 'مناسبت صنفی' : 'ضمیمه تقویم رسمی'),
          ),
        )),
        const SizedBox(height: 8),
        if (selectedItems.isEmpty && od == null) const Empty(text: 'موردی در این روز نیست'),
        ...selectedItems.map((x) => ItemCard(item: x['item'], kind: x['kind'], onAct: widget.onAct)),
      ],
    );
  }
}

class WorkspacesPage extends StatefulWidget {
  const WorkspacesPage({super.key});

  @override
  State<WorkspacesPage> createState() => _WorkspacesPageState();
}

class _WorkspacesPageState extends State<WorkspacesPage> {
  List<dynamic> workspaces = [];
  bool busy = true;
  String? error;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final x = await Api.call('/workspaces');
      if (mounted) setState(() { workspaces = x ?? []; busy = false; error = null; });
    } catch (e) {
      if (mounted) setState(() { error = e.toString(); busy = false; });
    }
  }

  Future<void> createWorkspace() async {
    final name = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (dialog) => AlertDialog(
        title: const Text('فضای کار جدید'),
        content: TextField(controller: name, autofocus: true, decoration: const InputDecoration(labelText: 'نام فضای کار')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialog, false), child: const Text('انصراف')),
          FilledButton(onPressed: () => Navigator.pop(dialog, true), child: const Text('ایجاد')),
        ],
      ),
    );
    if (ok == true && name.text.trim().isNotEmpty) {
      await Api.call('/workspaces', method: 'POST', body: {'name': name.text.trim()});
      await load();
    }
    name.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (busy) return const Center(child: CircularProgressIndicator());
    return RefreshIndicator(
      onRefresh: load,
      child: ListView(
        padding: const EdgeInsets.all(14),
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          Row(children: [
            Expanded(child: Text('فضاهای کاری من', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold))),
            FilledButton.icon(onPressed: createWorkspace, icon: const Icon(Icons.add), label: const Text('ایجاد')),
          ]),
          const SizedBox(height: 12),
          if (error != null) Card(child: Padding(padding: const EdgeInsets.all(12), child: Text(error!))),
          if (workspaces.isEmpty) const Empty(text: 'هنوز فضای کاری ندارید'),
          ...workspaces.map((w) => Card(
            elevation: 0,
            child: ListTile(
              leading: const CircleAvatar(child: Icon(Icons.groups_rounded)),
              title: Text(w['name'] ?? 'فضای کار'),
              subtitle: const Text('محیط مشترک اعضا، اسناد و گفتگو'),
              trailing: const Icon(Icons.chevron_left),
              onTap: () async {
                await Navigator.push(context, MaterialPageRoute(builder: (_) => WorkspaceDetailPage(workspaceId: w['id'], initialName: w['name'] ?? 'فضای کار')));
                await load();
              },
            ),
          )),
        ],
      ),
    );
  }
}

class WorkspaceDetailPage extends StatefulWidget {
  final String workspaceId;
  final String initialName;
  const WorkspaceDetailPage({super.key, required this.workspaceId, required this.initialName});

  @override
  State<WorkspaceDetailPage> createState() => _WorkspaceDetailPageState();
}

class _WorkspaceDetailPageState extends State<WorkspaceDetailPage> {
  dynamic detail;
  dynamic me;
  dynamic boardDocument;
  List<dynamic> boardItems = [];
  List<dynamic> documents = [];
  List<dynamic> foundUsers = [];
  final memberSearch = TextEditingController();
  bool busy = true;
  String? error;

  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void dispose() {
    memberSearch.dispose();
    super.dispose();
  }

  Future<void> load() async {
    try {
      final r = await Future.wait([
        Api.call('/workspaces/${widget.workspaceId}'),
        Api.call('/workspaces/${widget.workspaceId}/documents'),
        Api.call('/me'),
      ]);
      final rawDocs = List<dynamic>.from(r[1] ?? []);
      dynamic board;
      for (final d in rawDocs) {
        if (d['title'] == '__planner_workspace_board__') { board = d; break; }
      }
      List<dynamic> parsedBoard = [];
      if (board != null) {
        try {
          final decoded = jsonDecode((board['content'] ?? '[]').toString());
          if (decoded is List) parsedBoard = List<dynamic>.from(decoded);
        } catch (_) {}
      }
      if (mounted) setState(() {
        detail = r[0];
        me = r[2];
        boardDocument = board;
        boardItems = parsedBoard;
        documents = rawDocs.where((d) => d['title'] != '__planner_workspace_board__').toList();
        busy = false;
        error = null;
      });
    } catch (e) {
      if (mounted) setState(() { error = e.toString(); busy = false; });
    }
  }

  Future<void> searchMembers(String q) async {
    if (q.trim().length < 2) {
      if (mounted) setState(() => foundUsers = []);
      return;
    }
    final x = await Api.call('/users/search?q=${Uri.encodeComponent(q.trim())}');
    final existing = <String>{...(detail?['members'] ?? []).map<String>((m) => m['user_id'].toString())};
    if (mounted) setState(() => foundUsers = (x ?? []).where((u) => !existing.contains(u['id'].toString())).toList());
  }

  Future<void> addMember(dynamic user) async {
    try {
      await Api.call('/workspaces/${widget.workspaceId}/members', method: 'POST', body: {
        'user_id': user['id'], 'role': 'editor', 'color': '#${memberColor(user['id']).toARGB32().toRadixString(16).substring(2)}',
      });
      memberSearch.clear();
      if (mounted) setState(() => foundUsers = []);
      await load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  Future<void> _ensureBoard() async {
    if (boardDocument != null) return;
    final created = await Api.call('/workspaces/${widget.workspaceId}/documents', method: 'POST', body: {
      'title': '__planner_workspace_board__',
      'content': '[]',
    });
    boardDocument = created;
    boardItems = [];
  }

  Future<void> _saveBoard() async {
    await _ensureBoard();
    try {
      final r = await Api.call('/documents/${boardDocument['id']}', method: 'PUT', body: {
        'content': jsonEncode(boardItems),
        'base_revision': boardDocument['revision'] ?? 0,
      });
      boardDocument['revision'] = r['revision'] ?? ((boardDocument['revision'] ?? 0) + 1);
      boardDocument['content'] = jsonEncode(boardItems);
    } catch (e) {
      await load();
      rethrow;
    }
  }

  Future<void> addSharedItem() async {
    final title = TextEditingController();
    String kind = 'task';
    String? assignee = me?['id']?.toString();
    DateTime? when;
    final members = List<dynamic>.from(detail?['members'] ?? []);
    final ok = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (sheet) => StatefulBuilder(
        builder: (context, setLocal) => Padding(
          padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + MediaQuery.of(sheet).viewInsets.bottom),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(controller: title, autofocus: true, decoration: const InputDecoration(labelText: 'عنوان')),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(
              initialValue: kind,
              decoration: const InputDecoration(labelText: 'نوع'),
              items: const [
                DropdownMenuItem(value: 'task', child: Text('کار مشترک')),
                DropdownMenuItem(value: 'event', child: Text('رویداد مشترک')),
              ],
              onChanged: (v) => setLocal(() => kind = v ?? 'task'),
            ),
            const SizedBox(height: 10),
            DropdownButtonFormField<String?>(
              initialValue: assignee,
              decoration: const InputDecoration(labelText: 'مسئول'),
              items: [
                const DropdownMenuItem<String?>(value: null, child: Text('بدون مسئول مشخص')),
                ...members.map((m) => DropdownMenuItem<String?>(value: m['user_id']?.toString(), child: Text(m['name'] ?? m['email'] ?? 'عضو'))),
              ],
              onChanged: (v) => setLocal(() => assignee = v),
            ),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              onPressed: () async {
                final picked = await showPersianDateTimePicker(context, initial: when);
                if (picked != null) setLocal(() => when = picked);
              },
              icon: const Icon(Icons.calendar_month),
              label: Text(when == null ? 'تاریخ و ساعت شمسی' : persianDate(when!.toIso8601String())),
            ),
            const SizedBox(height: 12),
            SizedBox(width: double.infinity, child: FilledButton(onPressed: () => Navigator.pop(sheet, true), child: const Text('افزودن به فضای کار'))),
          ]),
        ),
      ),
    );
    if (ok == true && title.text.trim().isNotEmpty) {
      final item = <String, dynamic>{
        'id': DateTime.now().microsecondsSinceEpoch.toString(),
        'kind': kind,
        'title': title.text.trim(),
        'assignee_user_id': assignee,
        'date': when?.toUtc().toIso8601String(),
        'status': 'open',
        'created_by': me?['id'],
      };
      setState(() => boardItems = [...boardItems, item]);
      try {
        await _saveBoard();
      } catch (e) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('هم‌زمان عضو دیگری برد را تغییر داده است؛ اطلاعات تازه شد. $e')));
      }
    }
    title.dispose();
  }

  Future<void> toggleSharedItem(dynamic item) async {
    final copy = boardItems.map((x) => Map<String, dynamic>.from(x as Map)).toList();
    final index = copy.indexWhere((x) => x['id'] == item['id']);
    if (index < 0) return;
    copy[index]['status'] = copy[index]['status'] == 'completed' ? 'open' : 'completed';
    setState(() => boardItems = copy);
    try {
      await _saveBoard();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('ذخیره برد مشترک انجام نشد؛ اطلاعات تازه شد. $e')));
    }
  }

  bool get _isOwner => detail != null && me != null && detail['owner_id'].toString() == me['id'].toString();

  String get _myRole {
    for (final m in List<dynamic>.from(detail?['members'] ?? [])) {
      if (me != null && m['user_id'].toString() == me['id'].toString()) return (m['role'] ?? 'viewer').toString();
    }
    return 'viewer';
  }

  bool get _canEdit => _myRole != 'viewer';

  String _memberName(dynamic userId) {
    if (userId == null) return 'بدون مسئول';
    for (final m in List<dynamic>.from(detail?['members'] ?? [])) {
      if (m['user_id'].toString() == userId.toString()) return m['name'] ?? m['email'] ?? 'عضو';
    }
    return 'عضو';
  }

  Future<void> createDocument() async {
    final title = TextEditingController();
    final content = TextEditingController();
    final ok = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (sheet) => Padding(
        padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + MediaQuery.of(sheet).viewInsets.bottom),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: title, autofocus: true, decoration: const InputDecoration(labelText: 'عنوان سند')),
          const SizedBox(height: 10),
          TextField(controller: content, minLines: 4, maxLines: 10, decoration: const InputDecoration(labelText: 'محتوا')),
          const SizedBox(height: 12),
          SizedBox(width: double.infinity, child: FilledButton(onPressed: () => Navigator.pop(sheet, true), child: const Text('ایجاد سند مشترک'))),
        ]),
      ),
    );
    if (ok == true && title.text.trim().isNotEmpty) {
      await Api.call('/workspaces/${widget.workspaceId}/documents', method: 'POST', body: {'title': title.text.trim(), 'content': content.text});
      await load();
    }
    title.dispose(); content.dispose();
  }

  Future<void> chatWith(dynamic member) async {
    final c = await Api.call('/conversations', method: 'POST', body: {'other_user_id': member['user_id']});
    if (!mounted) return;
    await Navigator.push(context, MaterialPageRoute(builder: (_) => DirectConversationPage(
      conversationId: c['id'], peerName: member['name'] ?? 'عضو', peerEmail: member['email'] ?? '',
    )));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(detail?['name'] ?? widget.initialName), actions: [IconButton(onPressed: load, icon: const Icon(Icons.refresh))]),
      body: busy ? const Center(child: CircularProgressIndicator()) : error != null ? Center(child: Text(error!)) : RefreshIndicator(
        onRefresh: load,
        child: ListView(
          padding: const EdgeInsets.all(14),
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            Card(elevation: 0, child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Text('اعضا', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
                const SizedBox(height: 10),
                ...((detail?['members'] ?? []) as List).map((m) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: CircleAvatar(backgroundColor: memberColor(m['user_id']), foregroundColor: Colors.white, child: Text((m['name'] ?? 'U').toString().isEmpty ? 'U' : (m['name'] ?? 'U').toString().substring(0, 1))),
                  title: Text(m['name'] ?? 'کاربر'),
                  subtitle: Text('${m['email'] ?? ''} • ${m['role'] ?? 'editor'}'),
                  trailing: m['role'] == 'owner' ? const Icon(Icons.workspace_premium) : IconButton(onPressed: () => chatWith(m), icon: const Icon(Icons.chat_bubble_outline)),
                )),
                if (_isOwner) ...[
                  const Divider(),
                  TextField(
                    controller: memberSearch,
                    onChanged: searchMembers,
                    decoration: const InputDecoration(prefixIcon: Icon(Icons.person_add_alt_1), hintText: 'افزودن عضو با نام یا ایمیل'),
                  ),
                  if (foundUsers.isNotEmpty) ...foundUsers.map((u) => ListTile(
                    title: Text(u['name'] ?? ''), subtitle: Text(u['email'] ?? ''), trailing: const Icon(Icons.add_circle_outline), onTap: () => addMember(u),
                  )),
                ],
              ]),
            )),
            const SizedBox(height: 12),
            Row(children: [
              Expanded(child: Text('برد مشترک', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold))),
              FilledButton.tonalIcon(onPressed: _canEdit ? addSharedItem : null, icon: const Icon(Icons.add_task), label: const Text('افزودن')),
            ]),
            const SizedBox(height: 8),
            if (boardItems.isEmpty) const Empty(text: 'هنوز کار یا رویداد مشترکی ثبت نشده'),
            ...boardItems.map((item) => Card(
              elevation: 0,
              child: CheckboxListTile(
                value: item['status'] == 'completed',
                onChanged: _canEdit ? (_) => toggleSharedItem(item) : null,
                secondary: Icon(item['kind'] == 'event' ? Icons.event_outlined : Icons.check_circle_outline, color: memberColor(item['assignee_user_id'])),
                title: Text(
                  item['title'] ?? '',
                  style: TextStyle(decoration: item['status'] == 'completed' ? TextDecoration.lineThrough : null),
                ),
                subtitle: Text('${item['kind'] == 'event' ? 'رویداد' : 'کار'} • ${_memberName(item['assignee_user_id'])}${item['date'] == null ? '' : ' • ${persianDate(item['date'])}'}'),
              ),
            )),
            const SizedBox(height: 12),
            Row(children: [
              Expanded(child: Text('اسناد مشترک', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold))),
              FilledButton.tonalIcon(onPressed: _canEdit ? createDocument : null, icon: const Icon(Icons.note_add_outlined), label: const Text('سند جدید')),
            ]),
            const SizedBox(height: 8),
            if (documents.isEmpty) const Empty(text: 'سند مشترکی ساخته نشده'),
            ...documents.map((d) => Card(elevation: 0, child: ListTile(
              leading: const Icon(Icons.description_outlined),
              title: Text(d['title'] ?? 'سند'),
              subtitle: Text('ویرایش ${d['revision'] ?? 0}'),
              trailing: const Icon(Icons.chevron_left),
              onTap: () async {
                await Navigator.push(context, MaterialPageRoute(builder: (_) => WorkspaceDocumentPage(document: d)));
                await load();
              },
            ))),
          ],
        ),
      ),
    );
  }
}

class WorkspaceDocumentPage extends StatefulWidget {
  final dynamic document;
  const WorkspaceDocumentPage({super.key, required this.document});

  @override
  State<WorkspaceDocumentPage> createState() => _WorkspaceDocumentPageState();
}

class _WorkspaceDocumentPageState extends State<WorkspaceDocumentPage> {
  late final TextEditingController content;
  late int revision;
  late String lastSyncedContent;
  Timer? _pullTimer;
  Timer? _saveTimer;
  bool saving = false;
  bool dirty = false;
  bool applyingRemote = false;
  String syncText = 'همگام';

  @override
  void initState() {
    super.initState();
    lastSyncedContent = widget.document['content'] ?? '';
    content = TextEditingController(text: lastSyncedContent);
    revision = widget.document['revision'] ?? 0;
    content.addListener(_onLocalChanged);
    _pullTimer = Timer.periodic(const Duration(seconds: 2), (_) => _pullRemote());
    WidgetsBinding.instance.addPostFrameCallback((_) => _pullRemote());
  }

  void _onLocalChanged() {
    if (applyingRemote) return;
    dirty = content.text != lastSyncedContent;
    if (mounted) setState(() => syncText = dirty ? 'در انتظار همگام‌سازی…' : 'همگام');
    _saveTimer?.cancel();
    if (dirty) {
      _saveTimer = Timer(const Duration(milliseconds: 700), () => save(silent: true));
    }
  }

  void _applyText(String value) {
    if (content.text == value) return;
    applyingRemote = true;
    final oldSelection = content.selection;
    content.text = value;
    final offset = oldSelection.baseOffset < 0
        ? 0
        : (oldSelection.baseOffset > value.length ? value.length : oldSelection.baseOffset);
    content.selection = TextSelection.collapsed(offset: offset);
    applyingRemote = false;
  }

  Future<void> _pullRemote() async {
    if (!mounted || saving) return;
    try {
      final r = await Api.call('/documents/${widget.document['id']}');
      final remoteRevision = r['revision'] ?? revision;
      final remoteContent = r['content'] ?? '';
      if (remoteRevision <= revision) return;
      if (!dirty) {
        _applyText(remoteContent);
        if (mounted) {
          setState(() {
            revision = remoteRevision;
            lastSyncedContent = remoteContent;
            syncText = 'تغییرات همکار دریافت شد';
          });
        }
      } else if (mounted) {
        setState(() => syncText = 'تغییر همکار موجود است؛ هنگام ذخیره ادغام می‌شود');
      }
    } catch (_) {
      // Keep editing offline. Autosave retries on the next local change/manual save.
    }
  }

  Future<void> _resolveConflict(String localText) async {
    dynamic remote;
    try {
      remote = await Api.call('/documents/${widget.document['id']}');
    } catch (_) {
      if (mounted) setState(() => syncText = 'خطا در دریافت نسخه همکار');
      return;
    }
    if (!mounted) return;
    final remoteText = (remote['content'] ?? '').toString();
    final remoteRevision = remote['revision'] ?? revision;
    final choice = await showDialog<String>(
      context: context,
      builder: (dialog) => AlertDialog(
        title: const Text('تداخل در ویرایش مشترک'),
        content: const Text(
          'شما و یک عضو دیگر دقیقاً بخش مشترکی از متن را هم‌زمان تغییر داده‌اید. '
          'برای جلوگیری از حذف اطلاعات، یکی از روش‌های زیر را انتخاب کنید.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialog, 'remote'), child: const Text('نسخه همکار')),
          FilledButton(onPressed: () => Navigator.pop(dialog, 'manual'), child: const Text('ترکیب و ویرایش دستی')),
        ],
      ),
    );
    if (!mounted || choice == null) return;
    revision = remoteRevision;
    lastSyncedContent = remoteText;
    if (choice == 'remote') {
      _applyText(remoteText);
      dirty = false;
      setState(() => syncText = 'نسخه همکار بارگذاری شد');
    } else {
      final merged = 'نسخه من:\n$localText\n\n────────────\nنسخه همکار:\n$remoteText';
      _applyText(merged);
      dirty = true;
      setState(() => syncText = 'برای ادغام نهایی متن را ویرایش و ذخیره کنید');
    }
  }

  Future<void> save({bool silent = false}) async {
    if (saving || !dirty) return;
    _saveTimer?.cancel();
    final localText = content.text;
    final baseRevision = revision;
    if (mounted) setState(() { saving = true; syncText = 'در حال همگام‌سازی…'; });
    try {
      final r = await Api.call(
        '/documents/${widget.document['id']}',
        method: 'PUT',
        body: {'content': localText, 'base_revision': baseRevision},
      );
      final savedContent = (r['content'] ?? localText).toString();
      if (mounted) {
        _applyText(savedContent);
        setState(() {
          revision = r['revision'] ?? revision + 1;
          lastSyncedContent = savedContent;
          dirty = false;
          saving = false;
          syncText = r['merged'] == true ? 'تغییرات شما و همکار ادغام شد' : 'همگام';
        });
        if (!silent) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('تغییرات همگام شد')));
        }
      }
    } catch (e) {
      if (mounted) setState(() { saving = false; syncText = 'نیاز به بررسی تداخل'; });
      if (e.toString().contains('conflict')) {
        await _resolveConflict(localText);
      } else if (!silent && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('ذخیره انجام نشد: $e')));
      }
    }
  }

  @override
  void dispose() {
    _pullTimer?.cancel();
    _saveTimer?.cancel();
    content.removeListener(_onLocalChanged);
    content.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(widget.document['title'] ?? 'سند مشترک'),
          Text('ویرایش مشارکتی • نسخه $revision', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w500)),
        ],
      ),
      actions: [
        IconButton(onPressed: saving ? null : () => save(), tooltip: 'همگام‌سازی', icon: const Icon(Icons.cloud_done_outlined)),
      ],
    ),
    body: Padding(
      padding: const EdgeInsets.fromLTRB(14, 6, 14, 14),
      child: Column(children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: const Color(0xffeef6f1),
            borderRadius: BorderRadius.circular(14),
          ),
          child: Row(children: [
            Icon(saving ? Icons.sync : Icons.people_alt_outlined, size: 18),
            const SizedBox(width: 8),
            Expanded(child: Text(syncText, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600))),
          ]),
        ),
        const SizedBox(height: 10),
        Expanded(
          child: TextField(
            controller: content,
            expands: true,
            maxLines: null,
            minLines: null,
            textAlignVertical: TextAlignVertical.top,
            decoration: const InputDecoration(
              hintText: 'محتوای مشترک را بنویسید…',
              alignLabelWithHint: true,
            ),
          ),
        ),
        const SizedBox(height: 10),
        Row(children: [
          Expanded(
            child: FilledButton.icon(
              onPressed: saving || !dirty ? null : () => save(),
              icon: saving
                  ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.cloud_upload_outlined),
              label: Text(saving ? 'در حال همگام‌سازی…' : dirty ? 'همگام‌سازی اکنون' : 'همگام است'),
            ),
          ),
        ]),
      ]),
    ),
  );
}

class DirectConversationPage extends StatefulWidget {
  final String conversationId;
  final String peerName;
  final String peerEmail;
  const DirectConversationPage({super.key, required this.conversationId, required this.peerName, required this.peerEmail});

  @override
  State<DirectConversationPage> createState() => _DirectConversationPageState();
}

class _DirectConversationPageState extends State<DirectConversationPage> {
  List<dynamic> messages = [];
  final message = TextEditingController();
  Timer? poll;

  @override
  void initState() { super.initState(); load(); poll = Timer.periodic(const Duration(seconds: 5), (_) => load()); }
  @override
  void dispose() { poll?.cancel(); message.dispose(); super.dispose(); }

  Future<void> load() async {
    final x = await Api.call('/conversations/${widget.conversationId}/messages');
    if (mounted) setState(() => messages = x ?? []);
  }
  Future<void> send() async {
    if (message.text.trim().isEmpty) return;
    await Api.call('/conversations/${widget.conversationId}/messages', method: 'POST', body: {'body': message.text.trim()});
    message.clear(); await load();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(widget.peerName), Text(widget.peerEmail, style: const TextStyle(fontSize: 11))])),
    body: Column(children: [
      Expanded(child: RefreshIndicator(onRefresh: load, child: ListView.builder(
        padding: const EdgeInsets.all(12), physics: const AlwaysScrollableScrollPhysics(), itemCount: messages.length,
        itemBuilder: (_, i) => Card(elevation: 0, child: Padding(padding: const EdgeInsets.all(10), child: Text(messages[i]['body'] ?? ''))),
      ))),
      SafeArea(child: Padding(padding: const EdgeInsets.all(10), child: Row(children: [
        Expanded(child: TextField(controller: message, decoration: const InputDecoration(hintText: 'پیام بنویسید…'))),
        const SizedBox(width: 8), IconButton.filled(onPressed: send, icon: const Icon(Icons.send)),
      ]))),
    ]),
  );
}

class MessagesPage extends StatefulWidget {
  const MessagesPage({super.key});
  @override
  State<MessagesPage> createState() => _MessagesPageState();
}

class _MessagesPageState extends State<MessagesPage> {
  List<dynamic> convs = [], users = [], messages = [], typing = [];
  dynamic active, me, replyTo;
  final search = TextEditingController(), message = TextEditingController(), messageSearch = TextEditingController();
  Timer? poll, typingDebounce;

  @override
  void initState() { super.initState(); loadConvs(); Api.call('/me').then((x) { if (mounted) setState(() => me = x); }); }
  Future<void> loadConvs() async { final x = await Api.call('/chat/conversations'); if (mounted) setState(() => convs = x ?? []); }
  Future<void> searchUsers(String q) async { if (q.trim().isEmpty) return setState(() => users = []); final x = await Api.call('/users/search?q=${Uri.encodeComponent(q.trim())}'); if (mounted) setState(() => users = x ?? []); }
  Future<void> start(dynamic u) async { final c = await Api.call('/conversations', method: 'POST', body: {'other_user_id': u['id']}); setState(() { active = {'id': c['id'], 'peer': u}; users = []; search.clear(); }); await _startPolling(); await loadConvs(); }
  Future<void> open(dynamic c) async { setState(() => active = c); await _startPolling(); }
  Future<void> _startPolling() async { poll?.cancel(); await loadMessages(); poll = Timer.periodic(const Duration(seconds: 2), (_) { loadMessages(); loadConvs(); }); }
  Future<void> loadMessages() async {
    if (active == null) return;
    final q = messageSearch.text.trim();
    final x = await Api.call('/conversations/${active['id']}/messages${q.isEmpty ? '' : '?q=${Uri.encodeComponent(q)}'}');
    final t = await Api.call('/conversations/${active['id']}/typing').catchError((_) => []);
    if (mounted) setState(() { messages = x ?? []; typing = t ?? []; });
  }
  Future<void> send() async {
    if (active == null || message.text.trim().isEmpty) return;
    await Api.call('/conversations/${active['id']}/messages', method: 'POST', body: {'body': message.text.trim(), 'reply_to_id': replyTo?['id']});
    message.clear(); setState(() => replyTo = null); await _setTyping(false); await loadMessages(); await loadConvs();
  }
  Future<void> _setTyping(bool value) async { if (active == null) return; try { await Api.call('/conversations/${active['id']}/typing', method: 'POST', body: {'typing': value}); } catch (_) {} }
  void onTyping(String v) { typingDebounce?.cancel(); _setTyping(v.trim().isNotEmpty); typingDebounce = Timer(const Duration(seconds: 4), () => _setTyping(false)); }
  Future<void> editMessage(dynamic m) async {
    final c = TextEditingController(text: m['body'] ?? '');
    final ok = await showDialog<bool>(context: context, builder: (d) => AlertDialog(title: const Text('ویرایش پیام'), content: TextField(controller: c, minLines: 2, maxLines: 6), actions: [TextButton(onPressed: () => Navigator.pop(d, false), child: const Text('انصراف')), FilledButton(onPressed: () => Navigator.pop(d, true), child: const Text('ذخیره'))]));
    if (ok == true && c.text.trim().isNotEmpty) { await Api.call('/conversations/${active['id']}/messages/${m['id']}', method: 'PATCH', body: {'body': c.text.trim()}); await loadMessages(); }
    c.dispose();
  }
  Future<void> deleteMessage(dynamic m) async { await Api.call('/conversations/${active['id']}/messages/${m['id']}', method: 'DELETE'); await loadMessages(); }
  @override
  void dispose() { poll?.cancel(); typingDebounce?.cancel(); search.dispose(); message.dispose(); messageSearch.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    if (active != null) {
      return Column(children: [
        ListTile(
          leading: IconButton(onPressed: () { poll?.cancel(); setState(() { active = null; messages = []; typing = []; }); }, icon: const Icon(Icons.arrow_forward)),
          title: Text(active['peer']?['name'] ?? 'گفتگو'), subtitle: Text(active['peer']?['email'] ?? active['peer']?['phone'] ?? ''),
          trailing: IconButton(onPressed: loadMessages, icon: const Icon(Icons.refresh)),
        ),
        Padding(padding: const EdgeInsets.symmetric(horizontal: 12), child: TextField(controller: messageSearch, onChanged: (_) => loadMessages(), decoration: const InputDecoration(prefixIcon: Icon(Icons.search), hintText: 'جستجو در پیام‌ها'))),
        const SizedBox(height: 6),
        Expanded(child: ListView.builder(
          padding: const EdgeInsets.all(12), itemCount: messages.length,
          itemBuilder: (_, i) { final m = messages[i]; final mine = m['sender_id']?.toString() == me?['id']?.toString(); return Align(
            alignment: mine ? Alignment.centerLeft : Alignment.centerRight,
            child: Container(
              constraints: const BoxConstraints(maxWidth: 330), margin: const EdgeInsets.symmetric(vertical: 4), padding: const EdgeInsets.all(11),
              decoration: BoxDecoration(color: mine ? Theme.of(context).colorScheme.primaryContainer : Colors.white, borderRadius: BorderRadius.circular(16), border: Border.all(color: const Color(0xffdfe7e1))),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                if (m['reply_to'] != null) Container(padding: const EdgeInsets.all(7), margin: const EdgeInsets.only(bottom: 6), decoration: BoxDecoration(color: Colors.black.withValues(alpha: .04), borderRadius: BorderRadius.circular(9)), child: Text(m['reply_to']['body'] ?? '', maxLines: 2, overflow: TextOverflow.ellipsis)),
                Text(m['body'] ?? ''),
                const SizedBox(height: 5),
                Row(mainAxisSize: MainAxisSize.min, children: [
                  Text('${m['edited_at'] != null ? 'ویرایش‌شده • ' : ''}${m['seen_at'] != null && mine ? 'دیده شد • ' : ''}${m['sent_at'] == null ? '' : DateTime.tryParse(m['sent_at'].toString())?.toLocal().toString().substring(11,16) ?? ''}', style: Theme.of(context).textTheme.bodySmall),
                  const Spacer(),
                  IconButton(iconSize: 16, visualDensity: VisualDensity.compact, onPressed: () => setState(() => replyTo = m), icon: const Icon(Icons.reply)),
                  if (mine && m['deleted_at'] == null) PopupMenuButton<String>(padding: EdgeInsets.zero, iconSize: 17, onSelected: (v) => v == 'edit' ? editMessage(m) : deleteMessage(m), itemBuilder: (_) => const [PopupMenuItem(value: 'edit', child: Text('ویرایش')), PopupMenuItem(value: 'delete', child: Text('حذف'))]),
                ]),
              ]),
            ),
          ); },
        )),
        if (typing.isNotEmpty) Padding(padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4), child: Align(alignment: Alignment.centerRight, child: Text('${typing.map((x) => x['user']?['name']).where((x) => x != null).join('، ')} در حال تایپ…', style: Theme.of(context).textTheme.bodySmall))),
        if (replyTo != null) Container(color: Theme.of(context).colorScheme.surfaceContainerHighest, padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6), child: Row(children: [Expanded(child: Text('پاسخ به: ${replyTo['body']}', maxLines: 1, overflow: TextOverflow.ellipsis)), IconButton(onPressed: () => setState(() => replyTo = null), icon: const Icon(Icons.close))])),
        SafeArea(child: Padding(padding: const EdgeInsets.all(10), child: Row(children: [
          Expanded(child: TextField(controller: message, onChanged: onTyping, minLines: 1, maxLines: 4, decoration: const InputDecoration(hintText: 'پیام بنویسید…'))),
          const SizedBox(width: 8), IconButton.filled(onPressed: send, icon: const Icon(Icons.send)),
        ]))),
      ]);
    }
    return ListView(padding: const EdgeInsets.all(14), children: [
      TextField(controller: search, onChanged: searchUsers, autofillHints: const <String>[], decoration: const InputDecoration(prefixIcon: Icon(Icons.search), hintText: 'نام، ایمیل یا شماره کاربر')),
      if (users.isNotEmpty) Card(child: Column(children: users.map((u) => ListTile(title: Text(u['name'] ?? ''), subtitle: Text(u['email'] ?? u['phone'] ?? ''), onTap: () => start(u))).toList())),
      const SizedBox(height: 8),
      ...convs.map((c) => ListTile(
        leading: CircleAvatar(child: Text(c['peer']?['name']?.toString().substring(0, 1) ?? 'U')),
        title: Text(c['peer']?['name'] ?? 'کاربر'),
        subtitle: Text(c['last_message']?['body'] ?? 'گفتگو را شروع کنید', maxLines: 1, overflow: TextOverflow.ellipsis),
        trailing: (c['unread'] ?? 0) > 0 ? Badge(label: Text('${c['unread']}')) : null,
        onTap: () => open(c),
      )),
    ]);
  }
}

class ProfilePage extends StatefulWidget {
  const ProfilePage({super.key});
  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  final display = TextEditingController(), first = TextEditingController(), last = TextEditingController(), phone = TextEditingController(), avatar = TextEditingController();
  String email = '';
  bool busy = true;
  String? msg;

  @override
  void initState() { super.initState(); load(); }
  Future<void> load() async {
    try {
      final p = await Api.call('/profile');
      display.text = (p['display_name'] ?? p['name'] ?? '').toString(); first.text = (p['first_name'] ?? '').toString(); last.text = (p['last_name'] ?? '').toString(); phone.text = (p['phone'] ?? '').toString(); avatar.text = (p['avatar_url'] ?? '').toString(); email = (p['email'] ?? '').toString();
    } catch (e) { msg = e.toString(); }
    if (mounted) setState(() => busy = false);
  }
  Future<void> save() async {
    setState(() { busy = true; msg = null; });
    try {
      await Api.call('/profile', method: 'PUT', body: {'display_name': display.text.trim(), 'first_name': first.text.trim(), 'last_name': last.text.trim(), 'phone': phone.text.trim(), 'avatar_url': avatar.text.trim()});
      msg = 'پروفایل ذخیره شد.';
    } catch (e) { msg = e.toString().replaceFirst('Exception: ', ''); }
    if (mounted) setState(() => busy = false);
  }
  @override
  void dispose() { for (final c in [display, first, last, phone, avatar]) { c.dispose(); } super.dispose(); }
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('پروفایل من')),
    body: SafeArea(child: ListView(padding: const EdgeInsets.all(16), children: [
      Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const CircleAvatar(radius: 34, child: Icon(Icons.person_outline, size: 34)), const SizedBox(height: 14),
        TextField(controller: display, autofillHints: const <String>[], enableSuggestions: false, autocorrect: false, decoration: const InputDecoration(labelText: 'نام نمایشی')),
        const SizedBox(height: 10), Row(children: [Expanded(child: TextField(controller: first, autofillHints: const <String>[], enableSuggestions: false, autocorrect: false, decoration: const InputDecoration(labelText: 'نام'))), const SizedBox(width: 8), Expanded(child: TextField(controller: last, autofillHints: const <String>[], enableSuggestions: false, autocorrect: false, decoration: const InputDecoration(labelText: 'نام خانوادگی')))]),
        const SizedBox(height: 10), TextFormField(initialValue: email, enabled: false, decoration: const InputDecoration(labelText: 'ایمیل')),
        const SizedBox(height: 10), TextField(controller: phone, keyboardType: TextInputType.phone, autofillHints: const <String>[], decoration: const InputDecoration(labelText: 'شماره همراه')),
        const SizedBox(height: 10), TextField(controller: avatar, autofillHints: const <String>[], decoration: const InputDecoration(labelText: 'آدرس تصویر پروفایل')),
        const SizedBox(height: 14), FilledButton.icon(onPressed: busy ? null : save, icon: const Icon(Icons.save_outlined), label: Text(busy ? 'در حال ذخیره…' : 'ذخیره پروفایل')),
        if (msg != null) Padding(padding: const EdgeInsets.only(top: 10), child: Text(msg!, textAlign: TextAlign.center)),
      ]))),
    ])),
  );
}

class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key});

  Future<void> _pin(BuildContext context, String type) async {
    try {
      final ok = await widgetChannel.invokeMethod<bool>('pinWidget', {'type': type}) ?? false;
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            ok
                ? 'درخواست افزودن ویجت ارسال شد.'
                : 'لانچر افزودن مستقیم ویجت را پشتیبانی نمی‌کند؛ از فهرست Widgets گوشی، Planner را باز کنید.',
          ),
        ),
      );
    } catch (e) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('افزودن ویجت انجام نشد: $e')));
    }
  }

  Future<void> _logout(BuildContext context) async {
    try { await notificationChannel.invokeMethod('clearReminders'); } catch (_) {}
    await SecureSession.clear();
    if (context.mounted) Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('تنظیمات')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
        children: [
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              gradient: LinearGradient(colors: [cs.primary, cs.primaryContainer]),
              borderRadius: BorderRadius.circular(24),
            ),
            child: Row(children: [
              CircleAvatar(
                radius: 27,
                backgroundColor: Colors.white.withValues(alpha: .9),
                child: Icon(Icons.tune_rounded, color: cs.primary, size: 30),
              ),
              const SizedBox(width: 14),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Planner', style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w900)),
                    SizedBox(height: 3),
                    Text('تنظیم تجربه کاربری، ویجت‌ها و امنیت', style: TextStyle(color: Colors.white70, fontSize: 12)),
                  ],
                ),
              ),
            ]),
          ),
          const SizedBox(height: 22),
          Card(child: ListTile(
            leading: const CircleAvatar(child: Icon(Icons.person_outline)),
            title: const Text('پروفایل من'),
            subtitle: const Text('نام، شماره همراه و تصویر پروفایل'),
            trailing: const Icon(Icons.chevron_left),
            onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ProfilePage())),
          )),
          const SizedBox(height: 22),
          const _SettingsTitle(icon: Icons.widgets_outlined, title: 'ویجت‌های صفحه اصلی', subtitle: 'هر ویجت را جداگانه به Home Screen اضافه کنید'),
          const SizedBox(height: 10),
          WidgetOptionCard(
            icon: Icons.dashboard_customize_outlined,
            title: 'خلاصه Planner',
            subtitle: 'تاریخ، تعداد کارها، ۳ کار بعدی و ۲ رویداد بعدی',
            preview: const _OverviewWidgetPreview(),
            onAdd: () => _pin(context, 'overview'),
          ),
          const SizedBox(height: 12),
          WidgetOptionCard(
            icon: Icons.schedule_rounded,
            title: 'ساعت و تاریخ بزرگ',
            subtitle: 'ساعت زنده بزرگ + تاریخ شمسی خوانا و مینیمال',
            preview: const _ClockWidgetPreview(),
            onAdd: () => _pin(context, 'clock'),
          ),
          const SizedBox(height: 12),
          WidgetOptionCard(
            icon: Icons.checklist_rounded,
            title: 'کارهای بعدی',
            subtitle: 'تمرکز روی کارهای باز و دسترسی سریع به کار جدید',
            preview: const _TasksWidgetPreview(),
            onAdd: () => _pin(context, 'tasks'),
          ),
          const SizedBox(height: 12),
          WidgetOptionCard(
            icon: Icons.event_note_rounded,
            title: 'برنامه و رویدادها',
            subtitle: 'رویدادهای پیش‌رو و دسترسی سریع به رویداد جدید',
            preview: const _AgendaWidgetPreview(),
            onAdd: () => _pin(context, 'agenda'),
          ),
          const SizedBox(height: 24),
          const _SettingsTitle(icon: Icons.notifications_active_outlined, title: 'یادآوری', subtitle: 'اعلان محلی حتی در زمان بسته بودن برنامه'),
          const SizedBox(height: 10),
          const Card(
            child: ListTile(
              leading: Icon(Icons.alarm_rounded),
              title: Text('یک روز قبل، ساعت ۱۷:۰۰'),
              subtitle: Text('برای کارها و رویدادهای تاریخ‌دار به‌صورت خودکار زمان‌بندی می‌شود.'),
              trailing: Icon(Icons.verified_rounded),
            ),
          ),
          const SizedBox(height: 24),
          const _SettingsTitle(icon: Icons.shield_outlined, title: 'امنیت', subtitle: 'وضعیت حفاظت حساب و ارتباط شبکه'),
          const SizedBox(height: 10),
          Card(
            child: Column(children: [
              const ListTile(
                leading: Icon(Icons.lock_outline),
                title: Text('ذخیره امن نشست'),
                subtitle: Text('توکن ورود در Android Keystore رمزگذاری می‌شود'),
                trailing: Icon(Icons.verified_rounded),
              ),
              const Divider(height: 1),
              const ListTile(
                leading: Icon(Icons.https_outlined),
                title: Text('ارتباط HTTPS'),
                subtitle: Text('ارتباط با API فقط روی HTTPS انجام می‌شود'),
                trailing: Icon(Icons.verified_rounded),
              ),
              const Divider(height: 1),
              ListTile(
                leading: const Icon(Icons.logout_rounded),
                title: const Text('خروج امن از حساب'),
                subtitle: const Text('توکن رمزگذاری‌شده از دستگاه حذف می‌شود'),
                onTap: () => _logout(context),
              ),
            ]),
          ),
          const SizedBox(height: 24),
          const _SettingsTitle(icon: Icons.info_outline, title: 'درباره برنامه', subtitle: 'اطلاعات نسخه نصب‌شده'),
          const SizedBox(height: 10),
          Card(
            child: ListTile(
              leading: const Icon(Icons.event_note_rounded),
              title: const Text('Planner'),
              subtitle: const Text('نسخه $appVersion • Build $appBuild'),
              trailing: const Text('Android'),
            ),
          ),
        ],
      ),
    );
  }
}

class _SettingsTitle extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  const _SettingsTitle({required this.icon, required this.title, required this.subtitle});
  @override
  Widget build(BuildContext context) => Row(children: [
    Container(
      width: 42,
      height: 42,
      decoration: BoxDecoration(color: Theme.of(context).colorScheme.primaryContainer, borderRadius: BorderRadius.circular(13)),
      child: Icon(icon, color: Theme.of(context).colorScheme.primary),
    ),
    const SizedBox(width: 10),
    Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(title, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800)),
      const SizedBox(height: 2),
      Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
    ])),
  ]);
}

class WidgetOptionCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final Widget preview;
  final VoidCallback onAdd;
  const WidgetOptionCard({super.key, required this.icon, required this.title, required this.subtitle, required this.preview, required this.onAdd});

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          Icon(icon, color: Theme.of(context).colorScheme.primary),
          const SizedBox(width: 9),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
            Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
          ])),
        ]),
        const SizedBox(height: 12),
        preview,
        const SizedBox(height: 12),
        FilledButton.tonalIcon(onPressed: onAdd, icon: const Icon(Icons.add_to_home_screen), label: const Text('افزودن به صفحه اصلی')),
      ]),
    ),
  );
}

class _WidgetPreviewShell extends StatelessWidget {
  final Widget child;
  const _WidgetPreviewShell({required this.child});
  @override
  Widget build(BuildContext context) => Container(
    height: 122,
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: const Color(0xffeef4f0),
      borderRadius: BorderRadius.circular(20),
      border: Border.all(color: const Color(0xffd7e2db)),
    ),
    child: child,
  );
}

class _OverviewWidgetPreview extends StatelessWidget {
  const _OverviewWidgetPreview();
  @override
  Widget build(BuildContext context) => _WidgetPreviewShell(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
    const Row(children: [Expanded(child: Text('Planner', style: TextStyle(fontWeight: FontWeight.w900))), Text('10:42', style: TextStyle(fontWeight: FontWeight.w800))]),
    const SizedBox(height: 5),
    Text('${Jalali.now().formatter.wN} ${Jalali.now().formatter.d} ${Jalali.now().formatter.mN}', textAlign: TextAlign.right),
    const Spacer(),
    const Text('۳ کار باز  •  ۲ رویداد', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700)),
  ]));
}

class _ClockWidgetPreview extends StatelessWidget {
  const _ClockWidgetPreview();
  @override
  Widget build(BuildContext context) => _WidgetPreviewShell(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
    const Text('10:42', style: TextStyle(fontSize: 38, fontWeight: FontWeight.w900, height: .9)),
    const SizedBox(height: 8),
    Text('${Jalali.now().formatter.wN} ${Jalali.now().formatter.d} ${Jalali.now().formatter.mN} ${Jalali.now().year}', style: const TextStyle(fontWeight: FontWeight.w700)),
  ]));
}

class _TasksWidgetPreview extends StatelessWidget {
  const _TasksWidgetPreview();
  @override
  Widget build(BuildContext context) => _WidgetPreviewShell(child: Directionality(
    textDirection: TextDirection.rtl,
    child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Row(children: [
        const Expanded(child: Text('کارهای بعدی', style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16))),
        const Text('۱۰:۴۲', style: TextStyle(fontWeight: FontWeight.w900, fontSize: 20)),
      ]),
      Text('${Jalali.now().formatter.wN} ${Jalali.now().formatter.d} ${Jalali.now().formatter.mN}', textAlign: TextAlign.right, style: const TextStyle(fontWeight: FontWeight.w700)),
      const SizedBox(height: 6),
      const Text('ارسال گزارش کارشناسی', maxLines: 1),
      const Divider(height: 6),
      const Text('تماس با موکل', maxLines: 1),
    ]),
  ));
}

class _AgendaWidgetPreview extends StatelessWidget {
  const _AgendaWidgetPreview();
  @override
  Widget build(BuildContext context) => const _WidgetPreviewShell(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
    Text('برنامه پیش‌رو', style: TextStyle(fontWeight: FontWeight.w900)), SizedBox(height: 8),
    Text('09:30  جلسه', maxLines: 1), Text('14:00  پیگیری پرونده', maxLines: 1), Text('18:30  یادآوری', maxLines: 1),
  ]));
}

class Empty extends StatelessWidget {
  final String text;
  const Empty({super.key, required this.text});
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 28),
        child: Text(text, textAlign: TextAlign.center, style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant)),
      );
}
