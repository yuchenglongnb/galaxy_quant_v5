import json
from pathlib import Path

import scripts.evaluate_trend_etf_benchmark_scope as scope


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_etf_candidate_goes_to_non_stock_scope():
    rows = [{"code": "159206.SZ", "name": "卫星", "target_type": "ETF", "primary_blocker": "x"}]
    result = scope._non_stock_candidate_analysis(rows)
    assert result["etf_candidates"][0]["recommended_scope"] == "etf_confirmation"


def test_industry_without_code_excluded_from_stock_denominator():
    rows = [
        {"code": "", "name": "数字芯片设计", "target_type": "industry"},
        {"code": "000001.SZ", "name": "A", "target_type": "stock"},
    ]
    counts = scope._candidate_scope_counts(rows)
    coverage = scope._stock_etf_benchmark_coverage(rows)
    assert counts["industry_without_code"] == 1
    assert coverage["covered_count"] == 0
    assert coverage["missing_count"] == 1


def test_missing_benchmark_group_enters_review_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr(scope, "ROOT", tmp_path)
    monkeypatch.setattr(scope, "EVAL_ROOT", tmp_path / "reports" / "analysis" / "evaluations")
    monkeypatch.setattr(scope, "BENCHMARK_MAP_PATH", tmp_path / "watchlists" / "group_benchmark_map.csv")
    date = "20260629"
    _write_json(
        scope.EVAL_ROOT / f"trend_confirmation_shadow_attribution_{date}.json",
        {
            "blocking_reason_by_candidate": [
                {"code": "000001.SZ", "name": "A", "target_type": "stock", "group": "军工电子", "benchmark_etf_code": ""},
            ],
            "shadow_distribution": {"main": 0, "observe": 1, "drop": 0},
        },
    )
    _write_json(scope.EVAL_ROOT / f"recent_trend_confirmation_coverage_{date}_{date}.json", {"coverage_summary": {"rs_vs_etf_coverage": 0.0}})
    _write_json(scope.EVAL_ROOT / f"intraday_min1_backfill_{date}.json", {"backfill": {"failed_codes": []}})

    payload = scope.build_payload(date)

    assert payload["benchmark_map_review_candidates"][0]["group"] == "军工电子"
    assert payload["benchmark_map_change_required"] is False
    assert payload["evaluator_change_required"] is False


def test_failed_etf_code_scope_and_conclusions(tmp_path, monkeypatch):
    monkeypatch.setattr(scope, "EVAL_ROOT", tmp_path)
    monkeypatch.setattr(scope, "BENCHMARK_MAP_PATH", tmp_path / "missing.csv")
    date = "20260629"
    _write_json(
        tmp_path / f"trend_confirmation_shadow_attribution_{date}.json",
        {
            "blocking_reason_by_candidate": [
                {"code": "159206.SZ", "name": "卫星", "target_type": "ETF", "group": "", "benchmark_etf_code": ""},
                {"code": "", "name": "数字芯片设计", "target_type": "industry", "group": "数字芯片设计", "benchmark_etf_code": ""},
            ],
            "failed_code_analysis": {"159206.SZ": {"name": "卫星"}},
            "shadow_distribution": {"main": 0, "observe": 2, "drop": 0},
        },
    )
    _write_json(tmp_path / f"recent_trend_confirmation_coverage_{date}_{date}.json", {"coverage_summary": {"rs_vs_etf_coverage": 0.0}})
    _write_json(tmp_path / f"intraday_min1_backfill_{date}.json", {"backfill": {"failed_codes": ["159206.SZ"]}})

    payload = scope.build_payload(date)

    assert payload["failed_code_analysis"]["159206.SZ"]["scope"] == "etf"
    assert payload["failed_code_analysis"]["159206.SZ"]["should_exclude_from_stock_confirmation"] is True
    assert "benchmark_map_not_modified" in payload["conclusion"]
    assert "keep_trend_active_disabled" in payload["conclusion"]
    assert "non_stock_trend_scope_required" in payload["conclusion"]
    assert "industry_item_without_code_excluded" in payload["conclusion"]


def test_write_outputs_does_not_modify_benchmark_map(tmp_path, monkeypatch):
    monkeypatch.setattr(scope, "EVAL_ROOT", tmp_path / "eval")
    map_path = tmp_path / "watchlists" / "group_benchmark_map.csv"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    original = "group,benchmark_etf_code,benchmark_index_code,note\nA,,,\n"
    map_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(scope, "BENCHMARK_MAP_PATH", map_path)

    payload = {
        "date": "20260629",
        "candidate_scope_counts": {},
        "stock_etf_benchmark_coverage": {},
        "missing_group_analysis": [],
        "non_stock_candidate_analysis": {},
        "failed_code_analysis": {},
        "root_cause": "",
        "trend_active_allowed": False,
        "evaluator_change_required": False,
        "benchmark_map_change_required": False,
        "conclusion": ["benchmark_map_not_modified", "keep_trend_active_disabled"],
    }
    scope.write_outputs(payload)
    assert map_path.read_text(encoding="utf-8") == original
