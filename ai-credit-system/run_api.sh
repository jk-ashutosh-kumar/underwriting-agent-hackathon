#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source ".venv/bin/activate"
pip install -r requirements.txt >/dev/null

PORT="${PORT:-8010}"
echo "Starting FastAPI backend at http://localhost:${PORT}"
python api_server.py
