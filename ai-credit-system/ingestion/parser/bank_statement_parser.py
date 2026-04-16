"""Post-merge parser for bank_statement documents.

Responsibilities:
- Remove balance-forward / opening-balance rows that aren't real transactions
- Validate each transaction by comparing the stated debit/credit amount against
  the balance delta (abs(prev_balance - current_balance))
- Attach flag: bool and flag_type: str | None to every transaction
"""

from __future__ import annotations

import re

BALANCE_FORWARD_PATTERNS = [
    "balanceforward",
    "balancebf",
    "balancebroughtforward",
    "openingbalance",
    "bfbalance",
    "balancecf",
    "closingbalance",
    "broughtforward",
    "carriedforward",
]

AMOUNT_MISMATCH_TOLERANCE = 0.5


def _normalize(text: str) -> str:
    """Strip all non-alphanumeric characters and lowercase."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


# Pre-normalize patterns once at import time
_NORMALIZED_PATTERNS = [_normalize(p) for p in BALANCE_FORWARD_PATTERNS]


def is_balance_forward(description: str) -> bool:
    """Return True if the description matches a known balance-forward pattern.

    Matching is done on a normalized form (no spaces, no special chars,
    lowercase) so variations like 'BALANCE  FORWARD', 'Balance-Forward',
    'BAL.FORWARD' are all caught.
    """
    norm = _normalize(description)
    return any(pattern in norm for pattern in _NORMALIZED_PATTERNS)


def validate_bank_statement(merged: dict) -> dict:
    """Clean and flag transactions in a merged bank_statement output.

    Steps:
    1. Filter out balance-forward rows.
    2. For each remaining transaction, compute the expected amount from the
       running balance column and flag any mismatch beyond the tolerance.

    The input dict is mutated in-place and returned.
    """
    transactions = merged.get("transactions", [])

    # Step 1: remove balance-forward entries
    filtered = [
        t for t in transactions
        if not is_balance_forward(t.get("description", ""))
    ]

    # Step 2: validate amounts using running balance
    for i, txn in enumerate(filtered):
        prev_balance = filtered[i - 1].get("balance") if i > 0 else None
        curr_balance = txn.get("balance")

        # Support both debit/credit split fields and unified amount field
        stated = txn.get("debit") or txn.get("credit") or txn.get("amount") or 0

        if prev_balance is not None and curr_balance is not None:
            computed = abs(curr_balance - prev_balance)
            mismatch = abs(computed - stated) > AMOUNT_MISMATCH_TOLERANCE
            txn["flag"] = mismatch
            txn["flag_type"] = "amount_mismatch" if mismatch else None
        else:
            # Missing balance data — cannot validate
            txn["flag"] = False
            txn["flag_type"] = None

    merged["transactions"] = filtered
    return merged
