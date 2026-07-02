from pathlib import Path

import pandas as pd

import scripts.evaluate_rolling_t1_validation as rolling


def _write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _patch_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(rolling, "MANUAL_PATCH_ROOT", tmp_path / "manual")
    monkeypatch.setattr(rolling, "CODE_BACKFILLED_ROOT", tmp_path / "backfilled")
    monkeypatch.setattr(rolling, "ORIGINAL_DAILY_ROOT", tmp_path / "daily")
    monkeypatch.setattr(rolling, "EVAL_ROOT", tmp_path / "eval")
    monkeypatch.setattr(rolling, "OUTPUT_ROOT", tmp_path / "out")
    import scripts.backfill_signal_detail_code_temp_copy as source

    monkeypatch.setattr(source, "REPORTS_DAILY", tmp_path / "reports")
    monkeypatch.setattr(source, "STORE_ROOT", tmp_path / "store")


def test_manual_code_patch_has_priority(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    date = "20260630"
    _write_csv(tmp_path / "manual" / f"{date}_signal_detail.manual_code_patch.csv", [{"name": "manual"}])
    _write_csv(tmp_path / "backfilled" / f"{date}_signal_detail.code_backfilled.csv", [{"name": "backfilled"}])

    selected = rolling.select_signal_detail(date)

    assert selected["input_quality"] == "manual_code_patch"
    assert "manual_code_patch" in selected["input_file"]


def test_code_backfilled_has_priority_over_original(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    date = "20260630"
    _write_csv(tmp_path / "backfilled" / f"{date}_signal_detail.code_backfilled.csv", [{"name": "backfilled"}])
    _write_csv(tmp_path / "daily" / date / "signal_detail.csv", [{"name": "original"}])

    selected = rolling.select_signal_detail(date)

    assert selected["input_quality"] == "code_backfilled"
    assert selected["input_quality_degraded"] is False


def test_original_fallback_marks_quality_degraded(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    date = "20260630"
    _write_csv(tmp_path / "daily" / date / "signal_detail.csv", [{"name": "original"}])

    selected = rolling.select_signal_detail(date)

    assert selected["input_quality"] == "original_signal_detail"
    assert selected["input_quality_degraded"] is True


def test_pair_join_quality_and_signal_summary(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    prev = "20260630"
    date = "20260701"
    _write_csv(tmp_path / "manual" / f"{prev}_signal_detail.manual_code_patch.csv", [{"name": "A", "code": "000001.SZ", "signal_family": "CP风险"}])
    _write_csv(tmp_path / "reports" / date / "factor_snapshot_stock.csv", [{"name": "A", "code": "000001.SZ", "auction_pct": 1, "close_pct": -2}])

    pair = rolling.build_pair(prev, date)

    assert pair["join_quality"]["primary_code_join_count"] == 1
    assert pair["join_quality"]["quality"] == "code_keyed_complete"
    assert pair["signal_type_summary"]["CP风险"]["negative_count"] == 1


def test_aggregate_summary_is_stable(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _write_csv(tmp_path / "manual" / "20260630_signal_detail.manual_code_patch.csv", [{"name": "A", "code": "000001.SZ", "signal_family": "趋势机会"}])
    _write_csv(tmp_path / "manual" / "20260701_signal_detail.manual_code_patch.csv", [{"name": "B", "code": "000002.SZ", "signal_family": "趋势机会"}])
    _write_csv(tmp_path / "reports" / "20260701" / "factor_snapshot_stock.csv", [{"name": "A", "code": "000001.SZ", "auction_pct": 1, "close_pct": 2}])

    payload = rolling.build_payload("20260630", "20260701")

    assert payload["aggregate_join_quality"]["total_primary_code_join_count"] == 1
    assert payload["signal_type_aggregate_summary"]["趋势机会"]["resolved_count"] == 1


def test_observations_do_not_support_rule_or_trend_active(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _write_csv(tmp_path / "manual" / "20260630_signal_detail.manual_code_patch.csv", [{"name": "A", "code": "000001.SZ", "signal_family": "趋势机会"}])
    _write_csv(tmp_path / "reports" / "20260701" / "factor_snapshot_stock.csv", [{"name": "A", "code": "000001.SZ", "auction_pct": 1, "close_pct": 2}])

    payload = rolling.build_payload("20260630", "20260701")

    assert payload["observations"]["趋势机会"]["trend_active_supported"] is False
    assert payload["sample_size_sufficient_for_rule_change"] is False
    assert payload["cp_evaluator_change_required"] is False
    assert payload["trend_evaluator_change_required"] is False
    assert payload["lesson_pattern_written"] is False
    assert "sample_size_insufficient_for_rule_change" in payload["conclusion"]
