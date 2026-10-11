#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment and installing dependencies..."
    uv venv .venv
    uv pip install --python .venv pyarrow pandas numpy fastapi uvicorn python-multipart
fi

export PYTHONPATH="$SCRIPT_DIR"
echo "Starting Project 1 Data Quality Engine on http://localhost:8000 ..."
exec "$SCRIPT_DIR/.venv/bin/python" -m uvicorn server:app --host 0.0.0.0 --port 8000
