# -*- coding: utf-8 -*-
"""Build structured facts for AI-side auction signal interpretation."""

from __future__ import annotations

from typing import Any, Dict


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _round(value: Any, digits: int = 2) -> float:
    return round(_safe_float(value), digits)


class SignalFeatureBuilder:
    """Create evidence-ready facts from a signal row."""

    @classmethod
    def build(
        cls,
        *,
        name: str,
        target_type: str,
        scenario: str,
        category: str,
        row: Dict[str, Any],
        market_oar: float,
    ) -> Dict[str, Any]:
        cp = row.get("cp")
        sa = row.get("sa")
        facts = {
            "amt_rank": int(row.get("amt_rank", 99) or 99),
            "pos_5d": _round(row.get("pos_5d", 50)),
            "auction_pct": _round(row.get("auction_pct", 0)),
            "close_pct": _round(row.get("close_pct", row.get("pct", 0))),
            "body_pct": _round(row.get("body_pct", 0)),
            "prev_pct": _round(row.get("prev_pct", 0)),
            "prev_body_pct": _round(row.get("prev_body_pct", 0)),
            "prev_vol_ratio": _round(row.get("prev_vol_ratio", 1.0)),
            "vol_ratio": _round(row.get("vol_ratio", 1.0)),
            "auction_amt": _round(row.get("auction_amt", 0)),
            "cp": _round(cp) if cp is not None else None,
            "sa": _round(sa) if sa is not None else None,
            "market_oar": _round(market_oar),
        }

        trigger_reason = cls._trigger_reason(scenario, facts)
        return {
            "task": "explain_auction_signal",
            "target": {"name": name, "type": target_type},
            "hard_rule": {
                "scenario": scenario,
                "category": category,
                "trigger_reason": trigger_reason,
            },
            "facts": facts,
        }

    @staticmethod
    def _trigger_reason(scenario: str, facts: Dict[str, Any]) -> str:
        auction_pct = facts["auction_pct"]
        prev_pct = facts["prev_pct"]
        if scenario.startswith("TRAP"):
            if auction_pct > 0.3:
                return "standard_high_open_cp"
            if prev_pct > 3 and auction_pct > -0.3:
                return "post_surge_weak_open_cp"
            if prev_pct > 2 and auction_pct >= 0:
                return "post_surge_flat_or_better_cp"
            return "cp_threshold"
        if scenario.startswith("REVERSAL"):
            return "sa_candidate_threshold"
        if scenario.startswith("TREND"):
            return "prior_trend_auction_candidate"
        return "unknown"
