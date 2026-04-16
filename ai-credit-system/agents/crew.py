"""Multi-Agent Credit Committee orchestration for hackathon demos."""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

from agents.auditor import run_auditor
from agents.benchmark import run_benchmark
from agents.trend import run_trend_analysis
from llm.client import ask_llm_json
from memory.store import load_memory
from tools.accounting_tool import AccountingModuleTool

ROOT_DIR = Path(__file__).resolve().parents[1]
REGIONAL_RULES_FILE = ROOT_DIR / "data" / "regional_rules.json"
SAMPLE_DATA_FILE = ROOT_DIR / "data" / "sample_statement.json"


def _load_regional_rules() -> Dict[str, Any]:
    """Load regional thresholds and keywords from JSON config."""
    if not REGIONAL_RULES_FILE.exists():
        # Safe fallback to keep demo runnable even if file is missing.
        return {"India": {"dscr_threshold": 1.2, "large_txn_threshold": 100000, "keywords": []}}
    with REGIONAL_RULES_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _build_region_context(region: str) -> Dict[str, Any]:
    """Build context object injected into all agent tasks."""
    rules = _load_regional_rules()
    region_rules = rules.get(region, rules.get("India", {}))
    return {
        "region": region,
        "dscr_threshold": region_rules.get("dscr_threshold", 1.2),
        "large_txn_threshold": region_rules.get("large_txn_threshold", 100000),
        "keywords": region_rules.get("keywords", []),
    }


def _build_crewai_committee(region_context: Dict[str, Any], use_llm: bool) -> Dict[str, str]:
    """
    Create CrewAI agents and tasks with region-aware context injection.

    We keep this lightweight and avoid mandatory LLM kickoff so the project
    remains stable in hackathon environments.
    """
    try:
        from crewai import Agent, Crew, Task
    except Exception as exc:
        # Import failure only skips CrewAI wiring. run_crew() still calls auditor/trend/benchmark
        # directly; those honor USE_LLM independently — do not label the whole run "deterministic".
        logger.warning("crewai_import_failed: %s", exc)
        return {
            "status": (
                "CrewAI package import failed (orchestration skipped); "
                "auditor/trend/benchmark still run via direct calls — see each agent's mode from USE_LLM."
            )
        }

    accounting_tool = AccountingModuleTool()
    region = region_context["region"]
    large_threshold = region_context["large_txn_threshold"]
    keywords = ", ".join(region_context["keywords"]) or "N/A"

    # Distinct personas requested by the prompt.
    # Some CrewAI + tool combinations raise KeyError 'tools' if the tool is not a real BaseTool
    # instance for that version — fall back to no tools rather than failing the whole API.
    try:
        auditor_agent = Agent(
            role="Fraud Detection Specialist",
            goal="Detect anomalies and suspicious transaction behavior",
            backstory="Skeptical forensic accountant who trusts no one.",
            verbose=False,
            tools=[accounting_tool],
        )
    except Exception as exc:
        logger.warning("crewai_auditor_tools_skipped: %s", exc)
        auditor_agent = Agent(
            role="Fraud Detection Specialist",
            goal="Detect anomalies and suspicious transaction behavior",
            backstory="Skeptical forensic accountant who trusts no one.",
            verbose=False,
            tools=[],
        )
    trend_agent = Agent(
        role="Growth Analyst",
        goal="Analyze financial trends and profitability direction",
        backstory="Data-driven strategist focused on growth.",
        verbose=False,
    )
    benchmark_agent = Agent(
        role="Portfolio Manager",
        goal="Compare current applicant with historical portfolio behavior",
        backstory="Experienced portfolio manager.",
        verbose=False,
    )

    # Region-aware context injection directly inside task text.
    audit_task = Task(
        description=(
            f"This is a financial statement from {region}. "
            f"Apply rules: large transaction threshold = {large_threshold}; "
            f"consider keywords/patterns: {keywords}. "
            "Analyze fraud risk and explain WHY."
        ),
        agent=auditor_agent,
        expected_output="Fraud risk assessment with clear explanation and flags.",
    )
    trend_task = Task(
        description=(
            "Using financial totals and prior audit findings, determine growth trend, "
            "profitability, and explain WHY your trend label is reasonable."
        ),
        agent=trend_agent,
        context=[audit_task],  # Context pass from Task 1 -> Task 2.
        expected_output="Profit, trend label, and explainable growth insight.",
    )
    benchmark_task = Task(
        description=(
            "Compare this case against memory/history and prior task outputs. "
            "State whether this looks closer to high-risk or stable historical partners."
        ),
        agent=benchmark_agent,
        context=[audit_task, trend_task],  # Context pass from previous tasks.
        expected_output="Benchmark result plus historical comparison insight.",
    )

    # Build Crew object for demo visibility. We do not call kickoff here by default.
    crew_obj = Crew(
        agents=[auditor_agent, trend_agent, benchmark_agent],
        tasks=[audit_task, trend_task, benchmark_task],
        verbose=False,
    )
    use_crewai_kickoff = os.getenv("USE_CREWAI_KICKOFF", "false").lower() in {"1", "true", "yes"}
    # Safety gate: CrewAI kickoff can trigger provider calls internally.
    # If USE_LLM is false, force direct orchestration fallback to avoid unexpected OpenAI loops.
    if use_crewai_kickoff and not use_llm:
        return {
            "status": (
                "CrewAI configured but kickoff skipped because USE_LLM=false; "
                "using direct orchestration path."
            )
        }

    if use_crewai_kickoff and use_llm:
        kickoff_timeout_s = float(os.getenv("CREWAI_KICKOFF_TIMEOUT_SECONDS", "8"))
        ex = ThreadPoolExecutor(max_workers=1)
        try:
            future = ex.submit(crew_obj.kickoff)
            kickoff_result = future.result(timeout=kickoff_timeout_s)
            ex.shutdown(wait=False, cancel_futures=True)
            return {
                "status": "CrewAI kickoff executed successfully with chained tasks.",
                "kickoff_summary": str(kickoff_result)[:500],
            }
        except FuturesTimeoutError:
            # Important: do NOT wait for completion after timeout, otherwise request still blocks.
            ex.shutdown(wait=False, cancel_futures=True)
            logger.warning("crewai_kickoff_timeout after %.1fs", kickoff_timeout_s)
            return {
                "status": (
                    "CrewAI configured but kickoff timed out; using direct orchestration fallback. "
                    f"Timeout: {kickoff_timeout_s:.1f}s"
                )
            }
        except Exception as exc:
            ex.shutdown(wait=False, cancel_futures=True)
            logger.warning("crewai_kickoff_failed: %s", exc)
            return {
                "status": (
                    "CrewAI configured but kickoff failed; using direct orchestration fallback. "
                    f"Error: {exc}"
                )
            }
    return {"status": "CrewAI committee configured with 3 agents and chained tasks."}


