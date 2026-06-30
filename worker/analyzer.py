#!/usr/bin/env python3
"""Essentia-based music analyzer.

Walks LIBRARY_PATH, extracts low-level features + MusiCNN embedding per track,
writes to postgres (tracks table, pgvector embedding column). Incremental — skips
tracks whose (path, file_mtime, file_size) already match what's in the DB.
"""

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np
import psycopg
from mutagen import File as MutagenFile
from pgvector.psycopg import register_vector

# essentia imports are heavy; import inside functions where needed


AUDIO_EXTENSIONS = {".mp3", ".m4a", ".flac", ".ogg", ".opus", ".wav"}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def read_metadata(path: Path) -> dict:
    try:
        f = MutagenFile(path, easy=True)
        if not f:
            return {}
        return {
            "title": (f.get("title") or [None])[0],
            "artist": (f.get("artist") or [None])[0],
            "album": (f.get("album") or [None])[0],
            "year": int((f.get("date") or ["0"])[0][:4]) if f.get("date") else None,
            "duration": f.info.length if hasattr(f, "info") else None,
        }
    except Exception as e:
        log(f"meta err {path.name}: {e}")
        return {}


def analyze_audio(path: Path, model_dir: Path) -> dict | None:
    import essentia.standard as es

    try:
        audio_mono = es.MonoLoader(filename=str(path), sampleRate=16000, resampleQuality=4)()
        audio_stereo = es.EqloudLoader(filename=str(path), sampleRate=44100)()
    except Exception as e:
        log(f"load err {path.name}: {e}")
        return None

    out: dict = {}

    # --- rhythm
    try:
        bpm, _, _, _, _ = es.RhythmExtractor2013(method="multifeature")(audio_stereo)
        out["bpm"] = float(bpm)
    except Exception as e:
        log(f"bpm err {path.name}: {e}")

    # --- key & scale
    try:
        key, scale, _ = es.KeyExtractor()(audio_stereo)
        out["key"] = str(key)
        out["scale"] = str(scale)
    except Exception as e:
        log(f"key err {path.name}: {e}")

    # --- loudness
    try:
        loudness = es.LoudnessEBUR128(hopSize=1024 / 44100, sampleRate=44100)(
            es.StereoTrimmer(endTime=min(30.0, len(audio_stereo) / 44100))(
                es.MonoMixer()(audio_stereo, 1)
            )
        )
        out["loudness"] = float(loudness[2])  # integrated loudness
    except Exception:
        pass

    # --- danceability (essentia built-in)
    try:
        danceability, _ = es.Danceability()(audio_stereo)
        out["danceability"] = float(danceability)
    except Exception:
        pass

    # --- energy (rms proxy)
    try:
        out["energy"] = float(np.sqrt(np.mean(audio_stereo ** 2)))
    except Exception:
        pass

    # --- musicnn embedding
    musicnn_model = model_dir / "msd-musicnn-1.pb"
    if musicnn_model.exists():
        try:
            emb_model = es.TensorflowPredictMusiCNN(
                graphFilename=str(musicnn_model),
                output="model/dense/BiasAdd",
            )
            embs = emb_model(audio_mono)  # shape (n_frames, 200)
            out["embedding"] = np.mean(embs, axis=0).astype(np.float32).tolist()
        except Exception as e:
            log(f"musicnn err {path.name}: {e}")

    # --- mood models (if available)
    for mood_key, model_name in [
        ("mood_happy", "mood_happy-musicnn-msd-2.pb"),
        ("mood_sad", "mood_sad-musicnn-msd-2.pb"),
        ("mood_relaxed", "mood_relaxed-musicnn-msd-2.pb"),
        ("mood_aggressive", "mood_aggressive-musicnn-msd-2.pb"),
        ("mood_party", "mood_party-musicnn-msd-2.pb"),
        ("mood_electronic", "mood_electronic-musicnn-msd-2.pb"),
        ("mood_acoustic", "mood_acoustic-musicnn-msd-2.pb"),
    ]:
        model_path = model_dir / model_name
        if not model_path.exists():
            continue
        try:
            m = es.TensorflowPredict2D(
                graphFilename=str(model_path),
                input="serving_default_model_Placeholder",
                output="PartitionedCall",
            )
            # these models take musicnn embeddings as input
            if "embedding" in out:
                emb_array = np.array([out["embedding"]], dtype=np.float32)
                prediction = m(emb_array)
                # output shape (1, 2): [not_mood, mood]
                out[mood_key] = float(prediction[0][1])
        except Exception as e:
            log(f"{mood_key} err {path.name}: {e}")

    return out


