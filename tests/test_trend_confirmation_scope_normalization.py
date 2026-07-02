import json
from pathlib import Path

import scripts.evaluate_trend_confirmation_scope_normalization as norm


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_etf_candidate_excluded_from_stock_denominator():
    rows = [
        {"code": "000001.SZ", "target_type": "stock"},
        {"code": "159206.SZ", "target_type": "ETF"},
    ]
    counts = norm._scope_counts(rows)
    excluded = norm._excluded(rows)
    assert counts["stock"] == 1
    assert counts["etf"] == 1
    assert excluded["etf_candidates"][0]["code"] == "159206.SZ"


def test_industry_without_code_excluded_from_code_level_denominator():
    rows = [
        {"code": "", "name": "数字芯片设计", "target_type": "industry"},
        {"code": "000001.SZ", "target_type": "stock"},
    ]
    counts = norm._scope_counts(rows)
    excluded = norm._excluded(rows)
    assert counts["industry_without_code"] == 1
    assert excluded["industry_without_code"][0]["name"] == "数字芯片设计"


def test_unknown_candidate_not_defaulted_to_stock():
    rows = [{"code": "X", "target_type": ""}]
    counts = norm._scope_counts(rows)
    assert counts["unknown"] == 1
    assert counts["stock"] == 0


def test_normalized_stock_coverage_fields_stable():
    rows = [
        {
            "code": "000001.SZ",
            "target_type": "stock",
            "rs_vs_index_pct": "1.0",
            "rs_vs_etf_pct": "",
            "amount_1m_ratio": "0.8",
            "shadow": "observe",
        },
        {
            "code": "000002.SZ",
            "target_type": "stock",
            "rs_vs_index_pct": "2.0",
            "rs_vs_etf_pct": "1.0",
            "amount_1m_ratio": "1.2",
            "shadow": "drop",
        },
        {"code": "159206.SZ", "target_type": "ETF", "shadow": "observe"},
    ]
    result = norm._stock_after(rows, {"000001.SZ"})
    assert result["stock_denominator"] == 2
    assert result["stock_coverage_count"] == 1
    assert result["stock_rs_vs_index_coverage"] == 1.0
    assert result["stock_rs_vs_etf_coverage"] == 0.5
    assert result["stock_shadow_distribution"] == {"main": 0, "observe": 1, "drop": 1}


def test_build_payload_flags_and_conclusion(tmp_path, monkeypatch):
    monkeypatch.setattr(norm, "ROOT", tmp_path)
    monkeypatch.setattr(norm, "EVAL_ROOT", tmp_path / "reports" / "analysis" / "evaluations")
    monkeypatch.setattr(norm, "BENCHMARK_MAP_PATH", tmp_path / "watchlists" / "group_benchmark_map.csv")
    date = "20260629"
    _write_json(
        norm.EVAL_ROOT / f"trend_confirmation_shadow_attribution_{date}.json",
        {
            "coverage_count": 1,
            "coverage": {"rs_vs_index_coverage": 0.5, "amount_1m_ratio_coverage": 0.5, "rs_vs_etf_coverage": 0.0},
            "shadow_distribution": {"main": 0, "observe": 2, "drop": 0},
            "blocking_reason_by_candidate": [
                {"code": "000001.SZ", "target_type": "stock", "group": "A", "benchmark_etf_code": "", "shadow": "observe"},
                {"code": "159206.SZ", "target_type": "ETF", "shadow": "observe"},
            ],
        },
    )
    _write_json(norm.EVAL_ROOT / f"trend_etf_benchmark_scope_{date}.json", {"stock_etf_benchmark_coverage": {"missing_groups": ["A"]}})
    intraday = tmp_path / "AmazingData_Store" / date / "intraday"
    intraday.mkdir(parents=True)
    (intraday / "stock_confirmation_latest.csv").write_text("code\n000001.SZ\n", encoding="utf-8")

    payload = norm.build_payload(date)

    assert payload["after_normalization"]["stock_denominator"] == 1
    assert payload["benchmark_map_change_required"] is False
    assert payload["evaluator_change_required"] is False
    assert payload["trend_active_allowed"] is False
    assert "non_stock_candidate_excluded_from_stock_denominator" in payload["conclusion"]
    assert "benchmark_map_manual_review_required" in payload["conclusion"]


def test_write_outputs_does_not_modify_benchmark_map(tmp_path, monkeypatch):
    monkeypatch.setattr(norm, "EVAL_ROOT", tmp_path / "eval")
    map_path = tmp_path / "watchlists" / "group_benchmark_map.csv"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    original = "group,benchmark_etf_code,benchmark_index_code,note\nA,,,\n"
    map_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(norm, "BENCHMARK_MAP_PATH", map_path)
    payload = {
        "date": "20260629",
        "raw_candidate_count": 0,
        "normalized_scope_counts": {},
        "excluded_from_stock_denominator": {},
        "before_normalization": {},
        "after_normalization": {},
        "benchmark_map_missing_groups": [],
        "trend_active_allowed": False,
        "evaluator_change_required": False,
        "benchmark_map_change_required": False,
        "conclusion": ["benchmark_map_not_modified"],
    }
    norm.write_outputs(payload)
    assert map_path.read_text(encoding="utf-8") == original
