from pathlib import Path
import re
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else 'android').resolve()
app = root / 'app'
manifest = app / 'src/main/AndroidManifest.xml'
if not manifest.exists():
    raise SystemExit(f'Manifest not found: {manifest}')

main_files = list((app / 'src/main/kotlin').rglob('MainActivity.kt'))
if not main_files:
    raise SystemExit('MainActivity.kt not found')
main = main_files[0]
text = main.read_text(encoding='utf-8')
m = re.search(r'^\s*package\s+([\w.]+)', text, re.M)
if not m:
    raise SystemExit('Package not found')
pkg = m.group(1)
kotlin_dir = main.parent

(kotlin_dir / 'SecureTokenStore.kt').write_text(f'''package {pkg}

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

object SecureTokenStore {{
    private const val ALIAS = "planner_session_key_v2"
    private const val PREFS = "planner_secure_session"
    private const val ACCESS = "access_cipher"
    private const val ACCESS_IV = "access_iv"
    private const val REFRESH = "refresh_cipher"
    private const val REFRESH_IV = "refresh_iv"

    private fun key(): SecretKey {{
        val ks = KeyStore.getInstance("AndroidKeyStore").apply {{ load(null) }}
        (ks.getKey(ALIAS, null) as? SecretKey)?.let {{ return it }}
        val gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        gen.init(KeyGenParameterSpec.Builder(
            ALIAS,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
        ).setBlockModes(KeyProperties.BLOCK_MODE_GCM)
         .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
         .setRandomizedEncryptionRequired(true)
         .build())
        return gen.generateKey()
    }}

    private fun encrypt(context: Context, value: String, cipherKey: String, ivKey: String) {{
        if (value.isBlank()) {{
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().remove(cipherKey).remove(ivKey).apply()
            return
        }}
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val encrypted = cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(cipherKey, Base64.encodeToString(encrypted, Base64.NO_WRAP))
            .putString(ivKey, Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .apply()
    }}

    private fun decrypt(context: Context, cipherKey: String, ivKey: String): String? = try {{
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val enc = prefs.getString(cipherKey, null) ?: return null
        val iv = prefs.getString(ivKey, null) ?: return null
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, Base64.decode(iv, Base64.NO_WRAP)))
        String(cipher.doFinal(Base64.decode(enc, Base64.NO_WRAP)), Charsets.UTF_8)
    }} catch (_: Exception) {{ null }}

    fun saveAccess(context: Context, token: String) = encrypt(context, token, ACCESS, ACCESS_IV)
    fun saveTokens(context: Context, access: String, refresh: String?) {{
        saveAccess(context, access)
        if (!refresh.isNullOrBlank()) encrypt(context, refresh, REFRESH, REFRESH_IV)
    }}
    fun read(context: Context): String? = decrypt(context, ACCESS, ACCESS_IV)
    fun readRefresh(context: Context): String? = decrypt(context, REFRESH, REFRESH_IV)
    fun clear(context: Context) {{
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().clear().apply()
    }}
}}
''', encoding='utf-8')

