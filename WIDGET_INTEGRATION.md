# Planner Android Widgets 1.3.0

The build generates four native AppWidget providers:
- `PlannerWidgetProvider` — overview
- `PlannerClockWidgetProvider` — large live clock + Persian date
- `PlannerTasksWidgetProvider` — upcoming tasks
- `PlannerAgendaWidgetProvider` — upcoming events

All widgets are exposed in Android's widget picker with distinct labels and can also be pinned from **Settings → Home screen widgets**.

The clock uses Android `TextClock`, so the displayed time updates live without waiting for the 30-minute AppWidget refresh interval. Data widgets refresh cached/API data and use the securely stored session token from Android Keystore.
