import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import scripts.backfill_intraday_cache as backfill_module
from scripts.backfill_intraday_cache import load_plan_dates, write_result
from scripts.diagnose_intraday_cache_backfill import (
    build_plan_candidates,
    classify_missing_type,
    compute_priority,
    recommend_action,
)


class IntradayCacheBackfillPlanTest(unittest.TestCase):
    def test_classify_intraday_cache_missing(self):
        row = {"raw_trend_count": 12, "intraday_dir_exists": False}
        self.assertEqual(classify_missing_type(row), "intraday_cache_missing")

    def test_priority_prefers_days_with_trend_signals(self):
        rich = {"raw_trend_count": 20, "stock_trend_count": 18, "main_failure": "intraday_cache_missing", "confirmation_coverage_ratio": 0.0, "trend_filter_status": "degraded_global_missing"}
        poor = {"raw_trend_count": 0, "stock_trend_count": 0, "main_failure": "intraday_cache_missing", "confirmation_coverage_ratio": 0.0, "trend_filter_status": "degraded_global_missing"}
        self.assertGreater(compute_priority(rich, "intraday_cache_missing"), compute_priority(poor, "no_trend_signals"))

    def test_recommend_action_for_partial_intraday_missing(self):
        row = {
            "raw_trend_count": 6,
            "intraday_dir_exists": True,
            "stock_file_exists": True,
            "etf_file_exists": False,
            "index_file_exists": True,
        }
        missing_type = classify_missing_type(row)
        self.assertEqual(missing_type, "etf_intraday_missing")
        self.assertEqual(recommend_action(row, missing_type), "backfill_etf_only")

    def test_empty_intraday_dir_is_not_treated_as_complete(self):
        row = {
            "raw_trend_count": 10,
            "intraday_dir_exists": True,
            "stock_file_exists": False,
            "etf_file_exists": False,
            "index_file_exists": False,
            "confirmation_coverage_ratio": 0.0,
        }
        self.assertEqual(classify_missing_type(row), "partial_intraday_missing")

    def test_build_plan_candidates_preserves_candidate_shape(self):
        payload = {
            "daily": [
                {
                    "date": "20260612",
                    "raw_trend_count": 30,
                    "stock_trend_count": 28,
                    "intraday_dir_exists": False,
                    "stock_file_exists": False,
                    "etf_file_exists": False,
                    "index_file_exists": False,
                    "confirmation_coverage_ratio": 0.0,
                    "trend_filter_status": "degraded_global_missing",
                    "main_failure": "intraday_cache_missing",
                }
            ]
        }
        candidates = build_plan_candidates(payload)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["recommended_action"], "backfill_all_intraday")
        self.assertIn("priority", candidates[0])

    def test_load_plan_dates_filters_non_backfill_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(
                json.dumps(
                    {
                        "recommended_backfill_batch": [
                            {"date": "20260612", "recommended_action": "backfill_all_intraday"},
                            {"date": "20260611", "recommended_action": "skip_no_trend"},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            self.assertEqual(load_plan_dates(path), [20260612])

    def test_write_result_supports_dry_run_without_market_data(self):
        payload = {
            "created_at": "2026-06-15T18:00:00",
            "execute": False,
            "force": False,
            "mode": "minimal",
            "data_kind": "min1",
            "pre_inspect": False,
            "post_validate": False,
            "warn_after_sec": 120.0,
            "progress_path": "reports/analysis/evaluations/intraday_backfill_progress.jsonl",
            "timing_json": "reports/analysis/evaluations/intraday_backfill_timing.json",
            "timing_md": "reports/analysis/evaluations/intraday_backfill_timing.md",
            "dates": ["20260612"],
            "records": [
                {
                    "date": "20260612",
                    "before_coverage": 0.0,
                    "after_coverage": 0.0,
                    "after_status": "degraded_global_missing",
                    "after_main_failure": "intraday_cache_missing",
                    "universe": {"stock_codes": [], "etf_codes": [], "index_codes": []},
                    "result": {"reason": "dry_run"},
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            temp_eval_dir = Path(tmp)
            with mock.patch.object(backfill_module, "EVAL_DIR", temp_eval_dir):
                json_path, md_path = write_result(payload)
                self.assertTrue(json_path.exists())
                self.assertTrue(md_path.exists())


if __name__ == "__main__":
    unittest.main()
