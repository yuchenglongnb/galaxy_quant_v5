# -*- coding: utf-8 -*-
"""Audit benchmark ETF mapping gaps for active trend confirmation dates."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.auction import AuctionAnalyzer
from core.data_manager import DataManager
from core.intraday_confirmation import IntradayConfirmationBuilder
from scripts.diagnose_confirmation_coverage import _is_present
from utils.encoding import configure_utf8_console

EVAL_DIR = ROOT / "reports" / "analysis" / "evaluations"
BENCHMARK_MAP_PATH = ROOT / "watchlists" / "group_benchmark_map.csv"

SUGGESTION_RULES = [
    {
        "keywords": ("半导体",),
        "benchmark_etf_code": "512480.SH",
        "benchmark_index_code": "000688.SH",
        "benchmark_name": "半导体",
        "confidence": "high",
        "reason": "group_keyword_match",
    },
    {
        "keywords": ("证券",),
        "benchmark_etf_code": "512880.SH",
        "benchmark_index_code": "000001.SH",
        "benchmark_name": "证券",
        "confidence": "high",
        "reason": "group_keyword_match",
    },
    {
        "keywords": ("家电零部件", "消费电子"),
        "benchmark_etf_code": "159732.SZ",
        "benchmark_index_code": "399006.SZ",
        "benchmark_name": "消费电子",
        "confidence": "high",
        "reason": "group_keyword_match",
    },
    {
        "keywords": ("游戏", "传媒", "广告营销", "出版"),
        "benchmark_etf_code": "159805.SZ",
        "benchmark_index_code": "399006.SZ",
        "benchmark_name": "传媒",
        "confidence": "high",
        "reason": "group_keyword_match",
    },
    {
        "keywords": ("聚氨酯", "合成树脂", "化工", "钛白粉", "化学制品"),
        "benchmark_etf_code": "159870.SZ",
        "benchmark_index_code": "000001.SH",
        "benchmark_name": "化工",
        "confidence": "high",
        "reason": "group_keyword_match",
    },
    {
        "keywords": ("原料药", "创新药", "医疗"),
        "benchmark_etf_code": "512170.SH",
        "benchmark_index_code": "000001.SH",
        "benchmark_name": "医疗",
        "confidence": "medium",
        "reason": "broad_sector_fallback",
    },
    {
        "keywords": ("IT服务", "垂直应用软件"),
        "benchmark_etf_code": "159246.SZ",
        "benchmark_index_code": "399006.SZ",
        "benchmark_name": "AI人工智能",
        "confidence": "manual_required",
        "reason": "theme_proxy_candidate",
    },
    {
        "keywords": ("其他计算机设备",),
        "benchmark_etf_code": "159246.SZ",
        "benchmark_index_code": "399006.SZ",
        "benchmark_name": "AI人工智能",
        "confidence": "manual_required",
        "reason": "theme_proxy_candidate",
    },
    {
        "keywords": ("军工电子",),
        "benchmark_etf_code": "159206.SZ",
        "benchmark_index_code": "399006.SZ",
        "benchmark_name": "卫星",
        "confidence": "manual_required",
        "reason": "narrow_theme_proxy",
    },
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str}).fillna("")
    except Exception:
        return pd.DataFrame()


def _safe_ratio(numerator: int, denominator: int) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 0.0


def _load_map_rows() -> List[dict]:
    if not BENCHMARK_MAP_PATH.exists():
        return []
    with BENCHMARK_MAP_PATH.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _load_mapping() -> Dict[str, dict]:
    return IntradayConfirmationBuilder._normalize_benchmark_map(_read_csv(BENCHMARK_MAP_PATH))


def _normalize_group(value: str) -> str:
    return IntradayConfirmationBuilder._normalize_group_key(value)


def _suggest_mapping(group: str, theme_cluster: str = "") -> dict:
    group_text = group or ""
    theme_text = theme_cluster or ""
    for rule in SUGGESTION_RULES:
        if any(keyword and keyword in group_text for keyword in rule["keywords"]):
            return {
                "current_mapping": "",
                "suggested_benchmark_etf": rule["benchmark_name"],
                "suggested_benchmark_code": rule["benchmark_etf_code"],
                "suggested_benchmark_index_code": rule["benchmark_index_code"],
                "confidence": rule["confidence"],
                "suggested_action": "add_mapping" if rule["confidence"] == "high" else "manual_review",
                "reason": rule["reason"],
            }
    if theme_text:
        for rule in SUGGESTION_RULES:
            if any(keyword and keyword in theme_text for keyword in rule["keywords"]):
                return {
                    "current_mapping": "",
                    "suggested_benchmark_etf": rule["benchmark_name"],
                    "suggested_benchmark_code": rule["benchmark_etf_code"],
                    "suggested_benchmark_index_code": rule["benchmark_index_code"],
                    "confidence": "manual_required",
                    "suggested_action": "manual_review",
                    "reason": "theme_cluster_proxy",
                }
    return {
        "current_mapping": "",
        "suggested_benchmark_etf": "",
        "suggested_benchmark_code": "",
        "suggested_benchmark_index_code": "",
        "confidence": "manual_required",
        "suggested_action": "manual_review",
        "reason": "no_clear_etf_proxy",
    }


def _scan_days(start: str | None = None, end: str | None = None, max_days: int = 60) -> List[int]:
    dm = DataManager()
    local_days = [int(day) for day in dm.get_local_daily_days()]
    selected = []
    start_int = int(start) if start else None
    end_int = int(end) if end else None
    for day in sorted(local_days):
        if start_int and day < start_int:
            continue
        if end_int and day > end_int:
            continue
        selected.append(day)
    if max_days and len(selected) > max_days:
        return selected[-max_days:]
    return selected


def _refresh_confirmation_from_intraday(day: int) -> dict:
    intraday_dir = ROOT / "AmazingData_Store" / str(int(day)) / "intraday"
    stock_df = _read_csv(intraday_dir / "stocks_1min.csv")
    etf_df = _read_csv(intraday_dir / "etf_1min.csv")
    index_df = _read_csv(intraday_dir / "indices_1min.csv")
    if stock_df.empty:
        return {"date": str(day), "refreshed": False, "reason": "stock_intraday_missing"}
    features = IntradayConfirmationBuilder.build(stock_df, etf_df, index_df)
    latest_path = intraday_dir / "stock_confirmation_latest.csv"
    history_path = intraday_dir / "stock_confirmation_history.csv"
    intraday_dir.mkdir(parents=True, exist_ok=True)
    if features.empty:
        return {"date": str(day), "refreshed": False, "reason": "feature_build_empty"}
    features.to_csv(latest_path, index=False, encoding="utf-8-sig")
    features.to_csv(history_path, index=False, encoding="utf-8-sig")
    return {"date": str(day), "refreshed": True, "row_count": int(len(features))}


def _pick_rs_counts(stock_trends: List[dict]) -> Tuple[int, int]:
    rs_etf = 0
    rs_index = 0
    for signal in stock_trends:
        data = signal.get("data", {}) or {}
        confirmation = data.get("confirmation_data", {}) or {}
        if _is_present(confirmation.get("rs_vs_etf_pct")):
            rs_etf += 1
        if _is_present(confirmation.get("rs_vs_index_pct")):
            rs_index += 1
    return rs_etf, rs_index


def inspect_day(day: int, analyzer: AuctionAnalyzer, mapping: Dict[str, dict]) -> Tuple[dict, List[dict]]:
    result = analyzer.analyze(day, realtime=False)
    trend_signals = list((result.get("signals") or {}).get("trend", []) or [])
    stock_trends = [signal for signal in trend_signals if ((signal.get("data") or {}).get("target_type") == "stock")]
    groups = [str((signal.get("data") or {}).get("group", "") or "") for signal in stock_trends]
    theme_clusters = [str((signal.get("data") or {}).get("theme_cluster", "") or "") for signal in stock_trends]
    nonempty_groups = [group for group in groups if group]
    nonempty_theme_clusters = [theme for theme in theme_clusters if theme]

    mapped_etf = 0
    mapped_index = 0
    unmapped_records = []
    for signal in stock_trends:
        data = signal.get("data", {}) or {}
        group = str(data.get("group", "") or "")
        theme_cluster = str(data.get("theme_cluster", "") or "")
        normalized = _normalize_group(group)
        bench = mapping.get(normalized, {})
        if bench.get("benchmark_etf_code"):
            mapped_etf += 1
        if bench.get("benchmark_index_code"):
            mapped_index += 1
        if not bench.get("benchmark_etf_code"):
            unmapped_records.append(
                {
                    "date": str(day),
                    "code": str(data.get("code", "") or ""),
                    "name": str(data.get("name", signal.get("name", "")) or ""),
                    "group": group,
                    "theme_cluster": theme_cluster,
                }
            )

    coverage_context = {}
    for signal in trend_signals:
        context = signal.get("trend_filter_context", {}) or {}
        if context:
            coverage_context = context
            break
    rs_etf_count, rs_index_count = _pick_rs_counts(stock_trends)
    summary = {
        "date": str(day),
        "raw_trend_count": len(trend_signals),
        "stock_trend_count": len(stock_trends),
        "group_coverage_ratio": _safe_ratio(len(nonempty_groups), len(stock_trends)),
        "theme_cluster_coverage_ratio": _safe_ratio(len(nonempty_theme_clusters), len(stock_trends)),
        "benchmark_etf_mapping_ratio": _safe_ratio(mapped_etf, len(stock_trends)),
        "benchmark_index_mapping_ratio": _safe_ratio(mapped_index, len(stock_trends)),
        "rs_vs_etf_coverage_ratio": _safe_ratio(rs_etf_count, len(stock_trends)),
        "rs_vs_index_coverage_ratio": _safe_ratio(rs_index_count, len(stock_trends)),
        "confirmation_coverage_ratio": float(coverage_context.get("confirmation_coverage_ratio", 0.0) or 0.0),
        "trend_filter_status": str(next((signal.get("trend_filter_status") for signal in trend_signals if signal.get("trend_filter_status")), "disabled")),
    }
    active = summary["confirmation_coverage_ratio"] >= 0.6
    for item in unmapped_records:
        item["active_date"] = active
    return summary, unmapped_records


def build_payload(days: List[int], refresh_confirmation: bool = False) -> dict:
    refresh_results = []
    if refresh_confirmation:
        for day in days:
            refresh_results.append(_refresh_confirmation_from_intraday(day))

    mapping = _load_mapping()
    dm = DataManager()
    analyzer = AuctionAnalyzer(dm)
    daily_rows = []
    unmapped_groups: Dict[str, dict] = {}
    unmapped_themes: Dict[str, dict] = {}
    for day in days:
        row, missing = inspect_day(day, analyzer, mapping)
        daily_rows.append(row)
        for item in missing:
            group = item["group"]
            if group:
                entry = unmapped_groups.setdefault(
                    group,
                    {
                        "group": group,
                        "trend_signal_count": 0,
                        "dates": set(),
                        "example_codes": set(),
                        "theme_clusters": set(),
                        "active_trend_signal_count": 0,
                    },
                )
                entry["trend_signal_count"] += 1
                if item["active_date"]:
                    entry["active_trend_signal_count"] += 1
                entry["dates"].add(item["date"])
                if item["code"]:
                    entry["example_codes"].add(item["code"])
                if item["theme_cluster"]:
                    entry["theme_clusters"].add(item["theme_cluster"])
            theme_cluster = item["theme_cluster"]
            if theme_cluster:
                theme_entry = unmapped_themes.setdefault(
                    theme_cluster,
                    {
                        "theme_cluster": theme_cluster,
                        "trend_signal_count": 0,
                        "dates": set(),
                        "example_codes": set(),
                    },
                )
                theme_entry["trend_signal_count"] += 1
                theme_entry["dates"].add(item["date"])
                if item["code"]:
                    theme_entry["example_codes"].add(item["code"])

    active_dates = [row for row in daily_rows if row["confirmation_coverage_ratio"] >= 0.6]

    group_rows = []
    for group, entry in sorted(unmapped_groups.items(), key=lambda item: (-item[1]["trend_signal_count"], item[0])):
        theme_cluster = sorted(entry["theme_clusters"])[0] if entry["theme_clusters"] else ""
        suggestion = _suggest_mapping(group, theme_cluster)
        group_rows.append(
            {
                "group": group,
                "trend_signal_count": entry["trend_signal_count"],
                "active_trend_signal_count": entry["active_trend_signal_count"],
                "dates": sorted(entry["dates"]),
                "example_codes": sorted(entry["example_codes"])[:8],
                "current_mapping": "",
                **suggestion,
            }
        )

    theme_rows = []
    for theme_cluster, entry in sorted(unmapped_themes.items(), key=lambda item: (-item[1]["trend_signal_count"], item[0])):
        suggestion = _suggest_mapping("", theme_cluster)
        theme_rows.append(
            {
                "theme_cluster": theme_cluster,
                "trend_signal_count": entry["trend_signal_count"],
                "dates": sorted(entry["dates"]),
                "example_codes": sorted(entry["example_codes"])[:8],
                "current_mapping": "",
                **suggestion,
            }
        )

    top_mapping_gaps = sorted(
        group_rows,
        key=lambda row: (-row.get("active_trend_signal_count", 0), -row["trend_signal_count"], row["group"]),
    )[:10]
    recommended = []
    if any(row["suggested_action"] == "add_mapping" for row in group_rows):
        recommended.append("先补高置信 group -> benchmark ETF 映射，再刷新 active 日期 confirmation。")
    if any(row["suggested_action"] == "manual_review" for row in group_rows):
        recommended.append("低置信 group 保持 manual review，不为追求 coverage 统一映射到宽基 ETF。")
    if any(row["rs_vs_etf_coverage_ratio"] == 0 and row["confirmation_coverage_ratio"] >= 0.6 for row in active_dates):
        recommended.append("active 日期优先提升 rs_vs_etf 覆盖，而不是继续调 trend filter 阈值。")

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scope": {
            "start": str(days[0]) if days else "",
            "end": str(days[-1]) if days else "",
            "days_scanned": len(days),
        },
        "mapping_file": str(BENCHMARK_MAP_PATH.relative_to(ROOT)),
        "refresh_confirmation": refresh_confirmation,
        "refresh_results": refresh_results,
        "active_dates": active_dates,
        "daily": daily_rows,
        "unmapped_groups": group_rows,
        "unmapped_theme_clusters": theme_rows,
        "top_mapping_gaps": top_mapping_gaps,
        "recommended_minimal_fixes": recommended,
    }


def write_outputs(payload: dict):
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    json_path = EVAL_DIR / "benchmark_mapping_diagnosis.json"
    md_path = EVAL_DIR / "benchmark_mapping_diagnosis.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Benchmark Mapping Diagnosis",
        "",
        "## 1. Diagnosis Scope",
        "",
        f"- start: `{payload['scope']['start']}`",
        f"- end: `{payload['scope']['end']}`",
        f"- days_scanned: `{payload['scope']['days_scanned']}`",
        f"- mapping_file: `{payload['mapping_file']}`",
        "",
        "## 2. Active Dates Summary",
        "",
        "| date | raw_trend | confirmation_coverage | rs_vs_index_coverage | rs_vs_etf_coverage | benchmark_etf_mapping | benchmark_index_mapping |",
        "| ---- | --------: | --------------------: | -------------------: | -----------------: | --------------------: | ----------------------: |",
    ]
    for row in payload["active_dates"]:
        lines.append(
            f"| {row['date']} | {row['raw_trend_count']} | {row['confirmation_coverage_ratio']:.4f} | "
            f"{row['rs_vs_index_coverage_ratio']:.4f} | {row['rs_vs_etf_coverage_ratio']:.4f} | "
            f"{row['benchmark_etf_mapping_ratio']:.4f} | {row['benchmark_index_mapping_ratio']:.4f} |"
        )

    lines.extend(
        [
            "",
            "## 3. Unmapped Group Distribution",
            "",
            "| group | trend_signal_count | dates | current_mapping | suggested_action | suggested_benchmark | confidence |",
            "| ----- | -----------------: | ----- | --------------- | ---------------- | ------------------- | ---------- |",
        ]
    )
    for row in payload["unmapped_groups"][:20]:
        lines.append(
            f"| {row['group']} | {row['trend_signal_count']} | {','.join(row['dates'])} | "
            f"{row['current_mapping'] or '-'} | {row['suggested_action']} | "
            f"{row['suggested_benchmark_code'] or '-'} | {row['confidence']} |"
        )

    lines.extend(
        [
            "",
            "## 4. Unmapped Theme Cluster Distribution",
            "",
            "| theme_cluster | trend_signal_count | dates | current_mapping | suggested_action |",
            "| ------------- | -----------------: | ----- | --------------- | ---------------- |",
        ]
    )
    if payload["unmapped_theme_clusters"]:
        for row in payload["unmapped_theme_clusters"][:20]:
            lines.append(
                f"| {row['theme_cluster']} | {row['trend_signal_count']} | {','.join(row['dates'])} | "
                f"{row['current_mapping'] or '-'} | {row['suggested_action']} |"
            )
    else:
        lines.append("| - | 0 | - | - | - |")

    lines.extend(
        [
            "",
            "## 5. Top Mapping Gaps",
            "",
        ]
    )
    for row in payload["top_mapping_gaps"][:10]:
        lines.append(
            f"- {row['group']} | count={row['trend_signal_count']} | dates={','.join(row['dates'])} | "
            f"suggested={row['suggested_benchmark_code'] or 'manual_review'} | confidence={row['confidence']}"
        )

    lines.extend(
        [
            "",
            "## 6. Recommended Minimal Fixes",
            "",
        ]
    )
    for item in payload["recommended_minimal_fixes"]:
        lines.append(f"- {item}")
    if payload["refresh_results"]:
        lines.extend(
            [
                "",
                "## Confirmation Refresh",
                "",
            ]
        )
        for item in payload["refresh_results"]:
            lines.append(f"- {item}")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def parse_args():
    parser = argparse.ArgumentParser(description="Diagnose benchmark ETF mapping gaps for active trend dates.")
    parser.add_argument("--start", default="", help="Scan start date YYYYMMDD")
    parser.add_argument("--end", default="", help="Scan end date YYYYMMDD")
    parser.add_argument("--max-days", type=int, default=60, help="Maximum local trading days to scan")
    parser.add_argument("--dates", nargs="*", default=None, help="Specific dates to inspect")
    parser.add_argument("--refresh-confirmation", action="store_true", help="Rebuild confirmation CSVs from local intraday minute files before diagnosis")
    return parser.parse_args()


def main():
    configure_utf8_console()
    args = parse_args()
    if args.dates:
        days = sorted(int(day) for day in args.dates)
    else:
        days = _scan_days(start=args.start or None, end=args.end or None, max_days=args.max_days)
    payload = build_payload(days, refresh_confirmation=args.refresh_confirmation)
    json_path, md_path = write_outputs(payload)
    print(
        json.dumps(
            {
                "json": str(json_path.relative_to(ROOT)),
                "md": str(md_path.relative_to(ROOT)),
                "active_dates": [row["date"] for row in payload["active_dates"]],
                "top_mapping_gaps": payload["top_mapping_gaps"][:5],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
