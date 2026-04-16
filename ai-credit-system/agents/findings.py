"""Findings aggregator and question generator for the two-tier HITL flow."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List


# Single source of truth for which finding codes are critical (block) vs
# non-critical (allow provisional decision, async update).
# Keep the catalogue as a flat dict so it is easy to retune without touching code.
SEVERITY_OVERRIDES: Dict[str, str] = {
    "TAMPERING_BALANCE_MISMATCH": "critical",
    "LARGE_UNEXPLAINED_CREDIT": "critical",
    "ROUND_TRIPPING_DETECTED": "critical",
    "PAST_DEFAULTS_PRESENT": "critical",
    "DIRECTOR_DEFAULTS": "critical",
    "LEGAL_CASES_AGAINST_COMPANY": "critical",
    "LEGAL_CRIMINAL_CASES": "critical",
    "LEGAL_COUNTERPARTY_MATCH": "critical",
    "REVENUE_TRIANGULATION_MAJOR": "critical",
    "INVOICE_UNMATCHED_MAJOR": "critical",
    "CASH_VS_DECLARED_REVENUE": "critical",
    "GST_DELAY_SEVERE": "critical",
    "MISSING_CORE_FIELD": "critical",
    # Non-critical:
    "INVOICE_UNMATCHED": "warning",
    "UNINVOICED_INFLOW": "warning",
    "REVENUE_TRIANGULATION_MINOR": "warning",
    "HIGH_CASH_RATIO": "warning",
    "COUNTERPARTY_CONCENTRATION": "warning",
    "GST_DELAY_MILD": "warning",
    "GST_INVOICE_VS_FILING": "warning",
    "REPEATED_AMOUNT_PATTERN": "warning",
    "LARGE_TRANSACTION": "warning",
    "INVOICE_INFLOW_MISMATCH": "warning",
    "LEGAL_CASES_BY_COMPANY": "warning",
    "INVOICE_FREQUENCY_DRIFT": "info",
}


def _normalize_severity(finding: Dict[str, Any]) -> str:
    """Apply central severity catalogue, falling back to the agent's own tag."""
    code = str(finding.get("code", ""))
    if code in SEVERITY_OVERRIDES:
        return SEVERITY_OVERRIDES[code]
    return str(finding.get("severity", "info"))


