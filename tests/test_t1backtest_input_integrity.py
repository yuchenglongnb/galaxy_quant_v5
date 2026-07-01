import csv
import json
from pathlib import Path

import pandas as pd

import scripts.evaluate_t1backtest_input_integrity as audit
import scripts.repair_t1backtest_input_integrity as repair
from reports.t1_backtest import T1BacktestConfig, T1BacktestRunner


def _write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _write_malformed_csv(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "signal_category", "target_type", "name"])
        writer.writerow(["20260630", "trend", "个股", "A"])
        writer.writerow(["20260630", "trend", "个股", "B", "extra"])


def test_malformed_csv_line_is_identified(tmp_path):
    path = tmp_path / "validation.csv"
    _write_malformed_csv(path)

    result = audit.scan_malformed_csv(path)

    assert result["line"] == 3
    assert result["expected_fields"] == 4
    assert result["actual_fields"] == 5
    assert result["quarantine_recommended"] is True


def test_t1_runner_skips_malformed_line_without_crashing(tmp_path):
    store = tmp_path / "store"
    validation = tmp_path / "validation.csv"
    output = tmp_path / "out"
    _write_malformed_csv(validation)
    _write_quotes(store, "20260630", "000001.SZ", "A")
    _write_quotes(store, "20260701", "000001.SZ", "A")

    runner = T1BacktestRunner(
        T1BacktestConfig(
            validation_path=str(validation),
            store_root=str(store),
            output_root=str(output),
            actionable_only=False,
        )
    )
    detail = runner._load_detail("20260630", "20260630")

    assert len(detail) == 1
    assert runner.bad_validation_rows[0]["line"] == 3


def test_signal_detail_missing_code_is_detected_and_filled(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    prev_date = "20260630"
    _write_csv(
        tmp_path / "reports" / "validation" / "daily" / prev_date / "signal_detail.csv",
        [{"date": prev_date, "signal_family": "趋势机会", "signal_category": "trend", "name": "A"}],
    )
    _write_csv(
        tmp_path / "reports" / "validation" / "daily" / prev_date / "factor_snapshot_stock.csv",
        [{"date": prev_date, "code": "000001.SZ", "name": "A", "auction_pct": 1, "close_pct": 2}],
    )

    detail = audit.daily_signal_detail(prev_date)
    filled, stats = audit.fill_codes(detail, prev_date)

    assert "code" not in detail.columns
    assert filled.iloc[0]["code"] == "000001.SZ"
    assert stats["filled_count"] == 1
    assert stats["fallback_name_match_count"] == 1


def test_code_keyed_join_has_priority_over_name_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    date = "20260701"
    detail = pd.DataFrame(
        [
            {"signal_family": "趋势机会", "signal_category": "trend", "code": "000001.SZ", "name": "A"},
            {"signal_family": "趋势机会", "signal_category": "trend", "code": "", "name": "B"},
        ]
    )
    _write_csv(
        tmp_path / "reports" / "validation" / "daily" / date / "factor_snapshot_stock.csv",
        [
            {"date": date, "code": "000001.SZ", "name": "A-new", "auction_pct": 1.0, "close_pct": 2.0},
            {"date": date, "code": "000002.SZ", "name": "B", "auction_pct": 3.0, "close_pct": 4.0},
        ],
    )

    joined, stats = audit.join_t1(detail, date)

    assert stats["primary_code_join_count"] == 1
    assert stats["fallback_name_join_count"] == 1
    assert joined.loc[0, "t1_join_method"] == "code"
    assert joined.loc[1, "t1_join_method"] == "name_fallback"


def test_ambiguous_name_not_silently_matched(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    prev_date = "20260630"
    _write_csv(
        tmp_path / "reports" / "validation" / "daily" / prev_date / "factor_snapshot_stock.csv",
        [
            {"date": prev_date, "code": "000001.SZ", "name": "A"},
            {"date": prev_date, "code": "000002.SZ", "name": "A"},
        ],
    )
    detail = pd.DataFrame([{"name": "A", "signal_category": "trend"}])

    filled, stats = audit.fill_codes(detail, prev_date)

    assert filled.iloc[0]["code"] == ""
    assert stats["ambiguous_name_count"] == 1


def test_repair_dry_run_does_not_overwrite_original(tmp_path):
    path = tmp_path / "validation.csv"
    _write_malformed_csv(path)
    original = path.read_text(encoding="utf-8-sig")

    result = repair.scan_and_optionally_repair(path, dry_run=True)

    assert result["dry_run"] is True
    assert result["original_overwritten"] is False
    assert path.read_text(encoding="utf-8-sig") == original


def test_build_payload_conclusions(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "EVAL_ROOT", tmp_path / "eval")
    validation = tmp_path / "reports" / "validation" / "auction_signal_validation.csv"
    monkeypatch.setattr(audit, "VALIDATION_PATH", validation)
    _write_malformed_csv(validation)
    prev_date = "20260630"
    date = "20260701"
    _write_csv(
        tmp_path / "reports" / "validation" / "daily" / prev_date / "signal_detail.csv",
        [{"date": prev_date, "signal_family": "趋势机会", "signal_category": "trend", "name": "A"}],
    )
    _write_csv(
        tmp_path / "reports" / "validation" / "daily" / prev_date / "factor_snapshot_stock.csv",
        [{"date": prev_date, "code": "000001.SZ", "name": "A"}],
    )
    _write_csv(
        tmp_path / "reports" / "validation" / "daily" / date / "factor_snapshot_stock.csv",
        [{"date": date, "code": "000001.SZ", "name": "A", "auction_pct": 1.0, "close_pct": 2.0}],
    )

    payload = audit.build_payload(prev_date, date)

    assert payload["signal_detail_schema"]["has_code"] is False
    assert payload["t1_join_analysis"]["primary_code_join_count"] == 1
    assert "code_keyed_join_required" in payload["conclusion"]
    assert "signal_detail_code_missing" in payload["conclusion"]


def _write_quotes(store: Path, date: str, code: str, name: str):
    day = store / date
    day.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [{"code": code, "name": name, "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05}]
    ).to_csv(day / "stocks.csv", index=False, encoding="utf-8-sig")
