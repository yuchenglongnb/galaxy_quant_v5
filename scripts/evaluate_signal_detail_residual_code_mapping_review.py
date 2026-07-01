# -*- coding: utf-8 -*-
"""Build a manual review pack for residual signal_detail code mapping issues."""

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


DERIVED_ROOT = ROOT / "reports" / "validation" / "derived" / "signal_detail_code_backfilled"
REPORTS_DAILY = ROOT / "reports" / "validation" / "daily"
STORE_ROOT = ROOT / "AmazingData_Store"
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


def derived_path(date: str) -> Path:
    return DERIVED_ROOT / f"{date}_signal_detail.code_backfilled.csv"


def candidate_sources(date: str) -> list[tuple[str, Path]]:
    daily = REPORTS_DAILY / date
    store = STORE_ROOT / date
    return [
        ("factor_snapshot_stock", daily / "factor_snapshot_stock.csv"),
        ("factor_snapshot_etf", daily / "factor_snapshot_etf.csv"),
        ("factor_snapshot_index", daily / "factor_snapshot_index.csv"),
        ("factor_snapshot_industry_topk", daily / "factor_snapshot_industry_topk.csv"),
        ("factor_snapshot", store / "factor_snapshot.csv"),
        ("factor_snapshot_stock", store / "factor_snapshot_stock.csv"),
        ("factor_snapshot_etf", store / "factor_snapshot_etf.csv"),
        ("factor_snapshot_index", store / "factor_snapshot_index.csv"),
        ("factor_snapshot_industry_topk", store / "factor_snapshot_industry_topk.csv"),
        ("stocks_csv", store / "stocks.csv"),
        ("indices_csv", store / "indices.csv"),
    ]


def _valid_code(value) -> str:
    code = str(value or "").strip()
    if not code or code.lower() in {"nan", "none", "null"}:
        return ""
    return code


def candidate_catalog(date: str) -> dict[str, dict]:
    catalog: dict[str, dict] = {}
    for source_name, path in candidate_sources(date):
        frame = read_csv(path)
        if frame.empty or "name" not in frame.columns or "code" not in frame.columns:
            continue
        for _, row in frame.iterrows():
            name = str(row.get("name", "") or "").strip()
            code = _valid_code(row.get("code"))
            if not name or not code:
                continue
            entry = catalog.setdefault(name, {"codes": defaultdict(set), "names": set()})
            entry["codes"][code].add(source_name)
            entry["names"].add(name)
    normalized = {}
    for name, entry in catalog.items():
        normalized[name] = {
            "candidate_codes": sorted(entry["codes"].keys()),
            "candidate_sources": sorted({src for sources in entry["codes"].values() for src in sources}),
            "candidate_names": sorted(entry["names"]),
        }
    return normalized


def next_returns(date: str) -> pd.DataFrame:
    frames = []
    for _, path in candidate_sources(date):
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


def classify_confidence(row: dict) -> tuple[str, str]:
    codes = row["candidate_codes"]
    if len(codes) == 1 and row["name"] in row["candidate_names"]:
        return "high", "single_exact_name_candidate_requires_manual_approval"
    if len(codes) == 1:
        return "medium", "single_candidate_with_name_or_scope_difference"
    if len(codes) > 1:
        return "none", "conflicting_candidate_codes"
    return "none", "no_candidate_code"


def _signal_type(row: pd.Series) -> str:
    for col in ("signal_family", "signal_type", "signal_category"):
        if col in row and pd.notna(row.get(col)):
            return str(row.get(col))
    return ""


def mark_join_problems(prev_date: str, date: str, frame: pd.DataFrame) -> dict[int, set[str]]:
    problems: dict[int, set[str]] = defaultdict(set)
    ret = next_returns(date)
    if frame.empty:
        return problems
    if ret.empty:
        for idx in frame.index:
            problems[int(idx)].add("unmatched")
        return problems
    by_code = ret[ret["code"].astype(str) != ""].drop_duplicates("code")
    joined = frame.merge(
        by_code[["code", "t1_open_return", "t1_close_return"]],
        on="code",
        how="left",
    )
    if "code_fill_status" in joined.columns:
        for idx, row in joined.iterrows():
            if row.get("code_fill_status") == "ambiguous":
                problems[int(idx)].add("ambiguous_blocked")
    missing = joined["t1_close_return"].isna()
    if missing.any() and "name" in joined.columns:
        unique_names = ret.dropna(subset=["name"]).groupby("name").filter(lambda rows: len(rows) == 1)
        name_set = set(unique_names["name"].astype(str).tolist())
        for idx, row in joined[missing].iterrows():
            if row.get("code_fill_status") == "ambiguous":
                problems[int(idx)].add("unmatched")
                continue
            if str(row.get("name", "")) in name_set:
                problems[int(idx)].add("name_fallback")
            else:
                problems[int(idx)].add("unmatched")
    return problems


