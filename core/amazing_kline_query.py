# -*- coding: utf-8 -*-
"""Shared AmazingData min1 query helper for replay backfill and probes."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from core.amazing_login_client import bootstrap_amazingdata_client, logout_amazingdata_client
from core.calendar_helper import CalendarHelper
from core.snapshot_utils import iter_kline_frames, trade_time_to_hhmmss

LogCallback = Callable[[str, str], None]


def _append_progress(progress_path: str | None, payload: dict) -> None:
    if not progress_path:
        return
    path = Path(progress_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _log_event(
    progress_path: str | None,
    date_int: int,
    stage: str,
    status: str,
    started: float,
    *,
    code_count: int = 0,
    row_count: int = 0,
    warning: str = "",
    error: str = "",
    extra: Optional[dict] = None,
) -> None:
    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "date": str(int(date_int)),
        "stage": stage,
        "status": status,
        "elapsed_sec": round(time.time() - started, 4),
        "code_count": int(code_count or 0),
        "row_count": int(row_count or 0),
        "warning": warning or "",
        "error": error or "",
    }
    if extra:
        payload.update(extra)
    _append_progress(progress_path, payload)


def query_min1_kline_once(
    date_int: int,
    code_list: list[str],
    begin_time: int = 930,
    end_time: int = 935,
    batch_size: int = 20,
    progress_path: str | None = None,
    stage: str = "min1_probe",
    warn_after_sec: float | None = None,
    logout_after: bool = False,
) -> pd.DataFrame:
    if not code_list:
        return pd.DataFrame()

    started = time.time()
    ad = None
    config = None
    try:
        _log_event(
            progress_path,
            date_int,
            stage=f"{stage}_bootstrap",
            status="start",
            started=started,
            code_count=len(code_list),
            extra={
                "bootstrap_mode": "isolated_query",
                "begin_time": int(begin_time),
                "end_time": int(end_time),
                "batch_size": int(batch_size),
            },
        )
        ad, config = bootstrap_amazingdata_client()
        calendar = CalendarHelper.generate_workday_calendar(days=30)
        market = ad.MarketData(calendar)
        _log_event(
            progress_path,
            date_int,
            stage=f"{stage}_bootstrap",
            status="done",
            started=started,
            code_count=len(code_list),
            extra={
                "bootstrap_mode": "isolated_query",
                "calendar_size": len(calendar),
                "begin_time": int(begin_time),
                "end_time": int(end_time),
                "batch_size": int(batch_size),
            },
        )

        rows = []
        for i in range(0, len(code_list), batch_size):
            batch = [str(code) for code in code_list[i:i + batch_size] if str(code)]
            batch_started = time.time()
            _log_event(
                progress_path,
                date_int,
                stage=f"{stage}_batch",
                status="start",
                started=batch_started,
                code_count=len(batch),
                extra={
                    "bootstrap_mode": "isolated_query",
                    "batch_codes": batch,
                    "query_kwargs": {
                        "begin_date": int(date_int),
                        "end_date": int(date_int),
                        "period": "min1",
                        "begin_time": int(begin_time),
                        "end_time": int(end_time),
                    },
                },
            )
            try:
                result = market.query_kline(
                    batch,
                    begin_date=int(date_int),
                    end_date=int(date_int),
                    period=ad.constant.Period.min1.value,
                    begin_time=int(begin_time),
                    end_time=int(end_time),
                )
            except Exception as exc:
                _log_event(
                    progress_path,
                    date_int,
                    stage=f"{stage}_batch",
                    status="failed",
                    started=batch_started,
                    code_count=len(batch),
                    error=str(exc),
                    extra={"bootstrap_mode": "isolated_query", "batch_codes": batch},
                )
                continue

            batch_rows = 0
            for code, frame in iter_kline_frames(result or {}):
                if frame is None or frame.empty:
                    continue
                work = frame.copy()
                work["code"] = code
                if "kline_time" in work.columns:
                    work["_kline_hhmmss"] = work["kline_time"].map(trade_time_to_hhmmss)
                    work["time_int"] = (
                        pd.to_numeric(work["_kline_hhmmss"], errors="coerce").fillna(0).astype(int) // 100
                    )
                    work = work[(work["time_int"] >= int(begin_time)) & (work["time_int"] <= int(end_time))].copy()
                batch_rows += len(work)
                rows.append(work)
            batch_elapsed = time.time() - batch_started
            warning = ""
            if warn_after_sec and batch_elapsed >= float(warn_after_sec):
                warning = "batch_elapsed_exceeded_warn_after_sec"
            _log_event(
                progress_path,
                date_int,
                stage=f"{stage}_batch",
                status="done",
                started=batch_started,
                code_count=len(batch),
                row_count=batch_rows,
                warning=warning,
                extra={"bootstrap_mode": "isolated_query", "batch_codes": batch},
            )

        if not rows:
            return pd.DataFrame()
        return pd.concat(rows, ignore_index=True)
    finally:
        if logout_after:
            logout_amazingdata_client(ad, config)
