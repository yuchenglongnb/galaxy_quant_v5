# -*- coding: utf-8 -*-
"""Evaluate CP risk layering for a given trading day."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.evaluators.cp_risk_evaluator import CPRiskEvaluator
from analyzers.evaluators.leading_cluster_evidence import LeadingClusterEvidenceBuilder
from utils.encoding import configure_utf8_console


def _load_cp_rows(date_int: int) -> list[dict]:
    daily_dir = ROOT / "reports" / "validation" / "daily" / str(date_int)
    frames = []
    for name in (
        "factor_snapshot_index.csv",
        "factor_snapshot_etf.csv",
        "factor_snapshot_stock.csv",
        "factor_snapshot_industry_topk.csv",
    ):
        path = daily_dir / name
        if path.exists():
            frames.append(pd.read_csv(path, encoding="utf-8-sig"))
    if not frames:
        raise FileNotFoundError(f"missing factor snapshots under {daily_dir}")
    combined = pd.concat(frames, ignore_index=True, sort=False).fillna("")
    cp_rows = combined[
        (combined.get("signal_category", "").astype(str) == "trap")
        | (combined.get("cp_triggered", False).astype(str).str.lower() == "true")
    ].copy()
    return cp_rows.to_dict(orient="records")


def _load_regime_map(date_int: int) -> dict:
    path = ROOT / "reports" / "validation" / "daily" / str(date_int) / "signal_detail.csv"
    if not path.exists():
        return {}
    df = pd.read_csv(path, encoding="utf-8-sig").fillna("")
    mapping = {}
    for row in df.to_dict(orient="records"):
        key = (
            str(row.get("name", "") or ""),
            str(row.get("signal_category", "") or ""),
            str(row.get("scenario", "") or ""),
        )
        mapping[key] = str(row.get("market_regime", "") or "")
    return mapping


def _build_candidate(row: dict, date_int: int, regime_map: dict) -> dict:
    key = (
        str(row.get("name", "") or ""),
        "trap",
        str(row.get("scenario", "") or ""),
    )
    regime = regime_map.get(key, "")
    return {
        "name": row.get("name", ""),
        "cp": row.get("cp", ""),
        "scenario": row.get("scenario", ""),
        "market_regime": regime,
        "date_int": date_int,
        "action_score_breakdown": {
            "theme_cluster_bonus": 0.0,
            "group_regime_bonus": 0.0,
        },
        "data": {
            "code": row.get("code", ""),
            "name": row.get("name", ""),
            "group": row.get("group", ""),
            "theme_cluster": row.get("theme_cluster", ""),
            "target_type": row.get("universe_type", ""),
            "auction_pct": row.get("auction_pct", ""),
            "date_int": date_int,
        },
    }


def evaluate(date_int: int) -> dict:
    cp_rows = _load_cp_rows(date_int)
    regime_map = _load_regime_map(date_int)
    ifind_dir = ROOT / "AmazingData_Store" / str(date_int) / "ifind"
    real_snapshot_missing = not ifind_dir.exists()

    decision_counter = Counter()
    success_counter = Counter()
    example_buckets = defaultdict(list)

    evaluated = []
    for row in cp_rows:
        candidate = _build_candidate(row, date_int, regime_map)
        LeadingClusterEvidenceBuilder.enrich_candidate(candidate, date_int=date_int)
        cp_result = CPRiskEvaluator.evaluate_candidate(candidate, regime=candidate.get("market_regime"))
        candidate.update(cp_result)

        decision = str(candidate.get("cp_risk_decision", "") or "disabled")
        decision_counter[decision] += 1
        body_pct = _number(row.get("body_pct"), float("nan"))
        success = body_pct == body_pct and body_pct < 0
        if success:
            success_counter[decision] += 1

        record = {
            "code": str(row.get("code", "") or ""),
            "name": str(row.get("name", "") or ""),
            "target_type": str(row.get("universe_type", "") or ""),
            "group": str(row.get("group", "") or ""),
            "theme_cluster": str(row.get("theme_cluster", "") or ""),
            "cp": _nullable_float(row.get("cp")),
            "auction_pct": _nullable_float(row.get("auction_pct")),
            "body_pct": _nullable_float(row.get("body_pct")),
            "market_regime": str(candidate.get("market_regime", "") or ""),
            "cp_risk_decision": decision,
            "leading_cluster_name": candidate.get("leading_cluster_name", ""),
            "leading_cluster_strength": candidate.get("leading_cluster_strength"),
            "leading_cluster_status": candidate.get("leading_cluster_status", ""),
            "leading_cluster_evidence": candidate.get("leading_cluster_evidence", []),
            "cp_risk_reasons": candidate.get("cp_risk_reasons", []),
            "cp_risk_flags": candidate.get("cp_risk_flags", []),
            "validation_success": success,
        }
        evaluated.append(record)
        if len(example_buckets[decision]) < 5:
            example_buckets[decision].append(record)

    grouped_stats = {}
    for decision, count in decision_counter.items():
        matched = [row for row in evaluated if row["cp_risk_decision"] == decision and row["body_pct"] is not None]
        avg_body = sum(row["body_pct"] for row in matched) / len(matched) if matched else None
        grouped_stats[decision] = {
            "count": count,
            "success_count": success_counter.get(decision, 0),
            "success_rate": round(success_counter.get(decision, 0) / count, 4) if count else 0.0,
            "avg_body_pct": round(avg_body, 4) if avg_body is not None else None,
        }

    return {
        "date": str(date_int),
        "real_snapshot_missing": real_snapshot_missing,
        "cp_total": len(evaluated),
        "cp_decision_distribution": dict(decision_counter),
        "cp_decision_stats": grouped_stats,
        "decision_examples": dict(example_buckets),
        "notes": [
            "20260618 validation remains pending real market-structure snapshot when ifind dir is absent."
            if real_snapshot_missing
            else "real market-structure snapshot detected for this date."
        ],
    }


def write_outputs(payload: dict) -> tuple[Path, Path]:
    out_dir = ROOT / "reports" / "analysis" / "evaluations"
    out_dir.mkdir(parents=True, exist_ok=True)
    date_text = payload["date"]
    json_path = out_dir / f"cp_exemption_eval_{date_text}.json"
    md_path = out_dir / f"cp_exemption_eval_{date_text}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# CP Exemption Eval {date_text}",
        "",
        f"- cp_total: `{payload['cp_total']}`",
        f"- real_snapshot_missing: `{payload['real_snapshot_missing']}`",
        "",
        "## Decision Distribution",
        "",
        "| decision | count | success_count | success_rate | avg_body_pct |",
        "|---|---:|---:|---:|---:|",
    ]
    for decision, stats in sorted(payload["cp_decision_stats"].items()):
        avg_body = "" if stats["avg_body_pct"] is None else f"{stats['avg_body_pct']:+.4f}"
        lines.append(
            f"| {decision} | {stats['count']} | {stats['success_count']} | {stats['success_rate']:.2%} | {avg_body} |"
        )

    lines.extend(["", "## Notes", ""])
    for note in payload["notes"]:
        lines.append(f"- {note}")

    for decision, examples in sorted(payload["decision_examples"].items()):
        lines.extend(
            [
                "",
                f"## Examples: {decision}",
                "",
                "```json",
                json.dumps(examples, ensure_ascii=False, indent=2),
                "```",
            ]
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def _number(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _nullable_float(value):
    number = _number(value, float("nan"))
    return None if number != number else round(number, 4)


def main():
    configure_utf8_console()
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, type=int)
    args = parser.parse_args()

    payload = evaluate(args.date)
    json_path, md_path = write_outputs(payload)
    print(f"[ok] cp eval json: {json_path}")
    print(f"[ok] cp eval md: {md_path}")


if __name__ == "__main__":
    main()
