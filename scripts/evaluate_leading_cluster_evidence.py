# -*- coding: utf-8 -*-
"""Evaluate leading-cluster evidence enrichment for a given trading day."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.evaluators.leading_cluster_evidence import LeadingClusterEvidenceBuilder
from utils.encoding import configure_utf8_console


def _build_candidate(row: dict) -> dict:
    return {
        "name": row.get("name", ""),
        "signal_category": row.get("signal_category", ""),
        "scenario": row.get("scenario", ""),
        "action_score_breakdown": {
            "theme_cluster_bonus": 0.0,
            "group_regime_bonus": 0.0,
        },
        "date_int": int(row.get("date", 0) or 0),
        "data": {
            "code": row.get("code", ""),
            "name": row.get("name", ""),
            "group": row.get("group", ""),
            "theme_cluster": row.get("theme_cluster", ""),
            "target_type": row.get("universe_type", ""),
            "date_int": int(row.get("date", 0) or 0),
        },
    }


def evaluate(date_int: int) -> dict:
    detail_path = ROOT / "reports" / "validation" / "daily" / str(date_int) / "signal_detail.csv"
    if not detail_path.exists():
        raise FileNotFoundError(f"missing signal detail: {detail_path}")

    df = pd.read_csv(detail_path, encoding="utf-8-sig")
    candidates = []
    status_counter = Counter()
    evidence_counter = Counter()
    missing_counter = Counter()
    risk_counter = Counter()

    market_structure_hit = 0
    sector_hit = 0
    theme_hit = 0
    limitup_hit = 0

    for row in df.fillna("").to_dict(orient="records"):
        candidate = _build_candidate(row)
        result = LeadingClusterEvidenceBuilder.evaluate_candidate(candidate, date_int=date_int)
        candidates.append(
            {
                "code": candidate["data"]["code"],
                "name": candidate["name"],
                "group": candidate["data"]["group"],
                "theme_cluster": candidate["data"]["theme_cluster"],
                "signal_category": candidate["signal_category"],
                "leading_cluster_status": result["leading_cluster_status"],
                "leading_cluster_name": result["leading_cluster_name"],
                "leading_cluster_strength": result["leading_cluster_strength"],
                "leading_cluster_evidence": result["leading_cluster_evidence"],
                "leading_cluster_missing_fields": result["leading_cluster_missing_fields"],
                "leading_cluster_risk_flags": result["leading_cluster_risk_flags"],
            }
        )
        status_counter[result["leading_cluster_status"]] += 1
        for flag in result["leading_cluster_evidence"]:
            evidence_counter[flag] += 1
        for flag in result["leading_cluster_missing_fields"]:
            missing_counter[flag] += 1
        for flag in result["leading_cluster_risk_flags"]:
            risk_counter[flag] += 1

        evidence_set = set(result["leading_cluster_evidence"])
        if any(
            flag in evidence_set
            for flag in (
                "ifind_sector_strength_confirmed",
                "sector_strength_score_confirmed",
                "limitup_ladder_diffusion_confirmed",
                "theme_limitup_diffusion_confirmed",
                "limitup_core_member_confirmed",
            )
        ):
            market_structure_hit += 1
        if "ifind_sector_strength_confirmed" in evidence_set:
            sector_hit += 1
        if "theme_limitup_diffusion_confirmed" in evidence_set:
            theme_hit += 1
        if "limitup_core_member_confirmed" in evidence_set or "limitup_ladder_diffusion_confirmed" in evidence_set:
            limitup_hit += 1

    candidate_count = len(candidates)
    active_examples = [row for row in candidates if row["leading_cluster_status"] == "active"][:5]
    partial_examples = [row for row in candidates if row["leading_cluster_status"] == "partial"][:5]
    missing_examples = [
        row
        for row in candidates
        if row["leading_cluster_status"] in {"missing_ifind_overlay", "missing_sector_strength", "missing_ifind_signal_concepts"}
    ][:5]

    payload = {
        "date": str(date_int),
        "candidate_total": candidate_count,
        "leading_cluster_status_distribution": dict(status_counter),
        "leading_cluster_evidence_distribution": dict(evidence_counter),
        "leading_cluster_missing_distribution": dict(missing_counter),
        "leading_cluster_risk_distribution": dict(risk_counter),
        "market_structure_hit_rate": round(market_structure_hit / candidate_count, 4) if candidate_count else 0.0,
        "sector_strength_hit_rate": round(sector_hit / candidate_count, 4) if candidate_count else 0.0,
        "theme_diffusion_hit_rate": round(theme_hit / candidate_count, 4) if candidate_count else 0.0,
        "limitup_ladder_hit_rate": round(limitup_hit / candidate_count, 4) if candidate_count else 0.0,
        "active_examples": active_examples,
        "partial_examples": partial_examples,
        "missing_examples": missing_examples,
        "active_with_market_structure_count": sum(
            1
            for row in candidates
            if row["leading_cluster_status"] == "active"
            and any(
                flag in set(row["leading_cluster_evidence"])
                for flag in (
                    "ifind_sector_strength_confirmed",
                    "limitup_ladder_diffusion_confirmed",
                    "theme_limitup_diffusion_confirmed",
                    "limitup_core_member_confirmed",
                )
            )
        ),
    }
    return payload


def write_outputs(payload: dict) -> tuple[Path, Path]:
    out_dir = ROOT / "reports" / "analysis" / "evaluations"
    out_dir.mkdir(parents=True, exist_ok=True)
    date_int = payload["date"]
    json_path = out_dir / f"leading_cluster_evidence_eval_{date_int}.json"
    md_path = out_dir / f"leading_cluster_evidence_eval_{date_int}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Leading Cluster Evidence Eval {date_int}",
        "",
        f"- candidate_total: `{payload['candidate_total']}`",
        f"- market_structure_hit_rate: `{payload['market_structure_hit_rate']:.2%}`",
        f"- sector_strength_hit_rate: `{payload['sector_strength_hit_rate']:.2%}`",
        f"- theme_diffusion_hit_rate: `{payload['theme_diffusion_hit_rate']:.2%}`",
        f"- limitup_ladder_hit_rate: `{payload['limitup_ladder_hit_rate']:.2%}`",
        f"- active_with_market_structure_count: `{payload['active_with_market_structure_count']}`",
        "",
        "## Status Distribution",
        "",
        "| status | count |",
        "|---|---:|",
    ]
    for key, value in sorted(payload["leading_cluster_status_distribution"].items()):
        lines.append(f"| {key} | {value} |")

    lines.extend(
        [
            "",
            "## Evidence Distribution",
            "",
            "| evidence | count |",
            "|---|---:|",
        ]
    )
    for key, value in sorted(payload["leading_cluster_evidence_distribution"].items()):
        lines.append(f"| {key} | {value} |")

    for section_name, examples_key in (
        ("Active Examples", "active_examples"),
        ("Partial Examples", "partial_examples"),
        ("Missing Examples", "missing_examples"),
    ):
        lines.extend(
            [
                "",
                f"## {section_name}",
                "",
                "```json",
                json.dumps(payload[examples_key], ensure_ascii=False, indent=2),
                "```",
            ]
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main():
    configure_utf8_console()
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, type=int)
    args = parser.parse_args()

    payload = evaluate(args.date)
    json_path, md_path = write_outputs(payload)
    print(f"[ok] leading cluster eval json: {json_path}")
    print(f"[ok] leading cluster eval md: {md_path}")


if __name__ == "__main__":
    main()
