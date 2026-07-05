from scripts.evaluate_cp_exemption_evidence_coverage import (
    build_summary_payload,
    classify_evidence_bucket,
    evidence_profile,
    main,
    write_outputs,
)


def _row(**kwargs):
    base = {
        "cp_audit_bucket": "prior_day_context_explained_false_positive",
        "validation_success": False,
        "body_pct": 2.0,
        "cp_risk_decision": "crowded_observe",
        "leading_cluster_status": "missing_ifind_overlay",
        "leading_cluster_strength": 0,
        "leading_cluster_evidence": [],
        "prior_day_context_bonus": 0,
        "repair_context": False,
    }
    base.update(kwargs)
    return base


def test_exemption_ready_false_positive_when_complete_without_risk_decision():
    row = _row(
        cp_risk_decision="",
        leading_cluster_status="active",
        leading_cluster_strength=90,
        leading_cluster_evidence=["sector_breadth_strength_confirmed"],
        repair_context=True,
    )
    assert classify_evidence_bucket(row) == "exemption_ready_false_positive"


def test_evidence_missing_false_positive_when_key_evidence_missing():
    row = _row(repair_context=True)
    assert classify_evidence_bucket(row) == "evidence_missing_false_positive"
    profile = evidence_profile(row)
    assert "missing_leading_cluster_evidence" in profile["missing_evidence"]
    assert "missing_sector_breadth_evidence" in profile["missing_evidence"]


def test_rule_gap_false_positive_when_complete_but_still_risk_decision():
    row = _row(
        leading_cluster_status="partial",
        leading_cluster_strength=70,
        leading_cluster_evidence=["sector_money_flow_confirmed"],
        prior_day_context_bonus=3,
        cp_risk_decision="hard_trap",
    )
    assert classify_evidence_bucket(row) == "rule_gap_false_positive"


def test_ambiguous_false_positive_fallback_for_empty_missing_profile(monkeypatch):
    monkeypatch.setattr(
        "scripts.evaluate_cp_exemption_evidence_coverage.evidence_profile",
        lambda row: {
            "leading_cluster_support": False,
            "sector_breadth_support": False,
            "prior_day_context_support": False,
            "evidence_complete": False,
            "missing_evidence": [],
            "sector_evidence_flags": [],
        },
    )
    assert classify_evidence_bucket(_row()) == "ambiguous_false_positive"


def test_true_cp_risk_reference_not_counted_as_false_positive():
    row = _row(cp_audit_bucket="true_cp_risk", validation_success=True, body_pct=-1.0)
    assert classify_evidence_bucket(row) == "true_cp_risk_reference"


def test_summary_conclusion_contains_keep_cp_threshold_and_repair_first(monkeypatch):
    def fake_daily(date):
        return {
            "date": date,
            "cp_false_positive_total": 1,
            "exemption_ready_false_positive_count": 0,
            "evidence_missing_false_positive_count": 1,
            "rule_gap_false_positive_count": 0,
            "ambiguous_false_positive_count": 0,
            "true_cp_risk_reference_count": 1,
            "missing_evidence_summary": {"missing_sector_breadth_evidence": 1},
            "by_group": {},
            "by_leading_cluster_status": {},
            "by_prior_day_context": {},
            "top_exemption_ready": [],
            "top_evidence_missing": [],
            "top_rule_gap": [],
            "sample_false_positive_rows": [
                {
                    "date": date,
                    "evidence_bucket": "evidence_missing_false_positive",
                    "group": "数字芯片设计",
                    "leading_cluster_status": "missing_ifind_overlay",
                    "prior_day_context_bucket": "repair_readthrough",
                    "missing_evidence": ["missing_sector_breadth_evidence"],
                    "body_pct": 2.0,
                    "validation_success": False,
                }
            ],
            "sample_true_cp_risk_reference": [
                {
                    "date": date,
                    "evidence_bucket": "true_cp_risk_reference",
                    "group": "IT服务",
                    "body_pct": -1.0,
                    "validation_success": True,
                }
            ],
            "warnings": [],
        }

    monkeypatch.setattr("scripts.evaluate_cp_exemption_evidence_coverage.build_daily_payload", fake_daily)
    payload = build_summary_payload(["20260622"])
    assert payload["total_false_positives"] == 1
    assert payload["by_group_distribution"][0]["group"] == "数字芯片设计"
    assert "keep_cp_threshold" in payload["conclusion"]
    assert "repair_evidence_first" in payload["conclusion"]
    assert "need_sector_breadth_backfill" in payload["conclusion"]


def test_write_outputs_only_uses_explicit_tmp_path(tmp_path):
    payload = {
        "date_range": {"start_date": "20260622", "end_date": "20260622", "dates": ["20260622"]},
        "total_false_positives": 0,
        "exemption_ready_false_positive_count": 0,
        "evidence_missing_false_positive_count": 0,
        "rule_gap_false_positive_count": 0,
        "ambiguous_false_positive_count": 0,
        "true_cp_risk_reference_count": 0,
        "missing_evidence_summary": {},
        "by_date_distribution": {},
        "by_group_distribution": [],
        "by_leading_cluster_status_distribution": {},
        "by_prior_day_context_distribution": {},
        "conclusion": ["keep_cp_threshold", "repair_evidence_first", "not_ready_for_rule_change"],
    }
    json_path, md_path = write_outputs(payload, tmp_path)
    assert json_path.parent == tmp_path
    assert md_path.parent == tmp_path
    assert json_path.exists()
    assert md_path.exists()
    assert "not_ready_for_rule_change" in md_path.read_text(encoding="utf-8")


def test_dry_run_does_not_write_outputs(monkeypatch, tmp_path):
    payload = {
        "date_range": {"start_date": "20260622", "end_date": "20260622", "dates": ["20260622"]},
        "total_false_positives": 0,
        "exemption_ready_false_positive_count": 0,
        "evidence_missing_false_positive_count": 0,
        "rule_gap_false_positive_count": 0,
        "ambiguous_false_positive_count": 0,
        "true_cp_risk_reference_count": 0,
        "missing_evidence_summary": {},
        "by_date_distribution": {},
        "by_group_distribution": [],
        "by_leading_cluster_status_distribution": {},
        "by_prior_day_context_distribution": {},
        "conclusion": ["keep_cp_threshold", "repair_evidence_first", "not_ready_for_rule_change"],
    }
    monkeypatch.setattr("scripts.evaluate_cp_exemption_evidence_coverage._resolve_dates", lambda args: ["20260622"])
    monkeypatch.setattr("scripts.evaluate_cp_exemption_evidence_coverage.build_summary_payload", lambda dates: payload)
    monkeypatch.setattr("scripts.evaluate_cp_exemption_evidence_coverage.EVAL_ROOT", tmp_path)
    result = main(["--dates", "20260622", "--dry-run"])
    assert result["total_false_positives"] == 0
    assert list(tmp_path.iterdir()) == []