main.write_text(f'''package {pkg}

import android.Manifest
import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {{
    override fun onCreate(savedInstanceState: Bundle?) {{
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {{
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 417)
        }}
    }}

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {{
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "planner/security").setMethodCallHandler {{ call, result ->
            when (call.method) {{
                "setToken" -> {{
                    val token = call.argument<String>("token") ?: ""
                    if (token.isBlank()) result.error("TOKEN_EMPTY", "Token is empty", null)
                    else {{ SecureTokenStore.saveAccess(this, token); result.success(true) }}
                }}
                "setTokens" -> {{
                    val access = call.argument<String>("accessToken") ?: ""
                    val refresh = call.argument<String>("refreshToken")
                    if (access.isBlank()) result.error("TOKEN_EMPTY", "Access token is empty", null)
                    else {{ SecureTokenStore.saveTokens(this, access, refresh); result.success(true) }}
                }}
                "getToken" -> result.success(SecureTokenStore.read(this))
                "getRefreshToken" -> result.success(SecureTokenStore.readRefresh(this))
                "clearToken" -> {{ SecureTokenStore.clear(this); result.success(true) }}
                else -> result.notImplemented()
            }}
        }}

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "planner/notifications").setMethodCallHandler {{ call, result ->
            when (call.method) {{
                "syncReminders" -> {{
                    val items = call.argument<List<Map<String, Any?>>>("items") ?: emptyList()
                    PlannerReminderScheduler.sync(this, items)
                    result.success(true)
                }}
                "clearReminders" -> {{
                    PlannerReminderScheduler.clear(this)
                    result.success(true)
                }}
                else -> result.notImplemented()
            }}
        }}

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "planner/widget").setMethodCallHandler {{ call, result ->
            when (call.method) {{
                "updateWidget" -> {{
                    getSharedPreferences("planner_widget", Context.MODE_PRIVATE).edit()
                        .putInt("tasks", call.argument<Int>("tasks") ?: 0)
                        .putInt("events", call.argument<Int>("events") ?: 0)
                        .putString("date", call.argument<String>("date") ?: "")
                        .putString("task_items_json", call.argument<String>("taskItemsJson") ?: "[]")
                        .putString("event_items_json", call.argument<String>("eventItemsJson") ?: "[]")
                        .apply()
                    PlannerWidgetData.updateAll(this)
                    result.success(true)
                }}
                "pinWidget" -> {{
                    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {{ result.success(false); return@setMethodCallHandler }}
                    val manager = AppWidgetManager.getInstance(this)
                    if (!manager.isRequestPinAppWidgetSupported) {{ result.success(false); return@setMethodCallHandler }}
                    val type = call.argument<String>("type") ?: "overview"
                    val cls = when (type) {{
                        "clock" -> PlannerClockWidgetProvider::class.java
                        "tasks" -> PlannerTasksWidgetProvider::class.java
                        "agenda" -> PlannerAgendaWidgetProvider::class.java
                        else -> PlannerWidgetProvider::class.java
                    }}
                    result.success(manager.requestPinAppWidget(ComponentName(this, cls), null, null))
                }}
                else -> result.notImplemented()
            }}
        }}
    }}
}}
''', encoding='utf-8')

(kotlin_dir / 'PlannerReminderReceiver.kt').write_text(f'''package {pkg}

import android.app.AlarmManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.app.Notification
import org.json.JSONArray
import org.json.JSONObject

private const val REMINDER_PREFS = "planner_local_reminders"
private const val REMINDER_DATA = "items_json"
private const val REMINDER_CHANNEL = "planner_due_reminders"

object PlannerReminderScheduler {{
    private fun code(id: String): Int = id.hashCode() and 0x7fffffff

    private fun alarmIntent(context: Context, item: JSONObject): PendingIntent {{
        val id = item.optString("id")
        val intent = Intent(context, PlannerReminderReceiver::class.java).apply {{
            action = "{pkg}.REMINDER.$id"
            putExtra("id", id)
            putExtra("title", item.optString("title", "Planner"))
            putExtra("body", item.optString("body", "یادآوری Planner"))
        }}
        return PendingIntent.getBroadcast(context, code(id), intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }}

    private fun scheduleOne(context: Context, item: JSONObject) {{
        val at = item.optLong("triggerAt", 0L)
        if (at <= System.currentTimeMillis()) return
        val manager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val pi = alarmIntent(context, item)
        try {{
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && manager.canScheduleExactAlarms()) {{
                manager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi)
            }} else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {{
                manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi)
            }} else {{
                manager.set(AlarmManager.RTC_WAKEUP, at, pi)
            }}
        }} catch (_: Exception) {{
            manager.set(AlarmManager.RTC_WAKEUP, at, pi)
        }}
    }}

    fun sync(context: Context, items: List<Map<String, Any?>>) {{
        clear(context)
        val arr = JSONArray()
        items.forEach {{ raw ->
            val o = JSONObject()
            raw.forEach {{ (k, v) -> o.put(k, v) }}
            arr.put(o)
            scheduleOne(context, o)
        }}
        context.getSharedPreferences(REMINDER_PREFS, Context.MODE_PRIVATE).edit().putString(REMINDER_DATA, arr.toString()).apply()
    }}

    fun clear(context: Context) {{
        val prefs = context.getSharedPreferences(REMINDER_PREFS, Context.MODE_PRIVATE)
        val arr = try {{ JSONArray(prefs.getString(REMINDER_DATA, "[]")) }} catch (_: Exception) {{ JSONArray() }}
        val manager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        for (i in 0 until arr.length()) {{
            val o = arr.optJSONObject(i) ?: continue
            manager.cancel(alarmIntent(context, o))
        }}
        prefs.edit().remove(REMINDER_DATA).apply()
    }}

    fun restore(context: Context) {{
        val raw = context.getSharedPreferences(REMINDER_PREFS, Context.MODE_PRIVATE).getString(REMINDER_DATA, "[]") ?: "[]"
        val arr = try {{ JSONArray(raw) }} catch (_: Exception) {{ JSONArray() }}
        for (i in 0 until arr.length()) arr.optJSONObject(i)?.let {{ scheduleOne(context, it) }}
    }}
}}

class PlannerReminderReceiver : BroadcastReceiver() {{
    override fun onReceive(context: Context, intent: Intent) {{
        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {{
            nm.createNotificationChannel(NotificationChannel(REMINDER_CHANNEL, "یادآوری موعدها", NotificationManager.IMPORTANCE_HIGH).apply {{
                description = "یادآوری کارها و رویدادهای Planner"
            }})
        }}
        val launch = context.packageManager.getLaunchIntentForPackage(context.packageName) ?: Intent()
        val content = PendingIntent.getActivity(context, 9001, launch, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val id = intent.getStringExtra("id") ?: "planner"
        val body = intent.getStringExtra("body") ?: "موعد شما نزدیک است."
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) Notification.Builder(context, REMINDER_CHANNEL) else Notification.Builder(context)
        val n = builder
            .setSmallIcon(android.R.drawable.ic_popup_reminder)
            .setContentTitle(intent.getStringExtra("title") ?: "Planner")
            .setContentText(body)
            .setStyle(Notification.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setContentIntent(content)
            .build()
        nm.notify(code(id), n)
    }}

    private fun code(id: String): Int = id.hashCode() and 0x7fffffff
}}

class PlannerBootReceiver : BroadcastReceiver() {{
    override fun onReceive(context: Context, intent: Intent) {{
        if (intent.action == Intent.ACTION_BOOT_COMPLETED || intent.action == Intent.ACTION_MY_PACKAGE_REPLACED) {{
            PlannerReminderScheduler.restore(context)
        }}
    }}
}}
''', encoding='utf-8')

