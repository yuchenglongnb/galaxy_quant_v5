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
    date_in_scope = (not start or date_value >= start) and (not end or date_value <= end)
    usable_records = [row for row in records if _sector_record_usable(row)]
    in_scope = date_in_scope and bool(usable_records)
    daily_return_available = in_scope and any(
        _has_daily_return_for_date(row, date_value) for row in usable_records
    )
    if not date_in_scope:
        availability_reason = "date_outside_sector_evidence_scope"
    elif not records:
        availability_reason = "sector_records_missing"
    elif not usable_records:
        availability_reason = "no_usable_sector_records"
    elif daily_return_available:
        availability_reason = "daily_sector_return_available"
    else:
        availability_reason = "usable_range_context_without_daily_return"
    range_return_available = any(
        str(row.get("return_scope", "") or "") != "unavailable"
        for row in usable_records
    )
    return {
        "available": in_scope,
        "scope": f"{start}_{end}" if start and end else "",
        "daily_return_available": daily_return_available,
        "return_scope": "daily" if daily_return_available else (
            "period_arithmetic_mean" if in_scope and range_return_available else "unavailable"
        ),
        "usable_record_count": len(usable_records),
        "total_record_count": len(records),
        "availability_reason": availability_reason,
    }


def _sector_record_usable(row):
    quality = str(row.get("data_quality", "") or "")
    if quality not in {"usable_sector_only", "usable_sector_daily"}:
        return False
    return (
        str(row.get("return_scope", "") or "") != "unavailable"
        or str(row.get("turnover_scope", "") or "") != "unavailable"
        or bool(row.get("daily_amount"))
    )


def _has_daily_return_for_date(row, date_value):
    if not bool(row.get("daily_return_available")):
        return False
    for field in ("daily_return", "daily_returns", "return_by_date"):
        values = row.get(field)
        if isinstance(values, dict) and date_value in values and values[date_value] is not None:
            return True
    return False


def _result(level, reasons, sector_context):
    return {
        "validation_level": level,
        "candidate_close_verified": level == "candidate_close",
        "reasons": sorted(set(reasons)),
        "sector_context": sector_context,
    }


def _empty(value):
    return value is None or bool(getattr(value, "empty", False))
