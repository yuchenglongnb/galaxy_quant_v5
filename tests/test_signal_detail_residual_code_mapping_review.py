from pathlib import Path

import pandas as pd

import scripts.evaluate_signal_detail_residual_code_mapping_review as review


def _write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _patch_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(review, "DERIVED_ROOT", tmp_path / "derived")
    monkeypatch.setattr(review, "REPORTS_DAILY", tmp_path / "reports")
    monkeypatch.setattr(review, "STORE_ROOT", tmp_path / "store")
    monkeypatch.setattr(review, "EVAL_ROOT", tmp_path / "eval")


def test_unfilled_row_enters_residual_rows(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    date = "20260701"
    _write_csv(tmp_path / "derived" / f"{date}_signal_detail.code_backfilled.csv", [{"name": "A", "code_fill_status": "unfilled"}])

    payload = review.build_payload(date, date)

    assert payload["raw_problem_counts"]["unfilled"] == 1
    assert payload["residual_rows"][0]["problem_types"] == ["unfilled"]


def test_ambiguous_row_enters_residual_rows(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    date = "20260701"
    _write_csv(tmp_path / "derived" / f"{date}_signal_detail.code_backfilled.csv", [{"name": "A", "code_fill_status": "ambiguous"}])

    payload = review.build_payload(date, date)

    assert payload["raw_problem_counts"]["ambiguous"] == 1
    assert "ambiguous" in payload["residual_rows"][0]["problem_types"]


def test_name_fallback_row_enters_residual_rows(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    prev = "20260630"
    date = "20260701"
    _write_csv(tmp_path / "derived" / f"{prev}_signal_detail.code_backfilled.csv", [{"name": "A", "code": "", "code_fill_status": "unfilled"}])
    _write_csv(tmp_path / "reports" / date / "factor_snapshot_stock.csv", [{"name": "A", "code": "000001.SZ", "auction_pct": 1, "close_pct": 2}])

    payload = review.build_payload(prev, date)

    assert payload["raw_problem_counts"]["name_fallback"] == 1
    assert "name_fallback" in payload["residual_rows"][0]["problem_types"]


def test_same_row_multiple_problem_types_are_merged(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    prev = "20260630"
    date = "20260701"
    _write_csv(tmp_path / "derived" / f"{prev}_signal_detail.code_backfilled.csv", [{"name": "A", "code": "", "code_fill_status": "unfilled"}])

    payload = review.build_payload(prev, date)

    assert payload["raw_problem_counts"]["unfilled"] == 1
    assert payload["raw_problem_counts"]["unmatched"] == 1
    assert payload["unique_problem_row_count"] == 1
    assert payload["residual_rows"][0]["problem_types"] == ["unfilled", "unmatched"]


def test_high_confidence_row_still_cannot_auto_patch(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    date = "20260701"
    _write_csv(tmp_path / "derived" / f"{date}_signal_detail.code_backfilled.csv", [{"name": "A", "code_fill_status": "unfilled"}])
    _write_csv(tmp_path / "reports" / date / "factor_snapshot_stock.csv", [{"name": "A", "code": "000001.SZ"}])

    payload = review.build_payload(date, date)
    row = payload["residual_rows"][0]

    assert row["confidence"] == "high"
    assert row["should_auto_patch"] is False
    assert payload["auto_patch_allowed"] is False
    assert "high_confidence_rows_require_manual_approval" in payload["conclusion"]


def test_ambiguous_name_not_silently_matched(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    date = "20260701"
    _write_csv(tmp_path / "derived" / f"{date}_signal_detail.code_backfilled.csv", [{"name": "A", "code_fill_status": "ambiguous"}])
    _write_csv(
        tmp_path / "reports" / date / "factor_snapshot_stock.csv",
        [{"name": "A", "code": "000001.SZ"}, {"name": "A", "code": "000002.SZ"}],
    )

    payload = review.build_payload(date, date)
    row = payload["residual_rows"][0]

    assert sorted(row["candidate_codes"]) == ["000001.SZ", "000002.SZ"]
    assert row["confidence"] == "none"
    assert row["should_auto_patch"] is False


def test_payload_keeps_files_and_rules_unchanged(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    date = "20260701"
    _write_csv(tmp_path / "derived" / f"{date}_signal_detail.code_backfilled.csv", [{"name": "A", "code_fill_status": "unfilled"}])

    payload = review.build_payload(date, date)

    assert payload["original_files_modified"] is False
    assert payload["derived_files_modified"] is False
    assert payload["lesson_pattern_written"] is False
    assert payload["cp_evaluator_change_required"] is False
    assert payload["trend_evaluator_change_required"] is False
    assert "auto_patch_disabled" in payload["conclusion"]
