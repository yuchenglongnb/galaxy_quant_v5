# -*- coding: utf-8 -*-
"""Run a sector-only iFind snapshot rebuild smoke for one explicit date."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_cp_evidence_backfill_readiness import build_summary_payload as build_backfill_readiness  # noqa: E402
from scripts.evaluate_cp_exemption_evidence_coverage import build_summary_payload as build_evidence_coverage  # noqa: E402
from scripts.evaluate_cp_structural_repair_audit import build_summary_payload as build_structural_audit  # noqa: E402
from scripts.evaluate_ifind_market_structure import evaluate as rebuild_market_structure  # noqa: E402
from scripts.evaluate_ifind_market_structure import write_outputs as write_market_structure_outputs  # noqa: E402
from scripts.evaluate_ifind_raw_readiness import build_payload as build_raw_readiness  # noqa: E402
from utils.encoding import configure_utf8_console  # noqa: E402


EVAL_ROOT = ROOT / "reports" / "analysis" / "evaluations"
READY_FOR_SECTOR_REBUILD = {"sector_only", "full_ready"}


def _raw_path(date: str) -> Path:
    return ROOT / "AmazingData_Store" / str(date) / "ifind" / "raw" / "sector_strength_raw.csv"


def _snapshot_path(date: str) -> Path:
    return ROOT / "AmazingData_Store" / str(date) / "ifind" / "sector_strength_snapshot.csv"


def _metric_snapshot(date: str) -> dict:
    readiness = build_backfill_readiness([str(date)])
    evidence = build_evidence_coverage([str(date)])
    missing_reasons = readiness.get("missing_reason_distribution", {}) or {}
    return {
        "snapshot_missing": missing_reasons.get("snapshot_missing", 0),
        "leading_cluster_snapshot_missing": missing_reasons.get("leading_cluster_snapshot_missing", 0),
        "sector_breadth_snapshot_missing": missing_reasons.get("sector_breadth_snapshot_missing", 0),
        "evidence_missing_false_positive": evidence.get("evidence_missing_false_positive_count", 0),
        "exemption_ready_false_positive": evidence.get("exemption_ready_false_positive_count", 0),
        "rule_gap_false_positive": evidence.get("rule_gap_false_positive_count", 0),
        "builder_attachment_missing": missing_reasons.get("builder_attachment_missing", 0),
        "remaining_missing_reasons": missing_reasons,
    }


def _before_after(before: dict, after: dict) -> dict:
    keys = [
        "snapshot_missing",
        "leading_cluster_snapshot_missing",
        "sector_breadth_snapshot_missing",
        "evidence_missing_false_positive",
        "exemption_ready_false_positive",
        "rule_gap_false_positive",
        "builder_attachment_missing",
    ]
    return {
        key: {
            "before": before.get(key, 0),
            "after": after.get(key, 0),
        }
        for key in keys
    }


def _attempt_sector_snapshot_rebuild(date: str) -> tuple[bool, dict, list[str]]:
    sector_raw = _raw_path(date)
    if not sector_raw.exists():
        return False, {}, ["sector_strength_raw_missing_before_rebuild"]
    try:
        payload = rebuild_market_structure(
            int(date),
            None,
            str(sector_raw),
            sector_only=True,
        )
        json_path, md_path = write_market_structure_outputs(payload)
        payload["output_paths"] = {"json": str(json_path), "md": str(md_path)}
        return True, payload, []
    except Exception as exc:
        return False, {"error": str(exc)}, ["sector_snapshot_rebuild_failed"]


def _run_command(args: list[str]) -> tuple[bool, dict]:
    try:
        completed = subprocess.run(
            args,
            cwd=str(ROOT),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as exc:
        return False, {"error": str(exc)}
    return completed.returncode == 0, {
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    }


def _run_auction_replay(date: str) -> tuple[bool, dict]:
    return _run_command([sys.executable, "main.py", "auction", str(date)])


def _rerun_cp_audits(date: str) -> tuple[bool, dict]:
    try:
        structural = build_structural_audit([str(date)])
        evidence = build_evidence_coverage([str(date)])
        readiness = build_backfill_readiness([str(date)])
    except Exception as exc:
        return False, {"error": str(exc)}
    return True, {
        "structural_audit_conclusion": structural.get("conclusion", []),
        "evidence_coverage_conclusion": evidence.get("conclusion", []),
        "backfill_readiness_conclusion": readiness.get("conclusion", []),
    }


def _raw_files(readiness_payload: dict, date: str) -> dict:
    return readiness_payload.get("file_status_by_date", {}).get(str(date), {})


def build_smoke_payload(date: str) -> dict:
    date = str(date)
    before = _metric_snapshot(date)
    readiness_payload = build_raw_readiness([date], write_manifest_files=True)
    raw_readiness = readiness_payload.get("readiness_by_date", {}).get(date, "missing")
    warnings = list(readiness_payload.get("warnings", []))
    conclusion = [
        "do_not_fabricate_snapshot",
        "keep_cp_rules_unchanged",
        "sector_only_smoke",
    ]

    snapshot_rebuild_attempted = False
    snapshot_rebuild_success = False
    snapshot_payload = {}
    auction_replay_attempted = False
    auction_replay_success = False
    auction_payload = {}
    cp_audit_rerun_attempted = False
    cp_audit_rerun_success = False
    cp_audit_payload = {}

    if raw_readiness in READY_FOR_SECTOR_REBUILD:
        snapshot_rebuild_attempted = True
        if raw_readiness == "sector_only":
            conclusion.append("sector_only_ready")
        else:
            conclusion.append("full_ready")
        snapshot_rebuild_success, snapshot_payload, rebuild_warnings = _attempt_sector_snapshot_rebuild(date)
        warnings.extend(rebuild_warnings)

        if snapshot_rebuild_success:
            conclusion.append("snapshot_rebuild_success")
            auction_replay_attempted = True
            auction_replay_success, auction_payload = _run_auction_replay(date)
            if not auction_replay_success:
                warnings.append("auction_replay_failed")

            cp_audit_rerun_attempted = True
            cp_audit_rerun_success, cp_audit_payload = _rerun_cp_audits(date)
            if cp_audit_rerun_success:
                conclusion.append("cp_audit_rerun_success")
            else:
                warnings.append("cp_audit_rerun_failed")
    else:
        conclusion.extend(["raw_missing", "snapshot_rebuild_blocked"])
        warnings.append("raw_missing")

    after = _metric_snapshot(date) if (snapshot_rebuild_success or cp_audit_rerun_success) else before

    return {
        "date": date,
        "raw_readiness_before": raw_readiness,
        "raw_files": _raw_files(readiness_payload, date),
        "sector_strength_raw_path": str(_raw_path(date)),
        "sector_strength_snapshot_path": str(_snapshot_path(date)),
        "manifest_path": readiness_payload.get("manifest_paths", {}).get(date, ""),
        "snapshot_rebuild_attempted": snapshot_rebuild_attempted,
        "snapshot_rebuild_success": snapshot_rebuild_success,
        "snapshot_rebuild_payload": snapshot_payload,
        "auction_replay_attempted": auction_replay_attempted,
        "auction_replay_success": auction_replay_success,
        "auction_replay_payload": auction_payload,
        "cp_audit_rerun_attempted": cp_audit_rerun_attempted,
        "cp_audit_rerun_success": cp_audit_rerun_success,
        "cp_audit_payload": cp_audit_payload,
        "before_after": _before_after(before, after),
        "remaining_missing_reasons": after.get("remaining_missing_reasons", {}),
        "warnings": sorted(set(warnings)),
        "conclusion": sorted(set(conclusion), key=conclusion.index),
    }


def write_outputs(payload: dict) -> tuple[Path, Path]:
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    date = payload["date"]
    json_path = EVAL_ROOT / f"sector_only_snapshot_rebuild_smoke_{date}.json"
    md_path = EVAL_ROOT / f"sector_only_snapshot_rebuild_smoke_{date}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def _render_markdown(payload: dict) -> str:
    lines = [
        f"# Sector-only Snapshot Rebuild Smoke {payload['date']}",
        "",
        f"- raw_readiness_before: `{payload['raw_readiness_before']}`",
        f"- sector_strength_raw_path: `{payload['sector_strength_raw_path']}`",
        f"- sector_strength_snapshot_path: `{payload['sector_strength_snapshot_path']}`",
        f"- snapshot_rebuild_attempted: `{payload['snapshot_rebuild_attempted']}`",
        f"- snapshot_rebuild_success: `{payload['snapshot_rebuild_success']}`",
        f"- auction_replay_attempted: `{payload['auction_replay_attempted']}`",
        f"- auction_replay_success: `{payload['auction_replay_success']}`",
        f"- cp_audit_rerun_attempted: `{payload['cp_audit_rerun_attempted']}`",
        f"- cp_audit_rerun_success: `{payload['cp_audit_rerun_success']}`",
        f"- warnings: `{payload['warnings']}`",
        f"- conclusion: `{payload['conclusion']}`",
        "",
        "## Before / After",
        "",
    ]
    for key, value in payload["before_after"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend([
        "",
        "## Remaining Missing Reasons",
        "",
        "```json",
        json.dumps(payload["remaining_missing_reasons"], ensure_ascii=False, indent=2),
        "```",
    ])
    return "\n".join(lines) + "\n"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run a sector-only snapshot rebuild smoke.")
    parser.add_argument("--date", required=True)
    return parser.parse_args(argv)


def main(argv=None):
    configure_utf8_console()
    args = parse_args(argv)
    payload = build_smoke_payload(args.date)
    json_path, md_path = write_outputs(payload)
    print(json.dumps({"json": str(json_path), "md": str(md_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
