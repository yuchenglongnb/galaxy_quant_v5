# -*- coding: utf-8 -*-
"""Analysis-only audit for evidence coverage behind CP false positives.

This tool only emits validation reports. It does not change CP thresholds,
expand exemptions, write lesson/pattern/registry files, or mutate strategy
configuration.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_cp_structural_repair_audit import (  # noqa: E402
    _distribution,
    _performance_summary,
    cp_candidate_rows,
)
from utils.encoding import configure_utf8_console  # noqa: E402


EVAL_ROOT = ROOT / "reports" / "analysis" / "evaluations"
DAILY_ROOT = ROOT / "reports" / "analysis" / "daily"
VALIDATION_ROOT = ROOT / "reports" / "validation" / "daily"

FALSE_POSITIVE_BUCKETS = {
    "leading_cluster_repair_false_positive",
    "prior_day_context_explained_false_positive",
    "unresolved_cp",
}
SECTOR_BREADTH_EVIDENCE = {
    "sector_breadth_strength_confirmed",
    "sector_limitup_breadth_confirmed",
    "sector_money_flow_confirmed",
    "sector_strength_score_confirmed",
}
RISK_DECISIONS = {"hard_trap", "crowded_observe", "crowded_trap", "trap", "risk_observe"}
ACTIVE_CLUSTER_STATUSES = {"active", "partial"}


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


def _is_false_positive(row: dict) -> bool:
    return row.get("cp_audit_bucket") in FALSE_POSITIVE_BUCKETS and (
        row.get("validation_success") is False
        or (row.get("body_pct") is not None and row.get("body_pct") >= 0)
    )


def evidence_profile(row: dict) -> dict:
    evidence = set(row.get("leading_cluster_evidence") or [])
    leading_cluster_support = (
        str(row.get("leading_cluster_status", "") or "") in ACTIVE_CLUSTER_STATUSES
        and float(row.get("leading_cluster_strength") or 0.0) >= 50.0
    )
    sector_breadth_support = bool(evidence & SECTOR_BREADTH_EVIDENCE)
    prior_day_context_support = bool(row.get("repair_context")) or float(row.get("prior_day_context_bonus") or 0.0) > 0.0
    missing = []
    if not leading_cluster_support:
        missing.append("missing_leading_cluster_evidence")
    if not sector_breadth_support:
        missing.append("missing_sector_breadth_evidence")
    if not prior_day_context_support:
        missing.append("missing_prior_day_context_evidence")
    return {
        "leading_cluster_support": leading_cluster_support,
        "sector_breadth_support": sector_breadth_support,
        "prior_day_context_support": prior_day_context_support,
        "evidence_complete": leading_cluster_support and sector_breadth_support and prior_day_context_support,
        "missing_evidence": missing,
        "sector_evidence_flags": sorted(evidence & SECTOR_BREADTH_EVIDENCE),
    }


def classify_evidence_bucket(row: dict) -> str:
    profile = evidence_profile(row)
    if not _is_false_positive(row):
        return "true_cp_risk_reference" if row.get("cp_audit_bucket") == "true_cp_risk" else "non_false_positive_reference"
    if profile["evidence_complete"] and str(row.get("cp_risk_decision", "") or "") in RISK_DECISIONS:
        return "rule_gap_false_positive"
    if profile["evidence_complete"]:
        return "exemption_ready_false_positive"
    if profile["missing_evidence"]:
        return "evidence_missing_false_positive"
    return "ambiguous_false_positive"


def _compact_row(row: dict) -> dict:
    profile = evidence_profile(row)
    return {
        "date": row.get("date", ""),
        "evidence_bucket": row.get("evidence_bucket", ""),
        "cp_audit_bucket": row.get("cp_audit_bucket", ""),
        "target_type": row.get("target_type", ""),
        "code": row.get("code", ""),
        "name": row.get("name", ""),
        "group": row.get("group", ""),
        "theme_cluster": row.get("theme_cluster", ""),
        "market_regime": row.get("market_regime", ""),
        "environment_decision": row.get("environment_decision", ""),
        "cp": row.get("cp"),
        "cp_risk_score": row.get("cp_risk_score"),
        "cp_risk_decision": row.get("cp_risk_decision", ""),
        "cp_risk_flags": row.get("cp_risk_flags", []),
        "leading_cluster_status": row.get("leading_cluster_status", ""),
        "leading_cluster_strength": row.get("leading_cluster_strength"),
        "leading_cluster_name": row.get("leading_cluster_name", ""),
        "leading_cluster_evidence": row.get("leading_cluster_evidence", []),
        "sector_evidence_flags": profile["sector_evidence_flags"],
        "prior_day_context_bonus": row.get("prior_day_context_bonus"),
        "prior_day_context_bucket": row.get("prior_day_context_bucket", ""),
        "repair_context": bool(row.get("repair_context")),
        "missing_evidence": profile["missing_evidence"],
        "body_pct": row.get("body_pct"),
        "validation_success": row.get("validation_success"),
    }


def _missing_evidence_summary(rows: list[dict]) -> dict:
    counter = Counter()
    for row in rows:
        counter.update(evidence_profile(row)["missing_evidence"])
    return dict(counter)


def _group_distribution(rows: list[dict], key: str) -> dict:
    grouped = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key, "") or "(empty)")].append(row)
    output = {}
    for value, bucket_rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        output[value] = {
            "candidate_count": len(bucket_rows),
            "evidence_bucket_distribution": dict(Counter(row.get("evidence_bucket", "") for row in bucket_rows)),
            "missing_evidence_summary": _missing_evidence_summary(bucket_rows),
            "performance": _performance_summary(bucket_rows),
        }
    return output


def _prior_day_key(row: dict) -> str:
    if float(row.get("prior_day_context_bonus") or 0.0) > 0.0:
        return "positive_bonus"
    if row.get("repair_context"):
        return "repair_readthrough"
    return "no_prior_day_support"


def _top_rows(rows: list[dict], bucket: str, limit=12) -> list[dict]:
    bucket_rows = [row for row in rows if row.get("evidence_bucket") == bucket]
    return [
        _compact_row(row)
        for row in sorted(
            bucket_rows,
            key=lambda item: item.get("body_pct") if item.get("body_pct") is not None else -999.0,
            reverse=True,
        )[:limit]
    ]


def build_daily_payload(date: str) -> dict:
    rows, _result, _review = cp_candidate_rows(date)
    for row in rows:
        row["evidence_bucket"] = classify_evidence_bucket(row)
        row["prior_day_context_bucket"] = _prior_day_key(row)
    false_rows = [row for row in rows if _is_false_positive(row)]
    true_rows = [row for row in rows if row.get("cp_audit_bucket") == "true_cp_risk"]
    buckets = Counter(row.get("evidence_bucket", "") for row in false_rows)
    warnings = []
    if not false_rows:
        warnings.append("no_cp_false_positive_samples")
    return {
        "date": date,
        "cp_false_positive_total": len(false_rows),
        "exemption_ready_false_positive_count": buckets.get("exemption_ready_false_positive", 0),
        "evidence_missing_false_positive_count": buckets.get("evidence_missing_false_positive", 0),
        "rule_gap_false_positive_count": buckets.get("rule_gap_false_positive", 0),
        "ambiguous_false_positive_count": buckets.get("ambiguous_false_positive", 0),
        "true_cp_risk_reference_count": len(true_rows),
        "missing_evidence_summary": _missing_evidence_summary(false_rows),
        "by_group": _group_distribution(false_rows, "group"),
        "by_leading_cluster_status": _group_distribution(false_rows, "leading_cluster_status"),
        "by_prior_day_context": _group_distribution(false_rows, "prior_day_context_bucket"),
        "top_exemption_ready": _top_rows(false_rows, "exemption_ready_false_positive"),
        "top_evidence_missing": _top_rows(false_rows, "evidence_missing_false_positive"),
        "top_rule_gap": _top_rows(false_rows, "rule_gap_false_positive"),
        "sample_false_positive_rows": [_compact_row(row) for row in false_rows],
        "sample_true_cp_risk_reference": [_compact_row(row) for row in true_rows[:20]],
        "warnings": warnings,
    }


def _top_groups(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.get("group") or row.get("theme_cluster") or "(empty)"].append(row)
    output = []
    for group, bucket_rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        output.append({
            "group": group,
            "candidate_count": len(bucket_rows),
            "evidence_bucket_distribution": dict(Counter(row.get("evidence_bucket", "") for row in bucket_rows)),
            "missing_evidence_summary": _missing_evidence_summary(bucket_rows),
            "performance": _performance_summary(bucket_rows),
        })
    return output


def build_summary_payload(date_list: list[str]) -> dict:
    daily = [build_daily_payload(date) for date in date_list]
    false_rows = []
    true_rows = []
    for payload in daily:
        false_rows.extend(payload.get("sample_false_positive_rows", []) or [])
        true_rows.extend(payload.get("sample_true_cp_risk_reference", []) or [])
    bucket_counter = Counter(row.get("evidence_bucket", "") for row in false_rows)
    conclusions = ["keep_cp_threshold", "repair_evidence_first", "not_ready_for_rule_change"]
    if bucket_counter.get("rule_gap_false_positive", 0):
        conclusions.append("possible_exemption_rule_gap")
    if _missing_evidence_summary(false_rows).get("missing_sector_breadth_evidence", 0):
        conclusions.append("need_sector_breadth_backfill")
    return {
        "date_range": {
            "start_date": min(date_list) if date_list else "",
            "end_date": max(date_list) if date_list else "",
            "dates": date_list,
        },
        "total_false_positives": len(false_rows),
        "exemption_ready_false_positive_count": bucket_counter.get("exemption_ready_false_positive", 0),
        "evidence_missing_false_positive_count": bucket_counter.get("evidence_missing_false_positive", 0),
        "rule_gap_false_positive_count": bucket_counter.get("rule_gap_false_positive", 0),
        "ambiguous_false_positive_count": bucket_counter.get("ambiguous_false_positive", 0),
        "true_cp_risk_reference_count": len(true_rows),
        "missing_evidence_summary": _missing_evidence_summary(false_rows),
        "by_date_distribution": {
            payload["date"]: {
                "cp_false_positive_total": payload.get("cp_false_positive_total", 0),
                "exemption_ready_false_positive": payload.get("exemption_ready_false_positive_count", 0),
                "evidence_missing_false_positive": payload.get("evidence_missing_false_positive_count", 0),
                "rule_gap_false_positive": payload.get("rule_gap_false_positive_count", 0),
                "ambiguous_false_positive": payload.get("ambiguous_false_positive_count", 0),
                "true_cp_risk_reference": payload.get("true_cp_risk_reference_count", 0),
            }
            for payload in daily
        },
        "by_group_distribution": _top_groups(false_rows),
        "by_leading_cluster_status_distribution": _group_distribution(false_rows, "leading_cluster_status"),
        "by_prior_day_context_distribution": _group_distribution(false_rows, "prior_day_context_bucket"),
        "true_cp_risk_reference_performance": _performance_summary(true_rows),
        "false_positive_performance": _performance_summary(false_rows),
        "daily": daily,
        "conclusion": conclusions,
    }


def _render_markdown(payload: dict) -> str:
    lines = [
        "# CP Exemption Evidence Coverage Audit",
        "",
        f"- dates: `{payload['date_range']['dates']}`",
        f"- total_false_positives: `{payload['total_false_positives']}`",
        f"- exemption_ready_false_positive_count: `{payload['exemption_ready_false_positive_count']}`",
        f"- evidence_missing_false_positive_count: `{payload['evidence_missing_false_positive_count']}`",
        f"- rule_gap_false_positive_count: `{payload['rule_gap_false_positive_count']}`",
        f"- ambiguous_false_positive_count: `{payload['ambiguous_false_positive_count']}`",
        f"- true_cp_risk_reference_count: `{payload['true_cp_risk_reference_count']}`",
        f"- missing_evidence_summary: `{payload['missing_evidence_summary']}`",
        f"- conclusion: `{payload['conclusion']}`",
        "",
        "## By Date",
        "",
    ]
    for date, row in payload["by_date_distribution"].items():
        lines.append(f"- {date}: `{row}`")
    lines.extend(["", "## Top Groups Needing Evidence", ""])
    for row in payload["by_group_distribution"][:15]:
        lines.append(f"- {row}")
    lines.extend(["", "## Leading Cluster Status", ""])
    for key, row in payload["by_leading_cluster_status_distribution"].items():
        lines.append(f"- {key}: `{row}`")
    lines.extend(["", "## Prior Day Context", ""])
    for key, row in payload["by_prior_day_context_distribution"].items():
        lines.append(f"- {key}: `{row}`")
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict, output_dir: str | Path | None = None):
    root = Path(output_dir) if output_dir else EVAL_ROOT
    root.mkdir(parents=True, exist_ok=True)
    start = payload["date_range"]["start_date"]
    end = payload["date_range"]["end_date"]
    json_path = root / f"cp_exemption_evidence_coverage_{start}_{end}.json"
    md_path = root / f"cp_exemption_evidence_coverage_{start}_{end}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Audit CP exemption evidence coverage.")
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
        print(json.dumps({"dry_run": True, "dates": date_list, "total_false_positives": payload["total_false_positives"]}, ensure_ascii=False, indent=2))
        return payload
    json_path, md_path = write_outputs(payload, args.output_dir or None)
    print(json.dumps({"json": str(json_path), "md": str(md_path)}, ensure_ascii=False, indent=2))
    return payload


if __name__ == "__main__":
    main()
