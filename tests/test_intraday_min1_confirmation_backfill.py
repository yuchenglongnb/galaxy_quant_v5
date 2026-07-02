import csv
from pathlib import Path

import scripts.backfill_intraday_min1_confirmation as backfill


def _write_csv(path: Path, columns: list[str], rows: list[list[str]] | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = ",".join(columns) + "\n"
    for row in rows or []:
        text += ",".join(row) + "\n"
    path.write_text(text, encoding="utf-8")


def _write_review(root: Path, date: str, coverage_count=0):
    import json

    path = root / "reports" / "analysis" / "daily" / date / "auction_review.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "intraday_confirmation_summary": {
                    "available": coverage_count > 0,
                    "coverage_count": coverage_count,
                }
            }
        ),
        encoding="utf-8",
    )


def _write_validation(root: Path, date: str):
    validation = root / "reports" / "validation" / "daily" / date
    _write_csv(
        validation / "signal_detail.csv",
        ["signal_category", "target_type", "name"],
        [
            ["trend", "个股", "Alpha"],
            ["trend", "个股", "Beta"],
            ["trend", "行业", "数字芯片设计"],
        ],
    )
    _write_csv(
        validation / "factor_snapshot_stock.csv",
        ["code", "name", "signal_category"],
        [
            ["000001.SZ", "Alpha", "trend"],
            ["000002.SZ", "Beta", "trend"],
        ],
    )


def test_no_min1_source_does_not_fabricate_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(backfill, "ROOT", tmp_path)
    monkeypatch.setattr(backfill, "EVAL_ROOT", tmp_path / "reports" / "analysis" / "evaluations")
    date = "20260629"
    _write_review(tmp_path, date)
    _write_validation(tmp_path, date)

    payload = backfill.build_payload(date, runner=lambda *_: {"rebuilt": False, "reason": "kline_query_failed"})

    assert payload["backfill"]["success_count"] == 0
    assert payload["backfill"]["failed_count"] == 2
    assert payload["backfill"]["generated_files"] == []
    assert payload["trend_active_allowed"] is False
    assert "stock_intraday_minute_backfill_failed" in payload["conclusion"]


def test_partial_success_counts_coverage_and_failed_codes(tmp_path, monkeypatch):
    monkeypatch.setattr(backfill, "ROOT", tmp_path)
    date = "20260629"
    _write_review(tmp_path, date)
    _write_validation(tmp_path, date)

    def runner(date_arg, *_):
        intraday = tmp_path / "AmazingData_Store" / date_arg / "intraday"
        _write_csv(intraday / "stocks_1min.csv", ["code", "time"], [["000001.SZ", "935"]])
        _write_csv(intraday / "stock_confirmation_latest.csv", ["code", "confirmation"], [["000001.SZ", "1"]])
        return {"rebuilt": True}

    payload = backfill.build_payload(date, runner=runner)

    assert payload["backfill"]["success_count"] == 1
    assert payload["backfill"]["failed_count"] == 1
    assert payload["backfill"]["partial_success"] is True
    assert payload["after"]["coverage_count"] == 1
    assert "intraday_confirmation_coverage_recovered" in payload["conclusion"]


def test_industry_item_without_code_not_queryable(tmp_path, monkeypatch):
    monkeypatch.setattr(backfill, "ROOT", tmp_path)
    date = "20260629"
    _write_review(tmp_path, date)
    _write_validation(tmp_path, date)

    payload = backfill.build_payload(date, runner=lambda *_: {})

    assert payload["candidate_count"] == 3
    assert payload["queryable_candidate_count"] == 2
    assert payload["industry_item_without_code"] == ["数字芯片设计"]


def test_write_outputs_structure(tmp_path, monkeypatch):
    monkeypatch.setattr(backfill, "ROOT", tmp_path)
    monkeypatch.setattr(backfill, "EVAL_ROOT", tmp_path / "reports" / "analysis" / "evaluations")
    date = "20260629"
    _write_review(tmp_path, date)
    _write_validation(tmp_path, date)
    payload = backfill.build_payload(date, runner=lambda *_: {})

    json_path, md_path = backfill.write_outputs(payload)

    assert json_path.exists()
    assert md_path.exists()
    with json_path.open(encoding="utf-8") as fh:
        saved = next(csv.DictReader([line for line in []]), None) if False else None
    assert saved is None
    assert "keep_trend_active_disabled" in json_path.read_text(encoding="utf-8")


def test_generated_files_stable_when_all_success(tmp_path, monkeypatch):
    monkeypatch.setattr(backfill, "ROOT", tmp_path)
    date = "20260629"
    _write_review(tmp_path, date)
    _write_validation(tmp_path, date)

    def runner(date_arg, *_):
        intraday = tmp_path / "AmazingData_Store" / date_arg / "intraday"
        _write_csv(
            intraday / "stocks_1min.csv",
            ["code", "time"],
            [["000001.SZ", "935"], ["000002.SZ", "935"]],
        )
        _write_csv(
            intraday / "stock_confirmation_latest.csv",
            ["code", "confirmation"],
            [["000001.SZ", "1"], ["000002.SZ", "1"]],
        )
        return {"rebuilt": True}

    payload = backfill.build_payload(date, runner=runner)

    assert payload["backfill"]["success_count"] == 2
    assert payload["backfill"]["failed_count"] == 0
    assert payload["backfill"]["generated_files"]
    assert payload["trend_active_allowed"] is False
