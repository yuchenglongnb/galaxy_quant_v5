# -*- coding: utf-8 -*-
"""Analysis-only temporal decision feedback matrix seed builder.

This module turns existing validation reports into a partial temporal feedback
matrix. It reads local reports only, supports dry-run/output-dir flows, and does
not write lesson, pattern, registry, evaluator, config, strategy, or trading
execution files.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRIOR_DAY_GLOB = "reports/analysis/evaluations/prior_day_context_stock_effect_*.json"
DEFAULT_PATH_DISTRIBUTION = ROOT / "reports" / "analysis" / "replay" / "20260626_20260702_intraday_path_distribution_summary.json"
DEFAULT_GATE_REVIEW = ROOT / "reports" / "analysis" / "replay" / "20260626_20260702_path_stability_gate_review_summary.json"
DEFAULT_OUTPUT_DIR = ROOT / "reports" / "analysis" / "evaluations"


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
) -> dict:
    prior_day_paths = [
        path for path in ROOT.glob(prior_day_glob)
        if not date_start or path.stem.rsplit("_", 1)[-1] >= date_start
        if not date_end or path.stem.rsplit("_", 1)[-1] <= date_end or path.name.endswith("_summary.json")
    ]
    records, prior_sources = _prior_day_records(prior_day_paths)
    path_summary, path_source = _path_distribution_summary(path_distribution)
    gate_summary, gate_source = _gate_review_summary(gate_review)
    missing_sources = [
        source for source in [path_source, gate_source]
        if source.get("status") in {"missing", "unreadable"}
    ]
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
            "schema_version": "p2.0_seed",
            "record_count": len(records),
        },
        "sources": {
            "prior_day_context": prior_sources,
            "intraday_path_distribution": path_source,
            "path_stability_gate": gate_source,
        },
        "missing_sources": missing_sources,
        "measurable_pairs": [
            "prior_day_context -> same_day_close",
            "prior_day_context -> rank_change",
            "prior_day_context -> body_pct",
            "prior_day_context -> validation_success",
        ],
        "missing_capabilities": [
            "auction -> same_day_0935",
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


def write_outputs(matrix: dict, output_dir: str | Path | None = None):
    root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "temporal_feedback_matrix_seed.json"
    md_path = root / "temporal_feedback_matrix_seed.md"
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
    parser.add_argument("--output-dir", default="")
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
    )
    if args.dry_run:
        print(json.dumps({
            "dry_run": True,
            "record_count": matrix["metadata"]["record_count"],
            "missing_sources": matrix["missing_sources"],
            "measurable_pairs": matrix["measurable_pairs"],
        }, ensure_ascii=False, indent=2))
        return matrix
    json_path, md_path = write_outputs(matrix, args.output_dir or None)
    print(json.dumps({"json": str(json_path), "md": str(md_path)}, ensure_ascii=False, indent=2))
    return matrix


if __name__ == "__main__":
    main()
