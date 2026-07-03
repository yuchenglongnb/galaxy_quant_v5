import json

import pytest

from reports.path_stability_gate import (
    SAFETY_DISCLAIMER,
    evaluate_coverage_gate,
    evaluate_directional_stability,
    evaluate_path_concentration,
    evaluate_rule_proposal_gate,
    load_distribution_summary,
    render_gate_review_markdown,
    write_gate_review,
)


def _summary():
    return {
        "input_coverage": [
            {"date": "20260626", "signal_rows": 10, "signal_detail_quality": "daily_signal_detail"},
            {"date": "20260629", "signal_rows": 10, "signal_detail_quality": "manual_code_patch"},
            {"date": "20260630", "signal_rows": 10, "signal_detail_quality": "manual_code_patch"},
            {"date": "20260701", "signal_rows": 10, "signal_detail_quality": "manual_code_patch"},
            {"date": "20260702", "signal_rows": 10, "signal_detail_quality": "daily_signal_detail"},
        ],
        "signal_family_summary": [
            {
                "signal_family": "CP风险",
                "count": 30,
                "avg_body_pct": 1.0,
                "median_body_pct": -0.5,
                "path_type_distribution": {"range_chop": 12, "rush_up_fade": 18},
            },
            {
                "signal_family": "反核机会",
                "count": 40,
                "avg_body_pct": -1.0,
                "median_body_pct": -0.8,
                "path_type_distribution": {"low_open_rebound_failed": 20, "range_chop": 20},
            },
        ],
        "daily_signal_summary": [
            {"date": "20260702", "signal_family": "CP风险", "path_type_distribution": {"rush_up_fade": 18}},
            {"date": "20260701", "signal_family": "反核机会", "path_type_distribution": {"low_open_rebound_failed": 10}},
        ],
        "phase_summary": [
            {"phase_bucket": "pre_retreat_setup", "signal_family": "CP风险", "avg_body_pct": 3.0},
            {"phase_bucket": "retreat_confirmation", "signal_family": "CP风险", "avg_body_pct": -2.0},
            {"phase_bucket": "retreat_confirmation", "signal_family": "反核机会", "avg_body_pct": -2.0},
        ],
        "t1_pairs": [
            {"candidate_count": 50, "resolved_code_denominator": 20, "unmatched_count": 30},
        ],
        "t1_signal_summary": [
            {
                "signal_family": "反核机会",
                "resolved_count": 20,
                "avg_t1_close_return": 1.0,
                "median_t1_close_return": 0.8,
                "t1_close_positive_rate": 60.0,
                "t1_path_type_distribution": {"range_chop": 10},
            }
        ],
    }


def test_missing_input_json_fails_clearly(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_distribution_summary(tmp_path / "missing.json")


def test_empty_summary_is_blocked_safely():
    result = evaluate_rule_proposal_gate({})

    assert result["metadata"]["rule_change_allowed"] is False
    assert result["metadata"]["overall_status"] == "insufficient_sample"


def test_five_day_sample_fails_min_dates_gate():
    coverage = evaluate_coverage_gate(_summary())

    assert coverage["pass"] is False
    assert "insufficient_trading_dates" in coverage["blockers"]


def test_high_unmatched_ratio_fails_coverage_gate():
    coverage = evaluate_coverage_gate(_summary())

    assert "unmatched_ratio_too_high" in coverage["blockers"]


def test_mixed_phase_signs_fail_directional_stability_gate():
    result = evaluate_directional_stability(_summary())

    assert result["by_signal_family"]["CP风险"]["pass"] is False
    assert "phase_sign_flip" in result["by_signal_family"]["CP风险"]["blockers"]


def test_single_day_path_concentration_does_not_pass_stability_gate():
    result = evaluate_path_concentration(_summary())

    assert result["by_signal_family"]["CP风险"]["pass"] is False
    assert "dominant_path_not_persistent_across_dates" in result["by_signal_family"]["CP风险"]["blockers"]


def test_t1_contradiction_blocks_rule_proposal():
    result = evaluate_rule_proposal_gate(_summary())

    blockers = " ".join(result["blockers"])
    assert "reversal_same_day_weak_but_broader_t1_positive" in blockers
    assert result["metadata"]["rule_change_allowed"] is False


def test_rendered_markdown_includes_analysis_only_disclaimer():
    result = evaluate_rule_proposal_gate(_summary())
    markdown = render_gate_review_markdown(result)

    assert SAFETY_DISCLAIMER in markdown
    assert "rule_change_allowed" in markdown


def test_json_summary_is_analysis_only_and_rule_change_disabled(tmp_path):
    result = evaluate_rule_proposal_gate(_summary())
    md_path = tmp_path / "reports" / "analysis" / "replay" / "gate.md"
    json_path = tmp_path / "reports" / "analysis" / "replay" / "gate.json"

    write_gate_review(result, md_path, json_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert payload["metadata"]["analysis_only"] is True
    assert payload["metadata"]["rule_change_allowed"] is False


def test_output_path_rejects_lesson_pattern_or_registry(tmp_path):
    result = evaluate_rule_proposal_gate(_summary())

    with pytest.raises(ValueError):
        write_gate_review(result, tmp_path / "reports" / "analysis" / "lessons" / "x.md", tmp_path / "gate.json")
