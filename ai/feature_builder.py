# -*- coding: utf-8 -*-
"""Build structured market contexts for AI-side report interpretation."""

from __future__ import annotations

import math
from typing import Any, Dict

import pandas as pd


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _round(value: float, digits: int = 2) -> float:
    if value is None or math.isnan(value) or math.isinf(value):
        return 0.0
    return round(value, digits)


class IndexFeatureBuilder:
    """Create evidence-ready index features from OHLCV rows."""

    @classmethod
    def build(
        cls,
        *,
        code: str,
        name: str,
        hist: pd.DataFrame,
        row_t,
        row_t1,
        row_t2,
        auction_pct: float,
        close_pct: float,
        body_pct: float,
        vol_ratio: float,
    ) -> Dict[str, Any]:
        hist = hist.sort_values("date_int").copy()
        close = _safe_float(row_t.get("close"))
        open_price = _safe_float(row_t.get("open"))
        high = _safe_float(row_t.get("high"), close)
        low = _safe_float(row_t.get("low"), close)
        prev_close = _safe_float(row_t.get("prev_close"))

        body_abs = abs(close - open_price)
        upper_shadow = max(0.0, high - max(open_price, close))
        lower_shadow = max(0.0, min(open_price, close) - low)
        denom = prev_close if prev_close > 0 else max(close, 1.0)

        close_series = hist["close"].astype(float)
        ma = {}
        for window in (5, 10, 13, 30):
            if len(close_series) >= window:
                ma[f"ma{window}"] = _round(close_series.tail(window).mean())

        distances = {}
        for key, value in ma.items():
            if value:
                distances[f"distance_to_{key}_pct"] = _round((close - value) / value * 100)

        recent_5 = hist.tail(min(5, len(hist)))
        high_5 = _safe_float(recent_5["high"].max(), high)
        low_5 = _safe_float(recent_5["low"].min(), low)
        pos_5d = 50.0
        if high_5 > low_5:
            pos_5d = (close - low_5) / (high_5 - low_5) * 100

        pressure = []
        support = []
        for key, value in ma.items():
            if not value:
                continue
            dist = (value - close) / close * 100 if close else 0
            if 0 <= dist <= 1.5:
                pressure.append(key)
            elif -1.5 <= dist < 0:
                support.append(key)

        return {
            "code": code,
            "name": name,
            "date": int(row_t.get("date_int", 0)),
            "today": {
                "open": _round(open_price),
                "high": _round(high),
                "low": _round(low),
                "close": _round(close),
                "auction_pct": _round(auction_pct),
                "close_pct": _round(close_pct),
                "body_pct": _round(body_pct),
                "upper_shadow_pct": _round(upper_shadow / denom * 100),
                "lower_shadow_pct": _round(lower_shadow / denom * 100),
                "body_size_pct": _round(body_abs / denom * 100),
                "vol_ratio": _round(vol_ratio),
            },
            "previous": {
                "t1_pct": _round(_safe_float(row_t1.get("pct")) if row_t1 is not None else 0),
                "t2_pct": _round(_safe_float(row_t2.get("pct")) if row_t2 is not None else 0),
            },
            "moving_averages": ma,
            "distances": distances,
            "position": {
                "pos_5d": _round(pos_5d),
                "high_5d": _round(high_5),
                "low_5d": _round(low_5),
                "near_pressure": pressure,
                "near_support": support,
            },
        }
