from pathlib import Path

import pandas as pd

import scripts.backfill_signal_detail_code_temp_copy as backfill


def _write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _patch_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(backfill, "REPORTS_DAILY", tmp_path / "reports")
    monkeypatch.setattr(backfill, "STORE_ROOT", tmp_path / "store")
    monkeypatch.setattr(backfill, "DERIVED_ROOT", tmp_path / "derived")
    monkeypatch.setattr(backfill, "EVAL_ROOT", tmp_path / "eval")


def test_temp_copy_does_not_overwrite_original(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    date = "20260701"
    original_path = tmp_path / "reports" / date / "signal_detail.csv"
    _write_csv(original_path, [{"name": "A", "signal_category": "trend"}])
    original = original_path.read_text(encoding="utf-8-sig")
    _write_csv(tmp_path / "reports" / date / "factor_snapshot_stock.csv", [{"name": "A", "code": "000001.SZ"}])

    _, summary = backfill.backfill_date(date, dry_run=False)

    assert summary["written"] is True
    assert original_path.read_text(encoding="utf-8-sig") == original
    assert (tmp_path / "derived" / "20260701_signal_detail.code_backfilled.csv").exists()


def test_native_code_has_priority(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    date = "20260701"
    _write_csv(tmp_path / "reports" / date / "signal_detail.csv", [{"name": "A", "code": "000001.SZ"}])
    _write_csv(tmp_path / "reports" / date / "factor_snapshot_stock.csv", [{"name": "A", "code": "000002.SZ"}])

    result, summary = backfill.backfill_date(date, dry_run=True)

    assert result.iloc[0]["code"] == "000001.SZ"
    assert result.iloc[0]["code_fill_status"] == "native"
    assert summary["native_code_count"] == 1


def test_factor_snapshot_stock_can_fill_code(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    date = "20260701"
    _write_csv(tmp_path / "reports" / date / "signal_detail.csv", [{"name": "A"}])
    _write_csv(tmp_path / "reports" / date / "factor_snapshot_stock.csv", [{"name": "A", "code": "000001.SZ"}])

    result, summary = backfill.backfill_date(date, dry_run=True)

    assert result.iloc[0]["code"] == "000001.SZ"
    assert result.iloc[0]["code_fill_status"] == "filled"
    assert "factor_snapshot_stock" in result.iloc[0]["code_fill_source"]
    assert summary["filled_count"] == 1


def test_etf_and_index_sources_can_fill_code(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    date = "20260701"
    _write_csv(tmp_path / "reports" / date / "signal_detail.csv", [{"name": "ETF A"}, {"name": "INDEX A"}])
    _write_csv(tmp_path / "reports" / date / "factor_snapshot_etf.csv", [{"name": "ETF A", "code": "159001.SZ"}])
    _write_csv(tmp_path / "reports" / date / "factor_snapshot_index.csv", [{"name": "INDEX A", "code": "000001.SH"}])

    result, summary = backfill.backfill_date(date, dry_run=True)

    assert result["code"].tolist() == ["159001.SZ", "000001.SH"]
    assert summary["filled_count"] == 2


def test_ambiguous_name_not_silently_matched(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    date = "20260701"
    _write_csv(tmp_path / "reports" / date / "signal_detail.csv", [{"name": "A"}])
    _write_csv(
        tmp_path / "reports" / date / "factor_snapshot_stock.csv",
        [{"name": "A", "code": "000001.SZ"}, {"name": "A", "code": "000002.SZ"}],
    )

    result, summary = backfill.backfill_date(date, dry_run=True)

    assert result.iloc[0]["code"] == ""
    assert result.iloc[0]["code_fill_status"] == "ambiguous"
    assert summary["ambiguous_name_count"] == 1


def test_unfilled_row_keeps_empty_code(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    date = "20260701"
    _write_csv(tmp_path / "reports" / date / "signal_detail.csv", [{"name": "A"}])

    result, summary = backfill.backfill_date(date, dry_run=True)

    assert result.iloc[0]["code"] == ""
    assert result.iloc[0]["code_fill_status"] == "unfilled"
    assert result.iloc[0]["code_fill_warning"] == "no_unique_name_code_match"
    assert summary["unfilled_count"] == 1


def test_t1_join_prefers_code_and_counts_name_fallback(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    prev = "20260630"
    date = "20260701"
    detail = pd.DataFrame(
        [
            {"name": "A-old", "code": "000001.SZ", "code_fill_status": "filled"},
            {"name": "B", "code": "", "code_fill_status": "unfilled"},
            {"name": "C", "code": "", "code_fill_status": "ambiguous"},
        ]
    )
    _write_csv(
        tmp_path / "reports" / date / "factor_snapshot_stock.csv",
        [
            {"name": "A-new", "code": "000001.SZ", "auction_pct": 1.0, "close_pct": 2.0},
            {"name": "B", "code": "000002.SZ", "auction_pct": 1.0, "close_pct": 3.0},
            {"name": "C", "code": "000003.SZ", "auction_pct": 1.0, "close_pct": 4.0},
        ],
    )

    result = backfill.recheck_pair(prev, date, detail)

    assert result["primary_code_join_count"] == 1
    assert result["fallback_name_join_count"] == 1
    assert result["ambiguous_blocked_count"] == 1
    assert result["unmatched_count"] == 1


def test_payload_keeps_rules_unchanged(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    date = "20260701"
    _write_csv(tmp_path / "reports" / date / "signal_detail.csv", [{"name": "A"}])
    _write_csv(tmp_path / "reports" / date / "factor_snapshot_stock.csv", [{"name": "A", "code": "000001.SZ"}])

    payload = backfill.build_payload(date, date, dry_run=True)

    assert payload["original_files_modified"] is False
    assert payload["lesson_pattern_written"] is False
    assert payload["cp_evaluator_change_required"] is False
    assert payload["trend_evaluator_change_required"] is False
    assert "lesson_pattern_not_written" in payload["conclusion"]
