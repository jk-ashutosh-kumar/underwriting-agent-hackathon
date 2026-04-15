"""Simple JSON memory store for historical partner notes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parents[1]
MEMORY_FILE = BASE_DIR / "data" / "cases_memory.json"


def _default_memory() -> List[Dict[str, Any]]:
    """Return starter memory used when no file exists yet."""
    return [
        {
            "partner": "ABC Ltd",
            "risk": "high",
            "note": "Late payments in December",
        }
    ]


def load_memory() -> List[Dict[str, Any]]:
    """Load memory entries from JSON file with safe fallback behavior."""
    if not MEMORY_FILE.exists():
        return _default_memory()

    try:
        with MEMORY_FILE.open("r", encoding="utf-8") as f:
            content = json.load(f)
            if isinstance(content, list):
                return content
    except (json.JSONDecodeError, OSError):
        # If file is corrupted or unreadable, fallback to starter memory.
        return _default_memory()

    return _default_memory()


def save_memory(entry: Dict[str, Any]) -> None:
    """Append one entry to memory JSON; keeps implementation intentionally simple."""
    memory = load_memory()
    memory.append(entry)
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with MEMORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)


# Backward-compatible aliases used by existing app code.
def load_cases() -> List[Dict[str, Any]]:
    """Compatibility alias for existing imports."""
    return load_memory()


def save_case(data: Dict[str, Any]) -> None:
    """Compatibility alias for existing imports."""
    save_memory(data)
