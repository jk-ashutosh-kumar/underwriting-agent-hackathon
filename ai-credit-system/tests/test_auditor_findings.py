"""Tests for the enhanced auditor findings emission."""

from __future__ import annotations

from agents.auditor import run_auditor
from data.unified_schema import build_financial_profile


def _bank(transactions):
    return {"transactions": transactions, "total_inflow": sum(t.get("amount", 0) for t in transactions if t.get("type") == "credit"), "total_outflow": 0}


def test_parser_flag_propagates_to_critical_finding():
    bank = _bank(
        [
            {
                "date": "2026-03-01",
                "description": "Suspicious",
                "amount": 5000,
                "type": "credit",
                "flag": True,
                "flag_type": "amount_mismatch",
            }
        ]
    )
    profile = build_financial_profile(bank, [], {})
    result = run_auditor(profile, {"large_txn_threshold": 100000})
    codes = [f["code"] for f in result["findings"]]
    assert "TAMPERING_BALANCE_MISMATCH" in codes
    tamper = next(f for f in result["findings"] if f["code"] == "TAMPERING_BALANCE_MISMATCH")
    assert tamper["severity"] == "critical"


def test_round_tripping_emits_finding():
    bank = _bank(
        [
            {"date": "2026-03-01", "description": "Acme Corp Receipt", "amount": 50000, "type": "credit"},
            {"date": "2026-03-02", "description": "Acme Corp Refund", "amount": 50000, "type": "debit"},
            {"date": "2026-03-03", "description": "Beta Co Receipt", "amount": 70000, "type": "credit"},
            {"date": "2026-03-04", "description": "Beta Co Refund", "amount": 70000, "type": "debit"},
        ]
    )
    profile = build_financial_profile(bank, [], {})
    result = run_auditor(profile, {"large_txn_threshold": 1_000_000})
    codes = [f["code"] for f in result["findings"]]
    assert "ROUND_TRIPPING_DETECTED" in codes


def test_legal_against_company_is_critical():
    bank = _bank([])
    credit = {"credcheck_report": {"legal_profile": {"cases_against_company": {"total": 3}}}}
    profile = build_financial_profile(bank, [], credit)
    result = run_auditor(profile, {"large_txn_threshold": 100000})
    against = next(f for f in result["findings"] if f["code"] == "LEGAL_CASES_AGAINST_COMPANY")
    assert against["severity"] == "critical"


def test_no_findings_clean_profile():
    bank = _bank([{"date": "2026-03-01", "description": "Salary", "amount": 5000, "type": "debit"}])
    profile = build_financial_profile(bank, [], {})
    result = run_auditor(profile, {"large_txn_threshold": 1_000_000})
    assert result["findings"] == []
    assert result["recommendation"] == "approve"
