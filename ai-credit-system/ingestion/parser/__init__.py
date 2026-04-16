"""Legacy mock parser — re-exported here so existing imports still resolve
after ingestion/parser.py was replaced by the ingestion/parser/ package.
"""

from __future__ import annotations

from typing import Any, Dict, List


def parse_document(file_path: str) -> Dict[str, Any]:
    transactions: List[Dict[str, Any]] = [
        {"date": "2026-04-01", "description": "Client Payment A", "amount": 120000, "type": "credit"},
        {"date": "2026-04-03", "description": "Office Rent", "amount": 25000, "type": "debit"},
        {"date": "2026-04-04", "description": "Client Payment B", "amount": 80000, "type": "credit"},
        {"date": "2026-04-05", "description": "Vendor Settlement", "amount": 42000, "type": "debit"},
    ]
    total_inflow = sum(t["amount"] for t in transactions if t["type"] == "credit")
    total_outflow = sum(t["amount"] for t in transactions if t["type"] == "debit")
    return {
        "source_file": file_path,
        "transactions": transactions,
        "total_inflow": total_inflow,
        "total_outflow": total_outflow,
    }
