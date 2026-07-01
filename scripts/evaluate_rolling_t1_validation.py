# -*- coding: utf-8 -*-
"""Rolling code-keyed T+1 validation over closed days."""

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
CODE_BACKFILLED_ROOT = ROOT / "reports" / "validation" / "derived" / "signal_detail_code_backfilled"
ORIGINAL_DAILY_ROOT = ROOT / "reports" / "validation" / "daily"
EVAL_ROOT = ROOT / "reports" / "analysis" / "evaluations"
OUTPUT_ROOT = ROOT / "reports" / "t1_backtest" / "rolling_validation"


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


def select_signal_detail(date: str) -> dict:
    candidates = [
        ("manual_code_patch", MANUAL_PATCH_ROOT / f"{date}_signal_detail.manual_code_patch.csv", False),
        ("code_backfilled", CODE_BACKFILLED_ROOT / f"{date}_signal_detail.code_backfilled.csv", False),
        ("original_signal_detail", ORIGINAL_DAILY_ROOT / date / "signal_detail.csv", True),
    ]
    for quality, path, degraded in candidates:
        if path.exists():
            return {
                "date": date,
                "input_file": _display_path(path),
                "input_quality": quality,
                "input_quality_degraded": degraded,
                "path": path,
            }
    return {
        "date": date,
        "input_file": "",
        "input_quality": "missing",
        "input_quality_degraded": True,
        "path": None,
    }


def signal_key(row: pd.Series) -> str:
    for col in ("signal_family", "signal_type", "signal_category"):
        if col in row and pd.notna(row.get(col)):
            return str(row.get(col))
    return ""


def _bool_series(frame: pd.DataFrame, col: str, value: str) -> pd.Series:
    if col not in frame.columns:
        return pd.Series(False, index=frame.index)
    return frame[col].fillna("").astype(str) == value


def join_pair(prev_date: str, date: str) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    selection = select_signal_detail(prev_date)
    detail = read_csv(selection["path"]) if selection["path"] else pd.DataFrame()
    if detail.empty:
        return detail, {
            **selection,
            "candidate_count": 0,
            "resolved_code_denominator": 0,
            "manual_scope_excluded_count": 0,
            "pending_blocked_count": 0,
            "primary_code_join_count": 0,
            "fallback_name_join_count": 0,
            "unmatched_count": 0,
            "quality": "empty_or_missing_input",
        }, pd.DataFrame()
    if "code" not in detail.columns:
        detail["code"] = ""
    detail["code"] = detail["code"].fillna("").astype(str)
    manual_excluded = _bool_series(detail, "manual_resolution_scope", "industry_without_code")
    pending = _bool_series(detail, "manual_resolution_status", "pending")
    resolved = detail[~manual_excluded & ~pending].copy()
    ret = next_returns(date)
    by_code = ret[ret["code"].astype(str) != ""].drop_duplicates("code") if not ret.empty and "code" in ret.columns else pd.DataFrame()
    joined = resolved.merge(
        by_code[["code", "t1_open_return", "t1_close_return"]] if not by_code.empty else pd.DataFrame(columns=["code", "t1_open_return", "t1_close_return"]),
        on="code",
        how="left",
    )
    joined["t1_join_method"] = joined["t1_close_return"].notna().map(lambda ok: "code" if ok else "unmatched")
    joined["signal_type_key"] = joined.apply(signal_key, axis=1) if not joined.empty else []
    primary = int((joined["t1_join_method"] == "code").sum()) if not joined.empty else 0
    fallback = 0
    unmatched = int((joined["t1_join_method"] == "unmatched").sum()) if not joined.empty else 0
    if unmatched == 0 and fallback == 0:
        quality = "code_keyed_complete"
    elif unmatched == 0:
        quality = "complete_with_explicit_fallback"
    else:
        quality = "partial"
    return detail, {
        **selection,
        "candidate_count": int(len(detail)),
        "resolved_code_denominator": int(len(resolved)),
        "manual_scope_excluded_count": int(manual_excluded.sum()),
        "pending_blocked_count": int(pending.sum()),
        "primary_code_join_count": primary,
        "fallback_name_join_count": fallback,
        "unmatched_count": unmatched,
        "quality": quality,
    }, joined


