"""Unified financial profile builder for multi-source underwriting."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


# --------------------------------------------------------------------------- #
# Coercion helpers
# --------------------------------------------------------------------------- #


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


_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%d %B %Y",
    "%d %b %Y",
    "%B %d %Y",
    "%b %d %Y",
)


def _parse_date(text: Any) -> Optional[date]:
    if isinstance(text, date):
        return text
    if not isinstance(text, str) or not text.strip():
        return None
    text = text.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    # ISO with time component
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# Credit-report normalisation
# --------------------------------------------------------------------------- #


def _pick_latest_year_keyed(blob: Any) -> Tuple[Optional[str], Dict[str, Any]]:
    """Return (year, value-dict) for the highest-numeric-key year-keyed block."""
    if not isinstance(blob, dict):
        return None, {}
    year_entries = []
    for key, value in blob.items():
        if not isinstance(value, dict):
            continue
        try:
            year_entries.append((int(str(key)[:4]), str(key), value))
        except ValueError:
            continue
    if not year_entries:
        # Fallback: treat blob itself as the latest entry
        return None, blob
    year_entries.sort(key=lambda t: t[0], reverse=True)
    return year_entries[0][1], year_entries[0][2]


def _normalize_credit_report(credit_data: Dict[str, Any] | None) -> Dict[str, Any]:
    """Normalize legacy and new credcheck report payloads to common keys.

    Backward-compatible: returns all the keys the original implementation did
    plus a richer set used by the auditor and cross-check agent.
    """
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
    business_summary = report.get("business_summary", {})
    business_summary = business_summary if isinstance(business_summary, dict) else {}

    # Profit/Loss & balance sheet may be year-keyed in some payloads.
    pl_blob = report.get("profit_loss", {})
    bs_blob = report.get("balance_sheet", {})
    pl_year, pl_latest = _pick_latest_year_keyed(pl_blob if isinstance(pl_blob, dict) else {})
    bs_year, bs_latest = _pick_latest_year_keyed(bs_blob if isinstance(bs_blob, dict) else {})

    legal_cases = _safe_int(
        report.get("legal_cases", by_company.get("total", 0)),
        default=0,
    )
    legal_cases_against = _safe_int(against_company.get("total", 0), default=0)
    legal_cases_criminal = _safe_int(by_company.get("criminal", 0), default=0)
    on_time_filing_percent = _safe_int(
        tax_filing.get("on_time_filing_percent"),
        default=_safe_int(tax_filing.get("filing_last_12_months_percent"), 0),
    )
    has_delay = _safe_bool(
        tax_filing.get("has_delay"),
        default=_safe_bool(gstr_summary.get("total_delays"), False),
    )
    gst_total_delays = _safe_int(gstr_summary.get("total_delays"), default=0)
    gst_avg_delay_days = _safe_float(gstr_summary.get("average_delay_days"), default=0.0)

    if "gst_filing_status" in payload:
        gst_filing_status = str(payload.get("gst_filing_status", "unknown"))
    elif has_delay or gst_total_delays > 0:
        gst_filing_status = "irregular"
    elif on_time_filing_percent >= 95:
        gst_filing_status = "regular"
    else:
        gst_filing_status = "unknown"

    pl_revenue = _safe_float(pl_latest.get("revenue"), default=0.0)
    pl_pat = _safe_float(pl_latest.get("pat"), default=0.0)
    pl_ebitda = _safe_float(pl_latest.get("ebitda"), default=0.0)
    bs_total_assets = _safe_float(bs_latest.get("total_assets"), default=0.0)
    bs_equity = _safe_float(bs_latest.get("equity"), default=0.0)
    bs_current_liabilities = _safe_float(bs_latest.get("current_liabilities"), default=0.0)

    # Director/borrower defaults are sometimes nested under different keys.
    past_defaults = _safe_int(
        payload.get("past_defaults", report.get("past_defaults", 0)),
        default=0,
    )
    director_defaults = _safe_int(
        report.get("director_defaults", 0),
        default=0,
    )

    business = {
        "industry": str(business_summary.get("industry", "")),
        "business_type": str(business_summary.get("business_type", "")),
        "trade_name": str(business_summary.get("business_trade_name", business_summary.get("legal_name", ""))),
        "age_months": _safe_int(business_summary.get("age_of_business_months"), default=0),
        "incorporation_date": str(business_summary.get("incorporation_date_pan", business_summary.get("incorporation_date", ""))),
        "gst_number": str(business_summary.get("gst_number", tax_filing.get("gst_number", ""))),
        "pan_number": str(business_summary.get("pan_number", "")),
    }

    normalized = {
        # Backward-compatible keys
        "legal_cases": legal_cases,
        "legal_cases_against_company": legal_cases_against,
        "gst_filing_status": gst_filing_status,
        "gst_on_time_filing_percent": on_time_filing_percent,
        "gst_has_delay": has_delay,
        "past_defaults": past_defaults,
        "report": report,
        # New keys
        "legal_cases_criminal": legal_cases_criminal,
        "gst_total_delays": gst_total_delays,
        "gst_avg_delay_days": gst_avg_delay_days,
        "pl_latest_year": pl_year,
        "pl_latest_revenue": pl_revenue,
        "pl_latest_pat": pl_pat,
        "pl_latest_ebitda": pl_ebitda,
        "bs_latest_year": bs_year,
        "bs_latest_total_assets": bs_total_assets,
        "bs_latest_equity": bs_equity,
        "bs_latest_current_liabilities": bs_current_liabilities,
        "director_defaults": director_defaults,
        "business_summary": business,
    }
    return normalized


# --------------------------------------------------------------------------- #
# Invoice normalisation
# --------------------------------------------------------------------------- #


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
                    "tax_total": _safe_float(inv.get("tax_total", 0.0)),
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
        tax_details = invoice_data.get("tax_details", {})
        tax_details = tax_details if isinstance(tax_details, dict) else {}

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
                "tax_total": _safe_float(tax_details.get("total_tax", 0.0)),
                "payment_mode": str(payment.get("payment_mode", "")).upper(),
                "raw": invoice_data,
            }
        ]

    return []


# --------------------------------------------------------------------------- #
# Bank-side derived metrics (the part that was barely used before)
# --------------------------------------------------------------------------- #


_TOKEN_RE = re.compile(r"[A-Za-z]{3,}")
_CASH_HINTS = ("cash", "atm", "withdrawal", "wd ")
_NEFT_HINTS = ("neft", "imps", "rtgs", "upi", "transfer")


def _counterparty_token(description: str) -> str:
    """Pick a stable counterparty token from a transaction description."""
    if not description:
        return ""
    tokens = _TOKEN_RE.findall(description)
    skip = {"the", "for", "from", "and", "ltd", "pvt", "inc", "co"}
    meaningful = [t.lower() for t in tokens if t.lower() not in skip]
    return meaningful[0] if meaningful else (tokens[0].lower() if tokens else "")


def _is_credit(txn: Dict[str, Any]) -> bool:
    txn_type = str(txn.get("type", "")).strip().lower()
    if txn_type in {"credit", "cr"}:
        return True
    if txn_type in {"debit", "dr"}:
        return False
    # Fall back to credit/debit fields if present.
    if _safe_float(txn.get("credit", 0)) > 0:
        return True
    if _safe_float(txn.get("debit", 0)) > 0:
        return False
    # Default to credit if amount sign indicates it.
    return _safe_float(txn.get("amount", 0)) >= 0


def _is_cash_txn(description: str) -> bool:
    text = description.lower()
    return any(hint in text for hint in _CASH_HINTS)


def _bank_derived_metrics(bank: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the rich bank-statement signals downstream agents need."""
    transactions: List[Dict[str, Any]] = list(bank.get("transactions", []))

    flagged: List[Dict[str, Any]] = []
    flag_type_counts: Counter[str] = Counter()
    inflow_by_party: Counter[str] = Counter()
    outflow_by_party: Counter[str] = Counter()
    cash_outflow_total = 0.0
    total_inflow = 0.0
    total_outflow = 0.0
    weekday_count = 0
    weekend_count = 0
    txn_dates: List[date] = []

    credits: List[Tuple[Optional[date], float, str, Dict[str, Any]]] = []
    debits: List[Tuple[Optional[date], float, str, Dict[str, Any]]] = []
    largest_unexplained_credit = 0.0
    largest_unexplained_credit_txn: Optional[Dict[str, Any]] = None

    for txn in transactions:
        amount = _safe_float(txn.get("amount", 0.0))
        description = str(txn.get("description", ""))
        token = _counterparty_token(description)
        parsed_date = _parse_date(txn.get("date"))
        if parsed_date:
            txn_dates.append(parsed_date)
            if parsed_date.weekday() >= 5:
                weekend_count += 1
            else:
                weekday_count += 1

        if txn.get("flag"):
            flagged.append(
                {
                    "date": str(txn.get("date", "")),
                    "description": description,
                    "amount": amount,
                    "flag_type": str(txn.get("flag_type") or "unknown"),
                }
            )
            flag_type = str(txn.get("flag_type") or "unknown")
            flag_type_counts[flag_type] += 1

        if _is_credit(txn):
            total_inflow += amount
            inflow_by_party[token or "unknown"] += amount
            credits.append((parsed_date, amount, token, txn))
            if not description.strip() or "unknown" in description.lower() or "unexplained" in description.lower():
                if amount > largest_unexplained_credit:
                    largest_unexplained_credit = amount
                    largest_unexplained_credit_txn = txn
        else:
            total_outflow += amount
            outflow_by_party[token or "unknown"] += amount
            debits.append((parsed_date, amount, token, txn))
            if _is_cash_txn(description):
                cash_outflow_total += amount

    # Round-trip detection: same amount in/out within 3 days, same counterparty token.
    round_trip_pairs: List[Dict[str, Any]] = []
    for d_date, d_amount, d_token, d_txn in debits:
        for c_date, c_amount, c_token, c_txn in credits:
            if abs(d_amount - c_amount) > 1.0:
                continue
            if d_token and c_token and d_token != c_token:
                continue
            if d_date and c_date and abs((d_date - c_date).days) > 3:
                continue
            round_trip_pairs.append(
                {
                    "amount": d_amount,
                    "counterparty_token": d_token or c_token,
                    "credit_date": str(c_txn.get("date", "")),
                    "debit_date": str(d_txn.get("date", "")),
                    "credit_description": str(c_txn.get("description", "")),
                    "debit_description": str(d_txn.get("description", "")),
                }
            )

    inflow_concentration = 0.0
    top_inflow_counterparty = ""
    if total_inflow > 0 and inflow_by_party:
        top_party, top_amount = inflow_by_party.most_common(1)[0]
        inflow_concentration = top_amount / total_inflow
        top_inflow_counterparty = top_party

    cash_withdrawal_ratio = (cash_outflow_total / total_outflow) if total_outflow > 0 else 0.0

    if txn_dates:
        span_days = max((max(txn_dates) - min(txn_dates)).days, 1)
        txn_velocity = len(transactions) / span_days
    else:
        txn_velocity = 0.0

    weekday_vs_weekend = (weekday_count / weekend_count) if weekend_count else float(weekday_count)

    running_balance_consistent = not any(
        f["flag_type"] == "amount_mismatch" for f in flagged
    )

    return {
        "flagged_transactions": flagged,
        "flag_type_counts": dict(flag_type_counts),
        "round_trip_pairs": round_trip_pairs,
        "inflow_concentration": round(inflow_concentration, 4),
        "top_inflow_counterparty": top_inflow_counterparty,
        "cash_withdrawal_ratio": round(cash_withdrawal_ratio, 4),
        "cash_withdrawal_total": cash_outflow_total,
        "txn_velocity": round(txn_velocity, 4),
        "weekday_vs_weekend_ratio": round(weekday_vs_weekend, 4),
        "largest_unexplained_credit": largest_unexplained_credit,
        "largest_unexplained_credit_txn": largest_unexplained_credit_txn,
        "running_balance_consistent": running_balance_consistent,
        "credits_count": len(credits),
        "debits_count": len(debits),
    }


# --------------------------------------------------------------------------- #
# Public builder
# --------------------------------------------------------------------------- #


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

    bank_metrics = _bank_derived_metrics(bank)

    derived_metrics = {
        "monthly_inflow": monthly_inflow,
        "monthly_outflow": monthly_outflow,
        "avg_invoice_value": avg_invoice_value,
        "invoice_frequency": invoice_frequency,
        "total_invoice_volume": total_invoice_volume,
        "gst_compliance": str(credit_report.get("gst_filing_status", "unknown")),
    }
    # Merge bank-derived signals so downstream agents only read derived_metrics.
    derived_metrics.update(bank_metrics)

    profile = {
        "bank": bank,
        "invoices": invoices,
        "credit_report": credit_report,
        "derived_metrics": derived_metrics,
    }
    return profile
