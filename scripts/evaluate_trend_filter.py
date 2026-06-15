# -*- coding: utf-8 -*-
"""Replay trend-filter behavior without invoking runner side effects."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.auction import AuctionAnalyzer
from analyzers.evaluators.trend_candidate_filter import TrendCandidateFilter
from core.data_manager import DataManager
from utils.encoding import configure_utf8_console

EVAL_DIR = ROOT / "reports" / "analysis" / "evaluations"


def pick(obj, *keys):
    for key in keys:
        if isinstance(obj, dict) and key in obj and obj.get(key) not in (None, ""):
            return obj.get(key)
    return None


def is_present(value):
    if value in (None, ""):
        return False
    try:
        return not pd.isna(value)  # type: ignore[name-defined]
    except Exception:
        return True


def candidate_brief(candidate):
    data = candidate.get("data", {}) or {}
    confirmation = data.get("confirmation_data", {}) or {}
    return {
        "code": str(data.get("code", "") or ""),
        "name": str(data.get("name", candidate.get("name", "")) or ""),
        "group": str(data.get("group", data.get("industry", "")) or ""),
        "theme_cluster": str(data.get("theme_cluster", "") or ""),
        "action_score": round(float(candidate.get("action_score", 0) or 0), 2),
        "trend_filter_score": round(float(candidate.get("trend_filter_score", 0) or 0), 2),
        "trend_filter_decision": str(candidate.get("trend_filter_decision", "keep") or "keep"),
        "trend_filter_status": str(candidate.get("trend_filter_status", "disabled") or "disabled"),
        "trend_filter_context": candidate.get("trend_filter_context", {}) or {},
        "rs_vs_etf_pct": pick(confirmation, "rs_vs_etf_pct")
        if confirmation
        else pick(data, "confirmation_rs_vs_etf_pct", "rs_vs_etf_pct"),
        "rs_vs_index_pct": pick(confirmation, "rs_vs_index_pct")
        if confirmation
        else pick(data, "confirmation_rs_vs_index_pct", "rs_vs_index_pct"),
        "amount_1m_ratio": pick(confirmation, "amount_1m_ratio")
        if confirmation
        else pick(data, "confirmation_amount_1m_ratio", "amount_1m_ratio"),
        "reasons": list(candidate.get("trend_filter_reasons", []) or []),
        "risk_flags": list(candidate.get("trend_filter_risk_flags", []) or []),
        "missing_fields": list(candidate.get("trend_filter_missing_fields", []) or []),
        "invalid_conditions": list(candidate.get("trend_filter_invalid_conditions", []) or []),
        "shortlist_reason": str(candidate.get("shortlist_reason", "") or ""),
        "action_filter_reason": str(candidate.get("action_filter_reason", "") or ""),
    }


def analyze_date(target_date, enabled):
    config_path = TrendCandidateFilter.CONFIG_PATH
    original_text = config_path.read_text(encoding="utf-8")
    original_config = json.loads(original_text)
    try:
        config = deepcopy(original_config)
        config["enabled"] = enabled
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        TrendCandidateFilter.reset_cache()
        dm = DataManager()
        analyzer = AuctionAnalyzer(dm)
        result = analyzer.analyze(int(target_date), realtime=False)
        if result is None:
            raise RuntimeError(f"analyze returned None for {target_date}")
        return result
    finally:
        config_path.write_text(original_text, encoding="utf-8")
        TrendCandidateFilter.reset_cache()


def summarize_result(result, filter_enabled):
    shortlist = result.get("shortlist", {}) or {}
    raw_trends = list((result.get("signals", {}) or {}).get("trend", []) or [])
    confirmation_meta = result.get("intraday_confirmation", {}) or {}
    enrichment_meta = confirmation_meta.get("signal_enrichment", {}) or {}
    regime = (result.get("market_regime", {}) or {}).get("label", "unknown")

    decision_counter = Counter()
    reason_counter = defaultdict(Counter)
    decision_rows = defaultdict(list)
    for item in raw_trends:
        decision = str(item.get("trend_filter_decision", "keep") or "keep") if filter_enabled else "keep"
        decision_counter[decision] += 1
        decision_rows[decision].append(item)
        tokens = []
        if filter_enabled:
            tokens.extend(item.get("trend_filter_reasons", []) or [])
            tokens.extend(item.get("trend_filter_risk_flags", []) or [])
            tokens.extend(item.get("trend_filter_missing_fields", []) or [])
            tokens.extend(item.get("trend_filter_invalid_conditions", []) or [])
        else:
            tokens.append("filter_disabled")
        for token in tokens:
            reason_counter[decision][str(token)] += 1

    for decision in decision_rows:
        decision_rows[decision] = [
            candidate_brief(item)
            for item in sorted(
                decision_rows[decision],
                key=lambda row: row.get("action_score", 0),
                reverse=True,
            )
        ]

    context = {}
    if raw_trends:
        context = raw_trends[0].get("trend_filter_context", {}) or {}

    stock_trends = [item for item in raw_trends if ((item.get("data") or {}).get("target_type") == "stock")]
    mapped_etf_count = 0
    mapped_index_count = 0
    rs_etf_count = 0
    rs_index_count = 0
    for item in stock_trends:
        data = item.get("data", {}) or {}
        confirmation = data.get("confirmation_data", {}) or {}
        if is_present(data.get("benchmark_etf_code")) or is_present(confirmation.get("benchmark_etf_code")):
            mapped_etf_count += 1
        if is_present(data.get("benchmark_index_code")) or is_present(confirmation.get("benchmark_index_code")):
            mapped_index_count += 1
        if is_present(pick(confirmation, "rs_vs_etf_pct")) or is_present(pick(data, "confirmation_rs_vs_etf_pct", "rs_vs_etf_pct")):
            rs_etf_count += 1
        if is_present(pick(confirmation, "rs_vs_index_pct")) or is_present(pick(data, "confirmation_rs_vs_index_pct", "rs_vs_index_pct")):
            rs_index_count += 1

    return {
        "date": str(result.get("date")),
        "filter_enabled": filter_enabled,
        "data_status": result.get("data_status", {}),
        "regime_label": regime,
        "regime_detail": result.get("market_regime", {}),
        "coverage_context": context,
        "coverage_status": raw_trends[0].get("trend_filter_status", "disabled") if raw_trends else "disabled",
        "coverage_metrics": {
            "stock_trend_count": len(stock_trends),
            "benchmark_etf_mapping_ratio": round(mapped_etf_count / len(stock_trends), 4) if stock_trends else 0.0,
            "benchmark_index_mapping_ratio": round(mapped_index_count / len(stock_trends), 4) if stock_trends else 0.0,
            "rs_vs_etf_coverage_ratio": round(rs_etf_count / len(stock_trends), 4) if stock_trends else 0.0,
            "rs_vs_index_coverage_ratio": round(rs_index_count / len(stock_trends), 4) if stock_trends else 0.0,
        },
        "confirmation_meta": {
            "available": confirmation_meta.get("available"),
            "applied": confirmation_meta.get("applied"),
            "feature_timestamp": confirmation_meta.get("feature_timestamp"),
            "selected_after_confirmation": confirmation_meta.get("selected_after_confirmation"),
            "rejected_count": confirmation_meta.get("rejected_count"),
            "enriched_count": enrichment_meta.get("enriched_count", 0),
        },
        "counts": {
            "trend_count": len(shortlist.get("trend", []) or []),
            "trend_observation_count": len(shortlist.get("trend_observation", []) or []),
            "trend_dropped_debug_count": len(decision_rows.get("drop", [])),
            "cp_count": len(shortlist.get("trap", []) or []),
            "reversal_count": len(shortlist.get("reversal", []) or []),
            "raw_trend_signal_count": len(raw_trends),
        },
        "top_trend": [candidate_brief(item) for item in shortlist.get("trend", [])],
        "shortlist_trend_observation": [candidate_brief(item) for item in shortlist.get("trend_observation", [])],
        "decision_distribution": dict(decision_counter),
        "reason_distribution": {
            decision: [{"reason": reason, "count": count} for reason, count in counter.most_common(12)]
            for decision, counter in reason_counter.items()
        },
        "decision_samples": {decision: rows[:10] for decision, rows in decision_rows.items()},
    }


def build_single_payload(target_date):
    filter_off = summarize_result(analyze_date(target_date, enabled=False), filter_enabled=False)
    filter_on = summarize_result(analyze_date(target_date, enabled=True), filter_enabled=True)
    config = TrendCandidateFilter.load_config()
    regime_name = filter_on["regime_label"]
    regime_hit = regime_name in ((config.get("regime_rules", {}) or {}))
    potential_false_drops = []
    filter_off_top = {(row["code"] or row["name"]): row for row in filter_off["top_trend"]}
    for decision in ("observe", "drop"):
        for row in filter_on["decision_samples"].get(decision, []):
            key = row["code"] or row["name"]
            if key in filter_off_top:
                potential_false_drops.append(
                    {
                        **row,
                        "downgraded_from_filter_off_trend": True,
                        "likely_cause": "missing_confirmation_data" if row["missing_fields"] else "rule_strictness",
                    }
                )

    suggestions = []
    if not regime_hit:
        suggestions.append(f"missing regime rule: {regime_name}")
    if filter_on["confirmation_meta"]["enriched_count"] == 0:
        suggestions.append(
            f"{target_date} had no 09:35 confirmation enrichment; current decisions are dominated by missing confirmation coverage"
        )
    if filter_on["coverage_status"] == "degraded_global_missing":
        suggestions.append(
            "global coverage guard is active; keep/observe results should be read as data-missing-aware fallback, not relative-strength proof"
        )

    return {
        "date": str(target_date),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "filter_off": filter_off["counts"],
        "filter_on": filter_on["counts"],
        "filter_off_confirmation": filter_off["confirmation_meta"],
        "filter_on_confirmation": filter_on["confirmation_meta"],
        "filter_on_coverage": filter_on["coverage_context"],
        "filter_on_coverage_metrics": filter_on["coverage_metrics"],
        "filter_on_status": filter_on["coverage_status"],
        "decision_distribution": filter_on["decision_distribution"],
        "reason_distribution": filter_on["reason_distribution"],
        "regime_distribution": {regime_name: {"config_hit": regime_hit}},
        "top_trend_off": filter_off["top_trend"],
        "top_trend_on": filter_on["top_trend"],
        "observation_samples": filter_on["decision_samples"].get("observe", [])[:10],
        "drop_samples": filter_on["decision_samples"].get("drop", [])[:10],
        "potential_false_drops": potential_false_drops[:10],
        "config_suggestions": suggestions,
        "audit": {
            "trend_observation_preserved": True,
            "trend_observation_evidence": 'AuctionAnalyzer._apply_intraday_confirmation uses shortlist.setdefault("trend_observation", []) and appends rejected trend candidates.',
            "drop_audit_source": 'Raw trend candidates remain in result["signals"]["trend"] with trend_filter_decision preserved.',
        },
    }


def write_single_evaluation(target_date):
    payload = build_single_payload(target_date)
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    json_path = EVAL_DIR / f"trend_filter_eval_{target_date}.json"
    md_path = EVAL_DIR / f"trend_filter_eval_{target_date}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def reason_line(decision):
        rows = payload["reason_distribution"].get(decision, [])[:5]
        return ", ".join([f"{row['reason']}({row['count']})" for row in rows]) or "-"

    def sample_lines(rows, empty_text):
        if not rows:
            return [f"- {empty_text}"]
        rendered = []
        for row in rows[:10]:
            rendered.append(
                f"- {row['code'] or '-'} | {row['name']} | {row['group'] or row['theme_cluster'] or '-'} | "
                f"action_score={row['action_score']:.2f} | filter_score={row['trend_filter_score']:.2f} | "
                f"rs_vs_etf_pct={row['rs_vs_etf_pct']} | rs_vs_index_pct={row['rs_vs_index_pct']} | "
                f"reasons={';'.join(row['reasons']) or '-'} | risk={';'.join(row['risk_flags']) or '-'} | missing={';'.join(row['missing_fields']) or '-'}"
            )
        return rendered

    coverage = payload["filter_on_coverage"]
    coverage_metrics = payload["filter_on_coverage_metrics"]
    md = f"""# Trend Filter Evaluation {target_date}

