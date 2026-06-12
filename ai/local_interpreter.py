# -*- coding: utf-8 -*-
"""Local AI-side interpreter fallback.

This module keeps the future LLM contract stable: it consumes structured facts
and returns a JSON-like dict with label, evidence and watch points. A real LLM
or RAG-backed interpreter can replace this implementation later.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _fmt_pct(value: float) -> str:
    return f"{value:+.2f}%"


def _has_negative(value: float, threshold: float = -0.3) -> bool:
    return value <= threshold


class LocalIndexInterpreter:
    """Evidence-first index trend interpreter."""

    @classmethod
    def interpret(cls, ctx: Dict[str, Any]) -> Dict[str, Any]:
        today = ctx["today"]
        pos = ctx["position"]
        dist = ctx.get("distances", {})

        close_pct = today["close_pct"]
        body_pct = today["body_pct"]
        auction_pct = today["auction_pct"]
        vol_ratio = today["vol_ratio"]
        upper_shadow = today["upper_shadow_pct"]
        lower_shadow = today["lower_shadow_pct"]
        pressure = pos.get("near_pressure", [])
        support = pos.get("near_support", [])
        below_ma5 = dist.get("distance_to_ma5_pct", 0) < 0 if "distance_to_ma5_pct" in dist else False

        evidence: List[str] = []
        watch_points: List[str] = []
        invalid_if: List[str] = []

        if close_pct < -0.5 and vol_ratio < 0.8 and (below_ma5 or pressure):
            label = "缩量承压回落"
            bias = "偏弱震荡"
            confidence = 0.82
            evidence.extend([
                f"当日收跌{_fmt_pct(close_pct)}，实体{_fmt_pct(body_pct)}",
                f"OAR/量比 {vol_ratio:.2f}，处于缩量环境",
            ])
            if pressure:
                evidence.append(f"收盘附近上方有 {','.join(pressure)} 压力")
            if below_ma5:
                evidence.append("收盘低于 MA5，短线未重新转强")
            watch_points.extend(["能否重新站回 MA5", "当日低点是否失守", "缩量是否转为放量修复"])
            invalid_if.extend(["放量收复 MA5/MA10", "权重板块带量上行"])
        elif close_pct < -0.5 and lower_shadow > upper_shadow and lower_shadow > 0.3:
            label = "下探后弱修复"
            bias = "震荡待确认"
            confidence = 0.72
            evidence.extend([
                f"当日收跌{_fmt_pct(close_pct)}，但下影线 {lower_shadow:.2f}% 大于上影线",
                f"竞价{_fmt_pct(auction_pct)}后盘中有承接",
            ])
            watch_points.extend(["次日能否延续修复", "低点附近是否继续承接"])
            invalid_if.append("再度放量跌破今日低点")
        elif close_pct > 0.5 and vol_ratio < 0.8:
            label = "缩量反弹"
            bias = "反弹待验"
            confidence = 0.76
            evidence.extend([
                f"当日收涨{_fmt_pct(close_pct)}",
                f"量比 {vol_ratio:.2f}，上涨缺少放量确认",
            ])
            watch_points.extend(["是否补量上攻", "是否站稳短期均线"])
            invalid_if.append("次日低开跌回反弹实体")
        elif close_pct > 0.5 and vol_ratio >= 1.2:
            label = "放量上攻"
            bias = "偏强"
            confidence = 0.78
            evidence.extend([
                f"当日收涨{_fmt_pct(close_pct)}",
                f"量比 {vol_ratio:.2f}，资金放量参与",
            ])
            watch_points.extend(["能否突破前高", "强势板块是否扩散"])
            invalid_if.append("放量后次日无法维持红盘")
        elif abs(close_pct) <= 0.5 and vol_ratio < 0.8:
            label = "缩量震荡"
            bias = "方向不明"
            confidence = 0.68
            evidence.extend([
                f"当日涨跌幅{_fmt_pct(close_pct)}，方向不强",
                f"量比 {vol_ratio:.2f}，资金观望",
            ])
            watch_points.extend(["箱体上下沿突破", "量能是否放大"])
            invalid_if.append("放量长阳或长阴打破震荡")
        else:
            label = "中性震荡"
            bias = "观察"
            confidence = 0.58
            evidence.extend([
                f"竞价{_fmt_pct(auction_pct)}，收盘{_fmt_pct(close_pct)}",
                f"实体{_fmt_pct(body_pct)}，量比 {vol_ratio:.2f}",
            ])
            watch_points.extend(["短期均线方向", "量能变化"])
            invalid_if.append("出现放量突破或破位")

        if support:
            watch_points.append(f"关注 {','.join(support)} 支撑")
        if pos.get("pos_5d", 50) > 80:
            evidence.append(f"5日位置 {pos['pos_5d']:.0f}%，短线处于相对高位")
        elif pos.get("pos_5d", 50) < 20:
            evidence.append(f"5日位置 {pos['pos_5d']:.0f}%，短线处于相对低位")

        report_text = f"{ctx['name']}处于{label}状态，{bias}；重点观察{watch_points[0]}。"
        return {
            "label": label,
            "bias": bias,
            "confidence": round(confidence, 2),
            "evidence": evidence[:4],
            "watch_points": watch_points[:3],
            "invalid_if": invalid_if[:2],
            "report_text": report_text,
        }
