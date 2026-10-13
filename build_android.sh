#!/usr/bin/env sh
set -eu
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
flutter create --platforms=android --org com.plannersuite --project-name planner_suite "$TMP/scaffold"
rm -rf "$HERE/android"
cp -R "$TMP/scaffold/android" "$HERE/android"
python3 "$HERE/tool/prepare_android.py" "$HERE/android"
sed -i -E 's#gradle-[0-9.]+-bin.zip#gradle-8.14.3-bin.zip#' "$HERE/android/gradle/wrapper/gradle-wrapper.properties"
cd "$HERE"
flutter pub get
flutter build apk --debug --dart-define=API_BASE_URL=https://planner.datholding.ir/api
