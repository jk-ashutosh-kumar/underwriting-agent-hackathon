"""Simple decision flow (state machine style)."""

from __future__ import annotations


def make_decision(risk_score: float) -> str:
    """Return underwriting decision based on risk score threshold."""
    if risk_score > 7:
        return "HUMAN_REVIEW"
    return "APPROVED"
