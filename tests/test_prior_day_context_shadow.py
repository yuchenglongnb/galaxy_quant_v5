from analyzers.evaluators.prior_day_context_shadow import PriorDayContextShadowEvaluator
from analyzers.signal_shortlist import SignalShortlistBuilder


def _candidate(category="trend", leading_name="", leading_status="missing_ifind_overlay", cp_decision="hard_trap"):
    return {
        "signal_category": category,
        "name": "样本",
        "action_score": 50.0,
        "leading_cluster_name": leading_name,
        "leading_cluster_status": leading_status,
        "cp_risk_decision": cp_decision,
        "data": {
            "group": leading_name,
            "theme_cluster": leading_name,
            "target_type": "stock",
            "code": "000001.SZ",
        },
    }


def test_low_confidence_bonus_is_zero():
    candidate = _candidate()
    context = {"available": True, "context_confidence": "low", "bias": {"trend_bias": "negative"}, "leading_clusters": []}
    result = PriorDayContextShadowEvaluator.evaluate(candidate, context)
    assert result["prior_day_context_bonus_shadow"] == 0.0
    assert "low_confidence_zero_bonus" in result["prior_day_context_reasons"]


def test_medium_confidence_cap_is_enforced():
    candidate = _candidate(category="reversal")
    context = {
        "available": True,
        "context_confidence": "medium",
        "market_regime": "risk_off",
        "bias": {"reversal_bias": "positive"},
        "leading_clusters": [],
    }
    result = PriorDayContextShadowEvaluator.evaluate(candidate, context)
    assert abs(result["prior_day_context_bonus_shadow"]) <= 4.0


def test_high_confidence_trend_negative_non_cluster_gets_penalty():
    candidate = _candidate(category="trend", leading_name="航运", leading_status="partial")
    context = {
        "available": True,
        "context_confidence": "high",
        "bias": {"trend_bias": "negative"},
        "leading_clusters": ["数字芯片设计"],
    }
    result = PriorDayContextShadowEvaluator.evaluate(candidate, context)
    assert result["prior_day_context_bonus_shadow"] < 0
    assert "prev_day_trend_bias_negative" in result["prior_day_context_reasons"]
    assert "not_in_prev_leading_cluster" in result["prior_day_context_reasons"]


def test_prev_leading_cluster_continuation_gets_positive_bonus():
    candidate = _candidate(category="trend", leading_name="数字芯片设计", leading_status="active")
    context = {
        "available": True,
        "context_confidence": "high",
        "bias": {"trend_bias": "negative"},
        "leading_clusters": ["芯片概念"],
    }
    result = PriorDayContextShadowEvaluator.evaluate(candidate, context)
    assert result["prior_day_context_bonus_shadow"] > 0
    assert "matched_prev_leading_cluster" in result["prior_day_context_reasons"]


def test_cp_exempt_does_not_get_extra_cp_bonus():
    candidate = _candidate(category="trap", leading_name="数字芯片设计", leading_status="active", cp_decision="leading_cluster_exempt")
    context = {
        "available": True,
        "context_confidence": "high",
        "bias": {"cp_bias": "positive"},
        "leading_clusters": ["数字芯片设计"],
    }
    result = PriorDayContextShadowEvaluator.evaluate(candidate, context)
    assert result["prior_day_context_bonus_shadow"] == 0.0
    assert "cp_leading_cluster_exempt_skip" in result["prior_day_context_reasons"]


def test_signal_shortlist_shadow_does_not_change_action_score_or_order():
    signals = {
        "trend": [
            {"name": "A", "action_score": 40.0, "data": {"target_type": "stock", "group": "数字芯片设计", "code": "000001.SZ"}},
            {"name": "B", "action_score": 30.0, "data": {"target_type": "stock", "group": "航运", "code": "000002.SZ"}},
        ]
    }
    for item in signals["trend"]:
        item["signal_category"] = "trend"
    context = {
        "available": True,
        "context_confidence": "high",
        "bias": {"trend_bias": "negative"},
        "leading_clusters": ["芯片概念"],
    }
    before_scores = [item["action_score"] for item in signals["trend"]]
    before_order = [item["name"] for item in signals["trend"]]
    SignalShortlistBuilder._apply_prior_day_context_shadow(signals, context)
    after_scores = [item["action_score"] for item in signals["trend"]]
    after_order = [item["name"] for item in signals["trend"]]
    assert before_scores == after_scores
    assert before_order == after_order
    assert "prior_day_context_bonus_shadow" in signals["trend"][0]
