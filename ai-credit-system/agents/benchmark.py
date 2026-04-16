"""Benchmark agent that compares with simple memory history."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from llm.client import ask_llm_json

logger = logging.getLogger(__name__)


def _with_handoff(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure structured handoff keys exist for downstream agents."""
    payload["risk_drivers"] = (
        [str(x) for x in payload.get("risk_drivers", [])]
        if isinstance(payload.get("risk_drivers"), list)
        else []
    )
    payload["positive_signals"] = (
        [str(x) for x in payload.get("positive_signals", [])]
        if isinstance(payload.get("positive_signals"), list)
        else []
    )
    payload["uncertainties"] = (
        [str(x) for x in payload.get("uncertainties", [])]
        if isinstance(payload.get("uncertainties"), list)
        else []
    )
    recommendation = payload.get("recommendation")
    payload["recommendation"] = (
        str(recommendation)
        if isinstance(recommendation, str) and recommendation.strip()
        else "review"
    )
    return payload


def _summarize_memory(memory: List[Dict[str, Any]]) -> Tuple[int, int]:
    """Return (total_cases, high_risk_cases) from current memory schema."""
    total = len(memory)
    high = 0
    for entry in memory:
        decision = str(entry.get("decision", "")).upper()
        risk_val = entry.get("risk_score")
        risk_num = float(risk_val) if isinstance(risk_val, (int, float)) else None
        if decision in {"REJECTED", "FLAGGED"}:
            high += 1
            continue
        if risk_num is not None and risk_num >= 60:
            high += 1
            continue
        # Backward compatibility for older memory format.
        if str(entry.get("risk", "")).lower() == "high":
            high += 1
    return total, high


def _run_benchmark_deterministic(
    data: Dict[str, Any], context: Dict[str, Any], memory: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Current deterministic implementation kept as safe fallback."""
    _ = data
    _ = context

    if not memory:
        return _with_handoff({
            "benchmark_result": "No historical comparison",
            "comparison_insight": (
                "I cannot compare against portfolio history yet because memory is empty. "
                "Run a few cases first to enable historical benchmarking."
            ),
            "risk_drivers": [],
            "positive_signals": [],
            "uncertainties": ["No historical memory available."],
            "recommendation": "review",
        })

    total_cases, high_risk_count = _summarize_memory(memory)
    high_risk_ratio = high_risk_count / max(total_cases, 1)

    if high_risk_ratio >= 0.5:
        benchmark_result = "Risk profile is closer to historically higher-risk partners"
    else:
        benchmark_result = "Risk profile is closer to historically stable partners"

    comparison_insight = (
        f"I reviewed {total_cases} memory cases; {high_risk_count} were high risk. "
        f"This suggests the current case aligns with '{benchmark_result}'."
    )

    return _with_handoff({
        "benchmark_result": benchmark_result,
        "comparison_insight": comparison_insight,
        "risk_drivers": (
            ["High proportion of risky historical cases."]
            if high_risk_ratio >= 0.5
            else []
        ),
        "positive_signals": (
            ["Historical portfolio shows more stable than risky cases."]
            if high_risk_ratio < 0.5
            else []
        ),
        "uncertainties": ["Historical memory size and distribution may be limited."],
        "recommendation": "review" if high_risk_ratio >= 0.5 else "approve",
    })


def _run_benchmark_llm(
    data: Dict[str, Any], context: Dict[str, Any], memory: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """LLM-assisted benchmark analysis with strict output schema."""
    _ = data
    region = context.get("region", "Unknown")
    if not memory:
        return _with_handoff({
            "benchmark_result": "No historical comparison",
            "comparison_insight": (
                "I cannot compare against portfolio history yet because memory is empty. "
                "Run a few cases first to enable historical benchmarking."
            ),
            "risk_drivers": [],
            "positive_signals": [],
            "uncertainties": ["No historical memory available."],
            "recommendation": "review",
        })

    system_prompt = (
        "You are an experienced portfolio manager. "
        "Return ONLY JSON with keys: benchmark_result (string), comparison_insight (string), "
        "risk_drivers (string list), positive_signals (string list), uncertainties (string list), "
        "recommendation (approve|review|reject)."
    )
    # Keep LLM context compact and schema-stable.
    memory_snapshot = [
        {
            "case_id": entry.get("case_id"),
            "decision": entry.get("decision"),
            "risk_score": entry.get("risk_score"),
            "region": entry.get("region"),
        }
        for entry in memory[-25:]
    ]
    user_prompt = (
        "Compare a current underwriting case against historical memory entries.\n"
        f"Region: {region}\n"
        f"Memory entries (last {len(memory_snapshot)}): {memory_snapshot}\n"
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
    return _with_handoff({
        "benchmark_result": benchmark_result,
        "comparison_insight": comparison_insight,
    })


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
        # Guardrail: never claim "no historical comparison" when memory is non-empty.
        if memory and "no historical comparison" in str(llm_result.get("benchmark_result", "")).lower():
            deterministic = _run_benchmark_deterministic(data, context, memory)
            deterministic["mode"] = "deterministic_guardrail"
            deterministic["llm_error"] = (
                "LLM returned no-history judgement despite non-empty memory; "
                "used deterministic benchmark guardrail."
            )
            return deterministic
        llm_result["mode"] = "llm"
        return llm_result
    except Exception as exc:
        fallback = _run_benchmark_deterministic(data, context, memory)
        fallback["mode"] = "deterministic_fallback"
        fallback["llm_error"] = str(exc)
        return fallback
