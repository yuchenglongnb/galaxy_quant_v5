import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

import scripts.backfill_intraday_cache as backfill_module


class _FakeAnalyzer:
    def __init__(self, _dm):
        pass

    def analyze(self, target_date, realtime=False):
        return {
            "signals": {
                "trend": [
                    {"data": {"target_type": "stock", "code": "300308.SZ", "group": "半导体"}},
                    {"data": {"target_type": "stock", "code": "601688.SH", "group": "证券"}},
                    {"data": {"target_type": "etf", "code": "512480.SH"}},
                ]
            }
        }


class BackfillExecutionModesTest(unittest.TestCase):
    def test_parse_args_execute_defaults_disable_pre_and_post(self):
        argv = ["backfill_intraday_cache.py", "--dates", "20260604", "--execute"]
        with mock.patch.object(sys, "argv", argv):
            args = backfill_module.parse_args()
        self.assertFalse(args.pre_inspect)
        self.assertFalse(args.post_validate)
        self.assertEqual(args.mode, "minimal")
        self.assertEqual(args.data_kind, "min1")

    def test_parse_args_can_enable_pre_and_post(self):
        argv = [
            "backfill_intraday_cache.py",
            "--dates", "20260604",
            "--execute",
            "--pre-inspect",
            "--post-validate",
            "--data-kind", "snapshot,min1",
        ]
        with mock.patch.object(sys, "argv", argv):
            args = backfill_module.parse_args()
        self.assertTrue(args.pre_inspect)
        self.assertTrue(args.post_validate)
        self.assertEqual(args.data_kind, "snapshot,min1")

    def test_resolve_minimal_universe_collects_stock_and_benchmarks(self):
        mapping_df = pd.DataFrame(
            [
                {"group": "半导体", "benchmark_etf_code": "512480.SH", "benchmark_index_code": "000688.SH"},
                {"group": "证券", "benchmark_etf_code": "512880.SH", "benchmark_index_code": "000001.SH"},
            ]
        )
        with mock.patch.object(backfill_module, "AuctionAnalyzer", _FakeAnalyzer):
            with mock.patch.object(backfill_module.IntradayConfirmationBuilder, "load_benchmark_map", return_value=mapping_df):
                universe = backfill_module.resolve_minimal_universe(20260604, object())
        self.assertEqual(universe["stock_codes"], ["300308.SZ", "601688.SH"])
        self.assertEqual(universe["etf_codes"], ["512480.SH", "512880.SH"])
        self.assertEqual(universe["index_codes"], ["000001.SH", "000688.SH"])

    def test_summarize_progress_uses_only_new_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            progress = Path(tmp) / "progress.jsonl"
            progress.write_text(
                "\n".join(
                    [
                        json.dumps({"date": "20260604", "stage": "old", "status": "done"}),
                        json.dumps({"date": "20260604", "stage": "new", "status": "done"}),
                    ]
                ),
                encoding="utf-8",
            )
            summary = backfill_module.summarize_progress(progress, [20260604], start_index=1)
        self.assertEqual(len(summary["events"]["20260604"]), 1)
        self.assertEqual(summary["events"]["20260604"][0]["stage"], "new")


if __name__ == "__main__":
    unittest.main()
