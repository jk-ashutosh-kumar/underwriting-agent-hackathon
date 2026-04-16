"""Trend analysis agent for growth-oriented interpretation."""

from __future__ import annotations

import logging
from typing import Any, Dict

from llm.client import ask_llm_json

logger = logging.getLogger(__name__)


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

    return {
        "profit": float(profit),
        "trend": trend,
        "insight": insight,
    }


def _run_trend_llm(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """LLM-assisted trend analysis with strict output schema."""
    region = context.get("region", "Unknown")
    inflow = float(data.get("total_inflow", 0))
    outflow = float(data.get("total_outflow", 0))
    system_prompt = (
        "You are a data-driven strategist focused on growth. "
        "Return ONLY JSON with keys: profit (number), trend (string), insight (string)."
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
    return {"profit": profit, "trend": trend, "insight": insight}


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
