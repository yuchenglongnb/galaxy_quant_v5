import json
from pathlib import Path

import scripts.evaluate_intraday_confirmation_availability as availability


def _write_csv(path: Path, columns: list[str], rows: list[list[str]] | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = ",".join(columns) + "\n"
    for row in rows or []:
        text += ",".join(row) + "\n"
    path.write_text(text, encoding="utf-8")


def _write_review(root: Path, date: str, available=False, coverage_count=0):
    path = root / "reports" / "analysis" / "daily" / date / "auction_review.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "intraday_confirmation_summary": {
                    "available": available,
                    "coverage_count": coverage_count,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _write_trend_validation(root: Path, date: str, name="Alpha", code="000001.SZ"):
    validation = root / "reports" / "validation" / "daily" / date
    _write_csv(
        validation / "signal_detail.csv",
        ["signal_category", "target_type", "name"],
        [["trend", "stock", name]],
    )
    _write_csv(
        validation / "factor_snapshot_stock.csv",
        ["code", "name", "signal_category"],
        [[code, name, "trend"]],
    )


def test_stock_intraday_minute_missing_root_cause(tmp_path, monkeypatch):
    monkeypatch.setattr(availability, "ROOT", tmp_path)
    date = "20260629"
    _write_review(tmp_path, date)
    _write_trend_validation(tmp_path, date)
    store = tmp_path / "AmazingData_Store" / date
    _write_csv(store / "stocks_auction.csv", ["code"], [["000001.SZ"]])
    _write_csv(store / "stocks_close.csv", ["code"], [["000001.SZ"]])

    payload = availability.build_payload(date)

    assert payload["root_cause"] == "stock_intraday_minute_missing"
    assert payload["missing_reason_counts"]["stock_intraday_minute_missing"] == 1
    assert payload["trend_active_allowed"] is False
    assert "keep_trend_active_disabled" in payload["conclusion"]


def test_index_noon_present_does_not_make_stock_confirmation_available(tmp_path, monkeypatch):
    monkeypatch.setattr(availability, "ROOT", tmp_path)
    date = "20260629"
    _write_review(tmp_path, date)
    _write_trend_validation(tmp_path, date)
    store = tmp_path / "AmazingData_Store" / date
    _write_csv(store / "indices_noon.csv", ["code"], [["000001.SH"]])

    payload = availability.build_payload(date)

    assert payload["index_etf_minute_status"]["root_indices_noon"]["exists"] is True
    assert payload["stock_minute_status"]["stocks_1min"]["exists"] is False
    assert payload["root_cause"] == "stock_intraday_minute_missing"


def test_candidate_code_unmatched_when_intraday_stock_file_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(availability, "ROOT", tmp_path)
    date = "20260629"
    _write_review(tmp_path, date)
    validation = tmp_path / "reports" / "validation" / "daily" / date
    _write_csv(
        validation / "signal_detail.csv",
        ["signal_category", "target_type", "name"],
        [["trend", "stock", "Alpha"]],
    )
    _write_csv(
        validation / "factor_snapshot_stock.csv",
        ["code", "name", "signal_category"],
        [["000001.SZ", "Beta", "trend"]],
    )
    intraday = tmp_path / "AmazingData_Store" / date / "intraday"
    _write_csv(intraday / "stocks_1min.csv", ["code", "time"], [["000001.SZ", "935"]])

    payload = availability.build_payload(date)

    assert payload["root_cause"] == "candidate_code_unmatched"
    assert payload["candidate_code_match_status"]["code_unmatched_count"] == 1
    assert "intraday_confirmation_blocked_by_mapping" in payload["conclusion"]


def test_coverage_zero_keeps_trend_active_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(availability, "ROOT", tmp_path)
    date = "20260629"
    _write_review(tmp_path, date, available=False, coverage_count=0)
    _write_trend_validation(tmp_path, date)

    payload = availability.build_payload(date)

    assert payload["coverage_count"] == 0
    assert payload["trend_active_allowed"] is False
    assert "keep_trend_active_disabled" in payload["conclusion"]


def test_write_outputs_structure(tmp_path, monkeypatch):
    monkeypatch.setattr(availability, "ROOT", tmp_path)
    date = "20260629"
    _write_review(tmp_path, date)
    payload = availability.build_payload(date)
    json_path, md_path = availability.write_outputs(payload)

    assert json_path.exists()
    assert md_path.exists()
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["date"] == date
    assert saved["trend_active_allowed"] is False
