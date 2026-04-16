"""JSON checkpoint storage for HITL pause/resume.

Supports two modes:

* Legacy: a single anonymous checkpoint at `data/underwriting_checkpoint.json`
  (used by the original flow controller and `/api/debug/persistence`).
* Threaded: a per-thread map at `data/underwriting_threads.json`, keyed by
  `thread_id`, used by the two-tier HITL endpoints to resume a specific case.

Both modes write/read the same UnderwritingState shape. The threaded payload
also carries `version`, `applicant_data`, and `region` so a thread can be
resumed without re-uploading the original input.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


BASE_DIR = Path(__file__).resolve().parents[1]
CHECKPOINT_FILE = BASE_DIR / "data" / "underwriting_checkpoint.json"
THREADS_FILE = BASE_DIR / "data" / "underwriting_threads.json"

THREAD_SCHEMA_VERSION = 2


# --------------------------------------------------------------------------- #
# Legacy single-slot checkpoint
# --------------------------------------------------------------------------- #


def save_checkpoint(state: Dict[str, Any]) -> None:
    """Persist latest state to JSON so the legacy flow can be resumed."""
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CHECKPOINT_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, default=str)


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


# --------------------------------------------------------------------------- #
# Threaded checkpoint store
# --------------------------------------------------------------------------- #


def _load_threads() -> Dict[str, Any]:
    if not THREADS_FILE.exists():
        return {}
    try:
        with THREADS_FILE.open("r", encoding="utf-8") as f:
            payload = json.load(f)
            if isinstance(payload, dict):
                return payload
    except (OSError, json.JSONDecodeError):
        return {}
    return {}


def _write_threads(threads: Dict[str, Any]) -> None:
    THREADS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with THREADS_FILE.open("w", encoding="utf-8") as f:
        json.dump(threads, f, indent=2, default=str)


def save_thread(
    thread_id: str,
    state: Dict[str, Any],
    *,
    applicant_data: Optional[Dict[str, Any]] = None,
    region: Optional[str] = None,
) -> None:
    """Upsert a per-thread checkpoint."""
    threads = _load_threads()
    existing = threads.get(thread_id, {}) if isinstance(threads.get(thread_id), dict) else {}
    payload = {
        "version": THREAD_SCHEMA_VERSION,
        "thread_id": thread_id,
        "state": state,
        "applicant_data": applicant_data
        or existing.get("applicant_data")
        or state.get("applicant_data"),
        "region": region or existing.get("region") or state.get("region"),
    }
    threads[thread_id] = payload
    _write_threads(threads)


def load_thread(thread_id: str) -> Optional[Dict[str, Any]]:
    """Return the persisted thread payload (or None)."""
    threads = _load_threads()
    payload = threads.get(thread_id)
    if isinstance(payload, dict):
        return payload
    return None


def list_threads() -> Dict[str, Dict[str, Any]]:
    """Return a shallow summary of every persisted thread."""
    threads = _load_threads()
    summary: Dict[str, Dict[str, Any]] = {}
    for tid, payload in threads.items():
        if not isinstance(payload, dict):
            continue
        state = payload.get("state", {}) or {}
        summary[tid] = {
            "decision_status": state.get("decision_status"),
            "risk_score": state.get("risk_score"),
            "hitl_stage": state.get("hitl_stage"),
            "is_provisional": state.get("is_provisional", False),
            "pending_analyst": len(state.get("pending_analyst_qids", []) or []),
            "pending_borrower_critical": len(state.get("pending_borrower_qids_critical", []) or []),
            "pending_borrower_async": len(state.get("pending_borrower_qids_async", []) or []),
            "region": payload.get("region"),
        }
    return summary


def delete_thread(thread_id: str) -> bool:
    threads = _load_threads()
    if thread_id not in threads:
        return False
    del threads[thread_id]
    _write_threads(threads)
    return True
