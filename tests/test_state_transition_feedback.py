from reports.state_transition_feedback import build_transition_record


def test_transition_records_baseline_failure_and_cluster_repair():
    review = {
        "market_regime": {"label": "continuation"},
        "environment_gate": {"label": "continuation", "decision": "trend_enabled"},
    }
    decision = {
        "prior_trend_sample_count": 27, "prior_trend_success_rate": 40.74,
        "prior_trend_avg_body": -0.98, "path_available_count": 34,
        "broad_path_risk_ratio": 0.58, "one_way_selloff_ratio": 0.21,
        "cluster_top1_positive_share": 0.18, "cluster_top3_positive_share": 0.36,
        "feature_confidence": "high",
    }
    feedback = {
        "prior_trend_success_rate": 13.79, "prior_trend_avg_body": -2.28,
        "cluster_top1_positive_share": 0.4, "cluster_top3_positive_share": 0.8,
        "path_distribution": {"one_way_selloff": 16}, "market_regime": "hostile",
    }

    result = build_transition_record("20260706", "20260707", review, decision, feedback)

    assert result["feedback_label"] == "broad_continuation_failed"
    assert "baseline_trend_enabled_but_broad_trend_failed" in result["contradiction_labels"]
    assert "broad_failure_but_cluster_repair" in result["contradiction_labels"]


def test_sector_only_never_becomes_candidate_feedback():
    result = build_transition_record(
        "20260707", "20260708", {}, {}, None, validation_level="sector_only"
    )
    assert result["feedback_label"] == "sector_only_partial_confirmation"
    assert result["data_available"] is False
