import pandas as pd

from reports.t1_backtest import T1BacktestConfig, T1BacktestRunner
from reports.intraday_excursion import compute_intraday_excursion_fields
from runners.auction import AuctionRunner


def test_normal_ohlc_row_computes_excursion_fields():
    fields = compute_intraday_excursion_fields({"open": 10, "high": 11, "low": 9.5, "close": 10.5})

    assert fields["open_to_high_pct"] == 10.0
    assert fields["open_to_low_pct"] == -5.0
    assert fields["close_to_high_drawdown_pct"] == -4.5455
    assert fields["intraday_range_pct"] == 15.7895
    assert fields["mfe_pct"] == fields["open_to_high_pct"]
    assert fields["mae_pct"] == fields["open_to_low_pct"]


def test_one_way_selloff_classification():
    fields = compute_intraday_excursion_fields({"open": 10, "high": 10.05, "low": 9.0, "close": 9.2})

    assert fields["signal_path_type"] == "one_way_selloff"


def test_high_open_trap_classification_uses_positive_auction_context():
    fields = compute_intraday_excursion_fields(
        {"open": 10, "high": 10.5, "low": 9.7, "close": 9.9},
        auction_pct=1.2,
    )

    assert fields["signal_path_type"] == "high_open_trap"


def test_low_open_rebound_failed_classification_uses_nonpositive_auction_context():
    fields = compute_intraday_excursion_fields(
        {"open": 10, "high": 10.4, "low": 9.8, "close": 10.0},
        auction_pct=-1.0,
    )

    assert fields["signal_path_type"] == "low_open_rebound_failed"


def test_rush_up_fade_classification_without_auction_context():
    fields = compute_intraday_excursion_fields({"open": 10, "high": 10.5, "low": 9.9, "close": 10.0})

    assert fields["signal_path_type"] == "rush_up_fade"


def test_missing_ohlc_returns_unknown_without_crashing():
    fields = compute_intraday_excursion_fields({"open": 10, "close": 9})

    assert fields["open_to_high_pct"] is None
    assert fields["signal_path_type"] == "unknown"


def test_invalid_open_returns_unknown_without_crashing():
    fields = compute_intraday_excursion_fields({"open": 0, "high": 10, "low": 9, "close": 9.5})

    assert fields["open_to_high_pct"] is None
    assert fields["signal_path_type"] == "unknown"


def test_pandas_series_input_is_supported():
    row = pd.Series({"open": 10, "high": 10.2, "low": 9.8, "close": 10.18})
    fields = compute_intraday_excursion_fields(row)

    assert fields["signal_path_type"] == "close_near_high"


def test_auction_validation_record_exposes_excursion_fields():
    runner = AuctionRunner()
    records = runner._build_validation_records(
        {
            "date": 20260702,
            "data_status": {"session_state": "closed", "post_close_validation": True},
            "signals": {
                "trap": [
                    {
                        "signal": "CP",
                        "type": "ETF",
                        "name": "A",
                        "data": {
                            "code": "159999.SZ",
                            "open": 10,
                            "high": 10.5,
                            "low": 9.7,
                            "close": 9.9,
                            "auction_pct": 1.2,
                            "close_pct": -1.0,
                            "body_pct": -1.0,
                        },
                    }
                ]
            },
        }
    )

    assert records[0]["open_to_high_pct"] == 5.0
    assert records[0]["close_to_high_drawdown_pct"] == -5.7143
    assert records[0]["signal_path_type"] == "high_open_trap"


def test_t1_outcome_exposes_prefixed_excursion_fields(tmp_path):
    store = tmp_path / "store"
    for date, close in [("20260701", 10.0), ("20260702", 9.9)]:
        day = store / date
        day.mkdir(parents=True)
        pd.DataFrame(
            [
                {
                    "code": "000001.SZ",
                    "name": "A",
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.7,
                    "close": close,
                }
            ]
        ).to_csv(day / "stocks.csv", index=False)
        pd.DataFrame(
            [
                {
                    "code": "000001.SH",
                    "open": 1.0,
                    "high": 1.0,
                    "low": 1.0,
                    "close": 1.0,
                }
            ]
        ).to_csv(day / "indices.csv", index=False)

    runner = T1BacktestRunner(T1BacktestConfig(store_root=str(store)))
    row = pd.Series(
        {
            "date": "20260701",
            "signal_category": "trend",
            "target_type": "stock",
            "universe_type": "stock",
            "code": "000001.SZ",
            "name": "A",
        }
    )

    outcome = runner._build_outcome(row)

    assert outcome["t_open_to_high_pct"] == 5.0
    assert outcome["t_signal_path_type"] == "rush_up_fade"
    assert outcome["t1_open_to_low_pct"] == -3.0
    assert outcome["t1_signal_path_type"] == "rush_up_fade"
