# Planner Suite — merged changes on original Android-complete base

This release keeps the original `planner-suite-android-complete-github-fixed` project as the base and merges the requested changes into it.

## Mobile / Android
- Local-first startup: cached SQLite data is shown before any server synchronization.
- Offline outbox is preserved and synchronized after UI startup.
- Persistent device sessions: access token + rotating refresh token in Android encrypted secure storage.
- Task/Event widget lists remain scrollable using RemoteViewsService/ListView.
- Large Persian-locale native clock is fixed at the top of every widget tab.
- Add-task bottom sheet/FAB respects Android safe areas/navigation inset.
- Google/Gmail and Apple buttons are connected to native identity-token login endpoints.
- Push registration and foreground/background notification hooks remain enabled.
- Voice-call entry is exposed from Messenger and uses the existing WebRTC call service.
- Workspace is exposed as a mobile tab with stable member colors and last-editor color/name.
- Task/Event cards display exactly who the item is shared with and Viewer/Editor permission.

## Backend
- Task/Event list responses include `shared_with` user/name/color/permission metadata.
- Workspace summary returns members, stable colors, documents and last-editor identity/color.
- Conversation list returns the other participant's identity/color for Messenger UI.
- Mobile Google and Apple identity-token login endpoints issue the same Planner device session used by password login.
- New password hashes use Argon2id; legacy PBKDF2 hashes remain readable and are upgraded after successful login.
- CORS is configured by `CORS_ORIGINS` instead of wildcard production access.
- Existing push, reminders, workspace notifications, voice calls, sharing, Google Calendar sync and central PostgreSQL architecture are retained.

## GitHub
- Existing `.github/workflows/android-build.yml` is retained on the original project.
- It triggers on push, pull request, or manual dispatch and builds `mobile` as the Android APK project.

## Secrets intentionally not included
Production signing keys, Firebase credentials, Google OAuth client secrets, Apple private keys and TURN credentials must be configured as deployment secrets and must not be committed to Git.
