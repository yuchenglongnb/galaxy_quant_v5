import pandas as pd

from runners.auction import AuctionRunner


def test_daily_payload_keeps_incoming_and_current_close_shadows_separate(monkeypatch):
    runner = AuctionRunner.__new__(AuctionRunner)
    stubs = {
        "_match_market_patterns": [],
        "_build_intraday_confirmation_summary": {},
        "_build_unmatched_auction_summary": {},
        "_leading_clusters": [],
        "_build_theme_cluster_summary": {},
        "_build_shortlist_score_summary": {},
        "_build_technical_route_comparison": {},
        "_methodology_refs": [],
        "_pattern_progress_summary": {},
        "_derive_core_conclusion": "observation only",
        "_pick_notable_records": [],
        "_derive_analyst_judgment": {},
        "_derive_follow_up_points_v2": [],
    }
    for name, value in stubs.items():
        monkeypatch.setattr(runner, name, lambda *args, _value=value, **kwargs: _value)
    baseline = {"label": "continuation", "decision": "trend_enabled"}
    monkeypatch.setattr(runner, "_build_environment_gate", lambda *args: baseline)

    detail = pd.DataFrame([
        {
            "signal_category": "trend",
            "body_pct": -1.0,
            "validation_success": False,
            "signal_path_type": "one_way_selloff",
        }
        for _ in range(20)
    ])
    metrics = pd.DataFrame([
        {"signal_category": "trend", "success_rate": 20.0}
    ])
    incoming = {"label": "incoming_prior_state", "observation_only": True}
    result = {
        "date": "20260707",
        "data_status": {"session_state": "closed"},
        "market_oar": 0.8,
        "market_regime": {"label": "hostile"},
        "prior_day_context": {
            "outcome_features": {"feature_confidence": "high"},
            "environment_gate_shadow_v2": incoming,
        },
    }

    payload = runner._build_analysis_payload(result, detail, metrics)

    assert payload["environment_gate"] == baseline
    assert payload["prior_day_transition_shadow"] == incoming
    assert payload["close_state_transition_shadow"]["label"] == "weak_continuation"
    assert payload["environment_gate_shadow_v2"] == payload["close_state_transition_shadow"]
    assert payload["current_close_outcome_features"]["prior_trend_sample_count"] == 20
    assert payload["shadow_feature_date"] == "20260707"
    assert payload["shadow_decision_date"] == "20260707"
    assert payload["close_state_transition_shadow_available"] is True
    assert payload["shadow_timepoint"] == "close"


def test_provisional_payload_does_not_present_completed_close_shadow(monkeypatch):
    runner = AuctionRunner.__new__(AuctionRunner)
    stubs = {
        "_match_market_patterns": [],
        "_build_intraday_confirmation_summary": {},
        "_build_unmatched_auction_summary": {},
        "_leading_clusters": [],
        "_build_theme_cluster_summary": {},
        "_build_shortlist_score_summary": {},
        "_build_technical_route_comparison": {},
        "_methodology_refs": [],
        "_pattern_progress_summary": {},
        "_derive_core_conclusion": "observation only",
        "_pick_notable_records": [],
        "_derive_analyst_judgment": {},
        "_derive_follow_up_points_v2": [],
    }
    for name, value in stubs.items():
        monkeypatch.setattr(runner, name, lambda *args, _value=value, **kwargs: _value)
    monkeypatch.setattr(
        runner,
        "_build_environment_gate",
        lambda *args: {"label": "continuation", "decision": "trend_enabled"},
    )
    result = {
        "date": "20260707",
        "data_status": {"session_state": "intraday"},
        "prior_day_context": {
            "environment_gate_shadow_v2": {"label": "incoming_prior_state"}
        },
    }

    payload = runner._build_analysis_payload(result, pd.DataFrame(), pd.DataFrame())

    assert payload["close_state_transition_shadow_available"] is False
    assert payload["close_state_transition_shadow"]["label"] == "data_insufficient"
    assert payload["close_state_transition_shadow"]["reason"] == "close_validation_pending"
    assert payload["environment_gate_shadow_v2"] == payload["close_state_transition_shadow"]
    assert payload["current_close_outcome_features_status"] == "provisional_intraday"
    assert payload["shadow_timepoint"] == "provisional_intraday"
    assert payload["shadow_target"] == "close_validation_pending"
    assert payload["prior_day_transition_shadow"]["label"] == "incoming_prior_state"
