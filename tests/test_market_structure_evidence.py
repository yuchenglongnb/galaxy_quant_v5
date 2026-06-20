# -*- coding: utf-8 -*-

from pathlib import Path
from unittest import mock

import pandas as pd

from analyzers.evaluators.leading_cluster_evidence import LeadingClusterEvidenceBuilder


def _write_csv(path: Path, rows):
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _candidate(date_int=20260618):
    return {
        "name": "胜宏科技",
        "signal_category": "trend",
        "scenario": "TREND_CONTINUE",
        "date_int": date_int,
        "action_score_breakdown": {"theme_cluster_bonus": 4.0, "group_regime_bonus": 2.0},
        "data": {
            "code": "300476.SZ",
            "name": "胜宏科技",
            "group": "印制电路板",
            "target_type": "stock",
            "date_int": date_int,
            "confirmation_data": {
                "rs_vs_etf_pct": 1.2,
                "rs_vs_index_pct": 0.8,
                "amount_1m_ratio": 1.3,
            },
        },
    }


def setup_function():
    LeadingClusterEvidenceBuilder.reset_cache()


def test_market_structure_evidence_uses_sector_breadth_without_full_ladder(tmp_path):
    root = Path(tmp_path) / "AmazingData_Store" / "20260618" / "ifind"
    root.mkdir(parents=True)
    _write_csv(
        root / "stock_theme_snapshot.csv",
        [{"code": "300476.SZ", "ifind_signal_concepts": "PCB概念;AI手机", "ifind_updated_at": "2026-06-18T20:30:00"}],
    )
    _write_csv(
        root / "sector_strength_snapshot.csv",
        [{
            "date": "20260618",
            "sector_name": "PCB概念",
            "pct": 8.2,
            "amount_yuan": 4.37e11,
            "net_active_buy_yuan": 8.6e8,
            "dde_net_buy_yuan": 3.2e8,
            "member_count": 220,
            "turnover_rate": 5.4,
            "limitup_count": 7,
            "limitup_ratio": round(7 / 220, 6),
            "sector_strength_score": 62.0,
        }],
    )

    with mock.patch("config.settings.DBConfig.STORE_PATH", str(Path(tmp_path) / "AmazingData_Store")):
        LeadingClusterEvidenceBuilder.reset_cache()
        result = LeadingClusterEvidenceBuilder.evaluate_candidate(_candidate(), date_int=20260618)

    assert result["leading_cluster_membership"] is True
    assert "ifind_sector_strength_confirmed" in result["leading_cluster_evidence"]
    assert "sector_breadth_strength_confirmed" in result["leading_cluster_evidence"]
    assert "sector_limitup_breadth_confirmed" in result["leading_cluster_evidence"]
    assert "sector_money_flow_confirmed" in result["leading_cluster_evidence"]
    assert result["leading_cluster_status"] == "active"


def test_missing_market_structure_snapshots_do_not_crash_or_punish(tmp_path):
    root = Path(tmp_path) / "AmazingData_Store" / "20260618" / "ifind"
    root.mkdir(parents=True)
    _write_csv(
        root / "stock_theme_snapshot.csv",
        [{"code": "300476.SZ", "ifind_signal_concepts": "PCB概念", "ifind_updated_at": "2026-06-18T20:30:00"}],
    )

    with mock.patch("config.settings.DBConfig.STORE_PATH", str(Path(tmp_path) / "AmazingData_Store")):
        LeadingClusterEvidenceBuilder.reset_cache()
        result = LeadingClusterEvidenceBuilder.evaluate_candidate(_candidate(), date_int=20260618)

    assert result["leading_cluster_status"] == "partial"
    assert "missing_market_structure_snapshot" in result["leading_cluster_missing_fields"]