(kotlin_dir / 'PlannerWidgetProvider.kt').write_text(f'''package {pkg}

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.view.View
import android.widget.RemoteViews
import android.icu.text.SimpleDateFormat as IcuDateFormat
import android.icu.util.ULocale
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.Date

private const val PREFS = "planner_widget"
private const val API_BASE = "https://planner.datholding.ir/api"
private const val ACTION_REFRESH = "{pkg}.PLANNER_WIDGET_REFRESH"
private const val ACTION_TAB = "{pkg}.PLANNER_WIDGET_TAB"

object PlannerWidgetData {{
    fun persianDate(): String = try {{
        IcuDateFormat("EEEE d MMMM y", ULocale("fa_IR@calendar=persian")).format(Date())
    }} catch (_: Exception) {{ "Planner" }}

    private fun pendingActivity(context: Context, uri: String?, requestCode: Int): PendingIntent {{
        val intent = if (uri == null) context.packageManager.getLaunchIntentForPackage(context.packageName) ?: Intent()
        else Intent(Intent.ACTION_VIEW, Uri.parse(uri), context, MainActivity::class.java)
        return PendingIntent.getActivity(context, requestCode, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }}

    private fun pendingRefresh(context: Context, requestCode: Int): PendingIntent {{
        val intent = Intent(context, PlannerWidgetProvider::class.java).apply {{ action = ACTION_REFRESH }}
        return PendingIntent.getBroadcast(context, requestCode, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }}

    private fun pendingTab(context: Context, selected: String, requestCode: Int): PendingIntent {{
        val intent = Intent(context, PlannerWidgetProvider::class.java).apply {{ action = ACTION_TAB; putExtra("selected", selected) }}
        return PendingIntent.getBroadcast(context, requestCode, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }}

    fun updateAll(context: Context) {{
        val manager = AppWidgetManager.getInstance(context)
        renderOverview(context, manager, manager.getAppWidgetIds(ComponentName(context, PlannerWidgetProvider::class.java)))
        renderClock(context, manager, manager.getAppWidgetIds(ComponentName(context, PlannerClockWidgetProvider::class.java)))
        renderTasks(context, manager, manager.getAppWidgetIds(ComponentName(context, PlannerTasksWidgetProvider::class.java)))
        renderAgenda(context, manager, manager.getAppWidgetIds(ComponentName(context, PlannerAgendaWidgetProvider::class.java)))
    }}

    fun renderOverview(context: Context, manager: AppWidgetManager, ids: IntArray) {{
        val p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val tasks = safeArray(p.getString("task_items_json", "[]"))
        val events = safeArray(p.getString("event_items_json", "[]"))
        ids.forEach {{ id ->
            val v = RemoteViews(context.packageName, R.layout.planner_widget_overview)
            v.setTextViewText(R.id.widget_date, persianDate())
            v.setTextViewText(R.id.widget_summary, "${{p.getInt("tasks",0)}} کار • ${{p.getInt("events",0)}} رویداد")
            val showTasks = p.getString("selected_tab", "tasks") != "events"
            v.setTextViewText(R.id.widget_tab_tasks, if (showTasks) "● کارها" else "کارها")
            v.setTextViewText(R.id.widget_tab_events, if (showTasks) "رویدادها" else "● رویدادها")
            v.setOnClickPendingIntent(R.id.widget_tab_tasks, pendingTab(context,"tasks",110))
            v.setOnClickPendingIntent(R.id.widget_tab_events, pendingTab(context,"events",111))
            bindRows(v, if (showTasks) tasks else events, intArrayOf(R.id.widget_task_1,R.id.widget_task_2,R.id.widget_task_3,R.id.widget_event_1,R.id.widget_event_2), if (showTasks) "کاری ثبت نشده" else "رویدادی ثبت نشده")
            v.setOnClickPendingIntent(R.id.widget_root, pendingActivity(context,null,100))
            v.setOnClickPendingIntent(R.id.widget_add_task, pendingActivity(context,"planner://add-task",101))
            v.setOnClickPendingIntent(R.id.widget_add_event, pendingActivity(context,"planner://add-event",102))
            v.setOnClickPendingIntent(R.id.widget_refresh, pendingRefresh(context,103))
            manager.updateAppWidget(id,v)
        }}
    }}

    fun renderClock(context: Context, manager: AppWidgetManager, ids: IntArray) {{
        ids.forEach {{ id ->
            val v = RemoteViews(context.packageName, R.layout.planner_widget_clock)
            v.setTextViewText(R.id.clock_date, persianDate())
            v.setOnClickPendingIntent(R.id.clock_root, pendingActivity(context,null,200))
            manager.updateAppWidget(id,v)
        }}
    }}

    fun renderTasks(context: Context, manager: AppWidgetManager, ids: IntArray) {{
        val p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val tasks = safeArray(p.getString("task_items_json", "[]"))
        ids.forEach {{ id ->
            val v = RemoteViews(context.packageName, R.layout.planner_widget_tasks)
            v.setTextViewText(R.id.tasks_date, persianDate())
            bindRows(v,tasks,intArrayOf(R.id.tasks_1,R.id.tasks_2,R.id.tasks_3,R.id.tasks_4),"کاری ثبت نشده")
            v.setOnClickPendingIntent(R.id.tasks_root,pendingActivity(context,null,300))
            v.setOnClickPendingIntent(R.id.tasks_add,pendingActivity(context,"planner://add-task",301))
            v.setOnClickPendingIntent(R.id.tasks_refresh,pendingRefresh(context,302))
            manager.updateAppWidget(id,v)
        }}
    }}

    fun renderAgenda(context: Context, manager: AppWidgetManager, ids: IntArray) {{
        val p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val events = safeArray(p.getString("event_items_json", "[]"))
        ids.forEach {{ id ->
            val v = RemoteViews(context.packageName, R.layout.planner_widget_agenda)
            v.setTextViewText(R.id.agenda_date,persianDate())
            bindRows(v,events,intArrayOf(R.id.agenda_1,R.id.agenda_2,R.id.agenda_3,R.id.agenda_4),"رویدادی ثبت نشده")
            v.setOnClickPendingIntent(R.id.agenda_root,pendingActivity(context,null,400))
            v.setOnClickPendingIntent(R.id.agenda_add,pendingActivity(context,"planner://add-event",401))
            v.setOnClickPendingIntent(R.id.agenda_refresh,pendingRefresh(context,402))
            manager.updateAppWidget(id,v)
        }}
    }}

    fun refreshAsync(context: Context, pending: android.content.BroadcastReceiver.PendingResult) {{
        Thread {{
            try {{
                val tasksRaw = fetch(context, "/tasks")
                val eventsRaw = fetch(context, "/events")
                val tasks = compact(tasksRaw,"due_at",12)
                val events = compact(eventsRaw,"starts_at",12)
                context.getSharedPreferences(PREFS,Context.MODE_PRIVATE).edit()
                    .putInt("tasks",countOpen(tasksRaw)).putInt("events",countOpen(eventsRaw))
                    .putString("date",persianDate())
                    .putString("task_items_json",tasks.toString())
                    .putString("event_items_json",events.toString()).apply()
                updateAll(context)
            }} catch (_: Exception) {{
            }} finally {{ pending.finish() }}
        }}.start()
    }}

    private fun bindRows(v: RemoteViews, data: JSONArray, ids: IntArray, empty: String) {{
        ids.forEachIndexed {{ i, viewId ->
            val row=data.optJSONObject(i)
            if (row!=null) {{
                v.setViewVisibility(viewId,View.VISIBLE)
                val title=row.optString("title","")
                val date=row.optString("date","")
                v.setTextViewText(viewId, if (date.isBlank()) "• $title" else "• $title  —  $date")
            }} else if (i==0) {{ v.setViewVisibility(viewId,View.VISIBLE); v.setTextViewText(viewId,empty) }}
            else v.setViewVisibility(viewId,View.GONE)
        }}
    }}
    private fun safeArray(raw:String?):JSONArray=try{{JSONArray(raw?:"[]")}}catch(_:Exception){{JSONArray()}}
    private fun fetch(context:Context,path:String):JSONArray {{
        var access=SecureTokenStore.read(context) ?: throw IllegalStateException("No access token")
        var result=fetchWithToken(path,access)
        if(result.first==401) {{
            val refresh=SecureTokenStore.readRefresh(context) ?: throw IllegalStateException("Session expired")
            val renewed=refreshTokens(refresh)
            access=renewed.optString("access_token")
            val nextRefresh=renewed.optString("refresh_token",refresh)
            if(access.isBlank()) throw IllegalStateException("Refresh failed")
            SecureTokenStore.saveTokens(context,access,nextRefresh)
            result=fetchWithToken(path,access)
        }}
        if(result.first !in 200..299) throw IllegalStateException("HTTP ${{result.first}}")
        return JSONArray(result.second)
    }}
    private fun fetchWithToken(path:String,token:String):Pair<Int,String> {{
        val c=URL(API_BASE+path).openConnection() as HttpURLConnection
        c.requestMethod="GET"; c.connectTimeout=10000; c.readTimeout=10000
        c.setRequestProperty("Authorization","Bearer $token"); c.setRequestProperty("Accept","application/json")
        return try {{
            val code=c.responseCode
            val stream=if(code in 200..299)c.inputStream else c.errorStream
            Pair(code,stream?.bufferedReader()?.use{{it.readText()}} ?: "")
        }} finally {{ c.disconnect() }}
    }}
    private fun refreshTokens(refresh:String):JSONObject {{
        val c=URL(API_BASE+"/auth/refresh").openConnection() as HttpURLConnection
        c.requestMethod="POST"; c.doOutput=true; c.connectTimeout=10000; c.readTimeout=10000
        c.setRequestProperty("Content-Type","application/json"); c.setRequestProperty("Accept","application/json")
        c.outputStream.use {{ it.write(JSONObject().put("refresh_token",refresh).toString().toByteArray(Charsets.UTF_8)) }}
        return try {{
            val code=c.responseCode
            val stream=if(code in 200..299)c.inputStream else c.errorStream
            val body=stream?.bufferedReader()?.use{{it.readText()}} ?: ""
            if(code !in 200..299) throw IllegalStateException("Refresh HTTP $code")
            JSONObject(body)
        }} finally {{ c.disconnect() }}
    }}
    private fun countOpen(a:JSONArray):Int {{ var n=0; for(i in 0 until a.length()) if(a.optJSONObject(i)?.optString("status")!="completed") n++; return n }}
    private fun compact(a:JSONArray,key:String,limit:Int):JSONArray {{
        val out=JSONArray(); for(i in 0 until a.length()) {{ val x=a.optJSONObject(i)?:continue; if(x.optString("status")=="completed") continue; val r=JSONObject(); r.put("title",x.optString("title","")); r.put("date",x.optString(key,"")); out.put(r); if(out.length()>=limit) break }}; return out
    }}
}}

class PlannerWidgetProvider : AppWidgetProvider() {{
    override fun onUpdate(context:Context,manager:AppWidgetManager,ids:IntArray) {{ PlannerWidgetData.renderOverview(context,manager,ids); PlannerWidgetData.refreshAsync(context,goAsync()) }}
    override fun onReceive(context:Context,intent:Intent) {{ super.onReceive(context,intent); if(intent.action==ACTION_REFRESH) PlannerWidgetData.refreshAsync(context,goAsync()) else if(intent.action==ACTION_TAB) {{ context.getSharedPreferences(PREFS,Context.MODE_PRIVATE).edit().putString("selected_tab",intent.getStringExtra("selected") ?: "tasks").apply(); PlannerWidgetData.updateAll(context) }} }}
}}
class PlannerClockWidgetProvider : AppWidgetProvider() {{
    override fun onUpdate(context:Context,manager:AppWidgetManager,ids:IntArray) = PlannerWidgetData.renderClock(context,manager,ids)
}}
class PlannerTasksWidgetProvider : AppWidgetProvider() {{
    override fun onUpdate(context:Context,manager:AppWidgetManager,ids:IntArray) {{ PlannerWidgetData.renderTasks(context,manager,ids); PlannerWidgetData.refreshAsync(context,goAsync()) }}
}}
class PlannerAgendaWidgetProvider : AppWidgetProvider() {{
    override fun onUpdate(context:Context,manager:AppWidgetManager,ids:IntArray) {{ PlannerWidgetData.renderAgenda(context,manager,ids); PlannerWidgetData.refreshAsync(context,goAsync()) }}
}}
''', encoding='utf-8')

