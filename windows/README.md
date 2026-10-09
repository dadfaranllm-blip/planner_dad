# Windows client
The Windows client uses the same authenticated Backend API and central PostgreSQL source of truth as Web/Mobile. Local storage is cache-only. A production Flutter Windows shell can reuse the mobile domain/API layer; Windows build artifacts require the Windows Flutter/MSVC toolchain and are not included as precompiled binaries in this source release.
