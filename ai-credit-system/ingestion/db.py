"""Supabase connection layer for the ingestion pipeline."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

_client: Client | None = None


def get_client() -> Client:
    """Get or create the Supabase client (singleton)."""
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env")
        _client = create_client(url, key)
    return _client


def fetch_schema(document_type: str) -> dict | None:
    """Fetch the output_format JSON Schema for a given document type."""
    client = get_client()
    result = (
        client.table("document_schemas")
        .select("output_format")
        .eq("document_type", document_type)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]["output_format"]
    return None


def get_or_create_case(company_id: str) -> str:
    """Get existing case for company or create a new one. Returns case ID."""
    client = get_client()
    result = (
        client.table("cases")
        .select("id")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    if result.data:
        return str(result.data[0]["id"])

    new = (
        client.table("cases")
        .insert({"company_id": company_id})
        .execute()
    )
    return str(new.data[0]["id"])


def update_case_status(case_id: str, status: str) -> None:
    """Update the status field on a case."""
    client = get_client()
    client.table("cases").update({"status": status, "updated_at": "now()"}).eq("id", case_id).execute()


def get_case(case_id: str) -> dict | None:
    """Fetch a case by ID."""
    client = get_client()
    result = (
        client.table("cases")
        .select("id, company_id, status")
        .eq("id", case_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    row = result.data[0]
    return {
        "id": str(row["id"]),
        "company_id": str(row["company_id"]),
        "status": row["status"],
    }


def get_company_case(company_id: str) -> dict | None:
    """Fetch a case by company ID."""
    client = get_client()
    result = (
        client.table("cases")
        .select("id, company_id, status")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    row = result.data[0]
    return {
        "id": str(row["id"]),
        "company_id": str(row["company_id"]),
        "status": row["status"],
    }


def create_document(case_id: str, document_name: str, metadata: dict) -> str:
    """Insert a new document row and return its UUID."""
    client = get_client()
    result = (
        client.table("documents")
        .insert({
            "case_id": case_id,
            "document_name": document_name,
            "metadata": metadata,
            "status": "pending",
        })
        .execute()
    )
    return str(result.data[0]["id"])


def update_document(
    document_id: str,
    *,
    doc_type: str | None = None,
    extracted_data: dict | None = None,
    status: str | None = None,
) -> None:
    """Partial update on a document row."""
    client = get_client()
    payload: dict = {"updated_at": "now()"}
    if doc_type is not None:
        payload["doc_type"] = doc_type
    if extracted_data is not None:
        payload["extracted_data"] = extracted_data
    if status is not None:
        payload["status"] = status
    client.table("documents").update(payload).eq("id", document_id).execute()


def get_documents_by_case(
    case_id: str, doc_types: list[str] | None = None
) -> list[dict]:
    """Return documents for a case, optionally filtered to specific doc_types."""
    client = get_client()
    query = (
        client.table("documents")
        .select("id, document_name, doc_type, metadata, extracted_data, status, created_at")
        .eq("case_id", case_id)
    )
    if doc_types:
        query = query.in_("doc_type", doc_types)
    result = query.execute()
    return [
        {
            "document_id": str(r["id"]),
            "document_name": r["document_name"],
            "doc_type": r["doc_type"],
            "metadata": r["metadata"] or {},
            "extracted_data": r["extracted_data"] or {},
            "status": r["status"],
            "created_at": r["created_at"],
        }
        for r in (result.data or [])
    ]


def list_schemas() -> list[dict]:
    """List all registered document schemas."""
    client = get_client()
    result = client.table("document_schemas").select("document_type, output_format").execute()
    return [
        {"document_type": r["document_type"], "output_format": r["output_format"]}
        for r in result.data
    ]


def list_companies_with_cases() -> list[dict]:
    """Return all companies paired with their case summary and doc_types from documents table."""
    client = get_client()
    companies = client.table("companies").select("id, name").execute().data or []
    cases = client.table("cases").select("id, company_id, status").execute().data or []

    # Derive doc_types per case from the documents table
    docs = client.table("documents").select("case_id, doc_type").execute().data or []
    doc_types_by_case: dict[str, set] = {}
    for d in docs:
        cid = str(d["case_id"])
        if d["doc_type"]:
            doc_types_by_case.setdefault(cid, set()).add(d["doc_type"])

    cases_by_company = {str(c["company_id"]): c for c in cases}

    result = []
    for company in companies:
        cid = str(company["id"])
        case = cases_by_company.get(cid)
        case_id = str(case["id"]) if case else None
        result.append({
            "company_id": cid,
            "company_name": company["name"],
            "case_id": case_id,
            "case_status": case["status"] if case else None,
            "doc_types": sorted(doc_types_by_case.get(case_id, set())) if case_id else [],
        })
    return result
