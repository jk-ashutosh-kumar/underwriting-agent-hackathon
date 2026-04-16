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

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from graph.flow import iter_underwriting_flow_events, run_underwriting_flow
LANGGRAPH_IMPORT_ERROR: Optional[str] = None
try:
    # Optional migration path: fallback to legacy flow if LangGraph imports fail.
    from graph.adapter import iter_langgraph_flow_events, run_langgraph_flow
except Exception as exc:  # pragma: no cover - safe fallback when langgraph deps are unavailable
    LANGGRAPH_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
    iter_langgraph_flow_events = None  # type: ignore[assignment]
    run_langgraph_flow = None  # type: ignore[assignment]
from ingestion.parser import parse_document  # legacy mock fallback
from ingestion.db import (
    get_documents_by_case,
    get_or_create_case,
    list_companies_with_cases,
    list_schemas,
)
from ingestion.models import CompanyCaseSummary, DocumentSummary, IngestResponse
from ingestion.pipeline import run_pipeline
from webhooks import list_webhooks, register, unregister
from memory.checkpoint import load_checkpoint
from memory.store import load_memory
from memory.store import save_case

app = FastAPI(title="AI Credit Underwriting API", version="1.0.0")
logger = logging.getLogger(__name__)
if LANGGRAPH_IMPORT_ERROR:
    logger.warning("langgraph_import_unavailable error=%s", LANGGRAPH_IMPORT_ERROR)

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
USE_LANGGRAPH = os.getenv("USE_LANGGRAPH", "false").strip().lower() in {"1", "true", "yes", "on"}


def _crew_output_from_state(state: Dict[str, Any], data_dict: Dict[str, Any], region: str) -> Dict[str, Any]:
    """Use committee output cached on state when present to avoid duplicate LLM calls."""
    cached = state.get("committee_output")
    if isinstance(cached, dict) and cached:
        return cached
    from agents.crew import run_crew

    return run_crew(data_dict, region=region)


def _build_underwriting_response(
    state: Dict[str, Any],
    data_dict: Dict[str, Any],
    region: str,
) -> UnderwritingResponse:
    """Build API response model from flow state + crew outputs."""
    crew_out = _crew_output_from_state(state, data_dict, region)
    audit_data = crew_out.get("audit", crew_out.get("auditor", {}))
    trend_data = crew_out.get("trend", {})
    benchmark_data = crew_out.get("benchmark", {})
    committee_chair_data = crew_out.get("committee_chair", {})

    decision_status = state.get("decision_status", "PENDING")
    needs_hitl = decision_status == "FLAGGED"

    case_payload = {
        "case_id": f"case-{int(datetime.now(timezone.utc).timestamp())}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_data": data_dict,
        "agent_outputs": crew_out,
        "decision": decision_status,
        "region": region,
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
        committee_chair=CommitteeChairResult(
            final_verdict_rationale=committee_chair_data.get("final_verdict_rationale", ""),
            key_supporting_points=committee_chair_data.get("key_supporting_points", []),
            key_risks=committee_chair_data.get("key_risks", []),
            confidence=int(committee_chair_data.get("confidence", 0)),
            conditions_if_approved=committee_chair_data.get("conditions_if_approved", []),
            mode=committee_chair_data.get("mode"),
            llm_error=committee_chair_data.get("llm_error"),
        ),
        final_summary=crew_out.get("final_summary", ""),
        crew_status=crew_out.get("crew_status", ""),
        crew_mode=crew_out.get("mode"),
        needs_hitl=needs_hitl,
    )


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
    thread_id: Optional[str] = None


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


class CommitteeChairResult(BaseModel):
    final_verdict_rationale: str = ""
    key_supporting_points: List[str] = []
    key_risks: List[str] = []
    confidence: int = 0
    conditions_if_approved: List[str] = []
    mode: Optional[str] = None
    llm_error: Optional[str] = None


class UnderwritingResponse(BaseModel):
    risk_score: int
    decision_status: str
    agent_logs: List[str]
    audit: AuditResult
    trend: TrendResult
    benchmark: BenchmarkResult
    committee_chair: CommitteeChairResult
    final_summary: str
    crew_status: str
    crew_mode: Optional[str] = None
    needs_hitl: bool


class LangGraphFlowResponse(BaseModel):
    status: str  # COMPLETED | NEEDS_INPUT
    thread_id: str
    active_index: int
    label: str
    logs: List[str]
    decision: str
    hitl_context: Optional[Dict[str, Any]] = None
    result: Optional[UnderwritingResponse] = None


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


# --------------------------------------------------------------------------- #
# Webhook endpoints
# --------------------------------------------------------------------------- #

class WebhookRequest(BaseModel):
    url: str


@app.post("/api/webhooks/register", status_code=201)
def register_webhook(body: WebhookRequest) -> Dict[str, Any]:
    """Register a URL to receive document.extraction.completed events."""
    added = register(body.url)
    return {"url": body.url, "registered": added}


