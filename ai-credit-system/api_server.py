"""FastAPI backend for the AI Credit Underwriting frontend."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from graph.flow import run_underwriting_flow
from ingestion.parser import parse_document

app = FastAPI(title="AI Credit Underwriting API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SAMPLE_DATA_FILE = ROOT_DIR / "data" / "sample_statement.json"
REGIONAL_RULES_FILE = ROOT_DIR / "data" / "regional_rules.json"


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


class TrendResult(BaseModel):
    profit: float
    trend: str
    insight: str


class BenchmarkResult(BaseModel):
    benchmark_result: str
    comparison_insight: str


class UnderwritingResponse(BaseModel):
    risk_score: int
    decision_status: str
    agent_logs: List[str]
    audit: AuditResult
    trend: TrendResult
    benchmark: BenchmarkResult
    final_summary: str
    crew_status: str
    needs_hitl: bool


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

        return UnderwritingResponse(
            risk_score=int(state.get("risk_score", audit_data.get("risk_score", 0))),
            decision_status=decision_status,
            agent_logs=state.get("agent_logs", []),
            audit=AuditResult(
                risk_score=int(audit_data.get("risk_score", 0)),
                flags=audit_data.get("flags", []),
                explanation=audit_data.get("explanation", ""),
            ),
            trend=TrendResult(
                profit=float(trend_data.get("profit", 0)),
                trend=trend_data.get("trend", "stable"),
                insight=trend_data.get("insight", ""),
            ),
            benchmark=BenchmarkResult(
                benchmark_result=benchmark_data.get("benchmark_result", ""),
                comparison_insight=benchmark_data.get("comparison_insight", ""),
            ),
            final_summary=crew_out.get("final_summary", ""),
            crew_status=crew_out.get("crew_status", ""),
            needs_hitl=needs_hitl,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8010"))
    uvicorn.run("api_server:app", host="0.0.0.0", port=port, reload=True)
