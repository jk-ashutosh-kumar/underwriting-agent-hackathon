"""Credit limit recommendation agent."""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Tuple

# If any auditor flag text matches, we do not assign an annual limit (treat as elevated concern).
_BLOCKING_FLAG_KEYWORDS: Tuple[str, ...] = (
    "fraud",
    "suspicious",
    "fake",
    "illegal",
    "laundering",
    "mismatch",
    "round-trip",
    "round trip",
    "aml",
    "default",
    "uncollect",
)


def _combined_flags_contain_keyword(combined: str, kw: str) -> bool:
    """Whole-token match so e.g. 'default' does not match inside 'defaults'."""
    return bool(
        re.search(rf"(?<![A-Za-z0-9_]){re.escape(kw)}(?![A-Za-z0-9_])", combined, flags=re.IGNORECASE)
    )


def _fmt_plain_amount(value: float) -> str:
    """Plain number string (no grouping); matches UI ``formatPlainAmount`` style."""
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "0"
    n = float(value)
    if abs(n - round(n)) < 1e-9:
        return str(int(round(n)))
    text = f"{n:.2f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _truncate_words(text: str, max_len: int) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _coherent_credit_limit_reasoning(
    *,
    economics_base: float,
    nominal_min: float,
    nominal_max: float,
    final_min: float,
    final_max: float,
    decision_status: str,
    anchor_note: Optional[str],
    hitl_reject: bool,
    flag_count: int,
    flag_preview: str,
    blocked_policy: bool,
    risk: int,
    review_rec: bool,
    weak_trend: bool,
) -> str:
    """Two to four short sentences; numbers match ``final_min`` / ``final_max`` and nominal fields."""
    eb = _fmt_plain_amount(economics_base)
    nmin = _fmt_plain_amount(nominal_min)
    nmax = _fmt_plain_amount(nominal_max)
    fmin = _fmt_plain_amount(final_min)
    fmax = _fmt_plain_amount(final_max)
    ds = str(decision_status or "").strip().upper()

    if final_max <= 0 and final_min <= 0:
        return (
            "There was not enough invoice or bank history to anchor a positive range, "
            "so the annual band stays at 0 to 0."
        )

    if economics_base > 0:
        s1 = (
            f"The economics base anchor is {eb} (roughly one quarter of modeled annual flow). "
            f"Before final underwriting, the economics-only band ran from {nmin} up to {nmax}; "
            f"we treat {nmax} as the nominal ceiling from the model before policy haircuts."
        )
    else:
        s1 = (
            f"Invoice detail was thin, so the pre-policy economics band runs from {nmin} to {nmax}; "
            f"{nmax} is the nominal ceiling from that pass before final underwriting."
        )
    if anchor_note:
        s1 += f" {anchor_note}"

    s2 = (
        f"The quoted annual facility that matches the cards above is {fmin} to {fmax}. "
    )

    clauses: List[str] = []
    if ds == "REJECTED":
        clauses.append("the case was not approved, so the quote is a conservative reference only")
    elif ds and ds != "APPROVED":
        clauses.append(f"the status is {ds}, so we keep capacity cautious")
    if hitl_reject:
        clauses.append("HITL produced a reject-style override")
    if flag_count:
        pv = _truncate_words(flag_preview, 100) if flag_preview else ""
        clauses.append(
            f"the auditor raised {flag_count} issue(s)"
            + (f" (for example: {pv})" if pv else "")
        )
    if blocked_policy:
        clauses.append("language in the flags tripped an extra policy haircut")
    if risk >= 45:
        clauses.append(f"the audit risk score is {risk} out of 100 (lower is better)")
    if review_rec:
        clauses.append("the auditor asked for review rather than a clean approve")
    if weak_trend:
        clauses.append("cashflow looks weak or shrinking")

    if not clauses:
        s3 = "Final checks did not add heavy haircuts, so the quoted band stays near the economics envelope."
    else:
        joined = "; ".join(clauses)
        s3 = f"Compared with that nominal ceiling, the quoted band is tighter because {joined}."

    text = f"{s1} {s2}\n\n{s3}"
    return _truncate_words(text, 850)


