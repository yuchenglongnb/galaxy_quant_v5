# -*- coding: utf-8 -*-
"""Rule-based prior-day readthrough for next-day auction reports."""

from __future__ import annotations


class PriorDayReadthroughBuilder:
    """Translate prior-day context into a concise next-day reading."""

    @classmethod
    def build(cls, context: dict | None) -> dict:
        context = context or {}
        confidence = str(context.get("context_confidence", "low") or "low")
        if not context.get("available"):
            return cls._fallback("前一日语境数据不足，本次竞价报告仅基于当日信号。", confidence="low")
        if confidence == "low":
            return cls._fallback("前一日语境数据不足，本次竞价报告仅基于当日信号。", confidence="low")

        signal_metrics = context.get("signal_metrics", {}) or {}
        trap_rate = cls._metric_success_rate(signal_metrics, "trap")
        reversal_rate = cls._metric_success_rate(signal_metrics, "reversal")
        trend_rate = cls._metric_success_rate(signal_metrics, "trend")
        regime = str(context.get("market_regime", "") or "")
        leading_clusters = context.get("leading_clusters", []) or []

        headline = "昨日结构中性，今日优先结合竞价和主线簇判断。"
        bias = "neutral"
        focus_points = []
        risk_points = []

        if regime == "risk_off":
            headline = "昨日风险偏好偏低，今日先看修复能否集中，不先做趋势普开。"
            bias = "selective_reversal_first"
        elif regime == "strong_repair":
            headline = "昨日强修复成立，今日先看主线簇是否延续，再判断趋势是否扩散。"
            bias = "leading_cluster_continuation_first"
        elif regime == "repair":
            headline = "昨日修复已有迹象，今日重点看修复是否集中到主线簇。"
            bias = "theme_repair_focus"
        elif regime == "continuation":
            headline = "昨日延续结构未坏，今日重点区分主线延续和高位兑现。"
            bias = "trend_continuation_check"

        if trend_rate < 40:
            focus_points.append("趋势候选优先要求同主线和09:35确认。")
            risk_points.append("若主线簇不集中，趋势普开可信度下降。")
        elif trend_rate >= 55:
            focus_points.append("若昨日主线簇延续，趋势候选可优先观察强确认样本。")

        if reversal_rate > 60:
            focus_points.append("低开承接类机会优先观察。")
        elif reversal_rate < 35 and regime == "risk_off":
            risk_points.append("昨日反核胜率偏低，今日弱承接样本不宜机械放大。")

        if trap_rate > 60:
            risk_points.append("高 CP 票继续警惕兑现风险。")
        elif trap_rate < 20:
            focus_points.append("若今日仍是主线修复，高 CP 假阳性需要结合主线证据再判断。")

        if leading_clusters:
            focus_points.append("优先观察昨日主线簇是否延续或切换。")

        if confidence == "medium":
            risk_points.append("前一日语境仅作先验偏置，仍需结合今日竞价与盘中确认。")

        focus_points = cls._dedupe(focus_points)
        risk_points = cls._dedupe(risk_points)
        if not focus_points:
            focus_points = ["先看昨日主线簇是否延续，再结合今日竞价强弱判断。"]
        if not risk_points:
            risk_points = ["若今日竞价与昨日语境背离，应优先服从当日信号。"]

        return {
            "headline": headline,
            "bias": bias,
            "focus_points": focus_points,
            "risk_points": risk_points,
            "confidence": confidence,
        }

    @staticmethod
    def _metric_success_rate(metrics: dict, key: str) -> float | None:
        item = metrics.get(key, {}) or {}
        value = item.get("success_rate")
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _dedupe(items):
        seen = set()
        ordered = []
        for item in items or []:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            ordered.append(text)
        return ordered

    @classmethod
    def _fallback(cls, headline: str, confidence: str = "low") -> dict:
        return {
            "headline": headline,
            "bias": "neutral",
            "focus_points": [],
            "risk_points": [],
            "confidence": confidence,
        }
