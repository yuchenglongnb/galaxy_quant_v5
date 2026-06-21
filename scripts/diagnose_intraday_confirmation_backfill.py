# -*- coding: utf-8 -*-
"""Diagnose the minimal replay universe needed for intraday confirmation backfill."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.auction import AuctionAnalyzer
from core.data_manager import DataManager
from scripts.backfill_intraday_cache import resolve_minimal_universe
from utils.encoding import configure_utf8_console

EVAL_DIR = ROOT / "reports" / "analysis" / "evaluations"


def _load_codes(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        frame = pd.read_csv(path, dtype={"code": str}, encoding="utf-8-sig")
    except UnicodeDecodeError:
        frame = pd.read_csv(path, dtype={"code": str}, encoding="gb18030")
    if "code" not in frame.columns:
        return []
    return sorted({str(code) for code in frame["code"].fillna("").astype(str) if code})


def build_payload(target_date: int) -> dict:
    dm = DataManager()
    analyzer = AuctionAnalyzer(dm)
    result = analyzer.analyze(int(target_date), realtime=False)
    if result is None:
        raise RuntimeError(f"analyze returned None for {target_date}")

    universe = resolve_minimal_universe(int(target_date), dm)
    intraday_dir = ROOT / "AmazingData_Store" / str(int(target_date)) / "intraday"
    stock_path = intraday_dir / "stocks_1min.csv"
    etf_path = intraday_dir / "etf_1min.csv"
    index_path = intraday_dir / "indices_1min.csv"
    confirmation_path = intraday_dir / "stock_confirmation_latest.csv"

    existing_stock_codes = _load_codes(stock_path)
    existing_etf_codes = _load_codes(etf_path)
    existing_index_codes = _load_codes(index_path)

    needed_stock_codes = universe.get("stock_codes", [])
    needed_benchmark_etf_codes = universe.get("etf_codes", [])
    needed_benchmark_index_codes = universe.get("index_codes", [])
    board_index_codes_used = universe.get("board_index_codes", [])

    trend_signals = list(((result.get("signals") or {}).get("trend")) or [])
    stock_trend_total = sum(
        1 for signal in trend_signals if ((signal.get("data") or {}).get("target_type") == "stock")
    )

    return {
        "date": str(int(target_date)),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "trend_total": len(trend_signals),
        "stock_trend_total": stock_trend_total,
        "needed_stock_codes": needed_stock_codes,
        "needed_benchmark_etf_codes": needed_benchmark_etf_codes,
        "needed_benchmark_index_codes": needed_benchmark_index_codes,
        "board_index_codes_used": board_index_codes_used,
        "board_index_fallback_attached_count": int(universe.get("board_index_fallback_attached_count", 0) or 0),
        "board_index_fallback_coverage": round(
            float(universe.get("board_index_fallback_attached_count", 0) or 0) / float(stock_trend_total or 1),
            4,
        ),
        "intraday_dir_exists": intraday_dir.exists(),
        "existing_files": {
            "stocks_1min.csv": stock_path.exists(),
            "etf_1min.csv": etf_path.exists(),
            "indices_1min.csv": index_path.exists(),
            "stock_confirmation_latest.csv": confirmation_path.exists(),
        },
        "existing_stock_intraday_count": len(existing_stock_codes),
        "existing_benchmark_etf_intraday_count": len(existing_etf_codes),
        "existing_benchmark_index_intraday_count": len(existing_index_codes),
        "missing_stock_intraday_count": len([code for code in needed_stock_codes if code not in existing_stock_codes]),
        "missing_benchmark_etf_intraday_count": len(
            [code for code in needed_benchmark_etf_codes if code not in existing_etf_codes]
        ),
        "missing_benchmark_index_intraday_count": len(
            [code for code in needed_benchmark_index_codes if code not in existing_index_codes]
        ),
        "expected_confirmation_rows": stock_trend_total,
        "current_confirmation_available": confirmation_path.exists(),
    }


def write_outputs(payload: dict) -> tuple[Path, Path]:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    json_path = EVAL_DIR / f"intraday_confirmation_backfill_{payload['date']}.json"
    md_path = EVAL_DIR / f"intraday_confirmation_backfill_{payload['date']}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Intraday Confirmation Backfill Diagnosis {payload['date']}",
        "",
        "## Core Status",
        "",
        f"- trend_total: `{payload['trend_total']}`",
        f"- stock_trend_total: `{payload['stock_trend_total']}`",
        f"- intraday_dir_exists: `{payload['intraday_dir_exists']}`",
        f"- current_confirmation_available: `{payload['current_confirmation_available']}`",
        f"- board_index_fallback_attached_count: `{payload['board_index_fallback_attached_count']}`",
        f"- board_index_fallback_coverage: `{payload['board_index_fallback_coverage']}`",
        f"- board_index_codes_used: `{payload['board_index_codes_used']}`",
        "",
        "## Existing Files",
        "",
        "| file | exists |",
        "| --- | --- |",
    ]
    for name, exists in payload["existing_files"].items():
        lines.append(f"| {name} | {exists} |")

    lines.extend(
        [
            "",
            "## Universe Summary",
            "",
            f"- needed_stock_codes: `{len(payload['needed_stock_codes'])}`",
            f"- needed_benchmark_etf_codes: `{len(payload['needed_benchmark_etf_codes'])}`",
            f"- needed_benchmark_index_codes: `{len(payload['needed_benchmark_index_codes'])}`",
            f"- expected_confirmation_rows: `{payload['expected_confirmation_rows']}`",
            "",
            "## Missing Cache Counts",
            "",
            f"- missing_stock_intraday_count: `{payload['missing_stock_intraday_count']}`",
            f"- missing_benchmark_etf_intraday_count: `{payload['missing_benchmark_etf_intraday_count']}`",
            f"- missing_benchmark_index_intraday_count: `{payload['missing_benchmark_index_intraday_count']}`",
        ]
    )

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def parse_args():
    parser = argparse.ArgumentParser(description="Diagnose intraday confirmation backfill scope for a replay date.")
    parser.add_argument("--date", required=True, help="Replay trade date YYYYMMDD")
    return parser.parse_args()


def main():
    configure_utf8_console()
    args = parse_args()
    payload = build_payload(int(args.date))
    json_path, md_path = write_outputs(payload)
    print(
        json.dumps(
            {
                "json": str(json_path.relative_to(ROOT)),
                "md": str(md_path.relative_to(ROOT)),
                "trend_total": payload["trend_total"],
                "stock_trend_total": payload["stock_trend_total"],
                "missing_stock_intraday_count": payload["missing_stock_intraday_count"],
                "missing_benchmark_etf_intraday_count": payload["missing_benchmark_etf_intraday_count"],
                "missing_benchmark_index_intraday_count": payload["missing_benchmark_index_intraday_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