def recommend_credit_limit_with_context(
    financial_profile: Dict[str, Any],
    audit_result: Dict[str, Any],
    trend_result: Dict[str, Any],
    *,
    decision_status: str,
    hitl_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Always produce an explainable annual band after final decision.

    Nominal economics come from ``recommend_credit_limit``; this layer applies
    haircuts for rejected cases, auditor flags, blocking terms, and risk so the
    range moves to the lower side. Rationale is kept short and always states the
    same min/max as returned (no stale nominal range from the base model).
    """
    base = recommend_credit_limit(financial_profile, audit_result, trend_result)
    nominal_min = float(base.get("min_limit", 0.0))
    nominal_max = float(base.get("max_limit", 0.0))
    anchor_note: Optional[str] = None

    if nominal_max <= 0 and nominal_min <= 0:
        bank = financial_profile.get("bank", {}) if isinstance(financial_profile, dict) else {}
        metrics = financial_profile.get("derived_metrics", {}) if isinstance(financial_profile, dict) else {}
        anchor = float(metrics.get("total_invoice_volume", 0.0) or 0.0) * 12
        if anchor <= 0:
            anchor = float(bank.get("total_inflow", 0.0) or 0.0) * 12
        if anchor > 0:
            nominal_min = round(anchor * 0.06, 2)
            nominal_max = round(anchor * 0.12, 2)
            anchor_note = "Thin invoice trail; anchor rebuilt from bank inflow."

    mid = (nominal_min + nominal_max) / 2.0
    half = (nominal_max - nominal_min) / 2.0 if nominal_max >= nominal_min else max(mid * 0.1, 1.0)
    conservatism = 1.0

    ds = str(decision_status or "").strip().upper()
    if ds == "REJECTED":
        conservatism *= 0.38
    elif ds and ds != "APPROVED":
        conservatism *= 0.55

    hitl_reject = hitl_override == "reject"
    if hitl_reject:
        conservatism *= 0.42

    flags = audit_result.get("flags") if isinstance(audit_result, dict) else []
    if not isinstance(flags, list):
        flags = [str(flags)] if flags else []
    flag_count = len(flags)
    flag_preview = str(flags[0]) if flags else ""
    if flags:
        conservatism *= max(0.5, 1.0 - 0.065 * min(flag_count, 8))

    blocked_policy, block_reason = (
        audit_blocks_credit_limit(audit_result) if isinstance(audit_result, dict) else (False, "")
    )
    if blocked_policy and block_reason:
        conservatism *= 0.52

    risk = int(audit_result.get("risk_score", 0) or 0) if isinstance(audit_result, dict) else 0
    if risk >= 45:
        factor = max(0.55, 1.0 - (risk - 45) / 130.0)
        conservatism *= factor

    rec = str(audit_result.get("recommendation", "")).lower().strip() if isinstance(audit_result, dict) else ""
    review_rec = rec == "review"
    if review_rec:
        conservatism *= 0.82

    growth = str(trend_result.get("growth_signal", trend_result.get("trend", ""))).lower() if isinstance(trend_result, dict) else ""
    weak_trend = "shrink" in growth
    if weak_trend:
        conservatism *= 0.88

    conservatism = max(0.14, min(1.0, conservatism))

    new_mid = mid * conservatism
    new_half = max(half * max(0.28, conservatism), new_mid * 0.08 if new_mid > 0 else 0.0)
    new_min = max(0.0, round(new_mid - new_half, 2))
    new_max = max(new_min, round(new_mid + new_half, 2))

    economics_base = float(base.get("economics_base_limit", 0.0) or 0.0)
    if new_max <= 0 and new_min <= 0:
        reasoning = (
            "Shown range is 0 to 0 — not enough invoice or bank signal to size a facility."
        )
    else:
        reasoning = _coherent_credit_limit_reasoning(
            economics_base=economics_base,
            nominal_min=nominal_min,
            nominal_max=nominal_max,
            final_min=new_min,
            final_max=new_max,
            decision_status=ds,
            anchor_note=anchor_note,
            hitl_reject=hitl_reject,
            flag_count=flag_count,
            flag_preview=flag_preview,
            blocked_policy=bool(blocked_policy and block_reason),
            risk=risk,
            review_rec=review_rec,
            weak_trend=weak_trend,
        )

    return {
        "min_limit": new_min,
        "max_limit": new_max,
        "economics_base_limit": round(economics_base, 2),
        "nominal_ceiling": round(nominal_max, 2),
        "nominal_floor": round(nominal_min, 2),
        "reasoning": reasoning,
    }


def recommend_credit_limit(
    financial_profile: Dict[str, Any],
    audit_result: Dict[str, Any],
    trend_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Recommend annual credit limit range with explainable adjustments."""
    metrics = financial_profile.get("derived_metrics", {})
    annual_invoice_volume = float(metrics.get("total_invoice_volume", 0.0)) * 12
    if annual_invoice_volume <= 0:
        annual_invoice_volume = float(financial_profile.get("bank", {}).get("total_inflow", 0.0)) * 12

    # Base: 25% of annual invoice volume.
    base_limit = annual_invoice_volume * 0.25
    risk_score = int(audit_result.get("risk_score", 50))
    growth_signal = str(trend_result.get("growth_signal", trend_result.get("trend", "stable"))).lower()
    gst_posture = str(metrics.get("gst_compliance", "unknown")).lower()

    adjustment = 1.0
    if risk_score >= 70:
        adjustment -= 0.35
    elif risk_score >= 50:
        adjustment -= 0.2
    elif risk_score <= 25:
        adjustment += 0.15

    if "growing" in growth_signal:
        adjustment += 0.15
    elif "shrinking" in growth_signal:
        adjustment -= 0.1

    if gst_posture in {"regular", "compliant", "good"}:
        adjustment += 0.05
    elif gst_posture in {"irregular", "delayed", "non-compliant", "non_compliant"}:
        adjustment -= 0.1

    adjustment = max(0.4, min(1.6, adjustment))
    recommended = base_limit * adjustment
    min_limit = max(0.0, recommended * 0.8)
    max_limit = max(min_limit, recommended * 1.2)

    reasoning = (
        f"Based on annual invoice volume {annual_invoice_volume:.2f}, base limit {base_limit:.2f}, "
        f"risk score {risk_score}, growth signal '{growth_signal}', and GST posture '{gst_posture}', "
        f"recommended annual credit range is {min_limit:.2f}–{max_limit:.2f}."
    )
    return {
        "min_limit": round(min_limit, 2),
        "max_limit": round(max_limit, 2),
        "economics_base_limit": round(base_limit, 2),
        "nominal_floor": round(min_limit, 2),
        "nominal_ceiling": round(max_limit, 2),
        "reasoning": reasoning,
    }


def audit_blocks_credit_limit(audit: Dict[str, Any]) -> Tuple[bool, str]:
    """True when fraud / elevated risk wording should trigger extra limit haircuts (not a hard reject)."""
    if not isinstance(audit, dict):
        return False, ""
    rec = str(audit.get("recommendation", "")).lower().strip()
    if rec == "reject":
        return True, "Auditor recommendation is reject."
    risk = int(audit.get("risk_score", 0) or 0)
    if risk >= 65:
        return True, f"Auditor risk score {risk} is above the credit-limit safety threshold."
    flags = audit.get("flags") or []
    if not isinstance(flags, list):
        flags = [str(flags)]
    combined = " ".join(str(f) for f in flags)
    for kw in _BLOCKING_FLAG_KEYWORDS:
        if _combined_flags_contain_keyword(combined, kw):
            return True, f"Auditor flags matched blocking term '{kw}'."
    return False, ""


def credit_limit_skip_log_lines(reason: str) -> List[str]:
    """Legacy helper; contextual limits normally always emit a band + rationale."""
    base = "CreditLimit: No numeric band could be anchored from available financial signals."
    if reason.strip():
        return [base, f"CreditLimit: {reason.strip()}"]
    return [base]


def credit_limit_agent_log_lines(result: Dict[str, Any]) -> List[str]:
    """Structured lines appended to pipeline ``agent_logs`` (UI + audit trail)."""
    if not isinstance(result, dict) or "min_limit" not in result or "max_limit" not in result:
        return []
    mn = result.get("min_limit")
    mx = result.get("max_limit")
    lines: List[str] = [
        f"CreditLimit: Recommended annual range min={mn} max={mx}.",
    ]
    if "economics_base_limit" in result and "nominal_ceiling" in result:
        lines.append(
            f"CreditLimit: Economics base={result.get('economics_base_limit')} "
            f"nominal_ceiling={result.get('nominal_ceiling')}."
        )
    rationale = result.get("reasoning")
    if rationale:
        lines.append(f"CreditLimit: Rationale — {rationale}")
    return lines
