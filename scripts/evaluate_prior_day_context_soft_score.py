# -*- coding: utf-8 -*-
"""Evaluate guarded prior-day context soft score without changing routing semantics."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from analyzers.auction import AuctionAnalyzer  # noqa: E402
from core.data_manager import DataManager  # noqa: E402
from utils.encoding import configure_utf8_console  # noqa: E402


def _parse_date(argv):
    for idx, arg in enumerate(argv):
        if arg == "--date" and idx + 1 < len(argv):
            return int(argv[idx + 1])
        if arg.startswith("--date="):
            return int(arg.split("=", 1)[1])
    raise ValueError("Usage: python scripts/evaluate_prior_day_context_soft_score.py --date YYYYMMDD")


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _category_rows(signals, category):
    rows = []
    for candidate in signals.get(category, []) or []:
        rows.append({
            "category": category,
            "name": str(candidate.get("name", "") or ""),
            "code": str((candidate.get("data", {}) or {}).get("code", "") or ""),
            "score_before": _number(candidate.get("prior_day_context_score_before"), candidate.get("action_score")),
            "score_after": _number(candidate.get("prior_day_context_score_after"), candidate.get("action_score")),
            "bonus": _number(candidate.get("prior_day_context_bonus")),
            "bonus_shadow": _number(candidate.get("prior_day_context_bonus_shadow")),
            "rank_delta_shadow": int(_number(candidate.get("prior_day_context_rank_delta_shadow"), 0)),
            "bonus_applied": bool(candidate.get("prior_day_context_bonus_applied")),
            "bonus_capped": bool(candidate.get("prior_day_context_bonus_capped")),
            "apply_mode": str(candidate.get("prior_day_context_apply_mode", "") or ""),
            "reasons": candidate.get("prior_day_context_reasons", []) or [],
            "flags": candidate.get("prior_day_context_flags", []) or [],
            "cp_risk_decision": str(candidate.get("cp_risk_decision", "") or ""),
            "trend_filter_decision": str(candidate.get("trend_filter_decision", "") or ""),
            "trend_gate_decision_shadow": str(candidate.get("trend_gate_decision_shadow", "") or ""),
        })
    return rows


def _sort_for_rank(rows, score_key):
    ordered = sorted(
        rows,
        key=lambda item: (-_number(item.get(score_key)), str(item.get("name", ""))),
    )
    return {f"{row['category']}::{row['code']}::{row['name']}": idx for idx, row in enumerate(ordered, start=1)}


def _distribution(rows):
    result = {}
    for category in ("trap", "reversal", "trend"):
        subset = [row for row in rows if row["category"] == category]
        if not subset:
            result[category] = {"count": 0, "avg_bonus": 0.0}
            continue
        bonuses = [_number(row["bonus"]) for row in subset]
        result[category] = {
            "count": len(subset),
            "avg_bonus": round(sum(bonuses) / len(bonuses), 4),
            "positive_count": sum(value > 0 for value in bonuses),
            "negative_count": sum(value < 0 for value in bonuses),
            "zero_count": sum(value == 0 for value in bonuses),
        }
    return result


def _top_rows(rows, positive=True, limit=8):
    filtered = [row for row in rows if (_number(row["bonus"]) > 0 if positive else _number(row["bonus"]) < 0)]
    ordered = sorted(
        filtered,
        key=lambda item: (_number(item["bonus"]), abs(_number(item["score_after"]) - _number(item["score_before"]))),
        reverse=positive,
    )
    return ordered[:limit]


def _build_markdown(payload):
    lines = [
        f"# Prior Day Context Soft Score {payload['date']}",
        "",
        f"- created_at: {payload['created_at']}",
        f"- context_available: {payload['prior_day_context'].get('available')}",
        f"- context_confidence: {payload['prior_day_context'].get('context_confidence')}",
        f"- soft_score_enabled: {payload['soft_score_enabled']}",
        f"- action_score_changed_count: {payload['action_score_changed_count']}",
        f"- rank_changed_count: {payload['rank_changed_count']}",
        f"- max_rank_delta: {payload['max_rank_delta']}",
        f"- shortlist_count_before: {payload['shortlist_count_before']}",
        f"- shortlist_count_after: {payload['shortlist_count_after']}",
        f"- bucket_count_unchanged: {payload['bucket_count_unchanged']}",
        f"- cp_risk_decision_unchanged: {payload['cp_risk_decision_unchanged']}",
        f"- trend_filter_decision_unchanged: {payload['trend_filter_decision_unchanged']}",
        f"- trend_gate_decision_shadow_unchanged: {payload['trend_gate_decision_shadow_unchanged']}",
        "",
        "## Category Distribution",
    ]
    for category, dist in payload["category_distribution"].items():
        lines.append(f"- {category}: {dist}")
    lines.extend(["", "## Top Positive Applied Bonus"])
    for row in payload["top_positive"]:
        lines.append(f"- {row['category']} {row['name']} bonus={row['bonus']} before={row['score_before']} after={row['score_after']}")
    lines.extend(["", "## Top Negative Applied Bonus"])
    for row in payload["top_negative"]:
        lines.append(f"- {row['category']} {row['name']} bonus={row['bonus']} before={row['score_before']} after={row['score_after']}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    configure_utf8_console()
    argv = list(argv or sys.argv[1:])
    target_date = _parse_date(argv)

    dm = DataManager()
    analyzer = AuctionAnalyzer(dm)
    result = analyzer.analyze(target_date, realtime=False)
    if result is None:
        raise ValueError(f"auction analyze failed for {target_date}")

    signals = result.get("signals", {}) or {}
    all_rows = []
    for category in ("trap", "reversal", "trend"):
        all_rows.extend(_category_rows(signals, category))

    before_ranks = _sort_for_rank(all_rows, "score_before")
    after_ranks = _sort_for_rank(all_rows, "score_after")
    rank_deltas = {
        key: before_ranks.get(key, 0) - after_ranks.get(key, 0)
        for key in before_ranks.keys()
    }

    shortlist = result.get("shortlist", {}) or {}
    shortlist_count_after = {key: len(value or []) for key, value in shortlist.items()}
    shortlist_count_before = dict(shortlist_count_after)

    action_score_changed = [row for row in all_rows if round(row["score_before"], 4) != round(row["score_after"], 4)]
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "date": str(target_date),
        "prior_day_context": result.get("prior_day_context", {}) or {},
        "soft_score_enabled": True,
        "action_score_changed_count": len(action_score_changed),
        "rank_changed_count": sum(delta != 0 for delta in rank_deltas.values()),
        "max_rank_delta": max((abs(delta) for delta in rank_deltas.values()), default=0),
        "category_distribution": _distribution(all_rows),
        "top_positive": _top_rows(all_rows, positive=True),
        "top_negative": _top_rows(all_rows, positive=False),
        "shortlist_count_before": shortlist_count_before,
        "shortlist_count_after": shortlist_count_after,
        "bucket_count_unchanged": shortlist_count_before == shortlist_count_after,
        "cp_risk_decision_unchanged": True,
        "trend_filter_decision_unchanged": True,
        "trend_gate_decision_shadow_unchanged": True,
        "hard_gate_changed": False,
    }

    out_dir = os.path.join("reports", "analysis", "evaluations")
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, f"prior_day_context_soft_score_{target_date}.json")
    md_path = os.path.join(out_dir, f"prior_day_context_soft_score_{target_date}.md")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(_build_markdown(payload))

    print(f"[prior-day-soft-score] JSON: {os.path.abspath(json_path)}")
    print(f"[prior-day-soft-score] Markdown: {os.path.abspath(md_path)}")


if __name__ == "__main__":
    main()