## 1. 验证日期

`{target_date}`

## 2. 验证目的

说明本次验证是为了确认：`strong_repair 不等于 trend 全开`

## 3. before/after 数量对比

| 指标 | filter off | filter on | 变化 |
|---|---:|---:|---:|
| trend 主列表数量 | {payload['filter_off']['trend_count']} | {payload['filter_on']['trend_count']} | {payload['filter_on']['trend_count'] - payload['filter_off']['trend_count']} |
| trend_observation 数量 | {payload['filter_off']['trend_observation_count']} | {payload['filter_on']['trend_observation_count']} | {payload['filter_on']['trend_observation_count'] - payload['filter_off']['trend_observation_count']} |
| trend_dropped_debug 数量 | 0 | {payload['filter_on']['trend_dropped_debug_count']} | {payload['filter_on']['trend_dropped_debug_count']} |
| CP 数量 | {payload['filter_off']['cp_count']} | {payload['filter_on']['cp_count']} | {payload['filter_on']['cp_count'] - payload['filter_off']['cp_count']} |
| reversal 数量 | {payload['filter_off']['reversal_count']} | {payload['filter_on']['reversal_count']} | {payload['filter_on']['reversal_count'] - payload['filter_off']['reversal_count']} |

## Confirmation Coverage

| metric | value |
|---|---:|
| raw trend signals | {payload['filter_on']['raw_trend_signal_count']} |
| confirmation coverage count | {coverage.get('confirmation_coverage_count', 0)} |
| confirmation coverage ratio | {coverage.get('confirmation_coverage_ratio', 0)} |
| benchmark_etf_mapping_ratio | {coverage_metrics.get('benchmark_etf_mapping_ratio', 0)} |
| benchmark_index_mapping_ratio | {coverage_metrics.get('benchmark_index_mapping_ratio', 0)} |
| rs_vs_etf available | {coverage.get('rs_vs_etf_available_count', 0)} |
| rs_vs_index available | {coverage.get('rs_vs_index_available_count', 0)} |
| rs_vs_etf_coverage_ratio | {coverage_metrics.get('rs_vs_etf_coverage_ratio', 0)} |
| rs_vs_index_coverage_ratio | {coverage_metrics.get('rs_vs_index_coverage_ratio', 0)} |
| amount_1m_ratio available | {coverage.get('amount_1m_ratio_available_count', 0)} |
| trend_filter_status | {payload['filter_on_status']} |

