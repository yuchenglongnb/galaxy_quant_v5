# -*- coding: utf-8 -*-
"""Validate AI report text against deterministic market facts."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


class AIOutputValidator:
    """Guardrails for AI-generated signal interpretation."""

    HIGH_OPEN_WORDS = ("高开", "逆势高开")
    LOW_OPEN_WORDS = ("低开", "弱开")
    REVERSAL_WORDS = ("反转", "修复", "转强", "走强")

    @classmethod
    def validate(cls, output: Dict[str, Any], ctx: Dict[str, Any]) -> Tuple[bool, List[str]]:
        reasons: List[str] = []
        facts = ctx.get("facts", {})
        text = cls._joined_text(output)
        high_open_check_text = (
            text.replace("不是高开", "")
            .replace("不能使用高开", "")
            .replace("不应使用高开", "")
        )

        auction_pct = float(facts.get("auction_pct", 0) or 0)
        body_pct = float(facts.get("body_pct", 0) or 0)
        close_pct = float(facts.get("close_pct", 0) or 0)
        cp = facts.get("cp")
        sa = facts.get("sa")

        if auction_pct <= 0 and any(word in high_open_check_text for word in cls.HIGH_OPEN_WORDS):
            reasons.append("auction_pct<=0 but text says high open")
        if auction_pct >= 0 and "恐慌低开" in text:
            reasons.append("auction_pct>=0 but text says panic low open")
        if body_pct <= 0 and any(word in text for word in ("日内转强确认", "强势反转确认")):
            reasons.append("body_pct<=0 but text says confirmed intraday strength")
        if close_pct < auction_pct and "低开高走" in text:
            reasons.append("close_pct<auction_pct but text says low-open high-close")
        if cp is None and "CP" in text and "CP值" in text:
            reasons.append("text references CP while cp is null")
        if sa is None and "SA" in text and "SA值" in text:
            reasons.append("text references SA while sa is null")

        evidence = output.get("evidence", [])
        if not isinstance(evidence, list) or not evidence:
            reasons.append("missing evidence list")

        confidence = output.get("confidence", 0)
        confidence_value = 0.0
        try:
            confidence_value = float(confidence)
        except Exception:
            reasons.append("invalid confidence")
        if not (0 <= confidence_value <= 1):
            reasons.append("confidence out of range")

        required = ["scenario_label", "direction", "report_text"]
        for key in required:
            if not output.get(key):
                reasons.append(f"missing {key}")

        return not reasons, reasons

    @staticmethod
    def _joined_text(output: Dict[str, Any]) -> str:
        parts = []
        for key in ("scenario_label", "direction", "report_text", "context", "action", "risk", "advice"):
            value = output.get(key)
            if value:
                parts.append(str(value))
        for key in ("evidence", "watch_points", "invalid_if"):
            value = output.get(key)
            if isinstance(value, list):
                parts.extend(str(x) for x in value)
        return " ".join(parts)
