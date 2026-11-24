#!/usr/bin/env python3
from __future__ import annotations
import argparse
import shutil
from pathlib import Path

def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text: return text
    if old not in text: raise SystemExit("Migration stopped: expected " + label + " anchor was not found")
    return text.replace(old, new, 1)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--resolver-source", required=True, type=Path)
    args = parser.parse_args()
    root = args.source_root.resolve()
    app = root / "app"
    if not (app / "build.gradle.kts").is_file() or not (root / "settings.gradle.kts").is_file():
        raise SystemExit("Migration stopped: VYORA Gradle project root was not found")

    gradle_file = app / "build.gradle.kts"
    gradle = replace_once(gradle_file.read_text(encoding="utf-8"), "dependencies {",
        'dependencies {\n  implementation("com.github.MetrolistGroup.innertubex:innertubex:v0.13.0")\n  implementation("io.ktor:ktor-client-okhttp:3.6.0")',
        "app dependencies block")
    gradle_file.write_text(gradle, encoding="utf-8")

    settings_file = root / "settings.gradle.kts"
    settings = replace_once(settings_file.read_text(encoding="utf-8"),
        "    mavenCentral()\n  }\n}\n\nrootProject.name",
        '    mavenCentral()\n    maven("https://jitpack.io") {\n      content {\n        includeGroup("com.github.MetrolistGroup.innertubex")\n        includeGroup("com.github.MetrolistGroup.quackjs")\n      }\n    }\n  }\n}\n\nrootProject.name',
        "dependency repository block")
    settings_file.write_text(settings, encoding="utf-8")

    package = app / "src/main/java/com/vyorasound/app"
    repo_file = package / "repository/InnerTubeMusicRepository.kt"
    model_file = package / "domain/model/MusicModels.kt"
    app_file = package / "VyoraApplication.kt"
    service_file = package / "service/PlaybackService.kt"
    for path in (repo_file, model_file, app_file, service_file):
        if not path.is_file(): raise SystemExit("Migration stopped: required source file missing: " + str(path.relative_to(root)))

    resolver_dest = package / "repository/InnerTubeXStreamResolver.kt"
    resolver_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.resolver_source, resolver_dest)

    model = replace_once(model_file.read_text(encoding="utf-8"),
        '    val clientName: String = "UNKNOWN"\n)',
        '    val clientName: String = "UNKNOWN",\n    val requestHeaders: Map<String, String> = emptyMap()\n)',
        "PlaybackStream model")
    model_file.write_text(model, encoding="utf-8")

    repo = replace_once(repo_file.read_text(encoding="utf-8"),
        '.header("User-Agent", stream.userAgent)\n                .get()',
        '.apply { stream.requestHeaders.forEach { (name, value) -> header(name, value) } }\n                .header("User-Agent", stream.userAgent)\n                .get()',
        "stream probe headers")
    repo = replace_once(repo,
        '            ensureVisitorData()\n            ensureNativeVisitorData()',
        '''            // InnerTubeX is primary; existing InnerTube and public-relay paths remain fallbacks.
            val innerTubeXStream = runCatching { InnerTubeXStreamResolver.resolve(videoId) }
                .onFailure { error ->
                    PlaybackDiagnostics.w("InnerTubeXResolveFailed | videoId=" + videoId + " | reason=" + (error.message ?: "unknown"))
                }.getOrNull()
            if (innerTubeXStream != null) {
                val probe = streamProber.probe(innerTubeXStream)
                PlaybackDiagnostics.i("InnerTubeXStreamProbe | videoId=" + videoId + " | client=" +
                    innerTubeXStream.clientName + " | status=" + probe.httpStatus + " | playable=" + probe.isPlayable)
                if (probe.isPlayable) {
                    streamCache.put(videoId, innerTubeXStream)
                    return@withContext Result.success(innerTubeXStream)
                }
            }
            ensureVisitorData()
            ensureNativeVisitorData()''',
        "playback resolver insertion point")
    repo_file.write_text(repo, encoding="utf-8")

    application = replace_once(app_file.read_text(encoding="utf-8"),
        "        super.onCreate()\n        container = AppContainer(this)",
        "        super.onCreate()\n        InnerTubeXStreamResolver.initialize()\n        container = AppContainer(this)",
        "application startup")
    if "import com.vyorasound.app.repository.InnerTubeXStreamResolver" not in application:
        application = application.replace(
            "import com.vyorasound.app.repository.InnerTubeMusicRepository",
            "import com.vyorasound.app.repository.InnerTubeMusicRepository\nimport com.vyorasound.app.repository.InnerTubeXStreamResolver")
    app_file.write_text(application, encoding="utf-8")

    service = replace_once(service_file.read_text(encoding="utf-8"),
        '                        val headers = HashMap(dataSpec.httpRequestHeaders).apply {\n                            put("User-Agent", stream.userAgent)\n                        }',
        '                        val headers = HashMap(dataSpec.httpRequestHeaders).apply {\n                            putAll(stream.requestHeaders)\n                            put("User-Agent", stream.userAgent)\n                        }',
        "Media3 request headers")
    service_file.write_text(service, encoding="utf-8")
    print("InnerTubeX is now the primary VYORA playback resolver; legacy fallbacks are preserved.")

if __name__ == "__main__":
    main()
