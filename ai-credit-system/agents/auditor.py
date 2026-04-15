"""Auditor agent for fraud-risk pattern checks."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List


def run_auditor(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Skeptical forensic accountant who trusts no one.

    This agent keeps the logic intentionally simple and explainable for demo use:
    1) Flag large transactions above region threshold.
    2) Flag repeated same-amount transactions (possible round-tripping).
    """
    transactions: List[Dict[str, Any]] = data.get("transactions", [])
    large_txn_threshold = float(context.get("large_txn_threshold", 100000))

    large_txn_flags: List[str] = []
    amount_values: List[float] = []

    for txn in transactions:
        amount = float(txn.get("amount", 0))
        amount_values.append(amount)
        if amount > large_txn_threshold:
            large_txn_flags.append(
                f"Large transaction flagged: {txn.get('description', 'Unknown')} "
                f"for {amount:.2f} (threshold {large_txn_threshold:.2f})."
            )

    # Count repeated transaction amounts to detect possible circular flows.
    amount_counter = Counter(amount_values)
    repeated_amount_flags = [
        f"Repeated amount pattern: {amount:.2f} appears {count} times."
        for amount, count in amount_counter.items()
        if count > 1
    ]

    flags = large_txn_flags + repeated_amount_flags

    # Simple demo risk scoring model (0-100).
    # Large amount findings are weighted higher than repeats.
    risk_score = min(100, len(large_txn_flags) * 25 + len(repeated_amount_flags) * 15)

    if not flags:
        explanation = (
            "I did not find unusually large transactions or repeated exact amounts, "
            "so fraud indicators are currently low."
        )
    else:
        explanation = (
            "I flagged this because high-value movements and/or repeated identical "
            "amounts are common warning signs for layered or circular transaction behavior."
        )

    return {
        "risk_score": int(risk_score),
        "flags": flags,
        "explanation": explanation,
    }
