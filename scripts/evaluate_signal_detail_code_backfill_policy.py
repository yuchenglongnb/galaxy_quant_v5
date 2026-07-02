# -*- coding: utf-8 -*-
"""Evaluate historical signal_detail code backfill policy without editing files."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.encoding import configure_utf8_console  # noqa: E402


EVAL_ROOT = ROOT / "reports" / "analysis" / "evaluations"
REPORTS_DAILY = ROOT / "reports" / "validation" / "daily"
STORE_ROOT = ROOT / "AmazingData_Store"


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _date_range(start: str, end: str) -> list[str]:
    cur = datetime.strptime(start, "%Y%m%d").date()
    last = datetime.strptime(end, "%Y%m%d").date()
    days = []
    while cur <= last:
        days.append(cur.strftime("%Y%m%d"))
        cur += timedelta(days=1)
    return days


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str, "date": str})
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _add_mapping(mapping: dict, name: str, code: str, source: str):
    if not name or not code or str(code).lower() in {"nan", "none", "null"}:
        return
    entry = mapping.setdefault(str(name), defaultdict(set))
    entry[str(code)].add(source)


def build_name_code_map(date: str) -> tuple[dict[str, dict], list[str]]:
    mapping: dict = {}
    source_paths = []
    sources = [
        REPORTS_DAILY / date / "factor_snapshot_stock.csv",
        REPORTS_DAILY / date / "factor_snapshot_etf.csv",
        REPORTS_DAILY / date / "factor_snapshot_index.csv",
        REPORTS_DAILY / date / "factor_snapshot_industry_topk.csv",
        STORE_ROOT / date / "factor_snapshot.csv",
        STORE_ROOT / date / "factor_snapshot_stock.csv",
        STORE_ROOT / date / "factor_snapshot_etf.csv",
        STORE_ROOT / date / "factor_snapshot_index.csv",
        STORE_ROOT / date / "factor_snapshot_industry_topk.csv",
        STORE_ROOT / date / "stocks.csv",
        STORE_ROOT / date / "indices.csv",
    ]
    for path in sources:
        frame = read_csv(path)
        if frame.empty or "name" not in frame.columns or "code" not in frame.columns:
            continue
        source_paths.append(_display_path(path))
        for _, row in frame.iterrows():
            _add_mapping(mapping, row.get("name"), row.get("code"), _display_path(path))
    normalized = {}
    for name, code_sources in mapping.items():
        normalized[name] = {
            "codes": sorted(code_sources.keys()),
            "sources": {code: sorted(sources) for code, sources in code_sources.items()},
        }
    return normalized, sorted(source_paths)


def analyze_date(date: str) -> dict:
    detail_path = REPORTS_DAILY / date / "signal_detail.csv"
    detail = read_csv(detail_path)
    mapping, source_files = build_name_code_map(date)
    has_code = "code" in detail.columns
    native_code_count = 0
    backfillable = 0
    unfilled = 0
    fallback = 0
    ambiguous = 0
    fill_methods = Counter()
    if detail.empty:
        return {
            "date": date,
            "signal_detail_path": _display_path(detail_path),
            "signal_detail_exists": detail_path.exists(),
            "signal_detail_has_code": has_code,
            "signal_rows": 0,
            "native_code_count": 0,
            "backfillable_code_count": 0,
            "unfilled_count": 0,
            "name_fallback_count": 0,
            "ambiguous_name_count": 0,
            "source_files": source_files,
            "fill_method_counts": {},
            "temp_backfill_copy_recommended": False,
            "warnings": ["signal_detail_empty_or_missing"],
        }
    for _, row in detail.iterrows():
        code = str(row.get("code", "") or "").strip() if has_code else ""
        if code and code.lower() not in {"nan", "none", "null"}:
            native_code_count += 1
            fill_methods["native_code"] += 1
            continue
        name = str(row.get("name", "") or "")
        candidates = mapping.get(name, {}).get("codes", [])
        if len(candidates) == 1:
            backfillable += 1
            fallback += 1
            fill_methods["backfillable_from_name_code_map"] += 1
        elif len(candidates) > 1:
            ambiguous += 1
            fill_methods["ambiguous_name"] += 1
        else:
            unfilled += 1
            fill_methods["unfilled"] += 1
    return {
        "date": date,
        "signal_detail_path": _display_path(detail_path),
        "signal_detail_exists": detail_path.exists(),
        "signal_detail_has_code": has_code,
        "signal_rows": int(len(detail)),
        "native_code_count": int(native_code_count),
        "backfillable_code_count": int(backfillable),
        "unfilled_count": int(unfilled),
        "name_fallback_count": int(fallback),
        "ambiguous_name_count": int(ambiguous),
        "source_files": source_files,
        "fill_method_counts": dict(fill_methods),
        "temp_backfill_copy_recommended": bool(backfillable or ambiguous or unfilled),
        "warnings": [],
    }


def build_payload(start_date: str, end_date: str) -> dict:
    daily = [analyze_date(date) for date in _date_range(start_date, end_date)]
    totals = Counter()
    for row in daily:
        totals["signal_rows"] += row["signal_rows"]
        totals["native_code_count"] += row["native_code_count"]
        totals["backfillable_code_count"] += row["backfillable_code_count"]
        totals["unfilled_count"] += row["unfilled_count"]
        totals["name_fallback_count"] += row["name_fallback_count"]
        totals["ambiguous_name_count"] += row["ambiguous_name_count"]
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "date_range": {"start": start_date, "end": end_date},
        "daily_policy_analysis": daily,
        "total_signal_rows": int(totals["signal_rows"]),
        "native_code_count": int(totals["native_code_count"]),
        "backfillable_code_count": int(totals["backfillable_code_count"]),
        "unfilled_count": int(totals["unfilled_count"]),
        "name_fallback_count": int(totals["name_fallback_count"]),
        "ambiguous_name_count": int(totals["ambiguous_name_count"]),
        "recommended_primary_key": "code",
        "fallback_key": "name",
        "temp_backfill_copy_recommended": bool(totals["backfillable_code_count"] or totals["unfilled_count"] or totals["ambiguous_name_count"]),
        "original_files_modified": False,
        "strategy_rule_change_required": False,
        "cp_evaluator_change_required": False,
        "trend_evaluator_change_required": False,
        "recommended_next_actions": [
            "generate_backfilled_temp_signal_detail_copies_before_any_historical_overwrite",
            "use_code_as_primary_t1_join_key",
            "keep_name_fallback_explicitly_counted",
            "review_unfilled_and_ambiguous_names_manually",
        ],
        "warnings": ["original_signal_detail_files_not_modified"],
        "conclusion": [
            "code_keyed_join_required",
            "historical_signal_detail_code_backfill_policy_required",
            "original_file_not_modified",
            "no_strategy_rule_change",
            "cp_evaluator_change_not_required",
            "trend_evaluator_change_not_required",
            "lesson_pattern_not_written",
        ],
    }


def write_reports(payload: dict) -> tuple[Path, Path]:
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    start = payload["date_range"]["start"]
    end = payload["date_range"]["end"]
    stem = f"signal_detail_code_backfill_policy_{start}_{end}"
    json_path = EVAL_ROOT / f"{stem}.json"
    md_path = EVAL_ROOT / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def render_markdown(payload: dict) -> str:
    lines = [
        f"# Signal Detail Code Backfill Policy {payload['date_range']['start']} -> {payload['date_range']['end']}",
        "",
        f"- total_signal_rows: `{payload['total_signal_rows']}`",
        f"- native_code_count: `{payload['native_code_count']}`",
        f"- backfillable_code_count: `{payload['backfillable_code_count']}`",
        f"- unfilled_count: `{payload['unfilled_count']}`",
        f"- name_fallback_count: `{payload['name_fallback_count']}`",
        f"- ambiguous_name_count: `{payload['ambiguous_name_count']}`",
        f"- original_files_modified: `{payload['original_files_modified']}`",
        "",
        "## Daily",
        "",
    ]
    for row in payload["daily_policy_analysis"]:
        lines.append(
            f"- {row['date']}: rows={row['signal_rows']}, native={row['native_code_count']}, "
            f"backfillable={row['backfillable_code_count']}, unfilled={row['unfilled_count']}, "
            f"ambiguous={row['ambiguous_name_count']}"
        )
    lines.extend(["", "## Conclusion", ""])
    lines.extend(f"- {item}" for item in payload["conclusion"])
    return "\n".join(lines) + "\n"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate historical signal_detail code backfill policy.")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    return parser.parse_args(argv)


def main(argv=None):
    configure_utf8_console()
    args = parse_args(argv)
    payload = build_payload(args.start_date, args.end_date)
    json_path, md_path = write_reports(payload)
    print(
        json.dumps(
            {
                "json": _display_path(json_path),
                "md": _display_path(md_path),
                "total_signal_rows": payload["total_signal_rows"],
                "backfillable_code_count": payload["backfillable_code_count"],
                "unfilled_count": payload["unfilled_count"],
                "ambiguous_name_count": payload["ambiguous_name_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
