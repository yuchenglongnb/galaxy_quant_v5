# -*- coding: utf-8 -*-

import pandas as pd

from reports.t1_backtest import T1BacktestConfig, T1BacktestRunner


def test_t1_backtest_calculates_executable_etf_returns(tmp_path):
    store = tmp_path / "store"
    validation = tmp_path / "validation.csv"
    output = tmp_path / "out"
    _write_quotes(store, "20260528", "515790.SH", 1.0, 1.1, 0.9, 1.05)
    _write_quotes(store, "20260529", "515790.SH", 1.02, 1.2, 0.95, 1.1)
    pd.DataFrame([_signal("20260528", "reversal", "ETF", "光伏")]).to_csv(
        validation, index=False, encoding="utf-8-sig"
    )

    runner = T1BacktestRunner(T1BacktestConfig(
        validation_path=str(validation),
        store_root=str(store),
        output_root=str(output),
    ))
    result = runner.run("20260528", "20260528")
    trade = result["trades"].iloc[0]

    assert trade["entry_source"] == "daily_open_proxy"
    assert trade["t1_open_return_pct"] == 2.0
    assert trade["t1_close_return_pct"] == 10.0
    assert trade["holding_mae_pct"] == -10.0
    assert trade["holding_mfe_pct"] == 20.0


def test_intraday_entry_mode_uses_persisted_0935_snapshot_without_fallback(tmp_path):
    store = tmp_path / "store"
    validation = tmp_path / "validation.csv"
    output = tmp_path / "out"
    _write_quotes(store, "20260528", "515790.SH", 1.0, 1.1, 0.9, 1.05)
    _write_quotes(store, "20260529", "515790.SH", 1.02, 1.2, 0.95, 1.1)
    intraday = store / "20260528" / "intraday"
    intraday.mkdir()
    pd.DataFrame([
        {"code": "515790.SH", "time_int": 934, "last": 1.01},
        {"code": "515790.SH", "time_int": 935, "last": 1.04},
    ]).to_csv(intraday / "etf_1min.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([_signal("20260528", "reversal", "ETF", "光伏")]).to_csv(
        validation, index=False, encoding="utf-8-sig"
    )

    runner = T1BacktestRunner(T1BacktestConfig(
        validation_path=str(validation),
        store_root=str(store),
        output_root=str(output),
        entry_mode="intraday_0935",
    ))
    result = runner.run("20260528", "20260528")
    trade = result["trades"].iloc[0]

    assert trade["entry_source"] == "snapshot_at_or_after_935"
    assert trade["entry_price"] == 1.04
    assert round(trade["t1_open_return_pct"], 4) == -1.9231


def _write_quotes(store, date, code, open_price, high, low, close):
    day = store / date
    day.mkdir(parents=True)
    pd.DataFrame([{
        "code": code,
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "pre_close": open_price,
    }]).to_csv(day / "indices.csv", index=False, encoding="utf-8-sig")


def _signal(date, category, target_type, name):
    return {
        "date": date,
        "signal_category": category,
        "target_type": target_type,
        "name": name,
        "scenario": "REVERSAL_OVERSOLD",
        "market_regime": "risk_off",
        "actionable": True,
        "validation_scope": "post_close_final",
    }
