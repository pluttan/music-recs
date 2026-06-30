#!/usr/bin/env bash
# Download Essentia pretrained models required by the worker.
# Run once on host before `docker compose up`.

set -euo pipefail

MODELS_DIR="$(cd "$(dirname "$0")/.." && pwd)/data/models"
mkdir -p "$MODELS_DIR"

BASE="https://essentia.upf.edu/models"

MODELS=(
    "feature-extractors/musicnn/msd-musicnn-1.pb"
    "classification-heads/mood_happy/mood_happy-musicnn-msd-2.pb"
    "classification-heads/mood_sad/mood_sad-musicnn-msd-2.pb"
    "classification-heads/mood_relaxed/mood_relaxed-musicnn-msd-2.pb"
    "classification-heads/mood_aggressive/mood_aggressive-musicnn-msd-2.pb"
    "classification-heads/mood_party/mood_party-musicnn-msd-2.pb"
    "classification-heads/mood_electronic/mood_electronic-musicnn-msd-2.pb"
    "classification-heads/mood_acoustic/mood_acoustic-musicnn-msd-2.pb"
)

for m in "${MODELS[@]}"; do
    name="$(basename "$m")"
    dest="$MODELS_DIR/$name"
    if [[ -f "$dest" ]]; then
        echo "[skip] $name already exists"
        continue
    fi
    echo "[fetch] $name"
    if curl -fSL --progress-bar "$BASE/$m" -o "$dest.tmp"; then
        mv "$dest.tmp" "$dest"
    else
        echo "[warn] $name not available at $BASE/$m — skipping"
        rm -f "$dest.tmp"
    fi
done

echo "[done] models in $MODELS_DIR"
ls -lh "$MODELS_DIR"
