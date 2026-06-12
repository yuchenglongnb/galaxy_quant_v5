# -*- coding: utf-8 -*-
"""Label helpers for auction signal rendering."""

from __future__ import annotations

from typing import Any, Dict


def trap_subtype(data: Dict[str, Any]) -> str:
    """Return the human-readable subtype for a CP risk signal."""
    auction_pct = data.get("auction_pct", 0) or 0
    prev_pct = data.get("prev_pct", 0) or 0
    trigger_reason = data.get("trigger_reason", "")
    if trigger_reason == "overheated_acceleration_risk":
        return "高位加速兑现风险"
    if trigger_reason == "standard_high_open_cp" or auction_pct > 0.3:
        return "高开诱多"
    if trigger_reason in {"post_surge_weak_open_cp", "post_surge_flat_or_better_cp"} or prev_pct > 3:
        if auction_pct <= 0:
            return "强势后弱开兑现"
        return "强势后平/高开兑现"
    return "拥挤兑现风险"