@app.delete("/api/webhooks/unregister")
def unregister_webhook(body: WebhookRequest) -> Dict[str, Any]:
    """Remove a previously registered webhook URL."""
    removed = unregister(body.url)
    if not removed:
        raise HTTPException(status_code=404, detail="URL not found in registry")
    return {"url": body.url, "unregistered": True}


@app.get("/api/webhooks")
def get_webhooks() -> Dict[str, Any]:
    """List all registered webhook URLs."""
    return {"webhooks": list_webhooks()}


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


ALLOWED_UPLOAD_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@app.post("/api/parse-document", response_model=IngestResponse)
async def parse_uploaded_document(
    background_tasks: BackgroundTasks,
    company_id: str = Form(...),
    files: list[UploadFile] = File(...),
) -> IngestResponse:
    """Accept document uploads and run the ingestion pipeline in the background.

    Returns a case_id immediately. Poll GET /api/case/{case_id} for results.
    """
    for f in files:
        if f.content_type not in ALLOWED_UPLOAD_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {f.filename} ({f.content_type})",
            )

    case_id = get_or_create_case(company_id)

    # Read file bytes eagerly (stream closes after request ends)
    payloads = []
    for f in files:
        raw = await f.read()
        payloads.append({
            "filename": f.filename,
            "content_type": f.content_type,
            "bytes": raw,
        })

    background_tasks.add_task(run_pipeline, case_id, company_id, payloads)

    return IngestResponse(
        case_id=case_id,
        company_id=company_id,
        status="processing",
        files_received=len(payloads),
        message=f"{len(payloads)} file(s) queued for processing.",
    )


@app.get("/api/companies", response_model=List[CompanyCaseSummary])
def get_companies() -> List[CompanyCaseSummary]:
    """List all companies with their associated case ID, status, and ingested doc types."""
    rows = list_companies_with_cases()
    return [CompanyCaseSummary(**r) for r in rows]




@app.get("/api/case/{case_id}/documents", response_model=List[DocumentSummary])
def get_case_documents(
    case_id: str,
    doc_types: Optional[str] = None,
) -> List[DocumentSummary]:
    """List documents in a case. Optionally filter by doc_types (comma-separated).

    Example: /api/case/{id}/documents?doc_types=bank_statement,salary_slip
    """
    type_filter = [t.strip() for t in doc_types.split(",")] if doc_types else None
    docs = get_documents_by_case(case_id, type_filter)
    return [DocumentSummary(**d) for d in docs]


@app.get("/api/schemas")
def get_schemas() -> list[dict]:
    """List all registered document schemas."""
    return list_schemas()


@app.post("/api/underwrite", response_model=UnderwritingResponse)
def underwrite(request: AnalyzeRequest) -> UnderwritingResponse:
    """Run the full underwriting flow and return structured results."""
    try:
        data_dict = request.data.model_dump()
        if USE_LANGGRAPH and run_langgraph_flow is not None:
            # Keep API response stable by auto-resuming HITL when no explicit input is supplied.
            lg_result = run_langgraph_flow(
                data=data_dict,
                region=request.region,
                human_input=request.human_response or None,
                thread_id=request.thread_id,
                auto_resume=True,
            )
            state = lg_result["state"]
        else:
            state = run_underwriting_flow(
                data=data_dict,
                region=request.region,
                interactive=False,
                human_response=request.human_response or "",
            )
        return _build_underwriting_response(state, data_dict, request.region)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/underwrite/stream")
