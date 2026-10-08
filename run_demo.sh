#!/usr/bin/env bash
# Friction Finder v0.9-health demo (Lanford Health, fictional): one command, one process (FastAPI serves the built React app).
# Default port 8001 so the v0.8 demo in ../prototype can run on 8000 at the same time.
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
[ -x "$PY" ] || { echo "Missing .venv. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"; exit 1; }
[ -f data/generated/team_ops_monthly.csv ] || "$PY" data/generate.py
if [ ! -f web/dist/index.html ]; then
  (cd web && npm ci && npm run build)
fi
PORT="${PORT:-8001}"
( sleep 2; open "http://127.0.0.1:$PORT" 2>/dev/null || true ) &
exec .venv/bin/uvicorn api.main:app --port "$PORT"
