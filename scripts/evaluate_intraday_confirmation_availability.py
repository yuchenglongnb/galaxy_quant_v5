# -*- coding: utf-8 -*-
"""Read-only audit for intraday confirmation availability on one replay date."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.encoding import configure_utf8_console  # noqa: E402


def _eval_root() -> Path:
    return ROOT / "reports" / "analysis" / "evaluations"


def _safe_read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            with path.open("r", encoding=encoding, newline="") as fh:
                return list(csv.DictReader(fh))
        except UnicodeDecodeError:
            continue
        except Exception:
            return []
    return []


def _csv_status(path: Path, required_fields: list[str] | None = None) -> dict:
    required_fields = required_fields or []
    status = {
        "path": str(path),
        "exists": path.exists(),
        "rows": 0,
        "columns": [],
        "required_fields_missing": required_fields,
    }
    if not path.exists():
        return status
    rows = _safe_read_csv(path)
    columns = list(rows[0].keys()) if rows else []
    if not columns:
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as fh:
                columns = [str(item) for item in next(csv.reader(fh), [])]
        except Exception as exc:
            status["read_error"] = str(exc)
    status.update(
        {
            "rows": len(rows),
            "columns": columns,
            "required_fields_missing": [field for field in required_fields if field not in columns],
        }
    )
    return status


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}


def _clean(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _code_set(rows: list[dict]) -> set[str]:
    return {_clean(row.get("code")) for row in rows if _clean(row.get("code"))}


def _trend_candidates(date: str) -> list[dict]:
    detail_path = ROOT / "reports" / "validation" / "daily" / date / "signal_detail.csv"
    rows = _safe_read_csv(detail_path)
    return [row for row in rows if _clean(row.get("signal_category")) == "trend"]


def _name_to_codes(date: str) -> dict[str, set[str]]:
    validation_dir = ROOT / "reports" / "validation" / "daily" / date
    mapping: dict[str, set[str]] = {}
    for filename in (
        "factor_snapshot_stock.csv",
        "factor_snapshot_etf.csv",
        "factor_snapshot_index.csv",
        "factor_snapshot_industry_topk.csv",
    ):
        for row in _safe_read_csv(validation_dir / filename):
            name = _clean(row.get("name"))
            code = _clean(row.get("code"))
            if not name or not code:
                continue
            mapping.setdefault(name, set()).add(code)
    return mapping


def _candidate_code_match_status(date: str, stock_intraday_rows: list[dict]) -> dict:
    candidates = _trend_candidates(date)
    mapping = _name_to_codes(date)
    stock_intraday_codes = _code_set(stock_intraday_rows)
    matched = []
    unmatched = []
    intersected = []
    for row in candidates:
        name = _clean(row.get("name"))
        codes = sorted(mapping.get(name, set()))
        record = {
            "name": name,
            "target_type": _clean(row.get("target_type")),
            "codes": codes,
        }
        if codes:
            matched.append(record)
            if stock_intraday_codes and any(code in stock_intraday_codes for code in codes):
                intersected.append(record)
        else:
            unmatched.append(record)
    return {
        "trend_candidate_count": len(candidates),
        "code_matched_count": len(matched),
        "code_unmatched_count": len(unmatched),
        "intraday_intersection_count": len(intersected),
        "code_match_possible": bool(stock_intraday_codes),
        "unmatched_samples": unmatched,
        "matched_samples": matched,
    }


def _count_status(path: Path) -> dict:
    status = _csv_status(path)
    return {
        "exists": status["exists"],
        "rows": status["rows"],
        "path": status["path"],
    }


def _missing_reasons(
    *,
    stock_1min_status: dict,
    etf_1min_status: dict,
    index_1min_status: dict,
    confirmation_status: dict,
    stocks_noon_status: dict,
    candidate_status: dict,
) -> dict:
    reasons = {}
    if not stock_1min_status.get("exists") or int(stock_1min_status.get("rows", 0) or 0) == 0:
        reasons["stock_intraday_minute_missing"] = 1
    if not stocks_noon_status.get("exists") or int(stocks_noon_status.get("rows", 0) or 0) == 0:
        reasons["stock_noon_missing"] = 1
    if not etf_1min_status.get("exists") or int(etf_1min_status.get("rows", 0) or 0) == 0:
        reasons["etf_intraday_minute_missing"] = 1
    if not index_1min_status.get("exists") or int(index_1min_status.get("rows", 0) or 0) == 0:
        reasons["index_intraday_minute_missing"] = 1
    if not confirmation_status.get("exists") or int(confirmation_status.get("rows", 0) or 0) == 0:
        reasons["confirmation_file_missing"] = 1
    if candidate_status.get("trend_candidate_count", 0) and candidate_status.get("code_unmatched_count", 0) == candidate_status.get("trend_candidate_count", 0):
        reasons["candidate_code_unmatched"] = int(candidate_status.get("code_unmatched_count", 0) or 0)
    return reasons


def _root_cause(reasons: dict) -> str:
    for reason in (
        "stock_intraday_minute_missing",
        "candidate_code_unmatched",
        "confirmation_file_missing",
        "index_intraday_minute_missing",
        "etf_intraday_minute_missing",
    ):
        if reasons.get(reason):
            return reason
    return "other"


def build_payload(date: str) -> dict:
    date = str(date)
    store_dir = ROOT / "AmazingData_Store" / date
    intraday_dir = store_dir / "intraday"
    validation_dir = ROOT / "reports" / "validation" / "daily" / date
    review_path = ROOT / "reports" / "analysis" / "daily" / date / "auction_review.json"
    review = _load_json(review_path)
    summary = review.get("intraday_confirmation_summary", {}) or {}

    stock_1min = _csv_status(intraday_dir / "stocks_1min.csv", ["code"])
    etf_1min = _csv_status(intraday_dir / "etf_1min.csv", ["code"])
    index_1min = _csv_status(intraday_dir / "indices_1min.csv", ["code"])
    confirmation = _csv_status(intraday_dir / "stock_confirmation_latest.csv", ["code"])
    stocks_noon = _csv_status(store_dir / "stocks_noon.csv")
    indices_noon = _csv_status(store_dir / "indices_noon.csv")
    stock_intraday_rows = _safe_read_csv(intraday_dir / "stocks_1min.csv")
    candidate_status = _candidate_code_match_status(date, stock_intraday_rows)
    reasons = _missing_reasons(
        stock_1min_status=stock_1min,
        etf_1min_status=etf_1min,
        index_1min_status=index_1min,
        confirmation_status=confirmation,
        stocks_noon_status=stocks_noon,
        candidate_status=candidate_status,
    )
    root_cause = _root_cause(reasons)

    summary_coverage_count = int(summary.get("coverage_count", 0) or 0)
    confirmation_row_count = int(confirmation.get("rows", 0) or 0)
    coverage_count = summary_coverage_count or confirmation_row_count
    available = bool(summary.get("available", False)) or confirmation_row_count > 0
    conclusions = [
        "keep_trend_active_disabled",
        "no_strategy_rule_change",
        "read_only_audit",
    ]
    if root_cause == "stock_intraday_minute_missing":
        conclusions.extend(["stock_intraday_minute_missing", "intraday_confirmation_blocked_by_data"])
    if root_cause == "candidate_code_unmatched":
        conclusions.extend(["candidate_code_unmatched", "intraday_confirmation_blocked_by_mapping"])

    recommendations = []
    if root_cause == "stock_intraday_minute_missing":
        recommendations.extend(
            [
                "backfill_20260629_stock_0935_min1_with_isolated_query",
                "backfill_20260629_index_etf_0935_min1_for_benchmarks",
                "rebuild_intraday_confirmation_after_min1_available",
                "rerun_trend_confirmation_coverage_audit",
            ]
        )
    elif root_cause == "candidate_code_unmatched":
        recommendations.append("inspect_trend_candidate_name_code_mapping")
    recommendations.append("keep_trend_active_disabled_until_confirmation_coverage_recovers")

    warnings = []
    if _count_status(store_dir / "stocks_auction.csv")["exists"] and _count_status(store_dir / "stocks_close.csv")["exists"]:
        warnings.append("auction_and_close_exist_but_do_not_imply_0935_confirmation")
    if indices_noon.get("exists") and not stocks_noon.get("exists"):
        warnings.append("index_noon_exists_but_stock_noon_missing")

    return {
        "date": date,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "intraday_confirmation_available": available,
        "coverage_count": coverage_count,
        "coverage_source": "auction_review" if summary_coverage_count else "confirmation_file",
        "candidate_count": candidate_status["trend_candidate_count"],
        "stock_minute_status": {
            "intraday_dir_exists": intraday_dir.exists(),
            "stocks_1min": stock_1min,
            "stock_confirmation_latest": confirmation,
        },
        "index_etf_minute_status": {
            "intraday_dir_exists": intraday_dir.exists(),
            "indices_1min": index_1min,
            "etf_1min": etf_1min,
            "root_indices_noon": indices_noon,
        },
        "auction_status": {
            "stocks_auction": _count_status(store_dir / "stocks_auction.csv"),
            "indices_auction": _count_status(store_dir / "indices_auction.csv"),
        },
        "close_status": {
            "stocks_close": _count_status(store_dir / "stocks_close.csv"),
            "indices_close": _count_status(store_dir / "indices_close.csv"),
        },
        "noon_status": {
            "stocks_noon": stocks_noon,
            "indices_noon": indices_noon,
        },
        "validation_status": {
            "signal_detail": _count_status(validation_dir / "signal_detail.csv"),
            "signal_metrics": _count_status(validation_dir / "signal_metrics.csv"),
            "factor_snapshot_stock": _count_status(validation_dir / "factor_snapshot_stock.csv"),
            "factor_snapshot_etf": _count_status(validation_dir / "factor_snapshot_etf.csv"),
            "factor_snapshot_index": _count_status(validation_dir / "factor_snapshot_index.csv"),
            "factor_snapshot_industry_topk": _count_status(validation_dir / "factor_snapshot_industry_topk.csv"),
        },
        "candidate_code_match_status": candidate_status,
        "missing_reason_counts": reasons,
        "root_cause": root_cause,
        "trend_active_allowed": False,
        "recommended_next_actions": recommendations,
        "warnings": warnings,
        "conclusion": conclusions,
    }


def _render_markdown(payload: dict) -> str:
    lines = [
        f"# Intraday Confirmation Availability {payload['date']}",
        "",
        "## Core Status",
        "",
        f"- intraday_confirmation_available: `{payload['intraday_confirmation_available']}`",
        f"- coverage_count: `{payload['coverage_count']}`",
        f"- candidate_count: `{payload['candidate_count']}`",
        f"- root_cause: `{payload['root_cause']}`",
        f"- trend_active_allowed: `{payload['trend_active_allowed']}`",
        f"- conclusion: `{payload['conclusion']}`",
        "",
        "## Minute Data",
        "",
        f"- stock intraday dir exists: `{payload['stock_minute_status']['intraday_dir_exists']}`",
        f"- stocks_1min: `{payload['stock_minute_status']['stocks_1min']['exists']}` rows=`{payload['stock_minute_status']['stocks_1min']['rows']}`",
        f"- stock_confirmation_latest: `{payload['stock_minute_status']['stock_confirmation_latest']['exists']}` rows=`{payload['stock_minute_status']['stock_confirmation_latest']['rows']}`",
        f"- indices_1min: `{payload['index_etf_minute_status']['indices_1min']['exists']}` rows=`{payload['index_etf_minute_status']['indices_1min']['rows']}`",
        f"- etf_1min: `{payload['index_etf_minute_status']['etf_1min']['exists']}` rows=`{payload['index_etf_minute_status']['etf_1min']['rows']}`",
        f"- root indices_noon: `{payload['index_etf_minute_status']['root_indices_noon']['exists']}` rows=`{payload['index_etf_minute_status']['root_indices_noon']['rows']}`",
        f"- root stocks_noon: `{payload['noon_status']['stocks_noon']['exists']}` rows=`{payload['noon_status']['stocks_noon']['rows']}`",
        "",
        "## Candidate Matching",
        "",
    ]
    for key, value in payload["candidate_code_match_status"].items():
        if key.endswith("_samples"):
            continue
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Missing Reasons", ""])
    for key, value in payload["missing_reason_counts"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Recommended Next Actions", ""])
    for item in payload["recommended_next_actions"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Warnings", ""])
    for item in payload["warnings"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict) -> tuple[Path, Path]:
    root = _eval_root()
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / f"intraday_confirmation_availability_{payload['date']}.json"
    md_path = root / f"intraday_confirmation_availability_{payload['date']}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate why intraday confirmation is unavailable for one date.")
    parser.add_argument("--date", required=True, help="Trade date YYYYMMDD")
    return parser.parse_args(argv)


def main(argv=None):
    configure_utf8_console()
    args = parse_args(argv)
    payload = build_payload(args.date)
    json_path, md_path = write_outputs(payload)
    print(
        json.dumps(
            {
                "json": str(json_path.relative_to(ROOT)),
                "md": str(md_path.relative_to(ROOT)),
                "intraday_confirmation_available": payload["intraday_confirmation_available"],
                "coverage_count": payload["coverage_count"],
                "root_cause": payload["root_cause"],
                "trend_active_allowed": payload["trend_active_allowed"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
