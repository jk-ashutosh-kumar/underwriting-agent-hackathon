"""FastAPI backend for the AI Credit Underwriting frontend."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from logging.handlers import RotatingFileHandler

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env", override=True)

# Make agent logs visible in terminal and persist to file.
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = ROOT_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "backend.log"
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))

file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=2_000_000,
    backupCount=3,
    encoding="utf-8",
)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

logging.basicConfig(
    level=LOG_LEVEL,
    handlers=[stream_handler, file_handler],
    force=True,
)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from graph.flow import run_underwriting_flow
from ingestion.parser import parse_document
from memory.checkpoint import load_checkpoint
from memory.store import load_memory
from memory.store import save_case

app = FastAPI(title="AI Credit Underwriting API", version="1.0.0")
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SAMPLE_DATA_FILE = ROOT_DIR / "data" / "sample_statement.json"
REGIONAL_RULES_FILE = ROOT_DIR / "data" / "regional_rules.json"
CASES_MEMORY_FILE = ROOT_DIR / "data" / "cases_memory.json"


# --------------------------------------------------------------------------- #
# Request / Response Models
# --------------------------------------------------------------------------- #

class Transaction(BaseModel):
    date: str
    description: str
    amount: float
    type: str


class FinancialData(BaseModel):
    applicant_id: Optional[str] = None
    statement_month: Optional[str] = None
    transactions: List[Transaction]
    total_inflow: float
    total_outflow: float


class AnalyzeRequest(BaseModel):
    data: FinancialData
    region: str = "India"
    human_response: Optional[str] = ""


class ParseDocumentRequest(BaseModel):
    file_name: str
    file_type: str


class AuditResult(BaseModel):
    risk_score: int
    flags: List[str]
    explanation: str
    mode: Optional[str] = None
    llm_error: Optional[str] = None


class TrendResult(BaseModel):
    profit: float
    trend: str
    insight: str
    mode: Optional[str] = None
    llm_error: Optional[str] = None


class BenchmarkResult(BaseModel):
    benchmark_result: str
    comparison_insight: str
    mode: Optional[str] = None
    llm_error: Optional[str] = None


class UnderwritingResponse(BaseModel):
    risk_score: int
    decision_status: str
    agent_logs: List[str]
    audit: AuditResult
    trend: TrendResult
    benchmark: BenchmarkResult
    final_summary: str
    crew_status: str
    crew_mode: Optional[str] = None
    needs_hitl: bool


class PersistenceDebugResponse(BaseModel):
    cases_count: int
    last_case_id: Optional[str] = None
    last_case_timestamp: Optional[str] = None
    last_checkpoint_decision_status: Optional[str] = None
    last_checkpoint_risk_score: Optional[int] = None


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #

@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/sample")
def get_sample() -> Dict[str, Any]:
    """Return the sample financial statement."""
    if not SAMPLE_DATA_FILE.exists():
        raise HTTPException(status_code=404, detail="Sample data file not found")
    with SAMPLE_DATA_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/regions")
def get_regions() -> List[str]:
    """Return supported regions."""
    if REGIONAL_RULES_FILE.exists():
        with REGIONAL_RULES_FILE.open("r", encoding="utf-8") as f:
            rules = json.load(f)
        return list(rules.keys())
    return ["India", "Philippines"]


@app.get("/api/debug/persistence", response_model=PersistenceDebugResponse)
def get_persistence_debug() -> PersistenceDebugResponse:
    """Return quick persistence health snapshot for demo/debug."""
    cases = load_memory()
    checkpoint = load_checkpoint() or {}

    last_case = cases[-1] if cases else {}
    applicant_id = last_case.get("input_data", {}).get("applicant_id") if isinstance(last_case, dict) else None
    partner = last_case.get("partner") if isinstance(last_case, dict) else None
    last_case_id = applicant_id or partner or (f"case-{len(cases)}" if cases else None)
    last_case_timestamp = last_case.get("created_at") if isinstance(last_case, dict) else None
    if not last_case_timestamp and CASES_MEMORY_FILE.exists():
        # Fallback for legacy entries that predate created_at metadata.
        last_case_timestamp = datetime.fromtimestamp(
            CASES_MEMORY_FILE.stat().st_mtime, tz=timezone.utc
        ).isoformat()

    risk_val = checkpoint.get("risk_score")
    checkpoint_risk = int(risk_val) if isinstance(risk_val, (int, float)) else None

    return PersistenceDebugResponse(
        cases_count=len(cases),
        last_case_id=last_case_id,
        last_case_timestamp=last_case_timestamp,
        last_checkpoint_decision_status=checkpoint.get("decision_status"),
        last_checkpoint_risk_score=checkpoint_risk,
    )


@app.post("/api/parse-document")
def parse_uploaded_document(request: ParseDocumentRequest) -> Dict[str, Any]:
    """Normalize uploaded document metadata into financial data.

    NOTE: current parser is mock-based and deterministic for hackathon speed.
    """
    normalized_type = request.file_type.lower().strip()
    if normalized_type not in {"pdf", "json"}:
        raise HTTPException(status_code=400, detail="Unsupported document type")

    parsed = parse_document(request.file_name)
    return {
        "applicant_id": None,
        "statement_month": None,
        "transactions": parsed.get("transactions", []),
        "total_inflow": parsed.get("total_inflow", 0),
        "total_outflow": parsed.get("total_outflow", 0),
    }


@app.post("/api/underwrite", response_model=UnderwritingResponse)
def underwrite(request: AnalyzeRequest) -> UnderwritingResponse:
    """Run the full underwriting flow and return structured results."""
    try:
        data_dict = request.data.model_dump()
        state = run_underwriting_flow(
            data=data_dict,
            region=request.region,
            interactive=False,
            human_response=request.human_response or "",
        )

        audit = state.get("audit", {})
        trend = state.get("trend", {})
        benchmark = state.get("benchmark", {})
        committee = state.get("committee_output", {})

        # Fallback: extract from agent_logs if direct keys not on state
        # run_underwriting_flow returns UnderwritingState which may embed
        # committee output inside agent_logs. Re-run crew directly for structured
        # agent outputs.
        from agents.crew import run_crew

        crew_out = run_crew(data_dict, region=request.region)
        audit_data = crew_out.get("audit", crew_out.get("auditor", {}))
        trend_data = crew_out.get("trend", {})
        benchmark_data = crew_out.get("benchmark", {})

        decision_status = state.get("decision_status", "PENDING")
        needs_hitl = decision_status == "FLAGGED"

        # Persist each API-run case so frontend usage also updates memory store.
        case_payload = {
            "case_id": f"case-{int(datetime.now(timezone.utc).timestamp())}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "input_data": data_dict,
            "agent_outputs": crew_out,
            "decision": decision_status,
            "region": request.region,
            "risk_score": int(state.get("risk_score", audit_data.get("risk_score", 0))),
        }
        save_case(case_payload)
        logger.info("case_saved_to_memory_store")

        return UnderwritingResponse(
            risk_score=int(state.get("risk_score", audit_data.get("risk_score", 0))),
            decision_status=decision_status,
            agent_logs=state.get("agent_logs", []),
            audit=AuditResult(
                risk_score=int(audit_data.get("risk_score", 0)),
                flags=audit_data.get("flags", []),
                explanation=audit_data.get("explanation", ""),
                mode=audit_data.get("mode"),
                llm_error=audit_data.get("llm_error"),
            ),
            trend=TrendResult(
                profit=float(trend_data.get("profit", 0)),
                trend=trend_data.get("trend", "stable"),
                insight=trend_data.get("insight", ""),
                mode=trend_data.get("mode"),
                llm_error=trend_data.get("llm_error"),
            ),
            benchmark=BenchmarkResult(
                benchmark_result=benchmark_data.get("benchmark_result", ""),
                comparison_insight=benchmark_data.get("comparison_insight", ""),
                mode=benchmark_data.get("mode"),
                llm_error=benchmark_data.get("llm_error"),
            ),
            final_summary=crew_out.get("final_summary", ""),
            crew_status=crew_out.get("crew_status", ""),
            crew_mode=crew_out.get("mode"),
            needs_hitl=needs_hitl,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8010"))
    uvicorn.run("api_server:app", host="0.0.0.0", port=port, reload=True)
