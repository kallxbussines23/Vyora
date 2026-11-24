package com.vyorasound.app.repository

import com.metrolist.innertubex.InnerTube
import com.metrolist.innertubex.cipher.PlayerConfigRepository
import com.metrolist.innertubex.cipher.RemotePlayerConfigStore
import com.metrolist.innertubex.cipher.YouTubeCipherService
import com.metrolist.innertubex.extraction.AudioQuality
import com.metrolist.innertubex.extraction.ContentHints
import com.metrolist.innertubex.extraction.InnerTubeExtractor
import com.metrolist.innertubex.extraction.YtConfigParserImpl
import com.vyorasound.app.domain.model.PlaybackStream
import io.ktor.client.HttpClient
import io.ktor.client.engine.okhttp.OkHttp
import java.io.IOException
import kotlin.time.Clock
import kotlin.time.Duration.Companion.minutes

object InnerTubeXStreamResolver {
    @Volatile private var runtime: Runtime? = null

    @Synchronized
    fun initialize() {
        if (runtime != null) return
        val httpClient = HttpClient(OkHttp) { expectSuccess = false }
        val innerTube = InnerTube(httpClient)
        val configStore = RemotePlayerConfigStore(httpClient, PlayerConfigRepository.disabled())
        val cipherService = YouTubeCipherService(httpClient, configStore)
        val parser = YtConfigParserImpl(
            httpClient = httpClient,
            innerTube = innerTube,
            remotePlayerConfigStore = configStore,
            cipherService = cipherService
        )
        val extractor = InnerTubeExtractor(
            configParser = parser,
            cipherService = cipherService,
            innerTube = innerTube
        )
        runtime = Runtime(httpClient, innerTube, cipherService, extractor)
    }

    suspend fun resolve(videoId: String): PlaybackStream {
        require(videoId.matches(Regex("[A-Za-z0-9_-]{11}"))) { "Invalid YouTube video ID" }
        val active = runtime ?: synchronized(this) {
            runtime ?: run { initialize(); checkNotNull(runtime) }
        }
        val stream = active.extractor.extract(
            videoId = videoId,
            hints = ContentHints(wantVideo = false).withStreamCapabilities(
                allowHls = false, allowSabr = false,
                allowBoundedRange = false, allowProgressive = false
            ),
            audioQuality = AudioQuality.AUTO
        ) ?: throw IOException("InnerTubeX returned no playable audio stream")

        val parsed = runCatching { java.net.URI(stream.audioUrl) }.getOrNull()
        if (parsed == null || parsed.scheme !in setOf("https", "http") || parsed.host.isNullOrBlank()) {
            throw IOException("InnerTubeX returned an invalid audio URL")
        }
        val userAgent = stream.headers.entries
            .firstOrNull { it.key.equals("User-Agent", ignoreCase = true) }?.value
            .orEmpty().ifBlank { "com.google.android.youtube/20.10.38 (Linux; U; Android 13)" }
        val mime = if (stream.codecs.isNullOrBlank()) stream.mimeType.orEmpty()
            else stream.mimeType.orEmpty() + "; codecs=\"" + stream.codecs + "\""
        val expiry = stream.expiresAt?.toEpochMilliseconds()
            ?: (Clock.System.now() + 5.minutes).toEpochMilliseconds()

        return PlaybackStream(
            videoId = videoId,
            streamUrl = stream.audioUrl,
            mimeType = mime,
            bitrate = stream.bitrate ?: 0,
            userAgent = userAgent,
            expiresAtMs = expiry,
            isHls = false,
            itag = stream.itag,
            codecs = stream.codecs,
            contentLength = stream.contentLengthBytes,
            clientName = "INNERTUBEX_" + stream.clientName,
            requestHeaders = stream.headers
        )
    }

    private data class Runtime(
        val httpClient: HttpClient,
        val innerTube: InnerTube,
        val cipherService: YouTubeCipherService,
        val extractor: InnerTubeExtractor
    )
}
