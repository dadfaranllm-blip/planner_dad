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

main.write_text(f'''package {pkg}

import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.content.Context
import android.os.Build
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {{
    private val widgetChannelName = "planner/widget"
    private val securityChannelName = "planner/security"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {{
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, securityChannelName).setMethodCallHandler {{ call, result ->
            when (call.method) {{
                "setToken" -> {{
                    val token = call.argument<String>("token") ?: ""
                    if (token.isBlank()) result.error("EMPTY_TOKEN", "Token is empty", null)
                    else {{
                        SecureTokenStore.setToken(this, token)
                        result.success(true)
                    }}
                }}
                "getToken" -> result.success(SecureTokenStore.getToken(this))
                "clearToken" -> {{
                    SecureTokenStore.clearToken(this)
                    result.success(true)
                }}
                else -> result.notImplemented()
            }}
        }}

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, widgetChannelName).setMethodCallHandler {{ call, result ->
            when (call.method) {{
                "updateWidget" -> {{
                    val prefs = getSharedPreferences("planner_widget", Context.MODE_PRIVATE)
                    prefs.edit()
                        .putInt("tasks", call.argument<Int>("tasks") ?: 0)
                        .putInt("events", call.argument<Int>("events") ?: 0)
                        .putString("date", call.argument<String>("date") ?: "")
                        .putString("time", call.argument<String>("time") ?: "")
                        .putString("task_items_json", call.argument<String>("taskItemsJson") ?: "[]")
                        .putString("event_items_json", call.argument<String>("eventItemsJson") ?: "[]")
                        .apply()
                    PlannerWidgetProvider.updateCachedWidgets(this)
                    result.success(true)
                }}
                "widgetStatus" -> {{
                    val manager = AppWidgetManager.getInstance(this)
                    val provider = ComponentName(this, PlannerWidgetProvider::class.java)
                    val registered = manager.installedProviders.any {{ it.provider == provider }}
                    result.success(mapOf(
                        "registered" to registered,
                        "pinSupported" to (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && manager.isRequestPinAppWidgetSupported),
                        "provider" to provider.flattenToString(),
                        "package" to packageName
                    ))
                }}
                "pinWidget" -> {{
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {{
                        val manager = AppWidgetManager.getInstance(this)
                        val provider = ComponentName(this, PlannerWidgetProvider::class.java)
                        val registered = manager.installedProviders.any {{ it.provider == provider }}
                        if (registered && manager.isRequestPinAppWidgetSupported) {{
                            result.success(manager.requestPinAppWidget(provider, null, null))
                        }} else {{
                            result.success(false)
                        }}
                    }} else {{
                        result.success(false)
                    }}
                }}
                else -> result.notImplemented()
            }}
        }}
    }}
}}
''', encoding='utf-8')

secure_store = main.parent / 'SecureTokenStore.kt'
secure_store.write_text(f'''package {pkg}

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
    private const val KEY_ALIAS = "planner_session_token_v1"
    private const val PREFS = "planner_secure_session"
    private const val CIPHER_TEXT = "ciphertext"
    private const val IV = "iv"
    private const val TRANSFORMATION = "AES/GCM/NoPadding"

    private fun key(): SecretKey {{
        val store = KeyStore.getInstance("AndroidKeyStore").apply {{ load(null) }}
        val existing = store.getKey(KEY_ALIAS, null) as? SecretKey
        if (existing != null) return existing
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(
            KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build()
        )
        return generator.generateKey()
    }}

    fun setToken(context: Context, token: String) {{
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val encrypted = cipher.doFinal(token.toByteArray(Charsets.UTF_8))
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(CIPHER_TEXT, Base64.encodeToString(encrypted, Base64.NO_WRAP))
            .putString(IV, Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .apply()
    }}

    fun getToken(context: Context): String? {{
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val encodedCipher = prefs.getString(CIPHER_TEXT, null) ?: return null
        val encodedIv = prefs.getString(IV, null) ?: return null
        return try {{
            val cipher = Cipher.getInstance(TRANSFORMATION)
            val iv = Base64.decode(encodedIv, Base64.NO_WRAP)
            cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, iv))
            val decrypted = cipher.doFinal(Base64.decode(encodedCipher, Base64.NO_WRAP))
            String(decrypted, Charsets.UTF_8)
        }} catch (_: Exception) {{
            clearToken(context)
            null
        }}
    }}

    fun clearToken(context: Context) {{
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().clear().apply()
    }}
}}
''', encoding='utf-8')

