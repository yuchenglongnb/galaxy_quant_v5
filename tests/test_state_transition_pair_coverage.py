from reports.state_transition_pair_coverage import build_coverage


def _pair(decision, feedback, decision_level, feedback_level, valid=False, regime=""):
    return {
        "decision_date": decision,
        "feedback_date": feedback,
        "decision_validation_level": decision_level,
        "feedback_validation_level": feedback_level,
        "counts_as_valid_candidate_pair": valid,
        "baseline_regime": regime,
        "pair_exclusion_reasons": [] if valid else ["not_both_candidate_close"],
    }


def test_only_verified_candidate_pair_counts_and_sector_pairs_do_not():
    payload = build_coverage([
        _pair("1", "2", "candidate_close", "candidate_close", True, "hostile"),
        _pair("2", "3", "sector_range_context", "candidate_close"),
        _pair("3", "4", "candidate_close", "sector_daily_evidence"),
    ])
    assert payload["valid_candidate_pairs"] == 1
    assert payload["sector_range_pairs"] == 1
    assert payload["sector_daily_pairs"] == 1
    assert payload["regimes_covered"] == ["hostile"]


def test_pending_decision_is_not_completed_pair():
    payload = build_coverage([], pending_decisions=[{"decision_date": "20260717"}])
    assert payload["completed_transition_records"] == 0
    assert payload["pending_decisions"] == 1


def test_readiness_requires_ten_pairs_and_three_regimes():
    rows = [
        _pair(str(i), str(i + 1), "candidate_close", "candidate_close", True, ["a", "b", "c"][i % 3])
        for i in range(10)
    ]
    assert build_coverage(rows)["ready_for_p2_5"] is True
    assert build_coverage(rows[:9])["ready_for_p2_5"] is False


def test_duplicate_pairs_are_deduplicated_and_empty_input_is_safe():
    row = _pair("1", "2", "candidate_close", "candidate_close", True, "hostile")
    assert build_coverage([row, row])["valid_candidate_pairs"] == 1
    empty = build_coverage([])
    assert empty["total_transition_records"] == 0
    assert empty["ready_for_p2_5"] is False


def test_latest_evidence_levels_are_reported_without_runtime_memory():
    payload = build_coverage([], evidence_rows=[
        {"date": "20260707", "validation_level": "candidate_close"},
        {"date": "20260716", "validation_level": "sector_range_context"},
    ])
    assert payload["latest_candidate_close_date"] == "20260707"
    assert payload["latest_sector_range_date"] == "20260716"
