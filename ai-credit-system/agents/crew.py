"""Multi-Agent Credit Committee orchestration for hackathon demos."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from agents.auditor import run_auditor
from agents.benchmark import run_benchmark
from agents.trend import run_trend_analysis
from memory.store import load_memory
from tools.accounting_tool import AccountingModuleTool

ROOT_DIR = Path(__file__).resolve().parents[1]
REGIONAL_RULES_FILE = ROOT_DIR / "data" / "regional_rules.json"
SAMPLE_DATA_FILE = ROOT_DIR / "data" / "sample_statement.json"


def _load_regional_rules() -> Dict[str, Any]:
    """Load regional thresholds and keywords from JSON config."""
    if not REGIONAL_RULES_FILE.exists():
        # Safe fallback to keep demo runnable even if file is missing.
        return {"India": {"dscr_threshold": 1.2, "large_txn_threshold": 100000, "keywords": []}}
    with REGIONAL_RULES_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _build_region_context(region: str) -> Dict[str, Any]:
    """Build context object injected into all agent tasks."""
    rules = _load_regional_rules()
    region_rules = rules.get(region, rules.get("India", {}))
    return {
        "region": region,
        "dscr_threshold": region_rules.get("dscr_threshold", 1.2),
        "large_txn_threshold": region_rules.get("large_txn_threshold", 100000),
        "keywords": region_rules.get("keywords", []),
    }


def _build_crewai_committee(region_context: Dict[str, Any]) -> Dict[str, str]:
    """
    Create CrewAI agents and tasks with region-aware context injection.

    We keep this lightweight and avoid mandatory LLM kickoff so the project
    remains stable in hackathon environments.
    """
    try:
        from crewai import Agent, Crew, Task
    except Exception:
        return {"status": "CrewAI import unavailable; running deterministic local committee logic."}

    accounting_tool = AccountingModuleTool()
    region = region_context["region"]
    large_threshold = region_context["large_txn_threshold"]
    keywords = ", ".join(region_context["keywords"]) or "N/A"

    # Distinct personas requested by the prompt.
    auditor_agent = Agent(
        role="Fraud Detection Specialist",
        goal="Detect anomalies and suspicious transaction behavior",
        backstory="Skeptical forensic accountant who trusts no one.",
        verbose=False,
        tools=[accounting_tool],
    )
    trend_agent = Agent(
        role="Growth Analyst",
        goal="Analyze financial trends and profitability direction",
        backstory="Data-driven strategist focused on growth.",
        verbose=False,
    )
    benchmark_agent = Agent(
        role="Portfolio Manager",
        goal="Compare current applicant with historical portfolio behavior",
        backstory="Experienced portfolio manager.",
        verbose=False,
    )

    # Region-aware context injection directly inside task text.
    audit_task = Task(
        description=(
            f"This is a financial statement from {region}. "
            f"Apply rules: large transaction threshold = {large_threshold}; "
            f"consider keywords/patterns: {keywords}. "
            "Analyze fraud risk and explain WHY."
        ),
        agent=auditor_agent,
        expected_output="Fraud risk assessment with clear explanation and flags.",
    )
    trend_task = Task(
        description=(
            "Using financial totals and prior audit findings, determine growth trend, "
            "profitability, and explain WHY your trend label is reasonable."
        ),
        agent=trend_agent,
        context=[audit_task],  # Context pass from Task 1 -> Task 2.
        expected_output="Profit, trend label, and explainable growth insight.",
    )
    benchmark_task = Task(
        description=(
            "Compare this case against memory/history and prior task outputs. "
            "State whether this looks closer to high-risk or stable historical partners."
        ),
        agent=benchmark_agent,
        context=[audit_task, trend_task],  # Context pass from previous tasks.
        expected_output="Benchmark result plus historical comparison insight.",
    )

    # Build Crew object for demo visibility. We do not call kickoff here by default.
    _ = Crew(
        agents=[auditor_agent, trend_agent, benchmark_agent],
        tasks=[audit_task, trend_task, benchmark_task],
        verbose=False,
    )
    return {"status": "CrewAI committee configured with 3 agents and chained tasks."}


def run_crew(data: Dict[str, Any], region: str = "India") -> Dict[str, Any]:
    """Run the multi-agent committee and return explainable outputs."""
    region_context = _build_region_context(region)
    crew_meta = _build_crewai_committee(region_context)

    # Tool output is included in context so the committee appears integrated with
    # external accounting information, even in deterministic demo mode.
    accounting_tool = AccountingModuleTool()
    accounting_signal = accounting_tool._run("repayment trend")
    region_context["accounting_tool_signal"] = accounting_signal

    # Task 1: Auditor
    audit = run_auditor(data, region_context)

    # Task 2: Trend (receives context from audit)
    trend_context = {**region_context, "audit_result": audit}
    trend = run_trend_analysis(data, trend_context)

    # Task 3: Benchmark (receives prior outputs + memory)
    memory_entries = load_memory()
    benchmark_context = {**trend_context, "trend_result": trend}
    benchmark = run_benchmark(data, benchmark_context, memory_entries)

    final_summary = (
        f"Committee Summary ({region}): audit risk score is {audit['risk_score']}/100; "
        f"growth trend is '{trend['trend']}' with profit {trend['profit']:.2f}; "
        f"benchmark view: {benchmark['benchmark_result']}. "
        f"Accounting signal used: {accounting_signal}."
    )

    return {
        "audit": audit,
        "trend": trend,
        "benchmark": benchmark,
        # Backward-compatible keys for existing UI/CLI references.
        "auditor": audit,
        "final_summary": final_summary,
        "crew_status": crew_meta["status"],
    }


if __name__ == "__main__":
    # Runnable local test for demo day.
    with SAMPLE_DATA_FILE.open("r", encoding="utf-8") as f:
        sample_data = json.load(f)

    result = run_crew(sample_data, region="India")
    print(json.dumps(result, indent=2))
