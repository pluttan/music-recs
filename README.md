<div align="center">

# music-recs

**Self-hosted audio-based music recommendations with MusiCNN embeddings**


</div>

Self-hosted music recommendation pipeline that runs alongside a Navidrome library. Extracts real audio features (BPM, key, loudness, energy, danceability, mood) and 200-dimensional MusiCNN embeddings from every track, stores them in pgvector, and serves similarity/radio/mood endpoints. Systemd timers dump `.m3u` playlists into the Navidrome library so any Subsonic client sees them as regular playlists.

## ■ Features

- ❖ **Audio-based similarity** — cosine-distance KNN on 200-dim MusiCNN embeddings, not metadata
- ❖ **Feature extraction** — BPM, key, loudness, energy, danceability, mood via essentia-tensorflow
- ❖ **pgvector search** — ivfflat cosine index for fast similarity queries
- ❖ **REST API** — `/similar`, `/radio`, `/mood/<mood>`, `/stats` endpoints via FastAPI
- ❖ **m3u playlist export** — systemd timers write mood/daily-mix `.m3u` files into Navidrome library dir
- ❖ **Auto-scan worker** — hourly incremental rescan, skips tracks whose size/mtime are unchanged
- ❖ **Docker Compose** — single `make up` brings up PostgreSQL 16 + pgvector + worker + API

## ■ Stack

<div align="center">

| Component | Technology |
|-----------|------------|
| Feature extraction | essentia-tensorflow + MusiCNN |
| Metadata | mutagen |
| Vector DB | PostgreSQL 16 + pgvector (ivfflat) |
| API | FastAPI + uvicorn |
| Worker | Python (analyzer.py, watch mode) |
| Playlists | m3u dumper (systemd timer) |
| Deploy | Docker Compose |

</div>

## ■ How It Works

```
1. Worker scans /data/music/library/ (shared volume, read-only) for new or changed tracks
2. For each track, extracts audio features (BPM, key, loudness, energy, danceability, mood) and a 200-dim MusiCNN embedding
3. Features and embeddings are stored in PostgreSQL via pgvector (ivfflat cosine index)
4. FastAPI serves /similar, /radio, /mood/<mood>, and /stats endpoints using vector KNN queries
5. A systemd timer periodically runs the m3u dumper, writing mood and daily-mix playlists to _playlists/*.m3u inside the Navidrome library dir
6. Navidrome auto-scans and all Subsonic clients see the generated playlists
```

## ■ Usage

```bash
# Download essentia models
make install

# Start all services
make up

# Force full library re-scan
make analyze

# View stats
make stats

# Tear down
make down
```

Library path defaults to `/data/music/library/`; override via `LIBRARY_PATH` env var.

## ■ License

MIT © [pluttan](https://github.com/pluttan)
