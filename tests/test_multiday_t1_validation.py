from pathlib import Path

import pandas as pd

import scripts.evaluate_multiday_t1_validation as validation


def _write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _patch_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(validation, "MANUAL_PATCH_ROOT", tmp_path / "manual")
    monkeypatch.setattr(validation, "EVAL_ROOT", tmp_path / "eval")
    monkeypatch.setattr(validation, "OUTPUT_ROOT", tmp_path / "out")
    import scripts.backfill_signal_detail_code_temp_copy as source

    monkeypatch.setattr(source, "REPORTS_DAILY", tmp_path / "reports")
    monkeypatch.setattr(source, "STORE_ROOT", tmp_path / "store")


def test_manual_scope_excluded_not_in_denominator(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _write_csv(tmp_path / "manual" / "20260630_signal_detail.manual_code_patch.csv", [{"name": "行业A", "code": "", "signal_family": "趋势机会", "manual_resolution_scope": "industry_without_code", "manual_resolution_status": "approved"}])

    _, quality = validation.join_pair("20260630", "20260701")

    assert quality["candidate_count"] == 1
    assert quality["manual_scope_excluded_count"] == 1
    assert quality["resolved_code_denominator"] == 0


def test_pending_row_not_in_resolved_denominator(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _write_csv(tmp_path / "manual" / "20260630_signal_detail.manual_code_patch.csv", [{"name": "创业板", "code": "", "signal_family": "趋势机会", "manual_resolution_scope": "blocked", "manual_resolution_status": "pending"}])

    _, quality = validation.join_pair("20260630", "20260701")

    assert quality["pending_blocked_count"] == 1
    assert quality["resolved_code_denominator"] == 0


def test_code_join_priority_and_unmatched_count(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _write_csv(
        tmp_path / "manual" / "20260630_signal_detail.manual_code_patch.csv",
        [
            {"name": "A-old", "code": "000001.SZ", "signal_family": "趋势机会"},
            {"name": "B", "code": "000002.SZ", "signal_family": "趋势机会"},
        ],
    )
    _write_csv(tmp_path / "reports" / "20260701" / "factor_snapshot_stock.csv", [{"name": "A-new", "code": "000001.SZ", "auction_pct": 1, "close_pct": 2}])

    _, quality = validation.join_pair("20260630", "20260701")

    assert quality["primary_code_join_count"] == 1
    assert quality["fallback_name_join_count"] == 0
    assert quality["unmatched_count"] == 1


def test_signal_type_summary_is_stable(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _write_csv(tmp_path / "manual" / "20260630_signal_detail.manual_code_patch.csv", [{"name": "A", "code": "000001.SZ", "signal_family": "CP风险"}])
    _write_csv(tmp_path / "reports" / "20260701" / "factor_snapshot_stock.csv", [{"name": "A", "code": "000001.SZ", "auction_pct": 1, "close_pct": -2}])

    pair = validation.build_pair("20260630", "20260701")
    summary = pair["signal_type_summary"]["CP风险"]

    assert summary["resolved_count"] == 1
    assert summary["avg_t1_close_return"] == -2.0
    assert summary["negative_count"] == 1


def test_pending_ambiguity_is_preserved_in_pending_rows(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _write_csv(tmp_path / "manual" / "20260630_signal_detail.manual_code_patch.csv", [{"name": "创业板", "code": "", "signal_family": "趋势机会", "code_fill_warning": "159915.SZ;399006.SZ", "manual_resolution_scope": "blocked", "manual_resolution_status": "pending", "manual_resolution_reason": "manual"}])

    pair = validation.build_pair("20260630", "20260701")

    assert pair["pending_rows"][0]["name"] == "创业板"
    assert pair["pending_rows"][0]["candidate_codes"] == "159915.SZ;399006.SZ"


def test_payload_conclusions_include_fallback_eliminated_and_rules_unchanged(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _write_csv(tmp_path / "manual" / "20260630_signal_detail.manual_code_patch.csv", [{"name": "A", "code": "000001.SZ", "signal_family": "趋势机会"}])
    _write_csv(tmp_path / "manual" / "20260701_signal_detail.manual_code_patch.csv", [{"name": "B", "code": "000002.SZ", "signal_family": "趋势机会"}])
    _write_csv(tmp_path / "reports" / "20260701" / "factor_snapshot_stock.csv", [{"name": "A", "code": "000001.SZ", "auction_pct": 1, "close_pct": 2}])

    payload = validation.build_payload("20260630", "20260701")

    assert "name_fallback_eliminated" in payload["conclusion"]
    assert payload["cp_evaluator_change_required"] is False
    assert payload["trend_evaluator_change_required"] is False
    assert payload["lesson_pattern_written"] is False
