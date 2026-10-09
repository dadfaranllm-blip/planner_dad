# Planner Suite Mobile — Phase 5
Native Flutter client (not WebView).

## Run
flutter pub get
flutter run --dart-define=API_BASE=https://your-domain.example/api

Current Phase 5 UI: login, Today, Tasks, Events, quick task creation, Complete, Continue (server default next day 08:00), pull-to-refresh.
Native calendar/local notification dependencies are pinned for the device integration layer; platform permission wiring and production signing require Android/iOS SDK build environments.
