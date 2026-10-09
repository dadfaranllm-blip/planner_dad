import 'dart:async';

import 'package:flutter/material.dart';
import 'package:shamsi_date/shamsi_date.dart';

import 'api.dart';
import 'auth_store.dart';
import 'local_store.dart';
import 'push_service.dart';
import 'social_auth_service.dart';
import 'sync_service.dart';
import 'voice_call_service.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  PushService.installBackgroundHandler();
  runApp(const PlannerApp());
}

class PlannerApp extends StatelessWidget {
  const PlannerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Planner',
      locale: const Locale('fa', 'IR'),
      builder: (context, child) => Directionality(textDirection: TextDirection.rtl, child: child ?? const SizedBox.shrink()),
      theme: ThemeData(
        useMaterial3: true,
        colorSchemeSeed: const Color(0xff315c4b),
        scaffoldBackgroundColor: const Color(0xfffafafa),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(),
        ),
      ),
      home: const Gate(),
    );
  }
}

Color hexColor(dynamic raw) {
  final s = (raw ?? '#64748B').toString().replaceFirst('#', '');
  final v = int.tryParse(s, radix: 16) ?? 0x64748B;
  return Color(0xff000000 | v);
}

const _persianMonths = <String>[
  'فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور',
  'مهر','آبان','آذر','دی','بهمن','اسفند'
];

String faDigits(Object value) {
  const en = '0123456789';
  const fa = '۰۱۲۳۴۵۶۷۸۹';
  var out = value.toString();
  for (var i = 0; i < en.length; i++) {
    out = out.replaceAll(en[i], fa[i]);
  }
  return out;
}

String persianDate(dynamic raw, {bool withTime = true}) {
  if (raw == null || raw.toString().trim().isEmpty) return '';
  final dt = DateTime.tryParse(raw.toString())?.toLocal();
  if (dt == null) return '';
  final j = Jalali.fromDateTime(dt);
  final date = '${faDigits(j.day)} ${_persianMonths[j.month - 1]} ${faDigits(j.year)}';
  if (!withTime) return date;
  final hh = dt.hour.toString().padLeft(2, '0');
  final mm = dt.minute.toString().padLeft(2, '0');
  return '$date، ${faDigits(hh)}:${faDigits(mm)}';
}

Future<DateTime?> pickPersianDateTime(BuildContext context, DateTime? initial) async {
  final base = initial ?? DateTime.now();
  var j = Jalali.fromDateTime(base);
  var year = j.year;
  var month = j.month;
  var day = j.day;
  var hour = base.hour;
  var minute = (base.minute ~/ 5) * 5;
  final result = await showDialog<bool>(
    context: context,
    builder: (dialogContext) => StatefulBuilder(
      builder: (context, setState) {
        final monthLength = Jalali(year, month).monthLength;
        if (day > monthLength) day = monthLength;
        return AlertDialog(
          title: const Text('انتخاب تاریخ و زمان'),
          content: SingleChildScrollView(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Row(children: [
                Expanded(child: DropdownButtonFormField<int>(value: day, decoration: const InputDecoration(labelText: 'روز'), items: [for (var d = 1; d <= monthLength; d++) DropdownMenuItem(value: d, child: Text(faDigits(d)))], onChanged: (v) => setState(() => day = v ?? day))),
                const SizedBox(width: 6),
                Expanded(flex: 2, child: DropdownButtonFormField<int>(value: month, decoration: const InputDecoration(labelText: 'ماه'), items: [for (var m = 1; m <= 12; m++) DropdownMenuItem(value: m, child: Text(_persianMonths[m - 1]))], onChanged: (v) => setState(() { month = v ?? month; day = day.clamp(1, Jalali(year, month).monthLength).toInt(); }))),
                const SizedBox(width: 6),
                Expanded(child: DropdownButtonFormField<int>(value: year, decoration: const InputDecoration(labelText: 'سال'), items: [for (var y = j.year - 2; y <= j.year + 5; y++) DropdownMenuItem(value: y, child: Text(faDigits(y)))], onChanged: (v) => setState(() { year = v ?? year; day = day.clamp(1, Jalali(year, month).monthLength).toInt(); }))),
              ]),
              const SizedBox(height: 12),
              Row(children: [
                Expanded(child: DropdownButtonFormField<int>(value: hour, decoration: const InputDecoration(labelText: 'ساعت'), items: [for (var h = 0; h < 24; h++) DropdownMenuItem(value: h, child: Text(faDigits(h.toString().padLeft(2, '0'))))], onChanged: (v) => setState(() => hour = v ?? hour))),
                const SizedBox(width: 8),
                Expanded(child: DropdownButtonFormField<int>(value: minute, decoration: const InputDecoration(labelText: 'دقیقه'), items: [for (var m = 0; m < 60; m += 5) DropdownMenuItem(value: m, child: Text(faDigits(m.toString().padLeft(2, '0'))))], onChanged: (v) => setState(() => minute = v ?? minute))),
              ]),
            ]),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('انصراف')),
            FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('انتخاب')),
          ],
        );
      },
    ),
  );
  if (result != true) return null;
  final g = Jalali(year, month, day).toDateTime();
  return DateTime(g.year, g.month, g.day, hour, minute);
}

