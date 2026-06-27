import pandas as pd

from scripts.evaluate_prior_day_context_effect import (
    _normalize_target_type,
    _to_bool,
    build_day_payload,
    build_summary_payload,
)


def _result():
    return {
        "date": "20260624",
        "prior_day_context": {
            "available": True,
            "context_confidence": "medium",
            "prev_trade_date": "20260623",
            "market_regime": "risk_off",
            "environment_decision": "selective_reversal_only",
            "leading_clusters": ["数字芯片设计"],
        },
        "signals": {
            "trap": [
                {
                    "name": "医疗",
                    "data": {"code": "512170.SH", "target_type": "ETF"},
                    "prior_day_context_bonus": 0.0,
                    "prior_day_context_annotation_bonus": 3.0,
                    "prior_day_context_bonus_applied": False,
                    "prior_day_context_score_before": 80.0,
                    "prior_day_context_score_after": 80.0,
                    "prior_day_context_apply_mode": "annotation_only",
                    "cp_risk_decision": "hard_trap",
                }
            ],
            "reversal": [
                {
                    "name": "云南锗业",
                    "data": {"code": "002428.SZ", "target_type": "个股"},
                    "prior_day_context_bonus": 3.0,
                    "prior_day_context_bonus_applied": True,
                    "prior_day_context_score_before": 100.0,
                    "prior_day_context_score_after": 103.0,
                }
            ],
            "trend": [
                {
                    "name": "同花顺",
                    "data": {"code": "300033.SZ", "target_type": "个股"},
                    "prior_day_context_bonus": -3.0,
                    "prior_day_context_bonus_applied": True,
                    "prior_day_context_score_before": 70.0,
                    "prior_day_context_score_after": 67.0,
                    "trend_filter_decision": "keep",
                    "trend_gate_decision_shadow": "observe",
                }
            ],
        },
    }


def _detail_df():
    return pd.DataFrame(
        [
            {"signal_category": "trap", "name": "医疗", "code": "512170.SH", "target_type": "ETF", "body_pct": 1.0, "validation_success": False},
            {"signal_category": "reversal", "name": "云南锗业", "code": "002428.SZ", "target_type": "个股", "body_pct": 12.538, "validation_success": True},
            {"signal_category": "trend", "name": "同花顺", "code": "300033.SZ", "target_type": "个股", "body_pct": -2.4218, "validation_success": False},
        ]
    )


def test_normalize_target_type():
    assert _normalize_target_type("个股") == "stock"
    assert _normalize_target_type("ETF") == "ETF"
    assert _normalize_target_type("指数") == "index"
    assert _normalize_target_type("行业") == "industry"


def test_to_bool_keeps_false_values():
    assert _to_bool(False) is False
    assert _to_bool(True) is True
    assert _to_bool("false") is False


def test_build_day_payload_structure_and_warning():
    payload = build_day_payload("20260624", _result(), _detail_df())
    assert payload["context_available"] is True
    assert payload["candidate_total"] == 3
    assert payload["positive_bonus_count"] == 1
    assert payload["negative_bonus_count"] == 1
    assert payload["zero_bonus_count"] == 1
    assert payload["bucket_changed_count"] == 0
    assert payload["target_type_scope_enabled"] is True
    assert payload["stock_true_bonus_count"] == 2
    assert payload["non_stock_true_bonus_count"] == 0
    assert payload["non_stock_annotation_bonus_count"] == 1
    assert "non_stock_prior_day_bonus_present" not in payload["warnings"]
    assert payload["category_distribution"]["trend"]["candidate_count"] == 1
    assert payload["target_type_distribution"]["ETF"]["candidate_count"] == 1
    assert payload["category_distribution"]["trap"]["success_rate"] == 0.0
    assert payload["category_distribution"]["trend"]["success_rate"] == 0.0


def test_build_day_payload_marks_performance_unavailable_when_detail_missing():
    payload = build_day_payload("20260624", _result(), pd.DataFrame())
    assert "post_close_performance_unavailable" in payload["warnings"]
    assert payload["positive_bonus_performance"]["performance_available"] is False


def test_build_summary_payload_structure():
    payload = build_day_payload("20260624", _result(), _detail_df())
    summary = build_summary_payload([payload])
    assert summary["evaluated_dates"] == ["20260624"]
    assert summary["total_positive_bonus_count"] == 1
    assert summary["overall_bucket_changed_count"] == 0
    assert summary["non_stock_true_bonus_count"] == 0
    assert summary["stock_true_bonus_count"] == 2
    assert summary["conclusion"] == "keep_soft_score"


def test_build_day_payload_warns_when_non_stock_true_bonus_present():
    result = _result()
    result["signals"]["trap"][0]["prior_day_context_bonus"] = 3.0
    payload = build_day_payload("20260624", result, _detail_df())
    assert payload["non_stock_true_bonus_count"] == 1
    assert "non_stock_prior_day_bonus_present" in payload["warnings"]
