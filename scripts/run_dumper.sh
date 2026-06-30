#!/usr/bin/env bash
# Wrapper around dump_m3u.py that resolves paths, runs inside docker
# (so python + deps are available), and gets invoked by a systemd timer.

set -euo pipefail

cd "$(dirname "$0")/.."
docker compose exec -T recs-api python3 /app/dump_m3u.py \
  --api "http://localhost:8000" \
  --library "/music" \
  || true
