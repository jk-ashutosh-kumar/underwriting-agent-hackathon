"""Tests for the cross-check agent."""

from __future__ import annotations

from agents.cross_check import run_cross_check
from data.unified_schema import build_financial_profile


def _profile(bank, invoices=None, credit=None):
    return build_financial_profile(bank, invoices or [], credit or {})


def test_unmatched_invoice_triggers_finding():
    bank = {
        "transactions": [
            {"date": "2026-03-01", "description": "Retail", "amount": 10000, "type": "credit"},
        ],
        "total_inflow": 10000,
        "total_outflow": 0,
    }
    invoices = [
        {"invoice_id": "INV-1", "date": "2026-03-10", "amount": 50000},
    ]
    profile = _profile(bank, invoices=invoices)
    result = run_cross_check(profile, {"region": "India"})
    codes = [f["code"] for f in result["findings"]]
    assert "INVOICE_UNMATCHED_MAJOR" in codes or "INVOICE_UNMATCHED" in codes
    assert result["summary"]["unmatched_invoice_count"] == 1


def test_matched_invoice_has_no_unmatched_finding():
    bank = {
        "transactions": [
            {"date": "2026-03-10", "description": "Client Receipt", "amount": 50000, "type": "credit"},
        ],
        "total_inflow": 50000,
        "total_outflow": 0,
    }
    invoices = [
        {"invoice_id": "INV-1", "date": "2026-03-09", "amount": 50000},
    ]
    profile = _profile(bank, invoices=invoices)
    result = run_cross_check(profile, {"region": "India"})
    codes = [f["code"] for f in result["findings"]]
    assert "INVOICE_UNMATCHED" not in codes
    assert "INVOICE_UNMATCHED_MAJOR" not in codes
    assert result["summary"]["matched_count"] == 1


def test_revenue_triangulation_major_mismatch():
    bank = {
        "transactions": [{"date": "2026-03-01", "description": "Sale", "amount": 1_000, "type": "credit"}],
        "total_inflow": 1_000,  # → annualised 12_000
        "total_outflow": 0,
    }
    invoices = [
        {"invoice_id": "A", "date": "2026-03-01", "amount": 100_000},
    ]
    credit = {
        "credcheck_report": {
            "profit_loss": {"revenue": 10_000_000},
        }
    }
    profile = _profile(bank, invoices=invoices, credit=credit)
    result = run_cross_check(profile, {"region": "India"})
    codes = [f["code"] for f in result["findings"]]
    assert "REVENUE_TRIANGULATION_MAJOR" in codes


def test_deterministic_mode_is_default():
    result = run_cross_check(_profile({"transactions": []}), {"region": "India"})
    assert result["mode"] == "deterministic"
