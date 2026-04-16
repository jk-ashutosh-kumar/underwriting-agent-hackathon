"""Two-tier HITL nodes (Tier 1: internal analyst, Tier 2: external borrower).

Each node is non-blocking in API mode: when there are open questions the node
records them on the state and returns. The caller is responsible for re-invoking
the resume node once responses arrive (via API).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from agents.findings import (
    aggregate_findings,
    classify,
    generate_questions,
    split_unanswered_for_borrower,
)
from graph.state import UnderwritingState

logger = logging.getLogger(__name__)


# Bounded score impact for the async re-score path (per round).
ASYNC_RISK_DELTA_CAP = 10


def findings_router_node(state: UnderwritingState) -> UnderwritingState:
    """Aggregate agent findings and generate the question list.

    Replaces the old per-transaction router checks: source of truth for what
    needs human follow-up is now the findings list, not ad-hoc string matches.
    """
    committee = state.get("committee_output") or {}
    audit = committee.get("audit", committee.get("auditor", {}))
    cross_check = committee.get("cross_check", {})
    trend = committee.get("trend", {})
    benchmark = committee.get("benchmark", {})

    findings = aggregate_findings(audit, cross_check, trend, benchmark)
    questions = generate_questions(findings)

    state["findings"] = findings
    state["questions"] = questions
    state["pending_analyst_qids"] = [q["id"] for q in questions]

    buckets = classify(findings)
    state["agent_logs"].append(
        f"Findings: {len(buckets['critical'])} critical, "
        f"{len(buckets['non_critical'])} non-critical."
    )
    return state


def analyst_hitl_node(state: UnderwritingState) -> UnderwritingState:
    """Tier-1 HITL: surface pending questions to internal credit analyst.

    Non-blocking. If `analyst_responses` is empty, leaves state in
    `AWAITING_ANALYST` for the API to pause on. If responses are already
    present (e.g. injected for tests), folds them into questions.
    """
    questions: List[Dict[str, Any]] = state.get("questions", []) or []
    responses: Dict[str, str] = state.get("analyst_responses", {}) or {}

    for q in questions:
        if q["id"] in responses and q.get("status") == "pending":
            q["analyst_answer"] = responses[q["id"]]
            q["status"] = "answered_by_analyst"
            q["asked_to"] = "analyst"

    pending = [q["id"] for q in questions if q.get("status") == "pending"]
    state["pending_analyst_qids"] = pending
    state["hitl_stage"] = "analyst" if pending and not responses else "analyst_done"

    if pending and not responses:
        state["decision_status"] = "AWAITING_ANALYST"
        state["agent_logs"].append(
            f"Tier-1 HITL: {len(pending)} question(s) routed to internal analyst."
        )
    return state


def analyst_resume_node(state: UnderwritingState) -> UnderwritingState:
    """Process analyst answers and decide what (if anything) goes to the borrower."""
    questions: List[Dict[str, Any]] = state.get("questions", []) or []
    responses: Dict[str, str] = state.get("analyst_responses", {}) or {}

    answered_count = 0
    for q in questions:
        if q["id"] in responses and q.get("status") == "pending":
            q["analyst_answer"] = responses[q["id"]]
            q["status"] = "answered_by_analyst"
            q["asked_to"] = "analyst"
            answered_count += 1

    split = split_unanswered_for_borrower(questions)
    state["pending_borrower_qids_critical"] = split["critical"]
    state["pending_borrower_qids_async"] = split["async"]
    state["pending_analyst_qids"] = []

    state["agent_logs"].append(
        f"Tier-1 resume: analyst answered {answered_count}; "
        f"{len(split['critical'])} critical → blocking borrower; "
        f"{len(split['async'])} non-critical → async borrower."
    )
    return state


def borrower_blocking_node(state: UnderwritingState) -> UnderwritingState:
    """Tier-2 HITL (blocking): only triggered when critical questions remain.

    Records pending borrower questions and asks the API to pause. The decision
    node will short-circuit to AWAITING_BORROWER until they are answered.
    """
    pending_critical = state.get("pending_borrower_qids_critical", []) or []
    if not pending_critical:
        state["hitl_stage"] = "borrower_skipped"
        return state

    questions = state.get("questions", []) or []
    for q in questions:
        if q["id"] in pending_critical and q.get("status") == "pending":
            q["asked_to"] = "borrower"
            q["status"] = "escalated"

    state["hitl_stage"] = "borrower_blocking"
    state["decision_status"] = "AWAITING_BORROWER"
    state["agent_logs"].append(
        f"Tier-2 HITL (blocking): {len(pending_critical)} critical question(s) escalated to borrower."
    )
    return state


def borrower_blocking_resume_node(state: UnderwritingState) -> UnderwritingState:
    """Fold borrower answers for the blocking critical questions back into state."""
    questions = state.get("questions", []) or []
    responses = state.get("borrower_responses", {}) or {}

    answered = 0
    still_pending: List[str] = []
    for q in questions:
        if q["id"] in state.get("pending_borrower_qids_critical", []):
            if q["id"] in responses:
                q["borrower_answer"] = responses[q["id"]]
                q["status"] = "answered_by_borrower"
                answered += 1
            else:
                still_pending.append(q["id"])

    state["pending_borrower_qids_critical"] = still_pending

    # Apply a measured risk adjustment based on quality of the borrower response.
    delta = _score_response_quality(state, source="borrower", critical=True)
    state["risk_score"] = max(0, int(state.get("risk_score", 0)) + delta)
    state["agent_logs"].append(
        f"Tier-2 borrower resume (blocking): answered {answered}, risk_delta={delta}."
    )
    return state


def queue_async_borrower_node(state: UnderwritingState) -> UnderwritingState:
    """Mark non-critical questions as queued for async borrower follow-up.

    The pipeline does NOT wait for these — provisional decision will be issued.
    """
    pending_async = state.get("pending_borrower_qids_async", []) or []
    if not pending_async:
        return state

    questions = state.get("questions", []) or []
    for q in questions:
        if q["id"] in pending_async and q.get("status") == "pending":
            q["asked_to"] = "borrower_async"
            q["status"] = "escalated_async"

    state["agent_logs"].append(
        f"Tier-2 async: {len(pending_async)} non-critical question(s) queued for borrower."
    )
    state["is_provisional"] = True
    return state


def async_rescore_node(
    state: UnderwritingState,
    new_responses: Dict[str, str],
) -> Tuple[UnderwritingState, Dict[str, Any]]:
    """Process an async borrower batch and update score in-place.

    Does NOT re-run the full pipeline. Folds responses into questions, computes
    a bounded risk delta, and (if all async questions are answered) promotes
    PROVISIONAL_* → final.
    """
    questions = state.get("questions", []) or []
    pending_async = list(state.get("pending_borrower_qids_async", []) or [])

    answered = 0
    for q in questions:
        if q["id"] in new_responses and q["id"] in pending_async:
            q["borrower_answer"] = new_responses[q["id"]]
            q["status"] = "answered_by_borrower"
            pending_async.remove(q["id"])
            answered += 1

    state["borrower_responses"] = {**(state.get("borrower_responses") or {}), **new_responses}
    state["pending_borrower_qids_async"] = pending_async

    delta = _score_response_quality(state, source="borrower", critical=False)
    delta = max(-ASYNC_RISK_DELTA_CAP, min(ASYNC_RISK_DELTA_CAP, delta))
    new_score = max(0, int(state.get("risk_score", 0)) + delta)
    state["risk_score"] = new_score

    promoted = False
    if not pending_async:
        # All async questions resolved — promote provisional to final.
        current = str(state.get("decision_status", ""))
        if current == "PROVISIONAL_APPROVED":
            state["decision_status"] = "APPROVED"
            promoted = True
        elif current == "PROVISIONAL_REJECTED":
            state["decision_status"] = "REJECTED"
            promoted = True
        state["is_provisional"] = False

    state["agent_logs"].append(
        f"Async rescore: answered {answered}, delta={delta}, new_score={new_score}, "
        f"promoted={promoted}."
    )
    return state, {
        "answered": answered,
        "risk_delta": delta,
        "new_risk_score": new_score,
        "promoted": promoted,
        "decision_status": state.get("decision_status"),
        "remaining_async_qids": pending_async,
    }


# --------------------------------------------------------------------------- #
# Response-quality scoring (re-uses the existing keyword heuristics)
# --------------------------------------------------------------------------- #


_POSITIVE_MARKERS = (
    "invoice", "vendor", "salary", "tax", "gst", "rent", "loan", "emi",
    "client", "refund", "prepayment", "receipt", "contract", "po ",
)
_WEAK_MARKERS = (
    "dont know", "don't know", "not sure", "unknown", "cash", "friend",
    "personal", "just like that", "random", "no reason", "maybe",
)
_NEGATIVE_MARKERS = (
    "reject", "decline", "fraud", "suspicious", "fake", "illegal",
    "money laundering",
)


def _score_response_quality(
    state: UnderwritingState, *, source: str, critical: bool
) -> int:
    """Compute a bounded risk delta from the answers we have so far.

    Mirrors the heuristic in the legacy resume_node so behaviour stays
    explainable. Bounds:
      - blocking critical: ±15
      - non-critical async: ±ASYNC_RISK_DELTA_CAP (set by caller)
    """
    questions = state.get("questions", []) or []
    if source == "borrower":
        if critical:
            answers = [
                q.get("borrower_answer", "")
                for q in questions
                if q.get("status") == "answered_by_borrower"
                and q.get("severity") == "critical"
            ]
        else:
            answers = [
                q.get("borrower_answer", "")
                for q in questions
                if q.get("status") == "answered_by_borrower"
                and q.get("severity") != "critical"
            ]
    else:
        answers = [
            q.get("analyst_answer", "")
            for q in questions
            if q.get("status") == "answered_by_analyst"
        ]

    if not answers:
        return 0

    aggregate = " \n ".join(a or "" for a in answers).lower()
    quality = 0
    if len(aggregate) >= 24:
        quality += 1
    if any(m in aggregate for m in _POSITIVE_MARKERS):
        quality += 2
    if any(c.isdigit() for c in aggregate):
        quality += 1
    if any(m in aggregate for m in _WEAK_MARKERS):
        quality -= 2
    if any(m in aggregate for m in _NEGATIVE_MARKERS):
        quality -= 4

    if quality >= 5:
        delta = -6
    elif quality >= 3:
        delta = -4
    elif quality >= 1:
        delta = -2
    elif quality == 0:
        delta = 0
    elif quality >= -2:
        delta = 2
    else:
        delta = 12

    if any(m in aggregate for m in _NEGATIVE_MARKERS):
        delta = max(delta, 15)
        state["hitl_override"] = "reject"

    return delta
