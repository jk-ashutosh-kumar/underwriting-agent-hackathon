"""Recursive merger for credcheck_report documents.

Why a separate merger?
----------------------
The standard deep_merge in merger.py is intentionally shallow:
  - nested dicts  → first-truthy object wins  (later-page data is dropped)
  - lists         → simple concatenation       (no deduplication)
  - scalars       → first-truthy wins          (`0` / `False` can be overwritten)

For a credcheck report each page delivers only a slice of the full schema,
so we need:

  1. **Recursive dict merge** — nested objects (`business_summary`,
     `tax_filing`, `legal_profile.*`, and year-keyed `balance_sheet` /
     `profit_loss` blocks) are merged field-by-field across pages.

  2. **delay_records deduplication** — the `gstr3b_filing_delay.delay_records`
     array is keyed by month.  The same month can appear on multiple pages
     (page contains the table header + first rows, next page continues).
     We merge records by month; within a month we use first-non-null per
     field so a partial record on page N doesn't overwrite a richer one
     from page N+1.

  3. **Scalar first-non-null wins** — we check `existing is None` (not
     truthiness) so that valid falsy values like `0` (zero legal cases,
     zero delay days) and `False` (`has_delay: false`) are never silently
     overwritten by a later page's null.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Delay-records deduplication
# ---------------------------------------------------------------------------

def _merge_delay_records(
    base: list[dict], incoming: list[dict]
) -> list[dict]:
    """Merge two lists of delay records, deduplicating on the ``month`` key.

    Within the same month, fields are merged with first-non-null wins so that
    a partial record from one page is combined with a partial record from
    another rather than one silently dropping the other.

    Records that lack a ``month`` key cannot be deduplicated; they are
    appended as-is (rare, but guards against malformed LLM output).
    """
    by_month: dict[str, dict] = {}
    unkeyed: list[dict] = []

    for record in base + incoming:
        if not isinstance(record, dict):
            continue
        month = record.get("month")
        if month is None:
            unkeyed.append(record)
        elif month not in by_month:
            by_month[month] = dict(record)
        else:
            # Same month seen again — merge field-by-field, first-non-null wins
            existing = by_month[month]
            for field, val in record.items():
                if existing.get(field) is None and val is not None:
                    existing[field] = val

    return list(by_month.values()) + unkeyed


# ---------------------------------------------------------------------------
# Recursive merge
# ---------------------------------------------------------------------------

def _recursive_merge(base: dict, incoming: dict) -> None:
    """Merge *incoming* into *base* in-place, recursively."""
    for key, value in incoming.items():

        # Key never seen before → store as-is (even if null — lets later pages fill it)
        if key not in base:
            base[key] = value
            continue

        existing = base[key]

        # ── dict + dict → recurse ─────────────────────────────────────────
        # Handles all nested objects AND year-keyed additionalProperties
        # blocks (balance_sheet / profit_loss).
        if isinstance(existing, dict) and isinstance(value, dict):
            _recursive_merge(existing, value)

        # ── list + list → merge with deduplication ────────────────────────
        elif isinstance(existing, list) and isinstance(value, list):
            if key == "delay_records":
                base[key] = _merge_delay_records(existing, value)
            else:
                # Other arrays (none currently in schema, but future-safe)
                base[key] = existing + value

        # ── scalar: base is null, incoming has a real value → take it ─────
        # Intentionally uses ``is None`` and not ``not existing`` so that
        # valid falsy scalars (0, False, "") are never overwritten.
        elif existing is None and value is not None:
            base[key] = value

        # ── scalar: base already has a non-null value → keep it ───────────
        # (first-non-null wins; no action needed)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def merge_credcheck_pages(pages: list[dict]) -> dict:
    """Recursively merge per-page credcheck_report extractions into one dict.

    *pages* is the list of JSON objects returned by the extractor — one per
    document page.  Each may be sparse; together they should cover the full
    credcheck_report schema.

    Returns a single merged dict ready for persistence.
    """
    result: dict = {}
    for page in pages:
        if not isinstance(page, dict):
            continue
        _recursive_merge(result, page)
    return result
