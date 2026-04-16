"""LangGraph orchestrator: classify -> extract -> merge pipeline."""

from __future__ import annotations

import asyncio

from langgraph.graph import END, StateGraph

from ingestion.classifier import classify_node
from ingestion.db import create_document, update_case_status
from ingestion.extractor import extract_node
from ingestion.merger import merge_node
from ingestion.state import DocumentState


# -- Conditional routing --------------------------------------------------

def route_after_classify(state: DocumentState) -> str:
    return "extract" if state["status"] == "extracting" else END


def route_after_extract(state: DocumentState) -> str:
    return "merge" if state["status"] == "merging" else END


# -- Build the graph ------------------------------------------------------

builder = StateGraph(DocumentState)
builder.add_node("classify", classify_node)
builder.add_node("extract", extract_node)
builder.add_node("merge", merge_node)

builder.set_entry_point("classify")
builder.add_conditional_edges(
    "classify",
    route_after_classify,
    {"extract": "extract", END: END},
)
builder.add_conditional_edges(
    "extract",
    route_after_extract,
    {"merge": "merge", END: END},
)
builder.add_edge("merge", END)

graph = builder.compile()


# -- Per-document runner --------------------------------------------------

async def process_document(
    case_id: str, company_id: str, payload: dict
) -> DocumentState:
    document_id = create_document(
        case_id=case_id,
        document_name=payload["filename"],
        metadata={"content_type": payload["content_type"]},
    )

    initial_state = DocumentState(
        case_id=case_id,
        company_id=company_id,
        document_id=document_id,
        filename=payload["filename"],
        content_type=payload["content_type"],
        file_bytes=payload["bytes"],
        document_type=None,
        schema=None,
        page_outputs=None,
        merged_output=None,
        status="classifying",
        error=None,
    )

    print(f"[Pipeline] Starting: {payload['filename']}")
    final_state = await graph.ainvoke(initial_state)
    print(
        f"[Pipeline] Done: {payload['filename']} -> status={final_state['status']}"
    )
    return final_state


# -- Top-level case runner ------------------------------------------------

async def run_pipeline(
    case_id: str, company_id: str, payloads: list[dict]
) -> None:
    """Run ingestion for all uploaded documents concurrently."""
    update_case_status(case_id, "processing")

    try:
        tasks = [
            process_document(case_id, company_id, p) for p in payloads
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        any_failed = any(
            isinstance(r, Exception) or r.get("status") == "failed"
            for r in results
        )
        final_status = "failed" if any_failed else "done"
        update_case_status(case_id, final_status)

    except Exception as e:
        update_case_status(case_id, "failed")
        print(f"[Pipeline] Fatal error: {e}")
