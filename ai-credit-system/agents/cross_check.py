"""Cross-check agent: reconciles invoices, bank transactions and CredCheck."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from agents.auditor import (
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    _make_finding,
    _with_handoff,
)
from data.unified_schema import _parse_date, _safe_float, _is_credit, _counterparty_token
from llm.client import ask_llm_json

logger = logging.getLogger(__name__)


# Tolerances for invoice ↔ bank-credit matching.
DATE_WINDOW_DAYS = 5
AMOUNT_TOLERANCE_PCT = 0.02  # 2%


def _bank_credits(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    bank = profile.get("bank", {}) or {}
    return [t for t in bank.get("transactions", []) if _is_credit(t)]


def _amount_within_tolerance(a: float, b: float) -> bool:
    if a == 0 or b == 0:
        return abs(a - b) < 1.0
    return abs(a - b) / max(abs(a), abs(b)) <= AMOUNT_TOLERANCE_PCT


def _within_date_window(a: Optional[date], b: Optional[date]) -> bool:
    if a is None or b is None:
        return True  # cannot disprove → allow
    return abs((a - b).days) <= DATE_WINDOW_DAYS


def _match_invoices_to_credits(
    invoices: List[Dict[str, Any]],
    credits: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Greedy 1-to-1 matcher: each credit can be claimed by at most one invoice."""
    matched: List[Dict[str, Any]] = []
    unmatched_invoices: List[Dict[str, Any]] = []
    used_credit_idx: set[int] = set()

    parsed_credit_dates = [_parse_date(t.get("date")) for t in credits]
    credit_amounts = [_safe_float(t.get("amount", 0.0)) for t in credits]

    for inv in invoices:
        inv_date = _parse_date(inv.get("date"))
        inv_amount = _safe_float(inv.get("amount", 0.0))
        match_idx: Optional[int] = None
        for idx, credit in enumerate(credits):
            if idx in used_credit_idx:
                continue
            if not _amount_within_tolerance(inv_amount, credit_amounts[idx]):
                continue
            if not _within_date_window(inv_date, parsed_credit_dates[idx]):
                continue
            match_idx = idx
            break
        if match_idx is None:
            unmatched_invoices.append(inv)
        else:
            used_credit_idx.add(match_idx)
            matched.append({"invoice": inv, "credit": credits[match_idx]})

    unmatched_credits = [
        credit for idx, credit in enumerate(credits) if idx not in used_credit_idx
    ]
    return matched, unmatched_invoices, unmatched_credits


def _revenue_triangulation(profile: Dict[str, Any]) -> Dict[str, Any]:
    metrics = profile.get("derived_metrics", {})
    credit_report = profile.get("credit_report", {})
    invoice_total = float(metrics.get("total_invoice_volume", 0.0))
    bank_inflow_annualised = float(metrics.get("monthly_inflow", 0.0)) * 12
    pl_revenue = float(credit_report.get("pl_latest_revenue", 0.0))

    sources = {
        "invoice_total_annualised": invoice_total,
        "bank_inflow_annualised": bank_inflow_annualised,
        "credcheck_pl_revenue": pl_revenue,
    }
    nonzero = [v for v in sources.values() if v > 0]
    if len(nonzero) < 2:
        return {"sources": sources, "max_variance": 0.0, "comparable": False}

    hi = max(nonzero)
    lo = min(nonzero)
    variance = (hi - lo) / hi if hi > 0 else 0.0
    return {
        "sources": sources,
        "max_variance": round(variance, 4),
        "comparable": True,
    }


def _legal_counterparty_match(profile: Dict[str, Any]) -> List[str]:
    """If counterparty names from the bank statement appear in legal cases, surface them."""
    credit_report = profile.get("credit_report", {})
    raw_report = credit_report.get("report", {}) or {}
    legal = raw_report.get("legal_profile", {}) if isinstance(raw_report, dict) else {}
    case_blobs: List[str] = []
    if isinstance(legal, dict):
        for key in ("cases_by_company", "cases_against_company"):
            section = legal.get(key, {})
            if isinstance(section, dict):
                for v in section.values():
                    if isinstance(v, str):
                        case_blobs.append(v.lower())
                    elif isinstance(v, list):
                        case_blobs.extend(str(x).lower() for x in v)
    if not case_blobs:
        return []

    transactions = (profile.get("bank") or {}).get("transactions", [])
    matched: List[str] = []
    seen_tokens: set[str] = set()
    for txn in transactions:
        token = _counterparty_token(str(txn.get("description", "")))
        if not token or token in seen_tokens:
            continue
        seen_tokens.add(token)
        if any(token in blob for blob in case_blobs):
            matched.append(token)
    return matched


