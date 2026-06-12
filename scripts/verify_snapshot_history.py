#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Verify AmazingData historical snapshot usability for auction/minute reconstruction."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime

import AmazingData as ad
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config.settings import DBConfig
from core.snapshot_utils import iter_kline_frames, iter_snapshot_frames


DEFAULT_CODES = [
    "000001.SH",  # 上证
    "588000.SH",  # 科创50ETF
    "300308.SZ",  # 中际旭创
]


@dataclass
class VerificationResult:
    date: int
    code: str
    asset_type: str
    snapshot_rows: int
    snapshot_time_min: str
    snapshot_time_max: str
    snapshot_amount_monotonic: bool
    snapshot_volume_monotonic: bool
    snapshot_has_0925_window: bool
    snapshot_0925_time: str
    snapshot_0925_amount: float | None
    snapshot_0930_time: str
    snapshot_0930_amount: float | None
    snapshot_0930_delta_from_0925: float | None
    kline_rows: int
    kline_time_min: str
    kline_time_max: str
    kline_amount_sum: float | None
    kline_first_min_amount: float | None
    close_amount_gap: float | None
    structure: str


def do_login():
    ad.login(
        username=DBConfig.USERNAME,
        password=DBConfig.PASSWORD,
        host=DBConfig.IP,
        port=DBConfig.PORT,
    )


def get_target_date(requested: int | None) -> int:
    base = ad.BaseData()
    calendar = list(base.get_calendar())
    today = int(datetime.now().strftime("%Y%m%d"))
    if requested:
        return int(requested)
    valid_days = [day for day in calendar if int(day) <= today]
    return int(valid_days[-1])


def detect_asset_type(code: str) -> str:
    if code.endswith(".SH") and code.startswith("000"):
        return "index"
    if code.endswith(".BJ"):
        return "index"
    if code.startswith(("5", "1")) and code.endswith((".SH", ".SZ")):
        return "ETF_or_fund"
    return "stock"


def to_time_str(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    try:
        ts = pd.to_datetime(value)
        return ts.strftime("%H:%M:%S")
    except Exception:
        return str(value)


def monotonic(series: pd.Series) -> bool:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) <= 1:
        return True
    return bool((clean.diff().fillna(0) >= 0).all())


def latest_at_or_before(df: pd.DataFrame, hhmmss: str) -> pd.Series | None:
    if df.empty or "trade_time" not in df.columns:
        return None
    work = df.copy()
    work["_trade_time"] = pd.to_datetime(work["trade_time"], errors="coerce")
    work = work.dropna(subset=["_trade_time"])
    if work.empty:
        return None
    target = int(hhmmss.replace(":", ""))
    work["_clock"] = pd.to_numeric(work["_trade_time"].dt.strftime("%H%M%S"), errors="coerce")
    subset = work[work["_clock"] <= target]
    if subset.empty:
        return None
    return subset.sort_values("_clock").iloc[-1]


def first_at_or_after(df: pd.DataFrame, hhmmss: str) -> pd.Series | None:
    if df.empty or "trade_time" not in df.columns:
        return None
    work = df.copy()
    work["_trade_time"] = pd.to_datetime(work["trade_time"], errors="coerce")
    work = work.dropna(subset=["_trade_time"])
    if work.empty:
        return None
    target = int(hhmmss.replace(":", ""))
    work["_clock"] = pd.to_numeric(work["_trade_time"].dt.strftime("%H%M%S"), errors="coerce")
    subset = work[work["_clock"] >= target]
    if subset.empty:
        return None
    return subset.sort_values("_clock").iloc[0]


def infer_structure(result) -> str:
    if not isinstance(result, dict):
        return type(result).__name__
    sample = next(iter(result.values()), None)
    if isinstance(sample, pd.DataFrame):
        return "flat_dict[code->DataFrame]"
    if isinstance(sample, dict):
        return "nested_dict[date->code->DataFrame]"
    return f"dict[{type(sample).__name__}]"


