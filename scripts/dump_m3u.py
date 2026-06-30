#!/usr/bin/env python3
"""Dump .m3u playlists into Navidrome library based on recs API.

Generates:
  <library>/_playlists/radio-<artist>.m3u        — per-top-artist radio
  <library>/_playlists/mood-<mood>.m3u           — per mood
  <library>/_playlists/discover-weekly.m3u       — long cross-genre mix

Run via cron on the host that owns the Navidrome library.
"""

import argparse
import os
import sys
from pathlib import Path
from urllib.request import urlopen
import json


def fetch(api_base: str, path: str) -> list[dict]:
    url = f"{api_base.rstrip('/')}{path}"
    with urlopen(url, timeout=10) as resp:
        return json.load(resp)


def write_m3u(dest: Path, library_root: Path, entries: list[dict], title: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = ["#EXTM3U", f"#PLAYLIST:{title}"]
    for e in entries:
        duration = int(e.get("duration") or -1)
        name = f"{e.get('artist','?')} - {e.get('title','?')}"
        lines.append(f"#EXTINF:{duration},{name}")
        # navidrome reads paths relative to the music library root
        lines.append(e["path"])
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[ok] wrote {dest} ({len(entries)} tracks)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default=os.environ.get("RECS_API", "http://127.0.0.1:8765"))
    ap.add_argument("--library", type=Path, default=Path("/data/music/library"))
    ap.add_argument("--top-artists", type=int, default=10)
    args = ap.parse_args()

    out_dir = args.library / "_playlists"

    # mood playlists
    for mood in ["happy", "sad", "relaxed", "aggressive", "party", "electronic", "acoustic"]:
        try:
            entries = fetch(args.api, f"/mood/{mood}?n=40")
            if entries:
                write_m3u(out_dir / f"mood-{mood}.m3u", args.library, entries, f"Mood: {mood}")
        except Exception as e:
            print(f"[warn] mood {mood}: {e}", file=sys.stderr)

    # TODO: top-artist radios — need `/top-artists` endpoint or SQL query

    print(f"[done] playlists in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
