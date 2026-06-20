from scripts.diagnose_trend_gate_coverage import derive_primary_blocker, normalize_target_type


def test_normalize_target_type_keeps_expected_buckets():
    assert normalize_target_type("stock") == "stock"
    assert normalize_target_type("ETF") == "ETF"
    assert normalize_target_type("index") == "index"
    assert normalize_target_type("") == "unknown"


def test_primary_blocker_prefers_relative_strength_over_benchmark_missing():
    candidate = {
        "trend_gate_decision_shadow": "observe",
        "trend_gate_risk_flags": ["relative_strength_unverified"],
        "trend_gate_missing_fields": [
            "missing_rs_vs_etf_pct",
            "missing_benchmark_etf_code",
        ],
        "trend_gate_context": {"regime": "mixed"},
    }
    assert derive_primary_blocker(candidate) == "relative_strength_unverified"


def test_primary_blocker_marks_hostile_regime_first():
    candidate = {
        "trend_gate_decision_shadow": "drop",
        "trend_gate_risk_flags": ["leading_cluster_weak"],
        "trend_gate_missing_fields": [],
        "trend_gate_context": {"regime": "hostile"},
    }
    assert derive_primary_blocker(candidate) == "hostile_or_risk_off"
