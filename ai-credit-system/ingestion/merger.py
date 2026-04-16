"""Merger node: merge per-page extractions and persist to Supabase."""

from __future__ import annotations

from ingestion.db import update_document
from ingestion.parser.bank_statement_parser import validate_bank_statement
from ingestion.parser.credcheck_report_parser import merge_credcheck_pages
from ingestion.state import DocumentState
from webhooks import fire_extraction_completed


def deep_merge(pages: list[dict]) -> dict:
    """Merge strategy: arrays concatenated, scalars first-truthy wins.

    'First truthy' (not just non-None) ensures that an empty string returned
    by the LLM on one page doesn't block a real value found on another page.
    """
    merged: dict = {}
    for page in pages:
        for key, value in page.items():
            if key not in merged:
                merged[key] = value
            else:
                existing = merged[key]
                if isinstance(existing, list) and isinstance(value, list):
                    merged[key] = existing + value
                elif not existing and value:
                    merged[key] = value
    return merged


async def merge_node(state: DocumentState) -> DocumentState:
    if state["status"] == "failed":
        return state

    try:
        doc_type = state["document_type"]

        if doc_type == "credcheck_report":
            merged = merge_credcheck_pages(state["page_outputs"])
        else:
            merged = deep_merge(state["page_outputs"])

        if doc_type == "bank_statement":
            merged = validate_bank_statement(merged)

        update_document(
            state["document_id"],
            extracted_data=merged,
            status="done",
        )

        await fire_extraction_completed(state["case_id"], state["document_id"])

        return {
            **state,
            "merged_output": merged,
            "status": "done",
        }

    except Exception as e:
        update_document(state["document_id"], status="failed")
        return {
            **state,
            "status": "failed",
            "error": f"Merger error: {str(e)}",
        }