Color memberColor(dynamic id) {
  const palette = <Color>[
    Color(0xff2563EB), Color(0xff16A34A), Color(0xffDC2626),
    Color(0xff9333EA), Color(0xffEA580C), Color(0xff0891B2),
    Color(0xffDB2777), Color(0xff4F46E5), Color(0xff65A30D),
    Color(0xffB45309), Color(0xff0F766E), Color(0xff7C3AED),
  ];
  final text = (id ?? '').toString();
  var hash = 0;
  for (final code in text.codeUnits) {
    hash = ((hash * 31) + code) & 0x7fffffff;
  }
  return palette[hash % palette.length];
}

void showAppError(BuildContext context, Object error) {
  if (!context.mounted) return;
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text(ErrorHandler.message(error))),
  );
}

class Gate extends StatefulWidget {
  const Gate({super.key});

  @override
  State<Gate> createState() => _GateState();
}

class _GateState extends State<Gate> {
  bool? has;

  @override
  void initState() {
    super.initState();
    AuthStore.hasSession().then((value) {
      if (mounted) {
        setState(() => has = value);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    if (has == null) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }
    return has! ? const Home() : const Login();
  }
}

class Login extends StatefulWidget {
  const Login({super.key});

  @override
  State<Login> createState() => _LoginState();
}

class _LoginState extends State<Login> {
  final email = TextEditingController();
  final pass = TextEditingController();

  String? err;
  bool busy = false;

  Future<void> _finish(Future<void> Function() fn) async {
    setState(() => busy = true);
    try {
      await fn();
      if (mounted) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (_) => const Home()),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(
          () => err = ErrorHandler.message(e),
        );
      }
    } finally {
      if (mounted) {
        setState(() => busy = false);
      }
    }
  }

