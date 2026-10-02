# Planner Android 1.2.3 Security

Implemented in this package:

- Session token is no longer stored in Flutter SharedPreferences.
- Session token is encrypted with AES-GCM using an Android Keystore-backed key.
- Widget background refresh reads the encrypted token through SecureTokenStore; it does not keep a plaintext token in widget preferences.
- Cleartext HTTP is blocked in AndroidManifest and network_security_config.
- Android backup is disabled for app/session data.
- API calls require HTTPS in production and are restricted to planner.datholding.ir unless an explicit local insecure build flag is used.
- API requests have finite connect/read behavior at the Dart layer and do not follow redirects automatically.
- OAuth authorization URLs must use HTTPS.
- PendingIntents used by the widget are immutable.
- Release workflow verifies the final APK manifest for version, widget provider, cleartext blocking, and backup blocking.
- Release workflow emits the final APK certificate information and SHA256 in Planner-Build-Proof-1.2.3.

Remaining hardening item requiring backend coordination:

- OAuth currently supports receiving an oauth_token through the custom planner:// callback because that is the server flow currently exposed. A one-time authorization code exchanged inside the app is preferable to placing a bearer token in a callback URI. The Android app is ready to move to that model when the backend callback is changed.

Release signing:

The build proof prints the APK signing certificate. Before public distribution, use a persistent private release keystore stored in GitHub encrypted secrets. Do not publish an APK signed with the Android debug certificate.