def _run_cross_check_deterministic(
    profile: Dict[str, Any], context: Dict[str, Any]
) -> Dict[str, Any]:
    invoices = profile.get("invoices", []) or []
    credits = _bank_credits(profile)
    metrics = profile.get("derived_metrics", {})
    credit_report = profile.get("credit_report", {})

    findings: List[Dict[str, Any]] = []
    matched, unmatched_invoices, unmatched_credits = _match_invoices_to_credits(invoices, credits)
    invoice_match_ratio = (len(matched) / len(invoices)) if invoices else 1.0

    if invoices and unmatched_invoices:
        # Severity scales with how many invoices fail to match.
        severity = SEVERITY_WARNING
        if invoice_match_ratio < 0.4:
            severity = SEVERITY_CRITICAL
        findings.append(
            _make_finding(
                code="INVOICE_UNMATCHED" if severity == SEVERITY_WARNING else "INVOICE_UNMATCHED_MAJOR",
                severity=severity,
                category="cross_source",
                message=(
                    f"{len(unmatched_invoices)} of {len(invoices)} invoice(s) had no "
                    "matching bank credit within 5 days / 2% tolerance."
                ),
                evidence={
                    "unmatched_invoice_ids": [inv.get("invoice_id") for inv in unmatched_invoices][:10],
                    "match_ratio": round(invoice_match_ratio, 4),
                },
                source="cross_check",
                # Borrower must explain unmatched invoices for critical severity.
                needs_borrower=severity == SEVERITY_CRITICAL,
            )
        )

    if invoices and unmatched_credits:
        unaccounted_inflow = sum(_safe_float(c.get("amount", 0)) for c in unmatched_credits)
        bank_inflow = float(metrics.get("monthly_inflow", 0.0))
        if bank_inflow > 0 and unaccounted_inflow / bank_inflow > 0.3:
            findings.append(
                _make_finding(
                    code="UNINVOICED_INFLOW",
                    severity=SEVERITY_WARNING,
                    category="cross_source",
                    message=(
                        f"{unaccounted_inflow:.2f} of bank inflow is not covered by any invoice "
                        f"({unaccounted_inflow / bank_inflow:.0%} of total inflow)."
                    ),
                    evidence={
                        "unaccounted_inflow": unaccounted_inflow,
                        "unmatched_credit_count": len(unmatched_credits),
                    },
                    source="cross_check",
                    needs_borrower=True,
                )
            )

    triang = _revenue_triangulation(profile)
    if triang.get("comparable"):
        variance = float(triang.get("max_variance", 0.0))
        if variance > 0.6:
            findings.append(
                _make_finding(
                    code="REVENUE_TRIANGULATION_MAJOR",
                    severity=SEVERITY_CRITICAL,
                    category="cross_source",
                    message=(
                        f"Revenue figures from invoice / bank / CredCheck disagree by {variance:.0%} — "
                        "a major mismatch."
                    ),
                    evidence=triang["sources"],
                    source="cross_check",
                )
            )
        elif variance > 0.25:
            findings.append(
                _make_finding(
                    code="REVENUE_TRIANGULATION_MINOR",
                    severity=SEVERITY_WARNING,
                    category="cross_source",
                    message=(
                        f"Revenue figures from invoice / bank / CredCheck disagree by {variance:.0%}."
                    ),
                    evidence=triang["sources"],
                    source="cross_check",
                )
            )

    matches = _legal_counterparty_match(profile)
    if matches:
        findings.append(
            _make_finding(
                code="LEGAL_COUNTERPARTY_MATCH",
                severity=SEVERITY_CRITICAL,
                category="cross_source",
                message=(
                    f"Counterparties on the bank statement ({', '.join(matches)}) match "
                    "names appearing in CredCheck legal records."
                ),
                evidence={"counterparties": matches},
                source="cross_check",
            )
        )

    cash_ratio = float(metrics.get("cash_withdrawal_ratio", 0.0))
    if invoices and cash_ratio > 0.5 and invoice_match_ratio < 0.5:
        findings.append(
            _make_finding(
                code="CASH_VS_DECLARED_REVENUE",
                severity=SEVERITY_CRITICAL,
                category="cross_source",
                message=(
                    f"High cash outflow ratio ({cash_ratio:.0%}) combined with low invoice match "
                    f"ratio ({invoice_match_ratio:.0%}) suggests off-book revenue."
                ),
                evidence={
                    "cash_withdrawal_ratio": cash_ratio,
                    "invoice_match_ratio": invoice_match_ratio,
                },
                source="cross_check",
            )
        )

    # GST sanity: invoice-implied tax presence vs CredCheck filing pattern
    tax_invoiced = sum(_safe_float(inv.get("tax_total", 0.0)) for inv in invoices)
    gst_status = str(credit_report.get("gst_filing_status", "unknown")).lower()
    if tax_invoiced > 0 and gst_status not in {"regular", "compliant", "good"}:
        findings.append(
            _make_finding(
                code="GST_INVOICE_VS_FILING",
                severity=SEVERITY_WARNING,
                category="cross_source",
                message=(
                    "Invoices include GST tax components, but CredCheck reports filing status "
                    f"as '{gst_status}'."
                ),
                evidence={
                    "tax_total": tax_invoiced,
                    "gst_status": gst_status,
                },
                source="cross_check",
                needs_borrower=False,
            )
        )

    summary = {
        "matched_count": len(matched),
        "unmatched_invoice_count": len(unmatched_invoices),
        "unmatched_credit_count": len(unmatched_credits),
        "invoice_match_ratio": round(invoice_match_ratio, 4),
        "revenue_triangulation": triang,
        "legal_counterparty_matches": matches,
    }

    risk_drivers = [f["message"] for f in findings if f["severity"] == SEVERITY_CRITICAL][:3]
    recommendation = "review"
    if any(f["severity"] == SEVERITY_CRITICAL for f in findings):
        recommendation = "reject"
    elif not findings:
        recommendation = "approve"

    explanation = (
        "Cross-check found no material reconciliation issues across invoices, bank statement and CredCheck."
        if not findings
        else f"Cross-check raised {len(findings)} reconciliation finding(s); see findings list for detail."
    )

    result = {
        "summary": summary,
        "matched_pairs": matched,
        "unmatched_invoices": unmatched_invoices,
        "unmatched_credits": unmatched_credits,
        "findings": findings,
        "risk_drivers": risk_drivers,
        "positive_signals": ["Sources reconcile cleanly"] if not findings else [],
        "uncertainties": [
            "Date window and amount tolerance for matching are heuristic; small reconciliation gaps may be benign."
        ],
        "recommendation": recommendation,
        "explanation": explanation,
    }
    return _with_handoff(result)


