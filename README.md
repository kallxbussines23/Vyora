# VYORA

VYORA is an Android music discovery and playback app.

## Data and playback architecture

- **Metadata and discovery:** YouTube Music InnerTube. This supplies search, home feeds, artists, albums, playlists, artwork, and track metadata.
- **Audio URL extraction:** yt-dlp only, through the Android yt-dlp runtime. InnerTube Player responses are not used to resolve audio URLs.
- **PO token:** the in-app BotGuard WebView provider generates a session-bound Web PO token from the current InnerTube `visitorData`; yt-dlp receives it as an `mweb` GVS token.
- **Playback:** AndroidX Media3 ExoPlayer handles streaming, queue, background playback, and media notifications.

There are no Piped or Invidious playback fallbacks. If yt-dlp or BotGuard cannot resolve a stream, playback reports the extraction error rather than silently switching to another audio source.

## Build

Open the project in Android Studio and allow Gradle sync to complete. The project uses Android SDK 36 and requires the Android NDK/native runtime artifacts brought in by the yt-dlp Android dependency. The app's package ID is `com.vyorasound.app`.

## Notes

- YouTube's InnerTube and BotGuard interfaces are undocumented and may change. PO token generation is best-effort and does not guarantee that YouTube will serve every stream or remove all bot checks.
- The `youtubedl-android` runtime is distributed under GPL-3.0. Review its license obligations before redistributing builds.
- Use the app only for content you are authorized to access and play, and follow the applicable YouTube terms.
