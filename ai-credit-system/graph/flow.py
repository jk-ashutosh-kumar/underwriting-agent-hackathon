"""Governed underwriting flow (LangGraph-style, function-simulated)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from agents.crew import run_crew
from graph.state import UnderwritingState, create_initial_state
from memory.checkpoint import save_checkpoint

ROOT_DIR = Path(__file__).resolve().parents[1]
SAMPLE_DATA_FILE = ROOT_DIR / "data" / "sample_statement.json"
REGIONAL_POLICY_FILE = ROOT_DIR / "data" / "regional_policy.json"


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
    if risk_score <= 10:
        return risk_score
    return int(round(risk_score / 10))


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
    region_policy = policy.get(state["region"], policy.get("India", {}))
    amount_threshold = float(region_policy.get("cash_threshold", 50000))
    transactions: List[Dict[str, Any]] = state["applicant_data"].get("transactions", [])

    for txn in transactions:
        description = str(txn.get("description", "")).strip()
        amount = float(txn.get("amount", 0))
        if not description:
            state["decision_status"] = "FLAGGED"
            state["agent_logs"].append("Router: Missing transaction description detected -> FLAGGED.")
            return "hitl"
        if amount > amount_threshold:
            state["decision_status"] = "FLAGGED"
            state["agent_logs"].append(
                f"Router: Large transaction {amount:.2f} above threshold {amount_threshold:.2f} -> FLAGGED."
            )
            return "hitl"
        if "Transfer 00921" in description:
            state["decision_status"] = "FLAGGED"
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
        state["decision_status"] = "FLAGGED"
        state["agent_logs"].append(f"Router: Normalized risk {normalized_risk} > 7 -> HITL path.")
        return "hitl"

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
    """Node D: resume after HITL and apply small risk reduction."""
    clarification = state.get("human_input", "").strip() or "No clarification provided"
    state["agent_logs"].append(f"Resume: User clarified -> {clarification}")
    # Simple demo logic: reduce risk slightly after human clarification.
    state["risk_score"] = max(0, int(state["risk_score"]) - 2)
    state["agent_logs"].append(
        f"Resume: Reduced risk score by 2 after clarification. New risk={state['risk_score']}."
    )
    return state


def decision_node(state: UnderwritingState) -> UnderwritingState:
    """Node E: final decision assignment."""
    if int(state["risk_score"]) < 5:
        state["decision_status"] = "APPROVED"
    else:
        state["decision_status"] = "REJECTED"
    state["agent_logs"].append(
        f"Decision: Final risk={state['risk_score']} -> {state['decision_status']}."
    )
    return state


def run_underwriting_flow(
    data: Dict[str, Any],
    region: str,
    interactive: bool = True,
    human_response: str = "",
) -> UnderwritingState:
    """Flow controller orchestrating all nodes with conditional routing."""
    state = create_initial_state(data, region)
    state = run_analysis_node(state)
    next_step = router_node(state)

    if next_step == "approve":
        state = decision_node(state)
    elif next_step == "hitl":
        state = hitl_node(state, interactive=interactive, human_response=human_response)
        state = resume_node(state)
        state = decision_node(state)
    else:  # review
        state = decision_node(state)

    return state


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
