import unittest

from analyzers.auction import AuctionAnalyzer
from scripts.diagnose_confirmation_coverage import classify_failure


class _FakeFrame:
    def __init__(self, rows):
        self._rows = rows
        self.columns = list(rows[0].keys()) if rows else []
        self.empty = not rows

    def iterrows(self):
        for idx, row in enumerate(self._rows):
            yield idx, row


class ConfirmationCoverageDiagnosisTest(unittest.TestCase):
    def test_classify_failure_intraday_cache_missing(self):
        row = {
            "raw_trend_count": 12,
            "intraday_dir_exists": False,
        }
        self.assertEqual(classify_failure(row), ["intraday_cache_missing"])

    def test_classify_failure_signal_code_missing(self):
        row = {
            "raw_trend_count": 8,
            "intraday_dir_exists": True,
            "stock_signal_code_missing_count": 5,
            "stock_data_code_count": 100,
            "code_intersection_count": 0,
            "benchmark_etf_mapping_count": 3,
            "stock_trend_count": 5,
            "confirmation_file_exists": False,
            "confirmation_coverage_ratio": 0.0,
            "stock_time_values": [],
        }
        flags = classify_failure(row)
        self.assertIn("signal_code_missing", flags)

    def test_classify_failure_marks_coverage_available_when_ratio_is_high(self):
        row = {
            "raw_trend_count": 4,
            "stock_trend_count": 4,
            "confirmation_coverage_ratio": 1.0,
            "benchmark_etf_mapping_count": 0,
        }
        flags = classify_failure(row)
        self.assertIn("coverage_available", flags)

    def test_append_signal_rows_writes_code_and_group(self):
        df = _FakeFrame(
            [{
                "_scenario": "TREND_ACCELERATE",
                "_data": {"auction_pct": 1.0},
                "_name": "测试个股",
                "_code": "300308.SZ",
                "_amt_rank": 3,
                "分组": "通信设备",
            }]
        )
        signals = {"trend": [], "trap": [], "reversal": []}

        from analyzers import auction as auction_module

        original_get_signal_type = auction_module.ScenarioIdentifier.get_signal_type
        original_build = auction_module.SignalFeatureBuilder.build
        try:
            auction_module.ScenarioIdentifier.get_signal_type = lambda scenario: ("🟢趋势", "trend")
            auction_module.SignalFeatureBuilder.build = lambda **kwargs: {"hard_rule": {"trigger_reason": "unit_test"}}

            analyzer = AuctionAnalyzer.__new__(AuctionAnalyzer)
            analyzer._append_signal_rows(
                signals,
                df,
                market_oar=1.0,
                realtime=False,
                target_type="stock",
                display_type="个股",
                order=2,
            )
        finally:
            auction_module.ScenarioIdentifier.get_signal_type = original_get_signal_type
            auction_module.SignalFeatureBuilder.build = original_build

        item = signals["trend"][0]
        self.assertEqual(item["data"]["code"], "300308.SZ")
        self.assertEqual(item["data"]["group"], "通信设备")

    def test_row_to_confirmation_data_preserves_missing_relative_strength(self):
        analyzer = AuctionAnalyzer.__new__(AuctionAnalyzer)
        row = analyzer._row_to_confirmation_data(
            {
                "feature_timestamp": 935,
                "execution_bias": "observe",
                "benchmark_etf_code": "512880.SH",
                "benchmark_index_code": "000001.SH",
                "price_vs_open_pct": 0.12,
                "rs_vs_etf_pct": None,
                "rs_vs_index_pct": -0.45,
                "amount_1m_ratio": 1.25,
            }
        )
        self.assertEqual(row["benchmark_etf_code"], "512880.SH")
        self.assertEqual(row["benchmark_index_code"], "000001.SH")
        self.assertIsNone(row["rs_vs_etf_pct"])
        self.assertEqual(row["rs_vs_index_pct"], -0.45)
        self.assertEqual(row["amount_1m_ratio"], 1.25)

    def test_row_to_confirmation_data_turns_nan_text_into_empty_code(self):
        analyzer = AuctionAnalyzer.__new__(AuctionAnalyzer)
        row = analyzer._row_to_confirmation_data(
            {
                "feature_timestamp": 935,
                "execution_bias": "observe",
                "benchmark_etf_code": float("nan"),
                "benchmark_index_code": "nan",
            }
        )
        self.assertEqual(row["benchmark_etf_code"], "")
        self.assertEqual(row["benchmark_index_code"], "")


if __name__ == "__main__":
    unittest.main()
