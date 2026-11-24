# VYORA InnerTubeX migration

This patch migrates the latest source archive in the repository root to InnerTubeX v0.13.0 for audio stream extraction.

- Adds the InnerTubeX JitPack dependency and Ktor OkHttp engine.
- Replaces the yt-dlp resolver wiring while retaining the existing PlaybackStream model and Media3 player.
- Requests separate PO-token values for the player-request (videoId binding) and streaming-data (visitorData binding).
- Rejects SABR responses in this adapter rather than treating segmented transport as a direct URL.

## Build APK

Open **Actions → VYORA Android APK → Run workflow**. The workflow extracts `nexa-music-nov-21-2026-10-08-24-pm.zip`, applies the migration, and runs `:app:assembleDebug`. The resulting APK is uploaded as the `VYORA-debug-apk-innertubex` artifact.

This is a debug-signed APK. A production release needs a separately configured signing keystore; never commit signing keys or passwords.
