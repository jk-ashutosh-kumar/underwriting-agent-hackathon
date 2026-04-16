"""Unified financial profile builder for multi-source underwriting."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _normalize_credit_report(credit_data: Dict[str, Any] | None) -> Dict[str, Any]:
    """Normalize legacy and new credcheck report payloads to common keys."""
    payload = credit_data if isinstance(credit_data, dict) else {}
    credcheck = payload.get("credcheck_report")
    report = credcheck if isinstance(credcheck, dict) else payload

    tax_filing = report.get("tax_filing", {})
    tax_filing = tax_filing if isinstance(tax_filing, dict) else {}
    legal_profile = report.get("legal_profile", {})
    legal_profile = legal_profile if isinstance(legal_profile, dict) else {}
    by_company = legal_profile.get("cases_by_company", {})
    by_company = by_company if isinstance(by_company, dict) else {}
    against_company = legal_profile.get("cases_against_company", {})
    against_company = against_company if isinstance(against_company, dict) else {}
    gstr_delay = report.get("gstr3b_filing_delay", {})
    gstr_delay = gstr_delay if isinstance(gstr_delay, dict) else {}
    gstr_summary = gstr_delay.get("summary", {})
    gstr_summary = gstr_summary if isinstance(gstr_summary, dict) else {}

    legal_cases = _safe_int(
        report.get("legal_cases", by_company.get("total", 0)),
        default=0,
    )
    legal_cases_against = _safe_int(against_company.get("total", 0), default=0)
    on_time_filing_percent = _safe_int(
        tax_filing.get("on_time_filing_percent"),
        default=_safe_int(tax_filing.get("filing_last_12_months_percent"), 0),
    )
    has_delay = _safe_bool(
        tax_filing.get("has_delay"),
        default=_safe_bool(gstr_summary.get("total_delays"), False),
    )

    if "gst_filing_status" in payload:
        gst_filing_status = str(payload.get("gst_filing_status", "unknown"))
    elif has_delay:
        gst_filing_status = "irregular"
    elif on_time_filing_percent >= 95:
        gst_filing_status = "regular"
    else:
        gst_filing_status = "unknown"

    normalized = {
        "legal_cases": legal_cases,
        "legal_cases_against_company": legal_cases_against,
        "gst_filing_status": gst_filing_status,
        "gst_on_time_filing_percent": on_time_filing_percent,
        "gst_has_delay": has_delay,
        "past_defaults": _safe_int(payload.get("past_defaults", 0)),
        "report": report,
    }
    return normalized


def _normalize_invoices(invoice_data: Any) -> List[Dict[str, Any]]:
    """Normalize legacy list invoices and new nested invoice object payloads."""
    if isinstance(invoice_data, list):
        normalized: List[Dict[str, Any]] = []
        for inv in invoice_data:
            if not isinstance(inv, dict):
                continue
            amount = _safe_float(
                inv.get("amount", inv.get("total_amount", 0.0)),
                default=0.0,
            )
            date_val = inv.get("date", inv.get("invoice_date", ""))
            normalized.append(
                {
                    "invoice_id": str(
                        inv.get("invoice_id")
                        or inv.get("invoice_number")
                        or inv.get("id")
                        or ""
                    ),
                    "date": str(date_val or ""),
                    "amount": amount,
                    "customer": str(
                        inv.get("customer")
                        or inv.get("buyer_name")
                        or inv.get("buyer", {}).get("name")
                        or ""
                    ),
                    "status": str(
                        inv.get("status")
                        or inv.get("payment_status")
                        or "UNKNOWN"
                    ).upper(),
                    "raw": inv,
                }
            )
        return normalized

    if isinstance(invoice_data, dict):
        buyer = invoice_data.get("buyer", {})
        buyer = buyer if isinstance(buyer, dict) else {}
        payment = invoice_data.get("payment_details", {})
        payment = payment if isinstance(payment, dict) else {}
        amount_summary = invoice_data.get("amount_summary", {})
        amount_summary = amount_summary if isinstance(amount_summary, dict) else {}
        metadata = invoice_data.get("invoice_metadata", {})
        metadata = metadata if isinstance(metadata, dict) else {}

        amount_due = _safe_float(payment.get("amount_due"), default=0.0)
        amount_paid = _safe_float(payment.get("amount_paid"), default=0.0)
        total_amount = _safe_float(
            amount_summary.get("total_amount", amount_due + amount_paid),
            default=(amount_due + amount_paid),
        )
        if amount_due > 0:
            status = "PENDING"
        elif amount_paid >= total_amount > 0:
            status = "PAID"
        else:
            status = "UNKNOWN"

        return [
            {
                "invoice_id": str(metadata.get("invoice_number", "")),
                "date": str(metadata.get("invoice_date", "")),
                "amount": total_amount,
                "customer": str(buyer.get("name", "")),
                "status": status,
                "raw": invoice_data,
            }
        ]

    return []


def build_financial_profile(
    bank_data: Dict[str, Any] | None,
    invoice_data: Any,
    credit_data: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """Build a unified profile from bank, invoices, and credit report.

    Backward-compatible by tolerating missing invoice/credit sources.
    """
    bank = bank_data or {}
    invoices = _normalize_invoices(invoice_data)
    credit_report = _normalize_credit_report(credit_data)

    total_inflow = _safe_float(bank.get("total_inflow", 0.0))
    total_outflow = _safe_float(bank.get("total_outflow", 0.0))
    monthly_inflow = total_inflow
    monthly_outflow = total_outflow

    invoice_amounts = [_safe_float(inv.get("amount", 0.0)) for inv in invoices]
    total_invoice_volume = sum(invoice_amounts)
    avg_invoice_value = total_invoice_volume / len(invoice_amounts) if invoice_amounts else 0.0

    monthly_counts: Dict[str, int] = defaultdict(int)
    for inv in invoices:
        date_text = str(inv.get("date", ""))
        month = date_text[:7] if len(date_text) >= 7 else "unknown"
        monthly_counts[month] += 1
    invoice_frequency = int(round(sum(monthly_counts.values()) / max(len(monthly_counts), 1))) if invoices else 0

    profile = {
        "bank": bank,
        "invoices": invoices,
        "credit_report": credit_report,
        "derived_metrics": {
            "monthly_inflow": monthly_inflow,
            "monthly_outflow": monthly_outflow,
            "avg_invoice_value": avg_invoice_value,
            "invoice_frequency": invoice_frequency,
            "total_invoice_volume": total_invoice_volume,
            "gst_compliance": str(credit_report.get("gst_filing_status", "unknown")),
        },
    }
    return profile
