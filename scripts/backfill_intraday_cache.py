# -*- coding: utf-8 -*-
"""Decoupled intraday cache backfill with minimal-universe mode and stage timing."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.auction import AuctionAnalyzer
from core.data_manager import DataManager
from core.intraday_confirmation import IntradayConfirmationBuilder
from scripts.diagnose_confirmation_coverage import inspect_day
from scripts.diagnose_intraday_cache_backfill import build_plan_payload, write_outputs as write_plan_outputs
from utils.encoding import configure_utf8_console

EVAL_DIR = ROOT / "reports" / "analysis" / "evaluations"
PROGRESS_PATH = EVAL_DIR / "intraday_backfill_progress.jsonl"


def load_plan_dates(plan_path: Path, limit: int = 0) -> List[int]:
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    rows = payload.get("recommended_backfill_batch", []) or payload.get("candidates", [])
    dates = [int(row["date"]) for row in rows if str(row.get("recommended_action", "")).startswith("backfill_")]
    if limit > 0:
        dates = dates[:limit]
    return dates


def _read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _date_output_paths(day: int) -> Dict[str, Path]:
    intraday_dir = ROOT / "AmazingData_Store" / str(int(day)) / "intraday"
    return {
        "intraday_dir": intraday_dir,
        "stocks": intraday_dir / "stocks_1min.csv",
        "etf": intraday_dir / "etf_1min.csv",
        "index": intraday_dir / "indices_1min.csv",
        "confirmation": intraday_dir / "stock_confirmation_latest.csv",
    }


def record_inspection(day: int, dm: DataManager, analyzer: AuctionAnalyzer, prefix: str) -> dict:
    row = inspect_day(day, analyzer, dm)
    return {
        f"{prefix}_coverage": float(row.get("confirmation_coverage_ratio", 0.0) or 0.0),
        f"{prefix}_main_failure": str(row.get("main_failure", "") or ""),
        f"{prefix}_raw_trend": int(row.get("raw_trend_count", 0) or 0),
        f"{prefix}_stock_trend": int(row.get("stock_trend_count", 0) or 0),
        f"{prefix}_status": str(row.get("trend_filter_status", "disabled") or "disabled"),
        f"{prefix}_signal_enriched_count": int(row.get("signal_enriched_count", 0) or 0),
    }


def resolve_minimal_universe(day: int, dm: DataManager) -> dict:
    analyzer = AuctionAnalyzer(dm)
    result = analyzer.analyze(int(day), realtime=False)
    signals = (result.get("signals") or {}).get("trend", []) or []
    stock_signals = [signal for signal in signals if ((signal.get("data") or {}).get("target_type") == "stock")]

    mapping = IntradayConfirmationBuilder._normalize_benchmark_map(IntradayConfirmationBuilder.load_benchmark_map())
    stock_codes = []
    etf_codes = set()
    index_codes = set()
    unmapped_groups = set()
    for signal in stock_signals:
        data = signal.get("data", {}) or {}
        code = str(data.get("code", "") or "")
        if code:
            stock_codes.append(code)
        group = IntradayConfirmationBuilder._normalize_group_key(data.get("group", ""))
        bench = mapping.get(group, {})
        etf_code = str(bench.get("benchmark_etf_code", "") or "")
        index_code = str(bench.get("benchmark_index_code", "") or "")
        if etf_code:
            etf_codes.add(etf_code)
        elif group:
            unmapped_groups.add(group)
        if index_code:
            index_codes.add(index_code)

    if not index_codes:
        index_codes.add(IntradayConfirmationBuilder.DEFAULT_INDEX_CODE)

    return {
        "source": "analyzer",
        "raw_trend_count": len(signals),
        "stock_trend_count": len(stock_signals),
        "stock_codes": sorted(set(stock_codes)),
        "etf_codes": sorted(etf_codes),
        "index_codes": sorted(index_codes),
        "unmapped_groups": sorted(unmapped_groups),
    }


def summarize_progress(progress_path: Path, dates: Iterable[int], start_index: int = 0) -> dict:
    wanted = {str(int(day)) for day in dates}
    rows = _read_jsonl(progress_path)[start_index:]
    rows = [row for row in rows if str(row.get("date", "")) in wanted]
    grouped: Dict[str, List[dict]] = {}
    for row in rows:
        grouped.setdefault(str(row["date"]), []).append(row)
    try:
        progress_path_text = str(progress_path.relative_to(ROOT)) if progress_path.exists() else str(progress_path)
    except ValueError:
        progress_path_text = str(progress_path)
    return {
        "progress_path": progress_path_text,
        "dates": sorted(grouped.keys()),
        "events": grouped,
    }


def write_timing_outputs(summary: dict) -> tuple[Path, Path]:
    json_path = EVAL_DIR / "intraday_backfill_timing.json"
    md_path = EVAL_DIR / "intraday_backfill_timing.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Intraday Backfill Timing",
        "",
        f"- progress_path: `{summary['progress_path']}`",
        "",
    ]
    for date in summary["dates"]:
        lines.append(f"## {date}")
        lines.append("")
        lines.append("| stage | status | elapsed_sec | code_count | row_count | warning | error |")
        lines.append("| --- | --- | ---: | ---: | ---: | --- | --- |")
        for row in summary["events"].get(date, []):
            lines.append(
                f"| {row.get('stage','')} | {row.get('status','')} | {float(row.get('elapsed_sec', 0.0) or 0.0):.4f} | "
                f"{int(row.get('code_count', 0) or 0)} | {int(row.get('row_count', 0) or 0)} | "
                f"{row.get('warning', '') or '-'} | {row.get('error', '') or '-'} |"
            )
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def run_backfill(
    dates: Iterable[int],
    execute: bool,
    force: bool,
    mode: str,
    data_kind: str,
    pre_inspect: bool,
    post_validate: bool,
    warn_after_sec: Optional[float],
) -> dict:
    dm = DataManager()
    analyzer = AuctionAnalyzer(dm)
    records = []
    existing_progress_count = len(_read_jsonl(PROGRESS_PATH))

    for day in [int(d) for d in dates]:
        outputs = _date_output_paths(day)
        existed_before = {key: path.exists() for key, path in outputs.items()}
        universe = resolve_minimal_universe(day, dm) if mode == "minimal" else {
            "source": "full",
            "raw_trend_count": None,
            "stock_trend_count": None,
            "stock_codes": [],
            "etf_codes": [],
            "index_codes": [],
            "unmapped_groups": [],
        }

        record = {
            "date": str(day),
            "execute": execute,
            "force": force,
            "mode": mode,
            "data_kind": data_kind,
            "warn_after_sec": warn_after_sec,
            "output_exists_before": existed_before,
            "universe": universe,
        }

        if pre_inspect:
            record.update(record_inspection(day, dm, analyzer, "before"))

        if execute:
            result = dm.rebuild_intraday_confirmation_from_snapshot(
                day,
                force=force,
                stock_codes=universe["stock_codes"] if mode == "minimal" else None,
                etf_codes=universe["etf_codes"] if mode == "minimal" else None,
                index_codes=universe["index_codes"] if mode == "minimal" else None,
                mode=mode,
                data_kind=data_kind,
                warn_after_sec=warn_after_sec,
                progress_path=str(PROGRESS_PATH),
            )
        else:
            result = {
                "rebuilt": False,
                "skipped": True,
                "reason": "dry_run",
                "date": day,
                "mode": mode,
                "data_kind": data_kind,
            }

        record["result"] = result
        record["stock_file_exists_after"] = outputs["stocks"].exists()
        record["etf_file_exists_after"] = outputs["etf"].exists()
        record["index_file_exists_after"] = outputs["index"].exists()
        record["confirmation_file_exists_after"] = outputs["confirmation"].exists()

        if post_validate:
            record.update(record_inspection(day, dm, analyzer, "after"))

        records.append(record)

    timing_summary = summarize_progress(PROGRESS_PATH, dates, start_index=existing_progress_count)
    timing_json, timing_md = write_timing_outputs(timing_summary)
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "execute": execute,
        "force": force,
        "mode": mode,
        "data_kind": data_kind,
        "pre_inspect": pre_inspect,
        "post_validate": post_validate,
        "warn_after_sec": warn_after_sec,
        "dates": [str(int(d)) for d in dates],
        "records": records,
        "progress_path": str(PROGRESS_PATH.relative_to(ROOT)),
        "timing_json": str(timing_json.relative_to(ROOT)),
        "timing_md": str(timing_md.relative_to(ROOT)),
    }


def write_result(payload: dict) -> tuple[Path, Path]:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    json_path = EVAL_DIR / "intraday_cache_backfill_result.json"
    md_path = EVAL_DIR / "intraday_cache_backfill_result.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Intraday Cache Backfill Result",
        "",
        f"- created_at: `{payload['created_at']}`",
        f"- execute: `{payload['execute']}`",
        f"- force: `{payload['force']}`",
        f"- mode: `{payload['mode']}`",
        f"- data_kind: `{payload['data_kind']}`",
        f"- pre_inspect: `{payload['pre_inspect']}`",
        f"- post_validate: `{payload['post_validate']}`",
        f"- warn_after_sec: `{payload['warn_after_sec']}`",
        f"- progress_path: `{payload['progress_path']}`",
        f"- timing_json: `{payload['timing_json']}`",
        f"- timing_md: `{payload['timing_md']}`",
        f"- dates: `{', '.join(payload['dates'])}`",
        "",
        "| date | before_coverage | after_coverage | filter_status | main_failure | universe(stk/etf/idx) | note |",
        "| ---- | --------------: | -------------: | ------------- | ------------ | --------------------: | ---- |",
    ]
    for row in payload["records"]:
        note = row["result"].get("reason", "") if isinstance(row.get("result"), dict) else ""
        before_coverage = row.get("before_coverage", "")
        after_coverage = row.get("after_coverage", "")
        before_status = row.get("before_status", "")
        after_status = row.get("after_status", before_status)
        failure = row.get("after_main_failure", row.get("before_main_failure", ""))
        universe = row.get("universe", {}) or {}
        universe_text = f"{len(universe.get('stock_codes', []))}/{len(universe.get('etf_codes', []))}/{len(universe.get('index_codes', []))}"
        lines.append(
            f"| {row['date']} | {before_coverage if before_coverage != '' else '-'} | "
            f"{after_coverage if after_coverage != '' else '-'} | {after_status or before_status or '-'} | "
            f"{failure or '-'} | {universe_text} | {note or '-'} |"
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def parse_args():
    parser = argparse.ArgumentParser(description="Decoupled intraday cache backfill for replay confirmation.")
    parser.add_argument("--dates", nargs="*", default=[], help="Explicit trade dates YYYYMMDD")
    parser.add_argument("--plan", default="", help="Optional backfill plan json")
    parser.add_argument("--limit", type=int, default=0, help="Max dates to consume from plan")
    parser.add_argument("--execute", action="store_true", help="Actually rebuild missing intraday confirmation files")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing confirmation outputs")
    parser.add_argument("--plan-only", action="store_true", help="Only emit/update the backfill plan files")
    parser.add_argument("--mode", choices=["minimal", "full"], default="minimal", help="Universe scope for backfill")
    parser.add_argument("--data-kind", default="min1", help="Data kind: min1 or snapshot,min1")
    parser.add_argument("--pre-inspect", dest="pre_inspect", action="store_true", help="Run local inspect_day before execute")
    parser.add_argument("--no-pre-inspect", dest="pre_inspect", action="store_false", help="Disable local inspect_day before execute")
    parser.add_argument("--post-validate", dest="post_validate", action="store_true", help="Run local inspect_day after execute")
    parser.add_argument("--no-post-validate", dest="post_validate", action="store_false", help="Disable local inspect_day after execute")
    parser.add_argument("--warn-after-sec", type=float, default=120.0, help="Soft warning threshold for each remote stage")
    parser.set_defaults(pre_inspect=False, post_validate=False)
    return parser.parse_args()


def main():
    configure_utf8_console()
    args = parse_args()
    dates: List[int] = [int(item) for item in args.dates]
    if args.plan:
        dates.extend(load_plan_dates(Path(args.plan), limit=args.limit))
    dates = sorted({int(day) for day in dates})

    if args.plan_only:
        if not dates:
            raise SystemExit("No dates provided. Use --dates or --plan with --plan-only.")
        payload = build_plan_payload(dates)
        json_path, md_path = write_plan_outputs(payload)
        print(
            json.dumps(
                {
                    "json": str(json_path.relative_to(ROOT)),
                    "md": str(md_path.relative_to(ROOT)),
                    "plan_only": True,
                    "dates": [str(int(day)) for day in dates],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if not dates:
        raise SystemExit("No dates provided. Use --dates or --plan.")

    payload = run_backfill(
        dates=dates,
        execute=args.execute,
        force=args.force,
        mode=args.mode,
        data_kind=args.data_kind,
        pre_inspect=args.pre_inspect,
        post_validate=args.post_validate,
        warn_after_sec=args.warn_after_sec,
    )
    json_path, md_path = write_result(payload)
    print(
        json.dumps(
            {
                "json": str(json_path.relative_to(ROOT)),
                "md": str(md_path.relative_to(ROOT)),
                "execute": payload["execute"],
                "mode": payload["mode"],
                "data_kind": payload["data_kind"],
                "pre_inspect": payload["pre_inspect"],
                "post_validate": payload["post_validate"],
                "dates": payload["dates"],
                "progress_path": payload["progress_path"],
                "timing_json": payload["timing_json"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
