"""Auditor agent for fraud-risk pattern checks."""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List

from llm.client import ask_llm_json

logger = logging.getLogger(__name__)


def _run_auditor_deterministic(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Current deterministic implementation kept as safe fallback."""
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

    amount_counter = Counter(amount_values)
    repeated_amount_flags = [
        f"Repeated amount pattern: {amount:.2f} appears {count} times."
        for amount, count in amount_counter.items()
        if count > 1
    ]

    flags = large_txn_flags + repeated_amount_flags
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


def _run_auditor_llm(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """LLM-assisted auditor path with strict output schema."""
    large_txn_threshold = float(context.get("large_txn_threshold", 100000))
    region = context.get("region", "Unknown")
    system_prompt = (
        "You are a skeptical forensic accountant. "
        "Return ONLY JSON with keys: risk_score (0-100 int), flags (string list), explanation (string)."
    )
    user_prompt = (
        "Analyze this financial case for suspicious patterns.\n"
        f"Region: {region}\n"
        f"Large transaction threshold: {large_txn_threshold}\n"
        f"Transactions JSON: {data.get('transactions', [])}\n"
        "Rules: flag large transactions and repeated exact amounts. "
        "Keep explanation concise and explicit."
    )
    payload = ask_llm_json(system_prompt=system_prompt, user_prompt=user_prompt)

    risk_score = int(payload.get("risk_score", 0))
    flags_raw = payload.get("flags", [])
    if not isinstance(flags_raw, list):
        flags_raw = [str(flags_raw)]
    flags = [str(item) for item in flags_raw]
    explanation = str(payload.get("explanation", "No explanation provided by LLM."))
    logger.info(
        "auditor_llm_completed",
        extra={
            "region": region,
            "risk_score": risk_score,
            "flag_count": len(flags),
        },
    )
    return {
        "risk_score": max(0, min(100, risk_score)),
        "flags": flags,
        "explanation": explanation,
    }


def run_auditor(data: Dict[str, Any], context: Dict[str, Any], use_llm: bool = False) -> Dict[str, Any]:
    """
    Skeptical forensic accountant who trusts no one.

    This agent keeps the logic intentionally simple and explainable for demo use:
    1) Flag large transactions above region threshold.
    2) Flag repeated same-amount transactions (possible round-tripping).
    """
    if not use_llm:
        return _run_auditor_deterministic(data, context)

    try:
        llm_result = _run_auditor_llm(data, context)
        # Add source metadata for debug visibility in logs/UI.
        llm_result["mode"] = "llm"
        return llm_result
    except Exception as exc:
        fallback = _run_auditor_deterministic(data, context)
        fallback["mode"] = "deterministic_fallback"
        fallback["llm_error"] = str(exc)
        return fallback
