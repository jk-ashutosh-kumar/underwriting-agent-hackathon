"""Benchmark agent that compares with simple memory history."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from llm.client import ask_llm_json

logger = logging.getLogger(__name__)


def _run_benchmark_deterministic(
    data: Dict[str, Any], context: Dict[str, Any], memory: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Current deterministic implementation kept as safe fallback."""
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


def _run_benchmark_llm(
    data: Dict[str, Any], context: Dict[str, Any], memory: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """LLM-assisted benchmark analysis with strict output schema."""
    _ = data
    region = context.get("region", "Unknown")
    if not memory:
        return {
            "benchmark_result": "No historical comparison",
            "comparison_insight": (
                "I cannot compare against portfolio history yet because memory is empty. "
                "Run a few cases first to enable historical benchmarking."
            ),
        }

    system_prompt = (
        "You are an experienced portfolio manager. "
        "Return ONLY JSON with keys: benchmark_result (string), comparison_insight (string)."
    )
    user_prompt = (
        "Compare a current underwriting case against historical memory entries.\n"
        f"Region: {region}\n"
        f"Memory entries: {memory}\n"
        "Provide concise, explainable benchmark judgement."
    )
    payload = ask_llm_json(system_prompt=system_prompt, user_prompt=user_prompt)
    benchmark_result = str(payload.get("benchmark_result", "No historical comparison"))
    comparison_insight = str(
        payload.get("comparison_insight", "No comparison insight provided by LLM.")
    )
    logger.info(
        "benchmark_llm_completed",
        extra={"region": region, "memory_count": len(memory)},
    )
    return {
        "benchmark_result": benchmark_result,
        "comparison_insight": comparison_insight,
    }


def run_benchmark(
    data: Dict[str, Any],
    context: Dict[str, Any],
    memory: List[Dict[str, Any]],
    use_llm: bool = False,
) -> Dict[str, Any]:
    """
    Experienced portfolio manager.

    Compare current case against past memory entries.
    If no memory exists, return a clear fallback response.
    """
    if not use_llm:
        return _run_benchmark_deterministic(data, context, memory)

    try:
        llm_result = _run_benchmark_llm(data, context, memory)
        llm_result["mode"] = "llm"
        return llm_result
    except Exception as exc:
        fallback = _run_benchmark_deterministic(data, context, memory)
        fallback["mode"] = "deterministic_fallback"
        fallback["llm_error"] = str(exc)
        return fallback
