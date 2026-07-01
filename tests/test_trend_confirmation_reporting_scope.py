import json
from pathlib import Path

import scripts.evaluate_trend_confirmation_reporting_scope as reporting


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalization_payload():
    return {
        "raw_candidate_count": 13,
        "normalized_scope_counts": {
            "stock": 11,
            "etf": 1,
            "index": 0,
            "industry_without_code": 1,
            "unknown": 0,
        },
        "excluded_from_stock_denominator": {
            "etf_candidates": [{"code": "159206.SZ", "name": "卫星", "target_type": "ETF"}],
            "industry_without_code": [{"code": "", "name": "数字芯片设计", "target_type": "industry"}],
            "unknown": [],
        },
        "after_normalization": {
            "stock_denominator": 11,
            "stock_coverage_count": 11,
            "stock_rs_vs_index_coverage": 1.0,
            "stock_amount_1m_ratio_coverage": 1.0,
            "stock_rs_vs_etf_coverage": 0.4545,
            "stock_shadow_distribution": {"main": 0, "observe": 7, "drop": 4},
        },
        "benchmark_map_missing_groups": ["军工电子"],
    }


def test_build_payload_hardens_stock_reporting_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(reporting, "ROOT", tmp_path)
    monkeypatch.setattr(reporting, "EVAL_ROOT", tmp_path / "eval")
    monkeypatch.setattr(reporting, "BENCHMARK_MAP_PATH", tmp_path / "watchlists" / "group_benchmark_map.csv")
    monkeypatch.setattr(reporting, "_has_git_diff", lambda path: True)
    date = "20260629"
    _write_json(reporting.EVAL_ROOT / f"trend_confirmation_scope_normalization_{date}.json", _normalization_payload())
    _write_json(
        reporting.EVAL_ROOT / f"etf_benchmark_manual_review_pack_{date}.json",
        {"high_confidence_candidates": []},
    )

    payload = reporting.build_payload(date)

    assert payload["raw_candidate_count"] == 13
    assert payload["reporting_scope_counts"] == {
        "stock": 11,
        "etf": 1,
        "index": 0,
        "industry_without_code": 1,
        "unknown": 0,
    }
    assert payload["stock_level_reporting"]["denominator"] == 11
    assert payload["stock_level_reporting"]["rs_vs_index_coverage"] == 1.0
    assert payload["stock_level_reporting"]["amount_1m_ratio_coverage"] == 1.0
    assert payload["stock_level_reporting"]["rs_vs_etf_coverage"] == 0.4545
    assert payload["trend_active_allowed"] is False
    assert payload["evaluator_change_required"] is False
    assert payload["benchmark_map_modified"] is False
    assert payload["existing_group_benchmark_map_diff_detected"] is True
    assert "reporting_scope_hardened" in payload["conclusion"]
    assert "keep_trend_active_disabled" in payload["conclusion"]
    assert "existing_group_benchmark_map_diff_requires_separate_review" in payload["warnings"]


def test_etf_candidate_excluded_from_stock_reporting(tmp_path, monkeypatch):
    monkeypatch.setattr(reporting, "ROOT", tmp_path)
    monkeypatch.setattr(reporting, "EVAL_ROOT", tmp_path / "eval")
    monkeypatch.setattr(reporting, "_has_git_diff", lambda path: False)
    date = "20260629"
    _write_json(reporting.EVAL_ROOT / f"trend_confirmation_scope_normalization_{date}.json", _normalization_payload())

    payload = reporting.build_payload(date)

    assert payload["excluded_from_stock_reporting"]["etf_candidates"][0]["code"] == "159206.SZ"
    assert payload["reporting_scope_counts"]["stock"] == 11
    assert payload["reporting_scope_counts"]["etf"] == 1


def test_industry_without_code_excluded_from_code_level_reporting(tmp_path, monkeypatch):
    monkeypatch.setattr(reporting, "ROOT", tmp_path)
    monkeypatch.setattr(reporting, "EVAL_ROOT", tmp_path / "eval")
    monkeypatch.setattr(reporting, "_has_git_diff", lambda path: False)
    date = "20260629"
    _write_json(reporting.EVAL_ROOT / f"trend_confirmation_scope_normalization_{date}.json", _normalization_payload())

    payload = reporting.build_payload(date)

    assert payload["excluded_from_stock_reporting"]["industry_without_code"][0]["name"] == "数字芯片设计"
    assert payload["reporting_scope_counts"]["industry_without_code"] == 1
    assert "industry_item_without_code_excluded" in payload["conclusion"]


def test_unknown_not_defaulted_to_stock(tmp_path, monkeypatch):
    monkeypatch.setattr(reporting, "ROOT", tmp_path)
    monkeypatch.setattr(reporting, "EVAL_ROOT", tmp_path / "eval")
    monkeypatch.setattr(reporting, "_has_git_diff", lambda path: False)
    date = "20260629"
    payload = _normalization_payload()
    payload["normalized_scope_counts"] = {
        "stock": 0,
        "etf": 0,
        "index": 0,
        "industry_without_code": 0,
        "unknown": 1,
    }
    payload["excluded_from_stock_denominator"] = {
        "etf_candidates": [],
        "industry_without_code": [],
        "unknown": [{"code": "X"}],
    }
    payload["after_normalization"]["stock_denominator"] = 0
    _write_json(reporting.EVAL_ROOT / f"trend_confirmation_scope_normalization_{date}.json", payload)

    result = reporting.build_payload(date)

    assert result["reporting_scope_counts"]["unknown"] == 1
    assert result["reporting_scope_counts"]["stock"] == 0
    assert result["excluded_from_stock_reporting"]["unknown"][0]["code"] == "X"


def test_write_outputs_does_not_modify_benchmark_map(tmp_path, monkeypatch):
    monkeypatch.setattr(reporting, "EVAL_ROOT", tmp_path / "eval")
    map_path = tmp_path / "watchlists" / "group_benchmark_map.csv"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    original = "group,benchmark_etf_code,benchmark_index_code,note\nA,,,\n"
    map_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(reporting, "BENCHMARK_MAP_PATH", map_path)
    payload = {
        "date": "20260629",
        "raw_candidate_count": 0,
        "reporting_scope_counts": {},
        "stock_level_reporting": {},
        "excluded_from_stock_reporting": {},
        "remaining_reporting_blockers": {},
        "existing_group_benchmark_map_diff_detected": False,
        "benchmark_map_modified": False,
        "trend_active_allowed": False,
        "evaluator_change_required": False,
        "warnings": [],
        "conclusion": ["benchmark_map_not_modified"],
    }

    reporting.write_outputs(payload)

    assert map_path.read_text(encoding="utf-8") == original
