import scripts.backfill_intraday_confirmation as backfill_module


def test_filter_universe_stage_index_skips_etf_and_stock():
    universe = {
        "stock_codes": ["000001.SZ", "000002.SZ"],
        "etf_codes": ["512480.SH"],
        "index_codes": ["000001.SH", "399006.SZ"],
    }
    filtered = backfill_module._filter_universe(
        universe,
        stage="index",
        max_stocks=0,
        only_codes=[],
        selection_priority="original",
    )
    assert filtered["stock_codes"] == []
    assert filtered["etf_codes"] == []
    assert filtered["index_codes"] == ["000001.SH", "399006.SZ"]


def test_filter_universe_stage_stock_applies_max_stocks():
    universe = {
        "stock_codes": ["000001.SZ", "000002.SZ", "000003.SZ"],
        "etf_codes": ["512480.SH"],
        "index_codes": ["000001.SH"],
    }
    filtered = backfill_module._filter_universe(
        universe,
        stage="stock",
        max_stocks=2,
        only_codes=[],
        selection_priority="original",
    )
    assert filtered["stock_codes"] == ["000001.SZ", "000002.SZ"]
    assert filtered["etf_codes"] == []
    assert filtered["index_codes"] == []


def test_filter_universe_only_codes_has_priority():
    universe = {
        "stock_codes": ["000001.SZ", "000002.SZ"],
        "etf_codes": ["512480.SH"],
        "index_codes": ["000001.SH"],
    }
    filtered = backfill_module._filter_universe(
        universe,
        stage="all",
        max_stocks=0,
        only_codes=["000002.SZ", "000001.SH"],
        selection_priority="original",
    )
    assert filtered["stock_codes"] == ["000002.SZ"]
    assert filtered["etf_codes"] == []
    assert filtered["index_codes"] == ["000001.SH"]
