# -*- coding: utf-8 -*-
"""Evaluate trend triple gate shadow output without changing live shortlist routing."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.auction import AuctionAnalyzer
from core.data_manager import DataManager
from utils.encoding import configure_utf8_console

EVAL_DIR = ROOT / "reports" / "analysis" / "evaluations"


def pick(obj, *keys):
    for key in keys:
        if isinstance(obj, dict) and key in obj and obj.get(key) not in (None, ""):
            return obj.get(key)
    return None


def candidate_brief(candidate):
    data = candidate.get("data", {}) or {}
    confirmation = data.get("confirmation_data", {}) or {}
    return {
        "code": str(data.get("code", "") or ""),
        "name": str(data.get("name", candidate.get("name", "")) or ""),
        "group": str(data.get("group", "") or ""),
        "theme_cluster": str(candidate.get("theme_cluster", data.get("theme_cluster", "")) or ""),
        "action_score": round(float(candidate.get("action_score", 0) or 0), 2),
        "trend_filter_decision": str(candidate.get("trend_filter_decision", "keep") or "keep"),
        "trend_filter_status": str(candidate.get("trend_filter_status", "") or ""),
        "trend_gate_decision_shadow": str(candidate.get("trend_gate_decision_shadow", "disabled") or "disabled"),
        "trend_gate_score_shadow": round(float(candidate.get("trend_gate_score_shadow", 0) or 0), 2),
        "rs_vs_etf_pct": pick(confirmation, "rs_vs_etf_pct") if confirmation else pick(data, "confirmation_rs_vs_etf_pct", "rs_vs_etf_pct"),
        "rs_vs_index_pct": pick(confirmation, "rs_vs_index_pct") if confirmation else pick(data, "confirmation_rs_vs_index_pct", "rs_vs_index_pct"),
        "amount_1m_ratio": pick(confirmation, "amount_1m_ratio") if confirmation else pick(data, "confirmation_amount_1m_ratio", "amount_1m_ratio"),
        "leading_cluster_name": str(candidate.get("leading_cluster_name", "") or ""),
        "leading_cluster_strength": candidate.get("leading_cluster_strength"),
        "leading_cluster_status": str(candidate.get("leading_cluster_status", "") or ""),
        "shadow_reasons": list(candidate.get("trend_gate_reasons", []) or []),
        "shadow_risk_flags": list(candidate.get("trend_gate_risk_flags", []) or []),
        "shadow_missing_fields": list(candidate.get("trend_gate_missing_fields", []) or []),
    }


def analyze_date(target_date):
    dm = DataManager()
    analyzer = AuctionAnalyzer(dm)
    result = analyzer.analyze(int(target_date), realtime=False)
    if result is None:
        raise RuntimeError(f"analyze returned None for {target_date}")
    return result


def build_payload(target_date):
    result = analyze_date(target_date)
    shortlist = result.get("shortlist", {}) or {}
    raw_trends = list((result.get("signals", {}) or {}).get("trend", []) or [])
    trend_filter_counter = Counter()
    shadow_counter = Counter()
    mismatch_rows = []
    shadow_rows = {"main": [], "observe": [], "drop": [], "disabled": []}

    for item in raw_trends:
        filter_decision = str(item.get("trend_filter_decision", "keep") or "keep")
        shadow_decision = str(item.get("trend_gate_decision_shadow", "disabled") or "disabled")
        trend_filter_counter[filter_decision] += 1
        shadow_counter[shadow_decision] += 1
        row = candidate_brief(item)
        shadow_rows.setdefault(shadow_decision, []).append(row)
        mapped_filter = "main" if filter_decision == "keep" else filter_decision
        if mapped_filter != shadow_decision:
            mismatch_rows.append(row)

    total = len(raw_trends)
    matches = 0
    for item in raw_trends:
        mapped_filter = "main" if str(item.get("trend_filter_decision", "keep") or "keep") == "keep" else str(
            item.get("trend_filter_decision", "keep") or "keep"
        )
        if mapped_filter == str(item.get("trend_gate_decision_shadow", "disabled") or "disabled"):
            matches += 1
    consistency = round(matches / total, 4) if total else 0.0

    return {
        "date": str(target_date),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "data_status": result.get("data_status", {}),
        "regime_label": (result.get("market_regime", {}) or {}).get("label", "unknown"),
        "trend_candidate_total": total,
        "trend_filter_distribution": dict(trend_filter_counter),
        "shadow_distribution": dict(shadow_counter),
        "consistency_ratio": consistency,
        "shortlist_unchanged": True,
        "shortlist_trend_count": len(shortlist.get("trend", []) or []),
        "shortlist_trend_observation_count": len(shortlist.get("trend_observation", []) or []),
        "shadow_main_examples": shadow_rows.get("main", [])[:10],
        "shadow_observe_examples": shadow_rows.get("observe", [])[:10],
        "shadow_drop_examples": shadow_rows.get("drop", [])[:10],
        "mismatch_examples": mismatch_rows[:15],
    }


def write_outputs(target_date):
    payload = build_payload(target_date)
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    json_path = EVAL_DIR / f"trend_triple_gate_eval_{target_date}.json"
    md_path = EVAL_DIR / f"trend_triple_gate_eval_{target_date}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def render_rows(rows, empty_text):
        if not rows:
            return [f"- {empty_text}"]
        lines = []
        for row in rows:
            lines.append(
                f"- {row['code'] or '-'} | {row['name']} | {row['group'] or row['theme_cluster'] or '-'} | "
                f"filter={row['trend_filter_decision']} | shadow={row['trend_gate_decision_shadow']} | "
                f"score={row['trend_gate_score_shadow']:.2f} | rs_etf={row['rs_vs_etf_pct']} | "
                f"rs_index={row['rs_vs_index_pct']} | leading={row['leading_cluster_name'] or '-'} "
                f"({row['leading_cluster_status']}, {row['leading_cluster_strength']}) | "
                f"reasons={';'.join(row['shadow_reasons']) or '-'} | "
                f"risk={';'.join(row['shadow_risk_flags']) or '-'} | "
                f"missing={';'.join(row['shadow_missing_fields']) or '-'}"
            )
        return lines

    md = f"""# Trend Triple Gate Shadow Evaluation {target_date}

