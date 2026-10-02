#!/usr/bin/env sh
set -eu
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
flutter create --platforms=android --org com.plannersuite --project-name planner_suite "$TMP/scaffold"
rm -rf "$HERE/android"
cp -R "$TMP/scaffold/android" "$HERE/android"
python3 "$HERE/tool/prepare_android.py" "$HERE/android"
cd "$HERE"
flutter pub get
flutter build apk --release --dart-define=API_BASE_URL=https://planner.datholding.ir/api