def underwrite_stream(request: AnalyzeRequest) -> StreamingResponse:
    """
    Run underwriting flow while streaming LangGraph-style progress as NDJSON.

    Each line is one JSON object. Progress lines have ``type: "progress"``.
    The final line has ``type: "result"`` and includes the full underwriting payload.
    """
    data_dict = request.data.model_dump()
    region = request.region
    human_response = request.human_response or ""

    def event_generator():
        final_state: Dict[str, Any] | None = None
        try:
            event_iter = (
                iter_langgraph_flow_events(
                    data_dict,
                    region,
                    human_input=human_response or None,
                    thread_id=request.thread_id,
                    auto_resume=True,
                )
                if USE_LANGGRAPH and iter_langgraph_flow_events is not None
                else iter_underwriting_flow_events(
                    data_dict,
                    region,
                    interactive=False,
                    human_response=human_response,
                )
            )
            logger.info(
                "underwrite_stream_path mode=%s thread_id=%s",
                "langgraph" if USE_LANGGRAPH and iter_langgraph_flow_events is not None else "legacy",
                request.thread_id,
            )
            for event in event_iter:
                if event.get("type") == "complete":
                    final_state = event.get("state")
                    continue
                yield json.dumps(event, ensure_ascii=False) + "\n"
            if final_state is None:
                err = {"type": "error", "message": "Flow completed without final state"}
                yield json.dumps(err, ensure_ascii=False) + "\n"
                return
            response = _build_underwriting_response(final_state, data_dict, region)
            yield json.dumps(
                {"type": "result", "payload": json.loads(response.model_dump_json())},
                ensure_ascii=False,
            ) + "\n"
        except Exception as exc:
            yield json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n"

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/underwrite/langgraph/start", response_model=LangGraphFlowResponse)
def underwrite_langgraph_start(request: AnalyzeRequest) -> LangGraphFlowResponse:
    """Start a LangGraph underwriting thread and pause on HITL if needed."""
    if not USE_LANGGRAPH or run_langgraph_flow is None:
        logger.warning(
            "langgraph_start_fallback_to_legacy USE_LANGGRAPH=%s import_error=%s",
            USE_LANGGRAPH,
            LANGGRAPH_IMPORT_ERROR or "none",
        )
        data_dict = request.data.model_dump()
        state = run_underwriting_flow(
            data=data_dict,
            region=request.region,
            interactive=False,
            human_response=request.human_response or "",
        )
        result = _build_underwriting_response(state, data_dict, request.region)
        return LangGraphFlowResponse(
            status="COMPLETED",
            thread_id=request.thread_id or "legacy-fallback",
            active_index=6,
            label="Completed via legacy flow fallback",
            logs=state.get("agent_logs", []),
            decision=str(state.get("decision_status", "PENDING")),
            hitl_context=state.get("hitl_context"),
            result=result,
        )

    data_dict = request.data.model_dump()
    logger.info("langgraph_start_received region=%s thread_id=%s", request.region, request.thread_id)
    try:
        payload = run_langgraph_flow(
            data=data_dict,
            region=request.region,
            human_input=None,
            thread_id=request.thread_id,
            auto_resume=False,
        )
        state = payload["state"]
        logger.info(
            "langgraph_start_executed status=%s thread_id=%s decision=%s",
            payload["status"],
            payload["thread_id"],
            state.get("decision_status"),
        )
        result: Optional[UnderwritingResponse] = None
        if payload["status"] == "COMPLETED":
            result = _build_underwriting_response(state, data_dict, request.region)
        return LangGraphFlowResponse(
            status=payload["status"],
            thread_id=payload["thread_id"],
            active_index=int(payload.get("active_index", 3)),
            label=str(payload.get("label", "LangGraph execution")),
            logs=list(payload.get("logs", [])),
            decision=str(payload.get("decision", "PENDING")),
            hitl_context=state.get("hitl_context"),
            result=result,
        )
    except Exception as exc:
        logger.exception("langgraph_start_failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/underwrite/langgraph/resume", response_model=LangGraphFlowResponse)
def underwrite_langgraph_resume(request: AnalyzeRequest) -> LangGraphFlowResponse:
    """Resume a paused LangGraph underwriting thread with human clarification."""
    if not USE_LANGGRAPH or run_langgraph_flow is None:
        logger.warning(
            "langgraph_resume_fallback_to_legacy USE_LANGGRAPH=%s import_error=%s",
            USE_LANGGRAPH,
            LANGGRAPH_IMPORT_ERROR or "none",
        )
        data_dict = request.data.model_dump()
        state = run_underwriting_flow(
            data=data_dict,
            region=request.region,
            interactive=False,
            human_response=request.human_response or "",
        )
        result = _build_underwriting_response(state, data_dict, request.region)
        return LangGraphFlowResponse(
            status="COMPLETED",
            thread_id=request.thread_id or "legacy-fallback",
            active_index=6,
            label="Completed via legacy flow fallback",
            logs=state.get("agent_logs", []),
            decision=str(state.get("decision_status", "PENDING")),
            hitl_context=state.get("hitl_context"),
            result=result,
        )
    if not request.thread_id:
        raise HTTPException(status_code=400, detail="thread_id is required for LangGraph resume")

    data_dict = request.data.model_dump()
    clarification = (request.human_response or "").strip()
    if not clarification:
        raise HTTPException(status_code=400, detail="human_response is required for LangGraph resume")
    logger.info("langgraph_resume_received thread_id=%s", request.thread_id)
    try:
        payload = run_langgraph_flow(
            data=data_dict,
            region=request.region,
            human_input=clarification,
            thread_id=request.thread_id,
            auto_resume=False,
        )
        state = payload["state"]
        logger.info(
            "langgraph_resume_executed status=%s thread_id=%s decision=%s",
            payload["status"],
            payload["thread_id"],
            state.get("decision_status"),
        )
        result: Optional[UnderwritingResponse] = None
        if payload["status"] == "COMPLETED":
            result = _build_underwriting_response(state, data_dict, request.region)
        return LangGraphFlowResponse(
            status=payload["status"],
            thread_id=payload["thread_id"],
            active_index=int(payload.get("active_index", 3)),
            label=str(payload.get("label", "LangGraph execution")),
            logs=list(payload.get("logs", [])),
            decision=str(payload.get("decision", "PENDING")),
            hitl_context=state.get("hitl_context"),
            result=result,
        )
    except Exception as exc:
        logger.exception("langgraph_resume_failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8010"))
    uvicorn.run("api_server:app", host="0.0.0.0", port=port, reload=True)
