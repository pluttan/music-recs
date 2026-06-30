#!/usr/bin/env python3
"""Assemble a 'work' playlist from all instrumental _extras tracks.

Covers _extras/lofi/ + _extras/piano/, skips _extras/geo/ (documentaries
are too long for background work). Shuffles within each category so the
vibe doesn't cluster by channel.

Output: /data/music/library/_playlists/work.m3u — navidrome auto-scans it.
"""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path

LIBRARY = Path(os.environ.get("LIBRARY", "/data/music/library"))
PLAYLISTS = LIBRARY / "_playlists"
OUT = PLAYLISTS / "work.m3u"

SOURCES = ["_extras/lofi", "_extras/piano"]


def gather() -> list[Path]:
    files: list[Path] = []
    for sub in SOURCES:
        root = LIBRARY / sub
        if not root.exists():
            continue
        files.extend(sorted(root.rglob("*.opus")))
    return files


def main() -> int:
    files = gather()
    if not files:
        print("no files found", file=sys.stderr)
        return 1

    random.seed()
    random.shuffle(files)

    PLAYLISTS.mkdir(parents=True, exist_ok=True)
    lines = ["#EXTM3U", "#PLAYLIST:Work"]
    for p in files:
        rel = p.relative_to(LIBRARY)
        name = p.stem
        lines.append(f"#EXTINF:-1,{name}")
        lines.append(f"../{rel}")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(files)} tracks → {OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
