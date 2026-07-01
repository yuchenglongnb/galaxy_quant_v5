# -*- coding: utf-8 -*-
"""Evaluate multi-day T+1 performance using manual-patched signal_detail copies."""

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

from scripts.backfill_signal_detail_code_temp_copy import next_returns  # noqa: E402
from utils.encoding import configure_utf8_console  # noqa: E402


MANUAL_PATCH_ROOT = ROOT / "reports" / "validation" / "derived" / "signal_detail_manual_code_patch"
EVAL_ROOT = ROOT / "reports" / "analysis" / "evaluations"
OUTPUT_ROOT = ROOT / "reports" / "t1_backtest" / "multiday_validation"


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


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str, "date": str})
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def signal_path(date: str) -> Path:
    return MANUAL_PATCH_ROOT / f"{date}_signal_detail.manual_code_patch.csv"


def signal_key(row: pd.Series) -> str:
    for col in ("signal_family", "signal_type", "signal_category"):
        if col in row and pd.notna(row.get(col)):
            return str(row.get(col))
    return ""


def is_manual_excluded(frame: pd.DataFrame) -> pd.Series:
    if "manual_resolution_scope" not in frame.columns:
        return pd.Series(False, index=frame.index)
    return frame["manual_resolution_scope"].fillna("").astype(str) == "industry_without_code"


def is_pending(frame: pd.DataFrame) -> pd.Series:
    if "manual_resolution_status" not in frame.columns:
        return pd.Series(False, index=frame.index)
    return frame["manual_resolution_status"].fillna("").astype(str) == "pending"


def _valid_code(value) -> str:
    code = str(value or "").strip()
    if not code or code.lower() in {"nan", "none", "null"}:
        return ""
    return code


def join_pair(prev_date: str, date: str) -> tuple[pd.DataFrame, dict]:
    path = signal_path(prev_date)
    detail = _read_csv(path)
    if detail.empty:
        return detail, {
            "candidate_count": 0,
            "resolved_code_denominator": 0,
            "manual_scope_excluded_count": 0,
            "pending_blocked_count": 0,
            "primary_code_join_count": 0,
            "fallback_name_join_count": 0,
            "unmatched_count": 0,
            "quality": "empty_input",
        }
    if "code" not in detail.columns:
        detail["code"] = ""
    detail["code"] = detail["code"].fillna("").astype(str)
    manual_excluded = is_manual_excluded(detail)
    pending = is_pending(detail)
    resolved = detail[~manual_excluded & ~pending].copy()
    ret = next_returns(date)
    if ret.empty:
        joined = resolved.copy()
        joined["t1_open_return"] = pd.NA
        joined["t1_close_return"] = pd.NA
        joined["t1_join_method"] = "unmatched"
    else:
        by_code = ret[ret["code"].astype(str) != ""].drop_duplicates("code")
        joined = resolved.merge(
            by_code[["code", "t1_open_return", "t1_close_return"]],
            on="code",
            how="left",
        )
        joined["t1_join_method"] = joined["t1_close_return"].notna().map(lambda ok: "code" if ok else "unmatched")
    primary = int((joined["t1_join_method"] == "code").sum()) if not joined.empty else 0
    fallback = 0
    unmatched = int((joined["t1_join_method"] == "unmatched").sum()) if not joined.empty else 0
    if unmatched == 0 and fallback == 0:
        quality = "code_keyed_complete"
    elif unmatched == 0:
        quality = "complete_with_explicit_fallback"
    else:
        quality = "partial"
    joined["signal_type_key"] = joined.apply(signal_key, axis=1) if not joined.empty else []
    return joined, {
        "candidate_count": int(len(detail)),
        "resolved_code_denominator": int(len(resolved)),
        "manual_scope_excluded_count": int(manual_excluded.sum()),
        "pending_blocked_count": int(pending.sum()),
        "primary_code_join_count": primary,
        "fallback_name_join_count": fallback,
        "unmatched_count": unmatched,
        "quality": quality,
    }


