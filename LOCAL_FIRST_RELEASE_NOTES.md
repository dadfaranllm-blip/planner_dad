# Local-First Mobile Release Notes

## Changes
1. App startup reads tasks/events from local SQLite first; server sync starts only after the UI is open.
2. Offline mutations are stored in an outbox and retried when connectivity/server returns.
3. Login is device-persistent using rotating refresh sessions (default 180 days) and Flutter Secure Storage. Explicit logout/revoke ends the session.
4. Android widget: 54sp Persian-digit clock fixed above all tabs; Tasks and Events use scrollable collection lists.
5. Add Task UI and bottom NavigationBar are wrapped in safe areas so controls do not sit under Android system navigation.

## Verification
Backend pytest: 6 passed. Flutter/Android build not executed because SDK/toolchain is unavailable in this environment.