def _run_cross_check_llm(profile: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """LLM-augmented cross-check. Falls back to deterministic findings underneath."""
    deterministic = _run_cross_check_deterministic(profile, context)
    region = context.get("region", "Unknown")

    system_prompt = (
        "You are a reconciliation specialist. Compare invoices, bank credits and the CredCheck "
        "report. Return ONLY JSON with keys: explanation (string), risk_drivers (string list), "
        "positive_signals (string list), recommendation (approve|review|reject)."
    )
    user_prompt = (
        f"Region: {region}\n"
        f"Deterministic summary: {deterministic['summary']}\n"
        f"Deterministic findings: {deterministic['findings']}\n"
        "Synthesize a concise narrative."
    )
    try:
        payload = ask_llm_json(system_prompt=system_prompt, user_prompt=user_prompt)
        deterministic["explanation"] = str(payload.get("explanation", deterministic["explanation"]))
        if isinstance(payload.get("risk_drivers"), list):
            deterministic["risk_drivers"] = [str(x) for x in payload["risk_drivers"]][:5]
        if isinstance(payload.get("positive_signals"), list):
            deterministic["positive_signals"] = [str(x) for x in payload["positive_signals"]][:3]
        if isinstance(payload.get("recommendation"), str):
            deterministic["recommendation"] = payload["recommendation"]
        deterministic["mode"] = "llm"
    except Exception as exc:
        deterministic["mode"] = "deterministic_fallback"
        deterministic["llm_error"] = str(exc)
    return deterministic


def run_cross_check(
    profile: Dict[str, Any], context: Dict[str, Any], use_llm: bool = False
) -> Dict[str, Any]:
    """Reconcile invoices ↔ bank credits ↔ CredCheck and emit severity-tagged findings."""
    if not use_llm:
        result = _run_cross_check_deterministic(profile, context)
        result["mode"] = "deterministic"
        return result
    return _run_cross_check_llm(profile, context)
