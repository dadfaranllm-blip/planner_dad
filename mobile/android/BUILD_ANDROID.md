# Android build

This directory is now a complete Android host for the Flutter app, including the native widget.

## Requirements
- Flutter SDK compatible with Dart >= 3.4
- Android SDK accepted by the installed Flutter version
- JDK 17
- Internet access on the first Gradle build (the included `gradlew` bootstrapper downloads Gradle 8.10.2)

## Debug APK
From `mobile/`:

```bash
flutter pub get
flutter build apk --debug --dart-define=API_BASE=https://YOUR-HOST/api
```

The debug Android manifest permits cleartext traffic so emulator development can also use `http://10.0.2.2:8000`.
Release builds do not permit cleartext HTTP.

## Release signing
1. Create your own keystore (never commit it).
2. Copy `android/key.properties.example` to `android/key.properties` and set real values.
3. Build with `flutter build apk --release ...` or `flutter build appbundle --release ...`.

If `key.properties` is absent, release falls back to the debug key for local build validation only. Do not distribute that build.

## Firebase/FCM without google-services.json
This project intentionally does not require `google-services.json`; Firebase Android values are supplied with Dart defines so secrets/config do not need to be committed:

```bash
flutter build apk --release \
  --dart-define=API_BASE=https://YOUR-HOST/api \
  --dart-define=FIREBASE_ANDROID_API_KEY=... \
  --dart-define=FIREBASE_ANDROID_APP_ID=... \
  --dart-define=FIREBASE_MESSAGING_SENDER_ID=... \
  --dart-define=FIREBASE_PROJECT_ID=...
```

If these Firebase values are omitted, the app still builds and runs; push registration is disabled until configured.

## Sensitive Android permissions
The manifest contains READ_SMS / RECEIVE_SMS because SMS automation is an explicit Planner Suite feature. Public Google Play distribution is subject to Google Play's restricted SMS permission policy. If the Play release does not qualify, remove these permissions for that flavor/build.
