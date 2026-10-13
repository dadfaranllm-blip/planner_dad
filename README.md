# Planner Android 1.6.0+18

This release adds verified registration, profiles and a more capable chat/workspace experience.

## Account
- Sign up from the login screen.
- Email or phone registration, depending on the Admin setting.
- Mandatory one-time verification code before activation.
- Secure login fields with unwanted autofill/suggestions disabled for identity/name fields.
- Profile page: display name, first/last name, phone and avatar URL.

## Collaboration & chat
- Workspace members can use shared board/documents; backend 1.7 also exposes shared item and room-chat APIs.
- Direct chat polls every 2 seconds and includes typing, reply, edit/delete, seen and message search.

## Build
Use `.github/workflows/android-build.yml` (`Planner Android Build 1.6.0`).
