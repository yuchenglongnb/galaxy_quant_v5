# -*- coding: utf-8 -*-
"""Read-only audit for trend ETF benchmark coverage and non-stock scope."""

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
    if lowered in {"etf"}:
        return "etf"
    if lowered in {"index", "指数"}:
        return "index"
    if lowered in {"industry", "行业"}:
        return "industry"
    return "unknown"


def _ratio(num: int, den: int) -> float:
    return round(float(num) / float(den), 4) if den else 0.0


def _benchmark_map() -> dict[str, dict]:
    rows = _read_csv(BENCHMARK_MAP_PATH)
    return {str(row.get("group", "") or ""): row for row in rows if str(row.get("group", "") or "")}


def _candidate_scope_counts(rows: list[dict]) -> dict:
    counts = Counter()
    for row in rows:
        scope = _norm_type(row.get("target_type"))
        if scope == "industry" and not row.get("code"):
            counts["industry_without_code"] += 1
        elif scope in {"stock", "etf", "index"}:
            counts[scope] += 1
        else:
            counts["unknown"] += 1
    return {
        "stock": int(counts.get("stock", 0)),
        "etf": int(counts.get("etf", 0)),
        "index": int(counts.get("index", 0)),
        "industry_without_code": int(counts.get("industry_without_code", 0)),
        "unknown": int(counts.get("unknown", 0)),
    }


def _stock_etf_benchmark_coverage(rows: list[dict]) -> dict:
    stock_rows = [row for row in rows if _norm_type(row.get("target_type")) == "stock"]
    covered = [row for row in stock_rows if str(row.get("benchmark_etf_code", "") or "")]
    missing = [row for row in stock_rows if not str(row.get("benchmark_etf_code", "") or "")]
    return {
        "covered_count": len(covered),
        "missing_count": len(missing),
        "coverage_ratio": _ratio(len(covered), len(stock_rows)),
        "covered_groups": sorted({str(row.get("group", "") or "") for row in covered if row.get("group")}),
        "missing_groups": sorted({str(row.get("group", "") or "") for row in missing if row.get("group")}),
        "missing_candidates": [
            {
                "code": row.get("code", ""),
                "name": row.get("name", ""),
                "group": row.get("group", ""),
                "primary_blocker": row.get("primary_blocker", ""),
            }
            for row in missing
        ],
    }


def _missing_group_analysis(missing_groups: list[str], mapping: dict[str, dict]) -> list[dict]:
    output = []
    for group in missing_groups:
        mapped = mapping.get(group, {}) or {}
        current = str(mapped.get("benchmark_etf_code", "") or "")
        output.append(
            {
                "group": group,
                "current_benchmark": current or None,
                "candidate_benchmarks": [current] if current else [],
                "confidence": "medium" if current else "low",
                "evidence": str(mapped.get("note", "") or ""),
                "recommended_action": "manual_review",
            }
        )
    return output


def _non_stock_candidate_analysis(rows: list[dict]) -> dict:
    etf = []
    index = []
    industry = []
    for row in rows:
        scope = _norm_type(row.get("target_type"))
        record = {
            "code": row.get("code", ""),
            "name": row.get("name", ""),
            "target_type": row.get("target_type", ""),
            "primary_blocker": row.get("primary_blocker", ""),
            "recommended_scope": f"{scope}_confirmation" if scope in {"etf", "index"} else "exclude_from_code_level_confirmation",
        }
        if scope == "etf":
            etf.append(record)
        elif scope == "index":
            index.append(record)
        elif scope == "industry" and not row.get("code"):
            industry.append(record)
    return {
        "etf_candidates": etf,
        "index_candidates": index,
        "industry_without_code": industry,
    }


def _failed_code_analysis(attribution: dict, backfill: dict, rows: list[dict]) -> dict:
    existing = attribution.get("failed_code_analysis") or {}
    failed_codes = set(existing.keys())
    failed_codes.update(str(code) for code in (((backfill.get("backfill") or {}).get("failed_codes")) or []))
    by_code = {str(row.get("code", "") or ""): row for row in rows if row.get("code")}
    result = {}
    for code in sorted(failed_codes):
        row = by_code.get(code, {})
        scope = _norm_type(row.get("target_type") or ("ETF" if code.startswith(("15", "51")) else ""))
        result[code] = {
            "name": row.get("name", "") or (existing.get(code, {}) or {}).get("name", ""),
            "scope": scope,
            "should_exclude_from_stock_confirmation": scope != "stock",
            "recommended_scope": f"{scope}_confirmation" if scope in {"etf", "index"} else "stock_confirmation",
            "recommended_action": (
                "split_non_stock_trend_confirmation_scope"
                if scope != "stock"
                else "inspect_stock_min1_query"
            ),
        }
    return result


