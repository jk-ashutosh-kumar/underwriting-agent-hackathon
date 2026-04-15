"""Streamlit dashboard for AI Credit Underwriting System."""

from __future__ import annotations

import inspect
import json
import sys
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
from graph.flow import make_decision
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


st.set_page_config(page_title="AI Credit Underwriting", layout="wide")
st.title("AI Credit Underwriting System")
st.caption("Hackathon-ready demo with ingestion, agents, decision flow, and memory.")

st.subheader("1) Input Data")
uploaded_file = st.file_uploader("Upload statement JSON file", type=["json"])
use_sample = st.checkbox("Use sample data", value=True)
region = st.selectbox("Region context", options=["India", "Philippines"], index=0)

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

    st.json(parsed_data)

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
    st.markdown("### Auditor Agent Output")
    st.json(audit)
    if audit.get("explanation"):
        st.info(f"Why this decision: {audit['explanation']}")

    st.markdown("### Trend Agent Output")
    st.json(trend)
    if trend.get("insight"):
        st.info(f"Why this decision: {trend['insight']}")

    st.markdown("### Benchmark Agent Output")
    st.json(benchmark)
    if benchmark.get("comparison_insight"):
        st.info(f"Why this decision: {benchmark['comparison_insight']}")

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
    st.json(
        {
            "audit": audit,
            "trend": trend,
            "benchmark": benchmark,
            "final_summary": final_summary,
            "crew_status": crew_results.get("crew_status"),
        }
    )

    st.subheader("4) Decision Flow")
    risk_score = float(audit.get("risk_score", 0))
    decision = make_decision(risk_score)
    st.write(f"Risk Score: **{risk_score}**")
    st.write(f"Decision: **{decision}**")

    st.subheader("5) Memory Save")
    case_payload = {
        "input_data": parsed_data,
        "agent_outputs": crew_results,
        "decision": decision,
    }
    save_case(case_payload)
    st.success("Case saved to JSON memory store.")
