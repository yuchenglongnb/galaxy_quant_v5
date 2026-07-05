# -*- coding: utf-8 -*-
"""Analysis-only audit for CP false positives during structural repair regimes.

This tool is a validation/reporting helper. It does not change CP thresholds,
expand exemptions, write lesson/pattern/registry files, or mutate strategy
configuration. Heavy auction dependencies are imported lazily so unit tests can
exercise pure analysis functions without requiring a live data environment.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.encoding import configure_utf8_console  # noqa: E402


EVAL_ROOT = ROOT / "reports" / "analysis" / "evaluations"
VALIDATION_ROOT = ROOT / "reports" / "validation" / "daily"
DAILY_ROOT = ROOT / "reports" / "analysis" / "daily"

ACTIVE_CLUSTER_STATUSES = {"active", "partial"}
RISK_DECISIONS = {"hard_trap", "crowded_observe", "crowded_trap", "trap", "risk_observe"}


def _to_float(value, default=None):
    if value in (None, ""):
        return default
    try:
        return float(value)
    except Exception:
        return default


def _to_bool(value):
    if isinstance(value, bool):
        return value
    text = str("" if value is None else value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _avg(values: list[float]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return round(sum(clean) / len(clean), 4) if clean else None


def _median(values: list[float]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return round(float(statistics.median(clean)), 4) if clean else None


def _ratio(numerator: int, denominator: int) -> float:
    return round(float(numerator) * 100.0 / float(denominator), 4) if denominator else 0.0


def _normalize_target_type(value: str) -> str:
    text = str(value or "").strip().lower()
    mapping = {
        "stock": "stock",
        "个股": "stock",
        "涓偂": "stock",
        "etf": "ETF",
        "index": "index",
        "指数": "index",
        "鎸囨暟": "index",
        "industry": "industry",
        "行业": "industry",
        "琛屼笟": "industry",
    }
    return mapping.get(text, "unknown")


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


def _detail_key(category: str, code: str, name: str, target_type: str) -> str:
    return "::".join([str(category or ""), str(code or ""), str(name or ""), str(target_type or "")])


def _load_detail_map(date: str) -> dict[str, dict]:
    path = VALIDATION_ROOT / str(date) / "signal_detail.csv"
    if not path.exists():
        return {}
    detail = {}
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            category = str(row.get("signal_category", "") or "").strip()
            name = str(row.get("name", "") or "").strip()
            code = str(row.get("code", "") or "").strip()
            target_type = _normalize_target_type(row.get("target_type", ""))
            if not category or not name:
                continue
            detail[_detail_key(category, code, name, target_type)] = row
            detail.setdefault(_detail_key(category, "", name, target_type), row)
    return detail


def _load_review(date: str) -> dict:
    path = DAILY_ROOT / str(date) / "auction_review.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _market_label(result: dict, review: dict) -> str:
    gate = review.get("environment_gate") or {}
    if gate.get("label"):
        return str(gate.get("label"))
    regime = result.get("market_regime") or review.get("market_regime") or {}
    if isinstance(regime, dict):
        return str(regime.get("label", "") or "")
    return str(regime or "")


def _environment_decision(review: dict) -> str:
    gate = review.get("environment_gate") or {}
    return str(gate.get("decision", "") or "")


def _is_repair_context(result: dict, review: dict) -> bool:
    prior = result.get("prior_day_context") or review.get("prior_day_context") or {}
    readthrough = prior.get("readthrough") or review.get("prior_day_readthrough") or {}
    texts = [
        str(readthrough.get("headline", "") or ""),
        str(readthrough.get("bias", "") or ""),
        " ".join(str(item) for item in readthrough.get("focus_points", []) or []),
        " ".join(str(item) for item in readthrough.get("risk_points", []) or []),
    ]
    joined = " ".join(texts).lower()
    return any(token in joined for token in ["repair", "reversal", "修复", "承接", "反核"])


def _leading_cluster_active(row: dict) -> bool:
    return str(row.get("leading_cluster_status", "") or "") in ACTIVE_CLUSTER_STATUSES


def _performance_summary(rows: list[dict]) -> dict:
    body_values = [row.get("body_pct") for row in rows if row.get("body_pct") is not None]
    success_values = [row.get("validation_success") for row in rows if row.get("validation_success") is not None]
    return {
        "candidate_count": len(rows),
        "performance_available": bool(body_values or success_values),
        "avg_body_pct": _avg(body_values),
        "median_body_pct": _median(body_values),
        "success_rate": _ratio(sum(1 for item in success_values if item), len(success_values)) if success_values else None,
        "avg_t1_open_return": None,
        "t1_open_win_rate": None,
        "avg_t1_close_return": None,
        "t1_close_win_rate": None,
    }


def classify_cp_bucket(row: dict) -> str:
    """Assign one audit-only CP attribution bucket."""
    validation_success = row.get("validation_success")
    body_pct = row.get("body_pct")
    body_strong = body_pct is not None and body_pct > 0
    body_weak = body_pct is not None and body_pct < 0
    cp_failed = validation_success is False or body_strong
    cp_succeeded = validation_success is True or body_weak
    active_cluster = _leading_cluster_active(row)

    if cp_failed and active_cluster and float(row.get("leading_cluster_strength") or 0.0) >= 50:
        return "leading_cluster_repair_false_positive"
    if cp_failed and (float(row.get("prior_day_context_bonus") or 0.0) > 0 or row.get("repair_context")):
        return "prior_day_context_explained_false_positive"
    if cp_succeeded and row.get("market_regime") == "risk_off" and not active_cluster:
        return "true_cp_risk"
    if cp_succeeded and not active_cluster:
        return "true_cp_risk"
    return "unresolved_cp"


def _compact_row(row: dict) -> dict:
    return {
        "date": row.get("date", ""),
        "bucket": row.get("cp_audit_bucket", ""),
        "category": row.get("category", ""),
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
        "leading_cluster_status": row.get("leading_cluster_status", ""),
        "leading_cluster_strength": row.get("leading_cluster_strength"),
        "leading_cluster_name": row.get("leading_cluster_name", ""),
        "prior_day_context_bonus": row.get("prior_day_context_bonus"),
        "body_pct": row.get("body_pct"),
        "validation_success": row.get("validation_success"),
        "reasons": row.get("cp_audit_reasons", []),
    }


def _row_from_candidate(candidate: dict, detail: dict, date: str, result: dict, review: dict) -> dict:
    data = candidate.get("data") or {}
    target_type = _normalize_target_type(data.get("target_type", candidate.get("target_type", "")))
    name = str(candidate.get("name", "") or "")
    code = str(data.get("code", candidate.get("code", "")) or "")
    detail_row = detail.get(_detail_key("trap", code, name, target_type)) or detail.get(
        _detail_key("trap", "", name, target_type),
        {},
    )
    body_pct = _to_float(detail_row.get("body_pct"), _to_float(data.get("body_pct")))
    validation_success = _to_bool(detail_row.get("validation_success"))
    market_regime = _market_label(result, review)
    row = {
        "date": date,
        "category": "trap",
        "target_type": target_type,
        "code": code,
        "name": name,
        "group": str(data.get("group", "") or candidate.get("group", "") or ""),
        "theme_cluster": str(detail_row.get("theme_cluster", "") or candidate.get("theme_cluster", "") or ""),
        "market_regime": market_regime,
        "environment_decision": _environment_decision(review),
        "cp": _to_float(candidate.get("cp"), _to_float(data.get("cp"))),
        "cp_score": _to_float(data.get("cp_score")),
        "cp_risk_score": _to_float(candidate.get("cp_risk_score"), _to_float(data.get("cp_score"))),
        "cp_risk_decision": str(candidate.get("cp_risk_decision", "") or ""),
        "cp_risk_flags": candidate.get("cp_risk_flags") or [],
        "cp_risk_reasons": candidate.get("cp_risk_reasons") or [],
        "leading_cluster_status": str(candidate.get("leading_cluster_status", "") or ""),
        "leading_cluster_strength": _to_float(candidate.get("leading_cluster_strength"), 0.0),
        "leading_cluster_name": str(candidate.get("leading_cluster_name", "") or ""),
        "leading_cluster_evidence": candidate.get("leading_cluster_evidence") or [],
        "prior_day_context_bonus": _to_float(candidate.get("prior_day_context_bonus"), 0.0),
        "prior_day_context_bonus_shadow": _to_float(candidate.get("prior_day_context_bonus_shadow"), 0.0),
        "body_pct": body_pct,
        "validation_success": validation_success,
        "close_pct": _to_float(detail_row.get("close_pct")),
        "auction_pct": _to_float(detail_row.get("auction_pct"), _to_float(data.get("auction_pct"))),
        "performance_available": bool(detail_row) or body_pct is not None or validation_success is not None,
        "repair_context": _is_repair_context(result, review),
    }
    row["cp_audit_bucket"] = classify_cp_bucket(row)
    reasons = []
    if row["market_regime"] == "risk_off":
        reasons.append("risk_off_regime")
    if _leading_cluster_active(row):
        reasons.append("leading_cluster_active_or_partial")
    if row["validation_success"] is False:
        reasons.append("cp_validation_failed")
    if row["validation_success"] is True:
        reasons.append("cp_validation_success")
    if row["body_pct"] is not None and row["body_pct"] > 0:
        reasons.append("positive_body_false_positive")
    if row.get("repair_context"):
        reasons.append("prior_day_or_readthrough_repair_context")
    row["cp_audit_reasons"] = reasons
    return row


def cp_candidate_rows(date: str) -> tuple[list[dict], dict, dict]:
    from analyzers.auction import AuctionAnalyzer
    from core.data_manager import DataManager

    dm = DataManager()
    analyzer = AuctionAnalyzer(dm)
    result = analyzer.analyze(int(date), realtime=False) or {}
    review = _load_review(date)
    detail = _load_detail_map(date)
    rows = []
    for candidate in ((result.get("signals") or {}).get("trap") or []):
        if not (
            candidate.get("cp_risk_decision")
            or candidate.get("cp_risk_score") is not None
            or candidate.get("cp_risk_flags")
            or candidate.get("cp") is not None
        ):
            continue
        rows.append(_row_from_candidate(candidate, detail, date, result, review))
    return rows, result, review


def _distribution(rows: list[dict], key: str) -> dict:
    grouped = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key, "") or "(empty)")].append(row)
    output = {}
    for value, bucket_rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        output[value] = {
            "candidate_count": len(bucket_rows),
            "bucket_distribution": dict(Counter(row.get("cp_audit_bucket") or row.get("bucket", "") for row in bucket_rows)),
            "performance": _performance_summary(bucket_rows),
        }
    return output


def build_daily_payload(date: str) -> dict:
    rows, result, review = cp_candidate_rows(date)
    market_regime = _market_label(result, review)
    environment_decision = _environment_decision(review)
    by_bucket = defaultdict(list)
    for row in rows:
        by_bucket[row["cp_audit_bucket"]].append(row)
    warnings = []
    if not rows:
        warnings.append("no_cp_candidates")
    if any(not row.get("performance_available") for row in rows):
        warnings.append("post_close_performance_unavailable")
    return {
        "date": date,
        "market_regime": market_regime,
        "environment_decision": environment_decision,
        "cp_total": len(rows),
        "true_cp_risk_count": len(by_bucket["true_cp_risk"]),
        "leading_cluster_repair_false_positive_count": len(by_bucket["leading_cluster_repair_false_positive"]),
        "prior_day_context_explained_false_positive_count": len(by_bucket["prior_day_context_explained_false_positive"]),
        "unresolved_cp_count": len(by_bucket["unresolved_cp"]),
        "by_cp_risk_decision": _distribution(rows, "cp_risk_decision"),
        "by_leading_cluster_status": _distribution(rows, "leading_cluster_status"),
        "by_bucket_performance": {bucket: _performance_summary(bucket_rows) for bucket, bucket_rows in sorted(by_bucket.items())},
        "top_true_cp_risk": [_compact_row(row) for row in sorted(by_bucket["true_cp_risk"], key=lambda item: item.get("body_pct") or 0)[:12]],
        "top_false_positive": [_compact_row(row) for row in sorted(
            by_bucket["leading_cluster_repair_false_positive"] + by_bucket["prior_day_context_explained_false_positive"],
            key=lambda item: item.get("body_pct") if item.get("body_pct") is not None else -999,
            reverse=True,
        )[:12]],
        "sample_rows": [_compact_row(row) for row in rows],
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
            "bucket_distribution": dict(Counter(row.get("bucket", "") for row in bucket_rows)),
            "performance": _performance_summary(bucket_rows),
        })
    return output


def build_summary_payload(date_list: list[str]) -> dict:
    daily = [build_daily_payload(date) for date in date_list]
    rows = []
    for payload in daily:
        rows.extend(payload.get("sample_rows", []) or [])
    by_bucket = defaultdict(list)
    for row in rows:
        by_bucket[row.get("bucket", "")].append(row)
    false_positive_rows = by_bucket["leading_cluster_repair_false_positive"] + by_bucket["prior_day_context_explained_false_positive"]
    conclusions = [
        "keep_cp_threshold",
        "not_ready_for_rule_change",
    ]
    if false_positive_rows:
        conclusions.append("improve_exemption_evidence")
    if by_bucket["leading_cluster_repair_false_positive"]:
        conclusions.append("need_more_sector_breadth")
    if by_bucket["prior_day_context_explained_false_positive"]:
        conclusions.append("prior_day_context_helpful")
    return {
        "date_range": {
            "start_date": min(date_list) if date_list else "",
            "end_date": max(date_list) if date_list else "",
            "dates": date_list,
        },
        "total_cp_candidates": len(rows),
        "true_cp_risk_count": len(by_bucket["true_cp_risk"]),
        "leading_cluster_repair_false_positive_count": len(by_bucket["leading_cluster_repair_false_positive"]),
        "prior_day_context_explained_false_positive_count": len(by_bucket["prior_day_context_explained_false_positive"]),
        "unresolved_cp_count": len(by_bucket["unresolved_cp"]),
        "bucket_performance": {bucket: _performance_summary(bucket_rows) for bucket, bucket_rows in sorted(by_bucket.items())},
        "by_date_bucket_distribution": {
            payload["date"]: {
                "market_regime": payload.get("market_regime", ""),
                "environment_decision": payload.get("environment_decision", ""),
                "cp_total": payload.get("cp_total", 0),
                "true_cp_risk": payload.get("true_cp_risk_count", 0),
                "leading_cluster_repair_false_positive": payload.get("leading_cluster_repair_false_positive_count", 0),
                "prior_day_context_explained_false_positive": payload.get("prior_day_context_explained_false_positive_count", 0),
                "unresolved_cp": payload.get("unresolved_cp_count", 0),
            }
            for payload in daily
        },
        "by_regime_bucket_distribution": _distribution(rows, "market_regime"),
        "by_leading_cluster_status_bucket_distribution": _distribution(rows, "leading_cluster_status"),
        "cp_false_positive_top_groups": _top_groups(false_positive_rows)[:15],
        "cp_true_risk_top_groups": _top_groups(by_bucket["true_cp_risk"])[:15],
        "daily": daily,
        "conclusion": conclusions,
    }


def _render_markdown(payload: dict) -> str:
    lines = [
        "# CP Structural Repair False-positive Audit",
        "",
        f"- dates: `{payload['date_range']['dates']}`",
        f"- total_cp_candidates: `{payload['total_cp_candidates']}`",
        f"- true_cp_risk_count: `{payload['true_cp_risk_count']}`",
        f"- leading_cluster_repair_false_positive_count: `{payload['leading_cluster_repair_false_positive_count']}`",
        f"- prior_day_context_explained_false_positive_count: `{payload['prior_day_context_explained_false_positive_count']}`",
        f"- unresolved_cp_count: `{payload['unresolved_cp_count']}`",
        f"- conclusion: `{payload['conclusion']}`",
        "",
        "## By Date",
        "",
    ]
    for date, row in payload["by_date_bucket_distribution"].items():
        lines.append(f"- {date}: `{row}`")
    lines.extend(["", "## Bucket Performance", ""])
    for bucket, row in payload["bucket_performance"].items():
        lines.append(f"- {bucket}: `{row}`")
    lines.extend(["", "## False Positive Top Groups", ""])
    for row in payload["cp_false_positive_top_groups"]:
        lines.append(f"- {row}")
    lines.extend(["", "## True Risk Top Groups", ""])
    for row in payload["cp_true_risk_top_groups"]:
        lines.append(f"- {row}")
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict, output_dir: str | Path | None = None):
    root = Path(output_dir) if output_dir else EVAL_ROOT
    root.mkdir(parents=True, exist_ok=True)
    start = payload["date_range"]["start_date"]
    end = payload["date_range"]["end_date"]
    json_path = root / f"cp_structural_repair_audit_{start}_{end}.json"
    md_path = root / f"cp_structural_repair_audit_{start}_{end}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Audit CP false positives across structural repair dates.")
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
        print(json.dumps({"dry_run": True, "dates": date_list, "total_cp_candidates": payload["total_cp_candidates"]}, ensure_ascii=False, indent=2))
        return payload
    json_path, md_path = write_outputs(payload, args.output_dir or None)
    print(json.dumps({"json": str(json_path), "md": str(md_path)}, ensure_ascii=False, indent=2))
    return payload


if __name__ == "__main__":
    main()