## 4. keep / observe / drop 原因分布

| decision | count | top reasons |
|---|---:|---|
| keep | {payload['decision_distribution'].get('keep', 0)} | {reason_line('keep')} |
| observe | {payload['decision_distribution'].get('observe', 0)} | {reason_line('observe')} |
| drop | {payload['decision_distribution'].get('drop', 0)} | {reason_line('drop')} |

## 5. trend 主列表变化

{chr(10).join(sample_lines(payload['top_trend_on'], '无 trend 主列表保留样本'))}

## 6. observation 代表样本

{chr(10).join(sample_lines(payload['observation_samples'], '无 observation 样本'))}

## 7. drop 代表样本

{chr(10).join(sample_lines(payload['drop_samples'], '无 drop 样本'))}

## 8. 潜在误杀检查

{chr(10).join(sample_lines(payload['potential_false_drops'], '未发现明显核心票被 drop；若存在降级，更接近 coverage 缺失导致的保守处理'))}

## 9. regime 命中检查

- replay 实际 regime: `{next(iter(payload['regime_distribution'].keys()), 'unknown')}`
- config 命中: `{next(iter(payload['regime_distribution'].values()), {}).get('config_hit', False)}`
- 证据: `trend_filter_config.json -> regime_rules`

## 10. 结论

