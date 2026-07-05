from pathlib import Path

from scripts.evaluate_cp_evidence_backfill_readiness import (
    build_summary_payload,
    classify_missing_reasons,
    main,
    snapshot_status,
    write_outputs,
)


SAMPLE_GROUP = "sample_theme_a"
UNKNOWN_GROUP = "unknown_theme"


def test_snapshot_missing_classification(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.evaluate_cp_evidence_backfill_readiness.ROOT", tmp_path)
    status = snapshot_status("20260622")
    row = {
        "group": SAMPLE_GROUP,
        "leading_cluster_status": "missing_ifind_overlay",
        "leading_cluster_evidence": [],
        "prior_day_context_bonus": 1,
        "repair_context": True,
    }
    reasons = classify_missing_reasons(row, status, {SAMPLE_GROUP})
    assert "snapshot_missing" in reasons
    assert "sector_breadth_snapshot_missing" in reasons
    assert "leading_cluster_snapshot_missing" in reasons


def test_alias_or_group_unmatched_classification(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.evaluate_cp_evidence_backfill_readiness.ROOT", tmp_path)
    status = snapshot_status("20260622")
    row = {
        "group": UNKNOWN_GROUP,
        "leading_cluster_status": "missing_ifind_overlay",
        "leading_cluster_evidence": [],
        "prior_day_context_bonus": 1,
        "repair_context": True,
    }
    reasons = classify_missing_reasons(row, status, {SAMPLE_GROUP})
    assert "alias_or_group_unmatched" in reasons


def test_sector_breadth_field_missing(tmp_path, monkeypatch):
    ifind = tmp_path / "AmazingData_Store" / "20260622" / "ifind"
    ifind.mkdir(parents=True)
    (ifind / "sector_strength_snapshot.csv").write_text("sector_name,return_pct\nsample_theme_a,1.2\n", encoding="utf-8")
    (ifind / "theme_limitup_distribution.csv").write_text("theme,count\nsample_theme_a,3\n", encoding="utf-8")
    (ifind / "limitup_ladder_snapshot.csv").write_text("theme,count\nsample_theme_a,1\n", encoding="utf-8")
    monkeypatch.setattr("scripts.evaluate_cp_evidence_backfill_readiness.ROOT", tmp_path)
    status = snapshot_status("20260622")
    row = {
        "group": SAMPLE_GROUP,
        "leading_cluster_status": "missing_ifind_overlay",
        "leading_cluster_evidence": [],
        "prior_day_context_bonus": 1,
        "repair_context": True,
    }
    reasons = classify_missing_reasons(row, status, {SAMPLE_GROUP})
    assert "sector_breadth_field_missing" in reasons
    assert "snapshot_missing" not in reasons


def test_builder_attachment_missing_when_source_exists_and_alias_matches(tmp_path, monkeypatch):
    ifind = tmp_path / "AmazingData_Store" / "20260622" / "ifind"
    ifind.mkdir(parents=True)
    (ifind / "sector_strength_snapshot.csv").write_text(
        "sector_name,limitup_count,dde_net_buy_yuan\nsample_theme_a,4,200000000\n",
        encoding="utf-8",
    )
    (ifind / "theme_limitup_distribution.csv").write_text("theme,count\nsample_theme_a,3\n", encoding="utf-8")
    (ifind / "limitup_ladder_snapshot.csv").write_text("theme,count\nsample_theme_a,1\n", encoding="utf-8")
    monkeypatch.setattr("scripts.evaluate_cp_evidence_backfill_readiness.ROOT", tmp_path)
    status = snapshot_status("20260622")
    row = {
        "group": SAMPLE_GROUP,
        "leading_cluster_status": "missing_ifind_overlay",
        "leading_cluster_evidence": [],
        "prior_day_context_bonus": 1,
        "repair_context": True,
    }
    reasons = classify_missing_reasons(row, status, {SAMPLE_GROUP})
    assert "builder_attachment_missing" in reasons


def test_prior_day_context_missing_classification(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.evaluate_cp_evidence_backfill_readiness.ROOT", tmp_path)
    status = snapshot_status("20260622")
    row = {
        "group": SAMPLE_GROUP,
        "leading_cluster_status": "missing_ifind_overlay",
        "leading_cluster_evidence": [],
        "prior_day_context_bonus": 0,
        "repair_context": False,
    }
    reasons = classify_missing_reasons(row, status, {SAMPLE_GROUP})
    assert "prior_day_context_missing" in reasons


def test_summary_conclusion_contains_required_tags(monkeypatch):
    def fake_daily(date):
        return {
            "date": date,
            "evidence_missing_false_positive_total": 1,
            "snapshot_missing_count": 1,
            "snapshot_stale_or_fallback_count": 0,
            "alias_or_group_unmatched_count": 0,
            "sector_breadth_field_missing_count": 0,
            "sector_breadth_snapshot_missing_count": 1,
            "leading_cluster_snapshot_missing_count": 1,
            "builder_attachment_missing_count": 0,
            "prior_day_context_missing_count": 0,
            "unknown_missing_reason_count": 0,
            "snapshot_status": {"snapshot_missing": True, "ifind_dir_exists": False},
            "by_group": {},
            "by_missing_reason": {"snapshot_missing": 1},
            "top_missing_evidence_samples": [
                {
                    "date": date,
                    "group": SAMPLE_GROUP,
                    "missing_reasons": ["snapshot_missing", "sector_breadth_snapshot_missing"],
                }
            ],
            "readiness_labels": ["market_structure_snapshot_evidence_missing"],
            "warnings": [],
        }

    monkeypatch.setattr("scripts.evaluate_cp_evidence_backfill_readiness.build_daily_payload", fake_daily)
    payload = build_summary_payload(["20260622"])
    assert payload["total_evidence_missing_false_positives"] == 1
    assert payload["by_group_distribution"][SAMPLE_GROUP]["candidate_count"] == 1
    assert "keep_cp_threshold" in payload["conclusion"]
    assert "repair_evidence_first" in payload["conclusion"]
    assert "no_rule_change_yet" in payload["conclusion"]
    assert "ready_for_evidence_completeness_review" in payload["conclusion"]
    assert payload["readiness_labels"] == [
        "market_structure_snapshot_evidence_missing",
        "sector_breadth_evidence_missing",
    ]
    assert "not execution instructions" in payload["readiness_label_note"]


def _empty_payload():
    return {
        "date_range": {"start_date": "20260622", "end_date": "20260622", "dates": ["20260622"]},
        "total_evidence_missing_false_positives": 0,
        "missing_reason_distribution": {},
        "by_date_distribution": {},
        "by_group_distribution": {},
        "by_snapshot_availability": {},
        "by_alias_group_match_status": {},
        "sector_breadth_field_availability": {},
        "leading_cluster_attachment_status": {},
        "readiness_labels": ["manual_review_only"],
        "readiness_label_note": "Readiness labels are gate precondition labels, not execution instructions.",
        "daily": [],
        "conclusion": ["keep_cp_threshold", "repair_evidence_first", "no_rule_change_yet"],
    }


def test_write_outputs_only_uses_explicit_tmp_path(tmp_path):
    json_path, md_path = write_outputs(_empty_payload(), tmp_path)
    assert json_path.parent == tmp_path
    assert md_path.parent == tmp_path
    assert json_path.exists()
    assert md_path.exists()
    assert "readiness_labels" in json_path.read_text(encoding="utf-8")
    assert "not execution instructions" in md_path.read_text(encoding="utf-8")


def test_dry_run_does_not_write_outputs(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("scripts.evaluate_cp_evidence_backfill_readiness._resolve_dates", lambda _args: ["20260622"])
    monkeypatch.setattr("scripts.evaluate_cp_evidence_backfill_readiness.build_summary_payload", lambda _dates: _empty_payload())

    def fail_write(*_args, **_kwargs):
        raise AssertionError("dry-run must not write report files")

    monkeypatch.setattr("scripts.evaluate_cp_evidence_backfill_readiness.write_outputs", fail_write)
    payload = main(["--dates", "20260622", "--dry-run", "--output-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert payload["readiness_labels"] == ["manual_review_only"]
    assert '"dry_run": true' in captured.out
    assert not any(tmp_path.iterdir())


def test_snapshot_status_uses_repo_relative_paths(tmp_path, monkeypatch):
    ifind = tmp_path / "AmazingData_Store" / "20260622" / "ifind"
    ifind.mkdir(parents=True)
    (ifind / "sector_strength_snapshot.csv").write_text("sector_name,limitup_count\nsample_theme_a,1\n", encoding="utf-8")
    monkeypatch.setattr("scripts.evaluate_cp_evidence_backfill_readiness.ROOT", tmp_path)
    status = snapshot_status("20260622")
    assert status["ifind_dir"] == "AmazingData_Store/20260622/ifind"
    assert status["files"]["sector_strength_snapshot"]["path"] == "AmazingData_Store/20260622/ifind/sector_strength_snapshot.csv"
    assert str(tmp_path) not in status["ifind_dir"]


def test_payload_uses_labels_not_execution_actions(monkeypatch):
    def fake_daily(date):
        return {
            "date": date,
            "evidence_missing_false_positive_total": 0,
            "snapshot_status": {"snapshot_missing": False, "ifind_dir_exists": True},
            "top_missing_evidence_samples": [],
            "readiness_labels": ["manual_review_only"],
            "warnings": [],
        }

    monkeypatch.setattr("scripts.evaluate_cp_evidence_backfill_readiness.build_daily_payload", fake_daily)
    payload = build_summary_payload(["20260622"])
    assert "readiness_labels" in payload
    assert "readiness_labels" in payload
    assert "not execution instructions" in payload["readiness_label_note"]


def test_output_contract_does_not_reference_repo_mutation_paths(tmp_path):
    json_path, md_path = write_outputs(_empty_payload(), tmp_path)
    combined = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
    forbidden_paths = [
        "reports/analysis/lessons",
        "reports/analysis/patterns",
        "market_pattern_registry.json",
        "watchlists/group_benchmark_map.csv",
    ]
    for path in forbidden_paths:
        assert path not in combined
