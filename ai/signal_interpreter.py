# -*- coding: utf-8 -*-
"""AI-assisted auction signal interpretation with local fallback."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ai.model_client import ModelClient
from ai.signal_feature_builder import SignalFeatureBuilder
from ai.trace_logger import AITraceLogger
from ai.validator import AIOutputValidator
from config.settings import AIReportConfig


SYSTEM_PROMPT = """你是A股竞价复盘报告解释器。
只根据输入 JSON 的 facts 解释信号，不得编造行情数据，不得改写 CP/SA 分数。
输出必须是 JSON 对象，字段包括:
scenario_label, direction, confidence, evidence, watch_points, invalid_if, report_text。
所有文字字段必须使用简体中文。
confidence 必须是 0 到 1 之间的数字，例如 0.72；禁止输出“高/中/低/中低”等文字。
direction 只能是 risk、opportunity、trend、observe 之一。
evidence、watch_points、invalid_if 必须是字符串数组。
如果 auction_pct<=0，不得把今日行为描述为高开。
如果 body_pct<=0，不得写日内转强确认。
如果硬规则标签和事实冲突，要指出冲突并给出更准确的语义标签。
"""


class SignalInterpreter:
    """Interpret a deterministic signal into evidence-backed report text."""

    _model_calls_this_run = 0

    @classmethod
    def interpret(
        cls,
        *,
        name: str,
        target_type: str,
        scenario: str,
        category: str,
        row: Dict[str, Any],
        market_oar: float,
        fallback: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        mode = AIReportConfig.MODE
        fallback = fallback or {}
        ctx = SignalFeatureBuilder.build(
            name=name,
            target_type=target_type,
            scenario=scenario,
            category=category,
            row=row,
            market_oar=market_oar,
        )

        if mode == "off":
            return fallback

        source = "local"
        output = cls._local_interpret(ctx)
        model_output = None
        if cls._should_call_model():
            cls._model_calls_this_run += 1
            model_output = ModelClient().complete_json(system_prompt=SYSTEM_PROMPT, user_payload=ctx)
        elif ModelClient().enabled():
            source = "local_model_call_limit"
        if model_output:
            source = "model"
            output = model_output

        ok, reasons = AIOutputValidator.validate(output, ctx)
        if not ok and source == "model":
            source = "local_after_model_invalid"
            output = cls._local_interpret(ctx)
            ok, reasons = AIOutputValidator.validate(output, ctx)

        rendered = cls._to_commentary(output) if ok and mode in {"assist", "replace"} else fallback
        if not rendered:
            rendered = fallback

        AITraceLogger.log(
            {
                "mode": mode,
                "source": source,
                "ok": ok,
                "reasons": reasons,
                "ctx": ctx,
                "output": output,
                "rendered": rendered,
            }
        )
        if mode == "shadow":
            return fallback
        return rendered

    @classmethod
    def _should_call_model(cls) -> bool:
        if not ModelClient().enabled():
            return False
        limit = AIReportConfig.MODEL_MAX_CALLS_PER_RUN
        if limit < 0:
            return True
        return cls._model_calls_this_run < limit

    @classmethod
    def _local_interpret(cls, ctx: Dict[str, Any]) -> Dict[str, Any]:
        facts = ctx["facts"]
        hard = ctx["hard_rule"]
        scenario = hard["scenario"]
        trigger = hard["trigger_reason"]
        auction = facts["auction_pct"]
        close = facts["close_pct"]
        body = facts["body_pct"]
        prev = facts["prev_pct"]
        pos = facts["pos_5d"]
        cp = facts.get("cp")
        sa = facts.get("sa")

        if scenario.startswith("TRAP"):
            if trigger == "post_surge_weak_open_cp" and auction <= 0:
                return {
                    "scenario_label": "强势后弱开兑现风险",
                    "direction": "risk",
                    "confidence": 0.82,
                    "evidence": [
                        f"T-1上涨{prev:+.2f}%，短线获利盘较厚",
                        f"竞价{auction:+.2f}%，不是高开，不能使用高开诱多模板",
                        f"收盘{close:+.2f}%，实体{body:+.2f}%，弱开后修复不足",
                    ],
                    "watch_points": ["次日能否收回今日实体", "是否继续跌破短期区间", "核心ETF是否止跌"],
                    "invalid_if": ["次日放量反包今日实体", "重新站回短期均线"],
                    "report_text": "不是高开诱多，而是昨日大涨后的弱开兑现风险；竞价小幅低开后未能有效修复，获利盘压力仍需消化。",
                }
            if auction > 0:
                return {
                    "scenario_label": "高位高开兑现风险",
                    "direction": "risk",
                    "confidence": 0.78,
                    "evidence": [
                        f"CP={cp}，拥挤度较高",
                        f"竞价{auction:+.2f}%，存在高开消耗动能",
                        f"5日位置{pos:.0f}%，短线位置偏高",
                    ],
                    "watch_points": ["高开后能否继续放量", "是否回落跌破开盘价"],
                    "invalid_if": ["放量长阳突破前高"],
                    "report_text": "短线位置和CP偏高，高开后更需要验证承接；若无法放量延续，容易成为兑现窗口。",
                }
            return {
                "scenario_label": "拥挤兑现风险",
                "direction": "risk",
                "confidence": 0.68,
                "evidence": [f"CP={cp} 达到风险阈值", f"竞价{auction:+.2f}%", f"实体{body:+.2f}%"],
                "watch_points": ["开盘价附近承接", "是否继续缩量"],
                "invalid_if": ["放量修复并收回实体"],
                "report_text": "CP达到风险阈值，但不是标准高开场景，按拥挤兑现风险观察。",
            }

        if scenario.startswith("REVERSAL"):
            if body > 2:
                label = "低开强修复"
                text = "低开后实体明显修复，说明有资金承接，但仍需看次日延续。"
            else:
                label = "低开承接待验证"
                text = "SA偏高但实体修复不足，只能视为承接待验证。"
            return {
                "scenario_label": label,
                "direction": "opportunity",
                "confidence": 0.76 if body > 2 else 0.62,
                "evidence": [f"SA={sa}", f"竞价{auction:+.2f}%", f"实体{body:+.2f}%"],
                "watch_points": ["次日是否延续修复", "低点是否继续守住"],
                "invalid_if": ["跌破今日低点", "放量下杀"],
                "report_text": text,
            }

        return {
            "scenario_label": "趋势延续",
            "direction": "trend",
            "confidence": 0.7,
            "evidence": [f"实体{body:+.2f}%", f"收盘{close:+.2f}%"],
            "watch_points": ["趋势是否放量扩散", "回踩是否守住开盘价"],
            "invalid_if": ["次日跌回今日实体"],
            "report_text": "日内实体转强，属于趋势延续信号，但仍需观察量能配合。",
        }

    @staticmethod
    def _to_commentary(output: Dict[str, Any]) -> Dict[str, str]:
        evidence = output.get("evidence") or []
        watch = output.get("watch_points") or []
        invalid = output.get("invalid_if") or []
        return {
            "context": output.get("scenario_label", ""),
            "action": "；".join(str(x) for x in evidence[:2]),
            "risk": output.get("report_text", ""),
            "advice": "观察: " + "；".join(str(x) for x in watch[:2]) if watch else "",
            "ai_confidence": output.get("confidence", 0),
            "invalid_if": "；".join(str(x) for x in invalid[:2]),
        }
