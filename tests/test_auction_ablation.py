import pandas as pd

from reports.auction_ablation import AuctionAblationRunner


def test_ablation_uses_directed_body_as_primary_metric(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    validation_path = tmp_path / "validation.csv"
    rows = [
        _row("trap", "ETF", "A", body_pct=-2.0, cp=90, amt_rank=1),
        _row("trap", "ETF", "B", body_pct=1.0, cp=80, amt_rank=2),
        _row("trend", "个股", "C", body_pct=3.0, prev_pct=5, amt_rank=1),
        _row("trend", "个股", "D", body_pct=-1.0, prev_pct=4, amt_rank=2),
    ]
    pd.DataFrame(rows).to_csv(validation_path, index=False, encoding="utf-8-sig")
    runner = AuctionAblationRunner(str(validation_path), str(tmp_path / "out"))

    result = runner.run("20260529", "20260529")
    baseline = result["summary"][result["summary"]["experiment_id"] == "B0"].set_index("signal_category")

    assert baseline.loc["trap", "avg_directed_body_pct"] == 0.5
    assert baseline.loc["trend", "avg_directed_body_pct"] == 1.0
    assert baseline.loc["trap", "direction_hit_rate"] == 50.0


def test_topk_three_expands_trend_observation_selection(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    validation_path = tmp_path / "validation.csv"
    rows = [
        _row("trend", "个股", "A", body_pct=1.0, prev_pct=5, amt_rank=1),
        _row("trend", "个股", "B", body_pct=2.0, prev_pct=4, amt_rank=2),
        _row("trend", "个股", "C", body_pct=3.0, prev_pct=3, amt_rank=3),
    ]
    pd.DataFrame(rows).to_csv(validation_path, index=False, encoding="utf-8-sig")
    runner = AuctionAblationRunner(str(validation_path), str(tmp_path / "out"))

    result = runner.run("20260529", "20260529")
    summary = result["summary"].set_index(["experiment_id", "signal_category"])

    assert summary.loc[("B0", "trend"), "selected_count"] == 1
    assert summary.loc[("K01", "trend"), "selected_count"] == 1
    assert summary.loc[("K03", "trend"), "selected_count"] == 3


def test_legacy_shortlist_reason_restores_online_rank_bonus():
    row = pd.Series({"amt_rank": 4, "shortlist_reason": "regime=mixed; rank_bonus=0.0"})

    assert AuctionAblationRunner._rank_bonus(row) == 0.0


def test_data_universe_mode_distinguishes_compact_stock_pool(tmp_path):
    store_root = tmp_path / "store"
    day_dir = store_root / "20260529"
    day_dir.mkdir(parents=True)
    (day_dir / "stocks.csv").write_text("code\n000001.SZ\n", encoding="utf-8-sig")

    runner = AuctionAblationRunner(store_root=str(store_root))

    assert runner._detect_data_universe_mode("20260529") == "stock_pool"


def test_ablation_writes_layered_reversal_and_stability_outputs(tmp_path):
    validation_path = tmp_path / "validation.csv"
    first = _row("reversal", "指数", "创业板", body_pct=1.5, sa=80, amt_rank=1)
    second = _row("reversal", "ETF", "科创50ETF", body_pct=0.8, sa=70, amt_rank=2)
    for row in (first, second):
        row.update({
            "auction_pct": -1.0,
            "pos_5d": 10,
            "market_regime": "risk_off",
            "scenario": "REVERSAL_OVERSOLD",
        })
    pd.DataFrame([first, second]).to_csv(validation_path, index=False, encoding="utf-8-sig")
    runner = AuctionAblationRunner(str(validation_path), str(tmp_path / "out"))

    result = runner.run("20260529", "20260529")
    output_dir = tmp_path / "out" / "20260529_20260529"
    layer_summary = pd.read_csv(output_dir / "reversal_layer_summary.csv", encoding="utf-8-sig")

    assert (output_dir / "universe_topk_summary.csv").exists()
    assert (output_dir / "experiment_event_summary.csv").exists()
    assert (output_dir / "experiment_monthly_walk_forward.csv").exists()
    assert set(layer_summary["universe_type"]) == {"index", "ETF"}
    assert set(result["paths"]) >= {"universe_topk", "event_summary", "monthly", "reversal_layers"}


def _row(category, target_type, name, body_pct, amt_rank, cp=None, sa=None, prev_pct=1.0):
    return {
        "date": "20260529",
        "signal_category": category,
        "target_type": target_type,
        "name": name,
        "body_pct": body_pct,
        "auction_pct": 0.5,
        "prev_pct": prev_pct,
        "prev_vol_ratio": 2.0,
        "pos_5d": 80,
        "amt_rank": amt_rank,
        "cp": cp,
        "sa": sa,
        "market_regime": "mixed",
        "scenario": "TRAP_HOT_SECTOR" if category == "trap" else (
            "REVERSAL_GENERIC" if category == "reversal" else "TREND_ACCELERATE"
        ),
        "validation_scope": "post_close_final",
    }