def verify_code(market: "ad.MarketData", code: str, target_date: int) -> VerificationResult:
    snapshot_raw = market.query_snapshot([code], begin_date=target_date, end_date=target_date)
    structure = infer_structure(snapshot_raw)
    snapshot_frames = list(iter_snapshot_frames(snapshot_raw))
    snapshot_df = snapshot_frames[0][1].copy() if snapshot_frames else pd.DataFrame()
    if not snapshot_df.empty:
        for col in ("amount", "volume"):
            if col in snapshot_df.columns:
                snapshot_df[col] = pd.to_numeric(snapshot_df[col], errors="coerce")
        if "trade_time" in snapshot_df.columns:
            snapshot_df["trade_time"] = pd.to_datetime(snapshot_df["trade_time"], errors="coerce")
            snapshot_df = snapshot_df.dropna(subset=["trade_time"]).sort_values("trade_time")

    row_0925 = latest_at_or_before(snapshot_df, "09:25:00")
    row_0930 = first_at_or_after(snapshot_df, "09:30:00")

    kline_raw = market.query_kline([code], begin_date=target_date, end_date=target_date, period=ad.constant.Period.min1.value)
    kline_frames = list(iter_kline_frames(kline_raw))
    kline_df = kline_frames[0][1].copy() if kline_frames else pd.DataFrame()
    if not kline_df.empty:
        for col in ("amount", "volume"):
            if col in kline_df.columns:
                kline_df[col] = pd.to_numeric(kline_df[col], errors="coerce")
        if "kline_time" in kline_df.columns:
            kline_df["kline_time"] = pd.to_datetime(kline_df["kline_time"], errors="coerce")
            kline_df = kline_df.dropna(subset=["kline_time"]).sort_values("kline_time")

    snapshot_0925_amount = float(row_0925.get("amount")) if row_0925 is not None and pd.notna(row_0925.get("amount")) else None
    snapshot_0930_amount = float(row_0930.get("amount")) if row_0930 is not None and pd.notna(row_0930.get("amount")) else None
    kline_first_min_amount = None
    kline_amount_sum = None
    close_amount_gap = None
    if not kline_df.empty and "amount" in kline_df.columns:
        kline_amount_sum = float(kline_df["amount"].fillna(0).sum())
        if len(kline_df) > 0:
            kline_first_min_amount = float(kline_df.iloc[0].get("amount", 0) or 0)
    if snapshot_df is not None and not snapshot_df.empty and "amount" in snapshot_df.columns and kline_amount_sum is not None:
        close_amount_gap = float(snapshot_df.iloc[-1].get("amount", 0) or 0) - kline_amount_sum

    return VerificationResult(
        date=target_date,
        code=code,
        asset_type=detect_asset_type(code),
        snapshot_rows=int(len(snapshot_df)),
        snapshot_time_min=to_time_str(snapshot_df.iloc[0].get("trade_time")) if not snapshot_df.empty else "",
        snapshot_time_max=to_time_str(snapshot_df.iloc[-1].get("trade_time")) if not snapshot_df.empty else "",
        snapshot_amount_monotonic=monotonic(snapshot_df["amount"]) if "amount" in snapshot_df.columns else False,
        snapshot_volume_monotonic=monotonic(snapshot_df["volume"]) if "volume" in snapshot_df.columns else False,
        snapshot_has_0925_window=row_0925 is not None,
        snapshot_0925_time=to_time_str(row_0925.get("trade_time")) if row_0925 is not None else "",
        snapshot_0925_amount=snapshot_0925_amount,
        snapshot_0930_time=to_time_str(row_0930.get("trade_time")) if row_0930 is not None else "",
        snapshot_0930_amount=snapshot_0930_amount,
        snapshot_0930_delta_from_0925=(
            snapshot_0930_amount - snapshot_0925_amount
            if snapshot_0930_amount is not None and snapshot_0925_amount is not None
            else None
        ),
        kline_rows=int(len(kline_df)),
        kline_time_min=to_time_str(kline_df.iloc[0].get("kline_time")) if not kline_df.empty else "",
        kline_time_max=to_time_str(kline_df.iloc[-1].get("kline_time")) if not kline_df.empty else "",
        kline_amount_sum=kline_amount_sum,
        kline_first_min_amount=kline_first_min_amount,
        close_amount_gap=close_amount_gap,
        structure=structure,
    )


def result_to_dict(item: VerificationResult) -> dict:
    return {
        field: getattr(item, field)
        for field in item.__dataclass_fields__.keys()
    }


def write_outputs(results: list[VerificationResult], target_date: int):
    out_dir = os.path.join("reports", "verification", f"{target_date}")
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "amazing_snapshot_verification.json")
    csv_path = os.path.join(out_dir, "amazing_snapshot_verification.csv")
    md_path = os.path.join(out_dir, "amazing_snapshot_verification.md")

    payload = {
        "date": target_date,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "results": [result_to_dict(item) for item in results],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    df = pd.DataFrame([result_to_dict(item) for item in results])
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    lines = [f"# AmazingData Snapshot Verification {target_date}", ""]
    for item in results:
        lines.extend([
            f"## {item.code} ({item.asset_type})",
            f"- snapshot structure: `{item.structure}`",
            f"- snapshot rows: `{item.snapshot_rows}` | time range: `{item.snapshot_time_min}` -> `{item.snapshot_time_max}`",
            f"- snapshot monotonic amount/volume: `{item.snapshot_amount_monotonic}` / `{item.snapshot_volume_monotonic}`",
            f"- has 09:25 snapshot: `{item.snapshot_has_0925_window}` | 09:25 time `{item.snapshot_0925_time}` | amount `{item.snapshot_0925_amount}`",
            f"- first >=09:30: `{item.snapshot_0930_time}` | amount `{item.snapshot_0930_amount}` | delta from 09:25 `{item.snapshot_0930_delta_from_0925}`",
            f"- kline rows: `{item.kline_rows}` | time range: `{item.kline_time_min}` -> `{item.kline_time_max}`",
            f"- kline amount sum: `{item.kline_amount_sum}` | first min amount `{item.kline_first_min_amount}`",
            f"- snapshot close amount - kline amount sum: `{item.close_amount_gap}`",
            "",
        ])
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return json_path, csv_path, md_path


def main():
    parser = argparse.ArgumentParser(description="Verify AmazingData historical snapshot usability.")
    parser.add_argument("--date", type=int, default=None, help="Target trading date, e.g. 20260608")
    parser.add_argument("--codes", nargs="*", default=DEFAULT_CODES, help="Security codes to verify")
    args = parser.parse_args()

    do_login()
    target_date = get_target_date(args.date)
    base = ad.BaseData()
    calendar = base.get_calendar()
    market = ad.MarketData(calendar)

    results = []
    for code in args.codes:
        print(f"[verify] {target_date} {code}")
        results.append(verify_code(market, code, target_date))

    json_path, csv_path, md_path = write_outputs(results, target_date)
    print(f"[verify] JSON: {os.path.abspath(json_path)}")
    print(f"[verify] CSV:  {os.path.abspath(csv_path)}")
    print(f"[verify] MD:   {os.path.abspath(md_path)}")


if __name__ == "__main__":
    main()
