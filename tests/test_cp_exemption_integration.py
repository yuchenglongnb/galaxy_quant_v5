# -*- coding: utf-8 -*-

import pandas as pd

from analyzers.signal_shortlist import SignalShortlistBuilder


def _trend_candidate(name):
    return {
        "name": name,
        "order": 2,
        "amt_rank": 1,
        "scenario": "TREND_ACCELERATE",
        "data": {
            "target_type": "stock",
            "auction_pct": 1.0,
            "prev_pct": 3.0,
            "prev_vol_ratio": 1.5,
            "pos_5d": 70,
            "confirmation_data": {
                "rs_vs_etf_pct": 1.0,
                "rs_vs_index_pct": 0.8,
                "amount_1m_ratio": 1.5,
            },
        },
    }


def _trap_candidate(name, cp=80, auction_pct=2.0):
    return {
        "name": name,
        "order": 1,
        "amt_rank": 1,
        "cp": cp,
        "scenario": "TRAP_HOT_SECTOR",
        "leading_cluster_membership": False,
        "leading_cluster_strength": None,
        "leading_cluster_status": "partial",
        "leading_cluster_evidence": [],
        "leading_cluster_risk_flags": [],
        "data": {
            "target_type": "ETF",
            "auction_pct": auction_pct,
            "prev_pct": 4.0,
            "prev_vol_ratio": 1.3,
            "pos_5d": 80,
        },
    }


def test_trend_and_reversal_counts_do_not_change_when_cp_risk_is_added(monkeypatch):
    def fake_evidence(candidate, date_int=None):
        candidate.setdefault("leading_cluster_membership", False)
        candidate.setdefault("leading_cluster_name", "")
        candidate.setdefault("leading_cluster_rank", None)
        candidate.setdefault("leading_cluster_strength", None)
        candidate.setdefault("leading_cluster_evidence", [])
        candidate.setdefault("leading_cluster_missing_fields", [])
        candidate.setdefault("leading_cluster_risk_flags", [])
        candidate.setdefault("leading_cluster_status", "partial")
        return candidate

    monkeypatch.setattr(
        "analyzers.signal_shortlist.LeadingClusterEvidenceBuilder.enrich_candidate",
        fake_evidence,
    )

    index_df = pd.DataFrame({"_data": [{"auction_pct": 1.2}, {"auction_pct": 1.0}]})
    etf_df = pd.DataFrame({"_data": [{"auction_pct": 0.9}, {"auction_pct": 0.8}]})
    trap = _trap_candidate("TrapETF")
    reversal = {
        "name": "ReversalETF",
        "order": 1,
        "amt_rank": 1,
        "sa": 82,
        "scenario": "REVERSAL_OVERSOLD",
        "data": {
            "target_type": "ETF",
            "auction_pct": -1.0,
            "prev_pct": -4.0,
            "prev_vol_ratio": 1.2,
            "pos_5d": 30,
        },
    }
    trend = _trend_candidate("TrendStock")

    shortlist, _regime = SignalShortlistBuilder.build(
        {"trap": [trap], "reversal": [reversal], "trend": [trend]},
        index_df=index_df,
        etf_df=etf_df,
    )

    assert len(shortlist["trend"]) == 1
    assert len(shortlist["reversal"]) == 0
    assert len(shortlist["reversal_observation"]) == 1
    assert trap["cp_risk_decision"] in {"hard_trap", "crowded_observe", "leading_cluster_exempt", "disabled"}


def test_crowded_observe_goes_to_trap_observation(monkeypatch):
    def fake_evidence(candidate, date_int=None):
        candidate.update(
            {
                "leading_cluster_membership": True,
                "leading_cluster_name": "AI硬件",
                "leading_cluster_rank": 1,
                "leading_cluster_strength": 58.0,
                "leading_cluster_evidence": ["ifind_theme_match"],
                "leading_cluster_missing_fields": [],
                "leading_cluster_risk_flags": [],
                "leading_cluster_status": "partial",
            }
        )
        return candidate

    monkeypatch.setattr(
        "analyzers.signal_shortlist.LeadingClusterEvidenceBuilder.enrich_candidate",
        fake_evidence,
    )

    trap = _trap_candidate("CrowdedTrap", cp=76, auction_pct=3.5)
    shortlist, _regime = SignalShortlistBuilder.build({"trap": [trap], "reversal": [], "trend": []})

    assert shortlist["trap"] == []
    assert shortlist["trap_observation"][0]["name"] == "CrowdedTrap"
    assert trap["cp_risk_decision"] == "crowded_observe"