  Future<void> go() {
    return _finish(() async {
      final r = Map<String, dynamic>.from(
        await Api.call(
          '/auth/login',
          method: 'POST',
          body: {
            'email': email.text.trim(),
            'password': pass.text,
            'platform': 'mobile',
            'device_name': 'personal-phone',
          },
        ),
      );
      await AuthStore.save(r);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(
                      'برنامه‌ریز',
                      textAlign: TextAlign.right,
                      style: TextStyle(
                        fontSize: 30,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'اطلاعات این گوشی محلی می‌ماند و پس از ورود در پس‌زمینه همگام می‌شود.',
                      textAlign: TextAlign.right,
                    ),
                    const SizedBox(height: 28),
                    TextField(
                      controller: email,
                      keyboardType: TextInputType.emailAddress,
                      decoration: const InputDecoration(labelText: 'ایمیل'),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: pass,
                      obscureText: true,
                      decoration: const InputDecoration(labelText: 'رمز عبور'),
                    ),
                    if (err != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 10),
                        child: Text(err!, textAlign: TextAlign.right),
                      ),
                    const SizedBox(height: 18),
                    FilledButton(
                      onPressed: busy ? null : go,
                      child: Text(busy ? '...' : 'ورود'),
                    ),
                    const Padding(
                      padding: EdgeInsets.symmetric(vertical: 12),
                      child: Row(
                        children: [
                          Expanded(child: Divider()),
                          Padding(
                            padding: EdgeInsets.symmetric(horizontal: 10),
                            child: Text('یا'),
                          ),
                          Expanded(child: Divider()),
                        ],
                      ),
                    ),
                    OutlinedButton.icon(
                      onPressed:
                          busy ? null : () => _finish(SocialAuthService.google),
                      icon: const Icon(Icons.g_mobiledata, size: 28),
                      label: const Text('ورود با Google / Gmail'),
                    ),
                    const SizedBox(height: 8),
                    OutlinedButton.icon(
                      onPressed:
                          busy ? null : () => _finish(SocialAuthService.apple),
                      icon: const Icon(Icons.apple),
                      label: const Text('ورود با Apple'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

typedef ActionFn = Future<void> Function(String kind, String id, String action);
typedef EditFn = Future<void> Function(String kind, Map<String, dynamic> item);
typedef DeleteFn = Future<void> Function(String kind, Map<String, dynamic> item);

class Home extends StatefulWidget {
  const Home({super.key});

  @override
  State<Home> createState() => _HomeState();
}

class _HomeState extends State<Home> {
  int tab = 0;
  List<Map<String, dynamic>> tasks = [];
  List<Map<String, dynamic>> events = [];
  List<Map<String, dynamic>> workspaces = [];
  List<Map<String, dynamic>> conversations = [];

  bool localLoading = true;
  bool syncing = false;

  @override
  void initState() {
    super.initState();
    _openLocal();
  }

  Future<void> _openLocal() async {
    await _reloadLocal();
    if (mounted) {
      setState(() => localLoading = false);
    }

    unawaited(PushService.initialize());
    unawaited(_sync());
  }

  Future<void> _reloadLocal() async {
    final all = await Future.wait([
      LocalStore.list('task'),
      LocalStore.list('event'),
      LocalStore.list('workspace'),
      LocalStore.list('conversation'),
    ]);

    if (!mounted) return;

    int newestFirst(Map<String, dynamic> a, Map<String, dynamic> b, String primary) {
      String value(Map<String, dynamic> x) =>
          (x['created_at'] ?? x[primary] ?? x['updated_at'] ?? '').toString();
      return value(b).compareTo(value(a));
    }

    final nextTasks = List<Map<String, dynamic>>.from(all[0])
      ..sort((a, b) => newestFirst(a, b, 'due_at'));
    final nextEvents = List<Map<String, dynamic>>.from(all[1])
      ..sort((a, b) => newestFirst(a, b, 'starts_at'));

    setState(() {
      tasks = nextTasks;
      events = nextEvents;
      workspaces = all[2];
      conversations = all[3];
    });
  }

  Future<void> _sync() async {
    if (syncing) return;

    if (mounted) {
      setState(() => syncing = true);
    }

    try {
      await SyncService.sync();
      await _reloadLocal();
    } finally {
      if (mounted) {
        setState(() => syncing = false);
      }
    }
  }

  Future<void> act(String kind, String id, String action) async {
    final list = kind == 'task' ? tasks : events;
    final i = list.indexWhere((x) => x['id'].toString() == id);
    if (i < 0) return;

    final x = Map<String, dynamic>.from(list[i]);

    if (action == 'complete') {
      x['status'] = 'completed';
      x['completed_at'] = DateTime.now().toIso8601String();
    } else {
      x['status'] = 'open';
    }

    await LocalStore.upsert(kind, x);
    await LocalStore.enqueue(
      'POST',
      '/${kind}s/$id/$action',
      action == 'continue' ? <String, dynamic>{} : null,
    );

    await _reloadLocal();
    unawaited(_sync());
  }

  Future<void> editItem(String kind, Map<String, dynamic> item) async {
    final title = TextEditingController(text: (item['title'] ?? '').toString());
    DateTime? when = DateTime.tryParse((kind == 'task' ? item['due_at'] : item['starts_at'])?.toString() ?? '')?.toLocal();
    final ok = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text(kind == 'task' ? 'ویرایش کار' : 'ویرایش رویداد'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(controller: title, textDirection: TextDirection.rtl, decoration: const InputDecoration(labelText: 'عنوان')),
              const SizedBox(height: 12),
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('تاریخ و زمان', textAlign: TextAlign.right),
                subtitle: Text(when == null ? 'انتخاب نشده' : persianDate(when!.toIso8601String()), textAlign: TextAlign.right),
                trailing: const Icon(Icons.calendar_month),
                onTap: () async {
                  final picked = await pickPersianDateTime(context, when);
                  if (picked != null) setDialogState(() => when = picked);
                },
              ),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('انصراف')),
            FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('ذخیره')),
          ],
        ),
      ),
    );
    if (ok != true || title.text.trim().isEmpty) return;
    final updated = Map<String, dynamic>.from(item);
    updated['title'] = title.text.trim();
    updated['updated_at'] = DateTime.now().toIso8601String();
    final body = <String, dynamic>{'title': title.text.trim()};
    if (kind == 'task') {
      updated['due_at'] = when?.toUtc().toIso8601String();
      body['due_at'] = updated['due_at'];
    } else if (when != null) {
      updated['starts_at'] = when!.toUtc().toIso8601String();
      body['starts_at'] = updated['starts_at'];
    }
    await LocalStore.upsert(kind, updated);
    await LocalStore.enqueue('PATCH', '/${kind == 'task' ? 'tasks' : 'events'}/${item['id']}', body);
    await _reloadLocal();
    unawaited(_sync());
  }

