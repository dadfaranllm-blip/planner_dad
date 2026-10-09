# Planner Suite — Integrated Source Release

Single-project release with one central PostgreSQL source of truth. Web, Mobile and Windows clients must access data only through the Backend API; device SQLite/local storage is cache-only.

## Integrated capabilities
- Authentication, calendars, tasks/events, Done/Continue, reminders and activity log.
- Google Calendar connection foundation and idempotent device-calendar ingestion.
- Android-oriented mobile/widget source foundation from the previous release.
- SMS privacy-first rules/suggestions: local/rule processing first; AI provider intentionally remains opt-in.
- Task/Event/Calendar sharing records and the existing 1:1 messenger API.
- Collaborative workspace documents with member colors, comments, immutable versions and revision-conflict protection.
- Periodic sync preference (default 6 hours / 4 times daily), plus sync-on-open/change flags.
- Persistent PostgreSQL Docker volume, backup, restore and non-destructive schema migration runner.

## Install / upgrade
`./install.sh` starts the stack. Existing installations should use `./upgrade.sh`; it takes a PostgreSQL backup first and preserves the `pgdata` volume. `./backup.sh` and `./restore.sh <backup.sql.gz>` are provided.

## Verification in this package
`python -m pytest -q backend/test_api.py backend/test_final.py` passes 4/4 in the build environment.

## Explicit production gaps
This is an integrated **source** release, not a claim that every native binary is production-certified. Real Google OAuth needs project credentials. Android/iOS/Windows binaries require their platform SDK/toolchains and signing credentials. Workspace editing currently uses revision-safe optimistic concurrency/versioning; a true CRDT/WebSocket co-editing engine is not yet implemented. SMS inbox access depends on Android permissions/store policy. External AI SMS parsing is intentionally not enabled without an explicit provider/consent configuration.

## Integrated UX/Realtime update

This release keeps one central PostgreSQL-backed Planner identity and adds the requested collaboration/notification/voice improvements:

- Workspace member colors are stable per workspace and are returned with document versions and comments so the UI can show exactly who changed what.
- Task/Event sharing is inspectable per item through `/shares/entity/{type}/{id}` with user name, email, color and viewer/editor permission. Shares can be revoked individually.
- Unified notification center queues message, workspace/comment/share and due-reminder notifications. Mobile devices register FCM tokens with `/devices/push-token`; Firebase HTTP v1 dispatch is available through the protected internal push worker endpoint.
- Voice calls are integrated into 1-to-1 conversations using WebRTC signaling (`offer`, `answer`, `ice`) and support a production TURN server through environment settings.
- Android widget clock is always visible in Calendar/Tasks/Events modes and enlarged to 52sp for glanceability.
- Google Sign-In and Sign in with Apple map to the same central Planner user through external identities; provider credentials remain server-side.

### Production services still requiring deployment credentials

- Firebase service-account JSON + project id for actual remote push delivery.
- TURN credentials for reliable WebRTC across carrier/NAT networks.
- Google OAuth client credentials and exact HTTPS redirect URIs.
- Apple Services ID / Team ID / Key ID / EC private key and HTTPS callback.

Backend integration tests: `cd backend && pytest -q`.


## Local-first mobile update (0.7.0)
- Mobile opens from its own SQLite cache and does not block startup on the server.
- A local outbox queues task mutations and syncs after the UI is available.
- Device sessions use rotating refresh tokens; mobile credentials are stored in secure storage.
- Android widget has a persistent Persian-digit clock at the top of every tab.
- Tasks and events use a RemoteViews ListView so the full list can scroll inside its tab.
- Bottom navigation and add-task sheet/FAB use safe-area insets to stay above system navigation.

Production note: merge `mobile/android/ANDROID_MANIFEST_REQUIRED.xml` declarations into the generated Flutter Android manifest before APK build.
