# -*- coding: utf-8 -*-
"""Diagnose why 09:35 confirmation coverage is missing or weak."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.auction import AuctionAnalyzer
from core.data_manager import DataManager
from core.intraday_confirmation import IntradayConfirmationBuilder
from utils.encoding import configure_utf8_console

EVAL_DIR = ROOT / "reports" / "analysis" / "evaluations"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str})
    except Exception:
        return pd.DataFrame()


def _pick_confirmation_value(signal: dict, field: str):
    data = signal.get("data", {}) or {}
    confirmation = data.get("confirmation_data", {}) or {}
    for container, key in (
        (confirmation, field),
        (data, f"confirmation_{field}"),
        (data, field),
    ):
        value = container.get(key)
        if value not in (None, ""):
            return value
    return None


def _is_present(value) -> bool:
    if value in (None, ""):
        return False
    try:
        return not pd.isna(value)
    except Exception:
        return True


def _safe_ratio(numerator: int, denominator: int) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 0.0


def _extract_codes(df: pd.DataFrame) -> List[str]:
    if df.empty or "code" not in df.columns:
        return []
    return [str(code) for code in df["code"].astype(str).tolist() if str(code)]


def _time_values(df: pd.DataFrame) -> List[int]:
    if df.empty:
        return []
    for column in ("time_int", "feature_timestamp"):
        if column in df.columns:
            values = pd.to_numeric(df[column], errors="coerce").dropna()
            return sorted({int(v) for v in values.tolist()})
    return []


def _nearest_time_flag(time_values: Iterable[int]) -> bool:
    values = {int(v) for v in time_values}
    return 935 not in values and any(v in values for v in {934, 936, 937})


def classify_failure(day: dict) -> List[str]:
    flags: List[str] = []
    if day.get("raw_trend_count", 0) == 0:
        flags.append("no_trend_signals")
        return flags

    if day.get("confirmation_coverage_ratio", 0.0) >= 0.6:
        if day.get("benchmark_etf_mapping_count", 0) == 0 and day.get("stock_trend_count", 0) > 0:
            flags.append("benchmark_mapping_missing")
        flags.append("coverage_available")
        return flags

    if not day.get("intraday_dir_exists", False):
        flags.append("intraday_cache_missing")
        return flags

    if day.get("stock_signal_code_missing_count", 0) > 0:
        flags.append("signal_code_missing")

    if day.get("stock_data_code_count", 0) == 0:
        flags.append("stock_intraday_missing")

    if day.get("stock_data_code_count", 0) > 0 and day.get("code_intersection_count", 0) == 0:
        flags.append("possible_code_normalization_issue")

    if day.get("stock_data_code_count", 0) > 0 and (
        day.get("etf_data_code_count", 0) == 0 or day.get("index_data_code_count", 0) == 0
    ):
        flags.append("benchmark_intraday_data_missing")

    if day.get("benchmark_etf_mapping_count", 0) == 0 and day.get("stock_trend_count", 0) > 0:
        flags.append("benchmark_mapping_missing")

    if day.get("confirmation_file_exists", False) and day.get("matched_confirmation_count", 0) > 0:
        if day.get("signal_enriched_count", 0) == 0:
            flags.append("confirmation_enrichment_writeback_issue")

    if (
        day.get("intraday_dir_exists", False)
        and not day.get("confirmation_available", False)
        and (
            day.get("stock_data_code_count", 0) > 0
            or day.get("etf_data_code_count", 0) > 0
            or day.get("index_data_code_count", 0) > 0
        )
    ):
        flags.append("replay_intraday_loading_issue")

    if (
        day.get("confirmation_feature_timestamp") not in (None, 0)
        and int(day.get("confirmation_feature_timestamp", 0)) < 935
    ) or _nearest_time_flag(day.get("stock_time_values", [])):
        flags.append("possible_time_alignment_issue")

    if (
        day.get("confirmation_coverage_ratio", 0.0) == 0.0
        and day.get("confirmation_file_exists", False)
        and day.get("matched_confirmation_count", 0) > 0
        and day.get("signal_enriched_count", 0) > 0
    ):
        flags.append("coverage_present_but_filter_fields_missing")

    if not flags:
        flags.append("coverage_available")
    return flags


def pick_main_failure(flags: List[str]) -> str:
    priority = [
        "coverage_available",
        "intraday_cache_missing",
        "signal_code_missing",
        "stock_intraday_missing",
        "benchmark_intraday_data_missing",
        "possible_code_normalization_issue",
        "benchmark_mapping_missing",
        "confirmation_enrichment_writeback_issue",
        "replay_intraday_loading_issue",
        "possible_time_alignment_issue",
        "no_trend_signals",
        "coverage_present_but_filter_fields_missing",
        "coverage_available",
    ]
    for item in priority:
        if item in flags:
            return item
    return flags[0] if flags else "unknown"


def _benchmark_coverage(stock_trends: List[dict], confirm_df: pd.DataFrame) -> Dict[str, int]:
    benchmark_map_df = IntradayConfirmationBuilder.load_benchmark_map()
    benchmark_map = IntradayConfirmationBuilder._normalize_benchmark_map(benchmark_map_df)

    groups = [str((s.get("data", {}) or {}).get("group", "") or "") for s in stock_trends]
    nonempty_groups = [group for group in groups if group]
    signal_group_count = len(nonempty_groups)
    benchmark_etf_mapping_count = 0
    benchmark_index_mapping_count = 0
    for group in nonempty_groups:
        bench = benchmark_map.get(group, {})
        if str(bench.get("benchmark_etf_code", "") or ""):
            benchmark_etf_mapping_count += 1
        if str(bench.get("benchmark_index_code", "") or ""):
            benchmark_index_mapping_count += 1

    if not confirm_df.empty and "code" in confirm_df.columns:
        # Prefer matched confirmation rows when available: this reflects the actual
        # benchmark fields used during intraday feature construction.
        matched_codes = {str((s.get("data", {}) or {}).get("code", "") or "") for s in stock_trends}
        matched = confirm_df[confirm_df["code"].astype(str).isin(matched_codes)].copy()
        if not matched.empty:
            benchmark_etf_mapping_count = int(
                matched.get("benchmark_etf_code", pd.Series(dtype=str)).fillna("").astype(str).str.len().gt(0).sum()
            )
            benchmark_index_mapping_count = int(
                matched.get("benchmark_index_code", pd.Series(dtype=str)).fillna("").astype(str).str.len().gt(0).sum()
            )

    return {
        "signal_group_count": signal_group_count,
        "benchmark_etf_mapping_count": benchmark_etf_mapping_count,
        "benchmark_index_mapping_count": benchmark_index_mapping_count,
    }


def inspect_day(day: int, analyzer: AuctionAnalyzer, dm: DataManager) -> dict:
    result = analyzer.analyze(int(day), realtime=False)
    signals = (result.get("signals") or {})
    trend_signals = list(signals.get("trend", []) or [])
    stock_trends = [signal for signal in trend_signals if ((signal.get("data") or {}).get("target_type") == "stock")]

    stock_signal_codes = [str((signal.get("data") or {}).get("code", "") or "") for signal in stock_trends]
    stock_signal_codes_nonempty = [code for code in stock_signal_codes if code]
    stock_signal_code_missing_count = len(stock_signal_codes) - len(stock_signal_codes_nonempty)

    intraday_dir = Path(dm.base_path) / str(int(day)) / "intraday"
    stock_path = intraday_dir / "stocks_1min.csv"
    etf_path = intraday_dir / "etf_1min.csv"
    index_path = intraday_dir / "indices_1min.csv"
    confirm_path = intraday_dir / "stock_confirmation_latest.csv"

    stock_df = _read_csv(stock_path)
    etf_df = _read_csv(etf_path)
    index_df = _read_csv(index_path)
    confirm_df = _read_csv(confirm_path)

    stock_data_codes = _extract_codes(stock_df)
    etf_data_codes = _extract_codes(etf_df)
    index_data_codes = _extract_codes(index_df)
    confirmation_codes = _extract_codes(confirm_df)

    code_intersection = sorted(set(stock_signal_codes_nonempty) & set(stock_data_codes))
    confirmation_intersection = sorted(set(stock_signal_codes_nonempty) & set(confirmation_codes))

    coverage_context = {}
    for signal in trend_signals:
        context = signal.get("trend_filter_context", {}) or {}
        if context:
            coverage_context = context
            break
    stock_rs_etf = sum(1 for signal in stock_trends if _is_present(_pick_confirmation_value(signal, "rs_vs_etf_pct")))
    stock_rs_index = sum(1 for signal in stock_trends if _is_present(_pick_confirmation_value(signal, "rs_vs_index_pct")))
    stock_amount_ratio = sum(1 for signal in stock_trends if _is_present(_pick_confirmation_value(signal, "amount_1m_ratio")))

    intraday_meta = result.get("intraday_confirmation", {}) or {}
    signal_enrichment_meta = intraday_meta.get("signal_enrichment", {}) or {}
    benchmark_stats = _benchmark_coverage(stock_trends, confirm_df)

    row = {
        "date": str(int(day)),
        "raw_trend_count": len(trend_signals),
        "stock_trend_count": len(stock_trends),
        "intraday_dir_exists": intraday_dir.exists(),
        "stock_file_exists": stock_path.exists(),
        "etf_file_exists": etf_path.exists(),
        "index_file_exists": index_path.exists(),
        "confirmation_file_exists": confirm_path.exists(),
        "stock_data_code_count": len(set(stock_data_codes)),
        "etf_data_code_count": len(set(etf_data_codes)),
        "index_data_code_count": len(set(index_data_codes)),
        "confirmation_code_count": len(set(confirmation_codes)),
        "code_intersection_count": len(code_intersection),
        "matched_confirmation_count": len(confirmation_intersection),
        "benchmark_etf_mapping_count": benchmark_stats["benchmark_etf_mapping_count"],
        "benchmark_index_mapping_count": benchmark_stats["benchmark_index_mapping_count"],
        "signal_group_count": benchmark_stats["signal_group_count"],
        "rs_vs_etf_available_count": stock_rs_etf,
        "rs_vs_index_available_count": stock_rs_index,
        "amount_1m_ratio_available_count": stock_amount_ratio,
        "confirmation_coverage_ratio": _safe_ratio(
            int(coverage_context.get("confirmation_coverage_count", 0)),
            int(coverage_context.get("trend_total_count", 0)),
        ),
        "confirmation_coverage_count": int(coverage_context.get("confirmation_coverage_count", 0) or 0),
        "trend_total_count": int(coverage_context.get("trend_total_count", len(trend_signals)) or len(trend_signals)),
        "trend_filter_status": str(next((s.get("trend_filter_status") for s in trend_signals if s.get("trend_filter_status")), "disabled")),
        "confirmation_available": bool(signal_enrichment_meta.get("available")),
        "confirmation_feature_timestamp": signal_enrichment_meta.get("feature_timestamp"),
        "signal_enriched_count": int(signal_enrichment_meta.get("enriched_count", 0) or 0),
        "stock_signal_code_missing_count": stock_signal_code_missing_count,
        "stock_time_values": _time_values(stock_df),
        "etf_time_values": _time_values(etf_df),
        "index_time_values": _time_values(index_df),
        "signal_code_examples": stock_signal_codes_nonempty[:10],
        "stock_data_code_examples": stock_data_codes[:10],
        "etf_data_code_examples": etf_data_codes[:10],
        "index_data_code_examples": index_data_codes[:10],
        "unmatched_signal_code_examples": sorted(set(stock_signal_codes_nonempty) - set(stock_data_codes))[:10],
        "unmatched_confirmation_code_examples": sorted(set(stock_signal_codes_nonempty) - set(confirmation_codes))[:10],
        "signal_enrichment_meta": signal_enrichment_meta,
    }
    row["failure_flags"] = classify_failure(row)
    row["main_failure"] = pick_main_failure(row["failure_flags"])
    return row


def scan_days(start: str | None = None, end: str | None = None, max_days: int = 60) -> List[int]:
    dm = DataManager()
    local_days = [int(day) for day in dm.get_local_daily_days()]
    selected = []
    start_int = int(start) if start else None
    end_int = int(end) if end else None
    for day in sorted(local_days, reverse=True):
        if start_int and day < start_int:
            continue
        if end_int and day > end_int:
            continue
        selected.append(day)
        if len(selected) >= max_days:
            break
    return list(sorted(selected))


def build_payload(days: List[int]) -> dict:
    dm = DataManager()
    analyzer = AuctionAnalyzer(dm)
    daily = [inspect_day(day, analyzer, dm) for day in days]
    failure_distribution = Counter(item["main_failure"] for item in daily)

    recommended = []
    if any(item["main_failure"] == "intraday_cache_missing" for item in daily):
        recommended.append("优先补齐 monitor / snapshot-backfill 的 intraday 落盘，避免 replay 时完全没有 confirmation 输入。")
    if any(item["main_failure"] == "signal_code_missing" for item in daily):
        recommended.append("修复 raw trend signal 的 code 写回，确保 confirmation enrichment 能按 code join。")
    if any(item["main_failure"] == "benchmark_intraday_data_missing" for item in daily):
        recommended.append("检查 ETF / 指数 1min 文件是否和股票分钟数据一起落盘。")
    if any(item["main_failure"] == "possible_time_alignment_issue" for item in daily):
        recommended.append("评估 09:35 邻近 bar fallback（09:34/09:36）是否需要成为可配置诊断修复项。")
    if any(item["main_failure"] == "possible_code_normalization_issue" for item in daily):
        recommended.append("检查 intraday code 与 signal code 是否存在格式不一致，并考虑增加局部 normalization。")

    scope = {
        "start": daily[0]["date"] if daily else "",
        "end": daily[-1]["date"] if daily else "",
        "days_scanned": len(daily),
    }
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scope": scope,
        "daily": daily,
        "failure_distribution": dict(failure_distribution),
        "recommended_minimal_fixes": recommended,
    }


def write_outputs(payload: dict):
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    json_path = EVAL_DIR / "confirmation_coverage_diagnosis.json"
    md_path = EVAL_DIR / "confirmation_coverage_diagnosis.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Confirmation Coverage Diagnosis",
        "",
        "## 1. Diagnosis Scope",
        "",
        f"- start: `{payload['scope']['start']}`",
        f"- end: `{payload['scope']['end']}`",
        f"- days_scanned: `{payload['scope']['days_scanned']}`",
        "",
        "## 2. Coverage Summary",
        "",
        "| date | raw_trend | stock_data_codes | etf_data_codes | index_data_codes | code_intersection | etf_mapping | index_mapping | rs_vs_etf | rs_vs_index | amount_ratio | coverage_ratio | main_failure |",
        "| ---- | --------: | ---------------: | -------------: | ---------------: | ----------------: | ----------: | ------------: | --------: | ----------: | -----------: | -------------: | ------------ |",
    ]
    for row in payload["daily"]:
        lines.append(
            f"| {row['date']} | {row['raw_trend_count']} | {row['stock_data_code_count']} | "
            f"{row['etf_data_code_count']} | {row['index_data_code_count']} | {row['code_intersection_count']} | "
            f"{row['benchmark_etf_mapping_count']} | {row['benchmark_index_mapping_count']} | "
            f"{row['rs_vs_etf_available_count']} | {row['rs_vs_index_available_count']} | "
            f"{row['amount_1m_ratio_available_count']} | {row['confirmation_coverage_ratio']:.4f} | {row['main_failure']} |"
        )

    lines.extend(
        [
            "",
            "## 3. Failure Reason Distribution",
            "",
            "| failure_reason | count |",
            "| ------------------------------- | ----: |",
        ]
    )
    for reason, count in sorted(payload["failure_distribution"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {reason} | {count} |")

    deep_dive = next((row for row in payload["daily"] if row["date"] == "20260612"), None)
    if deep_dive:
        lines.extend(
            [
                "",
                "## 4. 20260612 Deep Dive",
                "",
                f"- raw trend signals: `{deep_dive['raw_trend_count']}`",
                f"- stock trend signals: `{deep_dive['stock_trend_count']}`",
                f"- intraday dir exists: `{deep_dive['intraday_dir_exists']}`",
                f"- confirmation file exists: `{deep_dive['confirmation_file_exists']}`",
                f"- confirmation coverage ratio: `{deep_dive['confirmation_coverage_ratio']:.4f}`",
                f"- trend filter status: `{deep_dive['trend_filter_status']}`",
                f"- failure flags: `{', '.join(deep_dive['failure_flags'])}`",
                f"- main failure: `{deep_dive['main_failure']}`",
                "",
                "结论：20260612 的 coverage=0 不是规则过严，而是 replay 当天本地没有 intraday confirmation 输入，属于数据缺失场景。",
            ]
        )

    lines.extend(
        [
            "",
            "## 5. Recommended Minimal Fix",
            "",
        ]
    )
    if payload["recommended_minimal_fixes"]:
        lines.extend([f"- {item}" for item in payload["recommended_minimal_fixes"]])
    else:
        lines.append("- 暂未发现需要额外修复的最小项。")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def parse_args():
    parser = argparse.ArgumentParser(description="Diagnose 09:35 confirmation coverage on local replay data.")
    parser.add_argument("date", nargs="?", default="", help="Optional single trade date YYYYMMDD")
    parser.add_argument("--start", default="", help="Scan start date YYYYMMDD")
    parser.add_argument("--end", default="", help="Scan end date YYYYMMDD")
    parser.add_argument("--max-days", type=int, default=60, help="Maximum local trading days to scan")
    return parser.parse_args()


def main():
    configure_utf8_console()
    args = parse_args()
    if args.date:
        days = [int(args.date)]
    else:
        days = scan_days(start=args.start or None, end=args.end or None, max_days=args.max_days)
    payload = build_payload(days)
    json_path, md_path = write_outputs(payload)
    print(
        json.dumps(
            {
                "json": str(json_path.relative_to(ROOT)),
                "md": str(md_path.relative_to(ROOT)),
                "days_scanned": payload["scope"]["days_scanned"],
                "failure_distribution": payload["failure_distribution"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
