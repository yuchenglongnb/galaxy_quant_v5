import csv
import json
from pathlib import Path

from scripts import collect_0935_feedback as hook


def _write_csv(path: Path, fields: list[str], rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _candidate_fields():
    return ["date", "code", "name", "target_type", "signal_category", "signal_family"]


def _confirmation_fields():
    return [
        "code",
        "name",
        "time_int",
        "time_str",
        "pre_close",
        "open",
        "last",
        "pct",
        "price_vs_open_pct",
        "amount_1m_ratio",
        "rs_vs_index_pct",
        "rs_vs_etf_pct",
        "volume_price_state",
        "benchmark_etf_code",
        "benchmark_index_code",
        "benchmark_source",
    ]


def test_dry_run_no_write(tmp_path):
    candidate = tmp_path / "reports" / "validation" / "daily" / "20260703" / "signal_detail.csv"
    _write_csv(candidate, _candidate_fields(), [{"date": "20260703", "code": "000001.SZ", "name": "sample"}])
    result = hook.collect_for_date(
        "20260703",
        validation_root=tmp_path / "reports" / "validation" / "daily",
        store_root=tmp_path / "AmazingData_Store",
        dry_run=True,
    )
    assert result["candidate_count"] == 1
    assert result["would_write"] is False
    assert not (tmp_path / "AmazingData_Store" / "20260703" / "intraday" / "stock_confirmation_0935.csv").exists()


def test_local_existing_confirmation_standardizes_0935_csv(tmp_path):
    candidate = tmp_path / "reports" / "validation" / "daily" / "20260703" / "signal_detail.csv"
    latest = tmp_path / "AmazingData_Store" / "20260703" / "intraday" / "stock_confirmation_latest.csv"
    _write_csv(candidate, _candidate_fields(), [{"date": "20260703", "code": "000001.SZ", "name": "sample", "target_type": "stock", "signal_category": "trend", "signal_family": "趋势机会"}])
    _write_csv(
        latest,
        _confirmation_fields(),
        [{"code": "000001.SZ", "name": "sample", "time_int": "935", "time_str": "09:35:00", "pre_close": "9.8", "open": "10", "last": "10.5", "pct": "7.1", "price_vs_open_pct": "5.0", "amount_1m_ratio": "1.2", "rs_vs_index_pct": "0.8", "volume_price_state": "up_with_amount", "benchmark_index_code": "000001.SH", "benchmark_source": "market_index"}],
    )
    result = hook.collect_for_date(
        "20260703",
        validation_root=tmp_path / "reports" / "validation" / "daily",
        store_root=tmp_path / "AmazingData_Store",
    )
    assert result["matched_count"] == 1
    output = tmp_path / "AmazingData_Store" / "20260703" / "intraday" / "stock_confirmation_0935.csv"
    rows = list(csv.DictReader(output.open(encoding="utf-8")))
    assert rows[0]["data_available"] == "True"
    assert rows[0]["price_vs_open_pct"] == "5.0"
    meta = json.loads((tmp_path / "AmazingData_Store" / "20260703" / "intraday" / "stock_confirmation_0935_meta.json").read_text(encoding="utf-8"))
    assert meta["matched_count"] == 1
    assert "labels_are_feedback_evidence_not_trading_instructions" in meta["notes"]


def test_missing_confirmation_writes_gap_rows_and_meta(tmp_path):
    candidate = tmp_path / "reports" / "validation" / "daily" / "20260703" / "signal_detail.csv"
    _write_csv(candidate, _candidate_fields(), [{"date": "20260703", "code": "000001.SZ", "name": "sample"}])
    hook.collect_for_date(
        "20260703",
        validation_root=tmp_path / "reports" / "validation" / "daily",
        store_root=tmp_path / "AmazingData_Store",
        mode="gap-only",
    )
    output = tmp_path / "AmazingData_Store" / "20260703" / "intraday" / "stock_confirmation_0935.csv"
    rows = list(csv.DictReader(output.open(encoding="utf-8")))
    assert rows[0]["data_available"] == "False"
    assert rows[0]["missing_reason"] == "missing_local_confirmation_match"
    meta = json.loads((tmp_path / "AmazingData_Store" / "20260703" / "intraday" / "stock_confirmation_0935_meta.json").read_text(encoding="utf-8"))
    assert meta["missing_count"] == 1


def test_name_fallback_join(tmp_path):
    candidate = tmp_path / "reports" / "validation" / "daily" / "20260703" / "signal_detail.csv"
    latest = tmp_path / "AmazingData_Store" / "20260703" / "intraday" / "stock_confirmation_latest.csv"
    _write_csv(candidate, _candidate_fields(), [{"date": "20260703", "name": "sample_name"}])
    _write_csv(latest, _confirmation_fields(), [{"code": "000002.SZ", "name": "sample_name", "last": "12.3"}])
    result = hook.collect_for_date(
        "20260703",
        validation_root=tmp_path / "reports" / "validation" / "daily",
        store_root=tmp_path / "AmazingData_Store",
    )
    assert result["matched_count"] == 1
    rows = list(csv.DictReader((tmp_path / "AmazingData_Store" / "20260703" / "intraday" / "stock_confirmation_0935.csv").open(encoding="utf-8")))
    assert rows[0]["code"] == "000002.SZ"


def test_no_overwrite_latest_unless_explicit(tmp_path):
    candidate = tmp_path / "reports" / "validation" / "daily" / "20260703" / "signal_detail.csv"
    latest = tmp_path / "AmazingData_Store" / "20260703" / "intraday" / "stock_confirmation_latest.csv"
    _write_csv(candidate, _candidate_fields(), [{"date": "20260703", "code": "000001.SZ", "name": "sample"}])
    _write_csv(latest, _confirmation_fields(), [{"code": "000001.SZ", "name": "sample", "last": "10.0"}])
    before = latest.read_text(encoding="utf-8")
    hook.collect_for_date(
        "20260703",
        validation_root=tmp_path / "reports" / "validation" / "daily",
        store_root=tmp_path / "AmazingData_Store",
    )
    assert latest.read_text(encoding="utf-8") == before


def test_no_forbidden_output_paths_or_secrets(tmp_path):
    candidate = tmp_path / "reports" / "validation" / "daily" / "20260703" / "signal_detail.csv"
    _write_csv(candidate, _candidate_fields(), [{"date": "20260703", "code": "000001.SZ", "name": "sample"}])
    hook.collect_for_date(
        "20260703",
        validation_root=tmp_path / "reports" / "validation" / "daily",
        store_root=tmp_path / "AmazingData_Store",
        mode="gap-only",
    )
    combined = ""
    for path in (tmp_path / "AmazingData_Store" / "20260703" / "intraday").glob("stock_confirmation_0935*"):
        combined += path.read_text(encoding="utf-8")
    for forbidden in ["reports/analysis/lessons", "reports/analysis/patterns", "market_pattern_registry.json", "password", "token", "secret"]:
        assert forbidden not in combined
