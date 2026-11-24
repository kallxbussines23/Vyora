#!/usr/bin/env python3
"""Apply VYORA's InnerTubeX playback patch to the checked-in source archive."""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


def find_project_root(path: Path) -> Path:
    for build_file in [path / "app/build.gradle.kts", *path.rglob("app/build.gradle.kts")]:
        root = build_file.parent.parent
        if (root / "settings.gradle.kts").is_file():
            return root
    raise SystemExit("Could not locate app/build.gradle.kts and settings.gradle.kts")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit("Migration stopped: expected " + label + " anchor was not found")
    return text.replace(old, new, 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--resolver-source", required=True, type=Path)
    args = parser.parse_args()
    root = find_project_root(args.source_root.resolve())

    gradle_file = root / "app/build.gradle.kts"
    gradle = gradle_file.read_text(encoding="utf-8")
    gradle = re.sub(r'^\s*// Bundled yt-dlp[^\n]*\n', "", gradle, flags=re.M)
    gradle = re.sub(
        r'^\s*implementation\("io\.github\.junkfood02\.youtubedl-android:library:[^"]+"\)\s*\n',
        "",
        gradle,
        flags=re.M,
    )
    if "com.github.MetrolistGroup.innertubex:innertubex:v0.13.0" not in gradle:
        gradle = replace_once(
            gradle,
            "dependencies {\n",
            'dependencies {\n  implementation("com.github.MetrolistGroup.innertubex:innertubex:v0.13.0")\n  implementation("io.ktor:ktor-client-okhttp:3.3.3")\n',
            "app dependencies",
        )
    gradle_file.write_text(gradle, encoding="utf-8")

    settings_file = root / "settings.gradle.kts"
    settings = settings_file.read_text(encoding="utf-8")
    if 'maven("https://jitpack.io")' not in settings:
        settings = replace_once(
            settings,
            "    mavenCentral()\n",
            '    mavenCentral()\n    maven("https://jitpack.io") {\n      content { includeGroup("com.github.MetrolistGroup.innertubex") }\n    }\n',
            "dependency repositories",
        )
    settings_file.write_text(settings, encoding="utf-8")

    # Source snapshots vary slightly in import order and whitespace. Rename the
    # old resolver symbol wherever it is referenced instead of relying on one
    # exact import block.
    touched = []
    for kotlin_file in root.rglob("*.kt"):
        source = kotlin_file.read_text(encoding="utf-8")
        if "YtDlpStreamResolver" in source:
            kotlin_file.write_text(
                source.replace("YtDlpStreamResolver", "InnerTubeXStreamResolver"),
                encoding="utf-8",
            )
            touched.append(str(kotlin_file.relative_to(root)))
    if not touched:
        raise SystemExit("Migration stopped: no Kotlin reference to YtDlpStreamResolver was found")

    old_resolver = root / "app/src/main/java/com/vyorasound/app/repository/YtDlpStreamResolver.kt"
    old_resolver.write_text(
        """package com.vyorasound.app.repository

fun interface AudioStreamResolver {
    suspend fun resolve(
        videoId: String,
        visitorData: String,
    ): com.vyorasound.app.domain.model.PlaybackStream
}
""",
        encoding="utf-8",
    )

    destination = root / "app/src/main/java/com/vyorasound/app/repository/InnerTubeXStreamResolver.kt"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.resolver_source, destination)
    print("InnerTubeX migration applied to " + str(root))
    print("Updated Kotlin references: " + ", ".join(touched))


if __name__ == "__main__":
    main()
