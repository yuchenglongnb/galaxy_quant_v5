# -*- coding: utf-8 -*-
"""Analysis-only prior-day context evidence loop tool.

This tool evaluates how prior-day context scoring relates to stock-only auction
validation outcomes. It is a reporting and evidence-loop utility, not a trading
instruction or rule-change tool. It does not change CP thresholds, expand
exemptions, enable Trend active, mutate signal/evaluator/strategy/config files,
write lesson/pattern/registry records, call sync/live APIs, or execute
market-structure backfill.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.encoding import configure_utf8_console  # noqa: E402


EVAL_ROOT = ROOT / "reports" / "analysis" / "evaluations"
VALIDATION_DAILY_ROOT = ROOT / "reports" / "validation" / "daily"


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _valid_number(value) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return number == number


def _normalize_date_str(value) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _normalize_target_type(value) -> str:
    text = str(value or "").strip().lower()
    mapping = {
        "stock": "stock",
        "涓偂": "stock",
        "etf": "ETF",
        "index": "index",
        "鎸囨暟": "index",
        "industry": "industry",
        "琛屼笟": "industry",
    }
    return mapping.get(text, "unknown")


def _to_bool(value):
    if isinstance(value, bool):
        return value
    text = str("" if value is None else value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _read_detail_rows(date_str: str) -> list[dict]:
    path = VALIDATION_DAILY_ROOT / date_str / "signal_detail.csv"
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh))
    except Exception:
        return []


def _detail_key(category: str, code: str, name: str, target_type: str) -> str:
    return "::".join([str(category or ""), str(code or ""), str(name or ""), str(target_type or "")])


def _build_detail_map(detail_rows) -> dict[str, dict]:
    if not detail_rows:
        return {}
    if hasattr(detail_rows, "to_dict"):
        detail_rows = detail_rows.to_dict("records")
    detail_map = {}
    for row in detail_rows:
        target_type = _normalize_target_type(row.get("target_type", ""))
        code = str(row.get("code", "") or "")
        key = _detail_key(row.get("signal_category", ""), code, row.get("name", ""), target_type)
        detail_map[key] = dict(row)
        if not code.strip():
            fallback_key = _detail_key(row.get("signal_category", ""), "", row.get("name", ""), target_type)
            detail_map.setdefault(fallback_key, dict(row))
    return detail_map


def _row_key(row: dict) -> str:
    return _detail_key(row.get("category", ""), row.get("code", ""), row.get("name", ""), row.get("target_type", ""))


def _rank_map(rows: list[dict], score_key: str) -> dict[str, int]:
    ordered = sorted(
        rows,
        key=lambda item: (-_number(item.get(score_key)), str(item.get("name", ""))),
    )
    return {_row_key(row): idx for idx, row in enumerate(ordered, start=1)}


def _candidate_rows(result: dict, detail_rows) -> list[dict]:
    detail_map = _build_detail_map(detail_rows)
    rows = []
    for category in ("trap", "reversal", "trend"):
        for candidate in (result.get("signals", {}) or {}).get(category, []) or []:
            data = candidate.get("data", {}) or {}
            target_type = _normalize_target_type(data.get("target_type", candidate.get("target_type", "")))
            code = str(data.get("code", candidate.get("code", "")) or "")
            name = str(candidate.get("name", "") or "")
            key = _detail_key(category, code, name, target_type)
            fallback_key = _detail_key(category, "", name, target_type)
            detail_row = detail_map.get(key) or detail_map.get(fallback_key) or {}
            performance_available = bool(detail_row)
            row = {
                "date": str(result.get("date", "") or ""),
                "category": category,
                "name": name,
                "code": code,
                "target_type": target_type,
                "bonus": _number(candidate.get("prior_day_context_bonus")),
                "annotation_bonus": _number(candidate.get("prior_day_context_annotation_bonus")),
                "bonus_shadow": _number(candidate.get("prior_day_context_bonus_shadow")),
                "bonus_applied": bool(candidate.get("prior_day_context_bonus_applied")),
                "apply_mode": str(candidate.get("prior_day_context_apply_mode", "") or ""),
                "scope_reason": str(candidate.get("prior_day_context_scope_reason", "") or ""),
                "score_before": _number(candidate.get("prior_day_context_score_before"), candidate.get("action_score")),
                "score_after": _number(candidate.get("prior_day_context_score_after"), candidate.get("action_score")),
                "cp_risk_decision": str(candidate.get("cp_risk_decision", "") or ""),
                "trend_filter_decision": str(candidate.get("trend_filter_decision", "") or ""),
                "trend_gate_decision_shadow": str(candidate.get("trend_gate_decision_shadow", "") or ""),
                "performance_available": performance_available,
                "body_pct": _number(detail_row.get("body_pct"), float("nan")) if performance_available else float("nan"),
                "validation_success": _to_bool(detail_row.get("validation_success")) if performance_available else None,
            }
            rows.append(row)
    before_ranks = _rank_map(rows, "score_before")
    after_ranks = _rank_map(rows, "score_after")
    for row in rows:
        key = _row_key(row)
        row["rank_before"] = before_ranks.get(key, 0)
        row["rank_after"] = after_ranks.get(key, 0)
        row["rank_delta"] = row["rank_before"] - row["rank_after"]
    return rows


def _resolve_dates(args) -> list[str]:
    if args.dates:
        return [_normalize_date_str(item) for item in args.dates.split(",") if item.strip()]
    if args.start_date and args.end_date:
        start = datetime.strptime(_normalize_date_str(args.start_date), "%Y%m%d").date()
        end = datetime.strptime(_normalize_date_str(args.end_date), "%Y%m%d").date()
        dates = []
        cursor = start
        while cursor <= end:
            date_str = cursor.strftime("%Y%m%d")
            if (ROOT / "reports" / "analysis" / "daily" / date_str).exists():
                dates.append(date_str)
            cursor += timedelta(days=1)
        return dates
    raise ValueError("Provide --dates YYYYMMDD,... or --start-date/--end-date")


def _median(values: list[float]) -> float | None:
    clean = sorted(value for value in values if _valid_number(value))
    if not clean:
        return None
    midpoint = len(clean) // 2
    if len(clean) % 2:
        return round(float(clean[midpoint]), 4)
    return round(float((clean[midpoint - 1] + clean[midpoint]) / 2.0), 4)


def _performance(rows: list[dict]) -> dict:
    available = [row for row in rows if row.get("performance_available")]
    if not available:
        return {
            "performance_available": False,
            "candidate_count": len(rows),
            "avg_body_pct": None,
            "median_body_pct": None,
            "success_rate": None,
            "avg_action_score_before": None,
            "avg_action_score_after": None,
            "avg_rank_delta": None,
        }
    body_values = [_number(row.get("body_pct"), float("nan")) for row in available]
    success_values = [row.get("validation_success") for row in available if row.get("validation_success") is not None]
    return {
        "performance_available": True,
        "candidate_count": len(rows),
        "avg_body_pct": round(sum(value for value in body_values if _valid_number(value)) / max(1, sum(_valid_number(value) for value in body_values)), 4)
        if any(_valid_number(value) for value in body_values)
        else None,
        "median_body_pct": _median(body_values),
        "success_rate": round(sum(1 for value in success_values if value) / len(success_values) * 100, 4)
        if success_values
        else None,
        "avg_action_score_before": round(sum(_number(row.get("score_before")) for row in rows) / len(rows), 4)
        if rows
        else None,
        "avg_action_score_after": round(sum(_number(row.get("score_after")) for row in rows) / len(rows), 4)
        if rows
        else None,
        "avg_rank_delta": round(sum(int(row.get("rank_delta", 0)) for row in rows) / len(rows), 4) if rows else None,
    }


def _bonus_groups(rows: list[dict]) -> dict[str, list[dict]]:
    return {
        "positive_bonus": [row for row in rows if _number(row.get("bonus")) > 0],
        "negative_bonus": [row for row in rows if _number(row.get("bonus")) < 0],
        "zero_bonus": [row for row in rows if _number(row.get("bonus")) == 0],
    }


def _category_breakdown(stock_rows: list[dict]) -> dict:
    result = {}
    for category in ("trap", "reversal", "trend", "other"):
        category_rows = [row for row in stock_rows if row.get("category") == category]
        groups = _bonus_groups(category_rows)
        result[category] = {name: _performance(rows) for name, rows in groups.items()}
        result[category]["candidate_count"] = len(category_rows)
    return result


def _topn_comparison(stock_rows: list[dict], n: int) -> dict:
    before = sorted(stock_rows, key=lambda row: (-_number(row.get("score_before")), str(row.get("name", ""))))[:n]
    after = sorted(stock_rows, key=lambda row: (-_number(row.get("score_after")), str(row.get("name", ""))))[:n]
    before_keys = {_row_id(row) for row in before}
    after_keys = {_row_id(row) for row in after}
    return {
        "candidate_count": min(n, len(stock_rows)),
        "topn_unchanged": [_row_id(row) for row in before] == [_row_id(row) for row in after],
        "before": _performance(before),
        "after": _performance(after),
        "overlap_count": len(before_keys & after_keys),
        "changed_names": [row.get("name", "") for row in after if _row_id(row) not in before_keys],
    }


def _row_id(row: dict) -> str:
    return "::".join([str(row.get("category", "")), str(row.get("code", "")), str(row.get("name", ""))])


def _rank_delta_rows(stock_rows: list[dict], limit=10) -> list[dict]:
    ordered = sorted(stock_rows, key=lambda row: abs(int(row.get("rank_delta", 0))), reverse=True)
    return [
        {
            "category": row.get("category", ""),
            "code": row.get("code", ""),
            "name": row.get("name", ""),
            "bonus": row.get("bonus", 0.0),
            "score_before": row.get("score_before"),
            "score_after": row.get("score_after"),
            "rank_before": row.get("rank_before"),
            "rank_after": row.get("rank_after"),
            "rank_delta": row.get("rank_delta"),
            "body_pct": row.get("body_pct"),
            "validation_success": row.get("validation_success"),
        }
        for row in ordered[:limit]
    ]


def build_stock_effect_payload(date_str: str, result: dict, detail_rows) -> dict:
    rows = _candidate_rows(result, detail_rows)
    stock_rows = [row for row in rows if row.get("target_type") == "stock"]
    excluded_rows = [row for row in rows if row.get("target_type") != "stock"]
    groups = _bonus_groups(stock_rows)
    prior_context = result.get("prior_day_context", {}) or {}
    payload = {
        "date": date_str,
        "prev_trade_date": prior_context.get("prev_trade_date", ""),
        "context_available": bool(prior_context.get("available")),
        "context_confidence": str(prior_context.get("context_confidence", "") or ""),
        "stock_candidate_total": len(stock_rows),
        "stock_true_bonus_count": sum(abs(_number(row.get("bonus"))) > 0 for row in stock_rows),
        "positive_bonus_count": len(groups["positive_bonus"]),
        "negative_bonus_count": len(groups["negative_bonus"]),
        "zero_bonus_count": len(groups["zero_bonus"]),
        "rank_changed_count": sum(int(row.get("rank_delta", 0)) != 0 for row in stock_rows),
        "max_rank_delta": max((abs(int(row.get("rank_delta", 0))) for row in stock_rows), default=0),
        "bucket_changed_count": 0,
        "excluded_non_stock_count": len(excluded_rows),
        "excluded_by_target_type": {
            "ETF": sum(row.get("target_type") == "ETF" for row in excluded_rows),
            "index": sum(row.get("target_type") == "index" for row in excluded_rows),
            "industry": sum(row.get("target_type") == "industry" for row in excluded_rows),
            "unknown": sum(row.get("target_type") == "unknown" for row in excluded_rows),
        },
        "positive_bonus_performance": _performance(groups["positive_bonus"]),
        "negative_bonus_performance": _performance(groups["negative_bonus"]),
        "zero_bonus_performance": _performance(groups["zero_bonus"]),
        "category_breakdown": _category_breakdown(stock_rows),
        "topn_comparison": {
            "top5": _topn_comparison(stock_rows, 5),
            "top10": _topn_comparison(stock_rows, 10),
            "top20": _topn_comparison(stock_rows, 20),
        },
        "top_rank_delta_candidates": _rank_delta_rows(stock_rows),
        "rank_change_performance_impact": _performance([row for row in stock_rows if int(row.get("rank_delta", 0)) != 0]),
        "warnings": [],
    }
    if not payload["context_available"]:
        payload["warnings"].append("context_unavailable")
    if any(not row.get("performance_available") for row in stock_rows):
        payload["warnings"].append("post_close_performance_unavailable")
    if payload["bucket_changed_count"]:
        payload["warnings"].append("unexpected_bucket_change")
    return payload


def _render_day_markdown(payload: dict) -> str:
    lines = [
        f"# Prior Day Context Stock Effect {payload['date']}",
        "",
        f"- prev_trade_date: `{payload['prev_trade_date']}`",
        f"- context_available: `{payload['context_available']}`",
        f"- context_confidence: `{payload['context_confidence']}`",
        f"- stock_candidate_total: `{payload['stock_candidate_total']}`",
        f"- stock_true_bonus_count: `{payload['stock_true_bonus_count']}`",
        f"- positive / negative / zero: `{payload['positive_bonus_count']} / {payload['negative_bonus_count']} / {payload['zero_bonus_count']}`",
        f"- rank_changed_count: `{payload['rank_changed_count']}`",
        f"- max_rank_delta: `{payload['max_rank_delta']}`",
        f"- bucket_changed_count: `{payload['bucket_changed_count']}`",
        f"- excluded_non_stock_count: `{payload['excluded_non_stock_count']}`",
        f"- warnings: `{payload['warnings']}`",
        "",
        "## Bonus Groups",
        "",
        f"- positive_bonus: `{payload['positive_bonus_performance']}`",
        f"- negative_bonus: `{payload['negative_bonus_performance']}`",
        f"- zero_bonus: `{payload['zero_bonus_performance']}`",
        "",
        "## TopN Before/After",
    ]
    for key, value in payload["topn_comparison"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Category Breakdown"])
    for key, value in payload["category_breakdown"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Top Rank Delta Candidates"])
    for row in payload["top_rank_delta_candidates"]:
        lines.append(f"- {row}")
    return "\n".join(lines) + "\n"


def _summary_performance(day_payloads: list[dict], field: str) -> dict:
    rows = [payload.get(field, {}) or {} for payload in day_payloads]
    rows = [row for row in rows if row.get("performance_available")]
    if not rows:
        return {"performance_available": False, "avg_body_pct": None, "median_body_pct": None, "success_rate": None}
    body_values = [row.get("avg_body_pct") for row in rows if row.get("avg_body_pct") is not None]
    median_values = [row.get("median_body_pct") for row in rows if row.get("median_body_pct") is not None]
    success_values = [row.get("success_rate") for row in rows if row.get("success_rate") is not None]
    return {
        "performance_available": True,
        "avg_body_pct": round(sum(body_values) / len(body_values), 4) if body_values else None,
        "median_body_pct": round(sum(median_values) / len(median_values), 4) if median_values else None,
        "success_rate": round(sum(success_values) / len(success_values), 4) if success_values else None,
    }


def build_summary(day_payloads: list[dict]) -> dict:
    warnings = sorted({warning for payload in day_payloads for warning in payload.get("warnings", [])})
    confidence = {"high": 0, "medium": 0, "low": 0}
    for payload in day_payloads:
        key = payload.get("context_confidence") or "low"
        confidence[key] = confidence.get(key, 0) + 1
    category_summary = {}
    for category in ("trap", "reversal", "trend", "other"):
        category_payloads = []
        for payload in day_payloads:
            breakdown = payload.get("category_breakdown", {}).get(category, {})
            category_payloads.append(
                {
                    "positive_bonus_performance": breakdown.get("positive_bonus", {}),
                    "negative_bonus_performance": breakdown.get("negative_bonus", {}),
                    "zero_bonus_performance": breakdown.get("zero_bonus", {}),
                }
            )
        category_summary[category] = {
            "positive_bonus": _summary_performance(category_payloads, "positive_bonus_performance"),
            "negative_bonus": _summary_performance(category_payloads, "negative_bonus_performance"),
            "zero_bonus": _summary_performance(category_payloads, "zero_bonus_performance"),
        }
    return {
        "evaluated_dates": [payload["date"] for payload in day_payloads],
        "context_available_dates": [payload["date"] for payload in day_payloads if payload.get("context_available")],
        "confidence_distribution": confidence,
        "total_stock_candidates": sum(payload.get("stock_candidate_total", 0) for payload in day_payloads),
        "stock_true_bonus_count": sum(payload.get("stock_true_bonus_count", 0) for payload in day_payloads),
        "positive_bonus_count": sum(payload.get("positive_bonus_count", 0) for payload in day_payloads),
        "negative_bonus_count": sum(payload.get("negative_bonus_count", 0) for payload in day_payloads),
        "zero_bonus_count": sum(payload.get("zero_bonus_count", 0) for payload in day_payloads),
        "overall_rank_changed_count": sum(payload.get("rank_changed_count", 0) for payload in day_payloads),
        "overall_bucket_changed_count": sum(payload.get("bucket_changed_count", 0) for payload in day_payloads),
        "positive_bonus_performance": _summary_performance(day_payloads, "positive_bonus_performance"),
        "negative_bonus_performance": _summary_performance(day_payloads, "negative_bonus_performance"),
        "zero_bonus_performance": _summary_performance(day_payloads, "zero_bonus_performance"),
        "category_level_stock_performance": category_summary,
        "topn_before_after": {
            key: {
                "unchanged_dates": sum(payload.get("topn_comparison", {}).get(key, {}).get("topn_unchanged") for payload in day_payloads),
                "changed_dates": sum(not payload.get("topn_comparison", {}).get(key, {}).get("topn_unchanged") for payload in day_payloads),
            }
            for key in ("top5", "top10", "top20")
        },
        "date_level_outliers": [
            {
                "date": payload["date"],
                "rank_changed_count": payload.get("rank_changed_count", 0),
                "max_rank_delta": payload.get("max_rank_delta", 0),
            }
            for payload in day_payloads
            if payload.get("rank_changed_count", 0) or payload.get("max_rank_delta", 0)
        ],
        "warnings_summary": warnings,
        "conclusion": _conclusion(day_payloads, warnings),
    }


def _conclusion(day_payloads: list[dict], warnings: list[str]) -> str:
    if any(payload.get("bucket_changed_count", 0) for payload in day_payloads):
        return "not_ready_for_weight_tuning"
    positive = _summary_performance(day_payloads, "positive_bonus_performance")
    negative = _summary_performance(day_payloads, "negative_bonus_performance")
    if positive.get("success_rate") is not None and negative.get("success_rate") is not None:
        if positive["success_rate"] > negative["success_rate"]:
            return "ready_for_robustness_check"
    if "context_unavailable" in warnings:
        return "need_more_dates"
    return "keep_current_weight"


def _render_summary_markdown(summary: dict) -> str:
    lines = [
        "# Prior Day Context Stock Effect Summary",
        "",
        f"- evaluated_dates: `{summary['evaluated_dates']}`",
        f"- context_available_dates: `{summary['context_available_dates']}`",
        f"- confidence_distribution: `{summary['confidence_distribution']}`",
        f"- total_stock_candidates: `{summary['total_stock_candidates']}`",
        f"- stock_true_bonus_count: `{summary['stock_true_bonus_count']}`",
        f"- positive / negative / zero: `{summary['positive_bonus_count']} / {summary['negative_bonus_count']} / {summary['zero_bonus_count']}`",
        f"- overall_rank_changed_count: `{summary['overall_rank_changed_count']}`",
        f"- overall_bucket_changed_count: `{summary['overall_bucket_changed_count']}`",
        f"- warnings_summary: `{summary['warnings_summary']}`",
        f"- conclusion: `{summary['conclusion']}`",
        "",
        "## Bonus Performance",
        "",
        f"- positive_bonus: `{summary['positive_bonus_performance']}`",
        f"- negative_bonus: `{summary['negative_bonus_performance']}`",
        f"- zero_bonus: `{summary['zero_bonus_performance']}`",
        "",
        "## TopN Before/After",
    ]
    for key, value in summary["topn_before_after"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Category Level"])
    for key, value in summary["category_level_stock_performance"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Date-Level Outliers"])
    for row in summary["date_level_outliers"]:
        lines.append(f"- {row}")
    return "\n".join(lines) + "\n"


def write_day_outputs(payload: dict, output_dir: str | Path | None = None):
    root = Path(output_dir) if output_dir else EVAL_ROOT
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / f"prior_day_context_stock_effect_{payload['date']}.json"
    md_path = root / f"prior_day_context_stock_effect_{payload['date']}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_day_markdown(payload), encoding="utf-8")
    return json_path, md_path


def write_summary_outputs(summary: dict, output_dir: str | Path | None = None):
    root = Path(output_dir) if output_dir else EVAL_ROOT
    root.mkdir(parents=True, exist_ok=True)
    summary_json = root / "prior_day_context_stock_effect_summary.json"
    summary_md = root / "prior_day_context_stock_effect_summary.md"
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_md.write_text(_render_summary_markdown(summary), encoding="utf-8")
    return summary_json, summary_md


def evaluate_dates(date_list: list[str], output_dir: str | Path | None = None, write_reports: bool = True) -> tuple[list[dict], dict]:
    from analyzers.auction import AuctionAnalyzer
    from core.data_manager import DataManager

    dm = DataManager()
    analyzer = AuctionAnalyzer(dm)
    payloads = []
    for date_str in date_list:
        result = analyzer.analyze(int(date_str), realtime=False)
        if result is None:
            continue
        result = dict(result)
        result["date"] = date_str
        payload = build_stock_effect_payload(date_str, result, _read_detail_rows(date_str))
        payloads.append(payload)
        if write_reports:
            write_day_outputs(payload, output_dir)
    summary = build_summary(payloads)
    return payloads, summary


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate stock-only prior-day context effect.")
    parser.add_argument("--dates", default="", help="Comma-separated trade dates.")
    parser.add_argument("--start-date", default="")
    parser.add_argument("--end-date", default="")
    parser.add_argument("--output-dir", default="", help="Repo-relative or explicit output directory for generated reports.")
    parser.add_argument("--dry-run", action="store_true", help="Build the payload and print a compact summary without writing reports.")
    return parser.parse_args(argv)


def main(argv=None):
    configure_utf8_console()
    args = parse_args(argv)
    dates = _resolve_dates(args)
    payloads, summary = evaluate_dates(dates, args.output_dir or None, write_reports=not args.dry_run)
    if args.dry_run:
        print(json.dumps({
            "dry_run": True,
            "evaluated_dates": len(payloads),
            "dates": dates,
            "conclusion": summary.get("conclusion"),
        }, ensure_ascii=False, indent=2))
        return payloads, summary
    summary_json, summary_md = write_summary_outputs(summary, args.output_dir or None)
    print(json.dumps({"evaluated_dates": len(payloads), "summary": str(summary_json), "summary_md": str(summary_md)}, ensure_ascii=False, indent=2))
    return payloads, summary


if __name__ == "__main__":
    main()
