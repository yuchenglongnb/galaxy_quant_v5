# -*- coding: utf-8 -*-
"""Harden trend confirmation reporting scope without changing evaluators."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.encoding import configure_utf8_console  # noqa: E402


EVAL_ROOT = ROOT / "reports" / "analysis" / "evaluations"
BENCHMARK_MAP_PATH = ROOT / "watchlists" / "group_benchmark_map.csv"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _has_git_diff(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        rel = str(path.relative_to(ROOT))
    except ValueError:
        rel = str(path)
    result = subprocess.run(
        ["git", "diff", "--quiet", "--", rel],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 1


def _scope_counts(normalization: dict) -> dict:
    counts = normalization.get("normalized_scope_counts") or {}
    return {
        "stock": int(counts.get("stock", 0) or 0),
        "etf": int(counts.get("etf", 0) or 0),
        "index": int(counts.get("index", 0) or 0),
        "industry_without_code": int(counts.get("industry_without_code", 0) or 0),
        "unknown": int(counts.get("unknown", 0) or 0),
    }


def _stock_reporting(normalization: dict) -> dict:
    after = normalization.get("after_normalization") or {}
    shadow = after.get("stock_shadow_distribution") or {}
    return {
        "denominator": int(after.get("stock_denominator", 0) or 0),
        "coverage_count": int(after.get("stock_coverage_count", 0) or 0),
        "rs_vs_index_coverage": float(after.get("stock_rs_vs_index_coverage", 0.0) or 0.0),
        "amount_1m_ratio_coverage": float(after.get("stock_amount_1m_ratio_coverage", 0.0) or 0.0),
        "rs_vs_etf_coverage": float(after.get("stock_rs_vs_etf_coverage", 0.0) or 0.0),
        "shadow_distribution": {
            "main": int(shadow.get("main", 0) or 0),
            "observe": int(shadow.get("observe", 0) or 0),
            "drop": int(shadow.get("drop", 0) or 0),
        },
    }


def _excluded(normalization: dict) -> dict:
    excluded = normalization.get("excluded_from_stock_denominator") or {}
    return {
        "etf_candidates": excluded.get("etf_candidates") or [],
        "industry_without_code": excluded.get("industry_without_code") or [],
        "unknown": excluded.get("unknown") or [],
    }


def build_payload(date: str) -> dict:
    date = str(date)
    normalization = _load_json(EVAL_ROOT / f"trend_confirmation_scope_normalization_{date}.json")
    manual_pack = _load_json(EVAL_ROOT / f"etf_benchmark_manual_review_pack_{date}.json")
    missing_groups = normalization.get("benchmark_map_missing_groups") or []
    existing_diff = _has_git_diff(BENCHMARK_MAP_PATH)
    warnings = []
    if existing_diff:
        warnings.append("existing_group_benchmark_map_diff_requires_separate_review")
    if manual_pack and not manual_pack.get("high_confidence_candidates"):
        warnings.append("no_high_confidence_benchmark_from_review_pack")

    return {
        "date": date,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "raw_candidate_count": int(normalization.get("raw_candidate_count", 0) or 0),
        "reporting_scope_counts": _scope_counts(normalization),
        "stock_level_reporting": _stock_reporting(normalization),
        "excluded_from_stock_reporting": _excluded(normalization),
        "remaining_reporting_blockers": {
            "benchmark_map_missing_groups": missing_groups,
        },
        "benchmark_map_modified": False,
        "benchmark_map_change_required": False,
        "existing_group_benchmark_map_diff_detected": bool(existing_diff),
        "trend_active_allowed": False,
        "evaluator_change_required": False,
        "manual_review_required": bool(missing_groups),
        "recommended_next_actions": [
            "use_hardened_stock_reporting_denominator",
            "keep_non_stock_candidates_out_of_stock_reporting",
            "review_existing_group_benchmark_map_diff_separately",
            "perform_benchmark_manual_review_before_any_map_patch",
            "keep_trend_active_disabled",
        ],
        "warnings": warnings,
        "conclusion": [
            "reporting_scope_hardened",
            "stock_denominator_normalized",
            "non_stock_candidate_excluded_from_stock_reporting",
            "industry_item_without_code_excluded",
            "benchmark_map_not_modified",
            "keep_trend_active_disabled",
            "no_strategy_rule_change",
            "evaluator_change_not_required",
        ],
    }


def _render_markdown(payload: dict) -> str:
    lines = [
        f"# Trend Confirmation Reporting Scope {payload['date']}",
        "",
        f"- raw_candidate_count: `{payload['raw_candidate_count']}`",
        f"- reporting_scope_counts: `{payload['reporting_scope_counts']}`",
        f"- stock_level_reporting: `{payload['stock_level_reporting']}`",
        f"- excluded_from_stock_reporting: `{payload['excluded_from_stock_reporting']}`",
        f"- remaining_reporting_blockers: `{payload['remaining_reporting_blockers']}`",
        f"- existing_group_benchmark_map_diff_detected: `{payload['existing_group_benchmark_map_diff_detected']}`",
        f"- benchmark_map_modified: `{payload['benchmark_map_modified']}`",
        f"- trend_active_allowed: `{payload['trend_active_allowed']}`",
        f"- evaluator_change_required: `{payload['evaluator_change_required']}`",
        "",
        "## Conclusion",
        "",
    ]
    for item in payload["conclusion"]:
        lines.append(f"- {item}")
    if payload["warnings"]:
        lines.extend(["", "## Warnings", ""])
        for item in payload["warnings"]:
            lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict) -> tuple[Path, Path]:
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = EVAL_ROOT / f"trend_confirmation_reporting_scope_{payload['date']}.json"
    md_path = EVAL_ROOT / f"trend_confirmation_reporting_scope_{payload['date']}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Harden trend confirmation reporting scope.")
    parser.add_argument("--date", required=True, help="Trade date YYYYMMDD")
    return parser.parse_args(argv)


def main(argv=None):
    configure_utf8_console()
    args = parse_args(argv)
    payload = build_payload(args.date)
    json_path, md_path = write_outputs(payload)
    print(
        json.dumps(
            {
                "json": str(json_path.relative_to(ROOT)),
                "md": str(md_path.relative_to(ROOT)),
                "raw_candidate_count": payload["raw_candidate_count"],
                "reporting_scope_counts": payload["reporting_scope_counts"],
                "stock_level_reporting": payload["stock_level_reporting"],
                "existing_group_benchmark_map_diff_detected": payload[
                    "existing_group_benchmark_map_diff_detected"
                ],
                "benchmark_map_modified": payload["benchmark_map_modified"],
                "trend_active_allowed": payload["trend_active_allowed"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
