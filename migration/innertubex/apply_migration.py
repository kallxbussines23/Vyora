#!/usr/bin/env python3
"""Apply the VYORA InnerTubeX playback migration to the latest source archive."""
from __future__ import annotations
import argparse
import re
import shutil
from pathlib import Path


def find_project_root(path: Path) -> Path:
    candidates = [path] + [p for p in path.rglob("app/build.gradle.kts")]
    for candidate in candidates:
        root = candidate.parent.parent if candidate.name == "build.gradle.kts" and candidate.parent.name == "app" else candidate
        if (root / "app/build.gradle.kts").is_file() and (root / "settings.gradle.kts").is_file():
            return root
    raise SystemExit("Could not locate Android project")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"Migration stopped: could not find {label} anchor")
    return text.replace(old, new, 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--resolver-source", required=True, type=Path)
    args = parser.parse_args()
    root = find_project_root(args.source_root.resolve())

    gradle_file = root / "app/build.gradle.kts"
    gradle = gradle_file.read_text(encoding="utf-8")
    gradle = re.sub(r"^\s*// Bundled yt-dlp.*\n\s*implementation\(\"io.github.junkfood02.youtubedl-android:library:[^\"]+\"\)\s*\n", "\n", gradle, flags=re.M)
    gradle = replace_once(gradle, "dependencies {\n", 'dependencies {\n  implementation("com.github.MetrolistGroup.innertubex:innertubex:v0.13.0")\n  implementation("io.ktor:ktor-client-okhttp:3.3.3")\n', "app dependencies")
    gradle_file.write_text(gradle, encoding="utf-8")

    settings_file = root / "settings.gradle.kts"
    settings = settings_file.read_text(encoding="utf-8")
    settings = replace_once(settings, "    mavenCentral()\n", '    mavenCentral()\n    maven("https://jitpack.io") {\n      content { includeGroup("com.github.MetrolistGroup.innertubex") }\n    }\n", "dependency repositories")
    settings_file.write_text(settings, encoding="utf-8")

    app_file = root / "app/src/main/java/com/vyorasound/app/VyoraApplication.kt"
    app = app_file.read_text(encoding="utf-8")
    app = replace_once(app, "import com.vyorasound.app.repository.YtDlpStreamResolver", "import com.vyorasound.app.repository.InnerTubeXStreamResolver", "resolver import")
    app = replace_once(app, "val ytDlpStreamResolver: YtDlpStreamResolver by lazy {\n        YtDlpStreamResolver(application.applicationContext, poTokenService)\n    }", "val innerTubeXStreamResolver: InnerTubeXStreamResolver by lazy {\n        InnerTubeXStreamResolver(application.applicationContext, poTokenService)\n    }", "resolver dependency")
    app = replace_once(app, "ytDlpStreamResolver = ytDlpStreamResolver", "ytDlpStreamResolver = innerTubeXStreamResolver", "repository resolver injection")
    app_file.write_text(app, encoding="utf-8")

    old = root / "app/src/main/java/com/vyorasound/app/repository/YtDlpStreamResolver.kt"
    old.write_text("package com.vyorasound.app.repository\n\nfun interface AudioStreamResolver {\n    suspend fun resolve(videoId: String, visitorData: String): com.vyorasound.app.domain.model.PlaybackStream\n}\n", encoding="utf-8")

    shutil.copy2(args.resolver_source, root / "app/src/main/java/com/vyorasound/app/repository/InnerTubeXStreamResolver.kt")
    print("InnerTubeX migration applied")

if __name__ == "__main__":
    main()