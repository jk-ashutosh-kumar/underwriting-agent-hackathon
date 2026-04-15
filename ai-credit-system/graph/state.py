"""State schema for governed underwriting flow."""

from __future__ import annotations

from typing import Any, Dict, List, TypedDict


class UnderwritingState(TypedDict):
    """Shared case folder passed across all flow nodes."""

    applicant_data: Dict[str, Any]
    region: str
    risk_score: int
    agent_logs: List[str]
    human_input: str
    decision_status: str  # "PENDING", "APPROVED", "REJECTED", "FLAGGED"


def create_initial_state(data: Dict[str, Any], region: str) -> UnderwritingState:
    """Create the initial state for flow execution."""
    return {
        "applicant_data": data,
        "region": region,
        "risk_score": 0,
        "agent_logs": [],
        "human_input": "",
        "decision_status": "PENDING",
    }
