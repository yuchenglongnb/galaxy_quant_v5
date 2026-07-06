# -*- coding: utf-8 -*-
"""Analysis-only temporal decision feedback matrix seed builder.

This module turns existing validation reports into a partial temporal feedback
matrix. It reads local reports only, supports dry-run/output-dir flows, and does
not write lesson, pattern, registry, evaluator, config, strategy, or trading
execution files.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRIOR_DAY_GLOB = "reports/analysis/evaluations/prior_day_context_stock_effect_*.json"
DEFAULT_PATH_DISTRIBUTION = ROOT / "reports" / "analysis" / "replay" / "20260626_20260702_intraday_path_distribution_summary.json"
DEFAULT_GATE_REVIEW = ROOT / "reports" / "analysis" / "replay" / "20260626_20260702_path_stability_gate_review_summary.json"
DEFAULT_OUTPUT_DIR = ROOT / "reports" / "analysis" / "evaluations"
DEFAULT_DAILY_VALIDATION_ROOT = ROOT / "reports" / "validation" / "daily"
DEFAULT_0935_ROOT = ROOT / "AmazingData_Store"


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _number(value, default=None):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


def _text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _bool(value):
    if isinstance(value, bool):
        return value
    text = _text(value).lower()
    if text in {"true", "1", "yes", "y", "success"}:
        return True
    if text in {"false", "0", "no", "n", "failed", "failure"}:
        return False
    return None


def feedback_label(performance: dict) -> str:
    if not performance or not performance.get("performance_available"):
        return "missing_feedback"
    avg_body = _number(performance.get("avg_body_pct"), 0.0)
    success_rate = _number(performance.get("success_rate"), 0.0)
    if avg_body is not None and avg_body > 0 and success_rate is not None and success_rate >= 50:
        return "confirmed_close"
    if avg_body is not None and avg_body < 0 and success_rate is not None and success_rate < 50:
        return "failed_close"
    return "mixed_close"


def contradiction_labels(decision_group: str, performance: dict, rank_changed_count: int = 0) -> list[str]:
    labels = []
    if not performance or not performance.get("performance_available"):
        return labels
    avg_body = _number(performance.get("avg_body_pct"), 0.0) if performance else 0.0
    success_rate = _number(performance.get("success_rate"), 0.0) if performance else 0.0
    if decision_group == "positive_bonus" and (avg_body is not None and avg_body < 0 or success_rate is not None and success_rate < 50):
        labels.append("positive_context_but_weak_path")
    if decision_group == "negative_bonus" and (avg_body is not None and avg_body > 0 or success_rate is not None and success_rate >= 50):
        labels.append("negative_context_but_strong_path")
    if rank_changed_count and decision_group == "positive_bonus" and avg_body is not None and avg_body < 0:
        labels.append("rank_up_but_path_weak")
    if rank_changed_count and decision_group == "negative_bonus" and avg_body is not None and avg_body > 0:
        labels.append("rank_down_but_path_strong")
    return labels


def daily_feedback_label(row: dict) -> str:
    success = _bool(row.get("validation_success"))
    body_pct = _number(row.get("body_pct"))
    if success is True and body_pct is not None and body_pct > 0:
        return "confirmed_close"
    if success is False and body_pct is not None and body_pct < 0:
        return "failed_close"
    if body_pct is not None:
        return "mixed_close"
    return "missing_feedback"


def daily_contradiction_labels(row: dict) -> list[str]:
    labels = []
    path_type = _text(row.get("signal_path_type"))
    body_pct = _number(row.get("body_pct"))
    success = _bool(row.get("validation_success"))
    if path_type in {"high_open_trap", "rush_up_fade", "one_way_selloff"}:
        labels.append("path_risk_after_auction")
    if success is True and path_type in {"rush_up_fade", "high_open_trap"}:
        labels.append("close_success_but_intraday_fade_risk")
    if success is False and path_type in {"close_near_high", "low_open_rebound", "low_open_rebound_failed"}:
        labels.append("close_failed_but_path_repaired")
    if body_pct is not None and body_pct < 0 and path_type in {"high_open_trap", "one_way_selloff"}:
        labels.append("auction_strength_failed_close")
    if body_pct is not None and body_pct > 0 and path_type in {"close_near_high", "range_chop"}:
        labels.append("auction_feedback_confirmed_close")
    return labels


def _date_selected(date: str, selected_dates: set[str], date_start: str, date_end: str) -> bool:
    if selected_dates and date not in selected_dates:
        return False
    if date_start and date < date_start:
        return False
    if date_end and date > date_end:
        return False
    return True


def _daily_validation_paths(root: Path, selected_dates: set[str], date_start: str, date_end: str) -> list[Path]:
    if not root.exists():
        return []
    paths = []
    for path in sorted(root.glob("*/signal_detail.csv")):
        date = path.parent.name
        if _date_selected(date, selected_dates, date_start, date_end):
            paths.append(path)
    return paths


def _daily_validation_records(
    daily_validation_root: Path = DEFAULT_DAILY_VALIDATION_ROOT,
    dates: list[str] | None = None,
    date_start: str = "",
    date_end: str = "",
) -> tuple[list[dict], list[dict], list[dict]]:
    records = []
    sources = []
    missing_sources = []
    selected_dates = {date.strip() for date in dates or [] if date.strip()}
    if not daily_validation_root.exists():
        missing_sources.append({"path": _repo_path(daily_validation_root), "status": "missing_daily_validation_root"})
        return records, sources, missing_sources

    detail_paths = _daily_validation_paths(daily_validation_root, selected_dates, date_start, date_end)
    if selected_dates:
        found = {path.parent.name for path in detail_paths}
        for date in sorted(selected_dates - found):
            missing_sources.append({
                "path": _repo_path(daily_validation_root / date / "signal_detail.csv"),
                "status": "missing_signal_detail",
                "date": date,
            })

    for detail_path in detail_paths:
        date = detail_path.parent.name
        metrics_path = detail_path.parent / "signal_metrics.csv"
        try:
            with detail_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
        except Exception:
            sources.append({"path": _repo_path(detail_path), "status": "unreadable", "date": date})
            continue
        sources.append({
            "path": _repo_path(detail_path),
            "status": "loaded_signal_detail",
            "date": date,
            "row_count": len(rows),
        })
        if metrics_path.exists():
            sources.append({"path": _repo_path(metrics_path), "status": "loaded_signal_metrics", "date": date})
        else:
            missing_sources.append({"path": _repo_path(metrics_path), "status": "missing_signal_metrics", "date": date})

        for index, row in enumerate(rows, 1):
            code = _text(row.get("code"))
            name = _text(row.get("name"))
            signal_category = _text(row.get("signal_category") or row.get("category"))
            signal_family = _text(row.get("signal_family") or signal_category)
            code_or_name = code or name or f"row{index}"
            body_pct = _number(row.get("body_pct"))
            validation_success = _bool(row.get("validation_success"))
            metric_fields = [
                "body_pct",
                "validation_success",
                "signal_path_type",
                "open_to_high_pct",
                "open_to_low_pct",
                "mfe_pct",
                "mae_pct",
                "close_to_high_drawdown_pct",
                "intraday_range_pct",
                "t1_open_return",
                "t1_close_return",
                "t1_close_positive_rate",
            ]
            metric_set = {}
            for field in metric_fields:
                if field == "validation_success":
                    metric_set[field] = validation_success
                elif field == "signal_path_type":
                    metric_set[field] = _text(row.get(field))
                else:
                    metric_set[field] = _number(row.get(field))
            data_available = body_pct is not None or validation_success is not None or bool(metric_set.get("signal_path_type"))
            records.append({
                "decision_id": f"auction:{date}:{signal_category}:{code_or_name}",
                "trade_date": date,
                "target_code": code,
                "target_name": name,
                "target_type": _text(row.get("target_type")),
                "decision_timepoint": "auction",
                "signal_family": signal_family,
                "signal_category": signal_category,
                "decision_score": _number(row.get("action_score") or row.get("score_base")),
                "decision_rank": _number(row.get("action_rank")),
                "decision_bucket": signal_category,
                "decision_view_fields": {
                    "scenario": _text(row.get("scenario")),
                    "trigger_reason": _text(row.get("trigger_reason")),
                    "market_regime": _text(row.get("market_regime")),
                    "theme_cluster": _text(row.get("theme_cluster")),
                    "validation_scope": _text(row.get("validation_scope")),
                    "data_session_state": _text(row.get("data_session_state")),
                },
                "prior_day_context_bonus": "",
                "cp_risk_decision": _text(row.get("cp")),
                "trend_filter_decision": "",
                "path_type": metric_set.get("signal_path_type", ""),
                "feedback_timepoint": "same_day_close",
                "feedback_date": date,
                "feedback_metric_set": metric_set,
                "feedback_label": daily_feedback_label(row),
                "contradiction_labels": daily_contradiction_labels(row),
                "regime_snapshot": {
                    "market_regime": _text(row.get("market_regime")),
                    "theme_cluster": _text(row.get("theme_cluster")),
                },
                "data_available": data_available,
                "missing_reason": "" if data_available else "daily_validation_feedback_unavailable",
                "review_status": "analysis_only_daily_validation",
            })
    return records, sources, missing_sources


def _increment(counter: dict, key: str):
    key = key or "missing"
    counter[key] = counter.get(key, 0) + 1


def _daily_validation_aggregate(records: list[dict]) -> dict:
    by_date = {}
    by_signal_category = {}
    by_target_type = {}
    by_feedback_label = {}
    by_path_type = {}
    by_contradiction_label = {}
    per_signal = {}
    for record in records:
        _increment(by_date, record.get("trade_date", ""))
        signal_category = record.get("signal_category", "")
        _increment(by_signal_category, signal_category)
        _increment(by_target_type, record.get("target_type", ""))
        _increment(by_feedback_label, record.get("feedback_label", ""))
        _increment(by_path_type, record.get("path_type", ""))
        for label in record.get("contradiction_labels", []):
            _increment(by_contradiction_label, label)
        bucket = per_signal.setdefault(signal_category or "missing", {"count": 0, "success": 0, "body": [], "path_risk_count": 0})
        bucket["count"] += 1
        if record.get("feedback_metric_set", {}).get("validation_success") is True:
            bucket["success"] += 1
        body = _number(record.get("feedback_metric_set", {}).get("body_pct"))
        if body is not None:
            bucket["body"].append(body)
        if "path_risk_after_auction" in record.get("contradiction_labels", []):
            bucket["path_risk_count"] += 1
    return {
        "daily_validation_record_count": len(records),
        "by_date": by_date,
        "by_signal_category": by_signal_category,
        "by_target_type": by_target_type,
        "by_feedback_label": by_feedback_label,
        "by_path_type": by_path_type,
        "by_contradiction_label": by_contradiction_label,
        "success_rate_by_signal_category": {
            key: round(value["success"] / value["count"] * 100, 4) if value["count"] else None
            for key, value in sorted(per_signal.items())
        },
        "avg_body_by_signal_category": {
            key: round(mean(value["body"]), 4) if value["body"] else None
            for key, value in sorted(per_signal.items())
        },
        "path_risk_count_by_signal_category": {
            key: value["path_risk_count"]
            for key, value in sorted(per_signal.items())
        },
    }


def _load_daily_decision_rows(
    daily_validation_root: Path,
    selected_dates: set[str],
    date_start: str,
    date_end: str,
) -> tuple[dict[str, list[dict]], list[dict], list[dict]]:
    rows_by_date = {}
    sources = []
    missing = []
    if not daily_validation_root.exists():
        missing.append({"path": _repo_path(daily_validation_root), "status": "missing_daily_validation_root"})
        return rows_by_date, sources, missing
    detail_paths = _daily_validation_paths(daily_validation_root, selected_dates, date_start, date_end)
    if selected_dates:
        found = {path.parent.name for path in detail_paths}
        for date in sorted(selected_dates - found):
            missing.append({"path": _repo_path(daily_validation_root / date / "signal_detail.csv"), "status": "missing_signal_detail", "date": date})
    for path in detail_paths:
        date = path.parent.name
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
        except Exception:
            sources.append({"path": _repo_path(path), "status": "unreadable", "date": date})
            continue
        rows_by_date[date] = rows
        sources.append({"path": _repo_path(path), "status": "loaded_decision_rows", "date": date, "row_count": len(rows)})
    return rows_by_date, sources, missing


def _confirmation_path(root: Path, date: str) -> Path:
    return root / str(date) / "intraday" / "stock_confirmation_latest.csv"


def _load_0935_rows(path: Path) -> tuple[list[dict], dict]:
    if not path.exists():
        return [], {"path": _repo_path(path), "status": "missing_0935_confirmation"}
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except Exception:
        return [], {"path": _repo_path(path), "status": "unreadable_0935_confirmation"}
    return rows, {"path": _repo_path(path), "status": "loaded_0935_confirmation", "row_count": len(rows)}


def _index_0935_rows(rows: list[dict]) -> tuple[dict[str, dict], dict[str, dict]]:
    by_code = {}
    by_name = {}
    for row in rows:
        code = _text(row.get("code"))
        name = _text(row.get("name"))
        if code:
            by_code[code] = row
        if name:
            by_name[name] = row
    return by_code, by_name


def feedback_0935_label(signal_category: str, row: dict | None) -> str:
    if not row:
        return "missing_0935_feedback"
    price_vs_open = _number(row.get("price_vs_open_pct"))
    pct = _number(row.get("pct"))
    signal_category = signal_category or ""
    if price_vs_open is None and pct is None:
        return "missing_0935_feedback"
    early_strength = price_vs_open if price_vs_open is not None else pct
    if signal_category == "trap":
        if early_strength is not None and early_strength < 0:
            return "auction_confirmed_by_0935"
        if early_strength is not None and early_strength > 0:
            return "auction_failed_by_0935"
    else:
        if early_strength is not None and early_strength > 0:
            return "auction_confirmed_by_0935"
        if early_strength is not None and early_strength < 0:
            return "auction_failed_by_0935"
    return "auction_mixed_by_0935"


def contradiction_0935_labels(signal_category: str, decision_row: dict, confirmation_row: dict | None) -> list[str]:
    if not confirmation_row:
        return []
    labels = []
    auction_pct = _number(decision_row.get("auction_pct"))
    price_vs_open = _number(confirmation_row.get("price_vs_open_pct"))
    pct = _number(confirmation_row.get("pct"))
    rs_vs_index = _number(confirmation_row.get("rs_vs_index_pct"))
    signal_category = signal_category or ""
    label = feedback_0935_label(signal_category, confirmation_row)
    if auction_pct is not None and auction_pct > 0 and price_vs_open is not None and price_vs_open < 0:
        labels.append("auction_high_open_failed_by_0935")
    if auction_pct is not None and auction_pct < 0 and price_vs_open is not None and price_vs_open > 0:
        labels.append("auction_weak_but_recovered_by_0935")
    if signal_category == "trap":
        labels.append("cp_warning_confirmed_early" if label == "auction_confirmed_by_0935" else "cp_warning_failed_early")
    if signal_category == "reversal":
        labels.append("reversal_confirmed_early" if label == "auction_confirmed_by_0935" else "reversal_failed_early")
    if signal_category == "trend":
        labels.append("trend_confirmed_early" if label == "auction_confirmed_by_0935" else "trend_failed_early")
    if rs_vs_index is not None and rs_vs_index < 0 and label == "auction_confirmed_by_0935":
        labels.append("confirmed_0935_but_weak_vs_index")
    return sorted(set(labels))


def _feedback_0935_records(
    feedback_0935_root: Path = DEFAULT_0935_ROOT,
    daily_validation_root: Path = DEFAULT_DAILY_VALIDATION_ROOT,
    dates: list[str] | None = None,
    date_start: str = "",
    date_end: str = "",
) -> tuple[list[dict], list[dict], list[dict]]:
    records = []
    sources = []
    missing = []
    selected_dates = {date.strip() for date in dates or [] if date.strip()}
    decision_rows_by_date, decision_sources, decision_missing = _load_daily_decision_rows(
        daily_validation_root,
        selected_dates,
        date_start,
        date_end,
    )
    sources.extend(decision_sources)
    missing.extend(decision_missing)
    dates_to_load = sorted(decision_rows_by_date)
    if selected_dates:
        dates_to_load = sorted(selected_dates)
    for date in dates_to_load:
        confirmation_rows, source = _load_0935_rows(_confirmation_path(feedback_0935_root, date))
        source["date"] = date
        sources.append(source)
        if not confirmation_rows:
            missing.append({**source, "date": date})
        by_code, by_name = _index_0935_rows(confirmation_rows)
        for index, row in enumerate(decision_rows_by_date.get(date, []), 1):
            code = _text(row.get("code"))
            name = _text(row.get("name"))
            signal_category = _text(row.get("signal_category") or row.get("category"))
            match = by_code.get(code) if code else None
            match = match or (by_name.get(name) if name else None)
            label = feedback_0935_label(signal_category, match)
            metric_set = {
                "auction_open_price": _number(match.get("open")) if match else None,
                "auction_pct": _number(row.get("auction_pct")),
                "price_0935": _number(match.get("last")) if match else None,
                "return_0935_from_open": _number(match.get("price_vs_open_pct")) if match else None,
                "return_0935_from_prev_close": _number(match.get("pct")) if match else None,
                "relative_strength_0935": _number(match.get("rs_vs_index_pct")) if match else None,
                "benchmark_return_0935": None,
                "volume_ratio_0935": _number(match.get("amount_1m_ratio")) if match else None,
                "volume_price_state": _text(match.get("volume_price_state")) if match else "",
            }
            data_available = match is not None
            code_or_name = code or name or f"row{index}"
            records.append({
                "decision_id": f"auction:{date}:{signal_category}:{code_or_name}:0935",
                "trade_date": date,
                "target_code": code,
                "target_name": name,
                "target_type": _text(row.get("target_type")),
                "decision_timepoint": "auction",
                "signal_family": _text(row.get("signal_family") or signal_category),
                "signal_category": signal_category,
                "decision_score": _number(row.get("action_score") or row.get("score_base")),
                "decision_rank": _number(row.get("action_rank")),
                "decision_bucket": signal_category,
                "decision_view_fields": {
                    "scenario": _text(row.get("scenario")),
                    "trigger_reason": _text(row.get("trigger_reason")),
                    "market_regime": _text(row.get("market_regime")),
                    "theme_cluster": _text(row.get("theme_cluster")),
                },
                "prior_day_context_bonus": "",
                "cp_risk_decision": _text(row.get("cp")),
                "trend_filter_decision": "",
                "path_type": "0935_confirmation",
                "feedback_timepoint": "same_day_0935",
                "feedback_date": date,
                "feedback_metric_set": metric_set,
                "feedback_label": label,
                "contradiction_labels": contradiction_0935_labels(signal_category, row, match),
                "regime_snapshot": {
                    "market_regime": _text(row.get("market_regime")),
                    "theme_cluster": _text(row.get("theme_cluster")),
                    "benchmark_source": _text(match.get("benchmark_source")) if match else "",
                },
                "data_available": data_available,
                "missing_reason": "" if data_available else "missing_0935_confirmation_match",
                "review_status": "analysis_only_0935_feedback",
            })
    return records, sources, missing


def _feedback_0935_aggregate(records: list[dict]) -> dict:
    by_feedback_label = {}
    by_signal_category = {}
    by_contradiction_label = {}
    missing_count = 0
    confirmed_count = 0
    failed_count = 0
    for record in records:
        label = record.get("feedback_label", "")
        _increment(by_feedback_label, label)
        _increment(by_signal_category, record.get("signal_category", ""))
        for contradiction in record.get("contradiction_labels", []):
            _increment(by_contradiction_label, contradiction)
        if label == "missing_0935_feedback":
            missing_count += 1
        if label == "auction_confirmed_by_0935":
            confirmed_count += 1
        if label == "auction_failed_by_0935":
            failed_count += 1
    return {
        "record_count": len(records),
        "by_feedback_label": by_feedback_label,
        "by_signal_category": by_signal_category,
        "by_contradiction_label": by_contradiction_label,
        "missing_0935_count": missing_count,
        "confirmed_by_0935_count": confirmed_count,
        "failed_by_0935_count": failed_count,
    }


def _prior_day_records(prior_day_paths: list[Path]) -> tuple[list[dict], list[dict]]:
    records = []
    sources = []
    for path in sorted(prior_day_paths):
        payload = _load_json(path)
        if payload is None:
            sources.append({"path": _repo_path(path), "status": "unreadable"})
            continue
        if path.name.endswith("_summary.json"):
            sources.append({"path": _repo_path(path), "status": "loaded_summary", "dates": payload.get("evaluated_dates", [])})
            continue
        date = str(payload.get("date", "") or path.stem.rsplit("_", 1)[-1])
        rank_changed_count = int(payload.get("rank_changed_count", 0) or 0)
        for group_name in ("positive_bonus", "negative_bonus", "zero_bonus"):
            performance = payload.get(f"{group_name}_performance", {}) or {}
            record = {
                "decision_id": f"prior_day_context:{date}:{group_name}",
                "trade_date": date,
                "target_code": "",
                "target_name": group_name,
                "target_type": "stock_group",
                "decision_timepoint": "auction",
                "signal_family": "prior_day_context",
                "signal_category": group_name,
                "decision_score": None,
                "decision_rank": None,
                "decision_bucket": group_name,
                "decision_view_fields": {
                    "prev_trade_date": payload.get("prev_trade_date", ""),
                    "context_confidence": payload.get("context_confidence", ""),
                    "rank_changed_count": rank_changed_count,
                },
                "prior_day_context_bonus": group_name,
                "cp_risk_decision": "",
                "trend_filter_decision": "",
                "path_type": "same_day_body_proxy",
                "feedback_timepoint": "same_day_close",
                "feedback_date": date,
                "feedback_metric_set": {
                    "avg_body_pct": performance.get("avg_body_pct"),
                    "median_body_pct": performance.get("median_body_pct"),
                    "success_rate": performance.get("success_rate"),
                    "candidate_count": performance.get("candidate_count"),
                },
                "feedback_label": feedback_label(performance),
                "contradiction_labels": contradiction_labels(group_name, performance, rank_changed_count),
                "regime_snapshot": {},
                "data_available": bool(performance.get("performance_available")),
                "missing_reason": "" if performance.get("performance_available") else "performance_unavailable",
                "review_status": "analysis_only_seed",
            }
            records.append(record)
        sources.append({"path": _repo_path(path), "status": "loaded_daily", "date": date})
    return records, sources


def _path_distribution_summary(path: Path) -> tuple[dict, dict]:
    if not path.exists():
        return {}, {"path": _repo_path(path), "status": "missing"}
    payload = _load_json(path)
    if payload is None:
        return {}, {"path": _repo_path(path), "status": "unreadable"}
    metadata = payload.get("metadata", {}) or {}
    return {
        "date_range": payload.get("date_range", {}),
        "analysis_only": payload.get("analysis_only", metadata.get("analysis_only")),
        "input_count": len(payload.get("inputs", []) or []),
        "coverage_count": len(payload.get("input_coverage", []) or []),
    }, {"path": _repo_path(path), "status": "loaded", "date_range": payload.get("date_range", {})}


def _gate_review_summary(path: Path) -> tuple[dict, dict]:
    if not path.exists():
        return {}, {"path": _repo_path(path), "status": "missing"}
    payload = _load_json(path)
    if payload is None:
        return {}, {"path": _repo_path(path), "status": "unreadable"}
    metadata = payload.get("metadata", {}) or {}
    return {
        "overall_status": metadata.get("overall_status"),
        "rule_change_allowed": metadata.get("rule_change_allowed"),
        "coverage_status": (payload.get("gate_results", {}).get("coverage", {}) or {}).get("status"),
    }, {"path": _repo_path(path), "status": "loaded", "overall_status": metadata.get("overall_status")}


def build_matrix(
    prior_day_glob: str = DEFAULT_PRIOR_DAY_GLOB,
    path_distribution: Path = DEFAULT_PATH_DISTRIBUTION,
    gate_review: Path = DEFAULT_GATE_REVIEW,
    date_start: str = "",
    date_end: str = "",
    include_daily_validation: bool = False,
    daily_validation_root: Path = DEFAULT_DAILY_VALIDATION_ROOT,
    dates: list[str] | None = None,
    include_0935_feedback: bool = False,
    feedback_0935_root: Path = DEFAULT_0935_ROOT,
) -> dict:
    prior_day_paths = [
        path for path in ROOT.glob(prior_day_glob)
        if not date_start or path.stem.rsplit("_", 1)[-1] >= date_start
        if not date_end or path.stem.rsplit("_", 1)[-1] <= date_end or path.name.endswith("_summary.json")
    ]
    records, prior_sources = _prior_day_records(prior_day_paths)
    daily_records = []
    daily_sources = []
    daily_missing_sources = []
    if include_daily_validation:
        daily_records, daily_sources, daily_missing_sources = _daily_validation_records(
            daily_validation_root=daily_validation_root,
            dates=dates,
            date_start=date_start,
            date_end=date_end,
        )
        records.extend(daily_records)
    feedback_0935_records = []
    feedback_0935_sources = []
    feedback_0935_missing_sources = []
    if include_0935_feedback:
        feedback_0935_records, feedback_0935_sources, feedback_0935_missing_sources = _feedback_0935_records(
            feedback_0935_root=feedback_0935_root,
            daily_validation_root=daily_validation_root,
            dates=dates,
            date_start=date_start,
            date_end=date_end,
        )
        records.extend(feedback_0935_records)
    path_summary, path_source = _path_distribution_summary(path_distribution)
    gate_summary, gate_source = _gate_review_summary(gate_review)
    missing_sources = [
        source for source in [path_source, gate_source]
        if source.get("status") in {"missing", "unreadable"}
    ]
    missing_sources.extend(daily_missing_sources)
    missing_sources.extend(feedback_0935_missing_sources)
    contradiction_counter = {}
    for record in records:
        for label in record.get("contradiction_labels", []):
            contradiction_counter[label] = contradiction_counter.get(label, 0) + 1
    avg_success = [
        _number(record.get("feedback_metric_set", {}).get("success_rate"))
        for record in records
        if _number(record.get("feedback_metric_set", {}).get("success_rate")) is not None
    ]
    return {
        "metadata": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "analysis_only": True,
            "schema_version": "p2.3_0935_feedback_seed" if include_0935_feedback else ("p2.2_daily_validation_seed" if include_daily_validation else "p2.0_seed"),
            "record_count": len(records),
        },
        "sources": {
            "prior_day_context": prior_sources,
            "daily_validation": daily_sources,
            "feedback_0935": feedback_0935_sources,
            "intraday_path_distribution": path_source,
            "path_stability_gate": gate_source,
        },
        "missing_sources": missing_sources,
        "measurable_pairs": [
            "prior_day_context -> same_day_close",
            "prior_day_context -> rank_change",
            "prior_day_context -> body_pct",
            "prior_day_context -> validation_success",
        ] + ([
            "auction -> same_day_close",
            "auction -> same_day_path_type",
            "auction -> body_pct",
            "auction -> validation_success",
            "auction -> close_feedback_label",
        ] if include_daily_validation else []) + ([
            "auction -> same_day_0935",
            "auction -> 0935_return",
            "auction -> 0935_relative_strength",
            "auction -> 0935_feedback_label",
        ] if include_0935_feedback else []),
        "missing_capabilities": [
            *([] if include_0935_feedback else ["auction -> same_day_0935"]),
            "auction -> same_day_midday",
            "0935 -> same_day_midday",
            "close -> t1_auction",
            "close -> t5_close",
            "close -> t10_close",
            "close -> t20_close",
        ],
        "path_distribution_summary": path_summary,
        "gate_review_summary": gate_summary,
        "aggregate": {
            "record_count": len(records),
            "avg_success_rate": round(mean(avg_success), 4) if avg_success else None,
            "contradiction_counts": contradiction_counter,
            "daily_validation": _daily_validation_aggregate(daily_records),
            "feedback_0935": _feedback_0935_aggregate(feedback_0935_records),
        },
        "records": records,
        "regime_answer_seed": {
            "definition": "Evidence ranking by regime, signal family, feedback horizon, path type, and performance; not trading advice.",
            "current_status": "seed_only_needs_more_feedback_horizons",
        },
        "safety": {
            "trading_advice": False,
            "rule_change_allowed": False,
            "writes_strategy_or_registry": False,
        },
    }


def render_markdown(matrix: dict) -> str:
    lines = [
        "# Temporal Feedback Matrix Seed",
        "",
        "This report is analysis-only. It is not trading advice and does not justify rule changes.",
        "",
        f"- schema_version: `{matrix['metadata']['schema_version']}`",
        f"- record_count: `{matrix['metadata']['record_count']}`",
        f"- measurable_pairs: `{matrix['measurable_pairs']}`",
        f"- missing_capabilities: `{matrix['missing_capabilities']}`",
        f"- aggregate: `{matrix['aggregate']}`",
        "",
        "## Sources",
        "",
    ]
    for name, source in matrix["sources"].items():
        lines.append(f"- {name}: `{source}`")
    lines.extend(["", "## Contradiction Labels", ""])
    for label, count in sorted(matrix["aggregate"]["contradiction_counts"].items()):
        lines.append(f"- {label}: `{count}`")
    lines.extend(["", "## Seed Records", ""])
    for record in matrix["records"][:30]:
        lines.append(
            f"- {record['decision_id']}: feedback={record['feedback_label']}, "
            f"contradictions={record['contradiction_labels']}, metrics={record['feedback_metric_set']}"
        )
    return "\n".join(lines) + "\n"


def write_outputs(matrix: dict, output_dir: str | Path | None = None, output_name: str = "temporal_feedback_matrix_seed"):
    root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / f"{output_name}.json"
    md_path = root / f"{output_name}.md"
    json_path.write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(matrix), encoding="utf-8")
    return json_path, md_path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Build an analysis-only temporal feedback matrix seed.")
    parser.add_argument("--prior-day-glob", default=DEFAULT_PRIOR_DAY_GLOB)
    parser.add_argument("--path-distribution", default=str(DEFAULT_PATH_DISTRIBUTION))
    parser.add_argument("--gate-review", default=str(DEFAULT_GATE_REVIEW))
    parser.add_argument("--date-start", default="")
    parser.add_argument("--date-end", default="")
    parser.add_argument("--dates", default="", help="Comma-separated trade dates for daily validation ingestion.")
    parser.add_argument("--daily-validation-root", default=str(DEFAULT_DAILY_VALIDATION_ROOT))
    parser.add_argument("--include-daily-validation", action="store_true")
    parser.add_argument("--include-0935-feedback", action="store_true")
    parser.add_argument("--feedback-0935-root", default=str(DEFAULT_0935_ROOT))
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--output-name", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    matrix = build_matrix(
        prior_day_glob=args.prior_day_glob,
        path_distribution=Path(args.path_distribution),
        gate_review=Path(args.gate_review),
        date_start=args.date_start,
        date_end=args.date_end,
        include_daily_validation=args.include_daily_validation,
        daily_validation_root=Path(args.daily_validation_root),
        dates=[date.strip() for date in args.dates.split(",") if date.strip()],
        include_0935_feedback=args.include_0935_feedback,
        feedback_0935_root=Path(args.feedback_0935_root),
    )
    if args.dry_run:
        print(json.dumps({
            "dry_run": True,
            "record_count": matrix["metadata"]["record_count"],
            "missing_sources": matrix["missing_sources"],
            "measurable_pairs": matrix["measurable_pairs"],
        }, ensure_ascii=False, indent=2))
        return matrix
    output_name = args.output_name or ("temporal_feedback_matrix_0935_seed" if args.include_0935_feedback else ("temporal_feedback_matrix_daily_validation_seed" if args.include_daily_validation else "temporal_feedback_matrix_seed"))
    json_path, md_path = write_outputs(matrix, args.output_dir or None, output_name=output_name)
    print(json.dumps({"json": str(json_path), "md": str(md_path)}, ensure_ascii=False, indent=2))
    return matrix


if __name__ == "__main__":
    main()
