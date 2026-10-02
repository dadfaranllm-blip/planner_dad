# Planner Android 1.2.3 Secure

This is the complete Android repository package.

## Important
Do not upload the ZIP itself into the repository. Extract it first and replace the repository contents with the extracted files. Use only `.github/workflows/android-build.yml`; its visible Actions name is `Planner Android Build 1.2.3 Secure`.

## What must be visible after installing the correct APK
- Today page shows `نسخه 1.2.3+14 • Secure Token Storage`.
- Persian calendar has Saturday on the far right and Friday on the far left.
- Today page has `کار جدید` and `رویداد جدید`.
- Workspace is present in bottom navigation.
- Today page has `افزودن ویجت Planner به صفحه اصلی`.

## Build artifacts
- `Planner-Android-APK-1.2.3-Secure`
- `Planner-Android-AAB-1.2.3-Secure`
- `Planner-Build-Proof-1.2.3`

The proof artifact contains the final merged Android manifest, APK SHA256 and signing certificate details. The workflow fails if the final APK does not contain version 1.2.3 / code 14, PlannerWidgetProvider, cleartext blocking and backup blocking.

See `SECURITY.md` for security notes.
