# -*- coding: utf-8 -*-
"""Build a replay-oriented intraday cache backfill plan from local coverage gaps."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.diagnose_confirmation_coverage import build_payload as build_coverage_payload
from scripts.diagnose_confirmation_coverage import scan_days as scan_coverage_days
from utils.encoding import configure_utf8_console

EVAL_DIR = ROOT / "reports" / "analysis" / "evaluations"


def classify_missing_type(row: dict) -> str:
    if row.get("raw_trend_count", 0) == 0:
        return "no_trend_signals"
    if not row.get("intraday_dir_exists", False):
        return "intraday_cache_missing"

    stock_exists = bool(row.get("stock_file_exists", False))
    etf_exists = bool(row.get("etf_file_exists", False))
    index_exists = bool(row.get("index_file_exists", False))

    missing = []
    if not stock_exists:
        missing.append("stock")
    if not etf_exists:
        missing.append("etf")
    if not index_exists:
        missing.append("index")

    if not missing:
        if row.get("confirmation_coverage_ratio", 0.0) > 0:
            return "coverage_available"
        return "unknown"
    if len(missing) == 1:
        return f"{missing[0]}_intraday_missing"
    return "partial_intraday_missing"


def recommend_action(row: dict, missing_type: str) -> str:
    if missing_type == "no_trend_signals":
        return "skip_no_trend"
    if missing_type == "coverage_available":
        return "skip_coverage_available"
    if missing_type == "intraday_cache_missing":
        return "backfill_all_intraday"
    if missing_type == "stock_intraday_missing":
        return "backfill_stock_only"
    if missing_type == "etf_intraday_missing":
        return "backfill_etf_only"
    if missing_type == "index_intraday_missing":
        return "backfill_index_only"
    if missing_type == "partial_intraday_missing":
        return "backfill_all_intraday"
    return "manual_check"


def compute_priority(row: dict, missing_type: str) -> int:
    score = 0
    if row.get("raw_trend_count", 0) > 0:
        score += min(int(row.get("raw_trend_count", 0)), 100)
    if row.get("stock_trend_count", 0) > 0:
        score += min(int(row.get("stock_trend_count", 0)), 50)
    if row.get("main_failure") == "intraday_cache_missing":
        score += 40
    elif "missing" in missing_type:
        score += 20
    if row.get("confirmation_coverage_ratio", 0.0) == 0.0:
        score += 10
    if row.get("trend_filter_status") == "degraded_global_missing":
        score += 5
    return score


def _has_daily_dir(date_dir: Path) -> bool:
    return (date_dir / "stocks.csv").exists() and (date_dir / "indices.csv").exists()


def _has_auction_dir(date_dir: Path) -> bool:
    return (date_dir / "stocks_auction.csv").exists() and (date_dir / "indices_auction.csv").exists()


def build_plan_candidates(coverage_payload: dict) -> List[dict]:
    candidates: List[dict] = []
    for row in coverage_payload.get("daily", []):
        date = str(row["date"])
        date_dir = ROOT / "AmazingData_Store" / date
        missing_type = classify_missing_type(row)
        recommended_action = recommend_action(row, missing_type)
        priority = compute_priority(row, missing_type)
        candidates.append(
            {
                "date": date,
                "has_daily": _has_daily_dir(date_dir),
                "has_auction": _has_auction_dir(date_dir),
                "raw_trend_count": int(row.get("raw_trend_count", 0) or 0),
                "stock_trend_count": int(row.get("stock_trend_count", 0) or 0),
                "intraday_dir_exists": bool(row.get("intraday_dir_exists", False)),
                "stock_intraday_exists": bool(row.get("stock_file_exists", False)),
                "etf_intraday_exists": bool(row.get("etf_file_exists", False)),
                "index_intraday_exists": bool(row.get("index_file_exists", False)),
                "current_confirmation_coverage_ratio": float(row.get("confirmation_coverage_ratio", 0.0) or 0.0),
                "trend_filter_status": str(row.get("trend_filter_status", "disabled") or "disabled"),
                "main_failure": str(row.get("main_failure", "") or ""),
                "missing_type": missing_type,
                "recommended_action": recommended_action,
                "priority": priority,
            }
        )
    return candidates


def build_plan_payload(days: List[int]) -> dict:
    coverage_payload = build_coverage_payload(days)
    candidates = build_plan_candidates(coverage_payload)
    missing_distribution = Counter(item["missing_type"] for item in candidates)
    recommended_batch = [
        item
        for item in sorted(candidates, key=lambda row: (-row["priority"], row["date"]))
        if item["recommended_action"].startswith("backfill_")
        and item["has_daily"]
        and item["has_auction"]
        and item["raw_trend_count"] > 0
    ]

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scope": coverage_payload.get("scope", {}),
        "coverage_failure_distribution": coverage_payload.get("failure_distribution", {}),
        "candidates": candidates,
        "missing_type_distribution": dict(missing_distribution),
        "recommended_backfill_batch": recommended_batch[:8],
    }


def write_outputs(payload: dict) -> Tuple[Path, Path]:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    json_path = EVAL_DIR / "intraday_cache_backfill_plan.json"
    md_path = EVAL_DIR / "intraday_cache_backfill_plan.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Intraday Cache Backfill Plan",
        "",
        "## 1. Scope",
        "",
        f"- start: `{payload['scope'].get('start', '')}`",
        f"- end: `{payload['scope'].get('end', '')}`",
        f"- days_scanned: `{payload['scope'].get('days_scanned', 0)}`",
        "",
        "## 2. Backfill Candidate Summary",
        "",
        "| date | has_daily | has_auction | raw_trend | intraday_dir | stock_intraday | etf_intraday | index_intraday | current_coverage | missing_type | recommended_action |",
        "| ---- | --------- | ----------- | --------: | ------------ | -------------- | ------------ | -------------- | ---------------: | ------------ | ------------------ |",
    ]
    for row in payload["candidates"]:
        lines.append(
            f"| {row['date']} | {row['has_daily']} | {row['has_auction']} | {row['raw_trend_count']} | "
            f"{row['intraday_dir_exists']} | {row['stock_intraday_exists']} | {row['etf_intraday_exists']} | "
            f"{row['index_intraday_exists']} | {row['current_confirmation_coverage_ratio']:.4f} | "
            f"{row['missing_type']} | {row['recommended_action']} |"
        )

    lines.extend(
        [
            "",
            "## 3. Missing Type Distribution",
            "",
            "| missing_type | count |",
            "| ------------ | ----: |",
        ]
    )
    for key, count in sorted(payload["missing_type_distribution"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {key} | {count} |")

    lines.extend(
        [
            "",
            "## 4. Recommended Backfill Batch",
            "",
        ]
    )
    if payload["recommended_backfill_batch"]:
        for row in payload["recommended_backfill_batch"]:
            lines.append(
                f"- `{row['date']}` | priority={row['priority']} | raw_trend={row['raw_trend_count']} | "
                f"missing_type={row['missing_type']} | action={row['recommended_action']}"
            )
    else:
        lines.append("- 暂无满足条件的回补候选。")

    lines.extend(
        [
            "",
            "## 5. Expected Validation",
            "",
            "- 回补后重新运行 `scripts/diagnose_confirmation_coverage.py`，确认 confirmation_coverage_ratio 是否提升。",
            "- 回补后重新运行 `scripts/diagnose_benchmark_mapping.py`，确认 benchmark ETF / index 映射在 active 日期中是否被实际消费。",
            "- 回补后重新运行 `scripts/evaluate_trend_filter.py`，确认 keep / observe / drop 是否从 data-missing-driven 转向 rule-driven。",
        ]
    )

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def parse_args():
    parser = argparse.ArgumentParser(description="Build an intraday cache backfill plan for replay confirmation.")
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
        days = scan_coverage_days(start=args.start or None, end=args.end or None, max_days=args.max_days)
    payload = build_plan_payload(days)
    json_path, md_path = write_outputs(payload)
    print(
        json.dumps(
            {
                "json": str(json_path.relative_to(ROOT)),
                "md": str(md_path.relative_to(ROOT)),
                "days_scanned": payload["scope"].get("days_scanned", 0),
                "missing_type_distribution": payload["missing_type_distribution"],
                "recommended_backfill_dates": [row["date"] for row in payload["recommended_backfill_batch"]],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
