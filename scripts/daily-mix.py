#!/usr/bin/env python3
"""Generate a smart 200-track daily mix playlist.

Rules:
- Weighted by rating: 5★=5x, 4★=4x, 3★(default)=3x, 2★=2x, 1★=1x
- No two consecutive tracks from the same artist
- Tracks played ≥2 times in last 7 daily mixes → skip
- Today's YaM feed recs + LBZ recs go FIRST (fresh discovery)
- Output: /data/music/library/_playlists/daily-mix.m3u (Navidrome auto-scans)
"""

import json
import os
import random
import re
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

RECS_API = os.environ.get("RECS_API", "http://127.0.0.1:8765")
LIBRARY = Path(os.environ.get("LIBRARY", "/data/music/library"))
PLAYLISTS = LIBRARY / "_playlists"
NAVIDROME_DB = Path(os.environ.get("NAVIDROME_DB",
    str(Path.home() / "pr/life/navidrome/data/navidrome.db")))
USER_ID = os.environ.get("NAVIDROME_USER", "9ktbXSh5xbMSve5dg2pWCb")
TARGET_SIZE = int(os.environ.get("MIX_SIZE", "200"))
MAX_PLAYS_PER_WEEK = 2
HISTORY_DAYS = 7
MAX_TRACKS_PER_ARTIST = int(os.environ.get("MAX_TRACKS_PER_ARTIST", "2"))
# artist that appeared in recent mixes gets weight * ARTIST_PENALTY^count
ARTIST_PENALTY = float(os.environ.get("ARTIST_PENALTY", "0.4"))