def _collect_points(*values: Any) -> List[str]:
    out: List[str] = []
    for value in values:
        if isinstance(value, list):
            out.extend([str(x) for x in value if str(x).strip()])
    # Deduplicate while preserving order.
    seen = set()
    deduped: List[str] = []
    for item in out:
        key = item.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _committee_chair_deterministic(
    audit: Dict[str, Any],
    trend: Dict[str, Any],
    benchmark: Dict[str, Any],
    *,
    region: str,
    memory_count: int,
    hitl_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Deterministic committee-chair synthesis over structured handoff outputs."""
    risk_score = int(audit.get("risk_score", 0))
    trend_label = str(trend.get("trend", "stable"))
    benchmark_view = str(benchmark.get("benchmark_result", "No historical comparison"))

    risk_drivers = _collect_points(
        audit.get("risk_drivers"),
        trend.get("risk_drivers"),
        benchmark.get("risk_drivers"),
    )
    positives = _collect_points(
        audit.get("positive_signals"),
        trend.get("positive_signals"),
        benchmark.get("positive_signals"),
    )
    uncertainties = _collect_points(
        audit.get("uncertainties"),
        trend.get("uncertainties"),
        benchmark.get("uncertainties"),
    )

    if hitl_context:
        msg = str(hitl_context.get("message", "")).strip()
        if msg:
            uncertainties = [msg] + uncertainties

    votes = [
        str(audit.get("recommendation", "review")).lower(),
        str(trend.get("recommendation", "review")).lower(),
        str(benchmark.get("recommendation", "review")).lower(),
    ]
    approve_votes = sum(v == "approve" for v in votes)
    reject_votes = sum(v == "reject" for v in votes)
    review_votes = sum(v == "review" for v in votes)

    if reject_votes >= 2 or risk_score >= 70:
        posture = "conservative"
        confidence = 82
    elif approve_votes >= 2 and risk_score <= 40:
        posture = "favorable"
        confidence = 78
    else:
        posture = "balanced"
        confidence = 64 + max(0, approve_votes - review_votes) * 5 - reject_votes * 4
        confidence = max(40, min(90, confidence))

    key_supporting_points = (positives or [str(trend.get("insight", "")), str(benchmark.get("comparison_insight", ""))])[:3]
    key_risks = (risk_drivers or [str(audit.get("explanation", ""))])[:3]
    conditions_if_approved = (
        ["Monthly statement monitoring", "No single undocumented transfer above policy threshold"]
        if posture in {"balanced", "conservative"}
        else []
    )

    final_verdict_rationale = (
        f"Committee chair view ({region}): audit risk is {risk_score}/100, trend is '{trend_label}', "
        f"benchmark indicates '{benchmark_view}', memory cases reviewed={memory_count}. "
        f"Overall posture is {posture}."
    )
    final_summary = (
        f"Committee Summary ({region}): {final_verdict_rationale} "
        f"Top supports: {', '.join(key_supporting_points[:2]) or 'N/A'}. "
        f"Top risks: {', '.join(key_risks[:2]) or 'N/A'}."
    )

    return {
        "final_summary": final_summary,
        "final_verdict_rationale": final_verdict_rationale,
        "key_supporting_points": key_supporting_points,
        "key_risks": key_risks,
        "confidence": int(confidence),
        "conditions_if_approved": conditions_if_approved,
    }


def _committee_chair_llm(
    audit: Dict[str, Any],
    trend: Dict[str, Any],
    benchmark: Dict[str, Any],
    *,
    region: str,
    memory_count: int,
    hitl_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    system_prompt = (
        "You are the committee chair synthesizing underwriting committee outputs. "
        "Return ONLY JSON with keys: final_summary (string), final_verdict_rationale (string), "
        "key_supporting_points (string list), key_risks (string list), confidence (0-100 int), "
        "conditions_if_approved (string list)."
    )
    user_prompt = (
        f"Region: {region}\n"
        f"Memory count: {memory_count}\n"
        f"HITL context: {hitl_context}\n"
        f"Audit output: {audit}\n"
        f"Trend output: {trend}\n"
        f"Benchmark output: {benchmark}\n"
        "Synthesize a concise, explainable committee chair verdict."
    )
    payload = ask_llm_json(system_prompt=system_prompt, user_prompt=user_prompt)
    return {
        "final_summary": str(payload.get("final_summary", "")),
        "final_verdict_rationale": str(payload.get("final_verdict_rationale", "")),
        "key_supporting_points": [str(x) for x in payload.get("key_supporting_points", [])][:3]
        if isinstance(payload.get("key_supporting_points"), list)
        else [],
        "key_risks": [str(x) for x in payload.get("key_risks", [])][:3]
        if isinstance(payload.get("key_risks"), list)
        else [],
        "confidence": max(0, min(100, int(payload.get("confidence", 60)))),
        "conditions_if_approved": [str(x) for x in payload.get("conditions_if_approved", [])]
        if isinstance(payload.get("conditions_if_approved"), list)
        else [],
    }


def run_crew(data: Dict[str, Any], region: str = "India") -> Dict[str, Any]:
    """Run the multi-agent committee and return explainable outputs."""
    region_context = _build_region_context(region)
    use_llm = os.getenv("USE_LLM", "false").lower() in {"1", "true", "yes"}
    logger.info("run_crew_start use_llm=%s use_crewai_kickoff=%s", use_llm, os.getenv("USE_CREWAI_KICKOFF", "false"))
    crew_meta = _build_crewai_committee(region_context, use_llm=use_llm)
    committee_mode = "LLM (USE_LLM)" if use_llm else "rules (USE_LLM off)"

    # Tool output is included in context so the committee appears integrated with
    # external accounting information, even in deterministic demo mode.
    accounting_tool = AccountingModuleTool()
    accounting_signal = accounting_tool._run("repayment trend")
    region_context["accounting_tool_signal"] = accounting_signal

    # Task 1: Auditor
    audit = run_auditor(data, region_context, use_llm=use_llm)

    # Task 2: Trend (receives context from audit)
    trend_context = {**region_context, "audit_result": audit}
    trend = run_trend_analysis(data, trend_context, use_llm=use_llm)

    # Task 3: Benchmark (receives prior outputs + memory)
    memory_entries = load_memory()
    benchmark_context = {**trend_context, "trend_result": trend}
    benchmark = run_benchmark(data, benchmark_context, memory_entries, use_llm=use_llm)
    # Committee Chair: synthesizes committee outputs into explainable verdict bundle.
    chair = _committee_chair_deterministic(
        audit,
        trend,
        benchmark,
        region=region,
        memory_count=len(memory_entries),
    )
    if use_llm:
        try:
            llm_chair = _committee_chair_llm(
                audit,
                trend,
                benchmark,
                region=region,
                memory_count=len(memory_entries),
            )
            # Only overwrite fields when LLM returns usable values.
            for key, value in llm_chair.items():
                if value:
                    chair[key] = value
            chair["mode"] = "llm"
        except Exception as exc:
            chair["mode"] = "deterministic_fallback"
            chair["llm_error"] = str(exc)
    chair["accounting_signal"] = accounting_signal

    crew_status = crew_meta["status"]
    if "import failed" in crew_status or "import unavailable" in crew_status:
        crew_status = f"{crew_status} Active committee path: {committee_mode}."

    return {
        "audit": audit,
        "trend": trend,
        "benchmark": benchmark,
        # Backward-compatible keys for existing UI/CLI references.
        "auditor": audit,
        "final_summary": chair.get("final_summary", ""),
        "committee_chair": chair,
        "crew_kickoff_summary": crew_meta.get("kickoff_summary"),
        "mode": "llm" if use_llm else "deterministic",
        "crew_status": crew_status,
    }


if __name__ == "__main__":
    # Runnable local test for demo day.
    with SAMPLE_DATA_FILE.open("r", encoding="utf-8") as f:
        sample_data = json.load(f)

    result = run_crew(sample_data, region="India")
    print(json.dumps(result, indent=2))
