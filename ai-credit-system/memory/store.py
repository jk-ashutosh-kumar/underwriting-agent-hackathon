"""Simple JSON file-based memory store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parents[1]
MEMORY_FILE = BASE_DIR / "data" / "cases_memory.json"


def load_cases() -> List[Dict[str, Any]]:
    """Load all stored cases from memory file."""
    if not MEMORY_FILE.exists():
        return []
    with MEMORY_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_case(data: Dict[str, Any]) -> None:
    """Append one case record to memory JSON."""
    cases = load_cases()
    cases.append(data)

    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with MEMORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2)