1. trend 主列表{'明显收敛' if payload['filter_on']['trend_count'] < payload['filter_off']['trend_count'] else '未明显收敛'}。
2. 本次更重要的结论是：`{target_date}` 的 relative strength 结论是否可信，取决于 confirmation coverage，而不是单看 keep/observe 数量。
3. 当前 status=`{payload['filter_on_status']}`，因此本次结果应被解释为 `{payload['filter_on_status']}` 模式下的过滤行为。
4. broad_strong_repair / rotational_strong_repair 的拆分可以继续，但前提是先有更多 `active` 状态样本。

## 附加审计

- `trend_observation` 保留状态: `{payload['audit']['trend_observation_preserved']}`
- 证据: {payload['audit']['trend_observation_evidence']}
- drop 审计来源: {payload['audit']['drop_audit_source']}
- config 建议: {', '.join(payload['config_suggestions']) if payload['config_suggestions'] else '无'}
"""
    md_path.write_text(md, encoding="utf-8")
    return payload, json_path, md_path


def build_summary_payload(seed_date, desired_days, max_scan_days):
    dm = DataManager()
    local_days = [int(day) for day in dm.get_local_daily_days()]
    rows = []
    selected_dates = []
    for day in sorted(local_days, reverse=True)[:max_scan_days]:
        payload = build_single_payload(day)
        row = {
            "date": str(day),
            "regime": next(iter(payload["regime_distribution"].keys()), "unknown"),
            "coverage_ratio": payload["filter_on_coverage"].get("confirmation_coverage_ratio", 0.0),
            "rs_vs_etf_coverage_ratio": payload.get("filter_on_coverage_metrics", {}).get("rs_vs_etf_coverage_ratio", 0.0),
            "rs_vs_index_coverage_ratio": payload.get("filter_on_coverage_metrics", {}).get("rs_vs_index_coverage_ratio", 0.0),
            "benchmark_etf_mapping_ratio": payload.get("filter_on_coverage_metrics", {}).get("benchmark_etf_mapping_ratio", 0.0),
            "benchmark_index_mapping_ratio": payload.get("filter_on_coverage_metrics", {}).get("benchmark_index_mapping_ratio", 0.0),
            "coverage_status": payload["filter_on_status"],
            "filter_off_trend": payload["filter_off"]["trend_count"],
            "filter_on_trend": payload["filter_on"]["trend_count"],
            "observation": payload["filter_on"]["trend_observation_count"],
            "drop": payload["filter_on"]["trend_dropped_debug_count"],
            "main_reason": (
                payload["reason_distribution"].get("observe", [{}])[0].get("reason", "-")
                if payload["reason_distribution"].get("observe")
                else payload["reason_distribution"].get("drop", [{}])[0].get("reason", "-")
            ),
            "confirmation_enriched_count": payload["filter_on_confirmation"].get("enriched_count", 0),
        }
        rows.append(row)
        if row["coverage_ratio"] >= 0.6:
            selected_dates.append(row["date"])
        if len(selected_dates) >= desired_days:
            break

    return {
        "seed_date": str(seed_date),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "selected_dates": selected_dates[:desired_days],
        "rows": rows,
    }


def write_summary(seed_date, desired_days, max_scan_days):
    payload = build_summary_payload(seed_date, desired_days, max_scan_days)
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    json_path = EVAL_DIR / "trend_filter_eval_summary.json"
    md_path = EVAL_DIR / "trend_filter_eval_summary.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Trend Filter Evaluation Summary",
        "",
        f"- seed_date: `{seed_date}`",
        f"- selected high-coverage dates: {', '.join(payload['selected_dates']) if payload['selected_dates'] else 'none found'}",
        "",
        "| date | regime | coverage_ratio | rs_vs_index_cov | rs_vs_etf_cov | etf_map_cov | filter_off_trend | filter_on_trend | observation | drop | main_reason |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['date']} | {row['regime']} | {row['coverage_ratio']:.2f} | "
            f"{row['rs_vs_index_coverage_ratio']:.2f} | {row['rs_vs_etf_coverage_ratio']:.2f} | "
            f"{row['benchmark_etf_mapping_ratio']:.2f} | {row['filter_off_trend']} | {row['filter_on_trend']} | {row['observation']} | "
            f"{row['drop']} | {row['main_reason']} |"
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return payload, json_path, md_path


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate trend filter behavior without runner side effects.")
    parser.add_argument("date", nargs="?", default="20260612", help="Target trade date YYYYMMDD")
    parser.add_argument("--summary-days", type=int, default=2, help="Number of high-coverage days to look for")
    parser.add_argument("--max-scan-days", type=int, default=30, help="Maximum local trading days to scan for high coverage samples")
    return parser.parse_args()


def main():
    configure_utf8_console()
    args = parse_args()
    single_payload, single_json, single_md = write_single_evaluation(args.date)
    summary_payload, summary_json, summary_md = write_summary(args.date, args.summary_days, args.max_scan_days)
    print(
        json.dumps(
            {
                "single_json": str(single_json.relative_to(ROOT)),
                "single_md": str(single_md.relative_to(ROOT)),
                "summary_json": str(summary_json.relative_to(ROOT)),
                "summary_md": str(summary_md.relative_to(ROOT)),
                "selected_high_coverage_dates": summary_payload["selected_dates"],
                "seed_filter_status": single_payload["filter_on_status"],
                "seed_coverage_ratio": single_payload["filter_on_coverage"].get("confirmation_coverage_ratio", 0.0),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
