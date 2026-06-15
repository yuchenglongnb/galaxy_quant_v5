# -*- coding: utf-8 -*-

from analyzers.evaluators.trend_candidate_filter import TrendCandidateFilter


def _candidate(**data):
    return {
        "name": data.pop("name", "candidate"),
        "signal_category": data.pop("signal_category", "trend"),
        "action_score_breakdown": data.pop("breakdown", {}),
        "data": data,
    }


def setup_function():
    TrendCandidateFilter.reset_cache()


def test_strong_vs_etf_index_and_amount_confirmed_keeps_candidate():
    candidate = _candidate(
        confirmation_data={
            "rs_vs_etf_pct": 1.1,
            "rs_vs_index_pct": 0.7,
            "amount_1m_ratio": 1.5,
        },
        auction_pct=1.0,
    )

    result = TrendCandidateFilter.evaluate_candidate(
        candidate,
        regime={"label": "continuation"},
        coverage_context={
            "trend_total_count": 1,
            "rs_vs_etf_available_count": 1,
            "rs_vs_index_available_count": 1,
            "amount_1m_ratio_available_count": 1,
            "confirmation_coverage_count": 1,
            "confirmation_coverage_ratio": 1.0,
        },
    )

    assert result["trend_filter_decision"] == "keep"
    assert result["trend_filter_status"] == "active"
    assert result["trend_filter_score"] > 0
    assert "strong_vs_etf" in result["trend_filter_reasons"]
    assert "strong_vs_index" in result["trend_filter_reasons"]
    assert "amount_confirmed" in result["trend_filter_reasons"]


def test_weak_vs_etf_and_index_observes_or_drops_candidate():
    candidate = _candidate(
        confirmation_data={
            "rs_vs_etf_pct": -0.4,
            "rs_vs_index_pct": -0.2,
            "amount_1m_ratio": 1.0,
        },
        auction_pct=0.8,
    )

    result = TrendCandidateFilter.evaluate_candidate(
        candidate,
        regime={"label": "mixed"},
        coverage_context={
            "trend_total_count": 2,
            "rs_vs_etf_available_count": 2,
            "rs_vs_index_available_count": 2,
            "amount_1m_ratio_available_count": 2,
            "confirmation_coverage_count": 2,
            "confirmation_coverage_ratio": 1.0,
        },
    )

    assert result["trend_filter_decision"] in {"observe", "drop"}
    assert result["trend_filter_status"] == "active"
    assert "weak_vs_etf" in result["trend_filter_risk_flags"]
    assert "weak_vs_index" in result["trend_filter_risk_flags"]


def test_strong_repair_without_relative_strength_confirmation_keeps_with_global_missing():
    candidate = _candidate(auction_pct=1.0)

    result = TrendCandidateFilter.evaluate_candidate(candidate, regime={"label": "strong_repair"})

    assert result["trend_filter_decision"] == "keep"
    assert result["trend_filter_status"] == "degraded_global_missing"
    assert "missing_rs_vs_etf_pct" in result["trend_filter_missing_fields"]
    assert "missing_rs_vs_index_pct" in result["trend_filter_missing_fields"]
    assert "relative_strength_unverified" in result["trend_filter_risk_flags"]
    assert "global_confirmation_unavailable" in result["trend_filter_risk_flags"]


def test_missing_relative_strength_fields_do_not_raise():
    candidate = _candidate(auction_pct=0.3)

    result = TrendCandidateFilter.evaluate_candidate(candidate, regime={"label": "continuation"})

    assert "missing_rs_vs_etf_pct" in result["trend_filter_missing_fields"]
    assert "missing_rs_vs_index_pct" in result["trend_filter_missing_fields"]
    assert result["trend_filter_decision"] in {"keep", "observe", "drop"}


def test_high_open_without_clear_relative_strength_observes():
    candidate = _candidate(
        confirmation_data={
            "rs_vs_etf_pct": 0.1,
            "rs_vs_index_pct": 0.1,
            "amount_1m_ratio": 1.0,
        },
        auction_pct=5.5,
    )

    result = TrendCandidateFilter.evaluate_candidate(
        candidate,
        regime={"label": "mixed"},
        coverage_context={
            "trend_total_count": 10,
            "rs_vs_etf_available_count": 8,
            "rs_vs_index_available_count": 8,
            "amount_1m_ratio_available_count": 8,
            "confirmation_coverage_count": 8,
            "confirmation_coverage_ratio": 0.8,
        },
    )

    assert result["trend_filter_decision"] == "observe"
    assert result["trend_filter_status"] == "active"
    assert "high_open_risk" in result["trend_filter_risk_flags"]
    assert "high_open_without_relative_strength" in result["trend_filter_invalid_conditions"]


def test_non_trend_candidate_is_not_dropped():
    candidate = _candidate(signal_category="trap", auction_pct=5.0)

    result = TrendCandidateFilter.evaluate_candidate(candidate, regime={"label": "hostile"})

    assert result["trend_filter_decision"] == "keep"
    assert result["trend_filter_score"] == 0.0
    assert result["trend_filter_reasons"] == ["non_trend_candidate"]


def test_partial_missing_status_softens_missing_confirmation_penalty():
    candidate = _candidate(auction_pct=1.2)

    result = TrendCandidateFilter.evaluate_candidate(
        candidate,
        regime={"label": "strong_repair"},
        coverage_context={
            "trend_total_count": 10,
            "rs_vs_etf_available_count": 4,
            "rs_vs_index_available_count": 4,
            "amount_1m_ratio_available_count": 4,
            "confirmation_coverage_count": 4,
            "confirmation_coverage_ratio": 0.4,
        },
    )

    assert result["trend_filter_status"] == "degraded_partial_missing"
    assert result["trend_filter_decision"] == "observe"
    assert "relative_strength_unverified" in result["trend_filter_risk_flags"]
