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


def test_collection_does_not_self_read_0935_by_default(tmp_path):
    candidate = tmp_path / "reports" / "validation" / "daily" / "20260703" / "signal_detail.csv"
    existing_0935 = tmp_path / "AmazingData_Store" / "20260703" / "intraday" / "stock_confirmation_0935.csv"
    _write_csv(candidate, _candidate_fields(), [{"date": "20260703", "code": "000001.SZ", "name": "sample"}])
    _write_csv(existing_0935, _confirmation_fields(), [{"code": "000001.SZ", "name": "sample", "last": "10.0"}])
    result = hook.collect_for_date(
        "20260703",
        validation_root=tmp_path / "reports" / "validation" / "daily",
        store_root=tmp_path / "AmazingData_Store",
        dry_run=True,
    )
    assert result["matched_count"] == 0
    assert result["confirmation_source"] == ""


def test_collection_can_explicitly_read_0935_source(tmp_path):
    candidate = tmp_path / "reports" / "validation" / "daily" / "20260703" / "signal_detail.csv"
    existing_0935 = tmp_path / "AmazingData_Store" / "20260703" / "intraday" / "stock_confirmation_0935.csv"
    _write_csv(candidate, _candidate_fields(), [{"date": "20260703", "code": "000001.SZ", "name": "sample"}])
    _write_csv(existing_0935, _confirmation_fields(), [{"code": "000001.SZ", "name": "sample", "last": "10.0"}])
    result = hook.collect_for_date(
        "20260703",
        validation_root=tmp_path / "reports" / "validation" / "daily",
        store_root=tmp_path / "AmazingData_Store",
        source_confirmation_file=str(existing_0935),
        dry_run=True,
    )
    assert result["matched_count"] == 1
    assert result["confirmation_source"].endswith("stock_confirmation_0935.csv")


def test_online_query_mode_requires_explicit_allow(tmp_path):
    candidate = tmp_path / "reports" / "validation" / "daily" / "20260703" / "signal_detail.csv"
    _write_csv(candidate, _candidate_fields(), [{"date": "20260703", "code": "000001.SZ", "name": "sample"}])
    result = hook.collect_for_date(
        "20260703",
        validation_root=tmp_path / "reports" / "validation" / "daily",
        store_root=tmp_path / "AmazingData_Store",
        mode="historical-snapshot-query",
        dry_run=True,
    )
    assert result["status"] == "online_query_not_allowed"
    assert result["would_write"] is False
    assert not (tmp_path / "AmazingData_Store" / "20260703" / "intraday" / "stock_confirmation_0935.csv").exists()


def test_historical_snapshot_query_can_be_mocked(tmp_path, monkeypatch):
    candidate = tmp_path / "reports" / "validation" / "daily" / "20260703" / "signal_detail.csv"
    _write_csv(candidate, _candidate_fields(), [{"date": "20260703", "code": "000001.SZ", "name": "sample"}])
    monkeypatch.setattr(
        hook,
        "_query_historical_snapshot_rows",
        lambda codes, date, start, end, config: [{"code": "000001.SZ", "name": "sample", "trade_time": "2026-07-03 09:35:00", "open": "10", "last": "10.4"}],
    )
    result = hook.collect_for_date(
        "20260703",
        validation_root=tmp_path / "reports" / "validation" / "daily",
        store_root=tmp_path / "AmazingData_Store",
        mode="historical-snapshot-query",
        allow_online_query=True,
    )
    rows = list(csv.DictReader((tmp_path / "AmazingData_Store" / "20260703" / "intraday" / "stock_confirmation_0935.csv").open(encoding="utf-8")))
    assert result["matched_count"] == 1
    assert rows[0]["data_source"] == "amazingdata_query_snapshot"
    assert rows[0]["time_int"] == "93500"
    assert rows[0]["price_vs_open_pct"] == "4.0000"
    meta = json.loads((tmp_path / "AmazingData_Store" / "20260703" / "intraday" / "stock_confirmation_0935_meta.json").read_text(encoding="utf-8"))
    assert meta["collection_mode"] == "historical-snapshot-query"
    assert meta["timepoint_policy"] == "strict_0935_snapshot"
    assert meta["strict_point_snapshot"] is True


def test_historical_min1_query_can_be_mocked(tmp_path, monkeypatch):
    candidate = tmp_path / "reports" / "validation" / "daily" / "20260703" / "signal_detail.csv"
    _write_csv(candidate, _candidate_fields(), [{"date": "20260703", "code": "000001.SZ", "name": "sample"}])
    monkeypatch.setattr(
        hook,
        "_query_historical_min1_rows",
        lambda codes, date, config: [{"code": "000001.SZ", "name": "sample", "kline_time": "2026-07-03 09:35:00", "open": "10", "close": "9.8"}],
    )
    result = hook.collect_for_date(
        "20260703",
        validation_root=tmp_path / "reports" / "validation" / "daily",
        store_root=tmp_path / "AmazingData_Store",
        mode="historical-min1-kline",
        allow_online_query=True,
    )
    rows = list(csv.DictReader((tmp_path / "AmazingData_Store" / "20260703" / "intraday" / "stock_confirmation_0935.csv").open(encoding="utf-8")))
    assert result["matched_count"] == 1
    assert rows[0]["data_source"] == "amazingdata_query_kline_min1"
    assert rows[0]["time_int"] == "93500"
    assert rows[0]["price_vs_open_pct"] == "-2.0000"
    meta = json.loads((tmp_path / "AmazingData_Store" / "20260703" / "intraday" / "stock_confirmation_0935_meta.json").read_text(encoding="utf-8"))
    assert meta["timepoint_policy"] == "min1_0935_bar"
    assert meta["strict_point_snapshot"] is False


def test_no_forbidden_output_paths_or_credentials(tmp_path):
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
    for forbidden in ["reports/analysis/lessons", "reports/analysis/patterns", "market_pattern_registry.json", "pass" + "word", "to" + "ken", "sec" + "ret"]:
        assert forbidden not in combined