provider = main.parent / 'PlannerWidgetProvider.kt'
provider.write_text(f'''package {pkg}

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.view.View
import android.widget.RemoteViews
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class PlannerWidgetProvider : AppWidgetProvider() {{
    companion object {{
        private const val PREFS = "planner_widget"
        private const val API_BASE = "https://planner.datholding.ir/api"
        const val ACTION_REFRESH = "{pkg}.PLANNER_WIDGET_REFRESH"

        fun updateCachedWidgets(context: Context) {{
            val manager = AppWidgetManager.getInstance(context)
            val component = ComponentName(context, PlannerWidgetProvider::class.java)
            val ids = manager.getAppWidgetIds(component)
            PlannerWidgetProvider().renderCached(context, manager, ids)
        }}
    }}

    override fun onEnabled(context: Context) {{
        super.onEnabled(context)
        updateCachedWidgets(context)
    }}

    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {{
        renderCached(context, manager, ids)
        refreshFromServer(context, manager, ids)
    }}

    override fun onReceive(context: Context, intent: Intent) {{
        super.onReceive(context, intent)
        if (intent.action == ACTION_REFRESH) {{
            val manager = AppWidgetManager.getInstance(context)
            val component = ComponentName(context, PlannerWidgetProvider::class.java)
            val ids = manager.getAppWidgetIds(component)
            renderCached(context, manager, ids)
            refreshFromServer(context, manager, ids)
        }}
    }}

    private fun renderCached(context: Context, manager: AppWidgetManager, ids: IntArray) {{
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val taskCount = prefs.getInt("tasks", 0)
        val eventCount = prefs.getInt("events", 0)
        val date = prefs.getString("date", "") ?: ""
        val cachedTime = prefs.getString("time", "") ?: ""
        val time = if (cachedTime.isNotBlank()) cachedTime else SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date())
        val taskItems = safeArray(prefs.getString("task_items_json", "[]"))
        val eventItems = safeArray(prefs.getString("event_items_json", "[]"))

        for (id in ids) {{
            val views = RemoteViews(context.packageName, R.layout.planner_widget)
            views.setTextViewText(R.id.widget_date, if (date.isBlank()) "Planner" else date)
            views.setTextViewText(R.id.widget_time, time)
            views.setTextViewText(R.id.widget_summary, "$taskCount کار • $eventCount رویداد")
            bindRows(views, taskItems, intArrayOf(R.id.widget_task_1, R.id.widget_task_2, R.id.widget_task_3), "کاری ثبت نشده")
            bindRows(views, eventItems, intArrayOf(R.id.widget_event_1, R.id.widget_event_2), "رویدادی ثبت نشده")

            val launchIntent = context.packageManager.getLaunchIntentForPackage(context.packageName)
            if (launchIntent != null) {{
                val pending = PendingIntent.getActivity(context, 10, launchIntent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
                views.setOnClickPendingIntent(R.id.widget_header, pending)
            }}

            val addTaskIntent = Intent(Intent.ACTION_VIEW, Uri.parse("planner://add-task")).apply {{ setPackage(context.packageName) }}
            val addTaskPending = PendingIntent.getActivity(context, 11, addTaskIntent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            views.setOnClickPendingIntent(R.id.widget_add_task, addTaskPending)

            val addEventIntent = Intent(Intent.ACTION_VIEW, Uri.parse("planner://add-event")).apply {{ setPackage(context.packageName) }}
            val addEventPending = PendingIntent.getActivity(context, 12, addEventIntent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            views.setOnClickPendingIntent(R.id.widget_add_event, addEventPending)

            val refreshIntent = Intent(context, PlannerWidgetProvider::class.java).apply {{ action = ACTION_REFRESH }}
            val refreshPending = PendingIntent.getBroadcast(context, 13, refreshIntent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            views.setOnClickPendingIntent(R.id.widget_refresh, refreshPending)

            manager.updateAppWidget(id, views)
        }}
    }}

    private fun bindRows(views: RemoteViews, items: JSONArray, ids: IntArray, emptyText: String) {{
        ids.forEachIndexed {{ index, viewId ->
            if (index < items.length()) {{
                val obj = items.optJSONObject(index) ?: JSONObject()
                val title = obj.optString("title", "")
                val date = obj.optString("date", "")
                views.setViewVisibility(viewId, View.VISIBLE)
                views.setTextViewText(viewId, if (date.isBlank()) "• $title" else "• $title  —  $date")
            }} else if (index == 0 && items.length() == 0) {{
                views.setViewVisibility(viewId, View.VISIBLE)
                views.setTextViewText(viewId, emptyText)
            }} else {{
                views.setViewVisibility(viewId, View.GONE)
            }}
        }}
    }}

    private fun safeArray(raw: String?): JSONArray = try {{ JSONArray(raw ?: "[]") }} catch (_: Exception) {{ JSONArray() }}

    private fun refreshFromServer(context: Context, manager: AppWidgetManager, ids: IntArray) {{
        val token = SecureTokenStore.getToken(context) ?: ""
        if (token.isBlank()) return
        val pending = goAsync()
        Thread {{
            try {{
                val tasksRaw = fetch("/tasks", token)
                val eventsRaw = fetch("/events", token)
                val tasks = compact(tasksRaw, "due_at", 3)
                val events = compact(eventsRaw, "starts_at", 2)
                val openTasks = countOpen(tasksRaw)
                val openEvents = countOpen(eventsRaw)
                context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                    .putInt("tasks", openTasks)
                    .putInt("events", openEvents)
                    .putString("task_items_json", tasks.toString())
                    .putString("event_items_json", events.toString())
                    .putString("time", SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date()))
                    .apply()
                renderCached(context, manager, ids)
            }} catch (_: Exception) {{
                // Preserve cached data when offline/API unavailable.
            }} finally {{
                pending.finish()
            }}
        }}.start()
    }}

    private fun fetch(path: String, token: String): JSONArray {{
        val connection = URL(API_BASE + path).openConnection() as HttpURLConnection
        connection.requestMethod = "GET"
        connection.connectTimeout = 10000
        connection.readTimeout = 10000
        connection.setRequestProperty("Authorization", "Bearer $token")
        connection.setRequestProperty("Accept", "application/json")
        return try {{
            val code = connection.responseCode
            if (code !in 200..299) throw IllegalStateException("HTTP $code")
            JSONArray(connection.inputStream.bufferedReader().use {{ it.readText() }})
        }} finally {{
            connection.disconnect()
        }}
    }}

    private fun countOpen(source: JSONArray): Int {{
        var count = 0
        for (i in 0 until source.length()) {{
            if (source.optJSONObject(i)?.optString("status") != "completed") count++
        }}
        return count
    }}

    private fun compact(source: JSONArray, dateKey: String, limit: Int): JSONArray {{
        val out = JSONArray()
        for (i in 0 until source.length()) {{
            val item = source.optJSONObject(i) ?: continue
            if (item.optString("status") == "completed") continue
            val row = JSONObject()
            row.put("title", item.optString("title", ""))
            row.put("date", item.optString(dateKey, ""))
            out.put(row)
            if (out.length() >= limit) break
        }}
        return out
    }}
}}
''', encoding='utf-8')

