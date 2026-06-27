from analyzers.evaluators.prior_day_context_soft_score import PriorDayContextSoftScoreEvaluator
from analyzers.signal_shortlist import SignalShortlistBuilder


def _candidate():
    return {
        "name": "样本",
        "action_score": 50.0,
        "action_score_breakdown": {"base_score": 50.0, "final_score": 50.0},
        "prior_day_context_bonus_shadow": -4.0,
        "prior_day_context_confidence": "medium",
        "cp_risk_decision": "hard_trap",
        "trend_filter_decision": "keep",
        "trend_gate_decision_shadow": "observe",
    }


def test_apply_to_score_false_does_not_change_action_score():
    PriorDayContextSoftScoreEvaluator._CONFIG_CACHE = {
        "enabled": True,
        "shadow_only": True,
        "apply_to_score": False,
        "max_abs_bonus": {"high": 6.0, "medium": 3.0, "low": 0.0},
    }
    candidate = _candidate()
    result = PriorDayContextSoftScoreEvaluator.apply(candidate, {"available": True, "context_confidence": "medium"})
    assert result["prior_day_context_bonus"] == 0.0
    assert result["prior_day_context_score_before"] == result["prior_day_context_score_after"] == 50.0


def test_apply_to_score_true_writes_real_bonus():
    PriorDayContextSoftScoreEvaluator._CONFIG_CACHE = {
        "enabled": True,
        "shadow_only": False,
        "apply_to_score": True,
        "disable_when_context_unavailable": True,
        "max_abs_bonus": {"high": 6.0, "medium": 3.0, "low": 0.0},
        "target_type_scope": {
            "enabled": True,
            "apply_score_target_types": ["stock"],
            "annotation_only_target_types": ["ETF", "index", "industry"],
            "unknown_target_type_mode": "annotation_only",
        },
    }
    candidate = _candidate()
    candidate["data"] = {"target_type": "stock"}
    result = PriorDayContextSoftScoreEvaluator.apply(candidate, {"available": True, "context_confidence": "medium"})
    assert result["prior_day_context_bonus"] == -3.0
    assert result["prior_day_context_bonus_applied"] is True
    assert result["prior_day_context_apply_mode"] == "soft_score"
    assert result["prior_day_context_scope_reason"] == "stock_target_type"
    assert result["prior_day_context_score_before"] == 50.0
    assert result["prior_day_context_score_after"] == 47.0


def test_low_confidence_real_bonus_is_zero():
    PriorDayContextSoftScoreEvaluator._CONFIG_CACHE = {
        "enabled": True,
        "shadow_only": False,
        "apply_to_score": True,
        "disable_when_context_unavailable": True,
        "max_abs_bonus": {"high": 6.0, "medium": 3.0, "low": 0.0},
        "target_type_scope": {
            "enabled": True,
            "apply_score_target_types": ["stock"],
            "annotation_only_target_types": ["ETF", "index", "industry"],
            "unknown_target_type_mode": "annotation_only",
        },
    }
    candidate = _candidate()
    candidate["data"] = {"target_type": "stock"}
    candidate["prior_day_context_confidence"] = "low"
    result = PriorDayContextSoftScoreEvaluator.apply(candidate, {"available": True, "context_confidence": "low"})
    assert result["prior_day_context_bonus"] == 0.0


def test_non_stock_candidate_keeps_annotation_only_bonus():
    PriorDayContextSoftScoreEvaluator._CONFIG_CACHE = {
        "enabled": True,
        "shadow_only": False,
        "apply_to_score": True,
        "disable_when_context_unavailable": True,
        "max_abs_bonus": {"high": 6.0, "medium": 3.0, "low": 0.0},
        "target_type_scope": {
            "enabled": True,
            "apply_score_target_types": ["stock"],
            "annotation_only_target_types": ["ETF", "index", "industry"],
            "unknown_target_type_mode": "annotation_only",
        },
    }
    candidate = _candidate()
    candidate["data"] = {"target_type": "ETF"}
    result = PriorDayContextSoftScoreEvaluator.apply(candidate, {"available": True, "context_confidence": "medium"})
    assert result["prior_day_context_bonus"] == 0.0
    assert result["prior_day_context_annotation_bonus"] == -3.0
    assert result["prior_day_context_bonus_applied"] is False
    assert result["prior_day_context_apply_mode"] == "annotation_only"
    assert result["prior_day_context_scope_reason"] == "non_stock_target_type"
    assert result["prior_day_context_score_before"] == result["prior_day_context_score_after"] == 50.0


