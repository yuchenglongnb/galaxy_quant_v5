import scripts.evaluate_trend_confirmation_shadow_attribution as attribution


def test_main_zero_keeps_trend_active_disabled():
    rows = [{"trend_gate_decision_shadow": "observe", "primary_blocker": "amount_not_confirmed"}]
    root = attribution._root_cause_refined(
        rows,
        {"rs_vs_etf_coverage": 0.8},
        {"main": 0, "observe": 1, "drop": 0},
    )
    assert root == "main_not_confirmed_after_data_recovery"


def test_etf_benchmark_coverage_insufficient_root_cause():
    rows = [{"trend_gate_decision_shadow": "observe", "primary_blocker": "relative_strength_unverified"}]
    root = attribution._root_cause_refined(
        rows,
        {"rs_vs_etf_coverage": 0.3846},
        {"main": 0, "observe": 1, "drop": 0},
    )
    assert root == "main_not_confirmed_after_data_recovery_etf_coverage_insufficient"


def test_industry_item_without_code_excluded_from_queryable():
    backfill = {"industry_item_without_code": ["数字芯片设计"]}
    rows = [{"name": "数字芯片设计", "target_type": "industry", "code": ""}]
    assert attribution._industry_without_code(backfill, rows) == ["数字芯片设计"]


def test_failed_etf_code_not_marked_as_stock():
    backfill = {"backfill": {"failed_codes": ["159206.SZ"]}}
    rows = [{"code": "159206.SZ", "name": "卫星", "target_type": "ETF"}]
    result = attribution._failed_code_analysis(backfill, rows)
    assert result["159206.SZ"]["is_etf"] is True
    assert result["159206.SZ"]["is_stock"] is False
    assert result["159206.SZ"]["reason"] == "trend_etf_candidate_not_in_stock_confirmation_latest"


def test_blocking_reason_counts_stable(monkeypatch):
    rows = [
        {
            "trend_gate_decision_shadow": "observe",
            "primary_blocker": "relative_strength_unverified",
            "target_type": "stock",
            "benchmark_etf_code": "",
            "code": "000001.SZ",
            "group": "A",
        },
        {
            "trend_gate_decision_shadow": "drop",
            "primary_blocker": "weak_vs_index",
            "target_type": "stock",
            "benchmark_etf_code": "512480.SH",
            "code": "000002.SZ",
            "group": "B",
        },
    ]
    monkeypatch.setattr(attribution, "_rows_for_date", lambda date: rows)
    monkeypatch.setattr(
        attribution,
        "_load_json",
        lambda path: {
            "queryable_candidate_count": 2,
            "backfill": {"failed_codes": []},
            "coverage_count": 2,
            "coverage_summary": {
                "rs_vs_index_coverage": 0.5,
                "amount_1m_ratio_coverage": 0.5,
                "rs_vs_etf_coverage": 0.5,
            },
        },
    )
    payload = attribution.build_payload("20260629")
    assert payload["blocking_reason_counts"]["relative_strength_unverified"] == 1
    assert payload["blocking_reason_counts"]["weak_vs_index"] == 1
    assert payload["evaluator_change_required"] is False
    assert "keep_trend_active_disabled" in payload["conclusion"]
    assert "no_strategy_rule_change" in payload["conclusion"]


def test_etf_benchmark_coverage_counts_missing_and_failed_codes():
    rows = [
        {"target_type": "stock", "benchmark_etf_code": "", "code": "000001.SZ", "group": "A"},
        {"target_type": "stock", "benchmark_etf_code": "512480.SH", "code": "000002.SZ", "group": "B"},
        {"target_type": "ETF", "benchmark_etf_code": "", "code": "159206.SZ", "group": "C"},
    ]
    result = attribution._etf_benchmark_coverage(rows, {"backfill": {"failed_codes": ["159206.SZ"]}})
    assert result["covered_count"] == 1
    assert result["missing_count"] == 1
    assert "159206.SZ" in result["missing_or_failed_codes"]
    assert "000001.SZ" in result["missing_or_failed_codes"]
