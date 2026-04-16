"""Supabase connection layer for the ingestion pipeline."""

from __future__ import annotations

import json
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


def merge_doc_output(case_id: str, doc_type: str, data: dict) -> None:
    """Append extracted document data to the case's extracted_data JSONB field.

    Each doc_type key holds a list so multiple uploads of the same type are preserved.
    """
    client = get_client()
    result = (
        client.table("cases")
        .select("extracted_data, doc_types")
        .eq("id", case_id)
        .limit(1)
        .execute()
    )
    row = result.data[0] if result.data else {}
    current = row.get("extracted_data") or {}

    existing = current.get(doc_type)
    if existing is None:
        current[doc_type] = [data]
    elif isinstance(existing, list):
        current[doc_type] = existing + [data]
    else:
        # Migrate legacy single-dict format to list
        current[doc_type] = [existing, data]

    doc_types = row.get("doc_types") or []
    if doc_type not in doc_types:
        doc_types = doc_types + [doc_type]

    client.table("cases").update({
        "extracted_data": current,
        "doc_types": doc_types,
        "updated_at": "now()",
    }).eq("id", case_id).execute()


def get_case(case_id: str) -> dict | None:
    """Fetch a case by ID."""
    client = get_client()
    result = (
        client.table("cases")
        .select("*")
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
        "doc_types": row.get("doc_types") or [],
        "extracted_data": row["extracted_data"] or {},
    }


def get_company_case(company_id: str) -> dict | None:
    """Fetch a case by company ID."""
    client = get_client()
    result = (
        client.table("cases")
        .select("*")
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
        "doc_types": row.get("doc_types") or [],
        "extracted_data": row["extracted_data"] or {},
    }


def list_schemas() -> list[dict]:
    """List all registered document schemas."""
    client = get_client()
    result = client.table("document_schemas").select("document_type, output_format").execute()
    return [
        {"document_type": r["document_type"], "output_format": r["output_format"]}
        for r in result.data
    ]


def list_companies_with_cases() -> list[dict]:
    """Return all companies paired with their case summary (if any)."""
    client = get_client()
    companies = client.table("companies").select("id, name").execute().data or []
    cases = client.table("cases").select("id, company_id, status, doc_types").execute().data or []

    cases_by_company = {str(c["company_id"]): c for c in cases}

    result = []
    for company in companies:
        cid = str(company["id"])
        case = cases_by_company.get(cid)
        result.append({
            "company_id": cid,
            "company_name": company["name"],
            "case_id": str(case["id"]) if case else None,
            "case_status": case["status"] if case else None,
            "doc_types": (case.get("doc_types") or []) if case else [],
        })
    return result


def get_case_documents_by_type(case_id: str, doc_type: str) -> list[dict]:
    """Return the list of extracted documents for a given doc_type within a case."""
    client = get_client()
    result = (
        client.table("cases")
        .select("extracted_data")
        .eq("id", case_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return []
    extracted = result.data[0].get("extracted_data") or {}
    docs = extracted.get(doc_type, [])
    # Handle legacy single-dict format
    if isinstance(docs, dict):
        return [docs]
    return docs
