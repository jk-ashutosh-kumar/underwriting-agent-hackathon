#!/usr/bin/env bash
set -euo pipefail

# Always run from this script's directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Create local virtual environment if missing.
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

# Activate environment and install dependencies if needed.
source ".venv/bin/activate"
pip install -r requirements.txt >/dev/null

# Launch Streamlit dashboard.
streamlit run ui/app.py
