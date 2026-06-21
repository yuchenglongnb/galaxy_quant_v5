# -*- coding: utf-8 -*-
"""Replay-date intraday confirmation backfill with dry-run and execute modes."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.data_manager import DataManager
from scripts.backfill_intraday_cache import resolve_minimal_universe
from scripts.diagnose_intraday_confirmation_backfill import build_payload as build_diag_payload
from scripts.diagnose_trend_gate_coverage import build_payload as build_trend_payload
from utils.encoding import configure_utf8_console

EVAL_DIR = ROOT / "reports" / "analysis" / "evaluations"


def _written_files(target_date: int) -> list[str]:
    intraday_dir = ROOT / "AmazingData_Store" / str(int(target_date)) / "intraday"
    files = []
    for name in ("stocks_1min.csv", "etf_1min.csv", "indices_1min.csv", "stock_confirmation_latest.csv"):
        path = intraday_dir / name
        if path.exists():
            files.append(str(path.relative_to(ROOT)))
    return files


def run_backfill(target_date: int, execute: bool, force: bool) -> dict:
    dm = DataManager()
    universe = resolve_minimal_universe(int(target_date), dm)
    before = build_diag_payload(int(target_date))

    result = {
        "date": str(int(target_date)),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "execute": bool(execute),
        "force": bool(force),
        "dry_run": not bool(execute),
        "universe": universe,
        "before": before,
        "rebuild_result": {
            "rebuilt": False,
            "skipped": True,
            "reason": "dry_run",
        },
        "written_files": [],
        "after_confirmation_available": before["current_confirmation_available"],
        "after_signal_enriched_count": 0,
        "after_rs_vs_etf_coverage": 0.0,
        "after_rs_vs_index_coverage": 0.0,
        "after_amount_1m_ratio_coverage": 0.0,
        "after_shadow_distribution": {},
    }

    if execute:
        rebuild = dm.rebuild_intraday_confirmation_from_snapshot(
            int(target_date),
            force=force,
            stock_codes=universe.get("stock_codes") or None,
            etf_codes=universe.get("etf_codes") or None,
            index_codes=universe.get("index_codes") or None,
            mode="minimal",
            data_kind="min1",
        )
        result["rebuild_result"] = rebuild
        result["written_files"] = _written_files(int(target_date))
        after_diag = build_diag_payload(int(target_date))
        after_trend = build_trend_payload(int(target_date))
        result["after"] = after_diag
        result["after_confirmation_available"] = after_diag["current_confirmation_available"]
        result["after_signal_enriched_count"] = int(
            ((after_trend.get("intraday_confirmation_status") or {}).get("signal_enriched_count", 0) or 0)
        )
        overall = after_trend.get("overall_coverage", {}) or {}
        result["after_rs_vs_etf_coverage"] = float(overall.get("rs_vs_etf_coverage", 0.0) or 0.0)
        result["after_rs_vs_index_coverage"] = float(overall.get("rs_vs_index_coverage", 0.0) or 0.0)
        result["after_amount_1m_ratio_coverage"] = float(overall.get("amount_1m_ratio_coverage", 0.0) or 0.0)
        result["after_shadow_distribution"] = dict(overall.get("shadow_distribution", {}) or {})

    return result


def write_outputs(payload: dict) -> tuple[Path, Path]:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "execute" if payload["execute"] else "dry_run"
    json_path = EVAL_DIR / f"intraday_confirmation_backfill_{payload['date']}_{suffix}.json"
    md_path = EVAL_DIR / f"intraday_confirmation_backfill_{payload['date']}_{suffix}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Intraday Confirmation Backfill {payload['date']}",
        "",
        f"- execute: `{payload['execute']}`",
        f"- dry_run: `{payload['dry_run']}`",
        f"- force: `{payload['force']}`",
        "",
        "## Before",
        "",
        f"- stock_trend_total: `{payload['before']['stock_trend_total']}`",
        f"- current_confirmation_available: `{payload['before']['current_confirmation_available']}`",
        f"- missing_stock_intraday_count: `{payload['before']['missing_stock_intraday_count']}`",
        f"- missing_benchmark_etf_intraday_count: `{payload['before']['missing_benchmark_etf_intraday_count']}`",
        f"- missing_benchmark_index_intraday_count: `{payload['before']['missing_benchmark_index_intraday_count']}`",
        f"- board_index_codes_used: `{payload['before']['board_index_codes_used']}`",
        "",
        "## Rebuild Result",
        "",
        f"- result: `{payload['rebuild_result']}`",
        f"- written_files: `{payload['written_files']}`",
        "",
        "## After",
        "",
        f"- after_confirmation_available: `{payload['after_confirmation_available']}`",
        f"- after_signal_enriched_count: `{payload['after_signal_enriched_count']}`",
        f"- after_rs_vs_etf_coverage: `{payload['after_rs_vs_etf_coverage']}`",
        f"- after_rs_vs_index_coverage: `{payload['after_rs_vs_index_coverage']}`",
        f"- after_amount_1m_ratio_coverage: `{payload['after_amount_1m_ratio_coverage']}`",
        f"- after_shadow_distribution: `{payload['after_shadow_distribution']}`",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def parse_args():
    parser = argparse.ArgumentParser(description="Backfill replay-date intraday confirmation cache.")
    parser.add_argument("--date", required=True, help="Replay trade date YYYYMMDD")
    parser.add_argument("--execute", action="store_true", help="Actually write local intraday cache and confirmation files")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing intraday outputs")
    return parser.parse_args()


def main():
    configure_utf8_console()
    args = parse_args()
    payload = run_backfill(int(args.date), execute=args.execute, force=args.force)
    json_path, md_path = write_outputs(payload)
    print(
        json.dumps(
            {
                "json": str(json_path.relative_to(ROOT)),
                "md": str(md_path.relative_to(ROOT)),
                "execute": payload["execute"],
                "dry_run": payload["dry_run"],
                "written_files": payload["written_files"],
                "after_confirmation_available": payload["after_confirmation_available"],
                "after_signal_enriched_count": payload["after_signal_enriched_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