def load_tracks_with_ratings() -> list[dict]:
    """Read all media files + their ratings from navidrome.db."""
    conn = sqlite3.connect(str(NAVIDROME_DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT m.id, m.path, m.title, m.artist, m.album, m.duration,
               COALESCE(a.rating, 0) as rating,
               COALESCE(a.starred, 0) as starred
        FROM media_file m
        LEFT JOIN annotation a ON a.item_id = m.id
            AND a.item_type = 'media_file'
            AND a.user_id = ?
        WHERE m.path NOT LIKE '_extras/%'
    """, (USER_ID,))
    tracks = [dict(row) for row in cur.fetchall()]
    conn.close()
    return tracks


def load_play_history() -> dict[str, int]:
    """Count how many times each track path appeared in last N daily mixes."""
    counts: dict[str, int] = {}
    today = date.today()
    for i in range(1, HISTORY_DAYS + 1):
        d = today - timedelta(days=i)
        path = PLAYLISTS / f"daily-mix-{d.isoformat()}.m3u"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                # strip ../ prefix
                clean = line.lstrip("./")
                counts[clean] = counts.get(clean, 0) + 1
    return counts


def load_recent_artist_counts() -> dict[str, int]:
    """Count how often each artist appeared in recent daily mixes (sum)."""
    counts: dict[str, int] = {}
    today = date.today()
    for i in range(1, HISTORY_DAYS + 1):
        d = today - timedelta(days=i)
        path = PLAYLISTS / f"daily-mix-{d.isoformat()}.m3u"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # path shape: ../Artist/Album/track.mp3
            parts = line.lstrip("./").split("/", 1)
            if parts:
                artist = parts[0]
                counts[artist] = counts.get(artist, 0) + 1
    return counts


def load_fresh_recs() -> list[str]:
    """Load today's YaM feed + LBZ playlist paths (if they exist)."""
    fresh: list[str] = []
    for name in ("lbz-daily-jams.m3u", "lbz-weekly-jams.m3u", "lbz-weekly-exploration.m3u"):
        p = PLAYLISTS / name
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    fresh.append(line.lstrip("./"))
    return fresh


def weighted_sample(
    tracks: list[dict],
    n: int,
    history: dict[str, int],
    recent_artists: dict[str, int] | None = None,
) -> list[dict]:
    """Weighted random sample: higher rating = more likely. Exclude overplayed.
    Enforces MAX_TRACKS_PER_ARTIST and penalizes artists seen in recent mixes."""
    recent_artists = recent_artists or {}
    eligible = []
    weights = []
    for t in tracks:
        path = t["path"]
        plays = history.get(path, 0)
        if plays >= MAX_PLAYS_PER_WEEK:
            continue
        rating = t["rating"] if t["rating"] > 0 else 3  # unrated = 3★
        w = rating * rating  # quadratic: 5★=25, 3★=9, 1★=1
        if t["starred"]:
            w *= 1.5
        # use path folder as the artist key (matches how history is indexed,
        # and avoids "Artist" vs "Artist feat X" splitting the same artist)
        t["_artist_key"] = path.split("/", 1)[0] if "/" in path else t["artist"]
        # dampen weight for artists that were prominent in recent mixes
        rc = recent_artists.get(t["_artist_key"], 0)
        if rc:
            w *= ARTIST_PENALTY ** min(rc, 10)
        eligible.append(t)
        weights.append(w)

    if not eligible:
        return []

    # weighted sampling without replacement, capped per artist
    selected: list[dict] = []
    per_artist: dict[str, int] = {}
    indices = list(range(len(eligible)))
    remaining_weights = list(weights)

    def drop(idx_in_list: int) -> None:
        indices.pop(idx_in_list)
        remaining_weights.pop(idx_in_list)

    while len(selected) < n and indices:
        total = sum(remaining_weights)
        if total <= 0:
            break
        r = random.uniform(0, total)
        cumulative = 0.0
        pick_idx = 0
        for j, w in enumerate(remaining_weights):
            cumulative += w
            if cumulative >= r:
                pick_idx = j
                break
        t = eligible[indices[pick_idx]]
        artist = t["_artist_key"]
        if per_artist.get(artist, 0) >= MAX_TRACKS_PER_ARTIST:
            # cap reached: drop ALL remaining tracks from this artist to speed up
            to_drop = [j for j in range(len(indices))
                       if eligible[indices[j]]["_artist_key"] == artist]
            for j in reversed(to_drop):
                drop(j)
            continue
        selected.append(t)
        per_artist[artist] = per_artist.get(artist, 0) + 1
        drop(pick_idx)
    return selected


def separate_artists(tracks: list[dict]) -> list[dict]:
    """Reorder so no two adjacent tracks share an artist."""
    if len(tracks) <= 1:
        return tracks
    result: list[dict] = []
    remaining = list(tracks)
    last_artist = None
    max_attempts = len(tracks) * 3

    for _ in range(max_attempts):
        if not remaining:
            break
        candidates = [t for t in remaining if t["artist"] != last_artist]
        if not candidates:
            candidates = remaining  # fallback
        pick = random.choice(candidates)
        result.append(pick)
        remaining.remove(pick)
        last_artist = pick["artist"]

    result.extend(remaining)  # anything left
    return result


def main() -> int:
    print(f"generating smart daily mix ({TARGET_SIZE} tracks)", file=sys.stderr)

    # 1. Load tracks + ratings
    all_tracks = load_tracks_with_ratings()
    print(f"  library: {len(all_tracks)} tracks", file=sys.stderr)
    rated = sum(1 for t in all_tracks if t["rating"] > 0)
    print(f"  rated: {rated}, unrated: {len(all_tracks) - rated}", file=sys.stderr)

    # 2. Load play history
    history = load_play_history()
    overplayed = sum(1 for v in history.values() if v >= MAX_PLAYS_PER_WEEK)
    print(f"  history: {len(history)} unique tracks in last {HISTORY_DAYS}d, {overplayed} overplayed", file=sys.stderr)
    recent_artists = load_recent_artist_counts()
    print(f"  recent artists: {len(recent_artists)} seen in last {HISTORY_DAYS}d", file=sys.stderr)

    # 3. Fresh recs (YaM + LBZ) → go first
    fresh_paths = set(load_fresh_recs())
    fresh_tracks = [t for t in all_tracks if t["path"] in fresh_paths]
    non_fresh = [t for t in all_tracks if t["path"] not in fresh_paths]
    print(f"  fresh recs (YaM+LBZ): {len(fresh_tracks)} tracks", file=sys.stderr)

    # 4. Weighted sample from non-fresh
    needed = TARGET_SIZE - len(fresh_tracks)
    sampled = weighted_sample(non_fresh, max(needed, 0), history, recent_artists)
    print(f"  weighted sample: {len(sampled)} tracks", file=sys.stderr)

    # 5. Combine: fresh first, then sampled
    combined = fresh_tracks + sampled

    # 6. Artist separation (within each section)
    fresh_separated = separate_artists(fresh_tracks)
    rest_separated = separate_artists(sampled)
    final = fresh_separated + rest_separated
    final = final[:TARGET_SIZE]

    # 7. Write m3u
    today = date.today().isoformat()
    lines = ["#EXTM3U", f"#PLAYLIST:Daily Mix {today}"]
    for t in final:
        lines.append(f"#EXTINF:{int(t.get('duration', -1))},{t['artist']} - {t['title']}")
        lines.append(f"../{t['path']}")

    PLAYLISTS.mkdir(parents=True, exist_ok=True)

    # save dated copy for history tracking
    dated = PLAYLISTS / f"daily-mix-{today}.m3u"
    dated.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # overwrite current for navidrome
    current = PLAYLISTS / "daily-mix.m3u"
    current.write_text("\n".join(lines) + "\n", encoding="utf-8")

    stars_dist = {}
    for t in final:
        r = t["rating"] if t["rating"] > 0 else 3
        stars_dist[f"{r}★"] = stars_dist.get(f"{r}★", 0) + 1

    print(f"\nwrote {len(final)} tracks → {current}", file=sys.stderr)
    print(f"  rating distribution: {stars_dist}", file=sys.stderr)
    unique_artists = len(set(t["artist"] for t in final))
    print(f"  unique artists: {unique_artists}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
