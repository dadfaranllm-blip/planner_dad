package com.plannersuite.app

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews

class PlannerWidgetProvider : AppWidgetProvider() {
    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) =
        ids.forEach { update(context, manager, it) }

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)
        when (intent.action) {
            ACTION_TAB_CALENDAR -> setTab(context, "calendar")
            ACTION_TAB_TASKS -> setTab(context, "tasks")
            ACTION_TAB_EVENTS -> setTab(context, "events")
            ACTION_REFRESH -> refreshAll(context)
        }
    }

    companion object {
        const val ACTION_REFRESH = "com.plannersuite.app.WIDGET_REFRESH"
        const val ACTION_TAB_CALENDAR = "com.plannersuite.app.WIDGET_CALENDAR"
        const val ACTION_TAB_TASKS = "com.plannersuite.app.WIDGET_TASKS"
        const val ACTION_TAB_EVENTS = "com.plannersuite.app.WIDGET_EVENTS"

        private fun pi(c: Context, action: String, req: Int) = PendingIntent.getBroadcast(
            c,
            req,
            Intent(c, PlannerWidgetProvider::class.java).setAction(action),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        fun setTab(c: Context, tab: String) {
            c.getSharedPreferences("planner_widget", Context.MODE_PRIVATE)
                .edit().putString("tab", tab).apply()
            refreshAll(c)
        }

        fun refreshAll(c: Context) {
            val m = AppWidgetManager.getInstance(c)
            m.getAppWidgetIds(ComponentName(c, PlannerWidgetProvider::class.java))
                .forEach { update(c, m, it) }
        }

        fun update(context: Context, manager: AppWidgetManager, id: Int) {
            val prefs = context.getSharedPreferences("planner_widget", Context.MODE_PRIVATE)
            val tab = prefs.getString("tab", "calendar") ?: "calendar"
            val rv = RemoteViews(context.packageName, R.layout.planner_widget)

            // Clock/date are native TextClock views. They update themselves every minute,
            // so the displayed time stays current even if the Flutter process is not running.
            rv.setTextViewText(
                R.id.widget_title,
                when (tab) {
                    "tasks" -> "همه کارها"
                    "events" -> "همه رویدادها"
                    else -> "امروز"
                }
            )
            rv.setOnClickPendingIntent(R.id.tab_calendar, pi(context, ACTION_TAB_CALENDAR, 1))
            rv.setOnClickPendingIntent(R.id.tab_tasks, pi(context, ACTION_TAB_TASKS, 2))
            rv.setOnClickPendingIntent(R.id.tab_events, pi(context, ACTION_TAB_EVENTS, 3))

            val service = Intent(context, PlannerWidgetService::class.java)
                .putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id)
                .putExtra("tab", tab)
            rv.setRemoteAdapter(R.id.widget_list, service)
            rv.setEmptyView(R.id.widget_list, R.id.widget_title)

            manager.updateAppWidget(id, rv)
            manager.notifyAppWidgetViewDataChanged(id, R.id.widget_list)
        }
    }
}
