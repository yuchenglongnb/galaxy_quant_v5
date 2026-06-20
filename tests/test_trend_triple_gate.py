# -*- coding: utf-8 -*-

from analyzers.evaluators.trend_triple_gate import TrendTripleGate


def _candidate(**data):
    payload = {
        "name": data.pop("name", "candidate"),
        "signal_category": data.pop("signal_category", "trend"),
        "trend_filter_decision": data.pop("trend_filter_decision", "keep"),
        "trend_filter_status": data.pop("trend_filter_status", "active"),
        "leading_cluster_membership": data.pop("leading_cluster_membership", False),
        "leading_cluster_name": data.pop("leading_cluster_name", ""),
        "leading_cluster_strength": data.pop("leading_cluster_strength", None),
        "leading_cluster_status": data.pop("leading_cluster_status", ""),
        "leading_cluster_evidence": data.pop("leading_cluster_evidence", []),
        "leading_cluster_risk_flags": data.pop("leading_cluster_risk_flags", []),
        "data": data,
    }
    return payload


def setup_function():
    TrendTripleGate.reset_cache()


def test_strong_relative_strength_and_active_leading_cluster_is_shadow_main():
    candidate = _candidate(
        confirmation_data={
            "rs_vs_etf_pct": 1.2,
            "rs_vs_index_pct": 0.8,
            "amount_1m_ratio": 1.4,
            "benchmark_etf_code": "512480.SH",
            "benchmark_index_code": "000001.SH",
        },
        leading_cluster_membership=True,
        leading_cluster_name="半导体",
        leading_cluster_strength=75.0,
        leading_cluster_status="active",
        leading_cluster_evidence=[
            "sector_strength_score_confirmed",
            "sector_limitup_breadth_confirmed",
            "sector_money_flow_confirmed",
        ],
    )
    result = TrendTripleGate.evaluate_shadow(candidate, regime={"label": "mixed"})
    assert result["trend_gate_decision_shadow"] == "main"
    assert "leading_cluster_active" in result["trend_gate_reasons"]


def test_weak_vs_etf_drops_in_shadow():
    candidate = _candidate(
        confirmation_data={
            "rs_vs_etf_pct": -0.6,
            "rs_vs_index_pct": 0.2,
        },
        leading_cluster_membership=True,
        leading_cluster_strength=70.0,
        leading_cluster_status="active",
        leading_cluster_evidence=["sector_strength_score_confirmed"],
    )
    result = TrendTripleGate.evaluate_shadow(candidate, regime={"label": "mixed"})
    assert result["trend_gate_decision_shadow"] == "drop"
    assert "weak_vs_etf" in result["trend_gate_risk_flags"]


def test_weak_vs_index_drops_in_shadow():
    candidate = _candidate(
        confirmation_data={
            "rs_vs_etf_pct": 0.5,
            "rs_vs_index_pct": -0.5,
        },
        leading_cluster_membership=True,
        leading_cluster_strength=70.0,
        leading_cluster_status="active",
        leading_cluster_evidence=["sector_strength_score_confirmed"],
    )
    result = TrendTripleGate.evaluate_shadow(candidate, regime={"label": "mixed"})
    assert result["trend_gate_decision_shadow"] == "drop"
    assert "weak_vs_index" in result["trend_gate_risk_flags"]


def test_missing_relative_strength_observes_not_drop():
    candidate = _candidate(
        leading_cluster_membership=True,
        leading_cluster_strength=58.0,
        leading_cluster_status="partial",
        leading_cluster_evidence=["sector_breadth_strength_confirmed"],
    )
    result = TrendTripleGate.evaluate_shadow(candidate, regime={"label": "mixed"})
    assert result["trend_gate_decision_shadow"] == "observe"
    assert "missing_rs_vs_etf_pct" in result["trend_gate_missing_fields"]
    assert "missing_rs_vs_index_pct" in result["trend_gate_missing_fields"]


def test_sector_breadth_and_partial_leading_cluster_observes():
    candidate = _candidate(
        confirmation_data={
            "rs_vs_etf_pct": 0.4,
            "rs_vs_index_pct": 0.2,
        },
        leading_cluster_membership=True,
        leading_cluster_strength=52.0,
        leading_cluster_status="partial",
        leading_cluster_evidence=["sector_breadth_strength_confirmed"],
    )
    result = TrendTripleGate.evaluate_shadow(candidate, regime={"label": "mixed"})
    assert result["trend_gate_decision_shadow"] == "observe"
    assert "leading_cluster_partial" in result["trend_gate_reasons"]


def test_active_leading_cluster_in_hostile_regime_drops():
    candidate = _candidate(
        confirmation_data={
            "rs_vs_etf_pct": 1.0,
            "rs_vs_index_pct": 0.8,
            "amount_1m_ratio": 1.4,
        },
        leading_cluster_membership=True,
        leading_cluster_strength=80.0,
        leading_cluster_status="active",
        leading_cluster_evidence=["sector_strength_score_confirmed"],
    )
    result = TrendTripleGate.evaluate_shadow(candidate, regime={"label": "hostile"})
    assert result["trend_gate_decision_shadow"] == "drop"


def test_stale_overlay_risk_observes_not_auto_drop():
    candidate = _candidate(
        confirmation_data={
            "rs_vs_etf_pct": 0.8,
            "rs_vs_index_pct": 0.6,
        },
        leading_cluster_membership=True,
        leading_cluster_strength=62.0,
        leading_cluster_status="active",
        leading_cluster_evidence=["sector_strength_score_confirmed"],
        leading_cluster_risk_flags=["stale_ifind_snapshot"],
    )
    result = TrendTripleGate.evaluate_shadow(candidate, regime={"label": "mixed"})
    assert result["trend_gate_decision_shadow"] in {"observe", "main"}
    assert "leading_cluster_stale_risk" in result["trend_gate_risk_flags"]


def test_disabled_config_returns_disabled():
    config = TrendTripleGate.load_config()
    config["enabled"] = False
    TrendTripleGate._CONFIG_CACHE = config
    result = TrendTripleGate.evaluate_shadow(_candidate(), regime={"label": "mixed"})
    assert result["trend_gate_decision_shadow"] == "disabled"
