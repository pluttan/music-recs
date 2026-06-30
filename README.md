![Header](header.png)

<div align="center">

# music-recs

**Self-hosted audio-based music recommendations with MusiCNN embeddings**

[![License](https://img.shields.io/badge/license-MIT-2C2C2C?style=for-the-badge&labelColor=1E1E1E)](LICENSE)
[![Python](https://img.shields.io/badge/Python-worker-2C2C2C?style=for-the-badge&logo=python&labelColor=1E1E1E)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-api-2C2C2C?style=for-the-badge&logo=fastapi&labelColor=1E1E1E)]()
[![pgvector](https://img.shields.io/badge/pgvector-PostgreSQL_16-2C2C2C?style=for-the-badge&logo=postgresql&labelColor=1E1E1E)]()
[![Docker](https://img.shields.io/badge/Docker-compose-2C2C2C?style=for-the-badge&logo=docker&labelColor=1E1E1E)]()

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

| Component | Technology |
|-----------|------------|
| Feature extraction | essentia-tensorflow + MusiCNN |
| Metadata | mutagen |
| Vector DB | PostgreSQL 16 + pgvector (ivfflat) |
| API | FastAPI + uvicorn |
| Worker | Python (analyzer.py, watch mode) |
| Playlists | m3u dumper (systemd timer) |
| Deploy | Docker Compose |

## ■ Data Flow

```
/data/music/library/  (shared volume, read-only for worker)
        |
[worker] scans -> extracts features + embedding -> INSERT tracks
        |
   [recs-db (pgvector)]
        |
[api] /similar?path=X&n=20 -> vector KNN
        |
[m3u dumper, systemd timer] -> writes _playlists/*.m3u
        |
   Navidrome auto-scans -> clients see playlists
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
