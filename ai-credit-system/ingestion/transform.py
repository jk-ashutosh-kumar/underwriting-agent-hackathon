"""Transform extracted document data into the FinancialData shape for underwriting."""

from __future__ import annotations

from typing import Any, Dict


def to_financial_data(merged_data: dict, doc_type: str) -> Dict[str, Any]:
    """Map ingestion output to the {transactions, total_inflow, total_outflow} shape
    expected by the existing underwriting pipeline."""

    if doc_type == "bank_statement":
        raw_txns = merged_data.get("transactions", [])
        transactions = []
        total_inflow = 0.0
        total_outflow = 0.0

        for t in raw_txns:
            credit = t.get("credit") or 0
            debit = t.get("debit") or 0
            amount = credit if credit else debit
            txn_type = "credit" if credit else "debit"

            transactions.append({
                "date": t.get("date", ""),
                "description": t.get("description", ""),
                "amount": amount,
                "type": txn_type,
            })

            if txn_type == "credit":
                total_inflow += amount
            else:
                total_outflow += amount

        return {
            "source_file": "ingestion_pipeline",
            "transactions": transactions,
            "total_inflow": total_inflow,
            "total_outflow": total_outflow,
        }

    if doc_type == "salary_slip":
        return {
            "source_file": "ingestion_pipeline",
            "transactions": [
                {
                    "date": merged_data.get("month", ""),
                    "description": f"Salary - {merged_data.get('company_name', '')}",
                    "amount": merged_data.get("net_salary", 0),
                    "type": "credit",
                }
            ],
            "total_inflow": merged_data.get("net_salary", 0),
            "total_outflow": 0,
        }

    # Fallback: return raw data wrapped in a minimal structure
    return {
        "source_file": "ingestion_pipeline",
        "transactions": [],
        "total_inflow": 0,
        "total_outflow": 0,
        "raw_extracted": merged_data,
    }
