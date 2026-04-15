"""Benchmark agent logic."""

from __future__ import annotations

from typing import Any, Dict


def run_benchmark(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a mock market benchmark comparison."""
    _ = data
    return {
        "agent": "benchmarker",
        "segment": "SME Lending",
        "performance_band": "average performer",
        "summary": "Applicant is comparable to peer median on liquidity and repayment behavior.",
    }
