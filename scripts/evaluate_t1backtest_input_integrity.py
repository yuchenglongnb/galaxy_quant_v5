# -*- coding: utf-8 -*-
"""Audit T+1 backtest inputs and code-keyed join quality."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.encoding import configure_utf8_console  # noqa: E402


VALIDATION_PATH = ROOT / "reports" / "validation" / "auction_signal_validation.csv"
EVAL_ROOT = ROOT / "reports" / "analysis" / "evaluations"


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def scan_malformed_csv(path: Path) -> dict:
    result = {
        "file": _display_path(path) if path.exists() else str(path),
        "line": None,
        "expected_fields": 0,
        "actual_fields": 0,
        "root_cause": "",
        "quarantine_recommended": False,
        "repair_attempted": False,
        "repair_success": False,
        "bad_rows": [],
    }
    if not path.exists():
        result["root_cause"] = "file_missing"
        return result
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, [])
        expected = len(header)
        result["expected_fields"] = expected
        for line_no, row in enumerate(reader, start=2):
            if len(row) == expected:
                continue
            bad = {
                "line": line_no,
                "expected_fields": expected,
                "actual_fields": len(row),
                "sample": row[:8],
                "tail": row[-5:],
            }
            result["bad_rows"].append(bad)
            if result["line"] is None:
                result.update(
                    {
                        "line": line_no,
                        "actual_fields": len(row),
                        "root_cause": classify_bad_row(expected, len(row)),
                        "quarantine_recommended": True,
                    }
                )
    if not result["root_cause"]:
        result["root_cause"] = "clean"
    return result


def classify_bad_row(expected_fields: int, actual_fields: int) -> str:
    if actual_fields > expected_fields:
        if actual_fields >= expected_fields * 2 - 1:
            return "historical_aggregate_append_field_count_mismatch"
        return "extra_fields_or_unescaped_delimiter"
    if actual_fields < expected_fields:
        return "truncated_or_partial_csv_row"
    return "clean"


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str, "date": str})


def daily_signal_detail(prev_date: str) -> pd.DataFrame:
    return read_csv(ROOT / "reports" / "validation" / "daily" / prev_date / "signal_detail.csv")


def factor_snapshot(date: str) -> pd.DataFrame:
    parts = []
    daily = ROOT / "reports" / "validation" / "daily" / date
    for filename in (
        "factor_snapshot_stock.csv",
        "factor_snapshot_etf.csv",
        "factor_snapshot_index.csv",
        "factor_snapshot_industry_topk.csv",
    ):
        path = daily / filename
        if path.exists():
            frame = read_csv(path)
            frame["source_file"] = str(path.relative_to(ROOT))
            parts.append(frame)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True, sort=False)


def build_code_map(date: str) -> tuple[dict[str, dict], list[str]]:
    snapshot = factor_snapshot(date)
    source_files = sorted(snapshot.get("source_file", pd.Series(dtype=str)).dropna().unique().tolist())
    if snapshot.empty or "name" not in snapshot.columns or "code" not in snapshot.columns:
        return {}, source_files
    work = snapshot[["name", "code", "source_file"]].dropna(subset=["name"]).copy()
    work["name"] = work["name"].astype(str)
    work["code"] = work["code"].fillna("").astype(str)
    mapping = {}
    for name, group in work.groupby("name", dropna=False):
        codes = sorted({code for code in group["code"].tolist() if code and code.lower() != "nan"})
        mapping[name] = {
            "codes": codes,
            "source_files": sorted(set(group["source_file"].astype(str).tolist())),
        }
    return mapping, source_files


def fill_codes(detail: pd.DataFrame, prev_date: str) -> tuple[pd.DataFrame, dict]:
    work = detail.copy()
    has_code = "code" in work.columns
    if not has_code:
        work["code"] = ""
    work["code"] = work["code"].fillna("").astype(str)
    mapping, source_files = build_code_map(prev_date)
    filled = 0
    unfilled = 0
    fallback = 0
    ambiguous = 0
    methods = []
    for idx, row in work.iterrows():
        code = str(row.get("code", "") or "").strip()
        if code and code.lower() not in {"nan", "none", "null"}:
            methods.append("primary_code")
            continue
        name = str(row.get("name", "") or "")
        candidates = mapping.get(name, {}).get("codes", [])
        if len(candidates) == 1:
            work.at[idx, "code"] = candidates[0]
            filled += 1
            fallback += 1
            methods.append("filled_from_factor_snapshot_by_name")
        elif len(candidates) > 1:
            ambiguous += 1
            methods.append("ambiguous_name")
        else:
            unfilled += 1
            methods.append("unfilled")
    work["code_fill_method"] = methods
    return work, {
        "source_files": source_files,
        "filled_count": int(filled),
        "unfilled_count": int(unfilled),
        "fallback_name_match_count": int(fallback),
        "ambiguous_name_count": int(ambiguous),
    }


def next_snapshot_returns(date: str) -> pd.DataFrame:
    snapshot = factor_snapshot(date)
    if snapshot.empty:
        return pd.DataFrame(columns=["code", "name", "t1_open_return", "t1_close_return"])
    cols = [col for col in ("code", "name", "auction_pct", "close_pct") if col in snapshot.columns]
    work = snapshot[cols].copy()
    if "code" in work.columns:
        work["code"] = work["code"].fillna("").astype(str)
    work = work.rename(columns={"auction_pct": "t1_open_return", "close_pct": "t1_close_return"})
    return work


def join_t1(detail_with_code: pd.DataFrame, date: str) -> tuple[pd.DataFrame, dict]:
    next_ret = next_snapshot_returns(date)
    work = detail_with_code.copy()
    if next_ret.empty:
        work["t1_open_return"] = pd.NA
        work["t1_close_return"] = pd.NA
        work["t1_join_method"] = "unmatched"
        return work, {"primary_code_join_count": 0, "fallback_name_join_count": 0, "unmatched_count": len(work), "join_quality": "missing_next_snapshot"}
    by_code = next_ret[next_ret.get("code", "").astype(str) != ""].drop_duplicates("code")
    joined = work.merge(
        by_code[["code", "t1_open_return", "t1_close_return"]],
        on="code",
        how="left",
    )
    joined["t1_join_method"] = joined["t1_close_return"].notna().map(lambda ok: "code" if ok else "unmatched")
    missing = joined["t1_close_return"].isna()
    fallback_count = 0
    if missing.any() and "name" in joined.columns and "name" in next_ret.columns:
        by_name = next_ret.dropna(subset=["name"]).copy()
        unique_names = by_name.groupby("name").filter(lambda rows: len(rows) == 1)
        name_map = unique_names.set_index("name")[["t1_open_return", "t1_close_return"]].to_dict("index")
        for idx, row in joined[missing].iterrows():
            values = name_map.get(row.get("name"))
            if not values:
                continue
            joined.at[idx, "t1_open_return"] = values.get("t1_open_return")
            joined.at[idx, "t1_close_return"] = values.get("t1_close_return")
            joined.at[idx, "t1_join_method"] = "name_fallback"
            fallback_count += 1
    primary_count = int((joined["t1_join_method"] == "code").sum())
    unmatched_count = int((joined["t1_join_method"] == "unmatched").sum())
    if unmatched_count == 0 and fallback_count == 0:
        quality = "code_keyed_complete"
    elif unmatched_count == 0:
        quality = "complete_with_name_fallback"
    else:
        quality = "partial"
    return joined, {
        "primary_code_join_count": primary_count,
        "fallback_name_join_count": int(fallback_count),
        "unmatched_count": unmatched_count,
        "join_quality": quality,
    }


def summarize_t1(joined: pd.DataFrame) -> dict:
    result = {}
    if joined.empty:
        return result
    key_col = "signal_family" if "signal_family" in joined.columns else "signal_category"
    for key, group in joined.groupby(key_col, dropna=False):
        valid = group[group["t1_close_return"].notna()].copy()
        if valid.empty:
            result[str(key)] = {
                "count": int(len(group)),
                "matched": 0,
                "avg_t1_open_return": None,
                "t1_open_win_rate": None,
                "avg_t1_close_return": None,
                "t1_close_win_rate": None,
            }
            continue
        open_ret = pd.to_numeric(valid["t1_open_return"], errors="coerce")
        close_ret = pd.to_numeric(valid["t1_close_return"], errors="coerce")
        result[str(key)] = {
            "count": int(len(group)),
            "matched": int(close_ret.notna().sum()),
            "avg_t1_open_return": round(float(open_ret.mean()), 4),
            "t1_open_win_rate": round(float((open_ret > 0).mean() * 100), 2),
            "avg_t1_close_return": round(float(close_ret.mean()), 4),
            "t1_close_win_rate": round(float((close_ret > 0).mean() * 100), 2),
        }
    return result


def name_based_reference(detail: pd.DataFrame, date: str) -> dict:
    next_ret = next_snapshot_returns(date)
    if next_ret.empty or "name" not in detail.columns:
        return {}
    unique_names = next_ret.dropna(subset=["name"]).groupby("name").filter(lambda rows: len(rows) == 1)
    joined = detail.merge(
        unique_names[["name", "t1_open_return", "t1_close_return"]],
        on="name",
        how="left",
    )
    return summarize_t1(joined)


def build_payload(prev_date: str, date: str) -> dict:
    bad_csv = scan_malformed_csv(VALIDATION_PATH)
    detail = daily_signal_detail(prev_date)
    has_code = "code" in detail.columns
    filled, fill_stats = fill_codes(detail, prev_date)
    joined, join_stats = join_t1(filled, date)
    code_summary = summarize_t1(joined)
    reference = name_based_reference(detail, date)
    conclusions = [
        "t1backtest_input_integrity_issue",
        "code_keyed_join_required",
        "no_strategy_rule_change",
        "cp_evaluator_change_not_required",
        "trend_evaluator_change_not_required",
    ]
    if bad_csv.get("quarantine_recommended"):
        conclusions.append("bad_csv_quarantine_required")
    if not has_code:
        conclusions.append("signal_detail_code_missing")
    return {
        "date": date,
        "prev_date": prev_date,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "t1backtest_official_blocked": bool(bad_csv.get("quarantine_recommended")),
        "blocked_reason": bad_csv.get("root_cause", ""),
        "bad_csv_analysis": bad_csv,
        "signal_detail_schema": {
            "has_code": bool(has_code),
            "has_name": "name" in detail.columns,
            "recommended_primary_key": "code",
            "fallback_key": "name",
        },
        "code_fill_analysis": fill_stats,
        "t1_join_analysis": join_stats,
        "t1_summary_code_keyed": code_summary,
        "t1_summary_name_based_reference": reference,
        "strategy_rule_change_required": False,
        "cp_evaluator_change_required": False,
        "trend_evaluator_change_required": False,
        "recommended_next_actions": [
            "quarantine_bad_rows_from_global_validation_csv",
            "include_code_in_new_signal_detail_outputs",
            "use_code_as_t1_join_primary_key",
            "count_name_fallback_explicitly",
            "rerun_official_t1backtest_after_clean_input_is_available",
        ],
        "warnings": [
            "historical_csv_not_overwritten",
            "name_fallback_is_diagnostic_only",
        ],
        "conclusion": conclusions,
    }


def write_outputs(payload: dict) -> tuple[Path, Path]:
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    stem = f"t1backtest_input_integrity_{payload['prev_date']}_{payload['date']}"
    json_path = EVAL_ROOT / f"{stem}.json"
    md_path = EVAL_ROOT / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def render_markdown(payload: dict) -> str:
    lines = [
        f"# T+1 Backtest Input Integrity {payload['prev_date']} -> {payload['date']}",
        "",
        f"- official_blocked: `{payload['t1backtest_official_blocked']}`",
        f"- blocked_reason: `{payload['blocked_reason']}`",
        f"- signal_detail_has_code: `{payload['signal_detail_schema']['has_code']}`",
        f"- t1_join_analysis: `{payload['t1_join_analysis']}`",
        "",
        "## Code-Keyed Summary",
        "",
        json.dumps(payload["t1_summary_code_keyed"], ensure_ascii=False, indent=2),
        "",
        "## Name-Based Reference",
        "",
        json.dumps(payload["t1_summary_name_based_reference"], ensure_ascii=False, indent=2),
        "",
        "## Conclusion",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["conclusion"])
    return "\n".join(lines) + "\n"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Audit T+1 backtest input integrity.")
    parser.add_argument("--prev-date", required=True)
    parser.add_argument("--date", required=True)
    return parser.parse_args(argv)


def main(argv=None):
    configure_utf8_console()
    args = parse_args(argv)
    payload = build_payload(args.prev_date, args.date)
    json_path, md_path = write_outputs(payload)
    print(json.dumps({
        "json": str(json_path.relative_to(ROOT)),
        "md": str(md_path.relative_to(ROOT)),
        "official_blocked": payload["t1backtest_official_blocked"],
        "blocked_reason": payload["blocked_reason"],
        "signal_detail_has_code": payload["signal_detail_schema"]["has_code"],
        "t1_join_analysis": payload["t1_join_analysis"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