res = app / 'src/main/res'
for d in ('layout','xml','drawable','values'):
    (res/d).mkdir(parents=True,exist_ok=True)

(res/'drawable/planner_widget_bg.xml').write_text('''<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle"><solid android:color="#F9FCFA"/><corners android:radius="22dp"/><stroke android:width="1dp" android:color="#D8E4DD"/></shape>''',encoding='utf-8')

(res/'drawable/planner_widget_section_bg.xml').write_text('''<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle"><solid android:color="#FFFFFF"/><corners android:radius="10dp"/><stroke android:width="1dp" android:color="#E2EAE5"/></shape>''',encoding='utf-8')

(res/'layout/planner_widget_overview.xml').write_text('''<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android" android:id="@+id/widget_root" android:layout_width="match_parent" android:layout_height="match_parent" android:orientation="vertical" android:layoutDirection="rtl" android:padding="10dp" android:background="@drawable/planner_widget_bg">
<TextView android:id="@+id/widget_date" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="right" android:textStyle="bold" android:textSize="14sp"/>
<TextView android:id="@+id/widget_summary" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="right"/>
<LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="horizontal"><TextView android:id="@+id/widget_tab_tasks" android:layout_width="0dp" android:layout_weight="1" android:layout_height="40dp" android:gravity="center" android:text="کارها" android:textStyle="bold"/><TextView android:id="@+id/widget_tab_events" android:layout_width="0dp" android:layout_weight="1" android:layout_height="40dp" android:gravity="center" android:text="رویدادها" android:textStyle="bold"/></LinearLayout>
<ScrollView android:layout_width="match_parent" android:layout_height="0dp" android:layout_weight="1" android:fillViewport="false"><LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical"><TextView android:id="@+id/widget_task_1" android:layout_width="match_parent" android:layout_height="wrap_content" android:padding="8dp"/><TextView android:id="@+id/widget_task_2" android:layout_width="match_parent" android:layout_height="wrap_content" android:padding="8dp"/><TextView android:id="@+id/widget_task_3" android:layout_width="match_parent" android:layout_height="wrap_content" android:padding="8dp"/><TextView android:id="@+id/widget_event_1" android:layout_width="match_parent" android:layout_height="wrap_content" android:padding="8dp"/><TextView android:id="@+id/widget_event_2" android:layout_width="match_parent" android:layout_height="wrap_content" android:padding="8dp"/></LinearLayout></ScrollView>
<LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="horizontal"><Button android:id="@+id/widget_add_task" android:layout_width="0dp" android:layout_weight="1" android:layout_height="48dp" android:text="+ کار"/><Button android:id="@+id/widget_add_event" android:layout_width="0dp" android:layout_weight="1" android:layout_height="48dp" android:text="+ رویداد"/><Button android:id="@+id/widget_refresh" android:layout_width="50dp" android:layout_height="48dp" android:text="↻"/></LinearLayout></LinearLayout>''',encoding='utf-8')