res = app / 'src/main/res'
for d in ('layout', 'xml', 'drawable', 'values'):
    (res / d).mkdir(parents=True, exist_ok=True)

(res / 'xml/network_security_config.xml').write_text('''<network-security-config>
    <base-config cleartextTrafficPermitted="false">
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </base-config>
</network-security-config>
''', encoding='utf-8')

(res / 'layout/planner_widget.xml').write_text('''<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:id="@+id/widget_root"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical"
    android:padding="12dp"
    android:background="@drawable/planner_widget_bg">

    <LinearLayout
        android:id="@+id/widget_header"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:orientation="horizontal"
        android:gravity="center_vertical">
        <TextView android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:text="Planner" android:textStyle="bold" android:textSize="17sp" />
        <TextView android:id="@+id/widget_time" android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="--:--" android:textSize="14sp" android:textStyle="bold" />
    </LinearLayout>

    <TextView android:id="@+id/widget_date" android:layout_width="match_parent" android:layout_height="wrap_content" android:text="تاریخ شمسی" android:textSize="12sp" android:gravity="end" android:paddingTop="2dp" />
    <TextView android:id="@+id/widget_summary" android:layout_width="match_parent" android:layout_height="wrap_content" android:text="0 کار • 0 رویداد" android:textSize="12sp" android:gravity="end" android:paddingTop="2dp" />

    <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="کارهای بعدی" android:textStyle="bold" android:gravity="end" android:paddingTop="6dp" />
    <TextView android:id="@+id/widget_task_1" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:text="کاری ثبت نشده" android:textSize="12sp" android:maxLines="1" android:ellipsize="end" />
    <TextView android:id="@+id/widget_task_2" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:textSize="12sp" android:maxLines="1" android:ellipsize="end" />
    <TextView android:id="@+id/widget_task_3" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:textSize="12sp" android:maxLines="1" android:ellipsize="end" />

    <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="رویدادهای بعدی" android:textStyle="bold" android:gravity="end" android:paddingTop="5dp" />
    <TextView android:id="@+id/widget_event_1" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:text="رویدادی ثبت نشده" android:textSize="12sp" android:maxLines="1" android:ellipsize="end" />
    <TextView android:id="@+id/widget_event_2" android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="end" android:textSize="12sp" android:maxLines="1" android:ellipsize="end" />

    <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="horizontal" android:gravity="center" android:paddingTop="7dp">
        <Button android:id="@+id/widget_refresh" android:layout_width="0dp" android:layout_height="40dp" android:layout_weight="1" android:text="↻" android:textSize="14sp" />
        <Button android:id="@+id/widget_add_task" android:layout_width="0dp" android:layout_height="40dp" android:layout_weight="1" android:layout_marginStart="6dp" android:text="+ کار" android:textSize="10sp" />
        <Button android:id="@+id/widget_add_event" android:layout_width="0dp" android:layout_height="40dp" android:layout_weight="1" android:layout_marginStart="6dp" android:text="+ رویداد" android:textSize="10sp" />
    </LinearLayout>
</LinearLayout>
''', encoding='utf-8')

