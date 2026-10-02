# Planner Android 1.3.0

Version: **1.3.0+15**

## Main changes
- New professional Settings screen.
- Widget management moved to Settings.
- Four native Android home-screen widgets:
  1. Planner Overview
  2. Large Clock & Persian Date
  3. Upcoming Tasks
  4. Agenda / Upcoming Events
- Each widget has its own AppWidgetProvider and can be pinned independently.
- Persian calendar is explicitly RTL: Saturday at the far right through Friday at the far left.
- Workspace document collaboration upgraded:
  - 700ms autosave debounce
  - remote revision polling every 2 seconds
  - non-overlapping concurrent edits are merged by the backend
  - overlapping edits show a conflict resolver instead of losing either user's text
- App security hardening:
  - login token encrypted with AES-GCM using Android Keystore
  - token is no longer stored as plaintext in Flutter SharedPreferences
  - cleartext HTTP disabled
  - Android app backup disabled
- UI refresh: professional dashboard hero, card system, spacing, settings previews and clearer collaborative sync state.

## Server requirement
Collaborative merge requires the companion `planner-server-collaboration-1.3.0.zip` backend update.

## GitHub Actions
Use `.github/workflows/android-build.yml` (Planner Android Build 1.3.0). It verifies all four widget providers, Keystore integration and the final APK manifest.