  Future<void> deleteItem(String kind, Map<String, dynamic> item) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(kind == 'task' ? 'حذف کار' : 'حذف رویداد'),
        content: Text('«${item['title'] ?? ''}» حذف شود؟ این عملیات پس از همگام‌سازی از سرور هم حذف می‌شود.', textAlign: TextAlign.right),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('انصراف')),
          FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('حذف')),
        ],
      ),
    );
    if (ok != true) return;
    await LocalStore.delete(kind, item['id'].toString());
    await LocalStore.enqueue('DELETE', '/${kind == 'task' ? 'tasks' : 'events'}/${item['id']}');
    await _reloadLocal();
    unawaited(_sync());
  }

  Future<void> addItem(String kind) async {
    final ctl = TextEditingController();
    DateTime? when = kind == 'event' ? DateTime.now().add(const Duration(hours: 1)) : null;
    final ok = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (sheetContext) {
        return StatefulBuilder(builder: (context, setSheetState) {
          final bottom = MediaQuery.of(sheetContext).viewInsets.bottom;
          return Padding(
            padding: EdgeInsets.fromLTRB(20, 20, 20, bottom + 24),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Text(kind == 'task' ? 'کار جدید' : 'رویداد جدید', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
              const SizedBox(height: 12),
              TextField(controller: ctl, autofocus: true, textDirection: TextDirection.rtl, decoration: const InputDecoration(labelText: 'عنوان')),
              const SizedBox(height: 12),
              ListTile(
                title: const Text('تاریخ و زمان', textAlign: TextAlign.right),
                subtitle: Text(when == null ? 'انتخاب نشده' : persianDate(when!.toIso8601String()), textAlign: TextAlign.right),
                trailing: const Icon(Icons.calendar_month),
                onTap: () async {
                  final picked = await pickPersianDateTime(context, when);
                  if (picked != null) setSheetState(() => when = picked);
                },
              ),
              const SizedBox(height: 12),
              SizedBox(width: double.infinity, child: FilledButton(onPressed: () => Navigator.pop(sheetContext, true), child: const Text('ثبت'))),
            ]),
          );
        });
      },
    );
    if (ok != true || ctl.text.trim().isEmpty) return;
    final id = 'local-${DateTime.now().microsecondsSinceEpoch}';
    final created = DateTime.now().toIso8601String();
    final data = <String, dynamic>{'id': id, 'title': ctl.text.trim(), 'status': 'open', 'created_at': created, 'local_only': true, 'shared_with': <dynamic>[]};
    final body = <String, dynamic>{'title': ctl.text.trim()};
    if (kind == 'task') {
      data['due_at'] = when?.toUtc().toIso8601String();
      body['due_at'] = data['due_at'];
    } else {
      when ??= DateTime.now().add(const Duration(hours: 1));
      data['starts_at'] = when!.toUtc().toIso8601String();
      body['starts_at'] = data['starts_at'];
    }
    await LocalStore.upsert(kind, data);
    await LocalStore.enqueue('POST', kind == 'task' ? '/tasks' : '/events', body);
    await _reloadLocal();
    unawaited(_sync());
  }

  @override
  Widget build(BuildContext context) {
    final pages = <Widget>[
      Today(tasks: tasks, events: events, onAct: act, onEdit: editItem, onDelete: deleteItem, onOpenTasks: () => setState(() => tab = 1), onOpenEvents: () => setState(() => tab = 2)),
      Items(kind: 'task', items: tasks, onAct: act, onEdit: editItem, onDelete: deleteItem),
      Items(kind: 'event', items: events, onAct: act, onEdit: editItem, onDelete: deleteItem),
      WorkspaceList(items: workspaces),
      MessengerList(items: conversations),
    ];

    const titles = ['امروز', 'کارها', 'رویدادها', 'محل کار', 'پیام‌ها'];

    return Scaffold(
      appBar: AppBar(
        title: Text(titles[tab]),
        actions: [
          if (tab == 0) PopupMenuButton<String>(icon: const Icon(Icons.add_circle_outline), onSelected: (v) => addItem(v), itemBuilder: (_) => const [PopupMenuItem(value: 'task', child: Text('کار جدید')), PopupMenuItem(value: 'event', child: Text('رویداد جدید'))]),
          if (tab == 1) IconButton(onPressed: () => addItem('task'), icon: const Icon(Icons.add_circle_outline), tooltip: 'کار جدید'),
          if (tab == 2) IconButton(onPressed: () => addItem('event'), icon: const Icon(Icons.add_circle_outline), tooltip: 'رویداد جدید'),
          if (syncing)
            const Padding(
              padding: EdgeInsets.all(14),
              child: SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ),
          IconButton(
            onPressed: _sync,
            icon: const Icon(Icons.sync_rounded),
          ),
        ],
      ),
      body: localLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _sync,
              child: pages[tab],
            ),
      bottomNavigationBar: SafeArea(
        top: false,
        child: NavigationBar(
          selectedIndex: tab,
          onDestinationSelected: (i) => setState(() => tab = i),
          destinations: const [
            NavigationDestination(
              icon: Icon(Icons.today_outlined),
              selectedIcon: Icon(Icons.today),
              label: 'امروز',
            ),
            NavigationDestination(
              icon: Icon(Icons.check_circle_outline),
              label: 'کارها',
            ),
            NavigationDestination(
              icon: Icon(Icons.calendar_month_outlined),
              label: 'رویدادها',
            ),
            NavigationDestination(
              icon: Icon(Icons.groups_outlined),
              label: 'محل کار',
            ),
            NavigationDestination(
              icon: Icon(Icons.chat_bubble_outline),
              label: 'پیام‌ها',
            ),
          ],
        ),
      ),
    );
  }
}

