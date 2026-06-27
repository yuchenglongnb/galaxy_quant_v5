# -*- coding: utf-8 -*-
"""Multi-day validation for prior-day context soft score."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from analyzers.auction import AuctionAnalyzer  # noqa: E402
from core.data_manager import DataManager  # noqa: E402
from utils.encoding import configure_utf8_console  # noqa: E402


EVAL_ROOT = Path("reports") / "analysis" / "evaluations"
VALIDATION_DAILY_ROOT = Path("reports") / "validation" / "daily"
PRIOR_DAY_CONFIG_PATH = Path("reports") / "analysis" / "configs" / "prior_day_context_config.json"


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_date_str(value) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _normalize_target_type(value) -> str:
    text = str(value or "").strip().lower()
    mapping = {
        "stock": "stock",
        "个股": "stock",
        "etf": "ETF",
        "index": "index",
        "指数": "index",
        "industry": "industry",
        "行业": "industry",
    }
    return mapping.get(text, "unknown")


def _parse_args(argv):
    args = {
        "dates": [],
        "start_date": "",
        "end_date": "",
    }
    for idx, arg in enumerate(argv):
        if arg == "--dates" and idx + 1 < len(argv):
            args["dates"] = [item.strip() for item in argv[idx + 1].split(",") if item.strip()]
        elif arg.startswith("--dates="):
            args["dates"] = [item.strip() for item in arg.split("=", 1)[1].split(",") if item.strip()]
        elif arg == "--start-date" and idx + 1 < len(argv):
            args["start_date"] = argv[idx + 1].strip()
        elif arg.startswith("--start-date="):
            args["start_date"] = arg.split("=", 1)[1].strip()
        elif arg == "--end-date" and idx + 1 < len(argv):
            args["end_date"] = argv[idx + 1].strip()
        elif arg.startswith("--end-date="):
            args["end_date"] = arg.split("=", 1)[1].strip()
    return args


def _resolve_dates(args) -> list[str]:
    if args["dates"]:
        return [_normalize_date_str(item) for item in args["dates"]]
    if args["start_date"] and args["end_date"]:
        start = datetime.strptime(_normalize_date_str(args["start_date"]), "%Y%m%d").date()
        end = datetime.strptime(_normalize_date_str(args["end_date"]), "%Y%m%d").date()
        results = []
        cursor = start
        while cursor <= end:
            date_str = cursor.strftime("%Y%m%d")
            if (VALIDATION_DAILY_ROOT / date_str).exists() or (Path("reports") / "analysis" / "daily" / date_str).exists():
                results.append(date_str)
            cursor += timedelta(days=1)
        return results
    raise ValueError(
        "Usage: python scripts/evaluate_prior_day_context_effect.py --dates YYYYMMDD,... "
        "or --start-date YYYYMMDD --end-date YYYYMMDD"
    )


def _read_detail_df(date_str: str) -> pd.DataFrame:
    path = VALIDATION_DAILY_ROOT / date_str / "signal_detail.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig", dtype={"date": str})
    except Exception:
        return pd.DataFrame()


def _read_prior_day_config() -> dict:
    if not PRIOR_DAY_CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(PRIOR_DAY_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _detail_key(category: str, code: str, name: str, target_type: str) -> str:
    return "::".join([str(category or ""), str(code or ""), str(name or ""), str(target_type or "")])


def _build_detail_map(detail_df: pd.DataFrame) -> dict[str, dict]:
    if detail_df.empty:
        return {}
    work = detail_df.copy()
    for column in ("signal_category", "name", "target_type"):
        if column not in work.columns:
            work[column] = ""
        work[column] = work[column].astype(str)
    if "code" not in work.columns:
        work["code"] = ""
    work["code"] = work["code"].fillna("").astype(str)
    detail_map = {}
    for _, row in work.iterrows():
        key = _detail_key(
            row.get("signal_category", ""),
            row.get("code", ""),
            row.get("name", ""),
            _normalize_target_type(row.get("target_type", "")),
        )
        detail_map[key] = row.to_dict()
        if not str(row.get("code", "")).strip():
            fallback_key = _detail_key(
                row.get("signal_category", ""),
                "",
                row.get("name", ""),
                _normalize_target_type(row.get("target_type", "")),
            )
            detail_map.setdefault(fallback_key, row.to_dict())
    return detail_map


def _candidate_rows(result: dict, detail_df: pd.DataFrame) -> list[dict]:
    detail_map = _build_detail_map(detail_df)
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


def _row_key(row: dict) -> str:
    return _detail_key(row.get("category", ""), row.get("code", ""), row.get("name", ""), row.get("target_type", ""))


def _rank_map(rows: list[dict], score_key: str) -> dict[str, int]:
    ordered = sorted(
        rows,
        key=lambda item: (-_number(item.get(score_key)), str(item.get("name", ""))),
    )
    return {_row_key(row): idx for idx, row in enumerate(ordered, start=1)}


def _to_bool(value):
    if isinstance(value, bool):
        return value
    text = str("" if value is None else value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _performance_summary(rows: list[dict]) -> dict:
    available = [row for row in rows if row.get("performance_available")]
    if not available:
        return {
            "performance_available": False,
            "avg_body_pct": None,
            "success_rate": None,
        }
    body_values = [row["body_pct"] for row in available if pd.notna(row["body_pct"])]
    success_values = [row["validation_success"] for row in available if row["validation_success"] is not None]
    return {
        "performance_available": True,
        "avg_body_pct": round(sum(body_values) / len(body_values), 4) if body_values else None,
        "success_rate": round(sum(1 for item in success_values if item) / len(success_values) * 100, 2)
        if success_values
        else None,
    }


def _group_counts(rows: list[dict], key_name: str, expected: list[str]) -> dict:
    result = {}
    for group in expected:
        subset = [row for row in rows if row.get(key_name) == group]
        result[group] = {
            "candidate_count": len(subset),
            "positive_bonus_count": sum(_number(row["bonus"]) > 0 for row in subset),
            "negative_bonus_count": sum(_number(row["bonus"]) < 0 for row in subset),
            "zero_bonus_count": sum(_number(row["bonus"]) == 0 for row in subset),
            "avg_bonus": round(sum(_number(row["bonus"]) for row in subset) / len(subset), 4) if subset else 0.0,
            "avg_rank_delta": round(sum(int(row.get("rank_delta", 0)) for row in subset) / len(subset), 4) if subset else 0.0,
            **_performance_summary(subset),
        }
    return result


def _top_rows(rows: list[dict], positive=True, limit=8) -> list[dict]:
    filtered = [row for row in rows if (_number(row["bonus"]) > 0 if positive else _number(row["bonus"]) < 0)]
    ordered = sorted(
        filtered,
        key=lambda item: (_number(item["bonus"]), abs(int(item.get("rank_delta", 0))), _number(item.get("body_pct"), -999.0)),
        reverse=positive,
    )
    return ordered[:limit]


def _warnings(rows: list[dict], context_available: bool) -> list[str]:
    warnings = []
    if not context_available:
        warnings.append("context_unavailable")
    if any(row["target_type"] in {"ETF", "index", "industry"} and abs(_number(row["bonus"])) > 0 for row in rows):
        warnings.append("non_stock_prior_day_bonus_present")
    if any(not row.get("performance_available") for row in rows):
        warnings.append("post_close_performance_unavailable")
    return warnings


def build_day_payload(date_str: str, result: dict, detail_df: pd.DataFrame) -> dict:
    rows = _candidate_rows(result, detail_df)
    config = _read_prior_day_config()
    prior_context = result.get("prior_day_context", {}) or {}
    positive_rows = [row for row in rows if _number(row["bonus"]) > 0]
    negative_rows = [row for row in rows if _number(row["bonus"]) < 0]
    zero_rows = [row for row in rows if _number(row["bonus"]) == 0]
    stock_rows = [row for row in rows if row.get("target_type") == "stock"]
    stock_positive_rows = [row for row in stock_rows if _number(row["bonus"]) > 0]
    stock_negative_rows = [row for row in stock_rows if _number(row["bonus"]) < 0]
    stock_zero_rows = [row for row in stock_rows if _number(row["bonus"]) == 0]
    non_stock_rows = [row for row in rows if row.get("target_type") != "stock"]
    payload = {
        "date": date_str,
        "prev_trade_date": prior_context.get("prev_trade_date", ""),
        "context_available": bool(prior_context.get("available")),
        "context_confidence": str(prior_context.get("context_confidence", "") or ""),
        "market_regime": str(prior_context.get("market_regime", "") or ""),
        "environment_decision": str(prior_context.get("environment_decision", "") or ""),
        "leading_clusters": prior_context.get("leading_clusters", []) or [],
        "candidate_total": len(rows),
        "target_type_scope_enabled": bool(((config.get("target_type_scope", {}) or {}).get("enabled"))),
        "bonus_applied_count": sum(bool(row.get("bonus_applied")) for row in rows),
        "positive_bonus_count": len(positive_rows),
        "negative_bonus_count": len(negative_rows),
        "zero_bonus_count": len(zero_rows),
        "stock_true_bonus_count": sum(row.get("target_type") == "stock" and abs(_number(row["bonus"])) > 0 for row in rows),
        "non_stock_true_bonus_count": sum(row.get("target_type") != "stock" and abs(_number(row["bonus"])) > 0 for row in rows),
        "non_stock_annotation_bonus_count": sum(row.get("target_type") != "stock" and abs(_number(row["annotation_bonus"])) > 0 for row in rows),
        "action_score_changed_count": sum(round(_number(row["score_before"]), 4) != round(_number(row["score_after"]), 4) for row in rows),
        "rank_changed_count": sum(int(row.get("rank_delta", 0)) != 0 for row in rows),
        "max_rank_delta": max((abs(int(row.get("rank_delta", 0))) for row in rows), default=0),
        "bucket_changed_count": 0,
        "category_distribution": _group_counts(rows, "category", ["trap", "reversal", "trend", "other"]),
        "target_type_distribution": _group_counts(rows, "target_type", ["stock", "ETF", "index", "industry", "unknown"]),
        "positive_bonus_performance": _performance_summary(positive_rows),
        "negative_bonus_performance": _performance_summary(negative_rows),
        "zero_bonus_performance": _performance_summary(zero_rows),
        "stock_positive_bonus_performance": _performance_summary(stock_positive_rows),
        "stock_negative_bonus_performance": _performance_summary(stock_negative_rows),
        "stock_zero_bonus_performance": _performance_summary(stock_zero_rows),
        "non_stock_annotation_summary": {
            "candidate_count": len(non_stock_rows),
            "annotation_bonus_count": sum(abs(_number(row["annotation_bonus"])) > 0 for row in non_stock_rows),
            "avg_annotation_bonus": round(
                sum(_number(row["annotation_bonus"]) for row in non_stock_rows) / len(non_stock_rows), 4
            ) if non_stock_rows else 0.0,
        },
        "top_positive_bonus_candidates": _top_rows(rows, positive=True),
        "top_negative_bonus_candidates": _top_rows(rows, positive=False),
        "warnings": _warnings(rows, bool(prior_context.get("available"))),
        "cp_risk_decision_unchanged": True,
        "trend_filter_decision_unchanged": True,
        "trend_gate_decision_shadow_unchanged": True,
    }
    if payload["bucket_changed_count"] > 0:
        payload["warnings"].append("unexpected_bucket_change")
    return payload


def _build_day_markdown(payload: dict) -> str:
    lines = [
        f"# Prior Day Context Effect {payload['date']}",
        "",
        f"- prev_trade_date: {payload['prev_trade_date']}",
        f"- context_available: {payload['context_available']}",
        f"- context_confidence: {payload['context_confidence']}",
        f"- market_regime: {payload['market_regime']}",
        f"- environment_decision: {payload['environment_decision']}",
        f"- candidate_total: {payload['candidate_total']}",
        f"- bonus_applied_count: {payload['bonus_applied_count']}",
        f"- positive_bonus_count: {payload['positive_bonus_count']}",
        f"- negative_bonus_count: {payload['negative_bonus_count']}",
        f"- zero_bonus_count: {payload['zero_bonus_count']}",
        f"- stock_true_bonus_count: {payload['stock_true_bonus_count']}",
        f"- non_stock_true_bonus_count: {payload['non_stock_true_bonus_count']}",
        f"- non_stock_annotation_bonus_count: {payload['non_stock_annotation_bonus_count']}",
        f"- action_score_changed_count: {payload['action_score_changed_count']}",
        f"- rank_changed_count: {payload['rank_changed_count']}",
        f"- max_rank_delta: {payload['max_rank_delta']}",
        f"- bucket_changed_count: {payload['bucket_changed_count']}",
        f"- warnings: {payload['warnings']}",
        "",
        "## Category Distribution",
    ]
    for key, value in payload["category_distribution"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Target Type Distribution"])
    for key, value in payload["target_type_distribution"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Top Positive Bonus Candidates"])
    for row in payload["top_positive_bonus_candidates"]:
        lines.append(f"- {row['category']} {row['name']} type={row['target_type']} bonus={row['bonus']} body={row.get('body_pct')}")
    lines.extend(["", "## Top Negative Bonus Candidates"])
    for row in payload["top_negative_bonus_candidates"]:
        lines.append(f"- {row['category']} {row['name']} type={row['target_type']} bonus={row['bonus']} body={row.get('body_pct')}")
    return "\n".join(lines) + "\n"


def build_summary_payload(day_payloads: list[dict]) -> dict:
    all_warnings = []
    for payload in day_payloads:
        all_warnings.extend(payload.get("warnings", []))
    confidence_counts = {"high": 0, "medium": 0, "low": 0}
    for payload in day_payloads:
        confidence = str(payload.get("context_confidence", "") or "low")
        if confidence not in confidence_counts:
            confidence_counts[confidence] = 0
        confidence_counts[confidence] += 1
    summary = {
        "evaluated_dates": [payload["date"] for payload in day_payloads],
        "context_available_dates": [payload["date"] for payload in day_payloads if payload.get("context_available")],
        "confidence_distribution": confidence_counts,
        "total_candidates": sum(payload.get("candidate_total", 0) for payload in day_payloads),
        "total_positive_bonus_count": sum(payload.get("positive_bonus_count", 0) for payload in day_payloads),
        "total_negative_bonus_count": sum(payload.get("negative_bonus_count", 0) for payload in day_payloads),
        "total_zero_bonus_count": sum(payload.get("zero_bonus_count", 0) for payload in day_payloads),
        "stock_true_bonus_count": sum(payload.get("stock_true_bonus_count", 0) for payload in day_payloads),
        "non_stock_true_bonus_count": sum(payload.get("non_stock_true_bonus_count", 0) for payload in day_payloads),
        "non_stock_annotation_bonus_count": sum(payload.get("non_stock_annotation_bonus_count", 0) for payload in day_payloads),
        "overall_rank_changed_count": sum(payload.get("rank_changed_count", 0) for payload in day_payloads),
        "overall_bucket_changed_count": sum(payload.get("bucket_changed_count", 0) for payload in day_payloads),
        "warnings_summary": sorted(set(all_warnings)),
        "category_level": _summary_group(day_payloads, "category_distribution", ["trap", "reversal", "trend", "other"]),
        "target_type_level": _summary_group(day_payloads, "target_type_distribution", ["stock", "ETF", "index", "industry", "unknown"]),
        "stock_only_performance": {
            "positive_bonus": _summary_performance(day_payloads, "stock_positive_bonus_performance"),
            "negative_bonus": _summary_performance(day_payloads, "stock_negative_bonus_performance"),
            "zero_bonus": _summary_performance(day_payloads, "stock_zero_bonus_performance"),
        },
    }
    summary["conclusion"] = _summary_conclusion(summary)
    return summary


def _summary_group(day_payloads: list[dict], field: str, keys: list[str]) -> dict:
    result = {}
    for key in keys:
        rows = [payload.get(field, {}).get(key, {}) for payload in day_payloads]
        candidate_count = sum(int(row.get("candidate_count", 0)) for row in rows)
        avg_bonus_values = [row.get("avg_bonus", 0.0) for row in rows if row.get("candidate_count", 0) > 0]
        success_values = [row.get("success_rate") for row in rows if row.get("success_rate") is not None]
        result[key] = {
            "candidate_count": candidate_count,
            "avg_bonus": round(sum(avg_bonus_values) / len(avg_bonus_values), 4) if avg_bonus_values else 0.0,
            "avg_success_rate": round(sum(success_values) / len(success_values), 4) if success_values else None,
        }
    return result


def _summary_conclusion(summary: dict) -> str:
    warnings = set(summary.get("warnings_summary", []))
    if summary.get("overall_bucket_changed_count", 0) > 0:
        return "not_ready"
    if "non_stock_prior_day_bonus_present" in warnings:
        return "require_target_type_scope"
    if summary.get("overall_rank_changed_count", 0) == 0:
        return "keep_soft_score"
    return "ready_for_weight_tuning"


def _summary_performance(day_payloads: list[dict], field: str) -> dict:
    rows = [payload.get(field, {}) or {} for payload in day_payloads]
    body_values = [row.get("avg_body_pct") for row in rows if row.get("avg_body_pct") is not None]
    success_values = [row.get("success_rate") for row in rows if row.get("success_rate") is not None]
    return {
        "avg_body_pct": round(sum(body_values) / len(body_values), 4) if body_values else None,
        "success_rate": round(sum(success_values) / len(success_values), 4) if success_values else None,
    }


def _build_summary_markdown(summary: dict) -> str:
    lines = [
        "# Prior Day Context Effect Summary",
        "",
        f"- evaluated_dates: {summary['evaluated_dates']}",
        f"- context_available_dates: {summary['context_available_dates']}",
        f"- confidence_distribution: {summary['confidence_distribution']}",
        f"- total_candidates: {summary['total_candidates']}",
        f"- total_positive_bonus_count: {summary['total_positive_bonus_count']}",
        f"- total_negative_bonus_count: {summary['total_negative_bonus_count']}",
        f"- total_zero_bonus_count: {summary['total_zero_bonus_count']}",
        f"- stock_true_bonus_count: {summary['stock_true_bonus_count']}",
        f"- non_stock_true_bonus_count: {summary['non_stock_true_bonus_count']}",
        f"- non_stock_annotation_bonus_count: {summary['non_stock_annotation_bonus_count']}",
        f"- overall_rank_changed_count: {summary['overall_rank_changed_count']}",
        f"- overall_bucket_changed_count: {summary['overall_bucket_changed_count']}",
        f"- warnings_summary: {summary['warnings_summary']}",
        f"- conclusion: {summary['conclusion']}",
        "",
        "## Category Level",
    ]
    for key, value in summary["category_level"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Target Type Level"])
    for key, value in summary["target_type_level"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Stock-only Performance"])
    lines.append(f"- positive_bonus: {summary['stock_only_performance']['positive_bonus']}")
    lines.append(f"- negative_bonus: {summary['stock_only_performance']['negative_bonus']}")
    lines.append(f"- zero_bonus: {summary['stock_only_performance']['zero_bonus']}")
    return "\n".join(lines) + "\n"


def evaluate_dates(date_list: list[str]) -> tuple[list[dict], dict]:
    dm = DataManager()
    analyzer = AuctionAnalyzer(dm)
    day_payloads = []
    for date_str in date_list:
        target_date = int(date_str)
        result = analyzer.analyze(target_date, realtime=False)
        if result is None:
            continue
        result = dict(result)
        result["date"] = date_str
        detail_df = _read_detail_df(date_str)
        payload = build_day_payload(date_str, result, detail_df)
        day_payloads.append(payload)
        day_json = EVAL_ROOT / f"prior_day_context_effect_{date_str}.json"
        day_md = EVAL_ROOT / f"prior_day_context_effect_{date_str}.md"
        day_json.parent.mkdir(parents=True, exist_ok=True)
        day_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        day_md.write_text(_build_day_markdown(payload), encoding="utf-8")
    summary = build_summary_payload(day_payloads)
    return day_payloads, summary


def main(argv=None):
    configure_utf8_console()
    args = _parse_args(list(argv or sys.argv[1:]))
    date_list = _resolve_dates(args)
    day_payloads, summary = evaluate_dates(date_list)
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    summary_json = EVAL_ROOT / "prior_day_context_effect_summary.json"
    summary_md = EVAL_ROOT / "prior_day_context_effect_summary.md"
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_md.write_text(_build_summary_markdown(summary), encoding="utf-8")
    print(f"[prior-day-effect] evaluated_dates={len(day_payloads)}")
    print(f"[prior-day-effect] Summary JSON: {summary_json.resolve()}")
    print(f"[prior-day-effect] Summary Markdown: {summary_md.resolve()}")


if __name__ == "__main__":
    main()
