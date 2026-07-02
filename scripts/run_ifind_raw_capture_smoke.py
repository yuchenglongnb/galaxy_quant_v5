# -*- coding: utf-8 -*-
"""Run a single-date iFind raw capture smoke without changing evaluator rules."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.capture_ifind_market_structure_raw import capture_raw_files  # noqa: E402
from scripts.evaluate_cp_evidence_backfill_readiness import build_summary_payload as build_backfill_readiness  # noqa: E402
from scripts.evaluate_cp_exemption_evidence_coverage import build_summary_payload as build_evidence_coverage  # noqa: E402
from scripts.evaluate_cp_structural_repair_audit import build_summary_payload as build_structural_audit  # noqa: E402
from scripts.evaluate_ifind_market_structure import evaluate as rebuild_market_structure  # noqa: E402
from scripts.evaluate_ifind_market_structure import write_outputs as write_market_structure_outputs  # noqa: E402
from utils.encoding import configure_utf8_console  # noqa: E402


EVAL_ROOT = ROOT / "reports" / "analysis" / "evaluations"
REBUILD_READY = {"sector_only", "full_ready"}


def _raw_path(date: str, filename: str) -> Path:
    return ROOT / "AmazingData_Store" / str(date) / "ifind" / "raw" / filename


def _metric_snapshot(date: str) -> dict:
    readiness = build_backfill_readiness([str(date)])
    evidence = build_evidence_coverage([str(date)])
    return {
        "snapshot_missing": readiness.get("missing_reason_distribution", {}).get("snapshot_missing", 0),
        "evidence_missing_false_positive": evidence.get("evidence_missing_false_positive_count", 0),
        "exemption_ready_false_positive": evidence.get("exemption_ready_false_positive_count", 0),
        "rule_gap_false_positive": evidence.get("rule_gap_false_positive_count", 0),
    }


def _before_after(before: dict, after: dict) -> dict:
    keys = [
        "snapshot_missing",
        "evidence_missing_false_positive",
        "exemption_ready_false_positive",
        "rule_gap_false_positive",
    ]
    return {
        key: {
            "before": before.get(key, 0),
            "after": after.get(key, 0),
        }
        for key in keys
    }


def _attempt_snapshot_rebuild(date: str, readiness: str) -> tuple[bool, dict, list[str]]:
    sector_raw = _raw_path(date, "sector_strength_raw.csv")
    limitup_raw = _raw_path(date, "limitup_ladder_raw.csv")
    warnings = []
    if not sector_raw.exists():
        return False, {}, ["sector_raw_missing_before_rebuild"]
    try:
        payload = rebuild_market_structure(
            int(date),
            None if readiness == "sector_only" else str(limitup_raw),
            str(sector_raw),
            sector_only=readiness == "sector_only",
        )
        json_path, md_path = write_market_structure_outputs(payload)
        payload["output_paths"] = {"json": str(json_path), "md": str(md_path)}
        return True, payload, warnings
    except Exception as exc:
        return False, {"error": str(exc)}, ["snapshot_rebuild_failed"]


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
    outputs = {}
    try:
        structural = build_structural_audit([str(date)])
        evidence = build_evidence_coverage([str(date)])
        readiness = build_backfill_readiness([str(date)])
        outputs = {
            "structural_audit_conclusion": structural.get("conclusion", []),
            "evidence_coverage_conclusion": evidence.get("conclusion", []),
            "backfill_readiness_conclusion": readiness.get("conclusion", []),
        }
    except Exception as exc:
        return False, {"error": str(exc), **outputs}
    return True, outputs


def _raw_files_from_capture(capture_payload: dict, date: str) -> dict:
    readiness_payload = capture_payload.get("raw_readiness_payload", {})
    return (
        readiness_payload
        .get("file_status_by_date", {})
        .get(str(date), {})
    )


def build_smoke_payload(
    date: str,
    sector_raw: str | None = None,
    theme_raw: str | None = None,
    limitup_raw: str | None = None,
    source: str = "manual_export",
) -> dict:
    date = str(date)
    before = _metric_snapshot(date)
    capture_payload = capture_raw_files(
        date,
        sector_raw=sector_raw,
        theme_raw=theme_raw,
        limitup_raw=limitup_raw,
        source=source,
    )
    readiness = capture_payload.get("readiness", "missing")
    warnings = list(capture_payload.get("warnings", []))
    conclusion = [
        "do_not_fabricate_snapshot",
        "keep_cp_rules_unchanged",
        "raw_capture_smoke_only",
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

    if readiness in REBUILD_READY:
        snapshot_rebuild_attempted = True
        conclusion.append("snapshot_rebuild_allowed")
        if readiness == "sector_only":
            conclusion.append("sector_only_ready")
        elif readiness == "full_ready":
            conclusion.append("full_ready")
        snapshot_rebuild_success, snapshot_payload, rebuild_warnings = _attempt_snapshot_rebuild(date, readiness)
        warnings.extend(rebuild_warnings)

        if snapshot_rebuild_success:
            auction_replay_attempted = True
            auction_replay_success, auction_payload = _run_auction_replay(date)
            if not auction_replay_success:
                warnings.append("auction_replay_failed")

            cp_audit_rerun_attempted = True
            cp_audit_rerun_success, cp_audit_payload = _rerun_cp_audits(date)
            if not cp_audit_rerun_success:
                warnings.append("cp_audit_rerun_failed")
    else:
        conclusion.extend(["raw_missing", "snapshot_rebuild_blocked"])

    after = _metric_snapshot(date) if (snapshot_rebuild_success or cp_audit_rerun_success) else before
    if readiness == "missing":
        warnings.append("raw_missing")

    return {
        "date": date,
        "raw_readiness": readiness,
        "raw_files": _raw_files_from_capture(capture_payload, date),
        "manifest_path": capture_payload.get("manifest_path", ""),
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
        "warnings": sorted(set(warnings)),
        "conclusion": sorted(set(conclusion), key=conclusion.index),
    }


def write_outputs(payload: dict) -> tuple[Path, Path]:
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    date = payload["date"]
    json_path = EVAL_ROOT / f"ifind_raw_capture_smoke_{date}.json"
    md_path = EVAL_ROOT / f"ifind_raw_capture_smoke_{date}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def _render_markdown(payload: dict) -> str:
    lines = [
        f"# iFind Raw Capture Smoke {payload['date']}",
        "",
        f"- raw_readiness: `{payload['raw_readiness']}`",
        f"- manifest_path: `{payload['manifest_path']}`",
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
    lines.extend(["", "## Raw Files", "", "```json", json.dumps(payload["raw_files"], ensure_ascii=False, indent=2), "```"])
    return "\n".join(lines) + "\n"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run a single-date iFind raw capture smoke.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--sector-raw", default="")
    parser.add_argument("--theme-raw", default="")
    parser.add_argument("--limitup-raw", default="")
    parser.add_argument("--source", default="manual_export")
    return parser.parse_args(argv)


def main(argv=None):
    configure_utf8_console()
    args = parse_args(argv)
    payload = build_smoke_payload(
        args.date,
        sector_raw=args.sector_raw or None,
        theme_raw=args.theme_raw or None,
        limitup_raw=args.limitup_raw or None,
        source=args.source,
    )
    json_path, md_path = write_outputs(payload)
    print(json.dumps({"json": str(json_path), "md": str(md_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
