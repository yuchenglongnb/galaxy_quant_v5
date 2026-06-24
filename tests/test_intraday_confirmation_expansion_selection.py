import scripts.backfill_intraday_confirmation as backfill_module


def test_filter_universe_leading_cluster_priority_reorders_stock_codes():
    universe = {
        "stock_codes": ["000001.SZ", "000002.SZ", "000003.SZ"],
        "prioritized_stock_codes": ["000003.SZ", "000001.SZ"],
        "etf_codes": [],
        "index_codes": ["000001.SH"],
    }
    filtered = backfill_module._filter_universe(
        universe,
        stage="stock",
        max_stocks=2,
        only_codes=[],
        selection_priority="leading_cluster",
    )
    assert filtered["stock_codes"] == ["000003.SZ", "000001.SZ"]
    assert filtered["selection_priority"] == "leading_cluster"


def test_filter_universe_only_codes_still_beats_priority_order():
    universe = {
        "stock_codes": ["000001.SZ", "000002.SZ", "000003.SZ"],
        "prioritized_stock_codes": ["000003.SZ", "000001.SZ", "000002.SZ"],
        "etf_codes": [],
        "index_codes": ["000001.SH"],
    }
    filtered = backfill_module._filter_universe(
        universe,
        stage="stock",
        max_stocks=2,
        only_codes=["000002.SZ"],
        selection_priority="leading_cluster",
    )
    assert filtered["stock_codes"] == ["000002.SZ"]
    assert filtered["selected_stock_preview"] == ["000002.SZ"]
