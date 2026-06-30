CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS tracks (
    path              TEXT PRIMARY KEY,
    title             TEXT,
    artist            TEXT,
    album             TEXT,
    year              INTEGER,
    duration          REAL,

    bpm               REAL,
    key               TEXT,
    scale             TEXT,
    loudness          REAL,
    danceability      REAL,
    energy            REAL,

    mood_happy        REAL,
    mood_sad          REAL,
    mood_relaxed      REAL,
    mood_aggressive   REAL,
    mood_party        REAL,
    mood_electronic   REAL,
    mood_acoustic     REAL,

    embedding         vector(200),

    file_size         BIGINT,
    file_mtime        TIMESTAMPTZ,
    analyzed_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS tracks_artist_idx ON tracks (artist);
CREATE INDEX IF NOT EXISTS tracks_album_idx  ON tracks (album);
CREATE INDEX IF NOT EXISTS tracks_bpm_idx    ON tracks (bpm);

CREATE INDEX IF NOT EXISTS tracks_embedding_idx
    ON tracks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
