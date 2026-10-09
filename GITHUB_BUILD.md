# GitHub Android Build

GitHub Actions only starts workflows stored at the repository root under `.github/workflows/`.

This project includes `.github/workflows/android-build.yml`.

## Expected repository layout

```
.github/workflows/android-build.yml
mobile/pubspec.yaml
mobile/lib/
mobile/android/
backend/
web/
```

Push to `main` or `master`, or open **Actions → Build Android APK → Run workflow**.

The generated APK is available at the bottom of the successful workflow run under **Artifacts**.

Firebase secrets are optional for compilation but required for working push notifications. Add them in **Settings → Secrets and variables → Actions**:

- `FIREBASE_ANDROID_API_KEY`
- `FIREBASE_ANDROID_APP_ID`
- `FIREBASE_MESSAGING_SENDER_ID`
- `FIREBASE_PROJECT_ID`

Release signing is currently allowed to fall back to the debug key so CI can produce an installable test APK. Before publishing to Google Play, configure a private release keystore and remove the debug-signing fallback.