class Today extends StatelessWidget {
  final List<Map<String, dynamic>> tasks;
  final List<Map<String, dynamic>> events;
  final ActionFn onAct;
  final EditFn onEdit;
  final DeleteFn onDelete;
  final VoidCallback onOpenTasks;
  final VoidCallback onOpenEvents;
  const Today({super.key, required this.tasks, required this.events, required this.onAct, required this.onEdit, required this.onDelete, required this.onOpenTasks, required this.onOpenEvents});

  @override
  Widget build(BuildContext context) {
    final open = tasks.where((x) => x['status'] != 'completed').toList();
    final ev = events.where((x) => x['status'] != 'completed').toList();
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: [
        InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: onOpenTasks,
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Row(children: [const Icon(Icons.chevron_left), const Spacer(), Text('کارها · ${faDigits(open.length)}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700))]),
          ),
        ),
        if (open.isEmpty) const Empty(text: 'کاری برای نمایش نیست'),
        ...open.take(5).map((x) => ItemCard(x: x, kind: 'task', onAct: onAct, onEdit: onEdit, onDelete: onDelete)),
        const SizedBox(height: 18),
        InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: onOpenEvents,
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Row(children: [const Icon(Icons.chevron_left), const Spacer(), Text('رویدادها · ${faDigits(ev.length)}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700))]),
          ),
        ),
        if (ev.isEmpty) const Empty(text: 'رویدادی ثبت نشده'),
        ...ev.take(5).map((x) => ItemCard(x: x, kind: 'event', onAct: onAct, onEdit: onEdit, onDelete: onDelete)),
      ],
    );
  }
}

class Items extends StatelessWidget {
  final String kind;
  final List<Map<String, dynamic>> items;
  final ActionFn onAct;
  final EditFn onEdit;
  final DeleteFn onDelete;
  const Items({super.key, required this.kind, required this.items, required this.onAct, required this.onEdit, required this.onDelete});
  @override
  Widget build(BuildContext context) => ListView(
    physics: const AlwaysScrollableScrollPhysics(),
    padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
    children: items.isEmpty
      ? const [Empty(text: 'هنوز چیزی ثبت نشده')]
      : items.map((x) => ItemCard(x: x, kind: kind, onAct: onAct, onEdit: onEdit, onDelete: onDelete)).toList(),
  );
}

class ItemCard extends StatelessWidget {
  final Map<String, dynamic> x;
  final String kind;
  final ActionFn onAct;
  final EditFn onEdit;
  final DeleteFn onDelete;
  const ItemCard({super.key, required this.x, required this.kind, required this.onAct, required this.onEdit, required this.onDelete});

