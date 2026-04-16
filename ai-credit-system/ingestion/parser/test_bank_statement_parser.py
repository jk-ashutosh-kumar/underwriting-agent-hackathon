"""Test bank_statement_parser on a real JSON input.

Run from ai-credit-system/:
    python -m ingestion.parser.test_bank_statement_parser
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ingestion.parser.bank_statement_parser import validate_bank_statement

INPUT_PATH = Path(__file__).parent.parent / "test.json"


def main() -> None:
    with open(INPUT_PATH) as f:
        merged = json.load(f)

    original_count = len(merged["transactions"])
    result = validate_bank_statement(merged)
    transactions = result["transactions"]

    print(f"Original rows : {original_count}")
    print(f"After filter  : {len(transactions)}  (removed {original_count - len(transactions)} balance-forward rows)")

    flagged = [t for t in transactions if t.get("flag")]
    print(f"Flagged rows  : {len(flagged)}\n")

    print(f"{'DATE':<14} {'AMOUNT':>10} {'TYPE':<8} {'BALANCE':>12} {'FLAG':<6} {'FLAG_TYPE'}")
    print("-" * 75)
    for t in transactions:
        print(
            f"{t.get('date', ''):<14} "
            f"{str(t.get('amount') or t.get('debit') or t.get('credit') or ''):>10} "
            f"{str(t.get('transaction_type') or ''):<8} "
            f"{t.get('balance', ''):>12} "
            f"{'TRUE' if t.get('flag') else 'false':<6} "
            f"{t.get('flag_type') or ''}"
        )

    if flagged:
        print("\n--- Flagged details ---")
        for t in flagged:
            print(f"  {t['date']} | {t['description'][:50]}")
            print(f"    stated={t.get('amount') or t.get('debit') or t.get('credit')}  balance={t.get('balance')}")


if __name__ == "__main__":
    main()
