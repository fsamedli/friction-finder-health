#!/usr/bin/env bash
# Demo safety net. Builds the web app, starts a private server on :8010 with NO model key (deterministic rules
# mode) and a scratch cache folder (your demo state is untouched), walks the demo path at 1440 px and 390 px,
# and exits non-zero on any failure. Run before every commit and before every rehearsal.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${CHECK_PORT:-8010}"
SCRATCH="$(mktemp -d)"
(cd web && npm run build >/dev/null)
env GW_AZURE_OPENAI_KEY= OPENAI_API_KEY= FF_CACHE_DIR="$SCRATCH/cache" FF_APPROVALS_PATH="$SCRATCH/approvals.jsonl" \
  .venv/bin/uvicorn api.main:app --port "$PORT" --log-level warning &
SERVER=$!
trap 'kill $SERVER 2>/dev/null; rm -rf "$SCRATCH"' EXIT
for _ in $(seq 1 40); do curl -sf "http://127.0.0.1:$PORT/api/meta" >/dev/null && break; sleep 0.5; done
node web/scripts/demo_check.mjs "http://127.0.0.1:$PORT"
