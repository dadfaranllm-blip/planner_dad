# Planner Suite - Integrated Collaboration Update

- Central database architecture preserved.
- Stable workspace member colors and author-colored versions/comments.
- Per-item share visibility with named recipients and permission level.
- Push notification queue + FCM HTTP v1 device registration/dispatcher.
- Message, workspace, comment, share and reminder notifications.
- 1-to-1 voice call lifecycle and WebRTC signaling; TURN configurable.
- Large always-visible Android widget clock (52sp) in all modes.
- Google and Apple sign-in identities use the same Planner user account.
- Protected internal scheduler/push endpoints with `SCHEDULER_KEY`.
- Backend test suite: 5 passing tests in this environment.

Mobile/Android/iOS binary builds were not executed because Flutter/Android/iOS SDKs are not installed in this runtime. Provider-dependent flows require real credentials for end-to-end verification.

## Android host completion
- Added complete Flutter Android host under `mobile/android`.
- Added Gradle settings/build files and cross-platform Gradle bootstrap scripts.
- Added production AndroidManifest with widget, notifications, calendar, microphone and SMS feature permissions.
- Added debug cleartext override only for local emulator development.
- Added release signing template without committing private keys.
- Added Android resources/themes/launcher icon/notification icon.
- Converted widget clock/date to native Persian-locale TextClock so time remains live without launching Flutter.
- Kept Tasks/Events widget tabs backed by a scrollable RemoteViews ListView.
- Wired Firebase Messaging initialization into app startup; Firebase values are provided through Dart defines so google-services.json is not required.
- Added foreground local notification display and FCM token registration through the authenticated API.