  @override
  Widget build(BuildContext context) {
    final shares = List<Map<String, dynamic>>.from((x['shared_with'] ?? []).map((e) => Map<String, dynamic>.from(e)));
    final date = persianDate(kind == 'task' ? x['due_at'] : x['starts_at']);
    final created = persianDate(x['created_at']);
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Row(children: [
            PopupMenuButton<String>(
              onSelected: (v) => v == 'edit' ? onEdit(kind, x) : onDelete(kind, x),
              itemBuilder: (_) => const [PopupMenuItem(value: 'edit', child: Text('ویرایش')), PopupMenuItem(value: 'delete', child: Text('حذف'))],
            ),
            if (x['local_only'] == true) const Icon(Icons.cloud_off_outlined, size: 16),
            const SizedBox(width: 6),
            Expanded(child: Text(x['title'] ?? '', textAlign: TextAlign.right, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 16))),
          ]),
          if (date.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 6), child: Text(date, textAlign: TextAlign.right)),
          if (created.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 3), child: Text('ثبت: $created', textAlign: TextAlign.right, style: Theme.of(context).textTheme.bodySmall)),
          if (shares.isNotEmpty) ...[
            const SizedBox(height: 8),
            const Text('اشتراک‌گذاری با:', textAlign: TextAlign.right, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
            const SizedBox(height: 4),
            Wrap(alignment: WrapAlignment.end, spacing: 6, runSpacing: 6, children: shares.map((person) {
              final permission = person['permission'] == 'editor' ? 'ویرایش' : 'مشاهده';
              return Chip(
                avatar: CircleAvatar(backgroundColor: memberColor(person['user_id'] ?? person['id']), radius: 7),
                label: Text('${person['name'] ?? person['email'] ?? 'کاربر'} · $permission', style: const TextStyle(fontSize: 11)),
                visualDensity: VisualDensity.compact,
              );
            }).toList()),
          ],
          const SizedBox(height: 12),
          Row(children: [
            Expanded(child: OutlinedButton(onPressed: () => onAct(kind, x['id'].toString(), 'continue'), child: const Text('ادامه دارد'))),
            const SizedBox(width: 8),
            Expanded(child: FilledButton(onPressed: () => onAct(kind, x['id'].toString(), 'complete'), child: const Text('انجام شد'))),
          ]),
        ]),
      ),
    );
  }
}

class WorkspaceList extends StatelessWidget {
  final List<Map<String, dynamic>> items;

