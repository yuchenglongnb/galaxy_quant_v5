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


def test_market_structure_evidence_uses_new_sector_snapshot_fields(tmp_path):
    root = Path(tmp_path) / "AmazingData_Store" / "20260618" / "ifind"
    root.mkdir(parents=True)
    _write_csv(
        root / "stock_theme_snapshot.csv",
        [{"code": "300476.SZ", "ifind_signal_concepts": "PCB概念;AI手机", "ifind_updated_at": "2026-06-18T20:30:00"}],
    )
    _write_csv(
        root / "sector_strength_snapshot.csv",
        [{"date": "20260618", "sector_name": "PCB概念", "pct": 8.2, "amount_yuan": 4.37e11, "member_count": 220, "sector_strength_score": 48.0}],
    )
    _write_csv(
        root / "theme_limitup_distribution.csv",
        [{"date": "20260618", "theme": "PCB概念", "limitup_count": 4, "first_board_count": 2, "second_board_count": 1, "third_board_count": 0, "high_board_count": 1, "max_limitup_days": 4, "core_codes": "300476.SZ", "core_names": "胜宏科技"}],
    )
    _write_csv(
        root / "limitup_ladder_snapshot.csv",
        [{"date": "20260618", "code": "300476.SZ", "name": "胜宏科技", "limitup_days": 2, "limitup_tier": "2板", "concepts": "PCB概念", "signal_concepts": "PCB概念", "ths_industry": "元件"}],
    )

    with mock.patch("config.settings.DBConfig.STORE_PATH", str(Path(tmp_path) / "AmazingData_Store")):
        LeadingClusterEvidenceBuilder.reset_cache()
        result = LeadingClusterEvidenceBuilder.evaluate_candidate(_candidate(), date_int=20260618)

    assert result["leading_cluster_membership"] is True
    assert "ifind_sector_strength_confirmed" in result["leading_cluster_evidence"]
    assert "theme_limitup_diffusion_confirmed" in result["leading_cluster_evidence"]
    assert "limitup_core_member_confirmed" in result["leading_cluster_evidence"]


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
