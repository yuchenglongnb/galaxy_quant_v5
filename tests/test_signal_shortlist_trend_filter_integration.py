# -*- coding: utf-8 -*-

import unittest

import pandas as pd

from analyzers.signal_shortlist import SignalShortlistBuilder
from analyzers.evaluators.trend_candidate_filter import TrendCandidateFilter


def _candidate(
    name,
    target_type="stock",
    category="trend",
    rank=1,
    auction_pct=1.0,
    prev_pct=3.0,
    confirmation_data=None,
):
    return {
        "name": name,
        "order": {"index": 0, "ETF": 1, "stock": 2, "industry": 3}[target_type],
        "amt_rank": rank,
        "scenario": {"trend": "TREND_ACCELERATE", "trap": "TRAP_HOT_SECTOR", "reversal": "REVERSAL_OVERSOLD"}[category],
        "cp": 70 if category == "trap" else None,
        "sa": 70 if category == "reversal" else None,
        "data": {
            "target_type": target_type,
            "auction_pct": auction_pct,
            "prev_pct": prev_pct,
            "prev_vol_ratio": 1.5,
            "pos_5d": 70,
            **({"confirmation_data": confirmation_data} if confirmation_data is not None else {}),
        },
    }


def _strong_repair_frames():
    index_df = pd.DataFrame({"_data": [{"auction_pct": 2.2, "trend_state": "连跌"}, {"auction_pct": 1.8, "trend_state": "昨跌"}]})
    etf_df = pd.DataFrame({"_data": [{"auction_pct": 1.6}, {"auction_pct": 1.1}, {"auction_pct": 1.0}]})
    return index_df, etf_df


class SignalShortlistTrendFilterIntegrationTest(unittest.TestCase):
    def setUp(self):
        TrendCandidateFilter.reset_cache()

    def test_global_missing_does_not_force_single_trend_candidate_to_observe(self):
        index_df, etf_df = _strong_repair_frames()
        trend = _candidate("GlobalMissingTrend")

        shortlist, regime = SignalShortlistBuilder.build(
            {"trap": [], "reversal": [], "trend": [trend]},
            index_df=index_df,
            etf_df=etf_df,
        )

        self.assertEqual(regime["label"], "strong_repair")
        self.assertEqual(len(shortlist["trend"]), 1)
        self.assertEqual(trend["trend_filter_decision"], "keep")
        self.assertEqual(trend["trend_filter_status"], "degraded_global_missing")
        self.assertEqual(trend["trend_filter_context"]["confirmation_coverage_ratio"], 0.0)

    def test_active_coverage_can_downgrade_only_missing_candidate(self):
        index_df, etf_df = _strong_repair_frames()
        strong = _candidate(
            "ConfirmedTrend",
            rank=1,
            confirmation_data={
                "rs_vs_etf_pct": 1.1,
                "rs_vs_index_pct": 0.8,
                "amount_1m_ratio": 1.6,
            },
        )
        missing = _candidate("MissingTrend", rank=2)

        shortlist, _regime = SignalShortlistBuilder.build(
            {"trap": [], "reversal": [], "trend": [strong, strong.copy(), missing]},
            index_df=index_df,
            etf_df=etf_df,
        )

        self.assertEqual(strong["trend_filter_status"], "active")
        self.assertIn(strong, shortlist["trend"])
        self.assertEqual(missing["trend_filter_decision"], "observe")
        self.assertEqual(missing["trend_filter_status"], "active")
        self.assertEqual(shortlist["trend_observation"][0]["name"], "MissingTrend")

    def test_active_coverage_allows_weak_relative_strength_to_be_rejected(self):
        index_df, etf_df = _strong_repair_frames()
        strong = _candidate(
            "StrongTrend",
            rank=1,
            confirmation_data={
                "rs_vs_etf_pct": 1.0,
                "rs_vs_index_pct": 0.7,
                "amount_1m_ratio": 1.5,
            },
        )
        weak = _candidate(
            "WeakTrend",
            rank=2,
            confirmation_data={
                "rs_vs_etf_pct": -0.6,
                "rs_vs_index_pct": -0.4,
                "amount_1m_ratio": 1.2,
            },
        )

        shortlist, _regime = SignalShortlistBuilder.build(
            {"trap": [], "reversal": [], "trend": [strong, weak]},
            index_df=index_df,
            etf_df=etf_df,
        )

        self.assertEqual(weak["trend_filter_status"], "active")
        self.assertIn(weak["trend_filter_decision"], {"observe", "drop"})
        self.assertTrue("weak_vs_etf" in weak["trend_filter_risk_flags"] or "weak_vs_index" in weak["trend_filter_risk_flags"])
        self.assertNotIn(weak, shortlist["trend"])

    def test_cp_and_reversal_are_unchanged_by_trend_filter(self):
        index_df, etf_df = _strong_repair_frames()
        trap = _candidate("Trap", category="trap", rank=1, auction_pct=1.5)
        reversal = _candidate("Reversal", category="reversal", rank=1, auction_pct=-1.0, prev_pct=-3.0)
        trend = _candidate("Trend", confirmation_data={"rs_vs_etf_pct": 1.0, "rs_vs_index_pct": 0.8, "amount_1m_ratio": 1.4})

        shortlist, _regime = SignalShortlistBuilder.build(
            {"trap": [trap], "reversal": [reversal], "trend": [trend]},
            index_df=index_df,
            etf_df=etf_df,
        )

        self.assertTrue(shortlist["trap"] or shortlist["trap_observation"])
        self.assertTrue(shortlist["reversal"] or shortlist["reversal_observation"])
        self.assertEqual(trend["trend_filter_status"], "active")

    def test_trend_filter_context_is_written(self):
        index_df, etf_df = _strong_repair_frames()
        strong = _candidate(
            "CoverageTrend",
            confirmation_data={
                "rs_vs_etf_pct": 1.0,
                "rs_vs_index_pct": 0.8,
                "amount_1m_ratio": 1.5,
            },
        )
        missing = _candidate("CoverageMissing")

        SignalShortlistBuilder.build(
            {"trap": [], "reversal": [], "trend": [strong, missing]},
            index_df=index_df,
            etf_df=etf_df,
        )

        context = strong["trend_filter_context"]
        self.assertEqual(context["trend_total_count"], 2)
        self.assertEqual(context["confirmation_coverage_count"], 1)
        self.assertAlmostEqual(context["confirmation_coverage_ratio"], 0.5)
        self.assertEqual(strong["trend_filter_status"], "degraded_partial_missing")


if __name__ == "__main__":
    unittest.main()
