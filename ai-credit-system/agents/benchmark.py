"""Benchmark agent that compares with simple memory history."""

from __future__ import annotations

from typing import Any, Dict, List


def run_benchmark(
    data: Dict[str, Any], context: Dict[str, Any], memory: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Experienced portfolio manager.

    Compare current case against past memory entries.
    If no memory exists, return a clear fallback response.
    """
    _ = data
    _ = context

    if not memory:
        return {
            "benchmark_result": "No historical comparison",
            "comparison_insight": (
                "I cannot compare against portfolio history yet because memory is empty. "
                "Run a few cases first to enable historical benchmarking."
            ),
        }

    high_risk_cases = [entry for entry in memory if str(entry.get("risk", "")).lower() == "high"]
    high_risk_ratio = len(high_risk_cases) / len(memory)

    if high_risk_ratio >= 0.5:
        benchmark_result = "Risk profile is closer to historically higher-risk partners"
    else:
        benchmark_result = "Risk profile is closer to historically stable partners"

    comparison_insight = (
        f"I reviewed {len(memory)} memory cases; {len(high_risk_cases)} were high risk. "
        f"This suggests the current case aligns with '{benchmark_result}'."
    )

    return {
        "benchmark_result": benchmark_result,
        "comparison_insight": comparison_insight,
    }
