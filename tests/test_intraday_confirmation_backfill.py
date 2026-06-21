from unittest import mock

import pandas as pd

import scripts.backfill_intraday_cache as cache_module
import scripts.backfill_intraday_confirmation as backfill_module


class _FakeAnalyzer:
    def __init__(self, _dm):
        pass

    def analyze(self, target_date, realtime=False):
        return {
            "signals": {
                "trend": [
                    {"data": {"target_type": "stock", "code": "688111.SH", "group": "数字芯片设计"}},
                    {"data": {"target_type": "stock", "code": "300308.SZ", "group": "通信网络设备及器件"}},
                    {"data": {"target_type": "stock", "code": "600111.SH", "group": ""}},
                ]
            }
        }


def test_resolve_minimal_universe_adds_board_index_fallback_codes():
    mapping_df = pd.DataFrame(
        [
            {"group": "数字芯片设计", "benchmark_etf_code": "512480.SH", "benchmark_index_code": "000688.SH"},
            {"group": "通信网络设备及器件", "benchmark_etf_code": "", "benchmark_index_code": ""},
        ]
    )
    with mock.patch.object(cache_module, "AuctionAnalyzer", _FakeAnalyzer):
        with mock.patch.object(
            cache_module.IntradayConfirmationBuilder,
            "load_benchmark_map",
            return_value=mapping_df,
        ):
            universe = cache_module.resolve_minimal_universe(20260616, object())
    assert "000688.SH" in universe["index_codes"]
    assert "399006.SZ" in universe["index_codes"]
    assert "000001.SH" in universe["index_codes"]
    assert "399006.SZ" in universe["board_index_codes"]
    assert universe["board_index_fallback_attached_count"] >= 1


def test_backfill_dry_run_does_not_write_files():
    fake_diag = {
        "date": "20260616",
        "stock_trend_total": 2,
        "current_confirmation_available": False,
        "missing_stock_intraday_count": 2,
        "missing_benchmark_etf_intraday_count": 1,
        "missing_benchmark_index_intraday_count": 2,
        "board_index_codes_used": ["399006.SZ"],
    }
    fake_universe = {
        "stock_codes": ["688111.SH"],
        "etf_codes": [],
        "index_codes": ["000688.SH"],
        "board_index_codes": ["000688.SH"],
    }
    with mock.patch.object(backfill_module, "build_diag_payload", return_value=fake_diag):
        with mock.patch.object(backfill_module, "resolve_minimal_universe", return_value=fake_universe):
            payload = backfill_module.run_backfill(
                20260616,
                execute=False,
                force=False,
                stage="all",
                max_stocks=0,
                only_codes=[],
                begin_time=930,
                end_time=935,
                batch_size=120,
                skip_existing=False,
                warn_after_sec=60.0,
                isolated_query=False,
            )
    assert payload["dry_run"] is True
    assert payload["rebuild_result"]["reason"] == "dry_run"
    assert payload["written_files"] == []
