#!/bin/bash
set -euo pipefail

APP_NAME="ScholarRAG"
APP_HOME="$HOME/Library/Application Support/$APP_NAME"
VENV="$APP_HOME/.venv"
LOG="$APP_HOME/app.log"

mkdir -p "$APP_HOME"

# Locate Resources inside the app bundle (Platypus copies your files here)
# When this script runs inside the .app, $0 is .../Contents/Resources/script
RESOURCES_DIR="$(cd "$(dirname "$0")" && pwd)"

# First-run bootstrap: create venv + install deps
if [ ! -d "$VENV" ]; then
  /usr/bin/python3 -m venv "$VENV"
  "$VENV/bin/python" -m pip install --upgrade pip wheel > /dev/null
  if [ -f "$RESOURCES_DIR/requirements.txt" ]; then
    "$VENV/bin/python" -m pip install -r "$RESOURCES_DIR/requirements.txt" | tee -a "$LOG"
  fi
fi

# Optional: auto-start Ollama if not serving
if ! pgrep -f "ollama serve" >/dev/null 2>&1; then
  if command -v ollama >/dev/null 2>&1; then
    # Start it in the background if you installed Ollama via pkg/brew
    (ollama serve >>"$LOG" 2>&1 &)
    sleep 1
  fi
fi

# Export vars: keep Streamlit polite and set DB path for your app code
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
export SCHOLARRAG_DB="$APP_HOME/.rag_db"

# Pick a free port (avoid the 'developmentMode' in-process issue; we run the normal server)
PORT=$("$VENV/bin/python" - <<'PY'
import socket
for p in range(8501, 8999):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", p))
            print(p)
            break
        except OSError:
            pass
PY
)

# Launch Streamlit (non-headless so it auto-opens the browser; we also 'open' as a fallback)
APP_FILE="$RESOURCES_DIR/app.py"     # <-- change if your file is named differently
if [ ! -f "$APP_FILE" ]; then
  # try main.py fallback
  APP_FILE="$RESOURCES_DIR/main.py"
fi

# Start server
"$VENV/bin/python" -m streamlit run "$APP_FILE" \
  --server.address=127.0.0.1 \
  --server.port="$PORT" \
  >>"$LOG" 2>&1 &

SPID=$!

# Give it a moment, then open browser
sleep 2
open "http://127.0.0.1:$PORT"

# Keep the app alive until the server process exits
wait $SPID