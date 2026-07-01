# -*- coding: utf-8 -*-
"""Attribute 20260629 trend confirmation shadow decisions after min1 backfill."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.auction import AuctionAnalyzer  # noqa: E402
from core.data_manager import DataManager  # noqa: E402
from core.intraday_confirmation import IntradayConfirmationBuilder  # noqa: E402
from scripts import diagnose_trend_gate_coverage as trend_diag  # noqa: E402
from utils.encoding import configure_utf8_console  # noqa: E402


EVAL_ROOT = ROOT / "reports" / "analysis" / "evaluations"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _ratio(numerator: int, denominator: int) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 0.0


def _present(value) -> bool:
    if value in (None, ""):
        return False
    text = str(value).strip().lower()
    return text not in {"", "nan", "none", "null"}


def _rows_for_date(date: str) -> list[dict]:
    dm = DataManager()
    analyzer = AuctionAnalyzer(dm)
    result = analyzer.analyze(int(date), realtime=False)
    signals = list(((result.get("signals") or {}).get("trend")) or [])
    benchmark_map = IntradayConfirmationBuilder._normalize_benchmark_map(
        IntradayConfirmationBuilder.load_benchmark_map()
    )
    return [trend_diag._candidate_row(signal, benchmark_map) for signal in signals]


def _coverage(rows: list[dict]) -> dict:
    total = len(rows)
    return {
        "rs_vs_index_coverage": _ratio(sum(_present(row.get("rs_vs_index_pct")) for row in rows), total),
        "amount_1m_ratio_coverage": _ratio(sum(_present(row.get("amount_1m_ratio")) for row in rows), total),
        "rs_vs_etf_coverage": _ratio(sum(_present(row.get("rs_vs_etf_pct")) for row in rows), total),
    }


def _blocking_rows(rows: list[dict]) -> list[dict]:
    output = []
    for row in rows:
        output.append(
            {
                "code": row.get("code", ""),
                "name": row.get("name", ""),
                "target_type": row.get("target_type", ""),
                "group": row.get("group", ""),
                "shadow": row.get("trend_gate_decision_shadow", ""),
                "primary_blocker": row.get("primary_blocker", ""),
                "risk_flags": row.get("shadow_risk_flags", []),
                "missing_fields": row.get("shadow_missing_fields", []),
                "rs_vs_etf_pct": row.get("rs_vs_etf_pct"),
                "rs_vs_index_pct": row.get("rs_vs_index_pct"),
                "amount_1m_ratio": row.get("amount_1m_ratio"),
                "benchmark_etf_code": row.get("benchmark_etf_code", ""),
                "benchmark_index_code": row.get("benchmark_index_code", ""),
                "leading_cluster_status": row.get("leading_cluster_status", ""),
                "leading_cluster_name": row.get("leading_cluster_name", ""),
            }
        )
    return output


def _etf_benchmark_coverage(rows: list[dict], backfill: dict) -> dict:
    stock_rows = [row for row in rows if str(row.get("target_type", "")).lower() == "stock"]
    covered = [row for row in stock_rows if row.get("benchmark_etf_code")]
    missing = [row for row in stock_rows if not row.get("benchmark_etf_code")]
    failed_codes = list(((backfill.get("backfill") or {}).get("failed_codes")) or [])
    return {
        "covered_count": len(covered),
        "missing_count": len(missing),
        "coverage_ratio": _ratio(len(covered), len(stock_rows)),
        "missing_or_failed_codes": sorted(
            set(failed_codes + [row.get("code", "") for row in missing if row.get("code")])
        ),
        "missing_groups": sorted({row.get("group", "") for row in missing if row.get("group")}),
    }


def _failed_code_analysis(backfill: dict, rows: list[dict]) -> dict:
    failed_codes = list(((backfill.get("backfill") or {}).get("failed_codes")) or [])
    by_code = {str(row.get("code", "")): row for row in rows if row.get("code")}
    result = {}
    for code in failed_codes:
        row = by_code.get(str(code), {})
        target_type = str(row.get("target_type", "") or "")
        is_etf = target_type == "ETF" or str(code).endswith((".SZ", ".SH")) and str(code).startswith(("15", "51"))
        result[str(code)] = {
            "name": row.get("name", ""),
            "reason": "trend_etf_candidate_not_in_stock_confirmation_latest" if is_etf else "query_or_mapping_failed",
            "is_stock": target_type == "stock",
            "is_etf": bool(is_etf),
            "recommended_action": (
                "audit_etf_candidate_confirmation_scope_or_exclude_non_stock_from_stock_confirmation"
                if is_etf
                else "inspect_stock_min1_query"
            ),
        }
    return result


def _industry_without_code(backfill: dict, rows: list[dict]) -> list[str]:
    existing = list(backfill.get("industry_item_without_code") or [])
    if existing:
        return existing
    return [
        row.get("name", "")
        for row in rows
        if str(row.get("target_type", "")).lower() in {"industry", "行业"} and not row.get("code")
    ]


def _root_cause_refined(rows: list[dict], coverage: dict, shadow: dict) -> str:
    if int(shadow.get("main", 0) or 0) == 0 and rows:
        if float(coverage.get("rs_vs_etf_coverage", 0.0) or 0.0) < 0.5:
            return "main_not_confirmed_after_data_recovery_etf_coverage_insufficient"
        return "main_not_confirmed_after_data_recovery"
    return "main_available_or_no_trend_candidates"


def build_payload(date: str) -> dict:
    date = str(date)
    rows = _rows_for_date(date)
    backfill = _load_json(EVAL_ROOT / f"intraday_min1_backfill_{date}.json")
    availability = _load_json(EVAL_ROOT / f"intraday_confirmation_availability_{date}.json")
    recent = _load_json(EVAL_ROOT / f"recent_trend_confirmation_coverage_{date}_{date}.json")

    shadow_counter = Counter(row.get("trend_gate_decision_shadow", "") for row in rows)
    shadow_distribution = {
        "main": int(shadow_counter.get("main", 0) or 0),
        "observe": int(shadow_counter.get("observe", 0) or 0),
        "drop": int(shadow_counter.get("drop", 0) or 0),
    }
    coverage = (recent.get("coverage_summary") or {}) if recent else _coverage(rows)
    blocker_counter = Counter(row.get("primary_blocker", "") for row in rows)
    blocking_rows = _blocking_rows(rows)
    etf_coverage = _etf_benchmark_coverage(rows, backfill)
    industry_items = _industry_without_code(backfill, rows)
    root_cause = _root_cause_refined(rows, coverage, shadow_distribution)

    conclusions = [
        "keep_trend_active_disabled",
        "no_strategy_rule_change",
        "read_only_audit",
        "evaluator_change_not_required",
    ]
    if float(coverage.get("rs_vs_etf_coverage", 0.0) or 0.0) < 0.5:
        conclusions.append("etf_benchmark_coverage_insufficient")
    if shadow_distribution["main"] == 0:
        conclusions.append("main_not_confirmed_after_data_recovery")
    if industry_items:
        conclusions.append("industry_item_without_code_excluded")

    return {
        "date": date,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_count": len(rows),
        "queryable_candidate_count": int(backfill.get("queryable_candidate_count", 0) or 0),
        "coverage_count": int((availability.get("coverage_count", 0) or 0)),
        "shadow_distribution": shadow_distribution,
        "coverage": {
            "rs_vs_index_coverage": float(coverage.get("rs_vs_index_coverage", 0.0) or 0.0),
            "amount_1m_ratio_coverage": float(coverage.get("amount_1m_ratio_coverage", 0.0) or 0.0),
            "rs_vs_etf_coverage": float(coverage.get("rs_vs_etf_coverage", 0.0) or 0.0),
        },
        "blocking_reason_counts": dict(blocker_counter),
        "blocking_reason_by_candidate": blocking_rows,
        "observe_candidates": [row for row in blocking_rows if row.get("shadow") == "observe"],
        "drop_candidates": [row for row in blocking_rows if row.get("shadow") == "drop"],
        "etf_benchmark_coverage": etf_coverage,
        "failed_code_analysis": _failed_code_analysis(backfill, rows),
        "industry_item_without_code": industry_items,
        "root_cause_refined": root_cause,
        "trend_active_allowed": False,
        "evaluator_change_required": False,
        "recommended_next_actions": [
            "do_not_open_trend_active_mode",
            "audit_or_expand_high_confidence_etf_benchmark_mapping",
            "separate_non_stock_trend_candidate_confirmation_scope",
            "run_multi_day_confirmation_coverage_validation",
        ],
        "warnings": [
            "confirmation_recovered_but_shadow_main_zero",
        ],
        "conclusion": conclusions,
    }


def _render_markdown(payload: dict) -> str:
    lines = [
        f"# Trend Confirmation Shadow Attribution {payload['date']}",
        "",
        "## Core Status",
        "",
        f"- candidate_count: `{payload['candidate_count']}`",
        f"- queryable_candidate_count: `{payload['queryable_candidate_count']}`",
        f"- coverage_count: `{payload['coverage_count']}`",
        f"- shadow_distribution: `{payload['shadow_distribution']}`",
        f"- coverage: `{payload['coverage']}`",
        f"- root_cause_refined: `{payload['root_cause_refined']}`",
        f"- trend_active_allowed: `{payload['trend_active_allowed']}`",
        f"- evaluator_change_required: `{payload['evaluator_change_required']}`",
        "",
        "## Blocking Reasons",
        "",
    ]
    for key, value in sorted(payload["blocking_reason_counts"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Observe Candidates", ""])
    for row in payload["observe_candidates"]:
        lines.append(f"- {row['code'] or '-'} {row['name']}: {row['primary_blocker']}")
    lines.extend(["", "## Drop Candidates", ""])
    for row in payload["drop_candidates"]:
        lines.append(f"- {row['code'] or '-'} {row['name']}: {row['primary_blocker']}")
    lines.extend(
        [
            "",
            "## ETF Benchmark Coverage",
            "",
            f"- {payload['etf_benchmark_coverage']}",
            "",
            "## Failed Code Analysis",
            "",
            f"- {payload['failed_code_analysis']}",
            "",
            "## Conclusion",
            "",
        ]
    )
    for item in payload["conclusion"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict) -> tuple[Path, Path]:
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = EVAL_ROOT / f"trend_confirmation_shadow_attribution_{payload['date']}.json"
    md_path = EVAL_ROOT / f"trend_confirmation_shadow_attribution_{payload['date']}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate trend confirmation shadow attribution.")
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
                "candidate_count": payload["candidate_count"],
                "coverage_count": payload["coverage_count"],
                "shadow_distribution": payload["shadow_distribution"],
                "root_cause_refined": payload["root_cause_refined"],
                "trend_active_allowed": payload["trend_active_allowed"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