## 1. Data Status

- date: `{target_date}`
- cache state: `{payload['data_status'].get('session_state', 'unknown')}`
- post-close validation allowed: `{payload['data_status'].get('session_state') == 'closed'}`

## 2. Core Conclusion

- regime: `{payload['regime_label']}`
- trend candidate total: `{payload['trend_candidate_total']}`
- existing TrendCandidateFilter distribution: `{payload['trend_filter_distribution']}`
- shadow distribution: `{payload['shadow_distribution']}`
- consistency ratio: `{payload['consistency_ratio']}`
- shortlist unchanged: `{payload['shortlist_unchanged']}`

## 3. Shadow Main Samples

{chr(10).join(render_rows(payload['shadow_main_examples'], 'no shadow main samples'))}

## 4. Shadow Observe Samples

{chr(10).join(render_rows(payload['shadow_observe_examples'], 'no shadow observe samples'))}

## 5. Shadow Drop Samples

{chr(10).join(render_rows(payload['shadow_drop_examples'], 'no shadow drop samples'))}

## 6. Mismatch Examples

{chr(10).join(render_rows(payload['mismatch_examples'], 'no mismatch examples'))}
"""
    md_path.write_text(md, encoding="utf-8")
    return payload, json_path, md_path


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate trend triple gate shadow mode.")
    parser.add_argument("--date", required=True, help="Target trade date YYYYMMDD")
    return parser.parse_args()


def main():
    configure_utf8_console()
    args = parse_args()
    payload, json_path, md_path = write_outputs(args.date)
    print(
        json.dumps(
            {
                "json": str(json_path.relative_to(ROOT)),
                "md": str(md_path.relative_to(ROOT)),
                "trend_candidate_total": payload["trend_candidate_total"],
                "shadow_distribution": payload["shadow_distribution"],
                "consistency_ratio": payload["consistency_ratio"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
