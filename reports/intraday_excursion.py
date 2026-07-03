# -*- coding: utf-8 -*-
"""Validation-only OHLC excursion features for auction and T+1 reports."""

from __future__ import annotations

import math
from typing import Any


EXCURSION_FIELDS = (
    "open_to_high_pct",
    "open_to_low_pct",
    "close_to_high_drawdown_pct",
    "intraday_range_pct",
    "mfe_pct",
    "mae_pct",
    "signal_path_type",
)


def compute_intraday_excursion_fields(
    ohlc: dict[str, Any] | Any,
    *,
    body_pct: Any = None,
    auction_pct: Any = None,
) -> dict[str, float | str | None]:
    """Return report-only path features from open/high/low/close.

    The fields are descriptive validation labels only; they do not encode
    signal direction or strategy decisions.
    """

    open_price = _field_number(ohlc, "open")
    high = _field_number(ohlc, "high")
    low = _field_number(ohlc, "low")
    close = _field_number(ohlc, "close")
    if not _valid_price(open_price) or not _valid_price(high) or not _valid_price(low) or not _valid_price(close):
        return _empty_fields()

    computed_body = _number(body_pct)
    if computed_body is None:
        computed_body = _pct(close, open_price)
    auction = _number(auction_pct)

    open_to_high = _pct(high, open_price)
    open_to_low = _pct(low, open_price)
    close_to_high_drawdown = _pct(close, high)
    intraday_range = _pct(high, low)
    lower_rebound = _pct(close, low)

    return {
        "open_to_high_pct": _round(open_to_high),
        "open_to_low_pct": _round(open_to_low),
        "close_to_high_drawdown_pct": _round(close_to_high_drawdown),
        "intraday_range_pct": _round(intraday_range),
        "mfe_pct": _round(open_to_high),
        "mae_pct": _round(open_to_low),
        "signal_path_type": classify_signal_path(
            open_to_high_pct=open_to_high,
            open_to_low_pct=open_to_low,
            close_to_high_drawdown_pct=close_to_high_drawdown,
            lower_rebound_pct=lower_rebound,
            body_pct=computed_body,
            auction_pct=auction,
        ),
    }


def prefix_excursion_fields(fields: dict[str, Any], prefix: str) -> dict[str, Any]:
    """Prefix all excursion fields except missing keys are still represented."""

    return {f"{prefix}_{field}": fields.get(field) for field in EXCURSION_FIELDS}


def classify_signal_path(
    *,
    open_to_high_pct: float | None,
    open_to_low_pct: float | None,
    close_to_high_drawdown_pct: float | None,
    lower_rebound_pct: float | None,
    body_pct: float | None,
    auction_pct: float | None = None,
) -> str:
    if any(value is None for value in (open_to_high_pct, open_to_low_pct, close_to_high_drawdown_pct, lower_rebound_pct, body_pct)):
        return "unknown"

    if open_to_high_pct <= 0.8 and body_pct <= -2.0:
        return "one_way_selloff"
    if auction_pct is not None and auction_pct > 0 and open_to_high_pct >= 1.0 and close_to_high_drawdown_pct <= -2.0 and body_pct < 0:
        return "high_open_trap"
    if auction_pct is not None and auction_pct <= 0 and open_to_high_pct >= 1.5 and close_to_high_drawdown_pct <= -2.0 and body_pct <= 0:
        return "low_open_rebound_failed"
    if open_to_high_pct >= 2.0 and close_to_high_drawdown_pct <= -3.0:
        return "rush_up_fade"
    if close_to_high_drawdown_pct >= -0.5:
        return "close_near_high"
    if lower_rebound_pct <= 0.5:
        return "close_near_low"
    return "range_chop"


def _empty_fields() -> dict[str, float | str | None]:
    return {
        "open_to_high_pct": None,
        "open_to_low_pct": None,
        "close_to_high_drawdown_pct": None,
        "intraday_range_pct": None,
        "mfe_pct": None,
        "mae_pct": None,
        "signal_path_type": "unknown",
    }


def _field_number(ohlc: dict[str, Any] | Any, field: str) -> float | None:
    if isinstance(ohlc, dict):
        return _number(ohlc.get(field))
    getter = getattr(ohlc, "get", None)
    if callable(getter):
        return _number(getter(field))
    return _number(getattr(ohlc, field, None))


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _valid_price(value: float | None) -> bool:
    return value is not None and value > 0


def _pct(numerator: float, denominator: float) -> float:
    return (numerator / denominator - 1.0) * 100.0


def _round(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None
