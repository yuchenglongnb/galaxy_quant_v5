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
        "cluster_positive_denominator": 11, "cluster_concentration_label": "dispersed",
        "feature_confidence": "high",
    }
    feedback = {
        "prior_trend_success_rate": 13.79, "prior_trend_avg_body": -2.28,
        "prior_trend_sample_count": 29, "path_available_count": 29,
        "broad_path_risk_ratio": 0.6, "one_way_selloff_ratio": 0.3,
        "feature_confidence": "high",
        "cluster_top1_positive_share": 0.4, "cluster_top3_positive_share": 0.8,
        "cluster_positive_denominator": 3, "cluster_concentration_label": "concentrated",
        "path_distribution": {"one_way_selloff": 16}, "market_regime": "hostile",
    }

    result = build_transition_record(
        "20260706", "20260707", review, decision, feedback,
        decision_validation_level="candidate_close",
        feedback_validation_level="candidate_close",
    )

    assert result["feedback_label"] == "broad_continuation_failed"
    assert "baseline_trend_enabled_but_broad_trend_failed" in result["contradiction_labels"]
    assert "broad_failure_but_cluster_repair" in result["contradiction_labels"]


def test_t1_single_positive_cluster_sample_cannot_confirm_rotational_repair():
    review = {"environment_gate": {"label": "hostile", "decision": "selective_reversal_only"}}
    decision = {
        "prior_trend_sample_count": 20,
        "prior_trend_success_rate": 20,
        "prior_trend_avg_body": -1,
        "path_available_count": 20,
        "broad_path_risk_ratio": 0.6,
        "one_way_selloff_ratio": 0.25,
        "cluster_top1_positive_share": 0.2,
        "cluster_top3_positive_share": 0.5,
        "cluster_positive_denominator": 4,
        "cluster_concentration_label": "dispersed",
        "feature_confidence": "high",
    }
    feedback = {
        "prior_trend_sample_count": 20,
        "prior_trend_success_rate": 20,
        "prior_trend_avg_body": -1,
        "path_available_count": 20,
        "broad_path_risk_ratio": 0.6,
        "one_way_selloff_ratio": 0.25,
        "feature_confidence": "high",
        "cluster_top1_positive_share": 1.0,
        "cluster_top3_positive_share": 1.0,
        "cluster_positive_denominator": 1,
        "cluster_concentration_label": "insufficient_samples",
    }
    result = build_transition_record(
        "20260706", "20260707", review, decision, feedback,
        decision_validation_level="candidate_close",
        feedback_validation_level="candidate_close",
    )
    assert result["feedback_label"] != "rotational_repair_confirmed"
    assert "broad_failure_but_cluster_repair" not in result["contradiction_labels"]
    assert result["next_day_cluster_concentration"]["usable"] is False


def test_sector_only_never_becomes_candidate_feedback():
    result = build_transition_record(
        "20260707", "20260708", {}, {}, None,
        decision_validation_level="candidate_close",
        feedback_validation_level="sector_range_context",
        sector_context={
            "available": True,
            "scope": "20260708_20260716",
            "daily_return_available": False,
        },
    )
    assert result["feedback_label"] == "sector_context_only_no_daily_price_confirmation"
    assert result["data_available"] is False
    assert result["counts_as_candidate_transition"] is False
    assert result["sector_context_available"] is True


def test_both_sides_must_be_candidate_close_for_valid_pair():
    features = {
        "prior_trend_sample_count": 20,
        "prior_trend_success_rate": 50,
        "prior_trend_avg_body": 0.2,
        "path_available_count": 20,
        "broad_path_risk_ratio": 0.2,
        "one_way_selloff_ratio": 0.1,
        "feature_confidence": "high",
    }
    decision_sector = build_transition_record(
        "20260706", "20260707", {}, features, features,
        decision_validation_level="sector_range_context",
        feedback_validation_level="candidate_close",
    )
    feedback_sector = build_transition_record(
        "20260706", "20260707", {}, features, None,
        decision_validation_level="candidate_close",
        feedback_validation_level="sector_range_context",
    )
    verified = build_transition_record(
        "20260706", "20260707", {}, features, features,
        decision_validation_level="candidate_close",
        feedback_validation_level="candidate_close",
    )
    assert decision_sector["counts_as_valid_candidate_pair"] is False
    assert "decision_not_candidate_close" in decision_sector["pair_exclusion_reasons"]
    assert feedback_sector["counts_as_valid_candidate_pair"] is False
    assert verified["counts_as_valid_candidate_pair"] is True


def test_feedback_reuses_shared_broad_failure_evidence():
    features = {
        "prior_trend_sample_count": 20,
        "prior_trend_success_rate": 50,
        "prior_trend_avg_body": 0.1,
        "path_available_count": 20,
        "broad_path_risk_ratio": 0.6,
        "one_way_selloff_ratio": 0.3,
        "feature_confidence": "high",
    }
    result = build_transition_record(
        "20260706", "20260707",
        {"environment_gate": {"label": "continuation", "decision": "trend_enabled"}},
        features,
        features,
        decision_validation_level="candidate_close",
        feedback_validation_level="candidate_close",
    )
    assert result["next_day_broad_failure_status"]["evidence_count"] == 2
    assert result["feedback_label"] == "broad_continuation_failed"
