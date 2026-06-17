# -*- coding: utf-8 -*-

import json
import sys
import types


if "AmazingData" not in sys.modules:
    amazing_data = types.ModuleType("AmazingData")
    amazing_data.BaseData = object
    amazing_data.InfoData = object
    amazing_data.MarketData = object
    amazing_data.constant = types.SimpleNamespace(
        Period=types.SimpleNamespace(
            day=types.SimpleNamespace(value="day"),
            min1=types.SimpleNamespace(value="min1"),
        )
    )
    sys.modules["AmazingData"] = amazing_data

from core.data_manager import DataManager


class _FakeDateTime:
    @classmethod
    def now(cls):
        import datetime as _dt

        return _dt.datetime(2026, 5, 26, 15, 20)


def _write_csv(path, size):
    path.write_text("x" * size, encoding="utf-8")


def _write_stock_csv(path):
    body = "code,industry\n000001.SZ,bank\n"
    path.write_text(body + ("x" * 10_000), encoding="utf-8")


def test_same_day_intraday_daily_cache_is_finalized_after_a_share_close(tmp_path, monkeypatch):
    monkeypatch.setattr("core.data_manager.datetime", _FakeDateTime)
    dm = DataManager.__new__(DataManager)

    _write_stock_csv(tmp_path / "stocks.csv")
    _write_csv(tmp_path / "indices.csv", 500)
    (tmp_path / "stocks.meta.json").write_text(
        json.dumps({"session_state": "intraday"}), encoding="utf-8"
    )
    (tmp_path / "indices.meta.json").write_text(
        json.dumps({"session_state": "closed"}), encoding="utf-8"
    )

    assert dm._daily_files_complete(str(tmp_path), 20260526)


class _FakeDateTimeHK:
    @classmethod
    def now(cls):
        import datetime as _dt

        return _dt.datetime(2026, 5, 26, 15, 20)


def test_hk_same_day_cache_stays_intraday_before_1600(tmp_path, monkeypatch):
    monkeypatch.setattr("core.data_manager.datetime", _FakeDateTimeHK)
    dm = DataManager.__new__(DataManager)

    (tmp_path / "stocks.csv").write_text("code,industry\n00700.HK,tech\n", encoding="utf-8")

    assert dm._session_state_for_date(20260526, str(tmp_path), "stocks.csv") == "intraday"


class _FakeDateTimeHKClosed:
    @classmethod
    def now(cls):
        import datetime as _dt

        return _dt.datetime(2026, 5, 26, 16, 5)


def test_hk_same_day_cache_is_closed_after_1600(tmp_path, monkeypatch):
    monkeypatch.setattr("core.data_manager.datetime", _FakeDateTimeHKClosed)
    dm = DataManager.__new__(DataManager)

    (tmp_path / "stocks.csv").write_text("code,industry\n00700.HK,tech\n", encoding="utf-8")

    assert dm._session_state_for_date(20260526, str(tmp_path), "stocks.csv") == "closed"


def test_historical_legacy_daily_cache_without_meta_is_complete(tmp_path, monkeypatch):
    monkeypatch.setattr("core.data_manager.datetime", _FakeDateTime)
    dm = DataManager.__new__(DataManager)

    _write_stock_csv(tmp_path / "stocks.csv")
    _write_csv(tmp_path / "indices.csv", 500)

    assert dm._daily_files_complete(str(tmp_path), 20260525)


def test_historical_analysis_window_falls_back_to_complete_local_days(tmp_path, monkeypatch):
    monkeypatch.setattr("core.data_manager.datetime", _FakeDateTime)
    dm = DataManager.__new__(DataManager)
    dm.base_path = str(tmp_path)
    dm.get_valid_trading_days = lambda lookback=10: [20260525, 20260526]

    local_days = [20260113, 20260114, 20260115, 20260116, 20260119, 20260120]
    for day in local_days:
        day_dir = tmp_path / str(day)
        day_dir.mkdir()
        _write_stock_csv(day_dir / "stocks.csv")
        _write_csv(day_dir / "indices.csv", 500)

    assert dm.get_analysis_window_days(20260120, lookback=6) == local_days
