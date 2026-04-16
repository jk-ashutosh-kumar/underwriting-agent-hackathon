"""Adapter that maps LangGraph runtime to existing API/UI contracts.

This file is the migration safety layer:
- Keep frontend payload shape unchanged.
- Provide optional pause/resume semantics for HITL.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, Optional
from uuid import uuid4

from graph.flow import _progress_event
from graph.langgraph_app import LANGGRAPH_RUNTIME
from memory.checkpoint import save_checkpoint


def run_langgraph_flow(
    data: Dict[str, Any],
    region: str,
    human_input: Optional[str] = None,
    *,
    thread_id: Optional[str] = None,
    auto_resume: bool = False,
) -> Dict[str, Any]:
    """Run LangGraph once and return compact adapter payload.

    Returns a stable payload compatible with existing backend expectations:
    - active_index
    - label
    - logs
    - decision
    Plus migration metadata:
    - status
    - thread_id
    """
    resolved_thread_id = thread_id or f"lg-{uuid4().hex[:12]}"
    first = LANGGRAPH_RUNTIME.run(
        data=data,
        region=region,
        thread_id=resolved_thread_id,
        human_input=human_input,
    )

    if first["status"] == "NEEDS_INPUT" and auto_resume:
        second = LANGGRAPH_RUNTIME.run(
            data=data,
            region=region,
            thread_id=resolved_thread_id,
            human_input=human_input or "No clarification provided",
        )
        first = second

    state = first["state"]
    return {
        "status": first["status"],
        "thread_id": first["thread_id"],
        "active_index": 6 if first["status"] == "COMPLETED" else 3,
        "label": "Persisting checkpoint" if first["status"] == "COMPLETED" else "Human-in-the-loop required",
        "logs": state.get("agent_logs", []),
        "decision": state.get("decision_status", "PENDING"),
        "state": state,
    }


def iter_langgraph_flow_events(
    data: Dict[str, Any],
    region: str,
    human_input: Optional[str] = None,
    *,
    thread_id: Optional[str] = None,
    auto_resume: bool = True,
) -> Iterator[Dict[str, Any]]:
    """Yield progress events in the existing NDJSON-friendly shape."""
    yield _progress_event("ingesting", "ingesting", "Preparing case folder")
    yield _progress_event("analysis", "analysis", "Multi-agent committee (Audit / Trend / Benchmark)")
    yield _progress_event("router", "router", "Policy routing & gates")

    result = run_langgraph_flow(
        data=data,
        region=region,
        human_input=human_input,
        thread_id=thread_id,
        auto_resume=auto_resume,
    )
    state = result["state"]
    route = state.get("route", "review")
    yield _progress_event("router_done", "route_decision", f"Route selected: {route}", route=route)

    if result["status"] == "NEEDS_INPUT":
        yield _progress_event(
            "hitl",
            "hitl",
            "Human-in-the-loop — capture clarification",
            human_in_loop=True,
            thread_id=result["thread_id"],
        )
        yield {"type": "interrupt", "status": "NEEDS_INPUT", "thread_id": result["thread_id"]}
        return

    if route == "hitl":
        yield _progress_event("hitl", "hitl", "Human-in-the-loop — capture clarification", human_in_loop=True)
        yield _progress_event("resume", "resume", "Resume pipeline after HITL")
    else:
        yield _progress_event(
            "hitl_skipped",
            "hitl_skipped",
            f"HITL: not required ({route} path)",
            skipped_steps=["hitl"],
        )
        yield _progress_event(
            "resume_skipped",
            "resume_skipped",
            "Resume: not required",
            skipped_steps=["hitl", "resume"],
        )

    yield _progress_event("deciding", "decision", "Final underwriting decision")
    save_checkpoint(state)
    yield _progress_event("checkpoint", "checkpoint", "Persisting checkpoint")
    yield {"type": "complete", "state": state}


if __name__ == "__main__":
    # Minimal migration sanity checks.
    sample = {
        "transactions": [
            {"date": "2026-01-01", "description": "Salary", "amount": 120000, "type": "credit"},
            {"date": "2026-01-05", "description": "Rent", "amount": 25000, "type": "debit"},
        ],
        "total_inflow": 120000,
        "total_outflow": 25000,
    }
    print("=== Case 1: Non-HITL ===")
    print(run_langgraph_flow(sample, "India", auto_resume=True))

    suspicious = {
        "transactions": [
            {"date": "2026-01-01", "description": "", "amount": 90000, "type": "debit"},
        ],
        "total_inflow": 100000,
        "total_outflow": 90000,
    }
    print("=== Case 2: HITL pause ===")
    paused = run_langgraph_flow(suspicious, "India", auto_resume=False)
    print(paused)
    if paused["status"] == "NEEDS_INPUT":
        print("=== Case 2: HITL resume ===")
        resumed = run_langgraph_flow(
            suspicious,
            "India",
            human_input="Large transfer was a one-time vendor prepayment.",
            thread_id=paused["thread_id"],
            auto_resume=False,
        )
        print(resumed)
