"""DocumentState: shared state for the ingestion LangGraph pipeline."""

from __future__ import annotations

from typing import Optional, TypedDict


class DocumentState(TypedDict):
    # Input
    case_id: str
    company_id: str
    filename: str
    content_type: str
    file_bytes: bytes

    # Set by classifier
    document_type: Optional[str]
    schema: Optional[dict]

    # Set by extractor
    page_outputs: Optional[list[dict]]

    # Set by merger
    merged_output: Optional[dict]

    # Control flow
    status: str  # classifying | extracting | merging | done | failed
    error: Optional[str]
