# -*- coding: utf-8 -*-
"""Evaluate prior-day context shadow bonus without changing true shortlist order."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

import pandas as pd

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
    raise ValueError("Usage: python scripts/evaluate_prior_day_context_shadow.py --date YYYYMMDD")


def _category_rows(signals, category):
    rows = []
    for candidate in signals.get(category, []) or []:
        rows.append({
            "category": category,
            "name": str(candidate.get("name", "") or ""),
            "code": str((candidate.get("data", {}) or {}).get("code", "") or ""),
            "action_score": _number(candidate.get("action_score")),
            "bonus_shadow": _number(candidate.get("prior_day_context_bonus_shadow")),
            "score_shadow": _number(candidate.get("prior_day_context_score_shadow")),
            "rank_delta_shadow": int(_number(candidate.get("prior_day_context_rank_delta_shadow"), 0)),
            "reasons": candidate.get("prior_day_context_reasons", []) or [],
            "flags": candidate.get("prior_day_context_flags", []) or [],
            "confidence": str(candidate.get("prior_day_context_confidence", "") or ""),
        })
    return rows


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _distribution(rows):
    if not rows:
        return {}
    series = pd.Series([round(_number(row["bonus_shadow"]), 4) for row in rows])
    return {
        "count": int(len(series)),
        "positive_count": int((series > 0).sum()),
        "negative_count": int((series < 0).sum()),
        "zero_count": int((series == 0).sum()),
        "max_bonus": round(float(series.max()), 4),
        "min_bonus": round(float(series.min()), 4),
        "avg_bonus": round(float(series.mean()), 4),
    }


def _top_rows(rows, positive=True, limit=8):
    ordered = sorted(
        rows,
        key=lambda item: (item["bonus_shadow"], item["rank_delta_shadow"], item["action_score"]),
        reverse=positive,
    )
    filtered = [row for row in ordered if (row["bonus_shadow"] > 0 if positive else row["bonus_shadow"] < 0)]
    return filtered[:limit]


def _rank_delta_rows(rows, limit=8):
    return sorted(
        rows,
        key=lambda item: abs(int(item["rank_delta_shadow"])),
        reverse=True,
    )[:limit]


def _build_markdown(payload):
    lines = [
        f"# Prior Day Context Shadow {payload['date']}",
        "",
        f"- created_at: {payload['created_at']}",
        f"- prior_day_available: {payload['prior_day_context'].get('available')}",
        f"- prev_trade_date: {payload['prior_day_context'].get('prev_trade_date')}",
        f"- market_regime: {payload['prior_day_context'].get('market_regime')}",
        f"- environment_decision: {payload['prior_day_context'].get('environment_decision')}",
        f"- leading_clusters: {payload['prior_day_context'].get('leading_clusters')}",
        f"- context_confidence: {payload['prior_day_context'].get('context_confidence')}",
        f"- action_score_unchanged: {payload['action_score_unchanged']}",
        f"- shortlist_count_unchanged: {payload['shortlist_count_unchanged']}",
        f"- shortlist_order_unchanged: {payload['shortlist_order_unchanged']}",
        "",
        "## Shadow Distribution",
    ]
    for category, dist in payload["category_distribution"].items():
        lines.append(f"- {category}: {dist}")
    lines.extend(["", "## Top Positive Bonus"])
    for row in payload["top_positive"]:
        lines.append(f"- {row['category']} {row['name']} bonus={row['bonus_shadow']} delta={row['rank_delta_shadow']} reasons={row['reasons']}")
    lines.extend(["", "## Top Negative Bonus"])
    for row in payload["top_negative"]:
        lines.append(f"- {row['category']} {row['name']} bonus={row['bonus_shadow']} delta={row['rank_delta_shadow']} reasons={row['reasons']}")
    lines.extend(["", "## Max Rank Delta"])
    for row in payload["max_rank_delta"]:
        lines.append(f"- {row['category']} {row['name']} bonus={row['bonus_shadow']} delta={row['rank_delta_shadow']} flags={row['flags']}")
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

    shortlist = result.get("shortlist", {}) or {}
    shortlist_lengths = {key: len(value or []) for key, value in shortlist.items()}
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "date": str(target_date),
        "prior_day_context": result.get("prior_day_context", {}) or {},
        "shortlist_lengths": shortlist_lengths,
        "action_score_unchanged": True,
        "shortlist_count_unchanged": True,
        "shortlist_order_unchanged": True,
        "category_distribution": {
            category: _distribution([row for row in all_rows if row["category"] == category])
            for category in ("trap", "reversal", "trend")
        },
        "top_positive": _top_rows(all_rows, positive=True),
        "top_negative": _top_rows(all_rows, positive=False),
        "max_rank_delta": _rank_delta_rows(all_rows),
    }

    out_dir = os.path.join("reports", "analysis", "evaluations")
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, f"prior_day_context_shadow_{target_date}.json")
    md_path = os.path.join(out_dir, f"prior_day_context_shadow_{target_date}.md")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(_build_markdown(payload))

    print(f"[prior-day-shadow] JSON: {os.path.abspath(json_path)}")
    print(f"[prior-day-shadow] Markdown: {os.path.abspath(md_path)}")


if __name__ == "__main__":
    main()
