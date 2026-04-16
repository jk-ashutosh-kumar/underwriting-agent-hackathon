"""Governed underwriting flow with two-tier HITL and critical/non-critical routing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from agents.credit_limit import (
    credit_limit_agent_log_lines,
    recommend_credit_limit_with_context,
)
from agents.crew import run_crew
from graph.hitl_nodes import (
    analyst_hitl_node,
    analyst_resume_node,
    borrower_blocking_node,
    borrower_blocking_resume_node,
    findings_router_node,
    queue_async_borrower_node,
)
from graph.state import UnderwritingState, create_initial_state
from memory.checkpoint import save_checkpoint

ROOT_DIR = Path(__file__).resolve().parents[1]
SAMPLE_DATA_FILE = ROOT_DIR / "data" / "sample_statement.json"
REGIONAL_POLICY_FILE = ROOT_DIR / "data" / "regional_policy.json"

# UI pipeline indices
_PROGRESS_INDEX = {
    "ingesting": 0,
    "analysis": 1,
    "cross_check": 1,
    "findings": 2,
    "analyst_hitl": 3,
    "analyst_hitl_skipped": 3,
    "analyst_resume": 4,
    "analyst_resume_skipped": 4,
    "borrower_hitl_blocking": 5,
    "borrower_hitl_skipped": 5,
    "borrower_async_queued": 5,
    "deciding": 6,
    "provisional_decision": 6,
    "checkpoint": 7,
    # Legacy step names kept so older UI clients don't break.
    "router": 2,
    "router_done": 2,
    "hitl": 3,
    "hitl_skipped": 3,
    "resume": 4,
    "resume_skipped": 4,
}


def _progress_event(step: str, phase: str, label: str, **extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "type": "progress",
        "phase": phase,
        "step": step,
        "label": label,
        "active_index": _PROGRESS_INDEX.get(step, 0),
    }
    payload.update(extra)
    return payload


def _load_regional_policy() -> Dict[str, Any]:
    if not REGIONAL_POLICY_FILE.exists():
        return {"India": {"cash_threshold": 50000, "flag_keywords": []}}
    with REGIONAL_POLICY_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _normalized_risk_for_rules(risk_score: int) -> int:
    bounded = max(0, min(100, int(risk_score)))
    return int(round(bounded / 10))


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #


def run_analysis_node(state: UnderwritingState) -> UnderwritingState:
    """Run multi-agent committee + cross-check + findings aggregation."""
    committee_output = run_crew(state["applicant_data"], region=state["region"])
    audit = committee_output.get("audit", committee_output.get("auditor", {}))
    trend = committee_output.get("trend", {})
    benchmark = committee_output.get("benchmark", {})
    cross_check = committee_output.get("cross_check", {})
    findings = committee_output.get("findings", [])

    state["risk_score"] = int(audit.get("risk_score", 0))
    state["agent_logs"].append(f"Auditor: {audit.get('explanation', 'No explanation provided.')}")
    state["agent_logs"].append(f"Trend: {trend.get('insight', 'No trend insight provided.')}")
    state["agent_logs"].append(
        f"Benchmark: {benchmark.get('comparison_insight', 'No benchmark insight provided.')}"
    )
    state["agent_logs"].append(
        f"Cross-check: {cross_check.get('explanation', 'No cross-check explanation.')}"
    )

    final_summary = committee_output.get("final_summary")
    if final_summary:
        state["agent_logs"].append(f"Committee: {final_summary}")

    state["committee_output"] = committee_output  # type: ignore[assignment]
    state["findings"] = findings
    return state


# Legacy router_node retained for backward-compat callers (LangGraph adapter,
# tests, etc.). The new flow uses findings_router_node + HITL nodes instead.
def router_node(state: UnderwritingState) -> str:
    """Legacy per-transaction router — superseded by findings_router_node."""
    policy = _load_regional_policy()
    state["hitl_context"] = None  # type: ignore[assignment]
    region_policy = policy.get(state["region"], policy.get("India", {}))
    amount_threshold = float(region_policy.get("cash_threshold", 50000))
    transactions: List[Dict[str, Any]] = state["applicant_data"].get("transactions", [])

    for txn in transactions:
        description = str(txn.get("description", "")).strip()
        amount = float(txn.get("amount", 0))
        if not description:
            state["decision_status"] = "FLAGGED"
            state["hitl_context"] = {  # type: ignore[assignment]
                "reason": "missing_description",
                "transaction": txn,
                "message": "Transaction description is missing.",
            }
            state["agent_logs"].append("Router: Missing transaction description detected -> FLAGGED.")
            return "hitl"
        if amount > amount_threshold:
            state["decision_status"] = "FLAGGED"
            state["hitl_context"] = {  # type: ignore[assignment]
                "reason": "large_transaction",
                "transaction": txn,
                "threshold": amount_threshold,
                "message": f"Amount {amount:.2f} exceeds threshold {amount_threshold:.2f}.",
            }
            state["agent_logs"].append(
                f"Router: Large transaction {amount:.2f} above threshold {amount_threshold:.2f} -> FLAGGED."
            )
            return "hitl"

    normalized_risk = _normalized_risk_for_rules(state["risk_score"])
    if normalized_risk < 4:
        state["decision_status"] = "APPROVED"
        return "approve"
    if normalized_risk > 7:
        state["decision_status"] = "PENDING"
        return "review"
    state["decision_status"] = "PENDING"
    return "review"


# Legacy single-tier HITL retained for backward-compat callers.
def hitl_node(
    state: UnderwritingState, interactive: bool = True, human_response: str = ""
) -> UnderwritingState:
    print("⚠️ Action Required: Suspicious transaction detected")
    save_checkpoint(state)
    if interactive:
        user_response = input("Explain this transaction: ").strip()
    else:
        user_response = human_response.strip() or "No clarification provided"
    state["human_input"] = user_response
    state["agent_logs"].append(f"HITL: User explanation captured -> {user_response}")
    return state


def resume_node(state: UnderwritingState) -> UnderwritingState:
    """Legacy single-tier resume — keyword-based delta to risk score."""
    clarification = state.get("human_input", "").strip() or "No clarification provided"
    state["agent_logs"].append(f"Resume: User clarified -> {clarification}")

    text = clarification.lower()
    positive_markers = [
        "invoice", "vendor", "salary", "tax", "gst", "rent", "loan", "emi",
        "client", "refund", "prepayment", "receipt",
    ]
    weak_markers = [
        "dont know", "don't know", "not sure", "unknown", "cash", "friend",
        "personal", "just like that", "random", "no reason", "maybe",
    ]
    negative_markers = [
        "reject", "decline", "fraud", "suspicious", "fake", "illegal", "money laundering",
    ]

    has_numeric_context = any(ch.isdigit() for ch in clarification)
    has_transaction_context = any(k in text for k in ["txn", "transaction", "transfer", "payment", "ref", "utr"])
    has_commercial_context = any(k in text for k in positive_markers)
    has_negative_signal = any(k in text for k in negative_markers)
    has_weak_signal = any(k in text for k in weak_markers)

    quality_score = 0
    if len(clarification) >= 24:
        quality_score += 1
    if has_commercial_context:
        quality_score += 2
    if has_numeric_context:
        quality_score += 1
    if has_transaction_context:
        quality_score += 1
    if has_weak_signal:
        quality_score -= 2
    if has_negative_signal:
        quality_score -= 4

    if quality_score >= 5:
        delta, note = -6, "strong documentary/commercial explanation"
    elif quality_score >= 3:
        delta, note = -4, "reasonable explanation"
    elif quality_score >= 1:
        delta, note = -2, "partial explanation"
    elif quality_score == 0:
        delta, note = 0, "neutral explanation"
    elif quality_score >= -2:
        delta, note = 2, "weak explanation"
    else:
        delta, note = 12, "negative/suspicious explanation"

    if has_negative_signal:
        delta = max(delta, 15)
        state["hitl_override"] = "reject"  # type: ignore[assignment]
        note = f"{note}; reject override armed"

    state["risk_score"] = max(0, int(state["risk_score"]) + delta)
    state["agent_logs"].append(
        f"Resume: Clarification quality={quality_score} ({note}); risk delta={delta}. "
        f"New risk={state['risk_score']} (lower is better)."
    )
    return state


def _apply_credit_limit_post_decision(state: UnderwritingState) -> None:
    co = state.get("committee_output")
    if not isinstance(co, dict):
        return

    audit = co.get("audit", co.get("auditor", {}))
    trend = co.get("trend", {})
    unified = co.get("unified_profile")
    if not isinstance(audit, dict):
        audit = {}
    if not isinstance(trend, dict):
        trend = {}
    if not isinstance(unified, dict):
        unified = {}

    chair = co.get("committee_chair")
    status = str(state.get("decision_status", ""))
    hitl_override = state.get("hitl_override") if state.get("hitl_override") == "reject" else None

    cl = recommend_credit_limit_with_context(
        unified,
        audit,
        trend,
        decision_status=status,
        hitl_override=hitl_override,
    )
    co["credit_limit"] = cl
    if isinstance(chair, dict):
        chair["credit_limit_reasoning"] = str(cl.get("reasoning", ""))
    for line in credit_limit_agent_log_lines(cl):
        state["agent_logs"].append(line)


def decision_node(state: UnderwritingState) -> UnderwritingState:
    """Final/provisional decision based on findings + HITL state."""
    if state.get("hitl_override") == "reject":
        state["decision_status"] = "REJECTED"
        state["agent_logs"].append(
            "Decision: HITL override requested rejection due to negative clarification."
        )
        _apply_credit_limit_post_decision(state)
        return state

    # Critical questions still open with the borrower → no decision yet.
    if state.get("pending_borrower_qids_critical"):
        state["decision_status"] = "AWAITING_BORROWER"
        state["agent_logs"].append(
            "Decision: blocked — awaiting borrower answers to critical questions."
        )
        return state

    normalized_risk = _normalized_risk_for_rules(int(state["risk_score"]))
    base = "APPROVED" if normalized_risk < 5 else "REJECTED"

    if state.get("pending_borrower_qids_async"):
        state["is_provisional"] = True
        provisional_status = (
            "PROVISIONAL_APPROVED" if base == "APPROVED" else "PROVISIONAL_REJECTED"
        )
        state["decision_status"] = provisional_status
        state["agent_logs"].append(
            f"Decision: provisional {base} (raw risk={state['risk_score']}, "
            f"normalized={normalized_risk}); "
            f"{len(state['pending_borrower_qids_async'])} async borrower question(s) outstanding."
        )
    else:
        state["decision_status"] = base
        state["is_provisional"] = False
        state["agent_logs"].append(
            f"Decision: Final risk(raw={state['risk_score']}, normalized={normalized_risk}) "
            f"(lower is better) -> {base}."
        )

    _apply_credit_limit_post_decision(state)
    return state


# --------------------------------------------------------------------------- #
# Streaming flow controller
# --------------------------------------------------------------------------- #


def iter_underwriting_flow_events(
    data: Dict[str, Any],
    region: str,
    interactive: bool = True,
    human_response: str = "",
    *,
    state: Optional[UnderwritingState] = None,
    analyst_responses: Optional[Dict[str, str]] = None,
    borrower_responses: Optional[Dict[str, str]] = None,
) -> Iterator[Dict[str, Any]]:
    """Yield progress events for UI streaming, then final state.

    The two-tier HITL flow is non-blocking in API mode: the function will pause
    by emitting an `awaiting_*` event and returning control. The caller resumes
    by passing in the existing `state` plus the relevant responses.

    The `human_response` parameter is kept for backward compatibility — it is
    interpreted as a free-text *analyst* answer applied uniformly to all
    pending analyst questions when no structured `analyst_responses` dict is
    supplied.
    """
    if state is None:
        state = create_initial_state(data, region)
        yield _progress_event("ingesting", "ingesting", "Preparing case folder")
        yield _progress_event(
            "analysis",
            "analysis",
            "Multi-agent committee (Audit / Trend / Benchmark / Cross-check)",
        )
        state = run_analysis_node(state)
        yield _progress_event("findings", "findings", "Aggregating findings & generating questions")
        state = findings_router_node(state)

    if analyst_responses:
        state["analyst_responses"] = {**(state.get("analyst_responses") or {}), **analyst_responses}
    elif human_response and not state.get("analyst_responses"):
        # Back-compat: apply free-text analyst answer to every pending analyst question.
        free_text = human_response.strip()
        if free_text and state.get("pending_analyst_qids"):
            state["analyst_responses"] = {
                qid: free_text for qid in state["pending_analyst_qids"]
            }

    # Tier-1: internal analyst.
    if not state.get("analyst_responses"):
        yield _progress_event("analyst_hitl", "analyst_hitl", "Tier-1: internal analyst review", human_in_loop=True)
        state = analyst_hitl_node(state)
        if state.get("decision_status") == "AWAITING_ANALYST":
            save_checkpoint(state)
            yield _progress_event(
                "analyst_hitl",
                "analyst_hitl_pending",
                f"Awaiting analyst answers ({len(state.get('pending_analyst_qids', []))} questions)",
                pending_qids=list(state.get("pending_analyst_qids", [])),
            )
            yield {"type": "complete", "state": state}
            return
    else:
        yield _progress_event("analyst_hitl", "analyst_hitl", "Tier-1: applying analyst responses")

    yield _progress_event("analyst_resume", "analyst_resume", "Folding analyst responses into findings")
    state = analyst_resume_node(state)

    # Tier-2 (blocking critical).
    if state.get("pending_borrower_qids_critical"):
        if borrower_responses:
            state["borrower_responses"] = {
                **(state.get("borrower_responses") or {}),
                **borrower_responses,
            }
            yield _progress_event(
                "borrower_hitl_blocking",
                "borrower_hitl_blocking",
                "Tier-2: applying borrower responses to critical findings",
            )
            state = borrower_blocking_resume_node(state)
            if state.get("pending_borrower_qids_critical"):
                save_checkpoint(state)
                yield _progress_event(
                    "borrower_hitl_blocking",
                    "borrower_hitl_blocking_pending",
                    "Awaiting remaining borrower answers (critical)",
                    pending_qids=list(state["pending_borrower_qids_critical"]),
                )
                yield {"type": "complete", "state": state}
                return
        else:
            state = borrower_blocking_node(state)
            save_checkpoint(state)
            yield _progress_event(
                "borrower_hitl_blocking",
                "borrower_hitl_blocking_pending",
                f"Tier-2 blocking: {len(state['pending_borrower_qids_critical'])} critical question(s) escalated",
                pending_qids=list(state["pending_borrower_qids_critical"]),
            )
            yield {"type": "complete", "state": state}
            return
    else:
        yield _progress_event(
            "borrower_hitl_skipped",
            "borrower_hitl_skipped",
            "Tier-2 blocking: not required (no critical unanswered questions)",
        )

    # Tier-2 (async non-critical) — never blocks.
    if state.get("pending_borrower_qids_async"):
        yield _progress_event(
            "borrower_async_queued",
            "borrower_async_queued",
            f"Tier-2 async: {len(state['pending_borrower_qids_async'])} non-critical "
            "question(s) queued for borrower",
            pending_qids=list(state["pending_borrower_qids_async"]),
        )
        state = queue_async_borrower_node(state)

    yield _progress_event("deciding", "decision", "Final / provisional underwriting decision")
    state = decision_node(state)

    save_checkpoint(state)
    yield _progress_event("checkpoint", "checkpoint", "Persisting checkpoint")
    yield {"type": "complete", "state": state}


def run_underwriting_flow(
    data: Dict[str, Any],
    region: str,
    interactive: bool = True,
    human_response: str = "",
    *,
    state: Optional[UnderwritingState] = None,
    analyst_responses: Optional[Dict[str, str]] = None,
    borrower_responses: Optional[Dict[str, str]] = None,
) -> UnderwritingState:
    """Drain the streaming flow and return the final state."""
    final_state: Optional[UnderwritingState] = None
    for event in iter_underwriting_flow_events(
        data,
        region,
        interactive,
        human_response,
        state=state,
        analyst_responses=analyst_responses,
        borrower_responses=borrower_responses,
    ):
        if event.get("type") == "complete":
            final_state = event["state"]
            break
    assert final_state is not None
    return final_state


def make_decision(risk_score: float) -> str:
    """Backward-compatible helper for legacy callers."""
    if risk_score > 7:
        return "HUMAN_REVIEW"
    return "APPROVED"


if __name__ == "__main__":
    with SAMPLE_DATA_FILE.open("r", encoding="utf-8") as f:
        sample_data = json.load(f)
    final = run_underwriting_flow(sample_data, region="India", interactive=False)
    print("\n=== GOVERNED UNDERWRITING FLOW RESULT ===")
    print(json.dumps(final, indent=2, default=str))
