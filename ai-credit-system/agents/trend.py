"""Trend analysis agent for growth-oriented interpretation."""

from __future__ import annotations

import logging
from typing import Any, Dict

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


def _run_trend_deterministic(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Current deterministic implementation kept as safe fallback."""
    inflow = float(data.get("total_inflow", 0))
    outflow = float(data.get("total_outflow", 0))
    profit = inflow - outflow

    # Small ratio-based indicator for demo clarity.
    # > 1.2 is "growing", around 1.0 is "stable", below 1.0 is "shrinking".
    growth_ratio = (inflow / outflow) if outflow > 0 else 0.0
    if growth_ratio > 1.2:
        trend = "growing"
    elif growth_ratio >= 1.0:
        trend = "stable"
    else:
        trend = "shrinking"

    region = context.get("region", "Unknown")
    insight = (
        f"In {region}, inflow is {inflow:.2f} and outflow is {outflow:.2f}, "
        f"so estimated profit is {profit:.2f}. Growth ratio is {growth_ratio:.2f}, "
        f"which I classify as '{trend}' for this demo."
    )

    result = {
        "profit": float(profit),
        "trend": trend,
        "insight": insight,
        "risk_drivers": ["Shrinking cashflow trend detected"] if trend == "shrinking" else [],
        "positive_signals": ["Healthy cashflow spread"] if trend == "growing" else [],
        "uncertainties": ["Single-period cashflow may hide seasonality effects."],
        "recommendation": "approve" if trend == "growing" else ("review" if trend == "stable" else "reject"),
    }
    return _with_handoff(result)


def _run_trend_llm(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """LLM-assisted trend analysis with strict output schema."""
    region = context.get("region", "Unknown")
    inflow = float(data.get("total_inflow", 0))
    outflow = float(data.get("total_outflow", 0))
    system_prompt = (
        "You are a data-driven strategist focused on growth. "
        "Return ONLY JSON with keys: profit (number), trend (string), insight (string), "
        "risk_drivers (string list), positive_signals (string list), uncertainties (string list), "
        "recommendation (approve|review|reject)."
    )
    user_prompt = (
        "Analyze business cashflow trend.\n"
        f"Region: {region}\n"
        f"Total inflow: {inflow}\n"
        f"Total outflow: {outflow}\n"
        "Classify trend as one of: growing, stable, shrinking. "
        "Keep insight concise and explain the reason."
    )
    payload = ask_llm_json(system_prompt=system_prompt, user_prompt=user_prompt)
    profit = float(payload.get("profit", inflow - outflow))
    trend = str(payload.get("trend", "stable")).lower().strip()
    if trend not in {"growing", "stable", "shrinking"}:
        trend = "stable"
    insight = str(payload.get("insight", "No insight provided by LLM."))
    logger.info(
        "trend_llm_completed",
        extra={"region": region, "trend": trend, "profit": profit},
    )
    return _with_handoff({"profit": profit, "trend": trend, "insight": insight})


def run_trend_analysis(data: Dict[str, Any], context: Dict[str, Any], use_llm: bool = False) -> Dict[str, Any]:
    """
    Data-driven strategist focused on growth.

    Required simple logic:
    - profit = inflow - outflow
    - simple growth indicator
    """
    if not use_llm:
        return _run_trend_deterministic(data, context)

    try:
        llm_result = _run_trend_llm(data, context)
        llm_result["mode"] = "llm"
        return llm_result
    except Exception as exc:
        fallback = _run_trend_deterministic(data, context)
        fallback["mode"] = "deterministic_fallback"
        fallback["llm_error"] = str(exc)
        return fallback
