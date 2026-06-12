# -*- coding: utf-8 -*-

from analyzers.factors import AuctionFactors, ScenarioIdentifier
from config.settings import AuctionConfig


def test_calc_cp_triggers_for_high_open_top_rank():
    row = {
        "amt_rank": 1,
        "pos_5d": 90,
        "auction_pct": 0.8,
        "prev_pct": 2.0,
        "prev_vol_ratio": 1.5,
        "is_gem": False,
    }

    cp = AuctionFactors.calc_cp(row, market_oar=1.0)

    assert cp is not None
    assert cp >= AuctionConfig.CP_THRESHOLD


def test_calc_sa_triggers_for_ranked_low_open_with_amount():
    row = {
        "auction_amt": 20,
        "auction_pct": -1.0,
        "prev_body_pct": -2.0,
        "prev_vol_ratio": 1.5,
        "amt_rank": 1,
    }

    sa = AuctionFactors.calc_sa(row, market_oar=1.0)

    assert sa is not None
    assert sa >= AuctionConfig.SA_THRESHOLD


def test_scenario_identifier_uses_configured_cp_threshold(monkeypatch):
    monkeypatch.setattr(AuctionConfig, "CP_THRESHOLD", 10)
    row = {
        "cp": 12,
        "sa": None,
        "auction_pct": 0.8,
        "body_pct": 0,
        "prev_pct": 2.0,
        "prev_body_pct": 0,
        "prev_vol_ratio": 1.0,
        "pos_5d": 50,
        "amt_rank": 4,
        "trend_state": "",
    }

    scenario = ScenarioIdentifier.identify(row, market_oar=1.0, realtime=True)

    assert scenario is not None
    assert scenario.startswith("TRAP")


def test_reversal_candidate_does_not_require_post_close_body():
    row = {
        "cp": None,
        "sa": 80,
        "auction_pct": -1.0,
        "body_pct": -2.5,
        "prev_pct": -1.0,
        "prev_body_pct": -1.0,
        "prev_vol_ratio": 1.0,
        "pos_5d": 50,
        "amt_rank": 1,
        "trend_state": "",
    }

    scenario = ScenarioIdentifier.identify(row, market_oar=1.0, realtime=False)

    assert scenario is not None
    assert scenario.startswith("REVERSAL")


def test_trend_candidate_does_not_require_post_close_body():
    row = {
        "cp": None,
        "sa": None,
        "auction_pct": 0.1,
        "body_pct": -3.0,
        "prev_pct": 1.5,
        "prev_body_pct": 1.0,
        "prev_vol_ratio": 1.0,
        "pos_5d": 80,
        "amt_rank": 10,
        "trend_state": "连涨",
    }

    scenario = ScenarioIdentifier.identify(row, market_oar=1.0, realtime=False)

    assert scenario is not None
    assert scenario.startswith("TREND")
