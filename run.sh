#!/usr/bin/env bash
set -euo pipefail

PORT="${SRAG_PORT:-8501}"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
PY_BIN="/Volumes/External_ssd/Github/projects/RAGucation/.venv/bin/python"  # or /opt/homebrew/bin/python3

cd "$APP_DIR"

"$PY_BIN" -m streamlit run "$APP_DIR/app.py" \
  --server.headless true \
  --server.port "$PORT" &

sleep 2
open -g "http://localhost:${PORT}"
wait