def build_payload(date: str) -> dict:
    date = str(date)
    attribution = _load_json(EVAL_ROOT / f"trend_confirmation_shadow_attribution_{date}.json")
    recent = _load_json(EVAL_ROOT / f"recent_trend_confirmation_coverage_{date}_{date}.json")
    backfill = _load_json(EVAL_ROOT / f"intraday_min1_backfill_{date}.json")
    rows = list(attribution.get("blocking_reason_by_candidate") or [])
    counts = _candidate_scope_counts(rows)
    stock_cov = _stock_etf_benchmark_coverage(rows)
    mapping = _benchmark_map()
    missing_analysis = _missing_group_analysis(stock_cov["missing_groups"], mapping)
    non_stock = _non_stock_candidate_analysis(rows)
    failed = _failed_code_analysis(attribution, backfill, rows)

    cause_bits = []
    if stock_cov["missing_count"] > 0:
        cause_bits.append("benchmark_map_missing")
    if non_stock["etf_candidates"] or non_stock["index_candidates"]:
        cause_bits.append("candidate_is_non_stock")
    if non_stock["industry_without_code"]:
        cause_bits.append("industry_item_without_code")
    root_cause = "_and_".join(cause_bits) if cause_bits else "benchmark_scope_clean"

    conclusions = [
        "keep_trend_active_disabled",
        "no_strategy_rule_change",
        "read_only_audit",
        "evaluator_change_not_required",
        "benchmark_map_not_modified",
    ]
    if stock_cov["missing_count"] > 0:
        conclusions.append("etf_benchmark_map_missing")
    if non_stock["etf_candidates"] or non_stock["index_candidates"]:
        conclusions.append("non_stock_trend_scope_required")
    if non_stock["industry_without_code"]:
        conclusions.append("industry_item_without_code_excluded")

    return {
        "date": date,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_scope_counts": counts,
        "stock_etf_benchmark_coverage": stock_cov,
        "missing_group_analysis": missing_analysis,
        "non_stock_candidate_analysis": non_stock,
        "failed_code_analysis": failed,
        "benchmark_map_review_candidates": missing_analysis,
        "coverage_context": {
            "rs_vs_etf_coverage": (recent.get("coverage_summary") or {}).get("rs_vs_etf_coverage"),
            "shadow_distribution": attribution.get("shadow_distribution", {}),
        },
        "root_cause": root_cause,
        "trend_active_allowed": False,
        "evaluator_change_required": False,
        "benchmark_map_change_required": False,
        "manual_review_required": bool(missing_analysis or non_stock["etf_candidates"] or non_stock["industry_without_code"]),
        "recommended_next_actions": [
            "manual_review_missing_etf_benchmark_groups",
            "split_non_stock_trend_confirmation_scope",
            "exclude_industry_without_code_from_code_level_confirmation",
            "keep_trend_active_disabled",
        ],
        "warnings": [
            "benchmark_map_read_only_not_modified",
        ],
        "conclusion": conclusions,
    }


def _render_markdown(payload: dict) -> str:
    lines = [
        f"# Trend ETF Benchmark Scope {payload['date']}",
        "",
        f"- candidate_scope_counts: `{payload['candidate_scope_counts']}`",
        f"- stock_etf_benchmark_coverage: `{payload['stock_etf_benchmark_coverage']}`",
        f"- root_cause: `{payload['root_cause']}`",
        f"- trend_active_allowed: `{payload['trend_active_allowed']}`",
        f"- evaluator_change_required: `{payload['evaluator_change_required']}`",
        f"- benchmark_map_change_required: `{payload['benchmark_map_change_required']}`",
        "",
        "## Missing Group Analysis",
        "",
    ]
    for row in payload["missing_group_analysis"]:
        lines.append(f"- {row}")
    lines.extend(["", "## Non-stock Candidate Analysis", ""])
    lines.append(json.dumps(payload["non_stock_candidate_analysis"], ensure_ascii=False, indent=2))
    lines.extend(["", "## Failed Code Analysis", ""])
    lines.append(json.dumps(payload["failed_code_analysis"], ensure_ascii=False, indent=2))
    lines.extend(["", "## Conclusion", ""])
    for item in payload["conclusion"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict) -> tuple[Path, Path]:
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = EVAL_ROOT / f"trend_etf_benchmark_scope_{payload['date']}.json"
    md_path = EVAL_ROOT / f"trend_etf_benchmark_scope_{payload['date']}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate ETF benchmark and non-stock trend scope.")
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
                "candidate_scope_counts": payload["candidate_scope_counts"],
                "stock_etf_benchmark_coverage": payload["stock_etf_benchmark_coverage"],
                "root_cause": payload["root_cause"],
                "trend_active_allowed": payload["trend_active_allowed"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
