"""Streamlit dashboard for AI Credit Underwriting System."""

from __future__ import annotations

import inspect
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    # Ensure sibling folders are importable when running streamlit from ui/.
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

import streamlit as st

from agents.crew import run_crew
import graph.flow as flow_module
from ingestion.parser import parse_document
from memory.store import save_case

SAMPLE_DATA_FILE = ROOT_DIR / "data" / "sample_statement.json"


def _load_json_from_upload(uploaded_file: Any) -> Dict[str, Any]:
    """Load uploaded JSON bytes into dictionary."""
    return json.loads(uploaded_file.read().decode("utf-8"))


def _load_sample_json() -> Dict[str, Any]:
    """Load local sample statement."""
    with SAMPLE_DATA_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _build_final_summary(
    region_name: str, audit: Dict[str, Any], trend: Dict[str, Any], benchmark: Dict[str, Any]
) -> str:
    """Build a deterministic final summary when backend summary is missing."""
    risk_score = audit.get("risk_score", "N/A")
    trend_label = trend.get("trend", "unknown")
    profit = trend.get("profit", 0)
    benchmark_result = benchmark.get("benchmark_result", "No benchmark result available")
    return (
        f"Committee Summary ({region_name}): audit risk score is {risk_score}; "
        f"growth trend is '{trend_label}' with profit {profit}; "
        f"benchmark view: {benchmark_result}."
    )


