"""Summarize observation-only state-transition pair coverage."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


def build_coverage(transitions=None, evidence_rows=None, pending_decisions=None, latest_date=""):
    transitions = _dedupe(transitions or [])
    evidence_rows = evidence_rows or []
    pending_decisions = pending_decisions or []
    valid = [row for row in transitions if row.get("counts_as_valid_candidate_pair")]
    excluded = [row for row in transitions if not row.get("counts_as_valid_candidate_pair")]
    regimes = Counter(
        str(row.get("baseline_regime", "") or "") for row in valid
        if str(row.get("baseline_regime", "") or "")
    )
    reasons = Counter(
        reason for row in excluded for reason in row.get("pair_exclusion_reasons", [])
    )
    levels = {str(row.get("date")): str(row.get("validation_level", "")) for row in evidence_rows}

    def pair_has(*names):
        wanted = set(names)
        return sum(
            row.get("decision_validation_level") in wanted
            or row.get("feedback_validation_level") in wanted
            for row in excluded
        )

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "observation_only": True,
        "latest_evidence_date": str(latest_date or max(levels, default="")),
        "total_transition_records": len(transitions),
        "completed_transition_records": len(transitions),
        "pending_decisions": len(pending_decisions),
        "valid_candidate_pairs": len(valid),
        "candidate_partial_pairs": pair_has(
            "candidate_partial", "candidate_close_unverified", "candidate_daily_observation"
        ),
        "sector_daily_pairs": pair_has("sector_daily_evidence"),
        "sector_range_pairs": pair_has("sector_range_context"),
        "missing_pairs": pair_has("missing"),
        "regimes_covered": sorted(regimes),
        "regime_counts": dict(sorted(regimes.items())),
        "valid_pair_dates": [_pair_id(row) for row in valid],
        "excluded_pair_dates": [_pair_id(row) for row in excluded],
        "pair_exclusion_reasons_summary": dict(sorted(reasons.items())),
        "latest_candidate_close_date": _latest(levels, "candidate_close"),
        "latest_candidate_observation_date": _latest(levels, "candidate_daily_observation"),
        "latest_sector_daily_date": _latest(levels, "sector_daily_evidence"),
        "latest_sector_range_date": _latest(levels, "sector_range_context"),
        "p2_5_min_pair_requirement": 10,
        "p2_5_min_regime_requirement": 3,
    }
    payload["ready_for_p2_5"] = (
        payload["valid_candidate_pairs"] >= payload["p2_5_min_pair_requirement"]
        and len(payload["regimes_covered"]) >= payload["p2_5_min_regime_requirement"]
    )
    return payload


def _dedupe(rows):
    deduped = {}
    for row in rows:
        deduped[_pair_id(row)] = row
    return [deduped[key] for key in sorted(deduped)]


def _pair_id(row):
    return f"{row.get('decision_date', '')}->{row.get('feedback_date', '')}"


def _latest(levels, target):
    return max((date for date, level in levels.items() if level == target), default="")


def _markdown(payload):
    return "\n".join([
        "# State Transition Pair Coverage",
        "",
        "This report is observation-only and does not change active gates.",
        "",
        f"- latest_evidence_date: {payload['latest_evidence_date']}",
        f"- total_transition_records: {payload['total_transition_records']}",
        f"- valid_candidate_pairs: {payload['valid_candidate_pairs']}",
        f"- pending_decisions: {payload['pending_decisions']}",
        f"- regimes_covered: {payload['regimes_covered']}",
        f"- ready_for_p2_5: {payload['ready_for_p2_5']}",
        f"- pair_exclusion_reasons: {payload['pair_exclusion_reasons_summary']}",
        "",
    ])


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--transition-json", required=True)
    parser.add_argument("--outcome-json", required=True)
    parser.add_argument("--pending-json")
    parser.add_argument("--latest-date", default="")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    transition_payload = json.loads(Path(args.transition_json).read_text(encoding="utf-8-sig"))
    outcome_payload = json.loads(Path(args.outcome_json).read_text(encoding="utf-8-sig"))
    pending = []
    if args.pending_json:
        pending_payload = json.loads(Path(args.pending_json).read_text(encoding="utf-8-sig"))
        pending = pending_payload.get("pending_decisions", [])
    payload = build_coverage(
        transition_payload.get("transitions", []),
        outcome_payload.get("outcome_features", []),
        pending,
        args.latest_date,
    )
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return payload
    json_path = Path(args.output_json)
    md_path = Path(args.output_md)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    main()
