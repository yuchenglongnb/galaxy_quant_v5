from scripts.evaluate_prior_day_context_stock_effect import (
    _topn_comparison,
    build_stock_effect_payload,
    build_summary,
    main,
    write_day_outputs,
    write_summary_outputs,
)


def _result():
    return {
        "date": "20260624",
        "prior_day_context": {
            "available": True,
            "context_confidence": "medium",
            "prev_trade_date": "20260623",
        },
        "signals": {
            "trap": [
                {
                    "name": "ETF-A",
                    "data": {"code": "512000.SH", "target_type": "ETF"},
                    "prior_day_context_bonus": 0.0,
                    "prior_day_context_annotation_bonus": 3.0,
                    "prior_day_context_score_before": 90.0,
                    "prior_day_context_score_after": 90.0,
                }
            ],
            "reversal": [
                {
                    "name": "Stock-A",
                    "data": {"code": "000001.SZ", "target_type": "stock"},
                    "prior_day_context_bonus": 3.0,
                    "prior_day_context_score_before": 80.0,
                    "prior_day_context_score_after": 83.0,
                }
            ],
            "trend": [
                {
                    "name": "Stock-B",
                    "data": {"code": "000002.SZ", "target_type": "stock"},
                    "prior_day_context_bonus": -3.0,
                    "prior_day_context_score_before": 82.0,
                    "prior_day_context_score_after": 79.0,
                },
                {
                    "name": "Stock-C",
                    "data": {"code": "000003.SZ", "target_type": "stock"},
                    "prior_day_context_bonus": 0.0,
                    "prior_day_context_score_before": 70.0,
                    "prior_day_context_score_after": 70.0,
                },
            ],
        },
    }


def _detail_df():
    return [
        {
            "signal_category": "reversal",
            "name": "Stock-A",
            "code": "000001.SZ",
            "target_type": "stock",
            "body_pct": 5.0,
            "validation_success": True,
        },
        {
            "signal_category": "trend",
            "name": "Stock-B",
            "code": "000002.SZ",
            "target_type": "stock",
            "body_pct": -2.0,
            "validation_success": False,
        },
        {
            "signal_category": "trend",
            "name": "Stock-C",
            "code": "000003.SZ",
            "target_type": "stock",
            "body_pct": 1.0,
            "validation_success": True,
        },
    ]


def test_stock_only_filter_and_excluded_counts():
    payload = build_stock_effect_payload("20260624", _result(), _detail_df())
    assert payload["stock_candidate_total"] == 3
    assert payload["excluded_non_stock_count"] == 1
    assert payload["excluded_by_target_type"]["ETF"] == 1
    assert payload["positive_bonus_count"] == 1
    assert payload["negative_bonus_count"] == 1
    assert payload["zero_bonus_count"] == 1


def test_category_breakdown_and_performance_groups():
    payload = build_stock_effect_payload("20260624", _result(), _detail_df())
    assert payload["positive_bonus_performance"]["success_rate"] == 100.0
    assert payload["negative_bonus_performance"]["success_rate"] == 0.0
    assert payload["category_breakdown"]["reversal"]["positive_bonus"]["candidate_count"] == 1
    assert payload["category_breakdown"]["trend"]["negative_bonus"]["candidate_count"] == 1


def test_topn_comparison_structure_and_rank_change():
    payload = build_stock_effect_payload("20260624", _result(), _detail_df())
    assert payload["rank_changed_count"] == 2
    assert payload["topn_comparison"]["top5"]["candidate_count"] == 3
    assert "topn_unchanged" in payload["topn_comparison"]["top5"]


def test_performance_unavailable_when_detail_missing():
    payload = build_stock_effect_payload("20260624", _result(), [])
    assert "post_close_performance_unavailable" in payload["warnings"]
    assert payload["positive_bonus_performance"]["performance_available"] is False


def test_summary_structure():
    payload = build_stock_effect_payload("20260624", _result(), _detail_df())
    summary = build_summary([payload])
    assert summary["total_stock_candidates"] == 3
    assert summary["positive_bonus_count"] == 1
    assert summary["negative_bonus_count"] == 1
    assert summary["overall_bucket_changed_count"] == 0
    assert summary["conclusion"] in {"ready_for_robustness_check", "keep_current_weight", "need_more_dates"}


def test_write_outputs_only_use_explicit_tmp_path(tmp_path):
    payload = build_stock_effect_payload("20260624", _result(), _detail_df())
    summary = build_summary([payload])
    day_json, day_md = write_day_outputs(payload, tmp_path)
    summary_json, summary_md = write_summary_outputs(summary, tmp_path)
    assert day_json.parent == tmp_path
    assert day_md.parent == tmp_path
    assert summary_json.parent == tmp_path
    assert summary_md.parent == tmp_path
    assert day_json.exists()
    assert summary_json.exists()


def test_dry_run_does_not_write_outputs(tmp_path, monkeypatch, capsys):
    payload = build_stock_effect_payload("20260624", _result(), _detail_df())
    summary = build_summary([payload])
    monkeypatch.setattr("scripts.evaluate_prior_day_context_stock_effect._resolve_dates", lambda _args: ["20260624"])
    monkeypatch.setattr(
        "scripts.evaluate_prior_day_context_stock_effect.evaluate_dates",
        lambda dates, output_dir=None, write_reports=True: ([payload], summary),
    )

    def fail_summary_write(*_args, **_kwargs):
        raise AssertionError("dry-run must not write summary reports")

    monkeypatch.setattr("scripts.evaluate_prior_day_context_stock_effect.write_summary_outputs", fail_summary_write)
    result_payloads, result_summary = main(["--dates", "20260624", "--dry-run", "--output-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert result_payloads == [payload]
    assert result_summary["total_stock_candidates"] == 3
    assert '"dry_run": true' in captured.out
    assert not any(tmp_path.iterdir())


def test_output_contract_does_not_reference_repo_mutation_paths(tmp_path):
    payload = build_stock_effect_payload("20260624", _result(), _detail_df())
    summary = build_summary([payload])
    day_json, day_md = write_day_outputs(payload, tmp_path)
    summary_json, summary_md = write_summary_outputs(summary, tmp_path)
    combined = "".join(path.read_text(encoding="utf-8") for path in [day_json, day_md, summary_json, summary_md])
    forbidden_paths = [
        "reports/analysis/lessons",
        "reports/analysis/patterns",
        "market_pattern_registry.json",
        "watchlists/group_benchmark_map.csv",
    ]
    for path in forbidden_paths:
        assert path not in combined
