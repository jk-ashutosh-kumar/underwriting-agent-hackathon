"""Auditor agent for fraud-risk pattern checks."""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List

from llm.client import ask_llm_json

logger = logging.getLogger(__name__)


def _with_handoff(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure structured handoff keys exist for downstream agents."""
    risk_drivers = payload.get("risk_drivers")
    positive_signals = payload.get("positive_signals")
    uncertainties = payload.get("uncertainties")
    recommendation = payload.get("recommendation")

    payload["risk_drivers"] = (
        [str(x) for x in risk_drivers] if isinstance(risk_drivers, list) else []
    )
    payload["positive_signals"] = (
        [str(x) for x in positive_signals] if isinstance(positive_signals, list) else []
    )
    payload["uncertainties"] = (
        [str(x) for x in uncertainties] if isinstance(uncertainties, list) else []
    )
    payload["recommendation"] = (
        str(recommendation)
        if isinstance(recommendation, str) and recommendation.strip()
        else "review"
    )
    return payload


def _run_auditor_deterministic(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic fraud/risk checks over unified profile."""
    bank = data.get("bank", data)
    transactions: List[Dict[str, Any]] = bank.get("transactions", [])
    invoices: List[Dict[str, Any]] = data.get("invoices", [])
    credit_report: Dict[str, Any] = data.get("credit_report", {})
    metrics: Dict[str, Any] = data.get("derived_metrics", {})
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
    invoice_volume = float(metrics.get("total_invoice_volume", 0.0))
    bank_inflow = float(metrics.get("monthly_inflow", bank.get("total_inflow", 0.0)))
    if invoice_volume > 0 and bank_inflow < (invoice_volume * 0.4):
        flags.append(
            f"Invoice-bank mismatch: invoice volume {invoice_volume:.2f} is high vs bank inflow {bank_inflow:.2f}."
        )
    legal_cases = int(credit_report.get("legal_cases", 0) or 0)
    legal_cases_against = int(credit_report.get("legal_cases_against_company", 0) or 0)
    if legal_cases > 0:
        flags.append(f"Credit report shows {legal_cases} legal case(s).")
    if legal_cases_against > 0:
        flags.append(
            f"Company has {legal_cases_against} legal case(s) filed against it."
        )
    gst_status = str(credit_report.get("gst_filing_status", metrics.get("gst_compliance", "unknown"))).lower()
    if gst_status not in {"regular", "compliant", "good"}:
        flags.append(f"GST compliance appears irregular: {gst_status}.")

    risk_score = min(100, len(large_txn_flags) * 25 + len(repeated_amount_flags) * 15)
    risk_score = min(100, risk_score + 15 * int("invoice-bank mismatch" in " ".join(flags).lower()) + 12 * int(legal_cases > 0) + 10 * int(gst_status not in {"regular", "compliant", "good"}))

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

    result = {
        "risk_score": int(risk_score),
        "flags": flags,
        "explanation": explanation,
        "risk_drivers": flags[:3],
        "positive_signals": ["No critical anomaly detected"] if not flags else [],
        "uncertainties": ["Limited historical transaction behavior context."],
        "recommendation": "review" if flags else "approve",
    }
    return _with_handoff(result)


def _run_auditor_llm(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """LLM-assisted auditor path with strict output schema."""
    large_txn_threshold = float(context.get("large_txn_threshold", 100000))
    region = context.get("region", "Unknown")
    system_prompt = (
        "You are a skeptical forensic accountant. "
        "Return ONLY JSON with keys: risk_score (0-100 int), flags (string list), explanation (string), "
        "risk_drivers (string list), positive_signals (string list), uncertainties (string list), "
        "recommendation (approve|review|reject)."
    )
    user_prompt = (
        "Analyze this financial case for suspicious patterns.\n"
        f"Region: {region}\n"
        f"Large transaction threshold: {large_txn_threshold}\n"
        f"Unified profile JSON: {data}\n"
        "Rules: include bank/invoice/credcheck cross-checks. Flag legal issues, GST irregularities, "
        "invoice-volume vs bank-inflow mismatches, large/repeated transactions. "
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
    result = {
        "risk_score": max(0, min(100, risk_score)),
        "flags": flags,
        "explanation": explanation,
    }
    return _with_handoff(result)


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
