"""Recs API — similarity, radio, mood endpoints on top of pgvector."""

import os
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, HTTPException, Query
from pgvector.psycopg import register_vector

DB_URL = os.environ["DATABASE_URL"]

_conn: psycopg.Connection | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _conn
    _conn = psycopg.connect(DB_URL, autocommit=True)
    register_vector(_conn)
    yield
    _conn.close()


app = FastAPI(title="music-recs", lifespan=lifespan)


def q(sql: str, params: tuple = ()) -> list[dict]:
    assert _conn is not None
    with _conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d.name for d in cur.description] if cur.description else []
        return [dict(zip(cols, row)) for row in cur.fetchall()]


@app.get("/")
def root() -> dict:
    return {"service": "music-recs", "endpoints": ["/similar", "/radio", "/mood", "/stats"]}


@app.get("/stats")
def stats() -> dict:
    rows = q("SELECT COUNT(*) AS total, COUNT(embedding) AS with_embedding FROM tracks")
    return rows[0] if rows else {}


@app.get("/similar")
def similar(path: str = Query(...), n: int = 20) -> list[dict]:
    rows = q("SELECT embedding FROM tracks WHERE path = %s", (path,))
    if not rows or rows[0]["embedding"] is None:
        raise HTTPException(404, f"no embedding for {path}")

    results = q(
        """
        SELECT path, title, artist, album, bpm, key, scale,
               1 - (embedding <=> %s) AS similarity
        FROM tracks
        WHERE embedding IS NOT NULL AND path != %s
        ORDER BY embedding <=> %s
        LIMIT %s
        """,
        (rows[0]["embedding"], path, rows[0]["embedding"], n),
    )
    return results


@app.get("/radio")
def radio(seed: str = Query(...), n: int = 50, bpm_tolerance: float = 15.0) -> list[dict]:
    """seed-based radio: similar embedding within BPM window of seed."""
    rows = q("SELECT embedding, bpm FROM tracks WHERE path = %s", (seed,))
    if not rows or rows[0]["embedding"] is None:
        raise HTTPException(404, f"no seed: {seed}")
    seed_emb = rows[0]["embedding"]
    seed_bpm = rows[0]["bpm"]

    if seed_bpm is None:
        return q(
            """
            SELECT path, title, artist, album, bpm
            FROM tracks WHERE embedding IS NOT NULL AND path != %s
            ORDER BY embedding <=> %s LIMIT %s
            """,
            (seed, seed_emb, n),
        )

    return q(
        """
        SELECT path, title, artist, album, bpm,
               1 - (embedding <=> %s) AS similarity
        FROM tracks
        WHERE embedding IS NOT NULL
          AND path != %s
          AND (bpm IS NULL OR ABS(bpm - %s) <= %s)
        ORDER BY embedding <=> %s
        LIMIT %s
        """,
        (seed_emb, seed, seed_bpm, bpm_tolerance, seed_emb, n),
    )


@app.get("/mood/{mood}")
def mood(mood: str, n: int = 30, threshold: float = 0.7) -> list[dict]:
    col = f"mood_{mood}"
    allowed = {
        "happy", "sad", "relaxed", "aggressive",
        "party", "electronic", "acoustic",
    }
    if mood not in allowed:
        raise HTTPException(400, f"mood must be one of {sorted(allowed)}")
    return q(
        f"""
        SELECT path, title, artist, album, bpm, {col} AS score
        FROM tracks
        WHERE {col} IS NOT NULL AND {col} >= %s
        ORDER BY {col} DESC
        LIMIT %s
        """,
        (threshold, n),
    )