def test_unknown_target_type_defaults_to_annotation_only():
    PriorDayContextSoftScoreEvaluator._CONFIG_CACHE = {
        "enabled": True,
        "shadow_only": False,
        "apply_to_score": True,
        "disable_when_context_unavailable": True,
        "max_abs_bonus": {"high": 6.0, "medium": 3.0, "low": 0.0},
        "target_type_scope": {
            "enabled": True,
            "apply_score_target_types": ["stock"],
            "annotation_only_target_types": ["ETF", "index", "industry"],
            "unknown_target_type_mode": "annotation_only",
        },
    }
    candidate = _candidate()
    candidate["data"] = {"target_type": "mystery"}
    result = PriorDayContextSoftScoreEvaluator.apply(candidate, {"available": True, "context_confidence": "medium"})
    assert result["prior_day_context_bonus"] == 0.0
    assert result["prior_day_context_apply_mode"] == "annotation_only"
    assert result["prior_day_context_scope_reason"] == "unknown_target_type"


def test_signal_shortlist_soft_score_changes_score_but_not_routing_flags():
    signals = {
        "trend": [
            {
                "name": "A",
                "action_score": 40.0,
                "action_score_breakdown": {"final_score": 40.0},
                "prior_day_context_bonus_shadow": -4.0,
                "prior_day_context_confidence": "medium",
                "cp_risk_decision": "hard_trap",
                "trend_filter_decision": "keep",
                "trend_gate_decision_shadow": "observe",
                "data": {"target_type": "stock"},
            }
        ]
    }
    shortlist = {"trend": [signals["trend"][0]], "reversal_high_confidence": [], "reversal": [], "reversal_observation": [], "trap": [], "trap_observation": [], "trap_exempted": [], "trend_observation": []}
    prior_day_context = {"available": True, "context_confidence": "medium"}
    PriorDayContextSoftScoreEvaluator._CONFIG_CACHE = {
        "enabled": True,
        "shadow_only": False,
        "apply_to_score": True,
        "disable_when_context_unavailable": True,
        "max_abs_bonus": {"high": 6.0, "medium": 3.0, "low": 0.0},
        "target_type_scope": {
            "enabled": True,
            "apply_score_target_types": ["stock"],
            "annotation_only_target_types": ["ETF", "index", "industry"],
            "unknown_target_type_mode": "annotation_only",
        },
    }
    SignalShortlistBuilder._apply_prior_day_context_soft_score(signals, shortlist, prior_day_context)
    candidate = signals["trend"][0]
    assert candidate["action_score"] == 37.0
    assert candidate["action_score_breakdown"]["prior_day_context_bonus"] == -3.0
    assert candidate["cp_risk_decision"] == "hard_trap"
    assert candidate["trend_filter_decision"] == "keep"
    assert candidate["trend_gate_decision_shadow"] == "observe"


def test_non_stock_signal_shortlist_keeps_action_score_unchanged():
    signals = {
        "reversal": [
            {
                "name": "ETF-A",
                "action_score": 40.0,
                "action_score_breakdown": {"final_score": 40.0},
                "prior_day_context_bonus_shadow": 3.0,
                "prior_day_context_confidence": "medium",
                "data": {"target_type": "ETF"},
            }
        ]
    }
    shortlist = {"trend": [], "reversal_high_confidence": [], "reversal": signals["reversal"], "reversal_observation": [], "trap": [], "trap_observation": [], "trap_exempted": [], "trend_observation": []}
    prior_day_context = {"available": True, "context_confidence": "medium"}
    PriorDayContextSoftScoreEvaluator._CONFIG_CACHE = {
        "enabled": True,
        "shadow_only": False,
        "apply_to_score": True,
        "disable_when_context_unavailable": True,
        "max_abs_bonus": {"high": 6.0, "medium": 3.0, "low": 0.0},
        "target_type_scope": {
            "enabled": True,
            "apply_score_target_types": ["stock"],
            "annotation_only_target_types": ["ETF", "index", "industry"],
            "unknown_target_type_mode": "annotation_only",
        },
    }
    SignalShortlistBuilder._apply_prior_day_context_soft_score(signals, shortlist, prior_day_context)
    candidate = signals["reversal"][0]
    assert candidate["action_score"] == 40.0
    assert candidate["action_score_breakdown"]["prior_day_context_bonus"] == 0.0
    assert candidate["prior_day_context_annotation_bonus"] == 3.0
    assert candidate["prior_day_context_apply_mode"] == "annotation_only"
