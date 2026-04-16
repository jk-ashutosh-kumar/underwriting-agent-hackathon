"""Pydantic request/response models for ingestion endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class IngestResponse(BaseModel):
    case_id: str
    company_id: str
    status: str
    files_received: int
    message: str


class CompanyCaseSummary(BaseModel):
    company_id: str
    company_name: str
    case_id: Optional[str]
    case_status: Optional[str]
    doc_types: List[str]


class CaseDocumentsResponse(BaseModel):
    case_id: str
    doc_type: str
    count: int
    documents: List[Dict[str, Any]]
