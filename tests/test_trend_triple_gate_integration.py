# -*- coding: utf-8 -*-

import unittest

import pandas as pd

from analyzers.signal_shortlist import SignalShortlistBuilder
from analyzers.evaluators.trend_triple_gate import TrendTripleGate


def _candidate(
    name,
    target_type="stock",
    rank=1,
    confirmation_data=None,
    leading_cluster_membership=False,
    leading_cluster_name="",
    leading_cluster_strength=None,
    leading_cluster_status="",
    leading_cluster_evidence=None,
    leading_cluster_risk_flags=None,
):
    data = {
        "target_type": target_type,
        "auction_pct": 1.0,
        "prev_pct": 3.0,
        "prev_vol_ratio": 1.5,
        "pos_5d": 70,
    }
    if confirmation_data is not None:
        data["confirmation_data"] = confirmation_data
    return {
        "name": name,
        "signal_category": "trend",
        "order": {"index": 0, "ETF": 1, "stock": 2, "industry": 3}[target_type],
        "amt_rank": rank,
        "scenario": "TREND_ACCELERATE",
        "leading_cluster_membership": leading_cluster_membership,
        "leading_cluster_name": leading_cluster_name,
        "leading_cluster_strength": leading_cluster_strength,
        "leading_cluster_status": leading_cluster_status,
        "leading_cluster_evidence": leading_cluster_evidence or [],
        "leading_cluster_risk_flags": leading_cluster_risk_flags or [],
        "data": data,
    }


def _mixed_frames():
    index_df = pd.DataFrame({"_data": [{"auction_pct": 0.2, "trend_state": "昨涨"}, {"auction_pct": -0.1, "trend_state": "昨跌"}]})
    etf_df = pd.DataFrame({"_data": [{"auction_pct": 0.3}, {"auction_pct": 0.1}, {"auction_pct": -0.1}]})
    return index_df, etf_df


class TrendTripleGateIntegrationTest(unittest.TestCase):
    def setUp(self):
        TrendTripleGate.reset_cache()

    def test_shadow_fields_are_attached_without_changing_trend_shortlist(self):
        index_df, etf_df = _mixed_frames()
        trend = _candidate(
            "ShadowTrend",
            confirmation_data={
                "rs_vs_etf_pct": 1.0,
                "rs_vs_index_pct": 0.8,
                "amount_1m_ratio": 1.4,
            },
            leading_cluster_membership=True,
            leading_cluster_name="半导体",
            leading_cluster_strength=72.0,
            leading_cluster_status="active",
            leading_cluster_evidence=["sector_strength_score_confirmed"],
        )
        signals = {"trap": [], "reversal": [], "trend": [trend]}

        shortlist, _regime = SignalShortlistBuilder.build(signals, index_df=index_df, etf_df=etf_df)

        self.assertIn("trend_gate_decision_shadow", trend)
        self.assertIn("trend_gate_context", trend)
        self.assertEqual(len(shortlist["trend"]), 0)
        self.assertEqual(len(shortlist["trend_observation"]), 1)

    def test_shadow_drop_does_not_change_existing_observation_routing(self):
        index_df, etf_df = _mixed_frames()
        weak = _candidate(
            "WeakShadow",
            confirmation_data={
                "rs_vs_etf_pct": -0.6,
                "rs_vs_index_pct": -0.4,
            },
            leading_cluster_membership=True,
            leading_cluster_name="半导体",
            leading_cluster_strength=70.0,
            leading_cluster_status="active",
            leading_cluster_evidence=["sector_strength_score_confirmed"],
        )

        shortlist, _regime = SignalShortlistBuilder.build(
            {"trap": [], "reversal": [], "trend": [weak]},
            index_df=index_df,
            etf_df=etf_df,
        )

        self.assertEqual(weak["trend_gate_decision_shadow"], "drop")
        self.assertEqual(weak["trend_filter_decision"], "drop")
        self.assertEqual(len(shortlist["trend"]), 0)


if __name__ == "__main__":
    unittest.main()