def summarize_by_signal_type(joined: pd.DataFrame, source_detail: pd.DataFrame | None = None) -> dict:
    result = {}
    if joined is None:
        joined = pd.DataFrame()
    if not joined.empty and "signal_type_key" not in joined.columns:
        joined = joined.copy()
        joined["signal_type_key"] = joined.apply(signal_key, axis=1)
    keys = sorted(set(joined.get("signal_type_key", pd.Series(dtype=str)).dropna().astype(str).tolist()))
    if source_detail is not None and not source_detail.empty:
        keys = sorted(set(keys) | set(source_detail.apply(signal_key, axis=1).dropna().astype(str).tolist()))
    for key in keys:
        group = joined[joined["signal_type_key"] == key] if not joined.empty else pd.DataFrame()
        close_ret = pd.to_numeric(group.get("t1_close_return", pd.Series(dtype=float)), errors="coerce")
        valid = close_ret.dropna()
        result[key] = {
            "signal_count": int(len(group)),
            "resolved_count": int(len(valid)),
            "avg_t1_close_return": round(float(valid.mean()), 4) if not valid.empty else None,
            "win_rate": round(float((valid > 0).mean() * 100), 2) if not valid.empty else None,
            "median_t1_close_return": round(float(valid.median()), 4) if not valid.empty else None,
            "positive_count": int((valid > 0).sum()),
            "negative_count": int((valid < 0).sum()),
            "pending_count": 0,
            "manual_scope_excluded_count": 0,
        }
    if source_detail is not None and not source_detail.empty:
        pending = is_pending(source_detail)
        excluded = is_manual_excluded(source_detail)
        for key, group in source_detail[pending].groupby(source_detail[pending].apply(signal_key, axis=1), dropna=False):
            result.setdefault(str(key), _empty_signal_summary())
            result[str(key)]["pending_count"] += int(len(group))
        for key, group in source_detail[excluded].groupby(source_detail[excluded].apply(signal_key, axis=1), dropna=False):
            result.setdefault(str(key), _empty_signal_summary())
            result[str(key)]["manual_scope_excluded_count"] += int(len(group))
    return result


def _empty_signal_summary() -> dict:
    return {
        "signal_count": 0,
        "resolved_count": 0,
        "avg_t1_close_return": None,
        "win_rate": None,
        "median_t1_close_return": None,
        "positive_count": 0,
        "negative_count": 0,
        "pending_count": 0,
        "manual_scope_excluded_count": 0,
    }


def pending_rows(detail: pd.DataFrame) -> list[dict]:
    if detail.empty:
        return []
    rows = []
    pending = is_pending(detail)
    for idx, row in detail[pending].iterrows():
        rows.append(
            {
                "row_index": int(idx),
                "name": str(row.get("name", "") or ""),
                "signal_type": signal_key(row),
                "candidate_codes": str(row.get("code_fill_warning", "") or ""),
                "reason": str(row.get("manual_resolution_reason", "") or ""),
            }
        )
    return rows


def excluded_rows(detail: pd.DataFrame) -> list[dict]:
    if detail.empty:
        return []
    rows = []
    excluded = is_manual_excluded(detail)
    for idx, row in detail[excluded].iterrows():
        rows.append(
            {
                "row_index": int(idx),
                "name": str(row.get("name", "") or ""),
                "signal_type": signal_key(row),
                "scope": "industry_without_code",
                "reason": str(row.get("manual_resolution_reason", "") or ""),
            }
        )
    return rows


def build_pair(prev_date: str, date: str) -> dict:
    detail = _read_csv(signal_path(prev_date))
    joined, quality = join_pair(prev_date, date)
    return {
        "prev_date": prev_date,
        "date": date,
        "input_signal_detail": _display_path(signal_path(prev_date)),
        "join_quality": quality,
        "pending_rows": pending_rows(detail),
        "manual_scope_excluded_rows": excluded_rows(detail),
        "signal_type_summary": summarize_by_signal_type(joined, detail),
    }


def aggregate_pairs(pairs: list[dict]) -> dict:
    totals = Counter()
    signal_acc: dict[str, dict] = defaultdict(_empty_signal_summary)
    values_by_signal: dict[str, list[float]] = defaultdict(list)
    for pair in pairs:
        q = pair["join_quality"]
        totals["total_candidate_count"] += q["candidate_count"]
        totals["total_resolved_code_denominator"] += q["resolved_code_denominator"]
        totals["total_manual_scope_excluded_count"] += q["manual_scope_excluded_count"]
        totals["total_pending_blocked_count"] += q["pending_blocked_count"]
        totals["total_primary_code_join_count"] += q["primary_code_join_count"]
        totals["total_fallback_name_join_count"] += q["fallback_name_join_count"]
        totals["total_unmatched_count"] += q["unmatched_count"]
        for key, summary in pair["signal_type_summary"].items():
            acc = signal_acc[key]
            acc["signal_count"] += summary["signal_count"]
            acc["resolved_count"] += summary["resolved_count"]
            acc["positive_count"] += summary["positive_count"]
            acc["negative_count"] += summary["negative_count"]
            acc["pending_count"] += summary["pending_count"]
            acc["manual_scope_excluded_count"] += summary["manual_scope_excluded_count"]
            # Store repeated rounded values weighted by resolved_count for compact aggregate.
            if summary["avg_t1_close_return"] is not None:
                values_by_signal[key].extend([summary["avg_t1_close_return"]] * max(summary["resolved_count"], 1))
    result_signal = {}
    for key, summary in signal_acc.items():
        values = values_by_signal.get(key, [])
        resolved = summary["resolved_count"]
        result_signal[key] = {
            "signal_count": int(summary["signal_count"]),
            "resolved_count": int(resolved),
            "avg_t1_close_return": round(float(sum(values) / len(values)), 4) if values else None,
            "win_rate": round(float(summary["positive_count"] / resolved * 100), 2) if resolved else None,
            "median_t1_close_return": None,
            "positive_count": int(summary["positive_count"]),
            "negative_count": int(summary["negative_count"]),
            "pending_count": int(summary["pending_count"]),
            "manual_scope_excluded_count": int(summary["manual_scope_excluded_count"]),
        }
    return {
        "pair_count": len(pairs),
        **{key: int(value) for key, value in totals.items()},
        "signal_type_summary": result_signal,
    }


