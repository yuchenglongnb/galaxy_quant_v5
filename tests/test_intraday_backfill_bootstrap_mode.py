from unittest import mock

import scripts.backfill_intraday_confirmation as backfill_module


def test_run_backfill_passes_isolated_query_to_data_manager():
    fake_diag = {
        "date": "20260616",
        "stock_trend_total": 0,
        "current_confirmation_available": False,
        "missing_stock_intraday_count": 0,
        "missing_benchmark_etf_intraday_count": 0,
        "missing_benchmark_index_intraday_count": 0,
        "board_index_codes_used": [],
    }
    fake_universe = {"stock_codes": [], "etf_codes": [], "index_codes": ["000001.SH"]}
    fake_dm = mock.Mock()
    fake_dm.rebuild_intraday_confirmation_from_snapshot.return_value = {"rebuilt": True, "reason": ""}
    fake_trend = {"overall_coverage": {}, "intraday_confirmation_status": {"signal_enriched_count": 0}}
    with mock.patch.object(backfill_module, "DataManager", return_value=fake_dm):
        with mock.patch.object(backfill_module, "resolve_minimal_universe", return_value=fake_universe):
            with mock.patch.object(backfill_module, "build_diag_payload", return_value=fake_diag):
                with mock.patch.object(backfill_module, "build_trend_payload", return_value=fake_trend):
                    with mock.patch.object(backfill_module, "_written_files", return_value=[]):
                        with mock.patch.object(backfill_module, "_summarize_stage_events", return_value={"events": [], "slow_batches": [], "failed_batches": []}):
                            with mock.patch.object(backfill_module, "_write_bootstrap_compare_report"):
                                backfill_module.run_backfill(
                                    20260616,
                                    execute=True,
                                    force=False,
                                    stage="index",
                                    max_stocks=0,
                                    only_codes=[],
                                    begin_time=930,
                                    end_time=935,
                                    batch_size=1,
                                    skip_existing=False,
                                    warn_after_sec=60.0,
                                    isolated_query=True,
                                )
    _, kwargs = fake_dm.rebuild_intraday_confirmation_from_snapshot.call_args
    assert kwargs["isolated_query"] is True


def test_run_backfill_default_mode_keeps_isolated_query_false():
    fake_diag = {
        "date": "20260616",
        "stock_trend_total": 0,
        "current_confirmation_available": False,
        "missing_stock_intraday_count": 0,
        "missing_benchmark_etf_intraday_count": 0,
        "missing_benchmark_index_intraday_count": 0,
        "board_index_codes_used": [],
    }
    fake_universe = {"stock_codes": [], "etf_codes": [], "index_codes": []}
    fake_dm = mock.Mock()
    fake_dm.rebuild_intraday_confirmation_from_snapshot.return_value = {"rebuilt": True, "reason": ""}
    fake_trend = {"overall_coverage": {}, "intraday_confirmation_status": {"signal_enriched_count": 0}}
    with mock.patch.object(backfill_module, "DataManager", return_value=fake_dm):
        with mock.patch.object(backfill_module, "resolve_minimal_universe", return_value=fake_universe):
            with mock.patch.object(backfill_module, "build_diag_payload", return_value=fake_diag):
                with mock.patch.object(backfill_module, "build_trend_payload", return_value=fake_trend):
                    with mock.patch.object(backfill_module, "_written_files", return_value=[]):
                        with mock.patch.object(backfill_module, "_summarize_stage_events", return_value={"events": [], "slow_batches": [], "failed_batches": []}):
                            backfill_module.run_backfill(
                                20260616,
                                execute=True,
                                force=False,
                                stage="stock",
                                max_stocks=10,
                                only_codes=[],
                                begin_time=930,
                                end_time=935,
                                batch_size=5,
                                skip_existing=False,
                                warn_after_sec=60.0,
                                isolated_query=False,
                            )
    _, kwargs = fake_dm.rebuild_intraday_confirmation_from_snapshot.call_args
    assert kwargs["isolated_query"] is False
