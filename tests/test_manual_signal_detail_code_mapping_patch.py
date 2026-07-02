from pathlib import Path

import pandas as pd

import scripts.apply_manual_signal_detail_code_mapping_patch as patch


def _write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _patch_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(patch, "P1_4C_DERIVED_ROOT", tmp_path / "p1_4c")
    monkeypatch.setattr(patch, "MANUAL_PATCH_ROOT", tmp_path / "manual")
    monkeypatch.setattr(patch, "TEMPLATE_ROOT", tmp_path / "templates")
    monkeypatch.setattr(patch, "EVAL_ROOT", tmp_path / "eval")


def test_default_dry_run_does_not_write_second_level_copy(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    approval = tmp_path / "approval.csv"
    _write_csv(approval, [{"date": "20260701", "row_index": 0, "name": "A", "candidate_codes": "", "approved_code": "", "approved_scope": "industry_without_code", "approval_status": "approved", "approval_reason": "sector"}])
    _write_csv(tmp_path / "p1_4c" / "20260701_signal_detail.code_backfilled.csv", [{"name": "A", "code": "", "code_fill_status": "unfilled"}])

    payload = patch.build_payload(approval, write_temp_copy=False)

    assert payload["manual_patch_files_written"] == []
    assert not (tmp_path / "manual").exists()
    assert payload["original_files_modified"] is False
    assert payload["p1_4c_derived_files_modified"] is False


def test_write_temp_copy_only_writes_second_level_copy(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    approval = tmp_path / "approval.csv"
    source = tmp_path / "p1_4c" / "20260701_signal_detail.code_backfilled.csv"
    _write_csv(approval, [{"date": "20260701", "row_index": 0, "name": "A", "candidate_codes": "", "approved_code": "", "approved_scope": "industry_without_code", "approval_status": "approved", "approval_reason": "sector"}])
    _write_csv(source, [{"name": "A", "code": "", "code_fill_status": "unfilled"}])
    original = source.read_text(encoding="utf-8-sig")

    payload = patch.build_payload(approval, write_temp_copy=True)

    assert len(payload["manual_patch_files_written"]) == 1
    assert source.read_text(encoding="utf-8-sig") == original
    assert (tmp_path / "manual" / "20260701_signal_detail.manual_code_patch.csv").exists()


def test_pending_status_does_not_patch(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    approval = tmp_path / "approval.csv"
    _write_csv(approval, [{"date": "20260701", "row_index": 0, "name": "A", "candidate_codes": "159915.SZ,399006.SZ", "approved_code": "159915.SZ", "approved_scope": "etf", "approval_status": "pending", "approval_reason": "wait"}])
    _write_csv(tmp_path / "p1_4c" / "20260701_signal_detail.code_backfilled.csv", [{"name": "A", "code": "", "code_fill_status": "ambiguous"}])

    frame, summary, _ = patch.apply_to_date("20260701", patch.read_approval_file(approval)[0])

    assert frame.iloc[0]["code"] == ""
    assert summary["pending_count"] == 1


def test_industry_without_code_does_not_write_code(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    approval = tmp_path / "approval.csv"
    _write_csv(approval, [{"date": "20260701", "row_index": 0, "name": "行业A", "candidate_codes": "", "approved_code": "", "approved_scope": "industry_without_code", "approval_status": "approved", "approval_reason": "sector"}])
    _write_csv(tmp_path / "p1_4c" / "20260701_signal_detail.code_backfilled.csv", [{"name": "行业A", "code": "", "code_fill_status": "unfilled"}])

    frame, summary, _ = patch.apply_to_date("20260701", patch.read_approval_file(approval)[0])

    assert frame.iloc[0]["code"] == ""
    assert frame.iloc[0]["manual_resolution_scope"] == "industry_without_code"
    assert summary["industry_without_code_marked_count"] == 1


def test_candidate_mismatch_warns_and_does_not_patch(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    approval = tmp_path / "approval.csv"
    _write_csv(approval, [{"date": "20260701", "row_index": 0, "name": "A", "candidate_codes": "159915.SZ", "approved_code": "399006.SZ", "approved_scope": "index", "approval_status": "approved", "approval_reason": "bad"}])
    _write_csv(tmp_path / "p1_4c" / "20260701_signal_detail.code_backfilled.csv", [{"name": "A", "code": "", "code_fill_status": "ambiguous"}])

    frame, summary, warnings = patch.apply_to_date("20260701", patch.read_approval_file(approval)[0])

    assert frame.iloc[0]["code"] == ""
    assert summary["warnings_count"] == 1
    assert "approved_code_not_in_candidates" in warnings[0]


def test_industry_without_code_is_excluded_from_join_unmatched(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    frame = pd.DataFrame([{"name": "行业A", "code": "", "code_fill_status": "unfilled", "manual_resolution_scope": "industry_without_code", "manual_resolution_status": "approved"}])

    result = patch.recheck_pair("20260630", "20260701", frame)

    assert result["manual_scope_excluded_count"] == 1
    assert result["unmatched_count"] == 0


def test_pending_row_remains_pending_blocked(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    frame = pd.DataFrame([{"name": "创业板", "code": "", "code_fill_status": "ambiguous", "manual_resolution_scope": "blocked", "manual_resolution_status": "pending"}])

    result = patch.recheck_pair("20260630", "20260701", frame)

    assert result["pending_blocked_count"] == 1
    assert result["unmatched_count"] == 0


def test_payload_keeps_rules_and_lessons_unchanged(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    approval = tmp_path / "approval.csv"
    _write_csv(approval, [{"date": "20260701", "row_index": 0, "name": "A", "candidate_codes": "", "approved_code": "", "approved_scope": "industry_without_code", "approval_status": "approved", "approval_reason": "sector"}])
    _write_csv(tmp_path / "p1_4c" / "20260701_signal_detail.code_backfilled.csv", [{"name": "A", "code": "", "code_fill_status": "unfilled"}])

    payload = patch.build_payload(approval, write_temp_copy=False)

    assert payload["auto_patch_used"] is False
    assert payload["cp_evaluator_change_required"] is False
    assert payload["trend_evaluator_change_required"] is False
    assert payload["lesson_pattern_written"] is False
    assert "auto_patch_disabled" in payload["conclusion"]