def build_payload(start_date: str, end_date: str) -> dict:
    dates = _date_range(start_date, end_date)
    pairs = [build_pair(prev, date) for prev, date in zip(dates, dates[1:])]
    aggregate = aggregate_pairs(pairs)
    conclusions = [
        "multiday_t1_validation_completed",
        "code_keyed_join_used",
        "manual_scope_excluded_explicitly",
        "pending_ambiguity_preserved",
        "no_strategy_rule_change",
        "cp_evaluator_change_not_required",
        "trend_evaluator_change_not_required",
        "trend_active_kept_disabled",
        "lesson_pattern_not_written",
    ]
    if aggregate.get("total_fallback_name_join_count", 0) == 0:
        conclusions.append("name_fallback_eliminated")
    if aggregate.get("total_pending_blocked_count", 0) > 0:
        conclusions.append("chuangyeban_pending_ambiguity_preserved")
    signal_summary = aggregate.get("signal_type_summary", {})
    cp_comment = "CP T+1 observation is available under code-keyed/manual-scope denominator; keep as observation, not rule."
    trend_comment = "Trend T+1 observation is available, but Trend active remains disabled pending confirmation coverage and benchmark evidence."
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "date_range": {"start": start_date, "end": end_date},
        "pairs": pairs,
        "aggregate_summary": aggregate,
        "cp_observation": {
            "multi_day_t1_supported": bool(signal_summary),
            "comment": cp_comment,
        },
        "trend_observation": {
            "multi_day_t1_supported": bool(signal_summary),
            "trend_active_allowed": False,
            "comment": trend_comment,
        },
        "strategy_rule_change_required": False,
        "cp_evaluator_change_required": False,
        "trend_evaluator_change_required": False,
        "lesson_pattern_written": False,
        "recommended_next_actions": [
            "keep_chuangyeban_pending_ambiguity_explicit",
            "extend_code_keyed_t1_validation_to_more_closed_days",
            "do_not_write_lesson_or_pattern_until_repeated_evidence",
        ],
        "warnings": ["pending_rows_excluded_from_resolved_denominator"],
        "conclusion": conclusions,
    }


def write_outputs(payload: dict) -> tuple[Path, Path, Path]:
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    stem = f"multiday_t1_validation_{payload['date_range']['start']}_{payload['date_range']['end']}"
    json_path = EVAL_ROOT / f"{stem}.json"
    md_path = EVAL_ROOT / f"{stem}.md"
    output_dir = OUTPUT_ROOT / f"{payload['date_range']['start']}_{payload['date_range']['end']}"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    (output_dir / "multiday_t1_validation.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path, md_path, output_dir


def render_markdown(payload: dict) -> str:
    agg = payload["aggregate_summary"]
    lines = [
        f"# Multi-day T+1 Validation {payload['date_range']['start']} -> {payload['date_range']['end']}",
        "",
        f"- pair_count: `{agg['pair_count']}`",
        f"- total_candidate_count: `{agg.get('total_candidate_count', 0)}`",
        f"- total_resolved_code_denominator: `{agg.get('total_resolved_code_denominator', 0)}`",
        f"- total_manual_scope_excluded_count: `{agg.get('total_manual_scope_excluded_count', 0)}`",
        f"- total_pending_blocked_count: `{agg.get('total_pending_blocked_count', 0)}`",
        f"- total_primary_code_join_count: `{agg.get('total_primary_code_join_count', 0)}`",
        f"- total_fallback_name_join_count: `{agg.get('total_fallback_name_join_count', 0)}`",
        f"- total_unmatched_count: `{agg.get('total_unmatched_count', 0)}`",
        "",
        "## Signal Type Summary",
        "",
        json.dumps(agg["signal_type_summary"], ensure_ascii=False, indent=2),
        "",
        "## Conclusion",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["conclusion"])
    return "\n".join(lines) + "\n"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate multi-day T+1 validation with manual patch scope.")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    return parser.parse_args(argv)


def main(argv=None):
    configure_utf8_console()
    args = parse_args(argv)
    payload = build_payload(args.start_date, args.end_date)
    json_path, md_path, output_dir = write_outputs(payload)
    print(
        json.dumps(
            {
                "json": _display_path(json_path),
                "md": _display_path(md_path),
                "output_dir": _display_path(output_dir),
                "aggregate_summary": payload["aggregate_summary"],
                "conclusion": payload["conclusion"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
