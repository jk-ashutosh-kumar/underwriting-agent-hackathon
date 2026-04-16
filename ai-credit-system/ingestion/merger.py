"""Merger node: merge per-page extractions and persist to Supabase."""

from __future__ import annotations

from ingestion.db import merge_doc_output
from ingestion.state import DocumentState


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
        merged = deep_merge(state["page_outputs"])

        merge_doc_output(
            state["case_id"],
            state["document_type"],
            merged,
        )

        return {
            **state,
            "merged_output": merged,
            "status": "done",
        }

    except Exception as e:
        return {
            **state,
            "status": "failed",
            "error": f"Merger error: {str(e)}",
        }
