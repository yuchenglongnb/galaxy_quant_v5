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


def build_pack(dates, analysis_root, validation_root, sector_only_dates=None):
    analysis_root = Path(analysis_root)
    validation_root = Path(validation_root)
    sector_only = {str(value) for value in sector_only_dates or []}
    feature_rows = []
    reviews = {}
    for date in dates:
        date = str(date)
        detail = _read_csv(validation_root / date / "signal_detail.csv")
        metrics = _read_csv(validation_root / date / "signal_metrics.csv")
        features = PriorDayOutcomeFeatureBuilder.build(detail, metrics)
        validation_level = "candidate_close" if not detail.empty else ("sector_only" if date in sector_only else "missing")
        feature_rows.append({"date": date, "validation_level": validation_level, **features})
        reviews[date] = _read_json(analysis_root / date / "auction_review.json")

    by_date = {row["date"]: row for row in feature_rows}
    transitions = []
    for decision_date, feedback_date in zip(dates, dates[1:]):
        decision_date = str(decision_date)
        feedback_date = str(feedback_date)
        feedback_level = by_date[feedback_date]["validation_level"]
        feedback_features = by_date[feedback_date] if feedback_level == "candidate_close" else None
        transitions.append(build_transition_record(
            decision_date,
            feedback_date,
            reviews.get(decision_date, {}),
            by_date[decision_date],
            feedback_features,
            feedback_level,
        ))
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "observation_only": True,
        "active_gate_changed": False,
        "outcome_features": feature_rows,
        "transitions": transitions,
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
        "| decision | feedback | baseline | shadow | level | feedback label | contradictions |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in payload["transitions"]:
        lines.append(
            f"| {row['decision_date']} | {row['feedback_date']} | {row['baseline_environment_decision'] or '-'} | "
            f"{row['shadow_state']} | {row['validation_level']} | {row['feedback_label']} | "
            f"{', '.join(row['contradiction_labels']) or '-'} |"
        )
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dates", required=True)
    parser.add_argument("--analysis-root", required=True)
    parser.add_argument("--validation-root", required=True)
    parser.add_argument("--sector-only-dates", default="")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--date-label", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    split = lambda value: [item.strip() for item in value.split(",") if item.strip()]
    payload = build_pack(
        split(args.dates),
        args.analysis_root,
        args.validation_root,
        split(args.sector_only_dates),
    )
    if args.dry_run:
        print(json.dumps({
            "feature_dates": len(payload["outcome_features"]),
            "transition_count": len(payload["transitions"]),
        }, ensure_ascii=False))
        return payload
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    feature_payload = {key: payload[key] for key in ("generated_at", "observation_only", "active_gate_changed", "outcome_features")}
    transition_payload = {key: payload[key] for key in ("generated_at", "observation_only", "active_gate_changed", "transitions")}
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