def upsert_track(cur, path: Path, rel_path: str, meta: dict, features: dict, stat) -> None:
    cols = {
        "path": rel_path,
        "title": meta.get("title"),
        "artist": meta.get("artist"),
        "album": meta.get("album"),
        "year": meta.get("year"),
        "duration": meta.get("duration"),
        "bpm": features.get("bpm"),
        "key": features.get("key"),
        "scale": features.get("scale"),
        "loudness": features.get("loudness"),
        "danceability": features.get("danceability"),
        "energy": features.get("energy"),
        "mood_happy": features.get("mood_happy"),
        "mood_sad": features.get("mood_sad"),
        "mood_relaxed": features.get("mood_relaxed"),
        "mood_aggressive": features.get("mood_aggressive"),
        "mood_party": features.get("mood_party"),
        "mood_electronic": features.get("mood_electronic"),
        "mood_acoustic": features.get("mood_acoustic"),
        "embedding": features.get("embedding"),
        "file_size": stat.st_size,
        "file_mtime": None,  # set via to_timestamp below
    }
    col_names = [k for k in cols.keys() if cols[k] is not None]
    placeholders = [f"%({k})s" for k in col_names]
    set_clauses = [f"{k} = EXCLUDED.{k}" for k in col_names if k != "path"]

    sql = f"""
        INSERT INTO tracks ({', '.join(col_names)}, file_mtime, analyzed_at)
        VALUES ({', '.join(placeholders)}, to_timestamp(%(mtime_unix)s), NOW())
        ON CONFLICT (path) DO UPDATE SET
            {', '.join(set_clauses)},
            file_mtime = EXCLUDED.file_mtime,
            analyzed_at = NOW()
    """
    cur.execute(sql, {**cols, "mtime_unix": stat.st_mtime})


def needs_reanalysis(cur, rel_path: str, stat) -> bool:
    cur.execute(
        "SELECT file_size, extract(epoch from file_mtime) FROM tracks WHERE path = %s",
        (rel_path,),
    )
    row = cur.fetchone()
    if row is None:
        return True
    db_size, db_mtime = row
    if db_size != stat.st_size:
        return True
    if db_mtime is None or abs(db_mtime - stat.st_mtime) > 1:
        return True
    return False


def scan_once(library: Path, model_dir: Path, conn) -> None:
    files = sorted(
        p for p in library.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
    )
    log(f"found {len(files)} audio files under {library}")
    ok = skip = err = 0
    for p in files:
        rel = str(p.relative_to(library))
        stat = p.stat()
        with conn.cursor() as cur:
            if not needs_reanalysis(cur, rel, stat):
                skip += 1
                continue
        feats = analyze_audio(p, model_dir)
        if feats is None:
            err += 1
            continue
        meta = read_metadata(p)
        with conn.cursor() as cur:
            upsert_track(cur, p, rel, meta, feats, stat)
        conn.commit()
        ok += 1
        if ok % 10 == 0:
            log(f"progress: ok={ok} skip={skip} err={err} / {len(files)}")
    log(f"scan done: ok={ok} skip={skip} err={err}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    library = Path(os.environ.get("LIBRARY_PATH", "/music"))
    model_dir = Path(os.environ.get("MODEL_DIR", "/models"))
    db_url = os.environ["DATABASE_URL"]
    interval = int(os.environ.get("SCAN_INTERVAL_SEC", "3600"))

    log(f"library: {library}")
    log(f"models:  {model_dir}")
    log(f"db:      {db_url.split('@')[-1]}")

    while True:
        try:
            with psycopg.connect(db_url, autocommit=False) as conn:
                register_vector(conn)
                scan_once(library, model_dir, conn)
        except Exception as e:
            log(f"scan fatal: {e}")

        if args.once or not args.watch:
            break
        log(f"sleeping {interval}s until next scan")
        time.sleep(interval)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
