"""Streamlit dashboard for AI Credit Underwriting System."""

from __future__ import annotations

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


st.set_page_config(page_title="AI Credit Underwriting", layout="wide")
st.title("AI Credit Underwriting System")
st.caption("Hackathon-ready demo with ingestion, agents, decision flow, and memory.")

st.subheader("1) Input Data")
uploaded_file = st.file_uploader("Upload statement JSON file", type=["json"])
use_sample = st.checkbox("Use sample data", value=True)

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

    st.subheader("3) Agent Analysis (Crew)")
    st.write("Running Auditor, Trend Analyst, and Benchmarker...")
    crew_results = run_crew(parsed_data)
    st.json(crew_results)

    st.subheader("4) Decision Flow")
    risk_score = float(crew_results["auditor"]["risk_score"])
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