def _empty_summary() -> dict:
    return {
        "signal_count": 0,
        "resolved_count": 0,
        "avg_t1_close_return": None,
        "median_t1_close_return": None,
        "win_rate": None,
        "positive_count": 0,
        "negative_count": 0,
        "pending_count": 0,
        "manual_scope_excluded_count": 0,
    }


def summarize_signal_types(joined: pd.DataFrame, detail: pd.DataFrame) -> dict:
    result = {}
    keys = set()
    if not joined.empty:
        keys |= set(joined["signal_type_key"].dropna().astype(str).tolist())
    if not detail.empty:
        keys |= set(detail.apply(signal_key, axis=1).dropna().astype(str).tolist())
    for key in sorted(keys):
        group = joined[joined["signal_type_key"] == key] if not joined.empty else pd.DataFrame()
        close_ret = pd.to_numeric(group.get("t1_close_return", pd.Series(dtype=float)), errors="coerce").dropna()
        result[key] = {
            "signal_count": int(len(group)),
            "resolved_count": int(len(close_ret)),
            "avg_t1_close_return": round(float(close_ret.mean()), 4) if not close_ret.empty else None,
            "median_t1_close_return": round(float(close_ret.median()), 4) if not close_ret.empty else None,
            "win_rate": round(float((close_ret > 0).mean() * 100), 2) if not close_ret.empty else None,
            "positive_count": int((close_ret > 0).sum()),
            "negative_count": int((close_ret < 0).sum()),
            "pending_count": 0,
            "manual_scope_excluded_count": 0,
        }
    if not detail.empty:
        pending = _bool_series(detail, "manual_resolution_status", "pending")
        excluded = _bool_series(detail, "manual_resolution_scope", "industry_without_code")
        for key, group in detail[pending].groupby(detail[pending].apply(signal_key, axis=1), dropna=False):
            result.setdefault(str(key), _empty_summary())
            result[str(key)]["pending_count"] += int(len(group))
        for key, group in detail[excluded].groupby(detail[excluded].apply(signal_key, axis=1), dropna=False):
            result.setdefault(str(key), _empty_summary())
            result[str(key)]["manual_scope_excluded_count"] += int(len(group))
    return result


def build_pair(prev_date: str, date: str) -> dict:
    detail, quality, joined = join_pair(prev_date, date)
    quality.pop("path", None)
    return {
        "prev_date": prev_date,
        "date": date,
        "input_signal_detail": quality.pop("input_file"),
        "input_quality": quality.pop("input_quality"),
        "input_quality_degraded": quality.pop("input_quality_degraded"),
        "join_quality": quality,
        "signal_type_summary": summarize_signal_types(joined, detail),
    }


def aggregate_pairs(pairs: list[dict]) -> tuple[dict, dict]:
    join = Counter()
    signal = defaultdict(_empty_summary)
    returns = defaultdict(list)
    for pair in pairs:
        q = pair["join_quality"]
        join["total_candidate_count"] += q["candidate_count"]
        join["total_resolved_code_denominator"] += q["resolved_code_denominator"]
        join["total_manual_scope_excluded_count"] += q["manual_scope_excluded_count"]
        join["total_pending_blocked_count"] += q["pending_blocked_count"]
        join["total_primary_code_join_count"] += q["primary_code_join_count"]
        join["total_fallback_name_join_count"] += q["fallback_name_join_count"]
        join["total_unmatched_count"] += q["unmatched_count"]
        for key, summary in pair["signal_type_summary"].items():
            agg = signal[key]
            for field in ("signal_count", "resolved_count", "positive_count", "negative_count", "pending_count", "manual_scope_excluded_count"):
                agg[field] += summary[field]
            if summary["avg_t1_close_return"] is not None:
                returns[key].extend([summary["avg_t1_close_return"]] * max(summary["resolved_count"], 1))
    join_quality = {
        **{key: int(value) for key, value in join.items()},
        "all_pairs_code_keyed_complete": all(pair["join_quality"]["quality"] == "code_keyed_complete" for pair in pairs),
    }
    signal_summary = {}
    for key, summary in signal.items():
        vals = returns.get(key, [])
        resolved = summary["resolved_count"]
        signal_summary[key] = {
            "signal_count": int(summary["signal_count"]),
            "resolved_count": int(resolved),
            "avg_t1_close_return": round(float(sum(vals) / len(vals)), 4) if vals else None,
            "median_t1_close_return": None,
            "win_rate": round(float(summary["positive_count"] / resolved * 100), 2) if resolved else None,
            "positive_count": int(summary["positive_count"]),
            "negative_count": int(summary["negative_count"]),
            "pending_count": int(summary["pending_count"]),
            "manual_scope_excluded_count": int(summary["manual_scope_excluded_count"]),
        }
    return join_quality, signal_summary