(res/'layout/planner_widget_clock.xml').write_text('''<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android" android:id="@+id/clock_root" android:layout_width="match_parent" android:layout_height="match_parent" android:orientation="vertical" android:layoutDirection="rtl" android:textDirection="rtl" android:gravity="center" android:padding="16dp" android:background="@drawable/planner_widget_bg"><TextClock android:layout_width="wrap_content" android:layout_height="wrap_content" android:format24Hour="HH:mm" android:textSize="52sp" android:textStyle="bold"/><TextView android:id="@+id/clock_date" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="center" android:textDirection="rtl" android:textSize="19sp" android:textStyle="bold" android:paddingTop="8dp"/><TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="center" android:text="Planner" android:textSize="12sp" android:paddingTop="5dp"/></LinearLayout>''',encoding='utf-8')

(res/'layout/planner_widget_tasks.xml').write_text('''<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android" android:id="@+id/tasks_root" android:layout_width="match_parent" android:layout_height="match_parent" android:orientation="vertical" android:layoutDirection="rtl" android:textDirection="rtl" android:gravity="end" android:padding="14dp" android:background="@drawable/planner_widget_bg"><LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="horizontal" android:layoutDirection="rtl" android:gravity="center_vertical"><TextView android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:text="کارهای بعدی" android:textStyle="bold" android:textSize="18sp" android:gravity="start"/><TextClock android:layout_width="wrap_content" android:layout_height="wrap_content" android:format24Hour="HH:mm" android:textStyle="bold" android:textSize="24sp"/></LinearLayout><TextView android:id="@+id/tasks_date" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:textDirection="rtl" android:textSize="15sp" android:textStyle="bold" android:paddingTop="2dp"/><TextView android:id="@+id/tasks_1" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:textDirection="rtl" android:background="@drawable/planner_widget_section_bg" android:padding="8dp" android:layout_marginTop="7dp"/><TextView android:id="@+id/tasks_2" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:textDirection="rtl" android:background="@drawable/planner_widget_section_bg" android:padding="8dp" android:layout_marginTop="5dp"/><TextView android:id="@+id/tasks_3" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:textDirection="rtl" android:background="@drawable/planner_widget_section_bg" android:padding="8dp" android:layout_marginTop="5dp"/><TextView android:id="@+id/tasks_4" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:textDirection="rtl" android:background="@drawable/planner_widget_section_bg" android:padding="8dp" android:layout_marginTop="5dp"/><LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="horizontal" android:layoutDirection="rtl" android:paddingTop="9dp"><Button android:id="@+id/tasks_add" android:layout_width="0dp" android:layout_height="40dp" android:layout_weight="2" android:text="+ کار جدید"/><Button android:id="@+id/tasks_refresh" android:layout_width="0dp" android:layout_height="40dp" android:layout_weight="1" android:text="↻"/></LinearLayout></LinearLayout>''',encoding='utf-8')

