# -*- coding: utf-8 -*-
"""Normalize trend confirmation denominator by candidate scope."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
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


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            with path.open("r", encoding=encoding, newline="") as fh:
                return list(csv.DictReader(fh))
        except UnicodeDecodeError:
            continue
        except Exception:
            return []
    return []


def _norm_type(value) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if lowered in {"stock", "个股"}:
        return "stock"
    if lowered == "etf":
        return "etf"
    if lowered in {"index", "指数"}:
        return "index"
    if lowered in {"industry", "行业"}:
        return "industry"
    return "unknown"


def _present(value) -> bool:
    if value in (None, ""):
        return False
    return str(value).strip().lower() not in {"", "nan", "none", "null"}


def _ratio(numerator: int, denominator: int) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 0.0


def _confirmation_codes(date: str) -> set[str]:
    path = ROOT / "AmazingData_Store" / date / "intraday" / "stock_confirmation_latest.csv"
    return {str(row.get("code", "") or "").strip() for row in _read_csv(path) if str(row.get("code", "") or "").strip()}


def _scope_counts(rows: list[dict]) -> dict:
    counter = Counter()
    for row in rows:
        scope = _norm_type(row.get("target_type"))
        if scope == "industry" and not row.get("code"):
            counter["industry_without_code"] += 1
        elif scope in {"stock", "etf", "index"}:
            counter[scope] += 1
        else:
            counter["unknown"] += 1
    return {
        "stock": int(counter.get("stock", 0)),
        "etf": int(counter.get("etf", 0)),
        "index": int(counter.get("index", 0)),
        "industry_without_code": int(counter.get("industry_without_code", 0)),
        "unknown": int(counter.get("unknown", 0)),
    }


def _excluded(rows: list[dict]) -> dict:
    result = {"etf_candidates": [], "industry_without_code": [], "unknown": []}
    for row in rows:
        scope = _norm_type(row.get("target_type"))
        record = {
            "code": row.get("code", ""),
            "name": row.get("name", ""),
            "target_type": row.get("target_type", ""),
            "primary_blocker": row.get("primary_blocker", ""),
        }
        if scope == "etf":
            result["etf_candidates"].append(record)
        elif scope == "industry" and not row.get("code"):
            result["industry_without_code"].append(record)
        elif scope == "unknown":
            result["unknown"].append(record)
    return result


def _shadow_distribution(rows: list[dict]) -> dict:
    counter = Counter(str(row.get("shadow", "") or row.get("trend_gate_decision_shadow", "") or "") for row in rows)
    return {
        "main": int(counter.get("main", 0)),
        "observe": int(counter.get("observe", 0)),
        "drop": int(counter.get("drop", 0)),
    }


def _stock_after(rows: list[dict], confirmation_codes: set[str]) -> dict:
    stock_rows = [row for row in rows if _norm_type(row.get("target_type")) == "stock"]
    denominator = len(stock_rows)
    coverage_count = sum(str(row.get("code", "") or "") in confirmation_codes for row in stock_rows)
    return {
        "stock_denominator": denominator,
        "stock_coverage_count": int(coverage_count),
        "stock_rs_vs_index_coverage": _ratio(sum(_present(row.get("rs_vs_index_pct")) for row in stock_rows), denominator),
        "stock_amount_1m_ratio_coverage": _ratio(sum(_present(row.get("amount_1m_ratio")) for row in stock_rows), denominator),
        "stock_rs_vs_etf_coverage": _ratio(sum(_present(row.get("rs_vs_etf_pct")) for row in stock_rows), denominator),
        "stock_shadow_distribution": _shadow_distribution(stock_rows),
    }


def _benchmark_missing_groups(rows: list[dict]) -> list[str]:
    groups = {
        str(row.get("group", "") or "")
        for row in rows
        if _norm_type(row.get("target_type")) == "stock"
        and not str(row.get("benchmark_etf_code", "") or "")
        and str(row.get("group", "") or "")
    }
    return sorted(groups)


def build_payload(date: str) -> dict:
    date = str(date)
    attribution = _load_json(EVAL_ROOT / f"trend_confirmation_shadow_attribution_{date}.json")
    scope = _load_json(EVAL_ROOT / f"trend_etf_benchmark_scope_{date}.json")
    recent = _load_json(EVAL_ROOT / f"recent_trend_confirmation_coverage_{date}_{date}.json")
    rows = list(attribution.get("blocking_reason_by_candidate") or [])
    before_coverage = recent.get("coverage_summary") or attribution.get("coverage") or {}
    before_shadow = attribution.get("shadow_distribution") or {}
    confirmation_codes = _confirmation_codes(date)
    after = _stock_after(rows, confirmation_codes)
    missing_groups = scope.get("stock_etf_benchmark_coverage", {}).get("missing_groups") or _benchmark_missing_groups(rows)

    conclusion = [
        "keep_trend_active_disabled",
        "no_strategy_rule_change",
        "read_only_scope_audit",
        "evaluator_change_not_required",
        "benchmark_map_not_modified",
        "non_stock_candidate_excluded_from_stock_denominator",
        "industry_item_without_code_excluded",
    ]
    if missing_groups:
        conclusion.append("benchmark_map_manual_review_required")

    return {
        "date": date,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "raw_candidate_count": len(rows),
        "normalized_scope_counts": _scope_counts(rows),
        "excluded_from_stock_denominator": _excluded(rows),
        "before_normalization": {
            "coverage_count": int(attribution.get("coverage_count", 0) or 0),
            "rs_vs_index_coverage": float(before_coverage.get("rs_vs_index_coverage", 0.0) or 0.0),
            "amount_1m_ratio_coverage": float(before_coverage.get("amount_1m_ratio_coverage", 0.0) or 0.0),
            "rs_vs_etf_coverage": float(before_coverage.get("rs_vs_etf_coverage", 0.0) or 0.0),
            "shadow_distribution": {
                "main": int(before_shadow.get("main", 0) or 0),
                "observe": int(before_shadow.get("observe", 0) or 0),
                "drop": int(before_shadow.get("drop", 0) or 0),
            },
        },
        "after_normalization": after,
        "benchmark_map_missing_groups": missing_groups,
        "trend_active_allowed": False,
        "evaluator_change_required": False,
        "benchmark_map_change_required": False,
        "manual_review_required": bool(missing_groups),
        "recommended_next_actions": [
            "use_stock_denominator_for_stock_confirmation_coverage",
            "split_etf_confirmation_scope",
            "exclude_industry_without_code_from_code_level_confirmation",
            "prepare_benchmark_manual_review_pack",
            "keep_trend_active_disabled",
        ],
        "warnings": ["scope_normalization_is_read_only", "benchmark_map_read_only_not_modified"],
        "conclusion": conclusion,
    }


def _render_markdown(payload: dict) -> str:
    lines = [
        f"# Trend Confirmation Scope Normalization {payload['date']}",
        "",
        f"- raw_candidate_count: `{payload['raw_candidate_count']}`",
        f"- normalized_scope_counts: `{payload['normalized_scope_counts']}`",
        f"- excluded_from_stock_denominator: `{payload['excluded_from_stock_denominator']}`",
        "",
        "## Before",
        "",
        json.dumps(payload["before_normalization"], ensure_ascii=False, indent=2),
        "",
        "## After",
        "",
        json.dumps(payload["after_normalization"], ensure_ascii=False, indent=2),
        "",
        f"- benchmark_map_missing_groups: `{payload['benchmark_map_missing_groups']}`",
        f"- trend_active_allowed: `{payload['trend_active_allowed']}`",
        f"- evaluator_change_required: `{payload['evaluator_change_required']}`",
        f"- benchmark_map_change_required: `{payload['benchmark_map_change_required']}`",
        "",
        "## Conclusion",
        "",
    ]
    for item in payload["conclusion"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict) -> tuple[Path, Path]:
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = EVAL_ROOT / f"trend_confirmation_scope_normalization_{payload['date']}.json"
    md_path = EVAL_ROOT / f"trend_confirmation_scope_normalization_{payload['date']}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Normalize trend confirmation scope denominator.")
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
                "normalized_scope_counts": payload["normalized_scope_counts"],
                "after_normalization": payload["after_normalization"],
                "trend_active_allowed": payload["trend_active_allowed"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
