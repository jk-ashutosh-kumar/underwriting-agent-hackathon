"""Governed underwriting flow (LangGraph-style, function-simulated)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterator, List

from agents.crew import run_crew
from graph.state import UnderwritingState, create_initial_state
from memory.checkpoint import save_checkpoint

ROOT_DIR = Path(__file__).resolve().parents[1]
SAMPLE_DATA_FILE = ROOT_DIR / "data" / "sample_statement.json"
REGIONAL_POLICY_FILE = ROOT_DIR / "data" / "regional_policy.json"

# UI pipeline indices (ingest → committee → router → HITL → resume → decision → checkpoint)
_PROGRESS_INDEX = {
    "ingesting": 0,
    "analysis": 1,
    "router": 2,
    "router_done": 2,
    "hitl": 3,
    "hitl_skipped": 3,
    "resume": 4,
    "resume_skipped": 4,
    "deciding": 5,
    "checkpoint": 6,
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
    """Load region-aware policy thresholds with safe fallback."""
    if not REGIONAL_POLICY_FILE.exists():
        return {"India": {"cash_threshold": 50000, "flag_keywords": []}}
    with REGIONAL_POLICY_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _normalized_risk_for_rules(risk_score: int) -> int:
    """
    Normalize risk score to a 0-10 style scale for simple routing.

    Phase 2 currently returns up to 100. For router thresholds (<4, >7),
    we scale down if needed.
    """
    # Treat incoming score as 0-100, then map to 0-10 for router/decision rules.
    # This avoids ambiguous behavior where a low raw value like "8" was treated as
    # high risk on a 0-10 scale instead of 8/100.
    bounded = max(0, min(100, int(risk_score)))
    return int(round(bounded / 10))


def run_analysis_node(state: UnderwritingState) -> UnderwritingState:
    """Node A: run multi-agent analysis and store explainable logs."""
    committee_output = run_crew(state["applicant_data"], region=state["region"])
    audit = committee_output.get("audit", committee_output.get("auditor", {}))
    trend = committee_output.get("trend", {})
    benchmark = committee_output.get("benchmark", {})

    state["risk_score"] = int(audit.get("risk_score", 0))
    state["agent_logs"].append(f"Auditor: {audit.get('explanation', 'No explanation provided.')}")
    state["agent_logs"].append(f"Trend: {trend.get('insight', 'No trend insight provided.')}")
    state["agent_logs"].append(
        f"Benchmark: {benchmark.get('comparison_insight', 'No benchmark insight provided.')}"
    )

    final_summary = committee_output.get("final_summary")
    if final_summary:
        state["agent_logs"].append(f"Committee: {final_summary}")
    # Cache crew output on state so API/streaming can avoid a second run_crew call.
    state["committee_output"] = committee_output  # type: ignore[assignment]
    return state


def router_node(state: UnderwritingState) -> str:
    """
    Node B: route case to approve/hitl/review.

    Rules:
    - risk < 4  -> approve
    - risk > 7  -> hitl
    - else      -> review
    Extra forced FLAGGED/HITL conditions:
    - missing description
    - large amount above regional threshold
    - "Transfer 00921" style trigger
    """
    policy = _load_regional_policy()
    # Reset per-run HITL context. When set, UI can show flagged transaction details.
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
        if "Transfer 00921" in description:
            state["decision_status"] = "FLAGGED"
            state["hitl_context"] = {  # type: ignore[assignment]
                "reason": "aha_trigger",
                "transaction": txn,
                "message": "Suspicious transfer pattern matched (Transfer 00921).",
            }
            state["agent_logs"].append(
                "Router: Aha trigger matched ('Transfer 00921') -> FLAGGED for HITL."
            )
            return "hitl"

    normalized_risk = _normalized_risk_for_rules(state["risk_score"])
    if normalized_risk < 4:
        state["decision_status"] = "APPROVED"
        state["agent_logs"].append(f"Router: Normalized risk {normalized_risk} < 4 -> APPROVE path.")
        return "approve"
    if normalized_risk > 7:
        # High risk alone should not always trigger HITL popup.
        # Keep it in review path unless an explicit transaction flag was found above.
        state["decision_status"] = "PENDING"
        state["agent_logs"].append(
            f"Router: Normalized risk {normalized_risk} > 7 -> REVIEW path (no explicit flagged transaction)."
        )
        return "review"

    state["decision_status"] = "PENDING"
    state["agent_logs"].append(f"Router: Normalized risk {normalized_risk} in [4..7] -> REVIEW path.")
    return "review"


def hitl_node(
    state: UnderwritingState, interactive: bool = True, human_response: str = ""
) -> UnderwritingState:
    """Node C: pause for human clarification and persist checkpoint."""
    print("⚠️ Action Required: Suspicious transaction detected")
    print("Found large transaction with no description")
    save_checkpoint(state)
    if interactive:
        user_response = input("Explain this transaction: ").strip()
    else:
        # UI-safe mode: do not block; consume provided response.
        user_response = human_response.strip() or "No clarification provided"
    state["human_input"] = user_response
    state["agent_logs"].append(f"HITL: User explanation captured -> {user_response}")
    return state


def resume_node(state: UnderwritingState) -> UnderwritingState:
    """Node D: resume after HITL and adjust risk from human clarification quality."""
    clarification = state.get("human_input", "").strip() or "No clarification provided"
    state["agent_logs"].append(f"Resume: User clarified -> {clarification}")

    text = clarification.lower()
    positive_markers = [
        "invoice",
        "vendor",
        "salary",
        "tax",
        "gst",
        "rent",
        "loan",
        "emi",
        "client",
        "refund",
        "prepayment",
        "receipt",
    ]
    weak_markers = [
        "dont know",
        "don't know",
        "not sure",
        "unknown",
        "cash",
        "friend",
        "personal",
        "just like that",
        "random",
        "no reason",
        "maybe",
    ]
    negative_markers = [
        "reject",
        "decline",
        "fraud",
        "suspicious",
        "fake",
        "illegal",
        "money laundering",
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

    # Apply an explainable score delta from clarification quality.
    # Positive reason can materially lower risk, weak reason can raise it.
    if quality_score >= 5:
        delta = -6
        note = "strong documentary/commercial explanation"
    elif quality_score >= 3:
        delta = -4
        note = "reasonable explanation"
    elif quality_score >= 1:
        delta = -2
        note = "partial explanation"
    elif quality_score == 0:
        delta = 0
        note = "neutral explanation"
    elif quality_score >= -2:
        delta = 2
        note = "weak explanation"
    else:
        delta = 12
        note = "negative/suspicious explanation"

    # Hard guardrail: explicitly negative clarifications should strongly penalize
    # and bias final decision toward reject.
    if has_negative_signal:
        delta = max(delta, 15)
        state["hitl_override"] = "reject"  # type: ignore[assignment]
        note = f"{note}; reject override armed"

    state["risk_score"] = max(0, int(state["risk_score"]) + delta)
    state["agent_logs"].append(
        f"Resume: Clarification quality={quality_score} ({note}); risk delta={delta} "
        "(negative lowers risk, positive raises risk). "
        f"New risk={state['risk_score']} (lower is better)."
    )
    return state


def decision_node(state: UnderwritingState) -> UnderwritingState:
    """Node E: final decision assignment using normalized risk scale."""
    if state.get("hitl_override") == "reject":  # type: ignore[attr-defined]
        state["decision_status"] = "REJECTED"
        state["agent_logs"].append(
            "Decision: HITL override requested rejection due to negative clarification."
        )
        return state

    normalized_risk = _normalized_risk_for_rules(int(state["risk_score"]))
    if normalized_risk < 5:
        state["decision_status"] = "APPROVED"
    else:
        state["decision_status"] = "REJECTED"
    state["agent_logs"].append(
        f"Decision: Final risk(raw={state['risk_score']}, normalized={normalized_risk}) "
        f"(lower is better) -> {state['decision_status']}."
    )
    return state


def iter_underwriting_flow_events(
    data: Dict[str, Any],
    region: str,
    interactive: bool = True,
    human_response: str = "",
) -> Iterator[Dict[str, Any]]:
    """
    Yield progress events for UI streaming, then final state.

    Each event is a dict with at least ``type``. Progress events use
    ``type == "progress"`` and include ``phase``, ``step``, and ``label``.
    Final event is ``type == "complete"`` with ``state`` (full UnderwritingState).
    """
    state = create_initial_state(data, region)
    yield _progress_event("ingesting", "ingesting", "Preparing case folder")

    yield _progress_event(
        "analysis",
        "analysis",
        "Multi-agent committee (Audit / Trend / Benchmark)",
    )
    state = run_analysis_node(state)

    yield _progress_event("router", "router", "Policy routing & gates")
    next_step = router_node(state)
    yield _progress_event(
        "router_done",
        "route_decision",
        f"Route selected: {next_step}",
        route=next_step,
    )

    if next_step == "approve":
        yield _progress_event(
            "hitl_skipped",
            "hitl_skipped",
            "HITL: not required (approve path)",
            skipped_steps=["hitl"],
        )
        yield _progress_event(
            "resume_skipped",
            "resume_skipped",
            "Resume: not required",
            skipped_steps=["hitl", "resume"],
        )
        yield _progress_event("deciding", "decision", "Final underwriting decision")
        state = decision_node(state)
    elif next_step == "hitl":
        yield _progress_event(
            "hitl",
            "hitl",
            "Human-in-the-loop — capture clarification",
            human_in_loop=True,
        )
        state = hitl_node(state, interactive=interactive, human_response=human_response)
        yield _progress_event("resume", "resume", "Resume pipeline after HITL")
        state = resume_node(state)
        yield _progress_event("deciding", "decision", "Final underwriting decision")
        state = decision_node(state)
    else:  # review
        yield _progress_event(
            "hitl_skipped",
            "hitl_skipped",
            "HITL: not required (review path)",
            skipped_steps=["hitl"],
        )
        yield _progress_event(
            "resume_skipped",
            "resume_skipped",
            "Resume: not required",
            skipped_steps=["hitl", "resume"],
        )
        yield _progress_event("deciding", "decision", "Final underwriting decision")
        state = decision_node(state)

    save_checkpoint(state)
    yield _progress_event("checkpoint", "checkpoint", "Persisting checkpoint")
    yield {"type": "complete", "state": state}


def run_underwriting_flow(
    data: Dict[str, Any],
    region: str,
    interactive: bool = True,
    human_response: str = "",
) -> UnderwritingState:
    """Flow controller orchestrating all nodes with conditional routing."""
    final_state: UnderwritingState | None = None
    for event in iter_underwriting_flow_events(data, region, interactive, human_response):
        if event.get("type") == "complete":
            final_state = event["state"]
            break
    assert final_state is not None
    return final_state


# Backward-compatible helper used by Phase 1/2 UI and CLI modules.
def make_decision(risk_score: float) -> str:
    """Return simple decision label for legacy callers."""
    if risk_score > 7:
        return "HUMAN_REVIEW"
    return "APPROVED"


if __name__ == "__main__":
    with SAMPLE_DATA_FILE.open("r", encoding="utf-8") as f:
        sample_data = json.load(f)
    final_state = run_underwriting_flow(sample_data, region="India")
    print("\n=== GOVERNED UNDERWRITING FLOW RESULT ===")
    print(json.dumps(final_state, indent=2))
