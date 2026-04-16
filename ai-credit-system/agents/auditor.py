"""Auditor agent for fraud-risk pattern checks."""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List

from llm.client import ask_llm_json

logger = logging.getLogger(__name__)


# Severity thresholds shared with the findings aggregator.
SEVERITY_CRITICAL = "critical"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"


def _make_finding(
    code: str,
    severity: str,
    category: str,
    message: str,
    *,
    evidence: Dict[str, Any] | None = None,
    needs_borrower: bool = True,
    source: str = "auditor",
) -> Dict[str, Any]:
    """Construct a finding dict in the standard shape."""
    return {
        "code": code,
        "severity": severity,
        "category": category,
        "source": source,
        "message": message,
        "evidence": evidence or {},
        "needs_borrower": needs_borrower,
    }


def _with_handoff(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure structured handoff keys exist for downstream agents."""
    risk_drivers = payload.get("risk_drivers")
    positive_signals = payload.get("positive_signals")
    uncertainties = payload.get("uncertainties")
    recommendation = payload.get("recommendation")
    findings = payload.get("findings")

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
    payload["findings"] = findings if isinstance(findings, list) else []
    return payload


def _run_auditor_deterministic(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic fraud/risk checks over unified profile."""
    bank = data.get("bank", data)
    transactions: List[Dict[str, Any]] = bank.get("transactions", [])
    credit_report: Dict[str, Any] = data.get("credit_report", {})
    metrics: Dict[str, Any] = data.get("derived_metrics", {})
    large_txn_threshold = float(context.get("large_txn_threshold", 100000))

    findings: List[Dict[str, Any]] = []
    flags: List[str] = []
    amount_values: List[float] = []
    large_txn_count = 0

    for txn in transactions:
        amount = float(txn.get("amount", 0))
        amount_values.append(amount)
        if amount > large_txn_threshold:
            large_txn_count += 1
            description = str(txn.get("description") or "Unknown")
            unexplained = (not description.strip()) or "unknown" in description.lower()
            severity = SEVERITY_CRITICAL if unexplained else SEVERITY_WARNING
            findings.append(
                _make_finding(
                    code="LARGE_UNEXPLAINED_CREDIT" if unexplained else "LARGE_TRANSACTION",
                    severity=severity,
                    category="bank_anomaly",
                    message=(
                        f"Large transaction {amount:.2f} on {txn.get('date', '?')} — "
                        f"{description}. Threshold {large_txn_threshold:.2f}."
                    ),
                    evidence={
                        "transaction": txn,
                        "threshold": large_txn_threshold,
                    },
                )
            )
            flags.append(
                f"Large transaction flagged: {description} for {amount:.2f} "
                f"(threshold {large_txn_threshold:.2f})."
            )

    amount_counter = Counter(amount_values)
    repeated = [(a, c) for a, c in amount_counter.items() if c > 1]
    if repeated:
        for amount, count in repeated:
            flags.append(f"Repeated amount pattern: {amount:.2f} appears {count} times.")
        findings.append(
            _make_finding(
                code="REPEATED_AMOUNT_PATTERN",
                severity=SEVERITY_WARNING,
                category="bank_anomaly",
                message=(
                    "Repeated identical amounts detected — could be regular billing "
                    "or layered transactions."
                ),
                evidence={"repeated": [{"amount": a, "count": c} for a, c in repeated]},
            )
        )

    # ---- Use the new derived metrics from unified_schema ------------------
    flagged_txns: List[Dict[str, Any]] = list(metrics.get("flagged_transactions", []))
    if flagged_txns:
        for txn in flagged_txns:
            findings.append(
                _make_finding(
                    code="TAMPERING_BALANCE_MISMATCH",
                    severity=SEVERITY_CRITICAL,
                    category="tampering",
                    message=(
                        "Bank statement row has running-balance mismatch "
                        f"({txn.get('flag_type')}) on {txn.get('date')}: "
                        f"{txn.get('description')} for {txn.get('amount')}"
                    ),
                    evidence={"transaction": txn},
                )
            )
        flags.append(
            f"Bank statement integrity: {len(flagged_txns)} row(s) flagged by parser."
        )

    round_trip_pairs = list(metrics.get("round_trip_pairs", []))
    if round_trip_pairs:
        severity = SEVERITY_CRITICAL if len(round_trip_pairs) >= 2 else SEVERITY_WARNING
        findings.append(
            _make_finding(
                code="ROUND_TRIPPING_DETECTED",
                severity=severity,
                category="bank_anomaly",
                message=(
                    f"{len(round_trip_pairs)} matching in/out transaction pair(s) "
                    "detected within 3 days — possible round-tripping."
                ),
                evidence={"pairs": round_trip_pairs[:5]},
            )
        )
        flags.append(f"Round-tripping pairs detected: {len(round_trip_pairs)}.")

    cash_ratio = float(metrics.get("cash_withdrawal_ratio", 0.0))
    if cash_ratio > 0.4:
        findings.append(
            _make_finding(
                code="HIGH_CASH_RATIO",
                severity=SEVERITY_WARNING,
                category="bank_anomaly",
                message=(
                    f"Cash outflow ratio {cash_ratio:.2%} exceeds 40% — high cash "
                    "intensity is a soft fraud / off-book risk signal."
                ),
                evidence={"cash_withdrawal_ratio": cash_ratio},
                needs_borrower=False,
            )
        )

    inflow_concentration = float(metrics.get("inflow_concentration", 0.0))
    if inflow_concentration > 0.6:
        findings.append(
            _make_finding(
                code="COUNTERPARTY_CONCENTRATION",
                severity=SEVERITY_WARNING,
                category="trend",
                message=(
                    f"Top counterparty contributes {inflow_concentration:.2%} of inflow "
                    f"({metrics.get('top_inflow_counterparty', '?')})."
                ),
                evidence={
                    "concentration": inflow_concentration,
                    "counterparty": metrics.get("top_inflow_counterparty"),
                },
                needs_borrower=False,
            )
        )

    largest_unexplained_credit = float(metrics.get("largest_unexplained_credit", 0.0))
    if largest_unexplained_credit > large_txn_threshold:
        findings.append(
            _make_finding(
                code="LARGE_UNEXPLAINED_CREDIT",
                severity=SEVERITY_CRITICAL,
                category="bank_anomaly",
                message=(
                    f"Unexplained credit of {largest_unexplained_credit:.2f} exceeds "
                    f"threshold {large_txn_threshold:.2f}."
                ),
                evidence={
                    "amount": largest_unexplained_credit,
                    "transaction": metrics.get("largest_unexplained_credit_txn"),
                },
            )
        )

    invoice_volume = float(metrics.get("total_invoice_volume", 0.0))
    bank_inflow = float(metrics.get("monthly_inflow", bank.get("total_inflow", 0.0)))
    if invoice_volume > 0 and bank_inflow < (invoice_volume * 0.4):
        flags.append(
            f"Invoice-bank mismatch: invoice volume {invoice_volume:.2f} is high vs bank inflow {bank_inflow:.2f}."
        )
        findings.append(
            _make_finding(
                code="INVOICE_INFLOW_MISMATCH",
                severity=SEVERITY_WARNING,
                category="cross_source",
                message=(
                    f"Declared invoice volume {invoice_volume:.2f} is much higher than "
                    f"observed bank inflow {bank_inflow:.2f}."
                ),
                evidence={"invoice_volume": invoice_volume, "bank_inflow": bank_inflow},
            )
        )

    legal_cases = int(credit_report.get("legal_cases", 0) or 0)
    legal_cases_against = int(credit_report.get("legal_cases_against_company", 0) or 0)
    legal_criminal = int(credit_report.get("legal_cases_criminal", 0) or 0)
    if legal_cases > 0:
        flags.append(f"Credit report shows {legal_cases} legal case(s).")
        findings.append(
            _make_finding(
                code="LEGAL_CASES_BY_COMPANY",
                severity=SEVERITY_WARNING if legal_cases < 10 else SEVERITY_CRITICAL,
                category="credit",
                message=f"Company is plaintiff in {legal_cases} legal case(s).",
                evidence={"count": legal_cases},
                needs_borrower=False,
            )
        )
    if legal_cases_against > 0:
        flags.append(f"Company has {legal_cases_against} legal case(s) filed against it.")
        findings.append(
            _make_finding(
                code="LEGAL_CASES_AGAINST_COMPANY",
                severity=SEVERITY_CRITICAL,
                category="credit",
                message=f"Company is defendant in {legal_cases_against} legal case(s).",
                evidence={"count": legal_cases_against},
            )
        )
    if legal_criminal > 0:
        findings.append(
            _make_finding(
                code="LEGAL_CRIMINAL_CASES",
                severity=SEVERITY_CRITICAL,
                category="credit",
                message=f"Credit report contains {legal_criminal} criminal legal case(s).",
                evidence={"count": legal_criminal},
            )
        )

    past_defaults = int(credit_report.get("past_defaults", 0) or 0)
    if past_defaults > 0:
        findings.append(
            _make_finding(
                code="PAST_DEFAULTS_PRESENT",
                severity=SEVERITY_CRITICAL,
                category="credit",
                message=f"Borrower has {past_defaults} past default(s) on record.",
                evidence={"count": past_defaults},
            )
        )

    director_defaults = int(credit_report.get("director_defaults", 0) or 0)
    if director_defaults > 0:
        findings.append(
            _make_finding(
                code="DIRECTOR_DEFAULTS",
                severity=SEVERITY_CRITICAL,
                category="credit",
                message=f"Director(s) have {director_defaults} default(s) on record.",
                evidence={"count": director_defaults},
            )
        )

    gst_status = str(credit_report.get("gst_filing_status", metrics.get("gst_compliance", "unknown"))).lower()
    gst_total_delays = int(credit_report.get("gst_total_delays", 0) or 0)
    gst_avg_delay = float(credit_report.get("gst_avg_delay_days", 0) or 0)
    if gst_status not in {"regular", "compliant", "good"}:
        flags.append(f"GST compliance appears irregular: {gst_status}.")
        if gst_total_delays > 6:
            findings.append(
                _make_finding(
                    code="GST_DELAY_SEVERE",
                    severity=SEVERITY_CRITICAL,
                    category="credit",
                    message=(
                        f"GST filings delayed {gst_total_delays} times "
                        f"(avg {gst_avg_delay:.1f} days)."
                    ),
                    evidence={"total_delays": gst_total_delays, "avg_delay_days": gst_avg_delay},
                    needs_borrower=False,
                )
            )
        else:
            findings.append(
                _make_finding(
                    code="GST_DELAY_MILD",
                    severity=SEVERITY_WARNING,
                    category="credit",
                    message=(
                        f"GST filing status is {gst_status} "
                        f"(on-time {credit_report.get('gst_on_time_filing_percent', 0)}%)."
                    ),
                    evidence={
                        "status": gst_status,
                        "on_time_percent": credit_report.get("gst_on_time_filing_percent"),
                    },
                    needs_borrower=False,
                )
            )

    # ---- Risk score (kept for backward compat with the rest of the flow) ----
    risk_score = min(
        100,
        large_txn_count * 25
        + len(repeated) * 15
        + 15 * int(any(f["code"] == "INVOICE_INFLOW_MISMATCH" for f in findings))
        + 12 * int(legal_cases > 0)
        + 10 * int(gst_status not in {"regular", "compliant", "good"})
        + 30 * int(any(f["code"] == "TAMPERING_BALANCE_MISMATCH" for f in findings))
        + 25 * int(any(f["code"] == "ROUND_TRIPPING_DETECTED" and f["severity"] == SEVERITY_CRITICAL for f in findings))
        + 20 * int(past_defaults > 0)
        + 10 * int(cash_ratio > 0.4),
    )

    if not flags and not findings:
        explanation = (
            "I did not find unusually large transactions or repeated exact amounts, "
            "so fraud indicators are currently low."
        )
    else:
        explanation = (
            "Multiple risk signals detected (see findings) — including statement "
            "integrity, transaction patterns and credit-bureau context."
        )

    risk_drivers = [f["message"] for f in findings if f["severity"] == SEVERITY_CRITICAL][:3]
    if not risk_drivers:
        risk_drivers = [f["message"] for f in findings][:3]

    result = {
        "risk_score": int(risk_score),
        "flags": flags,
        "findings": findings,
        "explanation": explanation,
        "risk_drivers": risk_drivers,
        "positive_signals": ["No critical anomaly detected"] if not findings else [],
        "uncertainties": ["Limited historical transaction behavior context."],
        "recommendation": "review" if findings else "approve",
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
    # Run deterministic findings detection so we always produce structured findings —
    # the LLM only contributes the headline numbers/explanation when enabled.
    deterministic = _run_auditor_deterministic(data, context)
    result = {
        "risk_score": max(0, min(100, risk_score)),
        "flags": flags or deterministic["flags"],
        "findings": deterministic["findings"],
        "explanation": explanation,
        "risk_drivers": deterministic["risk_drivers"],
        "positive_signals": deterministic["positive_signals"],
        "uncertainties": deterministic["uncertainties"],
        "recommendation": str(payload.get("recommendation", deterministic["recommendation"])),
    }
    return _with_handoff(result)


def run_auditor(data: Dict[str, Any], context: Dict[str, Any], use_llm: bool = False) -> Dict[str, Any]:
    """Skeptical forensic accountant who trusts no one."""
    if not use_llm:
        return _run_auditor_deterministic(data, context)

    try:
        llm_result = _run_auditor_llm(data, context)
        llm_result["mode"] = "llm"
        return llm_result
    except Exception as exc:
        fallback = _run_auditor_deterministic(data, context)
        fallback["mode"] = "deterministic_fallback"
        fallback["llm_error"] = str(exc)
        return fallback
