#!/usr/bin/env bash
# One-command development launcher for the quant-portfolio-lab web GUI.
#
#   ./dev.sh          # backend on :8000, frontend (Vite) on :5173
#
# Requires: pip install -e ".[api]"  and  (cd frontend && npm install)
set -euo pipefail
cd "$(dirname "$0")"

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"

if ! python3 -c "import fastapi, uvicorn" 2>/dev/null; then
  echo "FastAPI/uvicorn not installed. Run:  pip install -e \".[api]\"" >&2
  exit 1
fi
if [ ! -d frontend/node_modules ]; then
  echo "frontend/node_modules missing. Run:  (cd frontend && npm install)" >&2
  exit 1
fi

cleanup() {
  # shellcheck disable=SC2046
  kill $(jobs -p) 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[dev] starting FastAPI on http://localhost:${API_PORT}"
python3 -m uvicorn quant_portfolio_lab.api.main:app \
  --port "${API_PORT}" --reload --reload-dir src &

echo "[dev] starting Vite on http://localhost:${WEB_PORT}"
(cd frontend && npm run dev -- --port "${WEB_PORT}") &

echo
echo "[dev] GUI:  http://localhost:${WEB_PORT}"
echo "[dev] API:  http://localhost:${API_PORT}/docs"
echo "[dev] Ctrl-C stops both."
wait
