"""Simple JSON checkpoint storage for HITL pause/resume."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


BASE_DIR = Path(__file__).resolve().parents[1]
CHECKPOINT_FILE = BASE_DIR / "data" / "underwriting_checkpoint.json"


def save_checkpoint(state: Dict[str, Any]) -> None:
    """Persist latest state to JSON so flow can be resumed."""
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CHECKPOINT_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def load_checkpoint() -> Optional[Dict[str, Any]]:
    """Load checkpoint if it exists; otherwise return None."""
    if not CHECKPOINT_FILE.exists():
        return None
    try:
        with CHECKPOINT_FILE.open("r", encoding="utf-8") as f:
            payload = json.load(f)
            if isinstance(payload, dict):
                return payload
    except (OSError, json.JSONDecodeError):
        return None
    return None
