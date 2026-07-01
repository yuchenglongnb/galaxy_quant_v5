# -*- coding: utf-8 -*-
"""Isolated min1 backfill wrapper for trend confirmation availability."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import evaluate_intraday_confirmation_availability as availability  # noqa: E402
from utils.encoding import configure_utf8_console  # noqa: E402


EVAL_ROOT = ROOT / "reports" / "analysis" / "evaluations"


def _generated_files(date: str) -> list[str]:
    intraday_dir = ROOT / "AmazingData_Store" / str(date) / "intraday"
    files = []
    for name in ("stocks_1min.csv", "etf_1min.csv", "indices_1min.csv", "stock_confirmation_latest.csv"):
        path = intraday_dir / name
        if path.exists():
            files.append(str(path.relative_to(ROOT)))
    return files


def _codes_from_candidate_status(candidate_status: dict) -> tuple[set[str], list[str]]:
    queryable = set()
    industry_without_code = []
    for row in candidate_status.get("matched_samples", []) or []:
        for code in row.get("codes", []) or []:
            if code:
                queryable.add(str(code))
    for row in candidate_status.get("unmatched_samples", []) or []:
        target_type = str(row.get("target_type", "") or "").lower()
        if target_type in {"industry", "行业"} or "行业" in target_type:
            industry_without_code.append(str(row.get("name", "") or ""))
    return queryable, industry_without_code


def _intraday_codes(date: str) -> set[str]:
    intraday_dir = ROOT / "AmazingData_Store" / str(date) / "intraday"
    codes = set()
    for filename in ("stocks_1min.csv", "etf_1min.csv", "indices_1min.csv", "stock_confirmation_latest.csv"):
        for row in availability._safe_read_csv(intraday_dir / filename):
            code = str(row.get("code", "") or "").strip()
            if code:
                codes.add(code)
    return codes


def _default_runner(date: str, scope: str, batch_size: int, force: bool) -> dict:
    from scripts.backfill_intraday_confirmation import run_backfill  # noqa: WPS433

    if scope == "trend-candidates":
        return run_backfill(
            int(date),
            execute=True,
            force=force,
            stage="all",
            max_stocks=0,
            only_codes=[],
            begin_time=930,
            end_time=935,
            batch_size=batch_size,
            skip_existing=False,
            warn_after_sec=60.0,
            isolated_query=True,
            selection_priority="trend_score",
        )
    if scope == "auction-universe":
        return run_backfill(
            int(date),
            execute=True,
            force=force,
            stage="all",
            max_stocks=0,
            only_codes=[],
            begin_time=930,
            end_time=935,
            batch_size=batch_size,
            skip_existing=False,
            warn_after_sec=60.0,
            isolated_query=True,
            selection_priority="original",
        )
    raise ValueError(f"unsupported scope: {scope}")


def build_payload(
    date: str,
    scope: str = "trend-candidates",
    batch_size: int = 5,
    force: bool = True,
    runner: Callable[[str, str, int, bool], dict] | None = None,
) -> dict:
    date = str(date)
    availability.ROOT = ROOT
    runner = runner or _default_runner
    before = availability.build_payload(date)
    queryable_codes, industry_without_code = _codes_from_candidate_status(before["candidate_code_match_status"])

    payload = {
        "date": date,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scope": scope,
        "target_time": "09:35",
        "query_window": "09:30-09:35",
        "candidate_count": int(before.get("candidate_count", 0) or 0),
        "queryable_candidate_count": len(queryable_codes),
        "industry_item_without_code": industry_without_code,
        "before": {
            "intraday_confirmation_available": bool(before.get("intraday_confirmation_available", False)),
            "coverage_count": int(before.get("coverage_count", 0) or 0),
            "root_cause": before.get("root_cause", ""),
        },
        "backfill": {
            "attempted": True,
            "success_count": 0,
            "failed_count": len(queryable_codes),
            "partial_success": False,
            "generated_files": [],
            "failed_codes": sorted(queryable_codes),
            "warnings": [],
            "runner_result": {},
        },
        "after": {
            "intraday_confirmation_available": False,
            "coverage_count": 0,
        },
        "root_cause_after": "",
        "trend_active_allowed": False,
        "recommended_next_actions": [],
        "conclusion": [
            "read_only_rule_state",
            "keep_trend_active_disabled",
            "no_strategy_rule_change",
            "do_not_fabricate_intraday_confirmation",
        ],
    }

    try:
        runner_result = runner(date, scope, batch_size, force)
        payload["backfill"]["runner_result"] = runner_result
    except Exception as exc:
        payload["backfill"]["warnings"].append(f"kline_query_failed:{exc}")
        payload["recommended_next_actions"].append("inspect_amazingdata_min1_query_failure")

    after = availability.build_payload(date)
    generated = _generated_files(date)
    available_codes = _intraday_codes(date)
    successful_codes = sorted(code for code in queryable_codes if code in available_codes)
    failed_codes = sorted(code for code in queryable_codes if code not in available_codes)
    payload["backfill"].update(
        {
            "success_count": len(successful_codes),
            "failed_count": len(failed_codes),
            "partial_success": bool(successful_codes and failed_codes),
            "generated_files": generated,
            "failed_codes": failed_codes,
            "successful_codes": successful_codes,
        }
    )
    payload["after"] = {
        "intraday_confirmation_available": bool(after.get("intraday_confirmation_available", False)),
        "coverage_count": int(after.get("coverage_count", 0) or 0),
    }
    payload["root_cause_after"] = after.get("root_cause", "")
    if payload["after"]["coverage_count"] > 0:
        payload["conclusion"].extend(
            [
                "stock_intraday_minute_backfilled",
                "intraday_confirmation_coverage_recovered",
            ]
        )
        payload["recommended_next_actions"].extend(
            [
                "rerun_trend_confirmation_coverage_audit",
                "keep_trend_active_disabled_until_multi_day_coverage_validation",
            ]
        )
    else:
        payload["conclusion"].extend(
            [
                "stock_intraday_minute_backfill_failed",
                "intraday_confirmation_still_blocked_by_data",
            ]
        )
        payload["recommended_next_actions"].append("retry_isolated_query_or_inspect_min1_source_availability")
    return payload


def _render_markdown(payload: dict) -> str:
    lines = [
        f"# Intraday Min1 Backfill {payload['date']}",
        "",
        f"- scope: `{payload['scope']}`",
        f"- target_time: `{payload['target_time']}`",
        f"- query_window: `{payload['query_window']}`",
        f"- candidate_count: `{payload['candidate_count']}`",
        f"- queryable_candidate_count: `{payload['queryable_candidate_count']}`",
        f"- industry_item_without_code: `{payload['industry_item_without_code']}`",
        "",
        "## Before / After",
        "",
        f"- before coverage_count: `{payload['before']['coverage_count']}`",
        f"- after coverage_count: `{payload['after']['coverage_count']}`",
        f"- root_cause_after: `{payload['root_cause_after']}`",
        f"- trend_active_allowed: `{payload['trend_active_allowed']}`",
        "",
        "## Backfill",
        "",
        f"- attempted: `{payload['backfill']['attempted']}`",
        f"- success_count: `{payload['backfill']['success_count']}`",
        f"- failed_count: `{payload['backfill']['failed_count']}`",
        f"- partial_success: `{payload['backfill']['partial_success']}`",
        f"- generated_files: `{payload['backfill']['generated_files']}`",
        f"- failed_codes: `{payload['backfill']['failed_codes']}`",
        f"- warnings: `{payload['backfill']['warnings']}`",
        "",
        "## Conclusion",
        "",
    ]
    for item in payload["conclusion"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Recommended Next Actions", ""])
    for item in payload["recommended_next_actions"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict) -> tuple[Path, Path]:
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = EVAL_ROOT / f"intraday_min1_backfill_{payload['date']}.json"
    md_path = EVAL_ROOT / f"intraday_min1_backfill_{payload['date']}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Backfill intraday min1 confirmation for one date.")
    parser.add_argument("--date", required=True, help="Trade date YYYYMMDD")
    parser.add_argument("--scope", choices=["trend-candidates", "auction-universe"], default="trend-candidates")
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--no-force", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    configure_utf8_console()
    args = parse_args(argv)
    payload = build_payload(
        args.date,
        scope=args.scope,
        batch_size=args.batch_size,
        force=not args.no_force,
    )
    json_path, md_path = write_outputs(payload)
    print(
        json.dumps(
            {
                "json": str(json_path.relative_to(ROOT)),
                "md": str(md_path.relative_to(ROOT)),
                "scope": payload["scope"],
                "candidate_count": payload["candidate_count"],
                "queryable_candidate_count": payload["queryable_candidate_count"],
                "success_count": payload["backfill"]["success_count"],
                "failed_count": payload["backfill"]["failed_count"],
                "before_coverage_count": payload["before"]["coverage_count"],
                "after_coverage_count": payload["after"]["coverage_count"],
                "root_cause_after": payload["root_cause_after"],
                "trend_active_allowed": payload["trend_active_allowed"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
