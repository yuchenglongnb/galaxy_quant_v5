# -*- coding: utf-8 -*-

from ai.signal_interpreter import SignalInterpreter
from ai.signal_feature_builder import SignalFeatureBuilder
from ai.signal_labels import trap_subtype
from ai.validator import AIOutputValidator


def test_post_surge_weak_open_cp_does_not_render_high_open(monkeypatch):
    monkeypatch.setattr("config.settings.AIReportConfig.MODE", "assist")
    monkeypatch.setattr("ai.signal_interpreter.AIReportConfig.MODE", "assist")

    row = {
        "name": "半导体",
        "target_type": "ETF",
        "auction_pct": -0.17,
        "close_pct": -1.15,
        "body_pct": -0.98,
        "prev_pct": 7.26,
        "pos_5d": 88,
        "cp": 94.5,
    }

    commentary = SignalInterpreter.interpret(
        name="半导体",
        target_type="ETF",
        scenario="TRAP_MOMENTUM",
        category="trap",
        row=row,
        market_oar=1.01,
        fallback={"action": "高位逆势高开-0.17%"},
    )

    joined = " ".join(str(v) for v in commentary.values())
    assert "弱开兑现风险" in joined
    assert "高位逆势高开" not in joined


def test_validator_allows_negated_high_open_phrase():
    ctx = SignalFeatureBuilder.build(
        name="半导体",
        target_type="ETF",
        scenario="TRAP_MOMENTUM",
        category="trap",
        row={"auction_pct": -0.17, "prev_pct": 7.26, "body_pct": -0.98, "cp": 94.5},
        market_oar=1.01,
    )
    output = {
        "scenario_label": "强势后弱开兑现风险",
        "direction": "risk",
        "confidence": 0.8,
        "evidence": ["竞价-0.17%，不是高开，不能使用高开诱多模板"],
        "watch_points": ["次日能否修复"],
        "invalid_if": ["放量反包"],
        "report_text": "不是高开诱多，而是弱开兑现风险。",
    }

    ok, reasons = AIOutputValidator.validate(output, ctx)
    assert ok, reasons


def test_validator_rejects_text_confidence_without_crashing():
    ctx = SignalFeatureBuilder.build(
        name="半导体",
        target_type="ETF",
        scenario="TRAP_MOMENTUM",
        category="trap",
        row={"auction_pct": -0.17, "prev_pct": 7.26, "body_pct": -0.98, "cp": 94.5},
        market_oar=1.01,
    )
    output = {
        "scenario_label": "强势后弱开兑现风险",
        "direction": "risk",
        "confidence": "中低",
        "evidence": ["竞价-0.17%，不是高开"],
        "watch_points": ["次日能否修复"],
        "invalid_if": ["放量反包"],
        "report_text": "弱开兑现风险。",
    }

    ok, reasons = AIOutputValidator.validate(output, ctx)
    assert not ok
    assert "invalid confidence" in reasons


def test_trap_subtype_splits_high_open_and_post_surge_weak_open():
    assert trap_subtype(
        {"trigger_reason": "standard_high_open_cp", "auction_pct": 0.71, "prev_pct": 0.2}
    ) == "高开诱多"
    assert trap_subtype(
        {"trigger_reason": "post_surge_weak_open_cp", "auction_pct": -0.17, "prev_pct": 7.26}
    ) == "强势后弱开兑现"


def test_model_call_limit_falls_back_to_local(monkeypatch):
    calls = {"count": 0}

    def fake_complete_json(self, *, system_prompt, user_payload):
        calls["count"] += 1
        return None

    monkeypatch.setattr("ai.model_client.AIReportConfig.API_KEY", "test-key")
    monkeypatch.setattr("ai.model_client.AIReportConfig.BASE_URL", "https://example.test")
    monkeypatch.setattr("ai.model_client.AIReportConfig.MODEL", "test-model")
    monkeypatch.setattr("ai.signal_interpreter.AIReportConfig.MODE", "assist")
    monkeypatch.setattr("ai.signal_interpreter.AIReportConfig.MODEL_MAX_CALLS_PER_RUN", 1)
    monkeypatch.setattr("ai.signal_interpreter.ModelClient.complete_json", fake_complete_json)
    monkeypatch.setattr(SignalInterpreter, "_model_calls_this_run", 0)

    row = {
        "name": "半导体",
        "target_type": "ETF",
        "auction_pct": -0.17,
        "close_pct": -1.15,
        "body_pct": -0.98,
        "prev_pct": 7.26,
        "pos_5d": 88,
        "cp": 94.5,
    }

    for _ in range(2):
        SignalInterpreter.interpret(
            name="半导体",
            target_type="ETF",
            scenario="TRAP_MOMENTUM",
            category="trap",
            row=row,
            market_oar=1.01,
            fallback={},
        )

    assert calls["count"] == 1
