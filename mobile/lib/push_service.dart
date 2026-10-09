import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'api.dart';

@pragma('vm:entry-point')
Future<void> plannerFirebaseBackgroundHandler(RemoteMessage message) async {
  await PushService.ensureFirebase();
}

class PushService {
  static const _apiKey = String.fromEnvironment('FIREBASE_ANDROID_API_KEY');
  static const _appId = String.fromEnvironment('FIREBASE_ANDROID_APP_ID');
  static const _senderId = String.fromEnvironment('FIREBASE_MESSAGING_SENDER_ID');
  static const _projectId = String.fromEnvironment('FIREBASE_PROJECT_ID');
  static final FlutterLocalNotificationsPlugin _local = FlutterLocalNotificationsPlugin();
  static bool _ready = false;
  static bool _localReady = false;

  static void installBackgroundHandler() {
    FirebaseMessaging.onBackgroundMessage(plannerFirebaseBackgroundHandler);
  }

  static Future<bool> ensureFirebase() async {
    if (Firebase.apps.isNotEmpty) return true;
    if (_apiKey.isEmpty || _appId.isEmpty || _senderId.isEmpty || _projectId.isEmpty) {
      return false;
    }
    await Firebase.initializeApp(
      options: const FirebaseOptions(
        apiKey: _apiKey,
        appId: _appId,
        messagingSenderId: _senderId,
        projectId: _projectId,
      ),
    );
    return true;
  }

  static Future<void> _initLocalNotifications() async {
    if (_localReady) return;
    const init = InitializationSettings(
      android: AndroidInitializationSettings('@drawable/ic_notification'),
    );
    await _local.initialize(init);
    const channel = AndroidNotificationChannel(
      'planner_high',
      'Planner alerts',
      description: 'Messages, workspace updates and reminders',
      importance: Importance.high,
    );
    await _local
        .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(channel);
    _localReady = true;
  }

  static Future<void> initialize() async {
    if (_ready) return;
    if (!await ensureFirebase()) return;
    await _initLocalNotifications();

    final messaging = FirebaseMessaging.instance;
    await messaging.requestPermission(alert: true, badge: true, sound: true);

    final token = await messaging.getToken();
    if (token != null) await registerToken(token);
    messaging.onTokenRefresh.listen((token) async {
      try { await registerToken(token); } catch (_) {}
    });

    FirebaseMessaging.onMessage.listen((m) async {
      final n = m.notification;
      final title = n?.title ?? m.data['title']?.toString() ?? 'برنامه‌ریز';
      final body = n?.body ?? m.data['body']?.toString() ?? '';
      await _local.show(
        m.hashCode,
        title,
        body,
        const NotificationDetails(
          android: AndroidNotificationDetails(
            'planner_high',
            'Planner alerts',
            channelDescription: 'Messages, workspace updates and reminders',
            importance: Importance.high,
            priority: Priority.high,
            icon: '@drawable/ic_notification',
          ),
        ),
      );
    });
    _ready = true;
  }

  static Future<void> registerToken(String token) async {
    await Api.call('/devices/push-token', method: 'POST', body: {
      'token': token,
      'platform': 'android',
    });
  }
}
