import json
from pathlib import Path
from unittest import mock

import pandas as pd

from core.intraday_monitor import IntradayMonitor
import scripts.probe_amazing_kline_time_param as probe_module


def test_kline_time_encoding_uses_hhmm():
    assert IntradayMonitor._encode_kline_hhmm(930) == 930
    assert IntradayMonitor._encode_kline_hhmm(935) == 935


def test_snapshot_time_encoding_uses_millis():
    assert IntradayMonitor._encode_snapshot_hhmmss_millis(93000) == 93000000
    assert IntradayMonitor._encode_snapshot_hhmmss_millis(93500) == 93500000


def test_fetch_opening_minute_bars_passes_hhmm_to_query_kline():
    monitor = IntradayMonitor.__new__(IntradayMonitor)
    monitor.ad_market = mock.Mock()
    monitor.ad_market.query_kline.return_value = {"000001.SH": pd.DataFrame()}
    monitor._log_backfill_event = mock.Mock()

    with mock.patch("core.intraday_monitor.iter_kline_frames", return_value=[]):
        monitor._fetch_opening_minute_bars(
            ["000001.SH"],
            20260616,
            begin_hhmm=930,
            end_hhmm=935,
            batch_size=1,
            stage_name="index_min1",
        )

    _, kwargs = monitor.ad_market.query_kline.call_args
    assert kwargs["begin_time"] == 930
    assert kwargs["end_time"] == 935


def test_probe_build_cases_contains_expected_shapes():
    cases = {item["case"]: item for item in probe_module.build_cases()}
    assert cases["no_window"]["begin_time"] is None
    assert cases["hhmm"]["begin_time"] == 930
    assert cases["hhmm"]["end_time"] == 935
    assert cases["snapshot_like"]["begin_time"] == 93000000
    assert cases["snapshot_like"]["end_time"] == 93500000


def test_probe_write_outputs_structure_is_stable(tmp_path: Path):
    payload = {
        "date": "20260616",
        "code": "000001.SH",
        "timeout_sec": 20.0,
        "created_at": "2026-06-21T22:00:00",
        "elapsed_sec": 1.0,
        "results": [
            {
                "case": "hhmm",
                "code": "000001.SH",
                "date": "20260616",
                "begin_time": 930,
                "end_time": 935,
                "elapsed_sec": 0.5,
                "row_count": 6,
                "first_trade_time": "2026-06-16 09:30:00",
                "last_trade_time": "2026-06-16 09:35:00",
                "status": "ok",
                "error": "",
            }
        ],
    }
    with mock.patch.object(probe_module, "EVAL_DIR", tmp_path):
        json_path, md_path = probe_module.write_outputs(payload)
    assert json.loads(json_path.read_text(encoding="utf-8"))["date"] == "20260616"
    assert "| case | begin_time | end_time | status |" in md_path.read_text(encoding="utf-8")
