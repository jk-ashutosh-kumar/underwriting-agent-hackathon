"""Auditor agent logic."""

from __future__ import annotations

from typing import Any, Dict, List


def run_auditor(data: Dict[str, Any], threshold: float = 100000) -> Dict[str, Any]:
    """Flag unusually large transactions and compute a simple risk score."""
    transactions: List[Dict[str, Any]] = data.get("transactions", [])

    flagged = [txn for txn in transactions if float(txn.get("amount", 0)) > threshold]

    # Very simple risk score (0-10): each flagged transaction adds risk.
    risk_score = min(10, len(flagged) * 3 + (1 if flagged else 2))

    return {
        "agent": "auditor",
        "threshold": threshold,
        "flagged_transactions": flagged,
        "risk_score": risk_score,
        "summary": f"Found {len(flagged)} high-value transaction(s).",
    }