def aggregate_findings(*sources: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Combine findings from multiple agent outputs into a deduped, id-tagged list.

    Each source is an agent output dict (auditor, cross_check, ...). Findings are
    re-tagged with the central severity catalogue and assigned stable ids.
    """
    aggregated: List[Dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()

    for source in sources:
        if not isinstance(source, dict):
            continue
        for finding in source.get("findings", []) or []:
            if not isinstance(finding, dict):
                continue
            code = str(finding.get("code", ""))
            evidence = finding.get("evidence") or {}
            # Dedupe key: (code, first stable evidence value if present)
            evidence_signature = ""
            if isinstance(evidence, dict) and evidence:
                first_val = next(iter(evidence.values()))
                evidence_signature = str(first_val)[:80]
            key = (code, evidence_signature)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            normalized = dict(finding)
            normalized["severity"] = _normalize_severity(finding)
            normalized["id"] = f"F-{len(aggregated) + 1:03d}"
            aggregated.append(normalized)

    return aggregated


def classify(findings: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Split findings into critical (blocking) vs non_critical (async)."""
    critical: List[Dict[str, Any]] = []
    non_critical: List[Dict[str, Any]] = []
    for finding in findings:
        if str(finding.get("severity", "info")) == "critical":
            critical.append(finding)
        else:
            non_critical.append(finding)
    return {"critical": critical, "non_critical": non_critical}


# --------------------------------------------------------------------------- #
# Question templates
# --------------------------------------------------------------------------- #

# Template per finding code. {message} is always available; agents can rely on it
# even when no specific template exists.
_QUESTION_TEMPLATES: Dict[str, str] = {
    "TAMPERING_BALANCE_MISMATCH": (
        "The bank statement shows a running-balance mismatch on {date} "
        "({description} for {amount}). Can you confirm the source statement is unaltered "
        "and provide the original PDF or bank-portal export?"
    ),
    "LARGE_UNEXPLAINED_CREDIT": (
        "An unexplained credit of {amount} appears on {date}. What was the source "
        "of this deposit and can you provide supporting documentation (invoice, contract, etc.)?"
    ),
    "LARGE_TRANSACTION": (
        "Please clarify the nature and counterparty of the large transaction "
        "{description} on {date} for {amount}."
    ),
    "ROUND_TRIPPING_DETECTED": (
        "We detected matching in/out transfers within a few days. Please explain the "
        "business reason for these movements and provide counterparty details."
    ),
    "REPEATED_AMOUNT_PATTERN": (
        "We see repeated identical transaction amounts. Are these scheduled payments "
        "(rent, EMI, salary) or something else?"
    ),
    "INVOICE_UNMATCHED": (
        "We could not match {count} invoice(s) to bank deposits. Were these invoices "
        "paid in cash, via a different account, or are they still outstanding?"
    ),
    "INVOICE_UNMATCHED_MAJOR": (
        "A majority of invoices ({count}) had no matching bank credit. Please share the "
        "alternate settlement records or correct the invoice payment status."
    ),
    "UNINVOICED_INFLOW": (
        "A material portion of bank inflow ({amount}) has no corresponding invoice. "
        "What was the source — capital injection, loan, or other revenue?"
    ),
    "REVENUE_TRIANGULATION_MAJOR": (
        "Reported revenue across invoices, bank inflow and CredCheck disagrees by a wide "
        "margin. Please share the audited financial statement and reconciliation."
    ),
    "REVENUE_TRIANGULATION_MINOR": (
        "Revenue figures across invoices, bank inflow and CredCheck differ moderately. "
        "Can you explain the gap (timing differences, off-account settlement, etc.)?"
    ),
    "INVOICE_INFLOW_MISMATCH": (
        "Declared invoice volume is far higher than observed bank inflow. Please clarify "
        "whether collections are being routed through a different account."
    ),
    "PAST_DEFAULTS_PRESENT": (
        "CredCheck shows {count} past default(s). Please describe each default, the "
        "current status, and any settlement evidence."
    ),
    "DIRECTOR_DEFAULTS": (
        "CredCheck reports defaults associated with director(s). Please share details "
        "and any settlement letters or NOCs."
    ),
    "LEGAL_CASES_AGAINST_COMPANY": (
        "CredCheck shows {count} legal case(s) filed against the company. Provide a "
        "case summary and counsel opinion on the likely outcome."
    ),
    "LEGAL_CASES_BY_COMPANY": (
        "The company is plaintiff in {count} legal case(s). Please provide a brief on "
        "the most material disputes."
    ),
    "LEGAL_CRIMINAL_CASES": (
        "Criminal legal cases are present in CredCheck. Please share details and "
        "the current status of each."
    ),
    "LEGAL_COUNTERPARTY_MATCH": (
        "Counterparties on the bank statement also appear in legal-case records. "
        "Please confirm there is no related-party / disputed-counterparty exposure."
    ),
    "GST_DELAY_SEVERE": (
        "GST filings have been delayed many times (avg {avg_delay_days} days). What is "
        "driving the irregularity and what is the remediation plan?"
    ),
    "GST_DELAY_MILD": (
        "GST filing status is {status}. Could you clarify the recent filing pattern?"
    ),
    "GST_INVOICE_VS_FILING": (
        "Invoices include GST, but CredCheck shows GST status as {status}. Please "
        "reconcile and share recent return acknowledgements."
    ),
    "HIGH_CASH_RATIO": (
        "Cash withdrawals are {ratio} of total outflow. What are these cash payments for?"
    ),
    "COUNTERPARTY_CONCENTRATION": (
        "Top counterparty contributes {concentration} of inflow ({counterparty}). "
        "Is there contractual continuity / diversification planned?"
    ),
    "CASH_VS_DECLARED_REVENUE": (
        "High cash-outflow ratio combined with low invoice-coverage suggests off-book "
        "revenue. Please share the full cash ledger or reconciled invoices."
    ),
    "MISSING_CORE_FIELD": (
        "A core data field is missing. Please provide: {field}."
    ),
}

_DEFAULT_TEMPLATE = (
    "Please provide context for the following finding: {message}"
)


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def _format_template(template: str, finding: Dict[str, Any]) -> str:
    """Best-effort template fill using finding evidence + message + top-level fields."""
    evidence = finding.get("evidence") or {}
    txn = evidence.get("transaction") if isinstance(evidence, dict) else None
    txn = txn if isinstance(txn, dict) else {}
    fmt_kwargs: Dict[str, str] = {
        "message": str(finding.get("message", "")),
        "date": _format_value(txn.get("date", evidence.get("date", ""))),
        "amount": _format_value(txn.get("amount", evidence.get("amount", ""))),
        "description": _format_value(txn.get("description", "")),
        "count": _format_value(evidence.get("count", evidence.get("unmatched_invoice_count", ""))),
        "ratio": _format_value(evidence.get("cash_withdrawal_ratio", evidence.get("ratio", ""))),
        "concentration": _format_value(evidence.get("concentration", "")),
        "counterparty": _format_value(evidence.get("counterparty", evidence.get("counterparties", ""))),
        "avg_delay_days": _format_value(evidence.get("avg_delay_days", "")),
        "status": _format_value(evidence.get("status", evidence.get("gst_status", ""))),
        "field": _format_value(evidence.get("field", "")),
    }
    try:
        return template.format(**fmt_kwargs)
    except (KeyError, IndexError):
        return _DEFAULT_TEMPLATE.format(message=str(finding.get("message", "")))


def generate_questions(findings: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Produce one question per finding using template-fill (LLM optional later)."""
    questions: List[Dict[str, Any]] = []
    timestamp = datetime.now(timezone.utc).isoformat()
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        code = str(finding.get("code", ""))
        template = _QUESTION_TEMPLATES.get(code, _DEFAULT_TEMPLATE)
        text = _format_template(template, finding)
        questions.append(
            {
                "id": f"Q-{len(questions) + 1:03d}",
                "finding_id": finding.get("id"),
                "finding_code": code,
                "severity": finding.get("severity", "info"),
                "category": finding.get("category", ""),
                "tier": "analyst_first",
                "needs_borrower": bool(finding.get("needs_borrower", True)),
                "text": text,
                "context": {
                    "evidence": finding.get("evidence", {}),
                    "source": finding.get("source"),
                },
                "asked_at": timestamp,
                "asked_to": None,  # set by HITL nodes when routed
                "status": "pending",  # pending | answered_by_analyst | escalated | answered_by_borrower
                "analyst_answer": None,
                "borrower_answer": None,
            }
        )
    return questions


def split_unanswered_for_borrower(
    questions: Iterable[Dict[str, Any]],
) -> Dict[str, List[str]]:
    """After analyst tier, decide which qids go to the borrower (critical/async)."""
    critical_qids: List[str] = []
    async_qids: List[str] = []
    for q in questions:
        if q.get("status") in {"answered_by_analyst", "answered_by_borrower"}:
            continue
        if not q.get("needs_borrower", True):
            continue
        if q.get("severity") == "critical":
            critical_qids.append(q["id"])
        else:
            async_qids.append(q["id"])
    return {"critical": critical_qids, "async": async_qids}
