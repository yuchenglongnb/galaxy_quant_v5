"""Generate P2.4 outcome-feature and close-to-T+1 evaluation packs."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.context.prior_day_outcome_features import PriorDayOutcomeFeatureBuilder
from reports.daily_validation_level import derive_daily_validation_level
from reports.state_transition_feedback import build_transition_record


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


def build_pack(
    dates,
    analysis_root,
    validation_root,
    sector_only_dates=None,
    availability_records=None,
    sector_evidence=None,
):
    analysis_root = Path(analysis_root)
    validation_root = Path(validation_root)
    sector_only = {str(value) for value in sector_only_dates or []}
    availability_by_date = {
        str(row.get("date")): row for row in (availability_records or [])
    }
    feature_rows = []
    reviews = {}
    for date in dates:
        date = str(date)
        detail = _read_csv(validation_root / date / "signal_detail.csv")
        metrics = _read_csv(validation_root / date / "signal_metrics.csv")
        review = _read_json(analysis_root / date / "auction_review.json")
        features = PriorDayOutcomeFeatureBuilder.build(detail, metrics)
        legacy_sector_evidence = sector_evidence
        if date in sector_only and not sector_evidence:
            legacy_sector_evidence = {
                "date_start": date,
                "date_end": date,
                "records": [{"daily_return_available": False}],
            }
        validation = derive_daily_validation_level(
            date,
            detail,
            metrics,
            review,
            availability_record=availability_by_date.get(date),
            sector_evidence=legacy_sector_evidence,
        )
        market_regime = review.get("market_regime", "")
        if isinstance(market_regime, dict):
            market_regime = market_regime.get("label", "")
        feature_rows.append({
            "date": date,
            "validation_level": validation["validation_level"],
            "validation_reasons": validation["reasons"],
            "sector_context": validation["sector_context"],
            "market_regime": str(market_regime or ""),
            **features,
        })
        reviews[date] = review

    by_date = {row["date"]: row for row in feature_rows}
    transitions = []
    for decision_date, feedback_date in zip(dates, dates[1:]):
        decision_date = str(decision_date)
        feedback_date = str(feedback_date)
        decision_level = by_date[decision_date]["validation_level"]
        feedback_level = by_date[feedback_date]["validation_level"]
        feedback_features = by_date[feedback_date] if feedback_level == "candidate_close" else None
        transitions.append(build_transition_record(
            decision_date,
            feedback_date,
            reviews.get(decision_date, {}),
            by_date[decision_date],
            feedback_features,
            decision_validation_level=decision_level,
            feedback_validation_level=feedback_level,
            sector_context=by_date[feedback_date].get("sector_context"),
        ))
    valid_pair_count = sum(
        bool(row.get("counts_as_valid_candidate_pair")) for row in transitions
    )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "observation_only": True,
        "active_gate_changed": False,
        "outcome_features": feature_rows,
        "transitions": transitions,
        "valid_candidate_pair_count": valid_pair_count,
    }


def _features_markdown(payload):
    lines = [
        "# Prior-day Outcome Features",
        "",
        "All thresholds are analysis-only shadow thresholds and are not active strategy rules.",
        "",
        "| date | level | trend n | trend rate | avg body | selloff | broad risk | top1 | top3 | confidence |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in payload["outcome_features"]:
        lines.append(
            f"| {row['date']} | {row['validation_level']} | {row['prior_trend_sample_count']} | "
            f"{row['prior_trend_success_rate']} | {row['prior_trend_avg_body']} | "
            f"{row['one_way_selloff_ratio']} | {row['broad_path_risk_ratio']} | "
            f"{row['cluster_top1_positive_share']} | {row['cluster_top3_positive_share']} | "
            f"{row['feature_confidence']} |"
        )
    return "\n".join(lines) + "\n"


def _transitions_markdown(payload):
    lines = [
        "# State Transition Feedback",
        "",
        "Candidate-level and sector-only evidence are kept separate.",
        "",
        "| decision | feedback | baseline | shadow | decision level | feedback level | valid pair | feedback label | contradictions |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in payload["transitions"]:
        lines.append(
            f"| {row['decision_date']} | {row['feedback_date']} | {row['baseline_environment_decision'] or '-'} | "
            f"{row['shadow_state']} | {row['decision_validation_level']} | "
            f"{row['feedback_validation_level']} | {row['counts_as_valid_candidate_pair']} | "
            f"{row['feedback_label']} | "
            f"{', '.join(row['contradiction_labels']) or '-'} |"
        )
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dates", required=True)
    parser.add_argument("--analysis-root", required=True)
    parser.add_argument("--validation-root", required=True)
    parser.add_argument("--sector-only-dates", default="")
    parser.add_argument("--availability-json", default="")
    parser.add_argument("--sector-evidence-json", default="")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--date-label", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    split = lambda value: [item.strip() for item in value.split(",") if item.strip()]
    availability_payload = _read_json(args.availability_json) if args.availability_json else {}
    sector_evidence = _read_json(args.sector_evidence_json) if args.sector_evidence_json else {}
    payload = build_pack(
        split(args.dates),
        args.analysis_root,
        args.validation_root,
        split(args.sector_only_dates),
        availability_payload.get("records", []),
        sector_evidence,
    )
    if args.dry_run:
        print(json.dumps({
            "feature_dates": len(payload["outcome_features"]),
            "transition_count": len(payload["transitions"]),
            "valid_candidate_pair_count": payload["valid_candidate_pair_count"],
        }, ensure_ascii=False))
        return payload
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    feature_payload = {key: payload[key] for key in ("generated_at", "observation_only", "active_gate_changed", "outcome_features")}
    transition_payload = {key: payload[key] for key in ("generated_at", "observation_only", "active_gate_changed", "valid_candidate_pair_count", "transitions")}
    (output_dir / f"prior_day_outcome_features_{args.date_label}.json").write_text(
        json.dumps(feature_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / f"prior_day_outcome_features_{args.date_label}.md").write_text(
        _features_markdown(payload), encoding="utf-8"
    )
    (output_dir / f"state_transition_feedback_{args.date_label}.json").write_text(
        json.dumps(transition_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / f"state_transition_feedback_{args.date_label}.md").write_text(
        _transitions_markdown(payload), encoding="utf-8"
    )
    return payload


if __name__ == "__main__":
    main()
