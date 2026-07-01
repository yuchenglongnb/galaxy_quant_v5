from pathlib import Path

import pandas as pd

import scripts.evaluate_signal_detail_code_backfill_policy as policy


def _write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def test_native_code_has_priority(tmp_path, monkeypatch):
    monkeypatch.setattr(policy, "REPORTS_DAILY", tmp_path / "reports")
    monkeypatch.setattr(policy, "STORE_ROOT", tmp_path / "store")
    date = "20260701"
    _write_csv(
        tmp_path / "reports" / date / "signal_detail.csv",
        [{"name": "A", "code": "000001.SZ", "signal_category": "trend"}],
    )
    _write_csv(
        tmp_path / "reports" / date / "factor_snapshot_stock.csv",
        [{"name": "A", "code": "000002.SZ"}],
    )

    result = policy.analyze_date(date)

    assert result["native_code_count"] == 1
    assert result["backfillable_code_count"] == 0
    assert result["fill_method_counts"]["native_code"] == 1


def test_factor_snapshot_code_backfill_is_counted(tmp_path, monkeypatch):
    monkeypatch.setattr(policy, "REPORTS_DAILY", tmp_path / "reports")
    monkeypatch.setattr(policy, "STORE_ROOT", tmp_path / "store")
    date = "20260701"
    _write_csv(
        tmp_path / "reports" / date / "signal_detail.csv",
        [{"name": "A", "signal_category": "trend"}],
    )
    _write_csv(
        tmp_path / "reports" / date / "factor_snapshot_stock.csv",
        [{"name": "A", "code": "000001.SZ"}],
    )

    result = policy.analyze_date(date)

    assert result["backfillable_code_count"] == 1
    assert result["name_fallback_count"] == 1
    assert result["unfilled_count"] == 0


def test_ambiguous_name_is_not_silently_matched(tmp_path, monkeypatch):
    monkeypatch.setattr(policy, "REPORTS_DAILY", tmp_path / "reports")
    monkeypatch.setattr(policy, "STORE_ROOT", tmp_path / "store")
    date = "20260701"
    _write_csv(
        tmp_path / "reports" / date / "signal_detail.csv",
        [{"name": "A", "signal_category": "trend"}],
    )
    _write_csv(
        tmp_path / "reports" / date / "factor_snapshot_stock.csv",
        [{"name": "A", "code": "000001.SZ"}, {"name": "A", "code": "000002.SZ"}],
    )

    result = policy.analyze_date(date)

    assert result["backfillable_code_count"] == 0
    assert result["ambiguous_name_count"] == 1
    assert result["unfilled_count"] == 0


def test_policy_payload_does_not_modify_original_files(tmp_path, monkeypatch):
    monkeypatch.setattr(policy, "REPORTS_DAILY", tmp_path / "reports")
    monkeypatch.setattr(policy, "STORE_ROOT", tmp_path / "store")
    date = "20260701"
    _write_csv(
        tmp_path / "reports" / date / "signal_detail.csv",
        [{"name": "A", "signal_category": "trend"}],
    )
    _write_csv(
        tmp_path / "reports" / date / "factor_snapshot_stock.csv",
        [{"name": "A", "code": "000001.SZ"}],
    )

    payload = policy.build_payload(date, date)

    assert payload["original_files_modified"] is False
    assert payload["backfillable_code_count"] == 1
    assert "code_keyed_join_required" in payload["conclusion"]
    assert "cp_evaluator_change_not_required" in payload["conclusion"]
    assert "trend_evaluator_change_not_required" in payload["conclusion"]
