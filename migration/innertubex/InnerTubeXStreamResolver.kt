package com.vyorasound.app.repository

import android.content.Context
import com.metrolist.innertube.InnerTube
import com.metrolist.innertubex.InnerTubeLogger
import com.metrolist.innertubex.cipher.PlayerConfigRepository
import com.metrolist.innertubex.cipher.RemotePlayerConfigStore
import com.metrolist.innertubex.cipher.YouTubeCipherService
import com.metrolist.innertubex.extraction.AudioQuality
import com.metrolist.innertubex.extraction.ContentHints
import com.metrolist.innertubex.extraction.InnerTubeExtractor
import com.metrolist.innertubex.extraction.PoTokenResult
import com.metrolist.innertubex.extraction.TokenProvider
import com.metrolist.innertubex.extraction.TokenProviderCapabilities
import com.metrolist.innertubex.extraction.YtConfigParserImpl
import com.metrolist.innertubex.extraction.strategy.PoTokenProviderKind
import com.vyorasound.app.domain.model.PlaybackStream
import com.vyorasound.app.network.PoTokenService
import io.ktor.client.HttpClient
import io.ktor.client.engine.okhttp.OkHttp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.IOException

/** InnerTubeX resolves direct audio URLs; Media3 remains the playback engine. */
class InnerTubeXStreamResolver(
    context: Context,
    private val poTokenService: PoTokenService,
) : AudioStreamResolver {
    private val appContext = context.applicationContext
    private val initMutex = Mutex()
    @Volatile private var runtime: Runtime? = null
    private val logger = InnerTubeLogger { _ -> }

    override suspend fun resolve(videoId: String, visitorData: String): PlaybackStream =
        withContext(Dispatchers.IO) {
            require(videoId.isNotBlank()) { "Missing YouTube video ID" }
            require(visitorData.isNotBlank()) { "Missing YouTube visitor data" }

            val stream = requireNotNull(getRuntime().extractor.extract(
                videoId = videoId,
                hints = ContentHints(wantVideo = false),
                audioQuality = AudioQuality.HIGH,
            )) { "InnerTubeX returned no playable audio stream" }

            // The current Media3 adapter consumes direct URLs, not SABR segments.
            if (stream.sabrBootstrap != null) {
                throw IOException("InnerTubeX selected SABR; this Media3 adapter requires a direct stream")
            }
            val url = stream.audioUrl.takeIf { it.startsWith("https://") }
                ?: throw IOException("InnerTubeX returned no valid HTTPS audio URL")
            val mime = stream.mimeType.orEmpty().ifBlank { "application/octet-stream" }
            val headers = stream.headers
            val userAgent = headers.entries.firstOrNull {
                it.key.equals("User-Agent", ignoreCase = true)
            }?.value?.takeIf { it.isNotBlank() }
                ?: "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/134.0.0.0 Mobile Safari/537.36"

            PlaybackStream(
                videoId = videoId,
                streamUrl = url,
                mimeType = mime,
                bitrate = stream.bitrate ?: 0,
                userAgent = userAgent,
                expiresAtMs = stream.expiresAt?.toEpochMilliseconds()
                    ?: (System.currentTimeMillis() + 300_000L),
                isHls = mime.contains("mpegurl", ignoreCase = true) ||
                    url.contains(".m3u8", ignoreCase = true),
                itag = stream.itag,
                codecs = stream.codecs,
                audioQuality = "HIGH",
                contentLength = stream.contentLengthBytes,
                clientName = "innertubex-" + stream.clientName,
                originHeader = headers.entries.firstOrNull {
                    it.key.equals("Origin", ignoreCase = true)
                }?.value,
                httpHeaders = headers,
            )
        }

    private suspend fun getRuntime(): Runtime {
        runtime?.let { return it }
        return initMutex.withLock {
            runtime?.let { return@withLock it }

            val http = HttpClient(OkHttp)
            val innerTube = InnerTube(httpClient = http)
            val configStore = RemotePlayerConfigStore(
                httpClient = http,
                repository = PlayerConfigRepository.disabled(),
                logger = logger,
            )
            val cipher = YouTubeCipherService(http, configStore, logger)
            val tokenProvider = object : TokenProvider {
                override val capabilities = TokenProviderCapabilities(
                    providers = setOf(PoTokenProviderKind.WEB_BOTGUARD),
                    usesWebView = true,
                )

                override suspend fun getPoToken(
                    videoId: String,
                    visitorData: String,
                    cookie: String?,
                ): PoTokenResult? {
                    // The two token fields have different bindings; never reuse one value.
                    val playerToken = poTokenService.obtainPoToken(videoId) ?: return null
                    val streamToken = poTokenService.obtainPoToken(visitorData) ?: return null
                    return PoTokenResult(
                        playerRequestToken = playerToken,
                        streamingDataToken = streamToken,
                        visitorData = visitorData,
                    )
                }

                override suspend fun close() = Unit
            }
            val extractor = InnerTubeExtractor(
                configParser = YtConfigParserImpl(http, innerTube, configStore, logger),
                cipherService = cipher,
                innerTube = innerTube,
                tokenProvider = tokenProvider,
                logger = logger,
            )
            Runtime(http, innerTube, extractor).also { runtime = it }
        }
    }

    private data class Runtime(
        val http: HttpClient,
        val innerTube: InnerTube,
        val extractor: InnerTubeExtractor,
    )
}
