import pandas as pd

from core.intraday_confirmation import IntradayConfirmationBuilder


def test_build_relative_strength_and_amount_confirmation():
    stocks = pd.DataFrame(
        [
            {"code": "000001.SZ", "group": "bank", "time_int": 930, "pre_close": 10, "open": 10, "last": 10.1, "amount_1min": 100},
            {"code": "000001.SZ", "group": "bank", "time_int": 931, "pre_close": 10, "open": 10, "last": 10.2, "amount_1min": 100},
            {"code": "000001.SZ", "group": "bank", "time_int": 932, "pre_close": 10, "open": 10, "last": 10.4, "amount_1min": 300},
        ]
    )
    etfs = pd.DataFrame(
        [{"code": "512800.SH", "time_int": 932, "pre_close": 1, "open": 1, "last": 1.01, "amount_1min": 100}]
    )
    indices = pd.DataFrame(
        [{"code": "000001.SH", "time_int": 932, "pre_close": 100, "open": 100, "last": 101, "amount_1min": 100}]
    )
    mapping = pd.DataFrame(
        [{"group": "bank", "benchmark_etf_code": "512800.SH", "benchmark_index_code": "000001.SH"}]
    )

    row = IntradayConfirmationBuilder.build(stocks, etfs, indices, mapping).iloc[0]

    assert row["rs_vs_etf_pct"] == 3.0
    assert row["rs_vs_index_pct"] == 3.0
    assert row["amount_1m_ratio"] == 3.0
    assert row["volume_price_state"] == "up_with_amount"
    assert row["execution_bias"] == "confirmed_strength"


def test_missing_etf_mapping_keeps_index_relative_strength():
    stocks = pd.DataFrame(
        [{"code": "000001.SZ", "group": "unknown", "time_int": 930, "pre_close": 10, "open": 10, "last": 9.8, "amount_1min": 100}]
    )
    indices = pd.DataFrame(
        [{"code": "000001.SH", "time_int": 930, "pre_close": 100, "open": 100, "last": 99, "amount_1min": 100}]
    )

    row = IntradayConfirmationBuilder.build(stocks, pd.DataFrame(), indices, pd.DataFrame()).iloc[0]

    assert pd.isna(row["rs_vs_etf_pct"])
    assert row["rs_vs_index_pct"] == -1.0
    assert row["benchmark_index_code"] == "000001.SH"


def test_group_key_normalization_matches_mapping():
    stocks = pd.DataFrame(
        [{"code": "000001.SZ", "group": "  bank  ", "time_int": 930, "pre_close": 10, "open": 10, "last": 10.1, "amount_1min": 100}]
    )
    etfs = pd.DataFrame(
        [{"code": "512800.SH", "time_int": 930, "pre_close": 1, "open": 1, "last": 1.01, "amount_1min": 100}]
    )
    indices = pd.DataFrame(
        [{"code": "000001.SH", "time_int": 930, "pre_close": 100, "open": 100, "last": 101, "amount_1min": 100}]
    )
    mapping = pd.DataFrame(
        [{"group": "bank", "benchmark_etf_code": "512800.SH", "benchmark_index_code": "000001.SH"}]
    )

    row = IntradayConfirmationBuilder.build(stocks, etfs, indices, mapping).iloc[0]

    assert row["benchmark_etf_code"] == "512800.SH"
    assert row["rs_vs_etf_pct"] == 0.0


def test_board_index_fallback_for_star_board():
    fallback = IntradayConfirmationBuilder.resolve_board_index_fallback("688111.SH")
    assert fallback["benchmark_index_code"] == "000688.SH"
    assert fallback["board_index_fallback_used"] is True
    assert fallback["benchmark_etf_code"] == ""


def test_board_index_fallback_for_chinext():
    fallback = IntradayConfirmationBuilder.resolve_board_index_fallback("300308.SZ")
    assert fallback["benchmark_index_code"] == "399006.SZ"
    assert fallback["board_index_code"] == "399006.SZ"


def test_board_index_fallback_for_sse_main_board():
    fallback = IntradayConfirmationBuilder.resolve_board_index_fallback("600519.SH")
    assert fallback["benchmark_index_code"] == "000001.SH"


def test_board_index_fallback_for_szse_main_board():
    fallback = IntradayConfirmationBuilder.resolve_board_index_fallback("002371.SZ")
    assert fallback["benchmark_index_code"] == "399001.SZ"


def test_resolve_benchmark_prefers_existing_etf_mapping():
    resolved = IntradayConfirmationBuilder.resolve_benchmark(
        group="半导体",
        stock_code="688981.SH",
        benchmark_map={},
        existing_etf_code="512480.SH",
        existing_index_code="000688.SH",
    )
    assert resolved["benchmark_etf_code"] == "512480.SH"
    assert resolved["benchmark_index_code"] == "000688.SH"
    assert resolved["board_index_fallback_used"] is False
