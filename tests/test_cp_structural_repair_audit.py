from scripts.evaluate_cp_structural_repair_audit import (
    _distribution,
    _performance_summary,
    build_summary_payload,
    classify_cp_bucket,
    main,
    write_outputs,
)


def test_true_cp_risk_bucket():
    row = {
        "market_regime": "risk_off",
        "leading_cluster_status": "stale_ifind_snapshot",
        "validation_success": True,
        "body_pct": -2.0,
    }
    assert classify_cp_bucket(row) == "true_cp_risk"


def test_leading_cluster_repair_false_positive_bucket():
    row = {
        "market_regime": "mixed",
        "leading_cluster_status": "active",
        "leading_cluster_strength": 88,
        "validation_success": False,
        "body_pct": 3.2,
        "repair_context": True,
        "prior_day_context_bonus": 0,
    }
    assert classify_cp_bucket(row) == "leading_cluster_repair_false_positive"


def test_prior_day_context_explained_false_positive_bucket():
    row = {
        "market_regime": "mixed",
        "leading_cluster_status": "missing_ifind_overlay",
        "leading_cluster_strength": 0,
        "validation_success": False,
        "body_pct": 1.5,
        "prior_day_context_bonus": 3,
    }
    assert classify_cp_bucket(row) == "prior_day_context_explained_false_positive"


def test_unresolved_cp_fallback():
    row = {
        "market_regime": "risk_off",
        "leading_cluster_status": "active",
        "leading_cluster_strength": 80,
        "validation_success": True,
        "body_pct": -0.5,
    }
    assert classify_cp_bucket(row) == "unresolved_cp"


def test_performance_unavailable_is_stable():
    summary = _performance_summary([{"body_pct": None, "validation_success": None}])
    assert summary["performance_available"] is False
    assert summary["candidate_count"] == 1


def test_distribution_by_regime_and_leading_cluster():
    rows = [
        {"market_regime": "risk_off", "cp_audit_bucket": "true_cp_risk", "body_pct": -1.0, "validation_success": True},
        {
            "market_regime": "mixed",
            "cp_audit_bucket": "prior_day_context_explained_false_positive",
            "body_pct": 2.0,
            "validation_success": False,
        },
    ]
    grouped = _distribution(rows, "market_regime")
    assert grouped["risk_off"]["candidate_count"] == 1
    assert grouped["mixed"]["bucket_distribution"]["prior_day_context_explained_false_positive"] == 1


def test_summary_conclusion_contains_keep_cp_threshold(monkeypatch):
    def fake_daily(date):
        return {
            "date": date,
            "market_regime": "risk_off",
            "environment_decision": "selective_reversal_only",
            "cp_total": 1,
            "true_cp_risk_count": 1,
            "leading_cluster_repair_false_positive_count": 0,
            "prior_day_context_explained_false_positive_count": 0,
            "unresolved_cp_count": 0,
            "sample_rows": [
                {
                    "date": date,
                    "bucket": "true_cp_risk",
                    "market_regime": "risk_off",
                    "leading_cluster_status": "missing_ifind_overlay",
                    "group": "证券",
                    "body_pct": -1.0,
                    "validation_success": True,
                }
            ],
            "warnings": [],
        }

    monkeypatch.setattr("scripts.evaluate_cp_structural_repair_audit.build_daily_payload", fake_daily)
    payload = build_summary_payload(["20260623"])
    assert payload["total_cp_candidates"] == 1
    assert payload["by_date_bucket_distribution"]["20260623"]["true_cp_risk"] == 1
    assert "keep_cp_threshold" in payload["conclusion"]


def test_write_outputs_only_uses_explicit_tmp_path(tmp_path):
    payload = {
        "date_range": {"start_date": "20260623", "end_date": "20260623", "dates": ["20260623"]},
        "total_cp_candidates": 0,
        "true_cp_risk_count": 0,
        "leading_cluster_repair_false_positive_count": 0,
        "prior_day_context_explained_false_positive_count": 0,
        "unresolved_cp_count": 0,
        "by_date_bucket_distribution": {},
        "bucket_performance": {},
        "cp_false_positive_top_groups": [],
        "cp_true_risk_top_groups": [],
        "conclusion": ["keep_cp_threshold", "not_ready_for_rule_change"],
    }
    json_path, md_path = write_outputs(payload, tmp_path)
    assert json_path.parent == tmp_path
    assert md_path.parent == tmp_path
    assert json_path.exists()
    assert md_path.exists()
    assert "not_ready_for_rule_change" in md_path.read_text(encoding="utf-8")


def test_dry_run_does_not_write_outputs(monkeypatch, tmp_path):
    payload = {
        "date_range": {"start_date": "20260623", "end_date": "20260623", "dates": ["20260623"]},
        "total_cp_candidates": 0,
        "true_cp_risk_count": 0,
        "leading_cluster_repair_false_positive_count": 0,
        "prior_day_context_explained_false_positive_count": 0,
        "unresolved_cp_count": 0,
        "by_date_bucket_distribution": {},
        "bucket_performance": {},
        "cp_false_positive_top_groups": [],
        "cp_true_risk_top_groups": [],
        "conclusion": ["keep_cp_threshold", "not_ready_for_rule_change"],
    }
    monkeypatch.setattr("scripts.evaluate_cp_structural_repair_audit._resolve_dates", lambda args: ["20260623"])
    monkeypatch.setattr("scripts.evaluate_cp_structural_repair_audit.build_summary_payload", lambda dates: payload)
    monkeypatch.setattr("scripts.evaluate_cp_structural_repair_audit.EVAL_ROOT", tmp_path)
    result = main(["--dates", "20260623", "--dry-run"])
    assert result["total_cp_candidates"] == 0
    assert list(tmp_path.iterdir()) == []
