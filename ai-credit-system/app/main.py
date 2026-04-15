"""CLI entrypoint for end-to-end underwriting run."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    # Ensure sibling folders (agents, graph, memory, etc.) are importable.
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

from agents.crew import run_crew
from graph.flow import make_decision
from ingestion.parser import parse_document
from memory.store import save_case

SAMPLE_DATA_FILE = ROOT_DIR / "data" / "sample_statement.json"


def _load_sample_data() -> Dict[str, Any]:
    with SAMPLE_DATA_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def run_pipeline(use_sample: bool = True) -> Dict[str, Any]:
    """Parse -> Agent analysis -> Decision -> Memory save."""
    # Step 1: Ingest data.
    if use_sample and SAMPLE_DATA_FILE.exists():
        parsed_data = _load_sample_data()
        input_source = str(SAMPLE_DATA_FILE)
    else:
        parsed_data = parse_document("mock_statement.pdf")
        input_source = "mock_statement.pdf"

    # Step 2: Run multi-agent analysis.
    crew_output = run_crew(parsed_data)

    # Step 3: Make underwriting decision.
    risk_score = float(crew_output["auditor"]["risk_score"])
    decision = make_decision(risk_score)

    # Step 4: Save case to memory.
    case_record = {
        "input_source": input_source,
        "parsed_data": parsed_data,
        "agent_outputs": crew_output,
        "decision": decision,
    }
    save_case(case_record)
    return case_record


if __name__ == "__main__":
    result = run_pipeline(use_sample=True)
    print("\n=== AI CREDIT UNDERWRITING RESULT ===")
    print(json.dumps(result, indent=2))
    print("\nCase saved successfully to memory store.")
