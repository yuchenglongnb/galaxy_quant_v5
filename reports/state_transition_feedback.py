"""Build close-to-T+1 observation-only state-transition feedback records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from analyzers.context.prior_day_outcome_features import PriorDayOutcomeFeatureBuilder
from analyzers.context.state_transition_shadow import StateTransitionShadow


def _read_json(path):
    path = Path(path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _read_csv(path):
    path = Path(path)
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        return pd.DataFrame()


def build_transition_record(
    decision_date,
    feedback_date,
    decision_review,
    decision_features,
    feedback_features=None,
    validation_level="candidate_close",
):
    baseline = (decision_review or {}).get("environment_gate", {}) or {}
    shadow = StateTransitionShadow.evaluate(baseline, decision_features)
    feedback_features = feedback_features or {}
    next_rate = feedback_features.get("prior_trend_success_rate")
    next_body = feedback_features.get("prior_trend_avg_body")
    candidate_available = validation_level == "candidate_close" and bool(feedback_features)
    next_broad_failure = candidate_available and (
        (next_rate is not None and float(next_rate) < 45)
        and (next_body is not None and float(next_body) < 0)
    )
    next_concentration = StateTransitionShadow.cluster_concentration_status(feedback_features)
    next_concentrated = candidate_available and next_concentration["concentrated"]

    contradictions = list(shadow.get("contradiction_labels", []))
    if not candidate_available:
        feedback_label = (
            "sector_only_partial_confirmation" if validation_level == "sector_only" else "missing_candidate_feedback"
        )
        contradictions.append("candidate_feedback_missing")
    elif str(baseline.get("decision", "")) == "trend_enabled" and next_broad_failure:
        feedback_label = "broad_continuation_failed"
        contradictions.append("baseline_trend_enabled_but_broad_trend_failed")
    elif shadow.get("label") == "rotational_repair_with_broad_trend_failure_risk" and next_broad_failure and next_concentrated:
        feedback_label = "rotational_repair_confirmed"
    elif shadow.get("broad_trend_failure_risk") and next_broad_failure:
        feedback_label = "broad_failure_confirmed"
    elif shadow.get("label") == "broad_continuation_supported" and not next_broad_failure:
        feedback_label = "broad_continuation_confirmed"
    else:
        feedback_label = "mixed_transition"

    if next_broad_failure and next_concentrated:
        contradictions.append("broad_failure_but_cluster_repair")
    return {
        "decision_id": f"close:{decision_date}:state_transition",
        "decision_date": str(decision_date),
        "feedback_date": str(feedback_date),
        "decision_timepoint": "close",
        "feedback_timepoint": "t1_close",
        "baseline_regime": str(((decision_review or {}).get("market_regime", {}) or {}).get("label", "")),
        "baseline_environment_decision": str(baseline.get("decision", "")),
        "shadow_state": shadow.get("label"),
        "prior_outcome_features": decision_features,
        "next_day_regime": "" if not candidate_available else str(feedback_features.get("market_regime", "")),
        "next_day_trend_success_rate": next_rate if candidate_available else None,
        "next_day_trend_avg_body": next_body if candidate_available else None,
        "next_day_path_distribution": feedback_features.get("path_distribution", {}) if candidate_available else {},
        "next_day_cluster_concentration": {
            "top1_share": feedback_features.get("cluster_top1_positive_share"),
            "top3_share": feedback_features.get("cluster_top3_positive_share"),
            "denominator": next_concentration["denominator"],
            "usable": next_concentration["usable"],
            "reason": next_concentration["reason"],
        } if candidate_available else {},
        "validation_level": validation_level,
        "feedback_label": feedback_label,
        "contradiction_labels": sorted(set(contradictions)),
        "data_available": candidate_available,
        "counts_as_candidate_transition": candidate_available,
        "missing_reason": "" if candidate_available else "candidate_level_feedback_unavailable",
        "review_status": "analysis_only_state_transition",
    }


def build_from_roots(decision_date, feedback_date, analysis_root, validation_root, validation_level=None):
    analysis_root = Path(analysis_root)
    validation_root = Path(validation_root)
    decision_review = _read_json(analysis_root / str(decision_date) / "auction_review.json")
    decision_detail = _read_csv(validation_root / str(decision_date) / "signal_detail.csv")
    decision_metrics = _read_csv(validation_root / str(decision_date) / "signal_metrics.csv")
    feedback_detail = _read_csv(validation_root / str(feedback_date) / "signal_detail.csv")
    feedback_metrics = _read_csv(validation_root / str(feedback_date) / "signal_metrics.csv")
    feedback_review = _read_json(analysis_root / str(feedback_date) / "auction_review.json")
    decision_features = PriorDayOutcomeFeatureBuilder.build(decision_detail, decision_metrics)
    feedback_features = PriorDayOutcomeFeatureBuilder.build(feedback_detail, feedback_metrics)
    feedback_features["market_regime"] = str(
        ((feedback_review.get("market_regime", {}) or {}).get("label", ""))
    )
    if validation_level is None:
        validation_level = "candidate_close" if not feedback_detail.empty else "missing"
    return build_transition_record(
        decision_date,
        feedback_date,
        decision_review,
        decision_features,
        feedback_features if not feedback_detail.empty else None,
        validation_level,
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-date", required=True)
    parser.add_argument("--feedback-date", required=True)
    parser.add_argument("--analysis-root", default="reports/analysis/daily")
    parser.add_argument("--validation-root", default="reports/validation/daily")
    parser.add_argument("--validation-level")
    parser.add_argument("--output")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    record = build_from_roots(
        args.decision_date,
        args.feedback_date,
        args.analysis_root,
        args.validation_root,
        args.validation_level,
    )
    if args.dry_run or not args.output:
        print(json.dumps(record, ensure_ascii=False, indent=2))
    else:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


if __name__ == "__main__":
    main()
