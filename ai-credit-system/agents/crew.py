"""Crew orchestration layer.

Uses CrewAI objects when available, while keeping execution simple and local.
"""

from __future__ import annotations

import os
from typing import Any, Dict

from agents.auditor import run_auditor
from agents.benchmark import run_benchmark
from agents.trend import run_trend_analysis

def _build_mock_crew() -> Dict[str, str]:
    """Build placeholder CrewAI metadata for display."""
    return {
        "auditor_agent": "Auditor Agent configured",
        "trend_agent": "Trend Analyst Agent configured",
        "benchmark_agent": "Benchmarker Agent configured",
    }


def _build_crewai_objects() -> Dict[str, Any]:
    """Instantiate lightweight CrewAI objects (no external calls)."""
    try:
        # Lazy import keeps default run path stable on systems where CrewAI dependencies
        # are not fully compatible.
        from crewai import Agent, Crew, Task
    except Exception:
        return {"status": "CrewAI not installed; using local function orchestration."}

    auditor = Agent(
        role="Auditor",
        goal="Detect high risk transaction patterns",
        backstory="A finance auditor focused on anomaly detection.",
        verbose=False,
    )
    trend_analyst = Agent(
        role="Trend Analyst",
        goal="Summarize business financial trajectory",
        backstory="A portfolio analyst focused on cashflow trends.",
        verbose=False,
    )
    benchmarker = Agent(
        role="Benchmarker",
        goal="Compare applicant against peer performance",
        backstory="An industry benchmarking specialist.",
        verbose=False,
    )

    # These tasks are illustrative for hackathon visibility.
    audit_task = Task(description="Review transactions and compute risk.", agent=auditor)
    trend_task = Task(description="Analyze inflow vs outflow trend.", agent=trend_analyst)
    benchmark_task = Task(description="Benchmark against peer cohort.", agent=benchmarker)

    crew = Crew(
        agents=[auditor, trend_analyst, benchmarker],
        tasks=[audit_task, trend_task, benchmark_task],
        verbose=False,
    )
    return {"crew": crew, "status": "CrewAI objects initialized."}


def run_crew(data: Dict[str, Any]) -> Dict[str, Any]:
    """Run all analysis agents and return merged results."""
    # Default to mock orchestration for hackathon reliability.
    # Set USE_CREWAI=1 to attempt real CrewAI object initialization.
    use_crewai = os.getenv("USE_CREWAI", "0") == "1"
    crew_meta = _build_crewai_objects() if use_crewai else _build_mock_crew()

    auditor_result = run_auditor(data)
    trend_result = run_trend_analysis(data)
    benchmark_result = run_benchmark(data)

    return {
        "crew_status": crew_meta.get("status", "Crew configured."),
        "auditor": auditor_result,
        "trend": trend_result,
        "benchmark": benchmark_result,
    }
