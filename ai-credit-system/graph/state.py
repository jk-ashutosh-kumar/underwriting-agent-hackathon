"""State schema for governed underwriting flow."""

from __future__ import annotations

from typing import Any, Dict, List, TypedDict


class UnderwritingState(TypedDict, total=False):
    """Shared case folder passed across all flow nodes.

    `total=False` so callers may construct a partial state — `create_initial_state`
    fills the canonical defaults.
    """

    applicant_data: Dict[str, Any]
    region: str
    risk_score: int
    agent_logs: List[str]
    human_input: str
    decision_status: str  # PENDING | APPROVED | REJECTED | FLAGGED |
                          # PROVISIONAL_APPROVED | PROVISIONAL_REJECTED |
                          # AWAITING_ANALYST | AWAITING_BORROWER

    # Cached crew output (so the API doesn't re-run agents on resume).
    committee_output: Dict[str, Any]
    hitl_context: Dict[str, Any]
    hitl_override: str

    # Two-tier HITL bookkeeping
    findings: List[Dict[str, Any]]
    questions: List[Dict[str, Any]]
    analyst_responses: Dict[str, str]
    borrower_responses: Dict[str, str]
    pending_analyst_qids: List[str]
    pending_borrower_qids_critical: List[str]
    pending_borrower_qids_async: List[str]
    hitl_stage: str           # none | analyst | borrower_blocking | borrower_async | complete
    is_provisional: bool


def create_initial_state(data: Dict[str, Any], region: str) -> UnderwritingState:
    """Create the initial state for flow execution."""
    return {
        "applicant_data": data,
        "region": region,
        "risk_score": 0,
        "agent_logs": [],
        "human_input": "",
        "decision_status": "PENDING",
        "findings": [],
        "questions": [],
        "analyst_responses": {},
        "borrower_responses": {},
        "pending_analyst_qids": [],
        "pending_borrower_qids_critical": [],
        "pending_borrower_qids_async": [],
        "hitl_stage": "none",
        "is_provisional": False,
    }
