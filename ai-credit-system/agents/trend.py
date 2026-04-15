"""Trend analysis agent for growth-oriented interpretation."""

from __future__ import annotations

from typing import Any, Dict


def run_trend_analysis(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Data-driven strategist focused on growth.

    Required simple logic:
    - profit = inflow - outflow
    - simple growth indicator
    """
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
