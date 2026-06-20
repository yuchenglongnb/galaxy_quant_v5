# -*- coding: utf-8 -*-

from analyzers.evaluators.cp_risk_evaluator import CPRiskEvaluator


def _candidate(**overrides):
    candidate = {
        "cp": 88,
        "market_regime": "strong_repair",
        "leading_cluster_membership": False,
        "leading_cluster_strength": None,
        "leading_cluster_rank": None,
        "leading_cluster_status": "partial",
        "leading_cluster_evidence": [],
        "leading_cluster_risk_flags": [],
        "data": {
            "auction_pct": 2.8,
            "confirmation_data": {},
        },
    }
    candidate.update(overrides)
    if "data" in overrides:
        merged = {
            "auction_pct": 2.8,
            "confirmation_data": {},
        }
        merged.update(overrides["data"])
        candidate["data"] = merged
    return candidate


def test_leading_cluster_candidate_can_be_exempted():
    candidate = _candidate(
        leading_cluster_membership=True,
        leading_cluster_strength=82,
        leading_cluster_rank=1,
        leading_cluster_status="active",
        leading_cluster_evidence=[
            "ifind_sector_strength_confirmed",
            "sector_strength_score_confirmed",
        ],
        data={
            "auction_pct": 3.5,
            "confirmation_data": {
                "rs_vs_etf_pct": 0.9,
                "rs_vs_index_pct": 0.6,
                "amount_1m_ratio": 1.3,
            },
        },
    )

    result = CPRiskEvaluator.evaluate_candidate(candidate, regime="strong_repair")

    assert result["cp_risk_decision"] == "leading_cluster_exempt"
    assert result["cp_exempt_by_leading_cluster"] is True


def test_weak_candidate_stays_hard_trap():
    candidate = _candidate(
        data={
            "auction_pct": 6.2,
            "confirmation_data": {
                "rs_vs_etf_pct": -0.6,
                "rs_vs_index_pct": -0.5,
                "amount_1m_ratio": 0.8,
            },
        },
    )

    result = CPRiskEvaluator.evaluate_candidate(candidate, regime="risk_off")

    assert result["cp_risk_decision"] == "hard_trap"
    assert "weak_vs_index" in result["cp_risk_flags"] or "weak_vs_etf" in result["cp_risk_flags"]


def test_partial_leading_defaults_to_crowded_observe():
    candidate = _candidate(
        leading_cluster_membership=True,
        leading_cluster_strength=58,
        leading_cluster_status="partial",
        leading_cluster_evidence=["ifind_theme_match"],
        data={
            "auction_pct": 4.2,
            "confirmation_data": {
                "rs_vs_index_pct": 0.2,
            },
        },
    )

    result = CPRiskEvaluator.evaluate_candidate(candidate, regime="continuation")

    assert result["cp_risk_decision"] == "crowded_observe"


def test_missing_relative_strength_is_not_treated_as_weak():
    candidate = _candidate(
        leading_cluster_membership=True,
        leading_cluster_strength=75,
        leading_cluster_status="active",
        leading_cluster_evidence=["sector_strength_score_confirmed"],
        data={
            "auction_pct": 3.2,
            "confirmation_data": {},
        },
    )

    result = CPRiskEvaluator.evaluate_candidate(candidate, regime="strong_repair")

    assert result["cp_risk_decision"] == "leading_cluster_exempt"
    assert "relative_strength_partially_unverified" in result["cp_risk_flags"]
    assert "missing_rs_vs_etf" in result["cp_risk_missing_fields"]


def test_hostile_regime_blocks_exemption():
    candidate = _candidate(
        leading_cluster_membership=True,
        leading_cluster_strength=80,
        leading_cluster_status="active",
        leading_cluster_evidence=["sector_strength_score_confirmed"],
        data={
            "auction_pct": 2.5,
            "confirmation_data": {
                "rs_vs_etf_pct": 1.1,
                "rs_vs_index_pct": 0.7,
                "amount_1m_ratio": 1.5,
            },
        },
    )

    result = CPRiskEvaluator.evaluate_candidate(candidate, regime="hostile")

    assert result["cp_risk_decision"] == "hard_trap"