(res/'layout/planner_widget_agenda.xml').write_text('''<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android" android:id="@+id/agenda_root" android:layout_width="match_parent" android:layout_height="match_parent" android:orientation="vertical" android:layoutDirection="rtl" android:textDirection="rtl" android:gravity="end" android:padding="14dp" android:background="@drawable/planner_widget_bg"><TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="برنامه پیش‌رو" android:textStyle="bold" android:textSize="18sp" android:gravity="end"/><TextView android:id="@+id/agenda_date" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:textDirection="rtl" android:textSize="14sp" android:textStyle="bold"/><TextView android:id="@+id/agenda_1" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:textDirection="rtl" android:background="@drawable/planner_widget_section_bg" android:padding="8dp" android:layout_marginTop="7dp"/><TextView android:id="@+id/agenda_2" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:textDirection="rtl" android:background="@drawable/planner_widget_section_bg" android:padding="8dp" android:layout_marginTop="5dp"/><TextView android:id="@+id/agenda_3" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:textDirection="rtl" android:background="@drawable/planner_widget_section_bg" android:padding="8dp" android:layout_marginTop="5dp"/><TextView android:id="@+id/agenda_4" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:textDirection="rtl" android:background="@drawable/planner_widget_section_bg" android:padding="8dp" android:layout_marginTop="5dp"/><LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="horizontal" android:layoutDirection="rtl" android:paddingTop="9dp"><Button android:id="@+id/agenda_add" android:layout_width="0dp" android:layout_height="40dp" android:layout_weight="2" android:text="+ رویداد"/><Button android:id="@+id/agenda_refresh" android:layout_width="0dp" android:layout_height="40dp" android:layout_weight="1" android:text="↻"/></LinearLayout></LinearLayout>''',encoding='utf-8')