def collect_residual_rows(start_date: str, end_date: str) -> tuple[list[dict], dict, list[str]]:
    dates = _date_range(start_date, end_date)
    frames = {date: read_csv(derived_path(date)) for date in dates}
    input_files = [_display_path(derived_path(date)) for date in dates]
    problem_map: dict[tuple[str, int], set[str]] = defaultdict(set)
    raw_counts = Counter()
    for date, frame in frames.items():
        if frame.empty:
            continue
        for idx, row in frame.iterrows():
            status = str(row.get("code_fill_status", "") or "")
            if status == "unfilled":
                problem_map[(date, int(idx))].add("unfilled")
                raw_counts["unfilled"] += 1
            elif status == "ambiguous":
                problem_map[(date, int(idx))].add("ambiguous")
                raw_counts["ambiguous"] += 1
    for prev, date in zip(dates, dates[1:]):
        join_problems = mark_join_problems(prev, date, frames.get(prev, pd.DataFrame()))
        for idx, types in join_problems.items():
            for problem_type in types:
                problem_map[(prev, idx)].add(problem_type)
                raw_counts[problem_type] += 1
    catalogs = {date: candidate_catalog(date) for date in dates}
    rows = []
    for (date, idx), problem_types in sorted(problem_map.items()):
        frame = frames.get(date, pd.DataFrame())
        if frame.empty or idx >= len(frame):
            continue
        row = frame.iloc[idx]
        name = str(row.get("name", "") or "")
        candidates = catalogs.get(date, {}).get(
            name,
            {"candidate_codes": [], "candidate_sources": [], "candidate_names": []},
        )
        current = {
            "date": date,
            "source_file": _display_path(derived_path(date)),
            "row_index": int(idx),
            "name": name,
            "signal_type": _signal_type(row),
            "current_code": _valid_code(row.get("code")),
            "code_fill_status": str(row.get("code_fill_status", "") or ""),
            "code_fill_source": str(row.get("code_fill_source", "") or ""),
            "code_fill_warning": str(row.get("code_fill_warning", "") or ""),
            "problem_types": sorted(problem_types),
            "candidate_codes": candidates["candidate_codes"],
            "candidate_sources": candidates["candidate_sources"],
            "candidate_names": candidates["candidate_names"],
            "manual_resolution_required": True,
            "recommended_resolution": "",
            "confidence": "none",
            "should_auto_patch": False,
        }
        confidence, recommendation = classify_confidence(current)
        current["confidence"] = confidence
        current["recommended_resolution"] = recommendation
        rows.append(current)
    return rows, dict(raw_counts), input_files


def build_payload(start_date: str, end_date: str) -> dict:
    rows, raw_counts, input_files = collect_residual_rows(start_date, end_date)
    confidence_distribution = Counter(row["confidence"] for row in rows)
    conclusions = [
        "residual_code_mapping_manual_review_required",
        "original_signal_detail_not_modified",
        "derived_signal_detail_not_modified",
        "auto_patch_disabled",
        "ambiguous_name_not_silently_matched",
        "name_fallback_explicitly_counted",
        "no_strategy_rule_change",
        "cp_evaluator_change_not_required",
        "trend_evaluator_change_not_required",
        "lesson_pattern_not_written",
    ]
    if confidence_distribution.get("high", 0) > 0:
        conclusions.append("high_confidence_rows_require_manual_approval")
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "date_range": {"start": start_date, "end": end_date},
        "input_files": input_files,
        "original_files_modified": False,
        "derived_files_modified": False,
        "raw_problem_counts": {
            "unfilled": int(raw_counts.get("unfilled", 0)),
            "ambiguous": int(raw_counts.get("ambiguous", 0)),
            "name_fallback": int(raw_counts.get("name_fallback", 0)),
            "unmatched": int(raw_counts.get("unmatched", 0)),
            "ambiguous_blocked": int(raw_counts.get("ambiguous_blocked", 0)),
        },
        "unique_problem_row_count": len(rows),
        "residual_rows": rows,
        "confidence_distribution": {
            "high": int(confidence_distribution.get("high", 0)),
            "medium": int(confidence_distribution.get("medium", 0)),
            "low": int(confidence_distribution.get("low", 0)),
            "none": int(confidence_distribution.get("none", 0)),
        },
        "auto_patch_allowed": False,
        "manual_review_required": True,
        "temp_patch_recommended": False,
        "strategy_rule_change_required": False,
        "cp_evaluator_change_required": False,
        "trend_evaluator_change_required": False,
        "lesson_pattern_written": False,
        "recommended_next_actions": [
            "review_each_residual_row_before_any_temp_patch",
            "approve_candidate_codes_manually",
            "rerun_code_keyed_t1_join_after_manual_approved_temp_patch",
        ],
        "warnings": ["auto_patch_disabled_even_for_high_confidence_rows"],
        "conclusion": conclusions,
    }


def write_reports(payload: dict) -> tuple[Path, Path]:
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    start = payload["date_range"]["start"]
    end = payload["date_range"]["end"]
    stem = f"signal_detail_residual_code_mapping_review_{start}_{end}"
    json_path = EVAL_ROOT / f"{stem}.json"
    md_path = EVAL_ROOT / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def render_markdown(payload: dict) -> str:
    lines = [
        f"# Residual Signal Detail Code Mapping Review {payload['date_range']['start']} -> {payload['date_range']['end']}",
        "",
        f"- unique_problem_row_count: `{payload['unique_problem_row_count']}`",
        f"- raw_problem_counts: `{payload['raw_problem_counts']}`",
        f"- confidence_distribution: `{payload['confidence_distribution']}`",
        f"- auto_patch_allowed: `{payload['auto_patch_allowed']}`",
        "",
        "## Rows",
        "",
    ]
    for row in payload["residual_rows"]:
        lines.append(
            f"- {row['date']} #{row['row_index']} {row['name']}: "
            f"{','.join(row['problem_types'])}; candidates={row['candidate_codes']}; confidence={row['confidence']}"
        )
    lines.extend(["", "## Conclusion", ""])
    lines.extend(f"- {item}" for item in payload["conclusion"])
    return "\n".join(lines) + "\n"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Build residual code mapping manual review pack.")
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
                "raw_problem_counts": payload["raw_problem_counts"],
                "unique_problem_row_count": payload["unique_problem_row_count"],
                "confidence_distribution": payload["confidence_distribution"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
