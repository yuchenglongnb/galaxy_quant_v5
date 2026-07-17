"""Resolve daily evidence levels from one strict, provider-aware contract."""

from __future__ import annotations


def derive_daily_validation_level(
    date,
    detail_df,
    metrics_df,
    review,
    availability_record=None,
    sector_evidence=None,
    allow_unverified_candidate_close=False,
):
    """Return a structured validation level without promoting partial evidence."""

    detail_available = not _empty(detail_df)
    metrics_available = not _empty(metrics_df)
    review_available = bool(review)
    review_final = str((review or {}).get("validation_scope", "")) == "post_close_final"
    availability_level = str((availability_record or {}).get("validation_level", "") or "")
    candidate_artifacts_complete = (
        detail_available and metrics_available and review_available and review_final
    )

    reasons = []
    if not detail_available:
        reasons.append("signal_detail_missing_or_empty")
    if not metrics_available:
        reasons.append("signal_metrics_missing_or_empty")
    if not review_available:
        reasons.append("auction_review_missing")
    elif not review_final:
        reasons.append("auction_review_not_post_close_final")

    if candidate_artifacts_complete and availability_level == "candidate_close":
        level = "candidate_close"
    elif candidate_artifacts_complete and not availability_record:
        level = "candidate_close" if allow_unverified_candidate_close else "candidate_close_unverified"
        if not allow_unverified_candidate_close:
            reasons.append("availability_record_missing")
    else:
        if availability_record and availability_level != "candidate_close":
            reasons.append("availability_not_candidate_close")
        sector_context = _sector_context(date, sector_evidence)
        if sector_context["available"]:
            level = (
                "sector_daily_evidence"
                if sector_context["daily_return_available"]
                else "sector_range_context"
            )
        elif detail_available or metrics_available or review_available:
            level = "candidate_partial"
        else:
            level = "missing"
        return _result(level, reasons, sector_context)

    return _result(level, reasons, _sector_context(date, sector_evidence))


def _sector_context(date, payload):
    payload = payload or {}
    records = payload.get("records", []) if isinstance(payload, dict) else []
    date_value = str(date)
    start = str(payload.get("date_start", "") or "")
    end = str(payload.get("date_end", "") or "")
    in_scope = bool(records) and (not start or date_value >= start) and (not end or date_value <= end)
    daily_return_available = in_scope and any(
        bool(row.get("daily_return_available")) for row in records
    )
    return {
        "available": in_scope,
        "scope": f"{start}_{end}" if start and end else "",
        "daily_return_available": daily_return_available,
        "return_scope": "daily" if daily_return_available else (
            "period_arithmetic_mean" if in_scope else "unavailable"
        ),
    }


def _result(level, reasons, sector_context):
    return {
        "validation_level": level,
        "candidate_close_verified": level == "candidate_close",
        "reasons": sorted(set(reasons)),
        "sector_context": sector_context,
    }


def _empty(value):
    return value is None or bool(getattr(value, "empty", False))
