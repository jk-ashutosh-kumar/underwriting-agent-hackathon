"""Tests for findings aggregation, classification and question generation."""

from __future__ import annotations

from agents.findings import (
    aggregate_findings,
    classify,
    generate_questions,
    split_unanswered_for_borrower,
)


def _finding(code, severity="warning", **extra):
    base = {
        "code": code,
        "severity": severity,
        "category": "test",
        "message": f"{code} message",
        "evidence": {},
        "needs_borrower": True,
    }
    base.update(extra)
    return base


def test_aggregate_dedupes_same_code_and_evidence():
    audit = {"findings": [_finding("LARGE_TRANSACTION", evidence={"transaction": {"id": 1}})]}
    cross = {"findings": [_finding("LARGE_TRANSACTION", evidence={"transaction": {"id": 1}})]}
    result = aggregate_findings(audit, cross)
    assert len(result) == 1
    assert result[0]["id"] == "F-001"


def test_aggregate_assigns_stable_ids_in_order():
    audit = {"findings": [_finding("HIGH_CASH_RATIO"), _finding("REPEATED_AMOUNT_PATTERN")]}
    result = aggregate_findings(audit)
    assert [f["id"] for f in result] == ["F-001", "F-002"]


def test_severity_overrides_apply_central_catalogue():
    audit = {
        "findings": [
            _finding("TAMPERING_BALANCE_MISMATCH", severity="warning"),  # should be promoted
            _finding("LEGAL_CASES_BY_COMPANY", severity="critical"),    # should be demoted
        ]
    }
    result = aggregate_findings(audit)
    by_code = {f["code"]: f for f in result}
    assert by_code["TAMPERING_BALANCE_MISMATCH"]["severity"] == "critical"
    assert by_code["LEGAL_CASES_BY_COMPANY"]["severity"] == "warning"


def test_classify_splits_critical_and_non_critical():
    findings = [
        {"code": "A", "severity": "critical"},
        {"code": "B", "severity": "warning"},
        {"code": "C", "severity": "info"},
    ]
    buckets = classify(findings)
    assert {f["code"] for f in buckets["critical"]} == {"A"}
    assert {f["code"] for f in buckets["non_critical"]} == {"B", "C"}


def test_generate_questions_one_per_finding():
    findings = aggregate_findings({"findings": [_finding("HIGH_CASH_RATIO"), _finding("LARGE_TRANSACTION")]})
    questions = generate_questions(findings)
    assert len(questions) == 2
    assert questions[0]["finding_id"] == "F-001"
    assert questions[0]["status"] == "pending"
    assert questions[0]["text"]


def test_split_unanswered_routes_critical_vs_async():
    findings = aggregate_findings(
        {
            "findings": [
                _finding("PAST_DEFAULTS_PRESENT", severity="critical"),
                _finding("HIGH_CASH_RATIO", severity="warning", needs_borrower=False),
                _finding("UNINVOICED_INFLOW", severity="warning"),
            ]
        }
    )
    questions = generate_questions(findings)
    split = split_unanswered_for_borrower(questions)
    # PAST_DEFAULTS_PRESENT → critical; UNINVOICED_INFLOW → async; HIGH_CASH_RATIO skipped (needs_borrower=False)
    assert len(split["critical"]) == 1
    assert len(split["async"]) == 1
