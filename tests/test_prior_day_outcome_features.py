import pandas as pd

from analyzers.context.prior_day_outcome_features import PriorDayOutcomeFeatureBuilder


def test_outcome_features_compute_body_paths_and_cluster_dedupe():
    detail = pd.DataFrame([
        {"signal_category": "trend", "validation_success": True, "body_pct": 2.0,
         "signal_path_type": "close_near_high", "target_type": "stock", "code": "A",
         "name": "a", "theme_cluster": "semi"},
        {"signal_category": "reversal", "validation_success": True, "body_pct": 1.0,
         "signal_path_type": "rush_up_fade", "target_type": "stock", "code": "A",
         "name": "a", "theme_cluster": "semi"},
        {"signal_category": "trend", "validation_success": False, "body_pct": -2.0,
         "signal_path_type": "one_way_selloff", "target_type": "stock", "code": "B",
         "name": "b", "theme_cluster": "robot"},
        {"signal_category": "trap", "validation_success": True, "body_pct": -1.0,
         "signal_path_type": "high_open_trap", "target_type": "ETF", "code": "C",
         "name": "c", "theme_cluster": "fiber"},
    ])

    result = PriorDayOutcomeFeatureBuilder.build(detail)

    assert result["prior_trend_sample_count"] == 2
    assert result["prior_trend_avg_body"] == 0.0
    assert result["one_way_selloff_count"] == 1
    assert result["fade_path_count"] == 2
    assert result["broad_path_risk_count"] == 3
    assert result["cluster_positive_denominator"] == 1
    assert result["cluster_top1_positive_share"] == 1.0


def test_price_turnover_classification():
    classify = PriorDayOutcomeFeatureBuilder.classify_price_turnover
    assert classify(3, 20) == "price_turnover_confirmed"
    assert classify(-3, 20) == "high_turnover_without_price_confirmation"
    assert classify(3, -20) == "price_without_turnover_confirmation"
    assert classify(-3, -20) == "weak_or_cooling"
    assert classify(None, 20) == "insufficient_sector_evidence"
