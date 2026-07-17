from analyzers.context.state_transition_shadow import StateTransitionShadow


def _features(**overrides):
    base = {
        "prior_trend_sample_count": 27,
        "prior_trend_success_rate": 40.74,
        "prior_trend_avg_body": -0.98,
        "path_available_count": 34,
        "broad_path_risk_ratio": 0.58,
        "one_way_selloff_ratio": 0.21,
        "cluster_top1_positive_share": 0.18,
        "cluster_top3_positive_share": 0.36,
        "cluster_positive_denominator": 11,
        "cluster_concentration_label": "dispersed",
        "feature_confidence": "high",
    }
    base.update(overrides)
    return base


def test_continuation_with_broad_risk_becomes_weak_continuation():
    result = StateTransitionShadow.evaluate(
        {"label": "continuation", "decision": "trend_enabled"}, _features()
    )
    assert result["label"] == "weak_continuation"
    assert result["broad_trend_failure_risk"] is True
    assert "baseline_trend_enabled_but_broad_trend_failed" in result["contradiction_labels"]


def test_broad_weak_with_concentrated_repair_is_rotational():
    result = StateTransitionShadow.evaluate(
        {"label": "continuation", "decision": "trend_enabled"},
        _features(
            cluster_top1_positive_share=0.4,
            cluster_positive_denominator=3,
            cluster_concentration_label="concentrated",
        ),
    )
    assert result["label"] == "rotational_repair_with_broad_trend_failure_risk"
    assert result["cluster_concentration_usable"] is True
    assert result["not_active_strategy_rule"] is True


def test_single_positive_cluster_sample_cannot_trigger_rotational_repair():
    result = StateTransitionShadow.evaluate(
        {"label": "continuation", "decision": "trend_enabled"},
        _features(
            cluster_top1_positive_share=1.0,
            cluster_top3_positive_share=1.0,
            cluster_positive_denominator=1,
            cluster_concentration_label="insufficient_samples",
        ),
    )
    assert result["label"] == "weak_continuation"
    assert result["cluster_concentration_usable"] is False
    assert result["cluster_concentration_evidence"] is False
    assert result["cluster_concentration_reason"] == "insufficient_positive_cluster_samples"


def test_two_positive_cluster_samples_do_not_add_cluster_repair_contradiction():
    result = StateTransitionShadow.evaluate(
        {"label": "continuation", "decision": "trend_enabled"},
        _features(
            cluster_top3_positive_share=1.0,
            cluster_positive_denominator=2,
            cluster_concentration_label="insufficient_samples",
        ),
    )
    assert "broad_failure_but_cluster_repair" not in result["contradiction_labels"]


def test_good_breadth_supports_continuation():
    result = StateTransitionShadow.evaluate(
        {"label": "continuation", "decision": "trend_enabled"},
        _features(
            prior_trend_success_rate=60,
            prior_trend_avg_body=1.2,
            broad_path_risk_ratio=0.2,
            one_way_selloff_ratio=0.1,
        ),
    )
    assert result["label"] == "broad_continuation_supported"


def test_small_sample_is_data_insufficient():
    result = StateTransitionShadow.evaluate({}, _features(prior_trend_sample_count=3, feature_confidence="low"))
    assert result["label"] == "data_insufficient"
    assert result["cluster_positive_denominator"] == 11


def test_invalid_cluster_denominator_is_not_usable():
    result = StateTransitionShadow.cluster_concentration_status({
        "cluster_positive_denominator": float("nan"),
        "cluster_concentration_label": "concentrated",
        "cluster_top1_positive_share": 1.0,
    })
    assert result["denominator"] == 0
    assert result["usable"] is False


def test_broad_failure_status_is_shared_four_evidence_contract():
    result = StateTransitionShadow.broad_failure_status(_features())
    assert result["evidence_count"] == 4
    assert result["broad_failure"] is True