def observation_for_signal(name: str, summary: dict) -> dict:
    sample = int(summary.get("resolved_count", 0) or 0)
    avg = summary.get("avg_t1_close_return")
    win = summary.get("win_rate")
    if sample == 0:
        obs = "No resolved code-keyed T+1 sample."
    else:
        obs = f"Resolved code-keyed sample={sample}, avg_t1_close={avg}, win_rate={win}; observation only."
    payload = {
        "sample_size": sample,
        "avg_t1_close_return": avg,
        "win_rate": win,
        "observation": obs,
        "rule_change_supported": False,
    }
    if name == "趋势机会":
        payload["trend_active_supported"] = False
    return payload


def build_payload(start_date: str, end_date: str) -> dict:
    dates = _date_range(start_date, end_date)
    pairs = [build_pair(prev, date) for prev, date in zip(dates, dates[1:])]
    aggregate_join_quality, signal_summary = aggregate_pairs(pairs)
    observations = {
        key: observation_for_signal(key, signal_summary.get(key, _empty_summary()))
        for key in ("CP风险", "反核机会", "趋势机会")
    }
    conclusions = [
        "rolling_t1_validation_completed",
        "code_keyed_join_used",
        "pending_ambiguity_preserved",
        "manual_scope_excluded_explicitly",
        "sample_size_insufficient_for_rule_change",
        "no_strategy_rule_change",
        "cp_evaluator_change_not_required",
        "trend_evaluator_change_not_required",
        "trend_active_kept_disabled",
        "lesson_pattern_not_written",
    ]
    if aggregate_join_quality.get("total_fallback_name_join_count", 0) == 0:
        conclusions.append("name_fallback_eliminated")
    if aggregate_join_quality.get("total_unmatched_count", 0) == 0:
        conclusions.append("unmatched_eliminated")
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "date_range": {"start": start_date, "end": end_date},
        "pair_count": len(pairs),
        "pairs": pairs,
        "aggregate_join_quality": aggregate_join_quality,
        "signal_type_aggregate_summary": signal_summary,
        "observations": observations,
        "sample_size_sufficient_for_rule_change": False,
        "strategy_rule_change_required": False,
        "cp_evaluator_change_required": False,
        "trend_evaluator_change_required": False,
        "lesson_pattern_written": False,
        "recommended_next_actions": [
            "extend_rolling_code_keyed_t1_validation_to_more_closed_days",
            "keep_pending_ambiguity_explicit",
            "do_not_change_rules_until_sample_size_and_confirmation_evidence_are_sufficient",
        ],
        "warnings": ["observation_only_not_rule_change"],
        "conclusion": conclusions,
    }


def write_outputs(payload: dict) -> tuple[Path, Path, Path]:
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    start = payload["date_range"]["start"]
    end = payload["date_range"]["end"]
    stem = f"rolling_t1_validation_{start}_{end}"
    json_path = EVAL_ROOT / f"{stem}.json"
    md_path = EVAL_ROOT / f"{stem}.md"
    output_dir = OUTPUT_ROOT / f"{start}_{end}"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    (output_dir / "rolling_t1_validation.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path, md_path, output_dir


def render_markdown(payload: dict) -> str:
    lines = [
        f"# Rolling T+1 Validation {payload['date_range']['start']} -> {payload['date_range']['end']}",
        "",
        f"- pair_count: `{payload['pair_count']}`",
        f"- aggregate_join_quality: `{payload['aggregate_join_quality']}`",
        "",
        "## Signal Type Aggregate Summary",
        "",
        json.dumps(payload["signal_type_aggregate_summary"], ensure_ascii=False, indent=2),
        "",
        "## Observations",
        "",
        json.dumps(payload["observations"], ensure_ascii=False, indent=2),
        "",
        "## Conclusion",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["conclusion"])
    return "\n".join(lines) + "\n"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate rolling code-keyed T+1 validation.")
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
                "aggregate_join_quality": payload["aggregate_join_quality"],
                "signal_type_aggregate_summary": payload["signal_type_aggregate_summary"],
                "conclusion": payload["conclusion"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
