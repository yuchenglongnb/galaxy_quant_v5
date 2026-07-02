# -*- coding: utf-8 -*-
"""Apply manual-approved signal_detail code mapping decisions to second-level temp copies."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backfill_signal_detail_code_temp_copy import next_returns  # noqa: E402
from utils.encoding import configure_utf8_console  # noqa: E402


RESIDUAL_REPORT = ROOT / "reports" / "analysis" / "evaluations" / "signal_detail_residual_code_mapping_review_20260629_20260701.json"
P1_4C_DERIVED_ROOT = ROOT / "reports" / "validation" / "derived" / "signal_detail_code_backfilled"
MANUAL_PATCH_ROOT = ROOT / "reports" / "validation" / "derived" / "signal_detail_manual_code_patch"
TEMPLATE_ROOT = ROOT / "reports" / "analysis" / "templates"
EVAL_ROOT = ROOT / "reports" / "analysis" / "evaluations"

VALID_SCOPES = {"stock", "etf", "index", "industry_without_code", "blocked"}
VALID_STATUSES = {"approved", "blocked", "pending"}


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str, "date": str, "approved_code": str})
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _derived_path(date: str) -> Path:
    return P1_4C_DERIVED_ROOT / f"{date}_signal_detail.code_backfilled.csv"


def _manual_patch_path(date: str) -> Path:
    return MANUAL_PATCH_ROOT / f"{date}_signal_detail.manual_code_patch.csv"


def load_residual_rows() -> list[dict]:
    if not RESIDUAL_REPORT.exists():
        return []
    payload = json.loads(RESIDUAL_REPORT.read_text(encoding="utf-8"))
    return payload.get("residual_rows", [])


def default_approval_for_row(row: dict) -> dict:
    candidate_codes = ",".join(row.get("candidate_codes", []))
    if set(row.get("candidate_codes", [])) == {"159915.SZ", "399006.SZ"}:
        return {
            "date": row["date"],
            "row_index": row["row_index"],
            "name": row["name"],
            "signal_type": row.get("signal_type", ""),
            "problem_types": "|".join(row.get("problem_types", [])),
            "candidate_codes": candidate_codes,
            "approved_code": "",
            "approved_scope": "blocked",
            "approval_status": "pending",
            "approval_reason": "need_manual_decision_between_159915_SZ_etf_and_399006_SZ_index",
        }
    return {
        "date": row["date"],
        "row_index": row["row_index"],
        "name": row["name"],
        "signal_type": row.get("signal_type", ""),
        "problem_types": "|".join(row.get("problem_types", [])),
        "candidate_codes": candidate_codes,
        "approved_code": "",
        "approved_scope": "industry_without_code",
        "approval_status": "approved",
        "approval_reason": "sector_or_industry_item_excluded_from_code_level_join",
    }


def ensure_approval_template(path: Path) -> tuple[Path, bool]:
    if path.exists():
        return path, False
    rows = [default_approval_for_row(row) for row in load_residual_rows()]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "date",
                "row_index",
                "name",
                "signal_type",
                "problem_types",
                "candidate_codes",
                "approved_code",
                "approved_scope",
                "approval_status",
                "approval_reason",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return path, True


def read_approval_file(path: Path) -> tuple[dict[tuple[str, int], dict], dict, list[str]]:
    frame = _read_csv(path)
    approvals: dict[tuple[str, int], dict] = {}
    warnings = []
    summary = Counter()
    for _, row in frame.iterrows():
        status = str(row.get("approval_status", "") or "").strip()
        scope = str(row.get("approved_scope", "") or "").strip()
        if status not in VALID_STATUSES:
            warnings.append(f"invalid_approval_status:{row.get('date')}#{row.get('row_index')}:{status}")
            status = "pending"
        if scope not in VALID_SCOPES:
            warnings.append(f"invalid_approved_scope:{row.get('date')}#{row.get('row_index')}:{scope}")
            scope = "blocked"
        approved_code = str(row.get("approved_code", "") or "").strip()
        if approved_code.lower() in {"nan", "none", "null"}:
            approved_code = ""
        item = {
            "date": str(row.get("date", "")),
            "row_index": int(row.get("row_index")),
            "name": str(row.get("name", "")),
            "candidate_codes": [code for code in str(row.get("candidate_codes", "") or "").split(",") if code],
            "approved_code": approved_code,
            "approved_scope": scope,
            "approval_status": status,
            "approval_reason": str(row.get("approval_reason", "") or ""),
        }
        approvals[(item["date"], item["row_index"])] = item
        summary[status] += 1
        if scope == "industry_without_code":
            summary["industry_without_code"] += 1
        if status == "approved" and approved_code:
            summary["code_patch_approved"] += 1
    return approvals, {
        "approved": int(summary["approved"]),
        "blocked": int(summary["blocked"]),
        "pending": int(summary["pending"]),
        "industry_without_code": int(summary["industry_without_code"]),
        "code_patch_approved": int(summary["code_patch_approved"]),
    }, warnings


def apply_to_date(date: str, approvals: dict[tuple[str, int], dict]) -> tuple[pd.DataFrame, dict, list[str]]:
    path = _derived_path(date)
    frame = _read_csv(path)
    warnings = []
    summary = Counter()
    if frame.empty:
        return frame, {"date": date, "row_count": 0, "written": False}, ["derived_input_missing_or_empty"]
    result = frame.copy()
    if "code" not in result.columns:
        result["code"] = ""
    result["code"] = result["code"].fillna("").astype(str)
    for column in (
        "manual_resolution_status",
        "manual_resolution_scope",
        "manual_resolution_code",
        "manual_resolution_reason",
    ):
        if column not in result.columns:
            result[column] = ""
    for idx, row in result.iterrows():
        approval = approvals.get((date, int(idx)))
        if not approval:
            continue
        status = approval["approval_status"]
        scope = approval["approved_scope"]
        approved_code = approval["approved_code"]
        result.at[idx, "manual_resolution_status"] = status
        result.at[idx, "manual_resolution_scope"] = scope
        result.at[idx, "manual_resolution_code"] = approved_code
        result.at[idx, "manual_resolution_reason"] = approval["approval_reason"]
        if status == "pending":
            summary["pending_count"] += 1
            continue
        if status == "blocked":
            summary["blocked_count"] += 1
            continue
        if scope == "industry_without_code":
            summary["industry_without_code_marked_count"] += 1
            continue
        if approved_code and status == "approved" and scope in {"stock", "etf", "index"}:
            if approval["candidate_codes"] and approved_code not in approval["candidate_codes"]:
                warnings.append(f"approved_code_not_in_candidates:{date}#{idx}:{approved_code}")
                summary["warnings_count"] += 1
                continue
            result.at[idx, "code"] = approved_code
            summary["code_patched_count"] += 1
        elif approved_code:
            warnings.append(f"approved_code_without_valid_approval:{date}#{idx}:{approved_code}")
            summary["warnings_count"] += 1
    return result, {
        "date": date,
        "row_count": int(len(result)),
        "code_patched_count": int(summary["code_patched_count"]),
        "industry_without_code_marked_count": int(summary["industry_without_code_marked_count"]),
        "pending_count": int(summary["pending_count"]),
        "blocked_count": int(summary["blocked_count"]),
        "warnings_count": int(summary["warnings_count"]),
        "written": False,
    }, warnings


def recheck_pair(prev_date: str, date: str, frame: pd.DataFrame) -> dict:
    ret = next_returns(date)
    if frame.empty:
        return {
            "prev_date": prev_date,
            "date": date,
            "primary_code_join_count": 0,
            "manual_scope_excluded_count": 0,
            "pending_blocked_count": 0,
            "fallback_name_join_count": 0,
            "unmatched_count": 0,
            "ambiguous_blocked_count": 0,
            "join_quality": "empty",
        }
    excluded = frame["manual_resolution_scope"].fillna("").astype(str) == "industry_without_code"
    pending = frame["manual_resolution_status"].fillna("").astype(str) == "pending"
    code_level = frame[~excluded & ~pending].copy()
    ret = ret if not ret.empty else pd.DataFrame(columns=["code", "name", "t1_close_return", "t1_open_return"])
    by_code = ret[ret["code"].astype(str) != ""].drop_duplicates("code") if "code" in ret.columns else pd.DataFrame()
    joined = code_level.merge(
        by_code[["code", "t1_open_return", "t1_close_return"]] if not by_code.empty else pd.DataFrame(columns=["code", "t1_open_return", "t1_close_return"]),
        on="code",
        how="left",
    )
    joined["t1_join_method"] = joined["t1_close_return"].notna().map(lambda ok: "code" if ok else "unmatched")
    fallback_count = 0
    missing = joined["t1_close_return"].isna()
    if missing.any() and "name" in joined.columns and "name" in ret.columns:
        unique_names = ret.dropna(subset=["name"]).groupby("name").filter(lambda rows: len(rows) == 1)
        name_map = unique_names.set_index("name")[["t1_open_return", "t1_close_return"]].to_dict("index")
        for idx, row in joined[missing].iterrows():
            if row.get("code_fill_status") == "ambiguous":
                continue
            values = name_map.get(row.get("name"))
            if not values:
                continue
            joined.at[idx, "t1_open_return"] = values.get("t1_open_return")
            joined.at[idx, "t1_close_return"] = values.get("t1_close_return")
            joined.at[idx, "t1_join_method"] = "name_fallback"
            fallback_count += 1
    primary = int((joined["t1_join_method"] == "code").sum())
    unmatched = int((joined["t1_join_method"] == "unmatched").sum())
    ambiguous_blocked = int((joined.get("code_fill_status", pd.Series(dtype=str)) == "ambiguous").sum())
    pending_count = int(pending.sum())
    excluded_count = int(excluded.sum())
    if unmatched == 0 and fallback_count == 0 and pending_count == 0:
        quality = "code_keyed_complete"
    elif unmatched == 0:
        quality = "complete_with_explicit_pending_or_fallback"
    else:
        quality = "partial"
    return {
        "prev_date": prev_date,
        "date": date,
        "primary_code_join_count": primary,
        "manual_scope_excluded_count": excluded_count,
        "pending_blocked_count": pending_count,
        "fallback_name_join_count": int(fallback_count),
        "unmatched_count": unmatched,
        "ambiguous_blocked_count": ambiguous_blocked,
        "join_quality": quality,
    }


def build_payload(approval_file: Path, write_temp_copy: bool = False) -> dict:
    approval_file, template_created = ensure_approval_template(approval_file)
    approvals, approval_summary, approval_warnings = read_approval_file(approval_file)
    dates = sorted({date for date, _ in approvals.keys()})
    patched_by_date = {}
    patch_summaries = []
    warnings = list(approval_warnings)
    written_files = []
    total_patch = Counter()
    for date in dates:
        frame, summary, date_warnings = apply_to_date(date, approvals)
        patched_by_date[date] = frame
        patch_summaries.append(summary)
        warnings.extend(date_warnings)
        for key in ("code_patched_count", "industry_without_code_marked_count", "pending_count", "blocked_count", "warnings_count"):
            total_patch[key] += summary.get(key, 0)
        if write_temp_copy:
            MANUAL_PATCH_ROOT.mkdir(parents=True, exist_ok=True)
            output = _manual_patch_path(date)
            frame.to_csv(output, index=False, encoding="utf-8-sig")
            written_files.append(_display_path(output))
            summary["written"] = True
    pairs = []
    for prev, date in zip(dates, dates[1:]):
        pairs.append(recheck_pair(prev, date, patched_by_date.get(prev, pd.DataFrame())))
    join_totals = Counter()
    for pair in pairs:
        for key in (
            "primary_code_join_count",
            "manual_scope_excluded_count",
            "pending_blocked_count",
            "fallback_name_join_count",
            "unmatched_count",
            "ambiguous_blocked_count",
        ):
            join_totals[key] += pair.get(key, 0)
    if join_totals["unmatched_count"] == 0 and join_totals["fallback_name_join_count"] == 0 and join_totals["pending_blocked_count"] == 0:
        join_quality = "code_keyed_complete"
    elif join_totals["unmatched_count"] == 0:
        join_quality = "complete_with_explicit_pending_or_fallback"
    else:
        join_quality = "partial"
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "date_range": {"start": dates[0] if dates else "", "end": dates[-1] if dates else ""},
        "approval_file": _display_path(approval_file),
        "approval_template_created": template_created,
        "approval_summary": approval_summary,
        "original_files_modified": False,
        "p1_4c_derived_files_modified": False,
        "manual_patch_files_written": written_files,
        "patch_summary": {
            "code_patched_count": int(total_patch["code_patched_count"]),
            "industry_without_code_marked_count": int(total_patch["industry_without_code_marked_count"]),
            "pending_count": int(total_patch["pending_count"]),
            "blocked_count": int(total_patch["blocked_count"]),
            "warnings_count": int(total_patch["warnings_count"] + len(approval_warnings)),
        },
        "daily_patch_summary": patch_summaries,
        "t1_join_recheck": {
            "pairs": pairs,
            "primary_code_join_count": int(join_totals["primary_code_join_count"]),
            "manual_scope_excluded_count": int(join_totals["manual_scope_excluded_count"]),
            "pending_blocked_count": int(join_totals["pending_blocked_count"]),
            "fallback_name_join_count": int(join_totals["fallback_name_join_count"]),
            "unmatched_count": int(join_totals["unmatched_count"]),
            "ambiguous_blocked_count": int(join_totals["ambiguous_blocked_count"]),
            "join_quality": join_quality,
        },
        "auto_patch_used": False,
        "strategy_rule_change_required": False,
        "cp_evaluator_change_required": False,
        "trend_evaluator_change_required": False,
        "lesson_pattern_written": False,
        "recommended_next_actions": [
            "manually_review_pending_chinext_rows",
            "use_manual_temp_patch_for_t1_validation_only_after_review",
            "keep_original_and_p1_4c_derived_files_unchanged",
        ],
        "warnings": warnings,
        "conclusion": [
            "manual_approval_required",
            "auto_patch_disabled",
            "original_signal_detail_not_modified",
            "p1_4c_derived_signal_detail_not_modified",
            "manual_temp_patch_only",
            "industry_items_excluded_from_code_level_join",
            "ambiguous_index_etf_rows_pending",
            "no_strategy_rule_change",
            "cp_evaluator_change_not_required",
            "trend_evaluator_change_not_required",
            "lesson_pattern_not_written",
        ],
    }


def write_reports(payload: dict) -> tuple[Path, Path]:
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = EVAL_ROOT / "manual_signal_detail_code_mapping_patch_20260629_20260701.json"
    md_path = EVAL_ROOT / "manual_signal_detail_code_mapping_patch_20260629_20260701.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def render_markdown(payload: dict) -> str:
    lines = [
        "# Manual Signal Detail Code Mapping Patch",
        "",
        f"- approval_file: `{payload['approval_file']}`",
        f"- original_files_modified: `{payload['original_files_modified']}`",
        f"- p1_4c_derived_files_modified: `{payload['p1_4c_derived_files_modified']}`",
        f"- manual_patch_files_written: `{len(payload['manual_patch_files_written'])}`",
        f"- approval_summary: `{payload['approval_summary']}`",
        f"- patch_summary: `{payload['patch_summary']}`",
        f"- t1_join_recheck: `{payload['t1_join_recheck']}`",
        "",
        "## Conclusion",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["conclusion"])
    return "\n".join(lines) + "\n"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Apply manual signal_detail code mapping patch to temp copies.")
    parser.add_argument("--approval-file", required=True)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--write-temp-copy", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    configure_utf8_console()
    args = parse_args(argv)
    approval_file = Path(args.approval_file)
    if not approval_file.is_absolute():
        approval_file = ROOT / approval_file
    payload = build_payload(approval_file, write_temp_copy=args.write_temp_copy)
    json_path, md_path = write_reports(payload)
    print(
        json.dumps(
            {
                "json": _display_path(json_path),
                "md": _display_path(md_path),
                "approval_file": payload["approval_file"],
                "approval_summary": payload["approval_summary"],
                "manual_patch_files_written": payload["manual_patch_files_written"],
                "patch_summary": payload["patch_summary"],
                "t1_join_recheck": payload["t1_join_recheck"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
