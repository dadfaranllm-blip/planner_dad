import 'dart:async';

import 'package:flutter/material.dart';

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
          () => err =
              'ورود انجام نشد: ${e.toString().replaceFirst('Exception: ', '')}',
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

typedef ActionFn = Future<void> Function(
  String kind,
  String id,
  String action,
);

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

  void addTask() {
    final ctl = TextEditingController();

    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (sheetContext) {
        final media = MediaQuery.of(sheetContext);

        return SafeArea(
          top: false,
          child: Padding(
            padding: EdgeInsets.fromLTRB(
              20,
              20,
              20,
              24 + media.viewInsets.bottom + media.viewPadding.bottom,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: ctl,
                  autofocus: true,
                  textDirection: TextDirection.rtl,
                  decoration: const InputDecoration(
                    labelText: 'چه کاری باید انجام شود؟',
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: () async {
                      final title = ctl.text.trim();
                      if (title.isEmpty) return;

                      final id =
                          'local-${DateTime.now().microsecondsSinceEpoch}';

                      await LocalStore.upsert(
                        'task',
                        {
                          'id': id,
                          'title': title,
                          'status': 'open',
                          'created_at': DateTime.now().toIso8601String(),
                          'local_only': true,
                          'shared_with': <dynamic>[],
                        },
                      );

                      await LocalStore.enqueue(
                        'POST',
                        '/tasks',
                        {'title': title},
                      );

                      if (sheetContext.mounted) {
                        Navigator.pop(sheetContext);
                      }

                      await _reloadLocal();
                      unawaited(_sync());
                    },
                    child: const Text('ثبت کار'),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final pages = <Widget>[
      Today(tasks: tasks, events: events, onAct: act),
      Items(kind: 'task', items: tasks, onAct: act),
      Items(kind: 'event', items: events, onAct: act),
      WorkspaceList(items: workspaces),
      MessengerList(items: conversations),
    ];

    const titles = ['امروز', 'کارها', 'رویدادها', 'محل کار', 'پیام‌ها'];

    return Scaffold(
      appBar: AppBar(
        title: Text(titles[tab]),
        actions: [
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
      floatingActionButton: tab <= 2
          ? SafeArea(
              minimum: EdgeInsets.only(
                bottom: MediaQuery.of(context).viewPadding.bottom + 12,
              ),
              child: FloatingActionButton(
                onPressed: addTask,
                child: const Icon(Icons.add),
              ),
            )
          : null,
      floatingActionButtonLocation: FloatingActionButtonLocation.endFloat,
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

  const Today({
    super.key,
    required this.tasks,
    required this.events,
    required this.onAct,
  });

  @override
  Widget build(BuildContext context) {
    final open =
        tasks.where((x) => x['status'] != 'completed').toList();
    final ev =
        events.where((x) => x['status'] != 'completed').toList();

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: [
        const Text(
          'کارهای نزدیک',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 8),
        if (open.isEmpty)
          const Empty(text: 'کاری برای نمایش نیست'),
        ...open.map(
          (x) => ItemCard(x: x, kind: 'task', onAct: onAct),
        ),
        const SizedBox(height: 18),
        const Text(
          'رویدادها',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 8),
        if (ev.isEmpty)
          const Empty(text: 'رویدادی ثبت نشده'),
        ...ev.map(
          (x) => ItemCard(x: x, kind: 'event', onAct: onAct),
        ),
      ],
    );
  }
}

class Items extends StatelessWidget {
  final String kind;
  final List<Map<String, dynamic>> items;
  final ActionFn onAct;

  const Items({
    super.key,
    required this.kind,
    required this.items,
    required this.onAct,
  });

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: items.isEmpty
          ? const [Empty(text: 'هنوز چیزی ثبت نشده')]
          : items
              .map((x) => ItemCard(x: x, kind: kind, onAct: onAct))
              .toList(),
    );
  }
}

class ItemCard extends StatelessWidget {
  final Map<String, dynamic> x;
  final String kind;
  final ActionFn onAct;

  const ItemCard({
    super.key,
    required this.x,
    required this.kind,
    required this.onAct,
  });

  @override
  Widget build(BuildContext context) {
    final shares = List<Map<String, dynamic>>.from(
      (x['shared_with'] ?? []).map(
        (e) => Map<String, dynamic>.from(e),
      ),
    );

    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                if (x['local_only'] == true)
                  const Padding(
                    padding: EdgeInsets.only(right: 8),
                    child: Icon(Icons.cloud_off_outlined, size: 16),
                  ),
                Expanded(
                  child: Text(
                    x['title'] ?? '',
                    textAlign: TextAlign.right,
                    style: const TextStyle(
                      fontWeight: FontWeight.w600,
                      fontSize: 16,
                    ),
                  ),
                ),
              ],
            ),
            if (shares.isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(
                alignment: WrapAlignment.end,
                spacing: 6,
                runSpacing: 6,
                children: shares.map((s) {
                  final permission =
                      s['permission'] == 'editor' ? 'ویرایش' : 'مشاهده';
                  return Chip(
                    avatar: CircleAvatar(
                      backgroundColor: hexColor(s['color']),
                      radius: 7,
                    ),
                    label: Text(
                      '${s['name']} · $permission',
                      style: const TextStyle(fontSize: 11),
                    ),
                    visualDensity: VisualDensity.compact,
                  );
                }).toList(),
              ),
            ],
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => onAct(
                      kind,
                      x['id'].toString(),
                      'continue',
                    ),
                    child: const Text('ادامه دارد'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: FilledButton(
                    onPressed: () => onAct(
                      kind,
                      x['id'].toString(),
                      'complete',
                    ),
                    child: const Text('انجام شد'),
                  ),
                ),
              ],
            ),
          ],
        ),
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
                              backgroundColor:
                                  hexColor(member['color']),
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
                              lastEditor == null
                                  ? 'بدون ویرایش'
                                  : 'آخرین ویرایش: ${lastEditor['name']}',
                              textAlign: TextAlign.right,
                            ),
                            trailing: lastEditor == null
                                ? null
                                : CircleAvatar(
                                    backgroundColor:
                                        hexColor(lastEditor['color']),
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
          SnackBar(content: Text('شروع تماس ممکن نشد: $e')),
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