  const WorkspaceList({
    super.key,
    required this.items,
  });

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: items.isEmpty
          ? const [Empty(text: 'محل کاری ثبت نشده')]
          : items.map((workspace) {
              final members = List<Map<String, dynamic>>.from(
                (workspace['members'] ?? []).map(
                  (e) => Map<String, dynamic>.from(e),
                ),
              );

              final docs = List<Map<String, dynamic>>.from(
                (workspace['documents'] ?? []).map(
                  (e) => Map<String, dynamic>.from(e),
                ),
              );
              const workspacePalette = <Color>[
                Color(0xff2563EB), Color(0xff16A34A), Color(0xffDC2626), Color(0xff9333EA),
                Color(0xffEA580C), Color(0xff0891B2), Color(0xffDB2777), Color(0xff4F46E5),
                Color(0xff65A30D), Color(0xffB45309), Color(0xff0F766E), Color(0xff7C3AED),
                Color(0xff0369A1), Color(0xffBE123C), Color(0xff15803D), Color(0xffA16207),
              ];
              final memberColors = <String, Color>{};
              for (var i = 0; i < members.length; i++) {
                final key = (members[i]['user_id'] ?? members[i]['id'] ?? i).toString();
                memberColors[key] = workspacePalette[i % workspacePalette.length];
              }

              return Card(
                elevation: 0,
                margin: const EdgeInsets.only(bottom: 12),
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        workspace['name'] ?? '',
                        textAlign: TextAlign.right,
                        style: const TextStyle(
                          fontWeight: FontWeight.w700,
                          fontSize: 17,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Wrap(
                        alignment: WrapAlignment.end,
                        spacing: 6,
                        runSpacing: 6,
                        children: members.map((member) {
                          return Chip(
                            avatar: CircleAvatar(
                              backgroundColor: memberColors[(member['user_id'] ?? member['id']).toString()] ?? memberColor(member['user_id'] ?? member['id']),
                              radius: 7,
                            ),
                            label: Text(
                              '${member['name']} · ${member['role']}',
                              style: const TextStyle(fontSize: 11),
                            ),
                          );
                        }).toList(),
                      ),
                      if (docs.isNotEmpty) ...[
                        const Divider(height: 22),
                        ...docs.map((doc) {
                          final lastEditor = doc['last_editor'] is Map
                              ? Map<String, dynamic>.from(
                                  doc['last_editor'],
                                )
                              : null;

                          return ListTile(
                            contentPadding: EdgeInsets.zero,
                            title: Text(
                              doc['title'] ?? '',
                              textAlign: TextAlign.right,
                            ),
                            subtitle: Text(
                              '${lastEditor == null ? 'بدون ویرایش' : 'آخرین ویرایش: ${lastEditor['name']}'}${persianDate(doc['updated_at']).isEmpty ? '' : '\n${persianDate(doc['updated_at'])}'}',
                              textAlign: TextAlign.right,
                            ),
                            trailing: lastEditor == null
                                ? null
                                : CircleAvatar(
                                    backgroundColor: memberColors[(lastEditor['id'] ?? lastEditor['user_id']).toString()] ?? memberColor(lastEditor['id'] ?? lastEditor['user_id']),
                                    radius: 8,
                                  ),
                          );
                        }),
                      ],
                    ],
                  ),
                ),
              );
            }).toList(),
    );
  }
}

class MessengerList extends StatelessWidget {
  final List<Map<String, dynamic>> items;

  const MessengerList({
    super.key,
    required this.items,
  });

  Future<void> call(
    BuildContext context,
    Map<String, dynamic> row,
  ) async {
    final token = await AuthStore.access();
    if (token == null) return;

    try {
      final service = VoiceCallService(Api.base, token);
      await service.prepare();
      final id = await service.start(row['id'].toString());

      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('تماس برقرار شد · $id')),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(ErrorHandler.message(e))),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: items.isEmpty
          ? const [Empty(text: 'گفتگویی وجود ندارد')]
          : items.map((x) {
              final other = x['other'] is Map
                  ? Map<String, dynamic>.from(x['other'])
                  : <String, dynamic>{};

              return Card(
                elevation: 0,
                child: ListTile(
                  leading: IconButton(
                    icon: const Icon(Icons.call_outlined),
                    onPressed: () => call(context, x),
                  ),
                  title: Text(
                    other['name'] ?? 'کاربر',
                    textAlign: TextAlign.right,
                  ),
                  subtitle: Text(
                    other['email'] ?? '',
                    textAlign: TextAlign.right,
                  ),
                  trailing: CircleAvatar(
                    backgroundColor: hexColor(other['color']),
                    radius: 10,
                  ),
                ),
              );
            }).toList(),
    );
  }
}

class Empty extends StatelessWidget {
  final String text;

  const Empty({
    super.key,
    required this.text,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 24),
      child: Text(
        text,
        textAlign: TextAlign.center,
        style: TextStyle(
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
      ),
    );
  }
}
