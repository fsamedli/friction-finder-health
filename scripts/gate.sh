#!/usr/bin/env bash
# The whole v0.8 gate in one command, keyless. Saves the raw output of every check.
#   ./scripts/gate.sh docs/overnight/v0.8/_verify baseline     -> <dir>/baseline_<check>.txt
# Checks: web build (tsc + vite), lint (oxlint), pytest (no key), gold evals (rules), adversarial evals (rules),
# investigation evals (rules, when the pack exists), demo_check (1440 + 390 px), axe a11y (0 violations expected).
# Prints one summary line per check and exits non-zero if any check failed.
set -uo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-docs/overnight/v0.8/_verify}"; TAG="${2:-gate}"
mkdir -p "$OUT"
NOKEY=(env GW_AZURE_OPENAI_KEY= OPENAI_API_KEY=)
fail=0
run() {  # name, command...
  local name="$1"; shift
  local f="$OUT/${TAG}_${name}.txt"
  { echo "\$ $*"; echo "# $(date '+%Y-%m-%d %H:%M:%S %z') on $(git rev-parse --short HEAD) ($(git rev-parse --abbrev-ref HEAD))"; } > "$f"
  "$@" >> "$f" 2>&1; local rc=$?
  echo "exit=$rc" >> "$f"
  [ $rc -ne 0 ] && fail=1
  printf '%-12s exit=%s  %s\n' "$name" "$rc" "$(grep -v '^exit=' "$f" | grep -v '^\s*$' | tail -1 | cut -c1-110)"
}
run build bash -c "cd web && npm run build"
run lint bash -c "cd web && npm run lint"
run pytest "${NOKEY[@]}" .venv/bin/python -m pytest tests -q -p no:cacheprovider
run gold "${NOKEY[@]}" .venv/bin/python -m evals.run_evals --no-model
run adversarial "${NOKEY[@]}" .venv/bin/python -m evals.adversarial.run --no-model
if [ -f evals/investigate/run.py ]; then run investigate "${NOKEY[@]}" .venv/bin/python -m evals.investigate.run --no-model; fi
run demo_check ./scripts/demo_check.sh
# a11y against a private keyless server with a scratch cache (demo state untouched)
PORT="${A11Y_PORT:-8011}"; SCRATCH="$(mktemp -d)"
"${NOKEY[@]}" FF_CACHE_DIR="$SCRATCH/cache" FF_APPROVALS_PATH="$SCRATCH/approvals.jsonl" .venv/bin/uvicorn api.main:app --port "$PORT" --log-level warning >/dev/null 2>&1 &
SRV=$!
for _ in $(seq 1 40); do curl -sf -m 2 "http://127.0.0.1:$PORT/api/meta" >/dev/null && break; sleep 0.5; done
run a11y bash -c "node web/scripts/a11y.mjs http://127.0.0.1:$PORT && node -e \"\" "
kill $SRV 2>/dev/null; rm -rf "$SCRATCH"
grep -q '^0 rules violated' "$OUT/${TAG}_a11y.txt" || { echo "a11y: violations found"; fail=1; }
exit $fail
