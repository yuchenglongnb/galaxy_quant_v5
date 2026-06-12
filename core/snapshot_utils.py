# -*- coding: utf-8 -*-
"""Normalize AmazingData SDK responses across snapshot/kline response shapes."""

from __future__ import annotations

from typing import Iterator, Tuple

import pandas as pd


def iter_snapshot_frames(result) -> Iterator[Tuple[str, pd.DataFrame]]:
    """Yield code/DataFrame pairs from flat or date-nested snapshot responses."""
    if not isinstance(result, dict):
        return
    for key, value in result.items():
        if isinstance(value, pd.DataFrame):
            yield str(key), value
        elif isinstance(value, dict):
            yield from iter_snapshot_frames(value)


def latest_snapshot_rows(result):
    """Return the latest snapshot row for each security code."""
    rows = {}
    for code, frame in iter_snapshot_frames(result):
        if frame is None or frame.empty:
            continue
        row = frame.iloc[-1].to_dict()
        row["code"] = str(row.get("code") or code)
        rows[row["code"]] = row
    return list(rows.values())


def trade_time_to_hhmmss(value) -> int | None:
    """Best-effort conversion from AmazingData trade_time to HHMMSS integer."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    if " " in text:
        text = text.split(" ")[-1]
    text = text.replace("T", " ").split(" ")[-1]
    text = text.split(".")[0]
    text = text.replace(":", "")
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) < 6:
        return None
    try:
        return int(digits[:6])
    except ValueError:
        return None


def snapshot_rows_near_time(
    result,
    target_hhmmss: int,
    floor_hhmmss: int | None = None,
    ceil_hhmmss: int | None = None,
):
    """
    Select one snapshot row per code near a target time.

    Preference order:
    1. latest row <= target_hhmmss inside the window
    2. earliest row > target_hhmmss inside the window
    """
    rows = {}
    for code, frame in iter_snapshot_frames(result):
        if frame is None or frame.empty:
            continue
        work = frame.copy()
        work["_hhmmss"] = work.get("trade_time").map(trade_time_to_hhmmss)
        work = work[work["_hhmmss"].notna()].copy()
        if work.empty:
            continue
        work["_hhmmss"] = work["_hhmmss"].astype(int)
        if floor_hhmmss is not None:
            work = work[work["_hhmmss"] >= int(floor_hhmmss)]
        if ceil_hhmmss is not None:
            work = work[work["_hhmmss"] <= int(ceil_hhmmss)]
        if work.empty:
            continue

        before = work[work["_hhmmss"] <= int(target_hhmmss)]
        if not before.empty:
            row = before.sort_values("_hhmmss").iloc[-1].to_dict()
        else:
            after = work[work["_hhmmss"] > int(target_hhmmss)]
            if after.empty:
                continue
            row = after.sort_values("_hhmmss").iloc[0].to_dict()
        row.pop("_hhmmss", None)
        row["code"] = str(row.get("code") or code)
        rows[row["code"]] = row
    return list(rows.values())


def iter_kline_frames(result) -> Iterator[Tuple[str, pd.DataFrame]]:
    """Yield code/DataFrame pairs from flat or date-nested kline responses."""
    if not isinstance(result, dict):
        return
    for key, value in result.items():
        if isinstance(value, pd.DataFrame):
            yield str(key), value
        elif isinstance(value, dict):
            yield from iter_kline_frames(value)
