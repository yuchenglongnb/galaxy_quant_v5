# -*- coding: utf-8 -*-

import pandas as pd

from analyzers.signal_shortlist import SignalShortlistBuilder
from analyzers.factors import AuctionFactors, ScenarioIdentifier


def _candidate(name, target_type, category, rank, auction_pct, cp=None, sa=None, prev_pct=1.0, scenario=None):
    return {
        "name": name,
        "type": target_type,
        "order": {"index": 0, "ETF": 1, "stock": 2, "industry": 3}[target_type],
        "amt_rank": rank,
        "cp": cp,
        "sa": sa,
        "data": {
            "target_type": target_type,
            "auction_pct": auction_pct,
            "prev_pct": prev_pct,
            "prev_vol_ratio": 1.3,
            "pos_5d": 90,
        },
        "scenario": scenario or {"trap": "TRAP_GENERIC", "reversal": "REVERSAL_GENERIC", "trend": "TREND_CONTINUE"}[category],
    }


def test_shortlist_keeps_raw_candidates_and_limits_stock_trends():
    trends = []
    for i in range(12):
        item = _candidate(
            f"E{i}",
            "ETF",
            "trend",
            i + 1,
            1.2,
            prev_pct=6.0 - i * 0.05,
            scenario="TREND_ACCELERATE",
        )
        item["data"]["confirmation_data"] = {
            "rs_vs_etf_pct": 1.0,
            "rs_vs_index_pct": 0.8,
            "amount_1m_ratio": 1.4,
        }
        trends.append(item)
    signals = {"trap": [], "reversal": [], "trend": trends}

    shortlist, _regime = SignalShortlistBuilder.build(signals)

    assert len(signals["trend"]) == 12
    assert len(shortlist["trend"]) == 0
    assert len(shortlist["trend_observation"]) == 1
    assert sum(bool(item["actionable"]) for item in signals["trend"]) == 0
    assert shortlist["trend_observation"][0]["action_filter_reason"] == "trend_filter_observe"


def test_risk_off_regime_penalizes_trend_and_favors_cp():
    index_df = pd.DataFrame({"_data": [{"auction_pct": -0.8}, {"auction_pct": -0.4}]})
    etf_df = pd.DataFrame({"_data": [{"auction_pct": -0.5}, {"auction_pct": -0.2}]})
    trend = _candidate("trend", "ETF", "trend", 1, 0.1, prev_pct=2.0, scenario="TREND_ACCELERATE")
    trap = _candidate("trap", "ETF", "trap", 1, 0.8, cp=60, scenario="TRAP_HOT_SECTOR")
    signals = {"trap": [trap], "reversal": [], "trend": [trend]}

    shortlist, regime = SignalShortlistBuilder.build(signals, index_df=index_df, etf_df=etf_df)

    assert regime["label"] == "risk_off"
    assert shortlist["trap"]
    assert not shortlist["trend"]


def test_cp_shortlist_keeps_top3_and_highlights_top1():
    traps = [
        _candidate(f"T{i}", "ETF", "trap", i + 1, 6.0, cp=120 - i, scenario="TRAP_HOT_SECTOR")
        for i in range(6)
    ]

    shortlist, _regime = SignalShortlistBuilder.build({"trap": traps, "reversal": [], "trend": []})

    assert len(shortlist["trap"]) == 3
    assert shortlist["trap"][0]["action_priority"] == "P0"
    assert {item["action_priority"] for item in shortlist["trap"][1:]} == {"P1"}


def test_overheated_acceleration_is_cp_risk_instead_of_trend():
    scenario = ScenarioIdentifier.identify({
        "cp": 40,
        "sa": 20,
        "auction_pct": 5.5,
        "prev_pct": 4.0,
        "prev_body_pct": 3.0,
        "prev_vol_ratio": 1.5,
        "pos_5d": 85,
        "amt_rank": 5,
        "trend_state": "昨涨",
    })

    assert scenario == ScenarioIdentifier.TRAP_OVERHEATED_ACCELERATION


def test_risk_off_without_structural_repair_keeps_reversal_in_observation():
    index_df = pd.DataFrame({"_data": [{"auction_pct": -0.8}, {"auction_pct": -0.4}]})
    etf_df = pd.DataFrame({"_data": [{"auction_pct": -0.5}, {"auction_pct": -0.2}]})
    index_reversal = _candidate(
        "创业板", "index", "reversal", 1, -1.0, sa=80, scenario="REVERSAL_OVERSOLD"
    )
    etf_reversal = _candidate(
        "科创50ETF", "ETF", "reversal", 2, -0.8, sa=75, scenario="REVERSAL_OVERSOLD"
    )
    stock_reversal = _candidate(
        "S1", "stock", "reversal", 3, -1.2, sa=90, scenario="REVERSAL_OVERSOLD"
    )
    generic_reversal = _candidate(
        "沪深300", "index", "reversal", 4, -0.6, sa=95, scenario="REVERSAL_GENERIC"
    )

    shortlist, regime = SignalShortlistBuilder.build(
        {"trap": [], "reversal": [index_reversal, etf_reversal, stock_reversal, generic_reversal], "trend": []},
        index_df=index_df,
        etf_df=etf_df,
    )

    assert regime["label"] == "risk_off"
    assert shortlist["reversal_high_confidence"] == []
    assert all(item.get("action_filter_reason") == "reversal_observation_only" for item in [index_reversal, etf_reversal, stock_reversal, generic_reversal])


def test_auction_position_uses_open_and_prior_closes_only():
    df = pd.DataFrame({
        "code": ["000001.SZ"] * 6,
        "date_int": [1, 2, 3, 4, 5, 6],
        "open": [10, 11, 12, 13, 14, 12],
        "close": [10, 11, 12, 13, 14, 99],
    })

    result = AuctionFactors.calc_position_5d(df)

    assert result.iloc[-1] == 50.0
def test_trend_coverage_context_uses_trend_filter_and_returns_dict(monkeypatch):
    from analyzers import signal_shortlist

    class DummyTrendFilter:
        @staticmethod
        def build_coverage_context(candidates):
            return {
                "trend_total_count": len(candidates),
                "confirmation_coverage_count": 1,
                "confirmation_coverage_ratio": 0.5,
            }

    monkeypatch.setattr(signal_shortlist, "TrendCandidateFilter", DummyTrendFilter)
    result = signal_shortlist.SignalShortlistBuilder._build_trend_coverage_context(
        [{"name": "trend_a"}, {"name": "trend_b"}]
    )

    assert isinstance(result, dict)
    assert result["trend_total_count"] == 2
    assert result["confirmation_coverage_count"] == 1


def test_prior_day_shadow_does_not_return_last_category_coverage():
    from analyzers.signal_shortlist import SignalShortlistBuilder

    signals = {
        "trend": [{"name": "trend", "action_score": 1}],
        "reversal": [{"name": "reversal", "action_score": 2}],
    }
    result = SignalShortlistBuilder._apply_prior_day_context_shadow(signals, {})

    assert result is None