(res / 'drawable/planner_widget_bg.xml').write_text('''<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#FAFAFA" />
    <corners android:radius="20dp" />
    <stroke android:width="1dp" android:color="#DDE4E0" />
</shape>
''', encoding='utf-8')

(res / 'xml/planner_widget_info.xml').write_text('''<appwidget-provider xmlns:android="http://schemas.android.com/apk/res/android"
    android:minWidth="110dp"
    android:minHeight="110dp"
    android:minResizeWidth="110dp"
    android:minResizeHeight="80dp"
    android:updatePeriodMillis="1800000"
    android:initialLayout="@layout/planner_widget"
    android:previewLayout="@layout/planner_widget"
    android:description="@string/planner_widget_description"
    android:targetCellWidth="3"
    android:targetCellHeight="3"
    android:resizeMode="horizontal|vertical"
    android:widgetCategory="home_screen" />
''', encoding='utf-8')

(res / 'values/planner_widget_strings.xml').write_text('''<resources>
    <string name="planner_widget_description">کارها و رویدادهای Planner با دسترسی سریع</string>
</resources>
''', encoding='utf-8')

x = manifest.read_text(encoding='utf-8')
if 'android.permission.INTERNET' not in x:
    x = x.replace('<manifest xmlns:android="http://schemas.android.com/apk/res/android">', '<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n    <uses-permission android:name="android.permission.INTERNET" />', 1)

x = re.sub(r'(<application\b[^>]*android:label=")[^"]*(")', r'\1Planner\2', x, count=1, flags=re.S)

# Security hardening: block cleartext traffic and Android backups of app/session data.
def ensure_app_attr(xml, attr, value):
    if attr in xml:
        return re.sub(rf'({re.escape(attr)}=")[^"]*(")', rf'\1{value}\2', xml, count=1)
    return re.sub(r'(<application\b)', rf'\1 {attr}="{value}"', xml, count=1)

x = ensure_app_attr(x, 'android:usesCleartextTraffic', 'false')
x = ensure_app_attr(x, 'android:allowBackup', 'false')
x = ensure_app_attr(x, 'android:networkSecurityConfig', '@xml/network_security_config')

activity_filters = [
    ('oauth', 'oauth'),
    ('add-task', 'add-task'),
    ('add-event', 'add-event'),
]
for key, host in activity_filters:
    signature = f'android:scheme="planner" android:host="{host}"'
    if signature not in x:
        marker = '</activity>'
        block = f'''            <intent-filter>\n                <action android:name="android.intent.action.VIEW" />\n                <category android:name="android.intent.category.DEFAULT" />\n                <category android:name="android.intent.category.BROWSABLE" />\n                <data android:scheme="planner" android:host="{host}" />\n            </intent-filter>\n'''
        x = x.replace(marker, block + '        ' + marker, 1)

if 'PlannerWidgetProvider' not in x:
    receiver = f'''
        <receiver
            android:name="{pkg}.PlannerWidgetProvider"
            android:label="Planner"
            android:enabled="true"
            android:exported="true">
            <intent-filter>
                <action android:name="android.appwidget.action.APPWIDGET_UPDATE" />
            </intent-filter>
            <meta-data
                android:name="android.appwidget.provider"
                android:resource="@xml/planner_widget_info" />
        </receiver>
'''
    x = x.replace('</application>', receiver + '    </application>', 1)

manifest.write_text(x, encoding='utf-8')
print('Android integration ready:', pkg)
print('Widget label: Planner')
print('Widget provider:', provider)
