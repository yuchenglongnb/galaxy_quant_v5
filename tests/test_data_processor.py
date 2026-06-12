# -*- coding: utf-8 -*-

import pandas as pd

from core.data_processor import DataProcessor


def test_mark_price_discontinuities_uses_board_specific_limits():
    df = pd.DataFrame([
        {"code": "002837.SZ", "name": "英维克", "auction_pct": -24.71},
        {"code": "300750.SZ", "name": "宁德时代", "auction_pct": 19.50},
        {"code": "600759.SH", "name": "ST洲际", "auction_pct": 5.07},
        {"code": "601138.SH", "name": "工业富联", "auction_pct": 2.45},
    ])

    result = DataProcessor.mark_price_discontinuities(df).set_index("code")

    assert bool(result.loc["002837.SZ", "price_discontinuity"])
    assert not bool(result.loc["300750.SZ", "price_discontinuity"])
    assert not bool(result.loc["600759.SH", "price_discontinuity"])
    assert not bool(result.loc["601138.SH", "price_discontinuity"])


def test_calc_basic_indicators_prefers_api_pre_close():
    df = pd.DataFrame(
        [
            {
                "code": "000001.SZ",
                "date_int": 20260101,
                "open": 10.0,
                "high": 10.5,
                "low": 9.9,
                "close": 10.0,
                "amount": 100.0,
                "pre_close": 9.8,
            },
            {
                "code": "000001.SZ",
                "date_int": 20260102,
                "open": 10.2,
                "high": 10.6,
                "low": 10.1,
                "close": 10.5,
                "amount": 150.0,
                "pre_close": 10.1,
            },
        ]
    )

    result = DataProcessor.calc_basic_indicators(df)
    row = result[result["date_int"] == 20260102].iloc[0]

    assert row["prev_close"] == 10.1
    assert row["vol_ratio"] == 1.5
    assert "is_limit_up" in result.columns
    assert "prev_is_limit_up" in result.columns


def test_calc_industry_aggregates_sums_amount_and_limit_count():
    df = pd.DataFrame(
        [
            {
                "date_int": 20260102,
                "industry": "半导体",
                "is_limit_up": True,
                "amount": 100_000_000,
                "close": 10.0,
                "open": 9.5,
                "pct": 5.0,
                "code": "000001.SZ",
            },
            {
                "date_int": 20260102,
                "industry": "半导体",
                "is_limit_up": False,
                "amount": 200_000_000,
                "close": 20.0,
                "open": 19.0,
                "pct": 2.0,
                "code": "000002.SZ",
            },
        ]
    )

    result = DataProcessor.calc_industry_aggregates(df)
    row = result.iloc[0]

    assert row["industry"] == "半导体"
    assert row["stock_count"] == 2
    assert row["is_limit_up"] == 1
    assert row["amount"] == 300_000_000
