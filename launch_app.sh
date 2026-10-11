#!/usr/bin/env bash
set -e

PROJECT_DIR="/home/april/Documents/project1"
cd "$PROJECT_DIR"

fuser -k 8000/tcp > /dev/null 2>&1 || true
sleep 0.4

"$PROJECT_DIR/.venv/bin/python3" -m uvicorn server:app --host 0.0.0.0 --port 8000 > "$PROJECT_DIR/server.log" 2>&1 &
SERVER_PID=$!

cleanup() {
    kill -TERM "$SERVER_PID" 2>/dev/null || true
    sleep 0.3
    kill -9 "$SERVER_PID" 2>/dev/null || true
    fuser -k 8000/tcp > /dev/null 2>&1 || true
    exit 0
}

trap cleanup INT TERM EXIT HUP

MAX_ATTEMPTS=35
COUNT=0
while ! curl -s --max-time 1 http://127.0.0.1:8000/api/status > /dev/null 2>&1; do
    sleep 0.25
    COUNT=$((COUNT + 1))
    if [ $COUNT -ge $MAX_ATTEMPTS ]; then
        exit 1
    fi
done

CHROME_BIN=""
if [ -x "/home/april/.local/opt/google-chrome/opt/google/chrome/chrome" ]; then
    CHROME_BIN="/home/april/.local/opt/google-chrome/opt/google/chrome/chrome"
elif which google-chrome > /dev/null 2>&1; then
    CHROME_BIN="$(which google-chrome)"
fi

if [ -n "$CHROME_BIN" ]; then
    rm -f /tmp/innov8_desktop_profile/Singleton* 2>/dev/null || true
    "$CHROME_BIN" --app="http://localhost:8000" --user-data-dir="/tmp/innov8_desktop_profile" --no-first-run --no-default-browser-check
else
    xdg-open "http://localhost:8000"
fi
