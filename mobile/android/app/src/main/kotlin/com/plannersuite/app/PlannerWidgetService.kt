package com.plannersuite.app

import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import android.widget.RemoteViewsService
import org.json.JSONArray

class PlannerWidgetService: RemoteViewsService(){override fun onGetViewFactory(intent:Intent)=Factory(applicationContext,intent.getStringExtra("tab")?:"calendar")}
class Factory(private val c:Context,private val tab:String):RemoteViewsService.RemoteViewsFactory{
    private var rows=listOf<String>()
    override fun onCreate(){load()}; override fun onDataSetChanged(){load()}; override fun onDestroy(){}
    private fun load(){
        val p=c.getSharedPreferences("planner_widget",Context.MODE_PRIVATE)
        if(tab=="calendar"){ rows=listOf("برای دیدن کارها یا رویدادها تب مربوط را انتخاب کنید"); return }
        val raw=p.getString(if(tab=="tasks") "tasks_json" else "events_json","[]")?:"[]"
        val a=JSONArray(raw); val out=mutableListOf<String>()
        for(i in 0 until a.length()){val o=a.optJSONObject(i)?:continue;if(o.optString("status")!="completed") out.add(o.optString("title","بدون عنوان"))}
        rows=if(out.isEmpty()) listOf(if(tab=="tasks") "کاری ثبت نشده است" else "رویدادی ثبت نشده است") else out
    }
    override fun getCount()=rows.size
    override fun getViewAt(position:Int):RemoteViews{val v=RemoteViews(c.packageName,R.layout.widget_row);v.setTextViewText(R.id.row_text,rows[position]);return v}
    override fun getLoadingView():RemoteViews?=null
    override fun getViewTypeCount()=1
    override fun getItemId(position:Int)=position.toLong()
    override fun hasStableIds()=true
}
