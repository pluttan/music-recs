#!/usr/bin/env python3
"""Delete tracks marked for removal from the music library.

Convention: a track marked **starred AND rated 1 star** is to be deleted.
This combo is unusual enough to never happen by accident — a casual 1-star
rating won't trigger removal.

For each match:
  - removes the audio file
  - drops the annotation row (so navidrome stops showing it on next scan)
  - removes empty parent directories (album, then artist)
  - logs to data/purged.log

Run via systemd timer, ~hourly.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

LIBRARY = Path(os.environ.get("LIBRARY", "/data/music/library"))
NAVIDROME_DB = Path(os.environ.get("NAVIDROME_DB",
    str(Path.home() / "pr/life/navidrome/data/navidrome.db")))
LOG = Path(os.environ.get("PURGE_LOG",
    str(Path.home() / "pr/life/music-recs/data/purged.log")))
DRY_RUN = bool(int(os.environ.get("DRY_RUN", "0")))


def find_to_delete(conn) -> list[tuple[str, str, str]]:
    """Return [(media_id, user_id, path), ...] of tracks to purge."""
    cur = conn.cursor()
    cur.execute("""
        SELECT m.id, a.user_id, m.path
        FROM media_file m
        JOIN annotation a
          ON a.item_id = m.id
         AND a.item_type = 'media_file'
        WHERE a.rating = 1 AND a.starred = 1
    """)
    return cur.fetchall()


def remove_track(media_id: str, user_id: str, rel_path: str, conn) -> tuple[bool, str]:
    abs_path = LIBRARY / rel_path
    note = []

    if abs_path.exists():
        if not DRY_RUN:
            abs_path.unlink()
        note.append(f"removed file: {abs_path}")
    else:
        note.append(f"file already gone: {abs_path}")

    # walk up: remove album dir if empty, then artist dir
    parent = abs_path.parent
    for _ in range(2):
        if parent.exists() and parent != LIBRARY and not any(parent.iterdir()):
            if not DRY_RUN:
                parent.rmdir()
            note.append(f"removed empty dir: {parent}")
            parent = parent.parent
        else:
            break

    if not DRY_RUN:
        conn.execute(
            "DELETE FROM annotation WHERE item_id = ? AND user_id = ? AND item_type='media_file'",
            (media_id, user_id),
        )
    note.append(f"dropped annotation (id={media_id})")
    return True, " | ".join(note)


def main() -> int:
    if not NAVIDROME_DB.exists():
        print(f"navidrome db not found: {NAVIDROME_DB}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(NAVIDROME_DB))
    conn.row_factory = sqlite3.Row

    rows = find_to_delete(conn)
    if not rows:
        print("nothing to purge", file=sys.stderr)
        conn.close()
        return 0

    print(f"found {len(rows)} tracks marked for deletion (rating=1 + starred)", file=sys.stderr)
    LOG.parent.mkdir(parents=True, exist_ok=True)

    with LOG.open("a", encoding="utf-8") as logf:
        ts = datetime.now().isoformat(timespec="seconds")
        logf.write(f"\n=== {ts} ({'DRY-RUN ' if DRY_RUN else ''}purge {len(rows)} tracks) ===\n")
        for media_id, user_id, rel_path in rows:
            ok, note = remove_track(media_id, user_id, rel_path, conn)
            line = f"  {rel_path} :: {note}"
            print(line, file=sys.stderr)
            logf.write(line + "\n")

    if not DRY_RUN:
        conn.commit()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
