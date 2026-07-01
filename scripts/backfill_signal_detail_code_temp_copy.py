# -*- coding: utf-8 -*-
"""Create code-backfilled derived signal_detail copies without overwriting originals."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.encoding import configure_utf8_console  # noqa: E402


REPORTS_DAILY = ROOT / "reports" / "validation" / "daily"
STORE_ROOT = ROOT / "AmazingData_Store"
DERIVED_ROOT = ROOT / "reports" / "validation" / "derived" / "signal_detail_code_backfilled"
EVAL_ROOT = ROOT / "reports" / "analysis" / "evaluations"


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _date_range(start: str, end: str) -> list[str]:
    cur = datetime.strptime(start, "%Y%m%d").date()
    last = datetime.strptime(end, "%Y%m%d").date()
    dates = []
    while cur <= last:
        dates.append(cur.strftime("%Y%m%d"))
        cur += timedelta(days=1)
    return dates


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str, "date": str})
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def source_specs(date: str) -> list[tuple[str, Path]]:
    daily = REPORTS_DAILY / date
    store = STORE_ROOT / date
    return [
        ("factor_snapshot_stock", daily / "factor_snapshot_stock.csv"),
        ("factor_snapshot_stock", store / "factor_snapshot_stock.csv"),
        ("factor_snapshot_etf", daily / "factor_snapshot_etf.csv"),
        ("factor_snapshot_etf", store / "factor_snapshot_etf.csv"),
        ("factor_snapshot_index", daily / "factor_snapshot_index.csv"),
        ("factor_snapshot_index", store / "factor_snapshot_index.csv"),
        ("stocks_csv", store / "stocks.csv"),
        ("indices_csv", store / "indices.csv"),
        ("factor_snapshot", store / "factor_snapshot.csv"),
        ("factor_snapshot_industry_topk", daily / "factor_snapshot_industry_topk.csv"),
        ("factor_snapshot_industry_topk", store / "factor_snapshot_industry_topk.csv"),
    ]


def _valid_code(value) -> str:
    code = str(value or "").strip()
    if not code or code.lower() in {"nan", "none", "null"}:
        return ""
    return code


def build_priority_name_map(date: str) -> tuple[list[dict[str, dict[str, set[str]]]], list[str]]:
    priority_maps: list[dict[str, dict[str, set[str]]]] = []
    source_files = []
    for source_name, path in source_specs(date):
        frame = read_csv(path)
        current: dict[str, dict[str, set[str]]] = {}
        if not frame.empty and "name" in frame.columns and "code" in frame.columns:
            source_files.append(_display_path(path))
            for _, row in frame.iterrows():
                name = str(row.get("name", "") or "").strip()
                code = _valid_code(row.get("code"))
                if not name or not code:
                    continue
                current.setdefault(name, {}).setdefault(code, set()).add(source_name)
        priority_maps.append(current)
    return priority_maps, sorted(set(source_files))


def resolve_code(name: str, priority_maps: list[dict[str, dict[str, set[str]]]]) -> tuple[str, str, str, str]:
    all_codes = sorted(
        {
            code
            for current in priority_maps
            for code in current.get(name, {}).keys()
        }
    )
    if len(all_codes) > 1:
        return "", "ambiguous", "", ";".join(all_codes)
    for current in priority_maps:
        candidates = current.get(name, {})
        if not candidates:
            continue
        codes = sorted(candidates.keys())
        if len(codes) == 1:
            code = codes[0]
            return code, "filled", ",".join(sorted(candidates[code])), ""
        return "", "ambiguous", "", ";".join(codes)
    return "", "unfilled", "", "no_unique_name_code_match"


def backfill_date(date: str, dry_run: bool = False) -> tuple[pd.DataFrame, dict]:
    input_file = REPORTS_DAILY / date / "signal_detail.csv"
    output_file = DERIVED_ROOT / f"{date}_signal_detail.code_backfilled.csv"
    detail = read_csv(input_file)
    priority_maps, source_files = build_priority_name_map(date)
    if detail.empty:
        result = detail.copy()
        summary = {
            "date": date,
            "input_file": _display_path(input_file),
            "output_file": _display_path(output_file),
            "row_count": 0,
            "native_code_count": 0,
            "filled_count": 0,
            "unfilled_count": 0,
            "ambiguous_name_count": 0,
            "name_fallback_count": 0,
            "fill_source_counts": {},
            "source_files": source_files,
            "warnings": ["signal_detail_empty_or_missing"],
            "written": False,
        }
        return result, summary
    result = detail.copy()
    if "code" not in result.columns:
        result["code"] = ""
    result["code"] = result["code"].fillna("").astype(str)
    statuses = []
    sources = []
    warnings = []
    counts = Counter()
    for idx, row in result.iterrows():
        native_code = _valid_code(row.get("code"))
        if native_code:
            result.at[idx, "code"] = native_code
            statuses.append("native")
            sources.append("signal_detail")
            warnings.append("")
            counts["native_code_count"] += 1
            counts["source:signal_detail"] += 1
            continue
        name = str(row.get("name", "") or "").strip()
        code, status, source, warning = resolve_code(name, priority_maps)
        result.at[idx, "code"] = code
        statuses.append(status)
        sources.append(source)
        warnings.append(warning)
        if status == "filled":
            counts["filled_count"] += 1
            counts["name_fallback_count"] += 1
            counts[f"source:{source}"] += 1
        elif status == "ambiguous":
            counts["ambiguous_name_count"] += 1
        else:
            counts["unfilled_count"] += 1
    result["code_fill_status"] = statuses
    result["code_fill_source"] = sources
    result["code_fill_warning"] = warnings
    written = False
    if not dry_run:
        DERIVED_ROOT.mkdir(parents=True, exist_ok=True)
        result.to_csv(output_file, index=False, encoding="utf-8-sig")
        written = True
    fill_source_counts = {
        key.replace("source:", ""): int(value)
        for key, value in counts.items()
        if key.startswith("source:")
    }
    summary = {
        "date": date,
        "input_file": _display_path(input_file),
        "output_file": _display_path(output_file),
        "row_count": int(len(result)),
        "native_code_count": int(counts["native_code_count"]),
        "filled_count": int(counts["filled_count"]),
        "unfilled_count": int(counts["unfilled_count"]),
        "ambiguous_name_count": int(counts["ambiguous_name_count"]),
        "name_fallback_count": int(counts["name_fallback_count"]),
        "fill_source_counts": fill_source_counts,
        "source_files": source_files,
        "warnings": [],
        "written": written,
    }
    return result, summary


def next_returns(date: str) -> pd.DataFrame:
    frames = []
    for _, path in source_specs(date):
        frame = read_csv(path)
        if frame.empty or "name" not in frame.columns:
            continue
        if "auction_pct" not in frame.columns and "close_pct" not in frame.columns:
            continue
        cols = [col for col in ("code", "name", "auction_pct", "close_pct") if col in frame.columns]
        frames.append(frame[cols].copy())
    if not frames:
        return pd.DataFrame(columns=["code", "name", "t1_open_return", "t1_close_return"])
    work = pd.concat(frames, ignore_index=True, sort=False)
    if "code" not in work.columns:
        work["code"] = ""
    work["code"] = work["code"].fillna("").astype(str)
    work = work.rename(columns={"auction_pct": "t1_open_return", "close_pct": "t1_close_return"})
    return work.drop_duplicates(["code", "name"], keep="first")


def recheck_pair(prev_date: str, date: str, derived_detail: pd.DataFrame) -> dict:
    ret = next_returns(date)
    if ret.empty or derived_detail.empty:
        return {
            "prev_date": prev_date,
            "date": date,
            "row_count": int(len(derived_detail)),
            "primary_code_join_count": 0,
            "fallback_name_join_count": 0,
            "unmatched_count": int(len(derived_detail)),
            "ambiguous_blocked_count": int((derived_detail.get("code_fill_status", pd.Series(dtype=str)) == "ambiguous").sum()),
            "join_quality": "missing_next_snapshot",
        }
    by_code = ret[ret["code"].astype(str) != ""].drop_duplicates("code")
    joined = derived_detail.merge(
        by_code[["code", "t1_open_return", "t1_close_return"]],
        on="code",
        how="left",
    )
    joined["t1_join_method"] = joined["t1_close_return"].notna().map(lambda ok: "code" if ok else "unmatched")
    missing = joined["t1_close_return"].isna()
    fallback_count = 0
    if missing.any() and "name" in joined.columns:
        unique_names = ret.dropna(subset=["name"]).groupby("name").filter(lambda rows: len(rows) == 1)
        name_map = unique_names.set_index("name")[["t1_open_return", "t1_close_return"]].to_dict("index")
        for idx, row in joined[missing].iterrows():
            if row.get("code_fill_status") == "ambiguous":
                continue
            values = name_map.get(row.get("name"))
            if not values:
                continue
            joined.at[idx, "t1_open_return"] = values.get("t1_open_return")
            joined.at[idx, "t1_close_return"] = values.get("t1_close_return")
            joined.at[idx, "t1_join_method"] = "name_fallback"
            fallback_count += 1
    primary_count = int((joined["t1_join_method"] == "code").sum())
    unmatched_count = int((joined["t1_join_method"] == "unmatched").sum())
    ambiguous_blocked = int((joined.get("code_fill_status", pd.Series(dtype=str)) == "ambiguous").sum())
    if unmatched_count == 0 and fallback_count == 0:
        quality = "code_keyed_complete"
    elif unmatched_count == 0:
        quality = "complete_with_name_fallback"
    else:
        quality = "partial"
    return {
        "prev_date": prev_date,
        "date": date,
        "row_count": int(len(joined)),
        "primary_code_join_count": primary_count,
        "fallback_name_join_count": int(fallback_count),
        "unmatched_count": unmatched_count,
        "ambiguous_blocked_count": ambiguous_blocked,
        "join_quality": quality,
    }


def build_payload(start_date: str, end_date: str, dry_run: bool = False) -> dict:
    dates = _date_range(start_date, end_date)
    derived_by_date = {}
    summaries = []
    for date in dates:
        derived, summary = backfill_date(date, dry_run=dry_run)
        derived_by_date[date] = derived
        summaries.append(summary)
    aggregate = Counter()
    for summary in summaries:
        aggregate["total_rows"] += summary["row_count"]
        aggregate["native_code_count"] += summary["native_code_count"]
        aggregate["filled_count"] += summary["filled_count"]
        aggregate["unfilled_count"] += summary["unfilled_count"]
        aggregate["ambiguous_name_count"] += summary["ambiguous_name_count"]
    pairs = []
    for prev, date in zip(dates, dates[1:]):
        pairs.append(recheck_pair(prev, date, derived_by_date.get(prev, pd.DataFrame())))
    join_totals = Counter()
    for pair in pairs:
        join_totals["primary_code_join_count"] += pair["primary_code_join_count"]
        join_totals["fallback_name_join_count"] += pair["fallback_name_join_count"]
        join_totals["unmatched_count"] += pair["unmatched_count"]
        join_totals["ambiguous_blocked_count"] += pair["ambiguous_blocked_count"]
    if join_totals["unmatched_count"] == 0 and join_totals["fallback_name_join_count"] == 0:
        join_quality = "code_keyed_complete"
    elif join_totals["unmatched_count"] == 0:
        join_quality = "complete_with_name_fallback"
    else:
        join_quality = "partial"
    conclusions = [
        "historical_signal_detail_code_backfilled_temp_copy_written" if not dry_run else "historical_signal_detail_code_backfilled_temp_copy_planned",
        "original_signal_detail_not_modified",
        "code_keyed_join_quality_improved",
        "name_fallback_explicitly_counted",
        "ambiguous_name_not_silently_matched",
        "no_strategy_rule_change",
        "cp_evaluator_change_not_required",
        "trend_evaluator_change_not_required",
        "lesson_pattern_not_written",
    ]
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "date_range": {"start": start_date, "end": end_date},
        "dry_run": dry_run,
        "original_files_modified": False,
        "derived_files_written": [s["output_file"] for s in summaries if s["written"]],
        "daily_backfill_summary": summaries,
        "aggregate_summary": {
            "total_rows": int(aggregate["total_rows"]),
            "native_code_count": int(aggregate["native_code_count"]),
            "filled_count": int(aggregate["filled_count"]),
            "unfilled_count": int(aggregate["unfilled_count"]),
            "ambiguous_name_count": int(aggregate["ambiguous_name_count"]),
        },
        "t1_join_recheck": {
            "pairs": pairs,
            "primary_code_join_count": int(join_totals["primary_code_join_count"]),
            "fallback_name_join_count": int(join_totals["fallback_name_join_count"]),
            "unmatched_count": int(join_totals["unmatched_count"]),
            "ambiguous_blocked_count": int(join_totals["ambiguous_blocked_count"]),
            "join_quality": join_quality,
        },
        "strategy_rule_change_required": False,
        "cp_evaluator_change_required": False,
        "trend_evaluator_change_required": False,
        "lesson_pattern_written": False,
        "recommended_next_actions": [
            "review_unfilled_and_ambiguous_signal_detail_rows",
            "use_code_backfilled_temp_copies_for_multi_day_t1_validation",
            "keep_original_signal_detail_files_unchanged_until_manual_approval",
        ],
        "warnings": ["original_signal_detail_files_not_modified"],
        "conclusion": conclusions,
    }


def write_reports(payload: dict) -> tuple[Path, Path]:
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    start = payload["date_range"]["start"]
    end = payload["date_range"]["end"]
    stem = f"signal_detail_code_backfilled_temp_copy_{start}_{end}"
    json_path = EVAL_ROOT / f"{stem}.json"
    md_path = EVAL_ROOT / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def render_markdown(payload: dict) -> str:
    agg = payload["aggregate_summary"]
    join = payload["t1_join_recheck"]
    lines = [
        f"# Signal Detail Code Backfilled Temp Copy {payload['date_range']['start']} -> {payload['date_range']['end']}",
        "",
        f"- original_files_modified: `{payload['original_files_modified']}`",
        f"- derived_files_written: `{len(payload['derived_files_written'])}`",
        f"- total_rows: `{agg['total_rows']}`",
        f"- filled_count: `{agg['filled_count']}`",
        f"- unfilled_count: `{agg['unfilled_count']}`",
        f"- ambiguous_name_count: `{agg['ambiguous_name_count']}`",
        f"- primary_code_join_count: `{join['primary_code_join_count']}`",
        f"- fallback_name_join_count: `{join['fallback_name_join_count']}`",
        f"- unmatched_count: `{join['unmatched_count']}`",
        f"- join_quality: `{join['join_quality']}`",
        "",
        "## Daily Backfill",
        "",
    ]
    for row in payload["daily_backfill_summary"]:
        lines.append(
            f"- {row['date']}: rows={row['row_count']}, filled={row['filled_count']}, "
            f"unfilled={row['unfilled_count']}, ambiguous={row['ambiguous_name_count']}"
        )
    lines.extend(["", "## Conclusion", ""])
    lines.extend(f"- {item}" for item in payload["conclusion"])
    return "\n".join(lines) + "\n"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Create code-backfilled derived signal_detail copies.")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    configure_utf8_console()
    args = parse_args(argv)
    payload = build_payload(args.start_date, args.end_date, dry_run=args.dry_run)
    json_path, md_path = write_reports(payload)
    print(
        json.dumps(
            {
                "json": _display_path(json_path),
                "md": _display_path(md_path),
                "derived_files_written": payload["derived_files_written"],
                "aggregate_summary": payload["aggregate_summary"],
                "t1_join_recheck": payload["t1_join_recheck"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