infos = {
 'planner_widget_overview_info.xml':('@layout/planner_widget_overview','180dp','250dp'),
 'planner_widget_clock_info.xml':('@layout/planner_widget_clock','180dp','100dp'),
 'planner_widget_tasks_info.xml':('@layout/planner_widget_tasks','180dp','230dp'),
 'planner_widget_agenda_info.xml':('@layout/planner_widget_agenda','180dp','220dp'),
}
for name,(layout,w,h) in infos.items():
    (res/'xml'/name).write_text(f'''<appwidget-provider xmlns:android="http://schemas.android.com/apk/res/android" android:minWidth="{w}" android:minHeight="{h}" android:minResizeWidth="110dp" android:minResizeHeight="80dp" android:updatePeriodMillis="1800000" android:initialLayout="{layout}" android:resizeMode="horizontal|vertical" android:widgetCategory="home_screen"/>''',encoding='utf-8')

(res/'xml/network_security_config.xml').write_text('''<network-security-config><base-config cleartextTrafficPermitted="false"/></network-security-config>''',encoding='utf-8')
(res/'values/planner_widget_strings.xml').write_text('''<resources><string name="planner_widget_overview_label">Planner — خلاصه</string><string name="planner_widget_clock_label">Planner — ساعت و تاریخ</string><string name="planner_widget_tasks_label">Planner — کارها</string><string name="planner_widget_agenda_label">Planner — برنامه</string></resources>''',encoding='utf-8')

