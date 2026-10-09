package com.plannersuite.app

import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import android.widget.RemoteViewsService
import org.json.JSONArray
import org.json.JSONObject

class PlannerWidgetService : RemoteViewsService() {
    override fun onGetViewFactory(intent: Intent) = Factory(applicationContext, intent.getStringExtra("tab") ?: "calendar")
}

class Factory(private val c: Context, private val tab: String) : RemoteViewsService.RemoteViewsFactory {
    private data class Row(val title:String, val date:String, val created:String)
    private var rows = listOf<Row>()
    override fun onCreate() { load() }
    override fun onDataSetChanged() { load() }
    override fun onDestroy() {}

    private fun loadArray(raw:String, dateKey:String): List<Row> {
        val a=try { JSONArray(raw) } catch (_:Exception) { JSONArray() }
        val out=mutableListOf<Row>()
        for(i in 0 until a.length()) {
            val o=a.optJSONObject(i) ?: continue
            if(o.optString("status") == "completed") continue
            out.add(Row(o.optString("title","بدون عنوان"), PersianDate.fromIso(o.optString(dateKey)), o.optString("created_at", o.optString(dateKey))))
        }
        return out.sortedByDescending { it.created }
    }

    private fun load() {
        val p=c.getSharedPreferences("planner_widget",Context.MODE_PRIVATE)
        val tasks=loadArray(p.getString("tasks_json","[]") ?: "[]", "due_at")
        val events=loadArray(p.getString("events_json","[]") ?: "[]", "starts_at")
        rows = when(tab) {
            "tasks" -> tasks
            "events" -> events
            else -> (tasks + events).sortedByDescending { it.created }
        }
        if(rows.isEmpty()) rows=listOf(Row(if(tab=="tasks") "کاری ثبت نشده است" else if(tab=="events") "رویدادی ثبت نشده است" else "برای امروز موردی ثبت نشده است", "", ""))
    }

    override fun getCount() = rows.size
    override fun getViewAt(position:Int): RemoteViews {
        val row=rows[position]
        val v=RemoteViews(c.packageName,R.layout.widget_row)
        v.setTextViewText(R.id.row_text, if(row.date.isBlank()) row.title else "${row.title}\n${row.date}")
        return v
    }
    override fun getLoadingView(): RemoteViews? = null
    override fun getViewTypeCount() = 1
    override fun getItemId(position:Int) = position.toLong()
    override fun hasStableIds() = true
}
