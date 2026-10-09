#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
required="settings.gradle build.gradle gradle.properties gradlew gradlew.bat gradle/wrapper/gradle-wrapper.properties app/build.gradle app/proguard-rules.pro app/src/main/AndroidManifest.xml app/src/main/kotlin/com/plannersuite/app/MainActivity.kt app/src/main/kotlin/com/plannersuite/app/PlannerWidgetProvider.kt app/src/main/kotlin/com/plannersuite/app/PlannerWidgetService.kt app/src/main/res/layout/planner_widget.xml app/src/main/res/layout/widget_row.xml app/src/main/res/xml/planner_widget_info.xml app/src/main/res/values/styles.xml"
for f in $required; do [ -f "$f" ] || { echo "MISSING: $f"; exit 1; }; done
echo "Android structure OK"
