# -*- coding: utf-8 -*-

from datetime import datetime

import pandas as pd

from core.intraday_monitor import IntradayMonitor
from core.snapshot_utils import latest_snapshot_rows


def test_minute_increment_uses_current_cumulative_minus_previous_snapshot():
    monitor = IntradayMonitor.__new__(IntradayMonitor)
    monitor._prev_data = {}
    monitor._counter_date = 20260601

    first = monitor._calc_derived_fields(
        pd.DataFrame([_snapshot(100, 1000)]),
        now=datetime(2026, 6, 1, 9, 30),
    )
    second = monitor._calc_derived_fields(
        pd.DataFrame([_snapshot(135, 1600)]),
        now=datetime(2026, 6, 1, 9, 31),
    )

    assert first.iloc[0]["volume_1min"] == 0
    assert first.iloc[0]["amount_1min"] == 0
    assert second.iloc[0]["volume_1min"] == 35
    assert second.iloc[0]["amount_1min"] == 600
    assert second.iloc[0]["increment_source"] == "previous_snapshot"


def test_summary_calculation_does_not_advance_increment_cache():
    monitor = IntradayMonitor.__new__(IntradayMonitor)
    monitor._prev_data = {"000001.SH": {"volume": 100, "amount": 1000, "time_int": 930}}
    monitor._counter_date = 20260601

    monitor._calc_derived_fields(
        pd.DataFrame([_snapshot(120, 1300)]),
        now=datetime(2026, 6, 1, 9, 30),
        update_cache=False,
    )
    result = monitor._calc_derived_fields(
        pd.DataFrame([_snapshot(150, 1900)]),
        now=datetime(2026, 6, 1, 9, 31),
    )

    assert result.iloc[0]["amount_1min"] == 900


def test_restart_restores_previous_counters_and_guards_counter_reset(tmp_path):
    intraday = tmp_path / "20260601" / "intraday"
    intraday.mkdir(parents=True)
    pd.DataFrame([{
        "code": "000001.SH",
        "time_int": 930,
        "volume": 100,
        "amount": 1000,
    }]).to_csv(intraday / "indices_1min.csv", index=False, encoding="utf-8-sig")
    monitor = IntradayMonitor.__new__(IntradayMonitor)
    monitor.base_path = str(tmp_path)
    monitor._prev_data = {}

    assert monitor._restore_previous_counters(20260601) == 1
    result = monitor._calc_derived_fields(
        pd.DataFrame([_snapshot(90, 900)]),
        now=datetime(2026, 6, 1, 9, 31),
    )

    assert result.iloc[0]["amount_1min"] == 0
    assert bool(result.iloc[0]["counter_reset"])
    assert result.iloc[0]["increment_source"] == "counter_reset"


def test_append_new_minutes_migrates_old_header_and_skips_duplicate_minute(tmp_path):
    path = tmp_path / "indices_1min.csv"
    pd.DataFrame([{
        "code": "000001.SH",
        "time_int": 930,
        "amount": 1000,
    }]).to_csv(path, index=False, encoding="utf-8-sig")
    rows = pd.DataFrame([{
        "code": "000001.SH",
        "time_int": 930,
        "amount": 1200,
        "increment_source": "previous_snapshot",
    }, {
        "code": "000001.SH",
        "time_int": 931,
        "amount": 1600,
        "increment_source": "previous_snapshot",
    }])

    appended = IntradayMonitor._append_new_minutes(str(path), rows)
    saved = pd.read_csv(path, encoding="utf-8-sig")

    assert appended == 1
    assert saved["time_int"].tolist() == [930, 931]
    assert "increment_source" in saved.columns


def test_daemon_cross_day_resets_previous_counters(tmp_path):
    monitor = IntradayMonitor.__new__(IntradayMonitor)
    monitor.base_path = str(tmp_path)
    monitor._counter_date = 20260529
    monitor._prev_data = {"000001.SH": {"volume": 999, "amount": 9999, "time_int": 1500}}

    result = monitor._calc_derived_fields(
        pd.DataFrame([_snapshot(10, 100)]),
        now=datetime(2026, 6, 1, 9, 30),
    )

    assert result.iloc[0]["increment_source"] == "first_snapshot"
    assert result.iloc[0]["amount_1min"] == 0


def test_snapshot_window_uses_real_previous_minute():
    assert IntradayMonitor._snapshot_window(datetime(2026, 6, 2, 13, 35, 0)) == (
        133400000,
        133500000,
    )


def test_latest_snapshot_rows_supports_date_nested_sdk_shape():
    rows = latest_snapshot_rows({
        20260602: {
            "000001.SH": pd.DataFrame([
                {"trade_time": "2026-06-02 14:30:00", "last": 10},
                {"trade_time": "2026-06-02 14:30:03", "last": 11},
            ]),
        },
    })

    assert rows == [{
        "trade_time": "2026-06-02 14:30:03",
        "last": 11,
        "code": "000001.SH",
    }]


def _snapshot(volume, amount):
    return {
        "code": "000001.SH",
        "last": 101,
        "pre_close": 100,
        "volume": volume,
        "amount": amount,
    }
