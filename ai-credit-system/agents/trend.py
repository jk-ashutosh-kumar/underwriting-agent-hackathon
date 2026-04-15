"""Trend analysis agent logic."""

from __future__ import annotations

from typing import Any, Dict


def run_trend_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a basic trend summary using inflow and outflow totals."""
    inflow = float(data.get("total_inflow", 0))
    outflow = float(data.get("total_outflow", 0))
    profit = inflow - outflow

    if profit > 0:
        trend = "positive cashflow"
    elif profit < 0:
        trend = "negative cashflow"
    else:
        trend = "break-even"

    return {
        "agent": "trend_analyst",
        "inflow": inflow,
        "outflow": outflow,
        "profit": profit,
        "trend_summary": f"Business shows {trend} with net {profit:.2f}.",
    }
