package com.plannersuite.app

import android.appwidget.AppWidgetManager
import android.content.ComponentName
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity:FlutterActivity(){
    override fun configureFlutterEngine(flutterEngine:FlutterEngine){
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger,"planner/widget").setMethodCallHandler{call,result->
            if(call.method=="setWidgetData"){
                val p=getSharedPreferences("planner_widget",MODE_PRIVATE)
                p.edit().putString("tasks_json",call.argument<String>("tasks")?:"[]")
                    .putString("events_json",call.argument<String>("events")?:"[]")
                    .putString("persian_today",call.argument<String>("persianToday")?:"")
                    .apply()
                val m=AppWidgetManager.getInstance(this);val ids=m.getAppWidgetIds(ComponentName(this,PlannerWidgetProvider::class.java));ids.forEach{PlannerWidgetProvider.update(this,m,it)}
                result.success(true)
            } else result.notImplemented()
        }
    }
}
