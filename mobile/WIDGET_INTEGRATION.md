# Phase 6 widget integration
Android native AppWidget source is included under `android/app/src/main`.
Three product modes are defined: calendar/clock, tasks, events. Widget data is cached locally by the mobile app so the widget can render without opening the UI.

## Required Android manifest receiver
Add inside `<application>` when generating/merging the Flutter Android host:
```
<receiver android:name="com.plannersuite.app.PlannerWidgetProvider" android:exported="false">
  <intent-filter><action android:name="android.appwidget.action.APPWIDGET_UPDATE"/></intent-filter>
  <meta-data android:name="android.appwidget.provider" android:resource="@xml/planner_widget_info"/>
</receiver>
```

## iOS
WidgetKit target requires Xcode signing and an App Group. The data contract mirrors Android: calendar_text, tasks_text, events_text and active tab. Binary/signing verification must be done on macOS/Xcode.
