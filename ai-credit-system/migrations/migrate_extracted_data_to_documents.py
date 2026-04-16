"""One-time migration: split cases.extracted_data array entries into documents table rows.

Run from ai-credit-system/:
    python -m migrations.migrate_extracted_data_to_documents
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv()

from ingestion.db import get_client


def migrate() -> None:
    client = get_client()

    cases = client.table("cases").select("id, extracted_data").execute().data or []
    print(f"Found {len(cases)} case(s) to migrate.")

    total_created = 0

    for case in cases:
        case_id = str(case["id"])
        extracted_data: dict = case.get("extracted_data") or {}

        for doc_type, docs in extracted_data.items():
            # Normalise to list (handles legacy single-dict format)
            if isinstance(docs, dict):
                docs = [docs]
            if not isinstance(docs, list):
                continue

            print(f"  case={case_id}  doc_type={doc_type}  entries={len(docs)}")

            for i, doc_data in enumerate(docs):
                result = (
                    client.table("documents")
                    .insert({
                        "case_id": case_id,
                        "document_name": f"{doc_type}_{i + 1}",
                        "doc_type": doc_type,
                        "extracted_data": doc_data,
                        "metadata": {},
                        "status": "done",
                    })
                    .execute()
                )
                doc_id = result.data[0]["id"]
                print(f"    Created document {doc_id}  ({doc_type} #{i + 1})")
                total_created += 1

    print(f"\nDone. Created {total_created} document row(s).")


if __name__ == "__main__":
    migrate()