def _render_timeline(steps: list[str]) -> None:
    """Render a compact flow timeline as badge-like pills."""
    html = '<div style="display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 14px 0;">'
    for step in steps:
        html += (
            '<span style="background:#eef2ff;border:1px solid #c7d2fe;'
            'border-radius:999px;padding:6px 10px;font-size:0.85rem;">'
            f"{step}</span>"
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def _simulate_external_ai_call(governed_mode_enabled: bool) -> None:
    """Show staged status text and wait to simulate external AI API calls."""
    mode_text = "Governed underwriting flow" if governed_mode_enabled else "Multi-agent committee"
    with st.status(f"Simulating external AI calls ({mode_text})...", expanded=True) as status:
        st.write("Connecting to AI orchestration service...")
        time.sleep(0.6)
        st.write("Sending financial context and regional policy...")
        time.sleep(0.8)
        st.write("Running model reasoning and cross-agent checks...")
        time.sleep(0.9)
        st.write("Compiling explainable decision artifacts...")
        time.sleep(0.6)
        status.update(label="AI simulation complete", state="complete")


st.set_page_config(page_title="AI Credit Underwriting", layout="wide")
st.title("AI Credit Underwriting System")
st.caption("Hackathon-ready demo with ingestion, agents, decision flow, and memory.")

st.subheader("1) Input Data")
uploaded_file = st.file_uploader("Upload statement JSON file", type=["json"])
use_sample = st.checkbox("Use sample data", value=True)
region = st.selectbox("Region context", options=["India", "Philippines"], index=0)
governed_mode = st.checkbox("Use Governed Underwriting Flow (state machine)", value=False)
human_explanation = st.text_input(
    "HITL explanation (used only in Governed Mode if case is flagged)",
    value="Internal transfer between linked accounts.",
)

if st.button("Run Analysis", type="primary"):
    st.subheader("2) Ingestion")
    if uploaded_file is not None:
        parsed_data = _load_json_from_upload(uploaded_file)
        st.write("Loaded uploaded JSON data.")
    elif use_sample:
        parsed_data = _load_sample_json()
        st.write("Loaded sample JSON data.")
    else:
        # Demonstrate parser function even when user has no file.
        parsed_data = parse_document("mock_statement.pdf")
        st.write("No input provided; using parser mock data.")

    transaction_count = len(parsed_data.get("transactions", []))
    st.write(
        f"Applicant `{parsed_data.get('applicant_id', 'Unknown')}` with "
        f"`{transaction_count}` transactions loaded for region `{region}`."
    )
    _simulate_external_ai_call(governed_mode)

    if governed_mode:
        st.subheader("3) Governed Underwriting Flow (State Machine)")
        st.write(
            "Running analysis -> router -> optional HITL -> resume -> final decision with shared state."
        )
        run_underwriting_flow = getattr(flow_module, "run_underwriting_flow", None)
        make_decision = getattr(flow_module, "make_decision", None)
        if run_underwriting_flow is None:
            st.error(
                "Governed flow is unavailable in current runtime. "
                "Please restart Streamlit to reload latest `graph/flow.py`."
            )
            st.stop()

        governed_state = run_underwriting_flow(
            parsed_data,
            region=region,
            interactive=False,
            human_response=human_explanation,
        )
        hitl_used = any("HITL" in log for log in governed_state.get("agent_logs", []))
        route_steps = (
            ["A: Analysis", "B: Router", "C: HITL", "D: Resume", "E: Decision"]
            if hitl_used
            else ["A: Analysis", "B: Router", "E: Decision"]
        )
        st.markdown("### State Transition Timeline")
        _render_timeline(route_steps)

        st.markdown("### State Transition Logs")
        for idx, log_line in enumerate(governed_state.get("agent_logs", []), start=1):
            st.write(f"{idx}. {log_line}")

        st.markdown("### Final Committee Output")
        st.success(
            f"Decision Status: {governed_state.get('decision_status', 'PENDING')} | "
            f"Final Risk Score: {governed_state.get('risk_score', 0)}"
        )
        st.write(
            f"Human Input Used: {governed_state.get('human_input', 'No clarification captured')}"
        )

        st.subheader("4) Decision Flow")
        risk_score = float(governed_state.get("risk_score", 0))
        decision = str(governed_state.get("decision_status", "PENDING"))
        st.write(f"Risk Score: **{risk_score}**")
        st.write(f"Decision: **{decision}**")

        payload_for_memory = governed_state
    else:
        st.subheader("3) Multi-Agent Credit Committee")
        st.write("Running Auditor, Trend Analyst, and Benchmarker with explainable reasoning...")
        # Backward-compatible call:
        # - New signature: run_crew(data, region=...)
        # - Older signature: run_crew(data)
        if "region" in inspect.signature(run_crew).parameters:
            crew_results = run_crew(parsed_data, region=region)
        else:
            crew_results = run_crew(parsed_data)

        # Keep both key styles for compatibility.
        audit = crew_results.get("audit", crew_results.get("auditor", {}))
        trend = crew_results.get("trend", {})
        benchmark = crew_results.get("benchmark", {})
        final_summary = crew_results.get("final_summary")
        if not final_summary:
            # If an older backend format is loaded, compute a UI-safe summary.
            final_summary = _build_final_summary(region, audit, trend, benchmark)

        # Show each agent output and "thinking process" (why/explanation).
        st.markdown("### Agent Insights Summary")
        st.write(f"- **Auditor Risk Score:** {audit.get('risk_score', 'N/A')}")
        st.write(f"- **Auditor Why:** {audit.get('explanation', 'No explanation provided.')}")
        st.write(f"- **Trend:** {trend.get('trend', 'unknown')}")
        st.write(f"- **Profit:** {trend.get('profit', 0)}")
        st.write(f"- **Trend Why:** {trend.get('insight', 'No trend insight provided.')}")
        st.write(
            "- **Benchmark Insight:** "
            + benchmark.get("comparison_insight", "No benchmark insight provided.")
        )

        st.markdown("### Committee Transcript")
        with st.chat_message("assistant", avatar="🕵️"):
            st.markdown("**Auditor (Fraud Detection Specialist)**")
            st.write(audit.get("explanation", "No reasoning provided by auditor."))
        with st.chat_message("assistant", avatar="📈"):
            st.markdown("**Trend Analyst (Growth Strategist)**")
            st.write(trend.get("insight", "No reasoning provided by trend agent."))
        with st.chat_message("assistant", avatar="💼"):
            st.markdown("**Portfolio Manager (Benchmark Agent)**")
            st.write(
                benchmark.get(
                    "comparison_insight",
                    "No historical comparison insight provided by benchmark agent.",
                )
            )
        with st.chat_message("assistant", avatar="🏁"):
            st.markdown("**Committee Chair Final Verdict**")
            st.write(final_summary)

        st.markdown("### Final Committee Output")
        st.success(final_summary)
        st.caption(f"Crew Status: {crew_results.get('crew_status', 'Unknown')}")

        st.subheader("4) Decision Flow")
        make_decision = getattr(flow_module, "make_decision", None)
        if make_decision is None:
            st.error(
                "Decision helper is unavailable in current runtime. "
                "Please restart Streamlit to reload latest `graph/flow.py`."
            )
            st.stop()
        risk_score = float(audit.get("risk_score", 0))
        decision = make_decision(risk_score)
        st.write(f"Risk Score: **{risk_score}**")
        st.write(f"Decision: **{decision}**")

        payload_for_memory = crew_results

    st.subheader("5) Memory Save")
    case_payload = {
        "input_data": parsed_data,
        "agent_outputs": payload_for_memory,
        "decision": decision,
    }
    save_case(case_payload)
    st.success("Case saved to JSON memory store.")
