package com.plannersuite.app

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.widget.RemoteViews
import java.util.Calendar

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
            c, req, Intent(c, PlannerWidgetProvider::class.java).setAction(action),
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
            val today = prefs.getString("persian_today", "").orEmpty().ifBlank { PersianDate.today() }
            rv.setTextViewText(R.id.date, today)
            rv.setTextViewText(R.id.widget_title, when (tab) {
                "tasks" -> "کارها"
                "events" -> "رویدادها"
                else -> "تقویم امروز"
            })
            rv.setTextColor(R.id.tab_calendar, if (tab == "calendar") Color.rgb(20,100,65) else Color.DKGRAY)
            rv.setTextColor(R.id.tab_tasks, if (tab == "tasks") Color.rgb(20,100,65) else Color.DKGRAY)
            rv.setTextColor(R.id.tab_events, if (tab == "events") Color.rgb(20,100,65) else Color.DKGRAY)
            rv.setOnClickPendingIntent(R.id.tab_calendar, pi(context, ACTION_TAB_CALENDAR, 1))
            rv.setOnClickPendingIntent(R.id.tab_tasks, pi(context, ACTION_TAB_TASKS, 2))
            rv.setOnClickPendingIntent(R.id.tab_events, pi(context, ACTION_TAB_EVENTS, 3))
            val service = Intent(context, PlannerWidgetService::class.java)
                .putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id)
                .putExtra("tab", tab)
                .setData(android.net.Uri.parse("planner://widget/$id/$tab"))
            rv.setRemoteAdapter(R.id.widget_list, service)
            rv.setEmptyView(R.id.widget_list, R.id.widget_title)
            manager.updateAppWidget(id, rv)
            manager.notifyAppWidgetViewDataChanged(id, R.id.widget_list)
        }
    }
}

object PersianDate {
    private val months = arrayOf("فروردین","اردیبهشت","خرداد","تیر","مرداد","شهریور","مهر","آبان","آذر","دی","بهمن","اسفند")
    private val weekdays = arrayOf("یکشنبه","دوشنبه","سه‌شنبه","چهارشنبه","پنجشنبه","جمعه","شنبه")
    private val faDigits = "۰۱۲۳۴۵۶۷۸۹"
    private fun fa(n: Int) = n.toString().map { if (it.isDigit()) faDigits[it-'0'] else it }.joinToString("")

    fun today(): String {
        val c = Calendar.getInstance()
        val j = gregorianToJalali(c.get(Calendar.YEAR), c.get(Calendar.MONTH)+1, c.get(Calendar.DAY_OF_MONTH))
        return "${weekdays[c.get(Calendar.DAY_OF_WEEK)-1]}، ${fa(j[2])} ${months[j[1]-1]} ${fa(j[0])}"
    }

    fun fromIso(raw: String?): String {
        if (raw.isNullOrBlank()) return ""
        val m = Regex("^(\\d{4})-(\\d{2})-(\\d{2})(?:T(\\d{2}):(\\d{2}))?").find(raw) ?: return ""
        val y=m.groupValues[1].toInt(); val mo=m.groupValues[2].toInt(); val d=m.groupValues[3].toInt()
        val j=gregorianToJalali(y,mo,d)
        val time = if (m.groupValues[4].isNotBlank()) "، ${fa(m.groupValues[4].toInt())}:${fa(m.groupValues[5].toInt())}" else ""
        return "${fa(j[2])} ${months[j[1]-1]} ${fa(j[0])}$time"
    }

    private fun gregorianToJalali(gy0:Int, gm:Int, gd:Int): IntArray {
        var gy=gy0; val gdm=intArrayOf(0,31,59,90,120,151,181,212,243,273,304,334)
        val jy:Int
        if (gy > 1600) { jy=979; gy-=1600 } else { jy=0; gy-=621 }
        val gy2 = if (gm>2) gy+1 else gy
        var days=365*gy+(gy2+3)/4-(gy2+99)/100+(gy2+399)/400-80+gd+gdm[gm-1]
        var jyy=jy+33*(days/12053); days%=12053
        jyy+=4*(days/1461); days%=1461
        if(days>365){jyy+=(days-1)/365; days=(days-1)%365}
        val jm:Int; val jd:Int
        if(days<186){jm=1+days/31; jd=1+days%31}else{jm=7+(days-186)/30; jd=1+(days-186)%30}
        return intArrayOf(jyy,jm,jd)
    }
}