x=manifest.read_text(encoding='utf-8')
if 'android.permission.INTERNET' not in x:
    x=x.replace('<manifest xmlns:android="http://schemas.android.com/apk/res/android">','<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n    <uses-permission android:name="android.permission.INTERNET" />',1)
if 'android.permission.POST_NOTIFICATIONS' not in x:
    x=x.replace('<manifest xmlns:android="http://schemas.android.com/apk/res/android">','<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />\n    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />',1)
x=re.sub(r'(<application\b[^>]*android:label=")[^"]*(")',r'\1Planner\2',x,count=1,flags=re.S)
# App hardening attributes.
if 'android:usesCleartextTraffic=' not in x:
    x=x.replace('<application','<application android:usesCleartextTraffic="false"',1)
if 'android:networkSecurityConfig=' not in x:
    x=x.replace('<application','<application android:networkSecurityConfig="@xml/network_security_config"',1)
if 'android:allowBackup=' not in x:
    x=x.replace('<application','<application android:allowBackup="false"',1)

for host in ('oauth','add-task','add-event'):
    sig=f'android:scheme="planner" android:host="{host}"'
    if sig not in x:
        block=f'''            <intent-filter>\n                <action android:name="android.intent.action.VIEW" />\n                <category android:name="android.intent.category.DEFAULT" />\n                <category android:name="android.intent.category.BROWSABLE" />\n                <data android:scheme="planner" android:host="{host}" />\n            </intent-filter>\n'''
        x=x.replace('</activity>',block+'        </activity>',1)

providers=[
 ('PlannerWidgetProvider','@string/planner_widget_overview_label','@xml/planner_widget_overview_info'),
 ('PlannerClockWidgetProvider','@string/planner_widget_clock_label','@xml/planner_widget_clock_info'),
 ('PlannerTasksWidgetProvider','@string/planner_widget_tasks_label','@xml/planner_widget_tasks_info'),
 ('PlannerAgendaWidgetProvider','@string/planner_widget_agenda_label','@xml/planner_widget_agenda_info'),
]
for cls,label,info in providers:
    if cls not in x:
        receiver=f'''\n        <receiver android:name="{pkg}.{cls}" android:label="{label}" android:enabled="true" android:exported="false">\n            <intent-filter><action android:name="android.appwidget.action.APPWIDGET_UPDATE" /></intent-filter>\n            <meta-data android:name="android.appwidget.provider" android:resource="{info}" />\n        </receiver>\n'''
        x=x.replace('</application>',receiver+'    </application>',1)
if 'PlannerReminderReceiver' not in x:
    reminder_receivers=f'''
        <receiver android:name="{pkg}.PlannerReminderReceiver" android:enabled="true" android:exported="false" />
        <receiver android:name="{pkg}.PlannerBootReceiver" android:enabled="true" android:exported="false">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED" />
                <action android:name="android.intent.action.MY_PACKAGE_REPLACED" />
            </intent-filter>
        </receiver>
'''
    x=x.replace('</application>',reminder_receivers+'    </application>',1)

manifest.write_text(x,encoding='utf-8')

print('Android integration ready:',pkg)
print('Widgets: overview, clock, tasks, agenda')
print('Secure token storage: Android Keystore AES-GCM')
