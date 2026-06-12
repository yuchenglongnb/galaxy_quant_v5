# -*- coding: utf-8 -*-

import json

import pandas as pd

from analyzers.auction import AuctionAnalyzer
from core.data_manager import DataManager
from core.data_processor import DataProcessor


def test_auction_cache_marks_exact_and_approximate_sources(tmp_path):
    path = tmp_path / "stocks_auction.csv"
    df = pd.DataFrame([{"code": "000001.SZ", "open": 10, "amount": 100}])

    DataManager._write_auction_cache(df, str(path), "subscription_925", True, "09:25:01")
    meta = json.loads((tmp_path / "stocks_auction.meta.json").read_text(encoding="utf-8"))

    manager = DataManager.__new__(DataManager)
    assert meta["auction_amount_exact"] is True
    assert manager._auction_cache_ready(str(path), exact_only=True)

    DataManager._write_auction_cache(
        df, str(path), "minute_930_includes_first_minute", False, "09:30"
    )

    assert manager._auction_cache_ready(str(path))
    assert not manager._auction_cache_ready(str(path), exact_only=True)


def test_auction_metrics_prefers_matched_open_over_first_minute_close():
    analyzer = AuctionAnalyzer.__new__(AuctionAnalyzer)
    daily = pd.DataFrame([{
        "code": "000001.SZ",
        "open": 10,
        "close": 10.5,
        "amount": 1000,
        "prev_close": 9,
    }])
    auction = pd.DataFrame([{
        "code": "000001.SZ",
        "open": 10,
        "close": 11,
        "amount": 100,
        "auction_source": "minute_930_includes_first_minute",
        "auction_amount_exact": False,
    }])

    result = analyzer._calc_auction_metrics(daily, auction)

    assert result.iloc[0]["auction_price"] == 10
    assert result.iloc[0]["auction_amount_raw"] == 100
    assert result.iloc[0]["auction_source"] == "minute_930_includes_first_minute"


def test_data_processor_prefers_matched_open_over_first_minute_close():
    daily = pd.DataFrame([{
        "code": "000001.SZ",
        "open": 10,
        "close": 10.5,
        "amount": 1000,
        "pre_close": 9,
    }])
    auction = pd.DataFrame([{
        "code": "000001.SZ",
        "open": 10,
        "close": 11,
        "amount": 100,
        "pre_close": 9,
    }])

    result = DataProcessor.merge_auction_with_daily(auction, daily)

    assert result.iloc[0]["auction_price"] == 10
