# -*- coding: utf-8 -*-
"""Summarize real-snapshot readiness and CP exemption evaluation across dates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_cp_exemption import evaluate as evaluate_cp
from scripts.evaluate_leading_cluster_evidence import evaluate as evaluate_lc
from utils.encoding import configure_utf8_console


def build_summary(dates: list[int]) -> dict:
    rows = []
    for date_int in dates:
        cp_payload = evaluate_cp(date_int)
        lc_payload = evaluate_lc(date_int)
        cp_stats = cp_payload.get("cp_decision_stats", {})
        crowded = cp_stats.get("crowded_observe", {})
        exempt = cp_stats.get("leading_cluster_exempt", {})
        hard = cp_stats.get("hard_trap", {})
        rows.append(
            {
                "date": str(date_int),
                "real_snapshot": bool(cp_payload.get("snapshot_ready")),
                "snapshot_status": cp_payload.get("snapshot_status", ""),
                "real_snapshot_missing": bool(cp_payload.get("real_snapshot_missing")),
                "full_snapshot_missing": bool(cp_payload.get("full_snapshot_missing", False)),
                "cp_total": cp_payload.get("cp_total", 0),
                "hard_trap": cp_payload.get("cp_decision_distribution", {}).get("hard_trap", 0),
                "crowded_observe": cp_payload.get("cp_decision_distribution", {}).get("crowded_observe", 0),
                "leading_cluster_exempt": cp_payload.get("cp_decision_distribution", {}).get("leading_cluster_exempt", 0),
                "pending_validation": bool(cp_payload.get("full_snapshot_missing", cp_payload.get("real_snapshot_missing"))),
                "snapshot_missing_files": cp_payload.get("snapshot_missing_files", []),
                "crowded_success_rate": crowded.get("success_rate"),
                "hard_success_rate": hard.get("success_rate"),
                "exempt_success_rate": exempt.get("success_rate"),
                "leading_cluster_market_structure_hit_rate": lc_payload.get("market_structure_hit_rate"),
                "notes": cp_payload.get("notes", []),
            }
        )
    return {"dates": rows}


def write_outputs(payload: dict) -> tuple[Path, Path]:
    out_dir = ROOT / "reports" / "analysis" / "evaluations"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "cp_exemption_real_snapshot_summary.json"
    md_path = out_dir / "cp_exemption_real_snapshot_summary.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# CP Exemption Real Snapshot Summary",
        "",
        "| date | real_snapshot | snapshot_status | cp_total | hard_trap | crowded_observe | leading_cluster_exempt | pending_validation | notes |",
        "|---|---|---|---:|---:|---:|---:|---|---|",
    ]
    for row in payload["dates"]:
        notes = "; ".join(row.get("notes", []))
        lines.append(
            f"| {row['date']} | {row['real_snapshot']} | {row['snapshot_status']} | {row['cp_total']} | "
            f"{row['hard_trap']} | {row['crowded_observe']} | {row['leading_cluster_exempt']} | "
            f"{row['pending_validation']} | {notes} |"
        )

    lines.extend(
        [
            "",
            "## Detail",
            "",
        ]
    )
    for row in payload["dates"]:
        lines.extend(
            [
                f"### {row['date']}",
                "",
                f"- snapshot_status: `{row['snapshot_status']}`",
                f"- real_snapshot_missing: `{row['real_snapshot_missing']}`",
                f"- full_snapshot_missing: `{row['full_snapshot_missing']}`",
                f"- snapshot_missing_files: `{', '.join(row['snapshot_missing_files']) or 'none'}`",
                f"- hard_success_rate: `{(row['hard_success_rate'] or 0):.2%}`",
                f"- crowded_success_rate: `{(row['crowded_success_rate'] or 0):.2%}`",
                f"- exempt_success_rate: `{(row['exempt_success_rate'] or 0):.2%}`",
                f"- leading_cluster_market_structure_hit_rate: `{(row['leading_cluster_market_structure_hit_rate'] or 0):.2%}`",
                "",
            ]
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main():
    configure_utf8_console()
    parser = argparse.ArgumentParser()
    parser.add_argument("--dates", nargs="+", required=True, type=int)
    args = parser.parse_args()
    payload = build_summary(args.dates)
    json_path, md_path = write_outputs(payload)
    print(f"[ok] cp real snapshot summary json: {json_path}")
    print(f"[ok] cp real snapshot summary md: {md_path}")


if __name__ == "__main__":
    main()
