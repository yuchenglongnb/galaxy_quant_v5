# -*- coding: utf-8 -*-
"""Diagnose why trend triple gate shadow coverage remains mostly observe."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.auction import AuctionAnalyzer
from core.data_manager import DataManager
from core.intraday_confirmation import IntradayConfirmationBuilder
from utils.encoding import configure_utf8_console

EVAL_DIR = ROOT / "reports" / "analysis" / "evaluations"

POSITIVE_SECTOR_FLAGS = {
    "sector_strength_score_confirmed",
    "sector_breadth_strength_confirmed",
    "sector_limitup_breadth_confirmed",
    "sector_money_flow_confirmed",
}

BLOCKER_PRIORITY = [
    "weak_vs_etf",
    "weak_vs_index",
    "hostile_or_risk_off",
    "relative_strength_unverified",
    "benchmark_missing",
    "amount_missing",
    "amount_not_confirmed",
    "leading_cluster_missing",
    "leading_cluster_weak",
    "sector_vs_index_unverified",
    "stale_overlay_risk",
]


def normalize_target_type(value) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown"
    lowered = text.lower()
    if lowered == "etf":
        return "ETF"
    if lowered in {"index", "industry", "stock"}:
        return lowered
    return text


def derive_primary_blocker(candidate: dict) -> str:
    risk_flags = set(candidate.get("trend_gate_risk_flags", []) or [])
    missing_fields = set(candidate.get("trend_gate_missing_fields", []) or [])
    context = candidate.get("trend_gate_context", {}) or {}

    derived = set(risk_flags)
    if {"missing_rs_vs_etf_pct", "missing_rs_vs_index_pct"} & missing_fields:
        derived.add("relative_strength_unverified")
    if {"missing_benchmark_etf_code", "missing_benchmark_index_code"} & missing_fields:
        derived.add("benchmark_missing")
    if "missing_amount_1m_ratio" in missing_fields:
        derived.add("amount_missing")
    if "leading_cluster_missing" in missing_fields:
        derived.add("leading_cluster_missing")
    if str(context.get("regime", "") or "") in {"hostile", "risk_off"}:
        derived.add("hostile_or_risk_off")

    for label in BLOCKER_PRIORITY:
        if label in derived:
            return label
    if candidate.get("trend_gate_decision_shadow") == "main":
        return "shadow_main"
    return "other"


def _pick(container: dict, *keys):
    for key in keys:
        value = container.get(key)
        if value not in (None, ""):
            return value
    return None


def _present(value) -> bool:
    if value in (None, ""):
        return False
    try:
        return not pd.isna(value)
    except Exception:
        return True


def _ratio(numerator: int, denominator: int) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 0.0


def _candidate_row(signal: dict, benchmark_map: dict) -> dict:
    data = signal.get("data", {}) or {}
    confirmation = data.get("confirmation_data", {}) or {}
    context = signal.get("trend_gate_context", {}) or {}
    group = str(data.get("group", "") or "")
    norm_group = IntradayConfirmationBuilder._normalize_group_key(group)
    mapped = benchmark_map.get(norm_group, {}) if norm_group else {}
    target_type = normalize_target_type(data.get("target_type", ""))
    signal_benchmark_etf = _pick(confirmation, "benchmark_etf_code") or _pick(data, "benchmark_etf_code")
    signal_benchmark_index = _pick(confirmation, "benchmark_index_code") or _pick(data, "benchmark_index_code")
    leading_evidence = list(signal.get("leading_cluster_evidence", []) or [])
    sector_positive = [flag for flag in leading_evidence if flag in POSITIVE_SECTOR_FLAGS]

    row = {
        "code": str(data.get("code", "") or ""),
        "name": str(data.get("name", signal.get("name", "")) or ""),
        "group": group,
        "target_type": target_type,
        "action_score": round(float(signal.get("action_score", 0) or 0), 2),
        "trend_filter_decision": str(signal.get("trend_filter_decision", "") or ""),
        "trend_filter_status": str(signal.get("trend_filter_status", "") or ""),
        "trend_gate_decision_shadow": str(signal.get("trend_gate_decision_shadow", "") or ""),
        "trend_gate_score_shadow": round(float(signal.get("trend_gate_score_shadow", 0) or 0), 2),
        "rs_vs_etf_pct": _pick(confirmation, "rs_vs_etf_pct", "confirmation_rs_vs_etf_pct")
        if confirmation
        else _pick(data, "confirmation_rs_vs_etf_pct", "rs_vs_etf_pct"),
        "rs_vs_index_pct": _pick(confirmation, "rs_vs_index_pct", "confirmation_rs_vs_index_pct")
        if confirmation
        else _pick(data, "confirmation_rs_vs_index_pct", "rs_vs_index_pct"),
        "amount_1m_ratio": _pick(confirmation, "amount_1m_ratio", "confirmation_amount_1m_ratio")
        if confirmation
        else _pick(data, "confirmation_amount_1m_ratio", "amount_1m_ratio"),
        "benchmark_etf_code": str(signal_benchmark_etf or ""),
        "benchmark_index_code": str(signal_benchmark_index or ""),
        "mapped_benchmark_etf_code": str(mapped.get("benchmark_etf_code", "") or ""),
        "mapped_benchmark_index_code": str(mapped.get("benchmark_index_code", "") or ""),
        "leading_cluster_name": str(signal.get("leading_cluster_name", "") or ""),
        "leading_cluster_strength": signal.get("leading_cluster_strength"),
        "leading_cluster_status": str(signal.get("leading_cluster_status", "") or ""),
        "sector_positive_evidence": sector_positive,
        "shadow_reasons": list(signal.get("trend_gate_reasons", []) or []),
        "shadow_risk_flags": list(signal.get("trend_gate_risk_flags", []) or []),
        "shadow_missing_fields": list(signal.get("trend_gate_missing_fields", []) or []),
        "trend_gate_context": context,
    }
    row["primary_blocker"] = derive_primary_blocker(signal)
    return row


def _target_bucket(rows: list[dict]) -> dict:
    candidate_count = len(rows)
    shadow_counter = Counter(row["trend_gate_decision_shadow"] for row in rows)
    return {
        "candidate_count": candidate_count,
        "rs_vs_etf_coverage": _ratio(sum(_present(row["rs_vs_etf_pct"]) for row in rows), candidate_count),
        "rs_vs_index_coverage": _ratio(sum(_present(row["rs_vs_index_pct"]) for row in rows), candidate_count),
        "amount_1m_ratio_coverage": _ratio(sum(_present(row["amount_1m_ratio"]) for row in rows), candidate_count),
        "benchmark_etf_coverage": _ratio(sum(bool(row["benchmark_etf_code"]) for row in rows), candidate_count),
        "benchmark_index_coverage": _ratio(sum(bool(row["benchmark_index_code"]) for row in rows), candidate_count),
        "mapped_benchmark_etf_potential": _ratio(
            sum(bool(row["mapped_benchmark_etf_code"]) for row in rows), candidate_count
        ),
        "mapped_benchmark_index_potential": _ratio(
            sum(bool(row["mapped_benchmark_index_code"]) for row in rows), candidate_count
        ),
        "leading_cluster_active_count": sum(row["leading_cluster_status"] == "active" for row in rows),
        "sector_positive_evidence_count": sum(bool(row["sector_positive_evidence"]) for row in rows),
        "shadow_distribution": dict(shadow_counter),
    }


def build_payload(target_date: int) -> dict:
    dm = DataManager()
    analyzer = AuctionAnalyzer(dm)
    result = analyzer.analyze(int(target_date), realtime=False)
    if result is None:
        raise RuntimeError(f"analyze returned None for {target_date}")

    signals = list(((result.get("signals") or {}).get("trend")) or [])
    benchmark_map = IntradayConfirmationBuilder._normalize_benchmark_map(
        IntradayConfirmationBuilder.load_benchmark_map()
    )
    rows = [_candidate_row(signal, benchmark_map) for signal in signals]

    overall = _target_bucket(rows)
    by_target = defaultdict(list)
    for row in rows:
        by_target[row["target_type"]].append(row)
    by_target_type = {
        key: _target_bucket(bucket)
        for key, bucket in sorted(by_target.items(), key=lambda item: item[0])
    }

    stock_rows = [row for row in rows if row["target_type"] == "stock"]
    group_rows = defaultdict(lambda: {
        "group": "",
        "candidate_count": 0,
        "missing_rs_vs_etf_count": 0,
        "missing_rs_vs_index_count": 0,
        "missing_benchmark_etf_count": 0,
        "missing_benchmark_index_count": 0,
        "missing_amount_count": 0,
        "leading_cluster_missing_count": 0,
        "sector_positive_missing_count": 0,
    })
    for row in stock_rows:
        group = row["group"] or "(empty)"
        entry = group_rows[group]
        entry["group"] = group
        entry["candidate_count"] += 1
        entry["missing_rs_vs_etf_count"] += int(not _present(row["rs_vs_etf_pct"]))
        entry["missing_rs_vs_index_count"] += int(not _present(row["rs_vs_index_pct"]))
        entry["missing_benchmark_etf_count"] += int(not bool(row["benchmark_etf_code"]))
        entry["missing_benchmark_index_count"] += int(not bool(row["benchmark_index_code"]))
        entry["missing_amount_count"] += int(not _present(row["amount_1m_ratio"]))
        entry["leading_cluster_missing_count"] += int(row["leading_cluster_status"] in {"", "missing_ifind_overlay"})
        entry["sector_positive_missing_count"] += int(not bool(row["sector_positive_evidence"]))

    group_summary = sorted(
        group_rows.values(),
        key=lambda item: (
            -item["missing_rs_vs_etf_count"],
            -item["missing_benchmark_etf_count"],
            -item["candidate_count"],
            item["group"],
        ),
    )

    blocker_distribution = Counter(row["primary_blocker"] for row in rows)
    target_type_counter = Counter(row["target_type"] for row in rows)
    signal_enrichment = ((result.get("intraday_confirmation") or {}).get("signal_enrichment") or {})
    intraday_dir = ROOT / "AmazingData_Store" / str(int(target_date)) / "intraday"

    examples = {
        "active_leading_but_observe": [
            row for row in rows
            if row["trend_gate_decision_shadow"] == "observe" and row["leading_cluster_status"] == "active"
        ][:10],
        "shadow_drop": [row for row in rows if row["trend_gate_decision_shadow"] == "drop"][:10],
        "benchmark_missing_with_group": [
            row for row in stock_rows if row["group"] and not row["benchmark_etf_code"]
        ][:10],
        "non_stock_candidates": [row for row in rows if row["target_type"] != "stock"][:10],
        "mismatch_examples": [
            row for row in rows
            if ("main" if row["trend_filter_decision"] == "keep" else row["trend_filter_decision"])
            != row["trend_gate_decision_shadow"]
        ][:15],
    }

    return {
        "date": str(int(target_date)),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "data_status": result.get("data_status", {}),
        "regime_label": (result.get("market_regime") or {}).get("label", "unknown"),
        "intraday_confirmation_status": {
            "intraday_dir_exists": intraday_dir.exists(),
            "confirmation_available": bool(signal_enrichment.get("available")),
            "confirmation_feature_timestamp": signal_enrichment.get("feature_timestamp"),
            "signal_enriched_count": int(signal_enrichment.get("enriched_count", 0) or 0),
            "benchmark_fallback_attached_count": int(signal_enrichment.get("benchmark_fallback_attached_count", 0) or 0),
            "benchmark_fallback_missing_count": int(signal_enrichment.get("benchmark_fallback_missing_count", 0) or 0),
            "rebuild_attempted": bool(signal_enrichment.get("rebuild_attempted")),
            "rebuild_skipped_reason": str(signal_enrichment.get("rebuild_skipped_reason", "") or ""),
        },
        "trend_total": len(rows),
        "target_type_distribution": dict(target_type_counter),
        "overall_coverage": overall,
        "by_target_type": by_target_type,
        "group_missing_summary": group_summary[:20],
        "main_blocking_reason_distribution": dict(blocker_distribution),
        "examples": examples,
    }


def _render_row(row: dict) -> str:
    return (
        f"- {row['code'] or '-'} | {row['name']} | type={row['target_type']} | "
        f"group={row['group'] or '-'} | filter={row['trend_filter_decision']} | "
        f"shadow={row['trend_gate_decision_shadow']} | leading={row['leading_cluster_name'] or '-'} "
        f"({row['leading_cluster_status']}, {row['leading_cluster_strength']}) | "
        f"rs_etf={row['rs_vs_etf_pct']} | rs_index={row['rs_vs_index_pct']} | "
        f"amt={row['amount_1m_ratio']} | bench_etf={row['benchmark_etf_code'] or '-'} | "
        f"bench_idx={row['benchmark_index_code'] or '-'} | blocker={row['primary_blocker']}"
    )


def write_outputs(payload: dict):
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    json_path = EVAL_DIR / f"trend_gate_coverage_{payload['date']}.json"
    md_path = EVAL_DIR / f"trend_gate_coverage_{payload['date']}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Trend Gate Coverage Diagnosis {payload['date']}",
        "",
        "## 1. Core Status",
        "",
        f"- regime: `{payload['regime_label']}`",
        f"- trend_total: `{payload['trend_total']}`",
        f"- target_type_distribution: `{payload['target_type_distribution']}`",
        f"- intraday_dir_exists: `{payload['intraday_confirmation_status']['intraday_dir_exists']}`",
        f"- confirmation_available: `{payload['intraday_confirmation_status']['confirmation_available']}`",
        f"- confirmation_feature_timestamp: `{payload['intraday_confirmation_status']['confirmation_feature_timestamp']}`",
        f"- signal_enriched_count: `{payload['intraday_confirmation_status']['signal_enriched_count']}`",
        f"- benchmark_fallback_attached_count: `{payload['intraday_confirmation_status']['benchmark_fallback_attached_count']}`",
        "",
        "## 2. Overall Coverage",
        "",
        "| metric | value |",
        "| --- | ---: |",
    ]
    for key, value in payload["overall_coverage"].items():
        lines.append(f"| {key} | {value} |")

    lines.extend([
        "",
        "## 3. Coverage By Target Type",
        "",
        "| target_type | count | rs_vs_etf | rs_vs_index | amount | benchmark_etf | benchmark_index | mapped_etf_potential | mapped_index_potential | leading_active | sector_positive | shadow_distribution |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ])
    for key, value in payload["by_target_type"].items():
        lines.append(
            f"| {key} | {value['candidate_count']} | {value['rs_vs_etf_coverage']:.4f} | "
            f"{value['rs_vs_index_coverage']:.4f} | {value['amount_1m_ratio_coverage']:.4f} | "
            f"{value['benchmark_etf_coverage']:.4f} | {value['benchmark_index_coverage']:.4f} | "
            f"{value['mapped_benchmark_etf_potential']:.4f} | {value['mapped_benchmark_index_potential']:.4f} | "
            f"{value['leading_cluster_active_count']} | {value['sector_positive_evidence_count']} | "
            f"{value['shadow_distribution']} |"
        )

    lines.extend([
        "",
        "## 4. Main Blocking Reasons",
        "",
        "| blocker | count |",
        "| --- | ---: |",
    ])
    for blocker, count in sorted(payload["main_blocking_reason_distribution"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {blocker} | {count} |")

    lines.extend([
        "",
        "## 5. Missing-Field Top Groups",
        "",
        "| group | candidate_count | miss_rs_etf | miss_rs_index | miss_bench_etf | miss_bench_index | miss_amount | leading_missing | sector_positive_missing |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for row in payload["group_missing_summary"]:
        lines.append(
            f"| {row['group']} | {row['candidate_count']} | {row['missing_rs_vs_etf_count']} | "
            f"{row['missing_rs_vs_index_count']} | {row['missing_benchmark_etf_count']} | "
            f"{row['missing_benchmark_index_count']} | {row['missing_amount_count']} | "
            f"{row['leading_cluster_missing_count']} | {row['sector_positive_missing_count']} |"
        )

    for title, key in [
        ("Active Leading Cluster But Observe", "active_leading_but_observe"),
        ("Shadow Drop Samples", "shadow_drop"),
        ("Benchmark Missing With Group", "benchmark_missing_with_group"),
        ("Non-Stock Trend Candidates", "non_stock_candidates"),
        ("Mismatch Examples", "mismatch_examples"),
    ]:
        lines.extend(["", f"## {title}", ""])
        rows = payload["examples"].get(key, [])
        if not rows:
            lines.append("- none")
        else:
            lines.extend(_render_row(row) for row in rows)

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def parse_args():
    parser = argparse.ArgumentParser(description="Diagnose trend gate coverage gaps for a replay date.")
    parser.add_argument("--date", required=True, help="Target trade date YYYYMMDD")
    return parser.parse_args()


def main():
    configure_utf8_console()
    args = parse_args()
    payload = build_payload(int(args.date))
    json_path, md_path = write_outputs(payload)
    print(
        json.dumps(
            {
                "json": str(json_path.relative_to(ROOT)),
                "md": str(md_path.relative_to(ROOT)),
                "trend_total": payload["trend_total"],
                "overall_coverage": payload["overall_coverage"],
                "main_blocking_reason_distribution": payload["main_blocking_reason_distribution"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
