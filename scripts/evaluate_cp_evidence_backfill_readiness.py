# -*- coding: utf-8 -*-
"""Analysis-only CP evidence readiness gate precondition tool.

This tool checks whether CP false-positive evidence is complete enough for
later coverage, contradiction, and gate review. It does not change CP
thresholds, expand exemptions, update rules, write lesson/pattern/registry
files, mutate strategy/evaluator/config files, call sync or live APIs, or run
market-structure backfill. Readiness outputs are labels for human review, not
execution instructions.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_cp_exemption_evidence_coverage import (  # noqa: E402
    classify_evidence_bucket,
    evidence_profile,
)
from scripts.evaluate_cp_structural_repair_audit import cp_candidate_rows  # noqa: E402
from utils.encoding import configure_utf8_console  # noqa: E402


EVAL_ROOT = ROOT / "reports" / "analysis" / "evaluations"
DAILY_ROOT = ROOT / "reports" / "analysis" / "daily"
VALIDATION_ROOT = ROOT / "reports" / "validation" / "daily"
LEADING_CLUSTER_CONFIG_PATH = ROOT / "reports" / "analysis" / "configs" / "leading_cluster_config.json"

EXPECTED_SNAPSHOT_FILES = {
    "sector_strength_snapshot": "sector_strength_snapshot.csv",
    "theme_limitup_distribution": "theme_limitup_distribution.csv",
    "limitup_ladder_snapshot": "limitup_ladder_snapshot.csv",
}
SECTOR_BREADTH_COLUMNS = {
    "limitup_count",
    "limitup_ratio",
    "dde_net_buy_yuan",
    "net_active_buy_yuan",
    "sector_strength_score",
    "strength_score",
}


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _resolve_dates(args) -> list[str]:
    if args.dates:
        return [item.strip() for item in args.dates.split(",") if item.strip()]
    start = datetime.strptime(args.start_date, "%Y%m%d").date()
    end = datetime.strptime(args.end_date, "%Y%m%d").date()
    dates = []
    cursor = start
    while cursor <= end:
        date_str = cursor.strftime("%Y%m%d")
        if (DAILY_ROOT / date_str).exists() or (VALIDATION_ROOT / date_str).exists():
            dates.append(date_str)
        cursor += timedelta(days=1)
    return dates


def _load_alias_groups() -> set[str]:
    try:
        config = json.loads(LEADING_CLUSTER_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return set()
    groups = set((config.get("sector_alias_map") or {}).keys())
    groups.update((config.get("ifind_cluster_alias") or {}).keys())
    return {str(item) for item in groups if item}


def snapshot_status(date: str) -> dict:
    ifind_dir = ROOT / "AmazingData_Store" / str(date) / "ifind"
    files = {}
    for key, filename in EXPECTED_SNAPSHOT_FILES.items():
        path = ifind_dir / filename
        files[key] = {
            "path": _repo_relative(path),
            "exists": path.exists(),
            "size": path.stat().st_size if path.exists() else 0,
            "columns": _csv_columns(path) if path.exists() else [],
        }
    any_exists = any(item["exists"] for item in files.values())
    sector = files["sector_strength_snapshot"]
    sector_columns = set(sector.get("columns") or [])
    return {
        "ifind_dir": _repo_relative(ifind_dir),
        "ifind_dir_exists": ifind_dir.exists(),
        "snapshot_missing": not any_exists,
        "files": files,
        "sector_breadth_snapshot_missing": not sector["exists"],
        "sector_breadth_field_missing": bool(sector["exists"]) and not bool(sector_columns & SECTOR_BREADTH_COLUMNS),
    }


def _csv_columns(path: Path) -> list[str]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            return [str(item) for item in next(reader, [])]
    except Exception:
        return []


def _is_evidence_missing_false_positive(row: dict) -> bool:
    return classify_evidence_bucket(row) == "evidence_missing_false_positive"


def classify_missing_reasons(row: dict, status: dict, alias_groups: set[str]) -> list[str]:
    reasons = []
    profile = evidence_profile(row)
    group = str(row.get("group", "") or "")
    theme_cluster = str(row.get("theme_cluster", "") or "")
    concepts = " ".join(str(item) for item in row.get("ifind_signal_concepts", []) or [])
    status_text = " ".join([
        str(row.get("leading_cluster_status", "") or ""),
        " ".join(str(item) for item in row.get("leading_cluster_risk_flags", []) or []),
        " ".join(str(item) for item in row.get("cp_risk_flags", []) or []),
    ]).lower()

    if status.get("snapshot_missing"):
        reasons.append("snapshot_missing")
    if "stale" in status_text or "fallback" in status_text:
        reasons.append("snapshot_stale_or_fallback")
    if status.get("sector_breadth_snapshot_missing"):
        reasons.append("sector_breadth_snapshot_missing")
    if status.get("sector_breadth_field_missing"):
        reasons.append("sector_breadth_field_missing")
    if not status.get("files", {}).get("theme_limitup_distribution", {}).get("exists") and not status.get("files", {}).get("limitup_ladder_snapshot", {}).get("exists"):
        reasons.append("leading_cluster_snapshot_missing")

    alias_matched = bool(group and group in alias_groups) or bool(theme_cluster and theme_cluster in alias_groups)
    if not alias_matched and group and group not in {"(empty)", ""}:
        reasons.append("alias_or_group_unmatched")

    if (
        not profile["leading_cluster_support"]
        and not profile["sector_breadth_support"]
        and alias_matched
        and not status.get("snapshot_missing")
    ):
        reasons.append("builder_attachment_missing")

    if not profile["prior_day_context_support"]:
        reasons.append("prior_day_context_missing")

    if not reasons:
        reasons.append("unknown_missing_reason")
    return sorted(set(reasons))


def _compact_row(row: dict, reasons: list[str], status: dict) -> dict:
    profile = evidence_profile(row)
    return {
        "date": row.get("date", ""),
        "code": row.get("code", ""),
        "name": row.get("name", ""),
        "target_type": row.get("target_type", ""),
        "group": row.get("group", ""),
        "analysis_group": row.get("group") or row.get("theme_cluster") or "(empty)",
        "theme_cluster": row.get("theme_cluster", ""),
        "missing_reasons": reasons,
        "snapshot_missing": status.get("snapshot_missing"),
        "sector_breadth_snapshot_missing": status.get("sector_breadth_snapshot_missing"),
        "sector_breadth_field_missing": status.get("sector_breadth_field_missing"),
        "leading_cluster_status": row.get("leading_cluster_status", ""),
        "leading_cluster_strength": row.get("leading_cluster_strength"),
        "leading_cluster_evidence": row.get("leading_cluster_evidence", []),
        "missing_evidence": profile.get("missing_evidence", []),
        "prior_day_context_bonus": row.get("prior_day_context_bonus"),
        "body_pct": row.get("body_pct"),
        "validation_success": row.get("validation_success"),
    }


def _distribution(rows: list[dict], key: str) -> dict:
    grouped = defaultdict(list)
    for row in rows:
        value = row.get(key, "")
        if key == "analysis_group" and not value:
            value = row.get("group") or row.get("theme_cluster") or "(empty)"
        grouped[str(value or "(empty)")].append(row)
    output = {}
    for value, bucket in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        reason_counter = Counter()
        for row in bucket:
            reason_counter.update(row.get("missing_reasons", []) or [])
        output[value] = {
            "candidate_count": len(bucket),
            "missing_reason_distribution": dict(reason_counter),
        }
    return output


def _reason_distribution(rows: list[dict]) -> dict:
    counter = Counter()
    for row in rows:
        counter.update(row.get("missing_reasons", []) or [])
    return dict(counter)


def _readiness_labels(reason_distribution: dict) -> list[str]:
    labels = []
    if reason_distribution.get("snapshot_missing") or reason_distribution.get("leading_cluster_snapshot_missing"):
        labels.append("market_structure_snapshot_evidence_missing")
    if reason_distribution.get("alias_or_group_unmatched"):
        labels.append("sector_alias_review_needed")
    if reason_distribution.get("sector_breadth_snapshot_missing") or reason_distribution.get("sector_breadth_field_missing"):
        labels.append("sector_breadth_evidence_missing")
    if reason_distribution.get("builder_attachment_missing"):
        labels.append("builder_attachment_review_needed")
    if not labels:
        labels.append("manual_review_only")
    return labels


def build_daily_payload(date: str) -> dict:
    rows, _result, _review = cp_candidate_rows(date)
    status = snapshot_status(date)
    alias_groups = _load_alias_groups()
    missing_rows = []
    reference_rows = []
    for row in rows:
        row["evidence_bucket"] = classify_evidence_bucket(row)
        if _is_evidence_missing_false_positive(row):
            reasons = classify_missing_reasons(row, status, alias_groups)
            compact = _compact_row(row, reasons, status)
            missing_rows.append(compact)
        elif row.get("cp_audit_bucket") in {"leading_cluster_repair_false_positive", "true_cp_risk"}:
            reference_rows.append(_compact_row(row, [], status))

    reason_distribution = _reason_distribution(missing_rows)
    warnings = []
    if not missing_rows:
        warnings.append("no_evidence_missing_false_positive_samples")
    return {
        "date": date,
        "evidence_missing_false_positive_total": len(missing_rows),
        "snapshot_missing_count": sum("snapshot_missing" in row["missing_reasons"] for row in missing_rows),
        "snapshot_stale_or_fallback_count": sum("snapshot_stale_or_fallback" in row["missing_reasons"] for row in missing_rows),
        "alias_or_group_unmatched_count": sum("alias_or_group_unmatched" in row["missing_reasons"] for row in missing_rows),
        "sector_breadth_field_missing_count": sum("sector_breadth_field_missing" in row["missing_reasons"] for row in missing_rows),
        "sector_breadth_snapshot_missing_count": sum("sector_breadth_snapshot_missing" in row["missing_reasons"] for row in missing_rows),
        "leading_cluster_snapshot_missing_count": sum("leading_cluster_snapshot_missing" in row["missing_reasons"] for row in missing_rows),
        "builder_attachment_missing_count": sum("builder_attachment_missing" in row["missing_reasons"] for row in missing_rows),
        "prior_day_context_missing_count": sum("prior_day_context_missing" in row["missing_reasons"] for row in missing_rows),
        "unknown_missing_reason_count": sum("unknown_missing_reason" in row["missing_reasons"] for row in missing_rows),
        "snapshot_status": status,
        "by_group": _distribution(missing_rows, "analysis_group"),
        "by_missing_reason": {key: value for key, value in sorted(reason_distribution.items())},
        "top_missing_evidence_samples": missing_rows[:30],
        "readiness_labels": _readiness_labels(reason_distribution),
        "reference_rows": reference_rows[:30],
        "warnings": warnings,
    }


def build_summary_payload(date_list: list[str]) -> dict:
    daily = [build_daily_payload(date) for date in date_list]
    rows = []
    for payload in daily:
        rows.extend(payload.get("top_missing_evidence_samples", []) or [])
    reason_distribution = _reason_distribution(rows)
    readiness_labels = _readiness_labels(reason_distribution)
    conclusions = [
        "keep_cp_threshold",
        "repair_evidence_first",
        "no_rule_change_yet",
        "not_ready_for_exemption_expansion",
    ]
    if readiness_labels and readiness_labels != ["manual_review_only"]:
        conclusions.append("ready_for_evidence_completeness_review")
    return {
        "date_range": {
            "start_date": min(date_list) if date_list else "",
            "end_date": max(date_list) if date_list else "",
            "dates": date_list,
        },
        "total_evidence_missing_false_positives": len(rows),
        "missing_reason_distribution": reason_distribution,
        "by_date_distribution": {
            payload["date"]: {
                "evidence_missing_false_positive_total": payload.get("evidence_missing_false_positive_total", 0),
                "snapshot_missing_count": payload.get("snapshot_missing_count", 0),
                "alias_or_group_unmatched_count": payload.get("alias_or_group_unmatched_count", 0),
                "sector_breadth_snapshot_missing_count": payload.get("sector_breadth_snapshot_missing_count", 0),
                "sector_breadth_field_missing_count": payload.get("sector_breadth_field_missing_count", 0),
                "builder_attachment_missing_count": payload.get("builder_attachment_missing_count", 0),
                "readiness_labels": payload.get("readiness_labels", []),
            }
            for payload in daily
        },
        "by_group_distribution": _distribution(rows, "analysis_group"),
        "by_snapshot_availability": {
            payload["date"]: payload.get("snapshot_status", {})
            for payload in daily
        },
        "by_alias_group_match_status": {
            "alias_or_group_unmatched_count": reason_distribution.get("alias_or_group_unmatched", 0),
            "alias_or_group_matched_or_unknown_count": len(rows) - reason_distribution.get("alias_or_group_unmatched", 0),
        },
        "sector_breadth_field_availability": {
            "sector_breadth_snapshot_missing_count": reason_distribution.get("sector_breadth_snapshot_missing", 0),
            "sector_breadth_field_missing_count": reason_distribution.get("sector_breadth_field_missing", 0),
        },
        "leading_cluster_attachment_status": {
            "leading_cluster_snapshot_missing_count": reason_distribution.get("leading_cluster_snapshot_missing", 0),
            "builder_attachment_missing_count": reason_distribution.get("builder_attachment_missing", 0),
        },
        "readiness_labels": readiness_labels,
        "readiness_label_note": "Readiness labels are gate precondition labels, not execution instructions.",
        "daily": daily,
        "conclusion": conclusions,
    }


def _render_markdown(payload: dict) -> str:
    lines = [
        "# CP Evidence Backfill Readiness Audit",
        "",
        f"- dates: `{payload['date_range']['dates']}`",
        f"- total_evidence_missing_false_positives: `{payload['total_evidence_missing_false_positives']}`",
        f"- missing_reason_distribution: `{payload['missing_reason_distribution']}`",
        f"- readiness_labels: `{payload['readiness_labels']}`",
        "- readiness_label_note: `Readiness labels are gate precondition labels, not execution instructions.`",
        f"- conclusion: `{payload['conclusion']}`",
        "",
        "## By Date",
        "",
    ]
    for date, row in payload["by_date_distribution"].items():
        lines.append(f"- {date}: `{row}`")
    lines.extend(["", "## Top Groups", ""])
    for group, row in payload["by_group_distribution"].items():
        lines.append(f"- {group}: `{row}`")
    lines.extend(["", "## Snapshot Availability", ""])
    for date, row in payload["by_snapshot_availability"].items():
        lines.append(f"- {date}: ifind_dir_exists={row.get('ifind_dir_exists')}, snapshot_missing={row.get('snapshot_missing')}")
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict, output_dir: str | Path | None = None):
    root = Path(output_dir) if output_dir else EVAL_ROOT
    root.mkdir(parents=True, exist_ok=True)
    start = payload["date_range"]["start_date"]
    end = payload["date_range"]["end_date"]
    json_path = root / f"cp_evidence_backfill_readiness_{start}_{end}.json"
    md_path = root / f"cp_evidence_backfill_readiness_{start}_{end}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Audit CP evidence backfill readiness.")
    parser.add_argument("--dates", default="", help="Comma-separated trade dates.")
    parser.add_argument("--start-date", default="20260622")
    parser.add_argument("--end-date", default="20260626")
    parser.add_argument("--output-dir", default="", help="Repo-relative or explicit output directory for reports.")
    parser.add_argument("--dry-run", action="store_true", help="Build the payload and print a summary without writing reports.")
    return parser.parse_args(argv)


def main(argv=None):
    configure_utf8_console()
    args = parse_args(argv)
    date_list = _resolve_dates(args)
    payload = build_summary_payload(date_list)
    if args.dry_run:
        print(json.dumps({
            "dry_run": True,
            "dates": date_list,
            "total_evidence_missing_false_positives": payload["total_evidence_missing_false_positives"],
            "readiness_labels": payload["readiness_labels"],
        }, ensure_ascii=False, indent=2))
        return payload
    json_path, md_path = write_outputs(payload, args.output_dir or None)
    print(json.dumps({"json": str(json_path), "md": str(md_path)}, ensure_ascii=False, indent=2))
    return payload


if __name__ == "__main__":
    main()
