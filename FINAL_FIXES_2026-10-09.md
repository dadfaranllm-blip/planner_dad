# Final fixes 2026-10-09

- All user-visible task/event/document dates use Jalali/Persian formatting.
- Date/time selection for task/event editing/creation uses a Persian/Jalali picker.
- New Task/Event action moved to AppBar; no bottom floating button can overlap Android system navigation.
- Workspace member colors are distinct within each workspace and the same color is reused for last-editor identity.
- Android widget is RTL, tabbed (calendar/tasks/events), scrollable, and displays Jalali dates for rows and the header.
- Home task/event headers are clickable and open full lists.
- Task/event lists are newest-created-first.
- Task and event edit/delete added with Local-First SQLite update + Outbox synchronization.
- Backend PATCH/DELETE endpoints added for tasks/events.
- Central Persian error handler added; raw exceptions/API payloads are not shown to users.
- Existing Local-First, persistent session, push, voice call, Google/Apple login, sharing and security modules retained.
