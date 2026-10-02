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
    private const val ALIAS = "planner_session_key_v1"
    private const val PREFS = "planner_secure_session"
    private const val TOKEN = "token_cipher"
    private const val IV = "token_iv"

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

    fun save(context: Context, token: String) {{
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val encrypted = cipher.doFinal(token.toByteArray(Charsets.UTF_8))
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(TOKEN, Base64.encodeToString(encrypted, Base64.NO_WRAP))
            .putString(IV, Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .apply()
    }}

    fun read(context: Context): String? = try {{
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val enc = prefs.getString(TOKEN, null) ?: return null
        val iv = prefs.getString(IV, null) ?: return null
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, Base64.decode(iv, Base64.NO_WRAP)))
        String(cipher.doFinal(Base64.decode(enc, Base64.NO_WRAP)), Charsets.UTF_8)
    }} catch (_: Exception) {{ null }}

    fun clear(context: Context) {{
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().clear().apply()
    }}
}}
''', encoding='utf-8')

main.write_text(f'''package {pkg}

import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.content.Context
import android.os.Build
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {{
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {{
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "planner/security").setMethodCallHandler {{ call, result ->
            when (call.method) {{
                "setToken" -> {{
                    val token = call.argument<String>("token") ?: ""
                    if (token.isBlank()) result.error("TOKEN_EMPTY", "Token is empty", null)
                    else {{ SecureTokenStore.save(this, token); result.success(true) }}
                }}
                "getToken" -> result.success(SecureTokenStore.read(this))
                "clearToken" -> {{ SecureTokenStore.clear(this); result.success(true) }}
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
            bindRows(v, tasks, intArrayOf(R.id.widget_task_1,R.id.widget_task_2,R.id.widget_task_3), "کاری ثبت نشده")
            bindRows(v, events, intArrayOf(R.id.widget_event_1,R.id.widget_event_2), "رویدادی ثبت نشده")
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
                val token = SecureTokenStore.read(context) ?: return@Thread
                val tasksRaw = fetch("/tasks", token)
                val eventsRaw = fetch("/events", token)
                val tasks = compact(tasksRaw,"due_at",4)
                val events = compact(eventsRaw,"starts_at",4)
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
    private fun fetch(path:String,token:String):JSONArray {{
        val c=URL(API_BASE+path).openConnection() as HttpURLConnection
        c.requestMethod="GET"; c.connectTimeout=10000; c.readTimeout=10000
        c.setRequestProperty("Authorization","Bearer $token"); c.setRequestProperty("Accept","application/json")
        return try {{ val code=c.responseCode; if(code !in 200..299) throw IllegalStateException("HTTP $code"); JSONArray(c.inputStream.bufferedReader().use{{it.readText()}}) }} finally {{ c.disconnect() }}
    }}
    private fun countOpen(a:JSONArray):Int {{ var n=0; for(i in 0 until a.length()) if(a.optJSONObject(i)?.optString("status")!="completed") n++; return n }}
    private fun compact(a:JSONArray,key:String,limit:Int):JSONArray {{
        val out=JSONArray(); for(i in 0 until a.length()) {{ val x=a.optJSONObject(i)?:continue; if(x.optString("status")=="completed") continue; val r=JSONObject(); r.put("title",x.optString("title","")); r.put("date",x.optString(key,"")); out.put(r); if(out.length()>=limit) break }}; return out
    }}
}}

class PlannerWidgetProvider : AppWidgetProvider() {{
    override fun onUpdate(context:Context,manager:AppWidgetManager,ids:IntArray) {{ PlannerWidgetData.renderOverview(context,manager,ids); PlannerWidgetData.refreshAsync(context,goAsync()) }}
    override fun onReceive(context:Context,intent:Intent) {{ super.onReceive(context,intent); if(intent.action==ACTION_REFRESH) PlannerWidgetData.refreshAsync(context,goAsync()) }}
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

(res/'layout/planner_widget_overview.xml').write_text('''<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android" android:id="@+id/widget_root" android:layout_width="match_parent" android:layout_height="match_parent" android:orientation="vertical" android:padding="14dp" android:background="@drawable/planner_widget_bg">
<LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="horizontal" android:gravity="center_vertical"><TextView android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:text="Planner" android:textStyle="bold" android:textSize="17sp"/><TextClock android:layout_width="wrap_content" android:layout_height="wrap_content" android:format24Hour="HH:mm" android:textStyle="bold" android:textSize="15sp"/></LinearLayout>
<TextView android:id="@+id/widget_date" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:textSize="12sp"/><TextView android:id="@+id/widget_summary" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:textStyle="bold" android:paddingTop="3dp"/>
<TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="کارهای بعدی" android:gravity="end" android:textStyle="bold" android:paddingTop="7dp"/><TextView android:id="@+id/widget_task_1" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:maxLines="1"/><TextView android:id="@+id/widget_task_2" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:maxLines="1"/><TextView android:id="@+id/widget_task_3" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:maxLines="1"/>
<TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="رویدادهای بعدی" android:gravity="end" android:textStyle="bold" android:paddingTop="6dp"/><TextView android:id="@+id/widget_event_1" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:maxLines="1"/><TextView android:id="@+id/widget_event_2" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:maxLines="1"/>
<LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="horizontal" android:paddingTop="8dp"><Button android:id="@+id/widget_refresh" android:layout_width="0dp" android:layout_height="40dp" android:layout_weight="1" android:text="↻"/><Button android:id="@+id/widget_add_task" android:layout_width="0dp" android:layout_height="40dp" android:layout_weight="1" android:text="+ کار"/><Button android:id="@+id/widget_add_event" android:layout_width="0dp" android:layout_height="40dp" android:layout_weight="1" android:text="+ رویداد"/></LinearLayout></LinearLayout>''',encoding='utf-8')

(res/'layout/planner_widget_clock.xml').write_text('''<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android" android:id="@+id/clock_root" android:layout_width="match_parent" android:layout_height="match_parent" android:orientation="vertical" android:gravity="center" android:padding="16dp" android:background="@drawable/planner_widget_bg"><TextClock android:layout_width="wrap_content" android:layout_height="wrap_content" android:format24Hour="HH:mm" android:textSize="50sp" android:textStyle="bold"/><TextView android:id="@+id/clock_date" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="center" android:textSize="18sp" android:textStyle="bold" android:paddingTop="8dp"/><TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="center" android:text="Planner" android:textSize="12sp" android:paddingTop="5dp"/></LinearLayout>''',encoding='utf-8')

(res/'layout/planner_widget_tasks.xml').write_text('''<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android" android:id="@+id/tasks_root" android:layout_width="match_parent" android:layout_height="match_parent" android:orientation="vertical" android:padding="14dp" android:background="@drawable/planner_widget_bg"><TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="کارهای بعدی" android:textStyle="bold" android:textSize="18sp" android:gravity="end"/><TextView android:id="@+id/tasks_date" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:textSize="11sp"/><TextView android:id="@+id/tasks_1" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:paddingTop="8dp"/><TextView android:id="@+id/tasks_2" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end"/><TextView android:id="@+id/tasks_3" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end"/><TextView android:id="@+id/tasks_4" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end"/><LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="horizontal" android:paddingTop="8dp"><Button android:id="@+id/tasks_refresh" android:layout_width="0dp" android:layout_height="40dp" android:layout_weight="1" android:text="↻"/><Button android:id="@+id/tasks_add" android:layout_width="0dp" android:layout_height="40dp" android:layout_weight="2" android:text="+ کار جدید"/></LinearLayout></LinearLayout>''',encoding='utf-8')

(res/'layout/planner_widget_agenda.xml').write_text('''<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android" android:id="@+id/agenda_root" android:layout_width="match_parent" android:layout_height="match_parent" android:orientation="vertical" android:padding="14dp" android:background="@drawable/planner_widget_bg"><TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="برنامه پیش‌رو" android:textStyle="bold" android:textSize="18sp" android:gravity="end"/><TextView android:id="@+id/agenda_date" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:textSize="11sp"/><TextView android:id="@+id/agenda_1" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:paddingTop="8dp"/><TextView android:id="@+id/agenda_2" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end"/><TextView android:id="@+id/agenda_3" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end"/><TextView android:id="@+id/agenda_4" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end"/><LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="horizontal" android:paddingTop="8dp"><Button android:id="@+id/agenda_refresh" android:layout_width="0dp" android:layout_height="40dp" android:layout_weight="1" android:text="↻"/><Button android:id="@+id/agenda_add" android:layout_width="0dp" android:layout_height="40dp" android:layout_weight="2" android:text="+ رویداد"/></LinearLayout></LinearLayout>''',encoding='utf-8')

infos = {
 'planner_widget_overview_info.xml':('@layout/planner_widget_overview','180dp','220dp'),
 'planner_widget_clock_info.xml':('@layout/planner_widget_clock','180dp','100dp'),
 'planner_widget_tasks_info.xml':('@layout/planner_widget_tasks','180dp','180dp'),
 'planner_widget_agenda_info.xml':('@layout/planner_widget_agenda','180dp','180dp'),
}
for name,(layout,w,h) in infos.items():
    (res/'xml'/name).write_text(f'''<appwidget-provider xmlns:android="http://schemas.android.com/apk/res/android" android:minWidth="{w}" android:minHeight="{h}" android:minResizeWidth="110dp" android:minResizeHeight="80dp" android:updatePeriodMillis="1800000" android:initialLayout="{layout}" android:resizeMode="horizontal|vertical" android:widgetCategory="home_screen"/>''',encoding='utf-8')

(res/'xml/network_security_config.xml').write_text('''<network-security-config><base-config cleartextTrafficPermitted="false"/></network-security-config>''',encoding='utf-8')
(res/'values/planner_widget_strings.xml').write_text('''<resources><string name="planner_widget_overview_label">Planner — خلاصه</string><string name="planner_widget_clock_label">Planner — ساعت و تاریخ</string><string name="planner_widget_tasks_label">Planner — کارها</string><string name="planner_widget_agenda_label">Planner — برنامه</string></resources>''',encoding='utf-8')

x=manifest.read_text(encoding='utf-8')
if 'android.permission.INTERNET' not in x:
    x=x.replace('<manifest xmlns:android="http://schemas.android.com/apk/res/android">','<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n    <uses-permission android:name="android.permission.INTERNET" />',1)
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
manifest.write_text(x,encoding='utf-8')

print('Android integration ready:',pkg)
print('Widgets: overview, clock, tasks, agenda')
print('Secure token storage: Android Keystore AES-GCM')
