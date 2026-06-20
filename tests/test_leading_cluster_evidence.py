# -*- coding: utf-8 -*-

from unittest import mock

from analyzers.evaluators.leading_cluster_evidence import LeadingClusterEvidenceBuilder
from analyzers.signal_shortlist import SignalShortlistBuilder


def _candidate():
    return {
        "name": "胜宏科技",
        "signal_category": "trend",
        "scenario": "TREND_ACCELERATE",
        "amt_rank": 1,
        "date_int": 20260618,
        "action_score_breakdown": {
            "theme_cluster_bonus": 4.0,
            "group_regime_bonus": 2.0,
        },
        "data": {
            "code": "300476.SZ",
            "name": "胜宏科技",
            "group": "印制电路板",
            "target_type": "stock",
            "date_int": 20260618,
            "auction_pct": 1.2,
            "prev_pct": 4.5,
            "prev_vol_ratio": 1.6,
            "pos_5d": 68,
            "confirmation_data": {
                "rs_vs_etf_pct": 1.1,
                "rs_vs_index_pct": 0.7,
                "amount_1m_ratio": 1.4,
            },
        },
    }


def setup_function():
    LeadingClusterEvidenceBuilder.reset_cache()


def test_active_leading_cluster_evidence_from_ifind_overlay():
    candidate = _candidate()
    config = {
        "enabled": True,
        "ifind_cluster_alias": {"PCB概念": "AI硬件", "AI手机": "AI硬件"},
        "cluster_priority": ["AI硬件"],
        "min_sector_strength_for_active": 60,
        "min_sector_return_pct_for_active": 3,
        "min_catalyst_count_for_bonus": 1,
        "stale_days": 3,
        "market_structure": {
            "enabled": True,
            "allow_latest_fallback": True,
            "stale_days": 3,
            "min_sector_strength_score": 35,
            "min_theme_limitup_count": 3,
            "min_second_board_count": 1,
            "min_high_board_count": 1,
            "core_member_bonus": 10,
            "theme_diffusion_bonus": 12,
            "sector_strength_bonus": 15,
        },
    }
    with (
        mock.patch.object(LeadingClusterEvidenceBuilder, "load_config", return_value=config),
        mock.patch.object(
            LeadingClusterEvidenceBuilder,
            "_load_overlay_record",
            return_value=(
                {"ifind_signal_concepts": "PCB概念;AI手机", "ifind_updated_at": "2026-06-18T20:30:00"},
                {"missing": False, "used_fallback": False, "snapshot_date": 20260618},
            ),
        ),
        mock.patch.object(
            LeadingClusterEvidenceBuilder,
            "_load_sector_strength_map",
            return_value=(
                {
                    "PCB": {
                        "concept": "PCB概念",
                        "avg_return_pct": 11.94,
                        "amount_yuan": 437398860000.0,
                        "member_count": 220,
                        "sector_strength_score": 48.0,
                    },
                    "AI手机": {
                        "concept": "AI手机",
                        "avg_return_pct": 7.48,
                        "amount_yuan": 123764700000.0,
                        "member_count": 39,
                        "sector_strength_score": 35.0,
                    },
                },
                {"missing": False, "used_fallback": False, "snapshot_date": 20260618},
            ),
        ),
        mock.patch.object(
            LeadingClusterEvidenceBuilder,
            "_load_theme_diffusion_map",
            return_value=(
                {
                    "PCB": {
                        "theme": "PCB概念",
                        "limitup_count": 4,
                        "second_board_count": 1,
                        "high_board_count": 1,
                        "core_codes": "300476.SZ",
                        "core_names": "胜宏科技",
                    }
                },
                {"missing": False, "used_fallback": False, "snapshot_date": 20260618},
            ),
        ),
        mock.patch.object(
            LeadingClusterEvidenceBuilder,
            "_load_limitup_maps",
            return_value=(
                {"300476.SZ": {"signal_concepts": "PCB概念", "ths_industry": "元件"}},
                {"PCB": {"theme": "PCB概念", "limitup_count": 4, "core_codes": "300476.SZ"}},
                {"missing": False, "used_fallback": False, "snapshot_date": 20260618},
            ),
        ),
        mock.patch.object(
            LeadingClusterEvidenceBuilder,
            "_load_catalyst_map",
            return_value=(
                {"300476.SZ": {"count": 1, "summary": "订单饱满"}},
                {"missing": False, "used_fallback": False, "snapshot_date": 20260618},
            ),
        ),
        mock.patch.object(LeadingClusterEvidenceBuilder, "_snapshot_age_days", return_value=0),
        mock.patch.object(LeadingClusterEvidenceBuilder, "_cluster_rank", return_value=1),
    ):
        result = LeadingClusterEvidenceBuilder.evaluate_candidate(candidate, date_int=20260618)

    assert result["leading_cluster_membership"] is True
    assert result["leading_cluster_name"] == "AI硬件"
    assert result["leading_cluster_status"] == "active"
    assert "ifind_theme_match" in result["leading_cluster_evidence"]
    assert "ifind_sector_strength_confirmed" in result["leading_cluster_evidence"]
    assert "theme_limitup_diffusion_confirmed" in result["leading_cluster_evidence"]
    assert "limitup_core_member_confirmed" in result["leading_cluster_evidence"]
    assert "ifind_catalyst_confirmed" in result["leading_cluster_evidence"]


def test_partial_when_overlay_exists_but_market_structure_missing():
    candidate = _candidate()
    config = {
        "enabled": True,
        "ifind_cluster_alias": {"PCB概念": "AI硬件"},
        "cluster_priority": ["AI硬件"],
        "min_sector_strength_for_active": 60,
        "min_sector_return_pct_for_active": 3,
        "min_catalyst_count_for_bonus": 1,
        "stale_days": 3,
        "market_structure": {"enabled": True, "allow_latest_fallback": False, "stale_days": 3},
    }
    with (
        mock.patch.object(LeadingClusterEvidenceBuilder, "load_config", return_value=config),
        mock.patch.object(
            LeadingClusterEvidenceBuilder,
            "_load_overlay_record",
            return_value=(
                {"ifind_signal_concepts": "PCB概念", "ifind_updated_at": "2026-06-18T20:30:00"},
                {"missing": False, "used_fallback": False, "snapshot_date": 20260618},
            ),
        ),
        mock.patch.object(
            LeadingClusterEvidenceBuilder,
            "_load_sector_strength_map",
            return_value=({}, {"missing": True, "used_fallback": False, "snapshot_date": None}),
        ),
        mock.patch.object(
            LeadingClusterEvidenceBuilder,
            "_load_theme_diffusion_map",
            return_value=({}, {"missing": True, "used_fallback": False, "snapshot_date": None}),
        ),
        mock.patch.object(
            LeadingClusterEvidenceBuilder,
            "_load_limitup_maps",
            return_value=({}, {}, {"missing": True, "used_fallback": False, "snapshot_date": None}),
        ),
        mock.patch.object(
            LeadingClusterEvidenceBuilder,
            "_load_catalyst_map",
            return_value=({}, {"missing": True, "used_fallback": False, "snapshot_date": None}),
        ),
        mock.patch.object(LeadingClusterEvidenceBuilder, "_snapshot_age_days", return_value=0),
    ):
        result = LeadingClusterEvidenceBuilder.evaluate_candidate(candidate, date_int=20260618)

    assert result["leading_cluster_membership"] is True
    assert result["leading_cluster_status"] == "partial"
    assert "missing_market_structure_snapshot" in result["leading_cluster_missing_fields"]


def test_missing_overlay_marks_status_without_penalty():
    candidate = _candidate()
    with mock.patch.object(
        LeadingClusterEvidenceBuilder,
        "_load_overlay_record",
        return_value=(None, {"missing": True, "used_fallback": False, "snapshot_date": None}),
    ):
        result = LeadingClusterEvidenceBuilder.evaluate_candidate(candidate, date_int=20260618)

    assert result["leading_cluster_membership"] is False
    assert result["leading_cluster_status"] == "missing_ifind_overlay"
    assert "missing_ifind_overlay" in result["leading_cluster_missing_fields"]


def test_stale_snapshot_is_recognized():
    candidate = _candidate()
    config = {
        "enabled": True,
        "ifind_cluster_alias": {"PCB概念": "AI硬件"},
        "cluster_priority": ["AI硬件"],
        "min_sector_strength_for_active": 60,
        "min_sector_return_pct_for_active": 3,
        "min_catalyst_count_for_bonus": 1,
        "stale_days": 3,
        "market_structure": {"enabled": True, "allow_latest_fallback": True, "stale_days": 3},
    }
    with (
        mock.patch.object(LeadingClusterEvidenceBuilder, "load_config", return_value=config),
        mock.patch.object(
            LeadingClusterEvidenceBuilder,
            "_load_overlay_record",
            return_value=(
                {"ifind_signal_concepts": "PCB概念", "ifind_updated_at": "2026-06-10T20:30:00"},
                {"missing": False, "used_fallback": False, "snapshot_date": 20260610},
            ),
        ),
        mock.patch.object(
            LeadingClusterEvidenceBuilder,
            "_load_sector_strength_map",
            return_value=(
                {"PCB": {"concept": "PCB概念", "avg_return_pct": 11.94, "amount_yuan": 437398860000.0, "member_count": 220, "sector_strength_score": 48.0}},
                {"missing": False, "used_fallback": False, "snapshot_date": 20260610},
            ),
        ),
        mock.patch.object(
            LeadingClusterEvidenceBuilder,
            "_load_theme_diffusion_map",
            return_value=({}, {"missing": True, "used_fallback": False, "snapshot_date": None}),
        ),
        mock.patch.object(
            LeadingClusterEvidenceBuilder,
            "_load_limitup_maps",
            return_value=({}, {}, {"missing": True, "used_fallback": False, "snapshot_date": None}),
        ),
        mock.patch.object(
            LeadingClusterEvidenceBuilder,
            "_load_catalyst_map",
            return_value=({}, {"missing": True, "used_fallback": False, "snapshot_date": None}),
        ),
        mock.patch.object(LeadingClusterEvidenceBuilder, "_snapshot_age_days", return_value=6),
    ):
        result = LeadingClusterEvidenceBuilder.evaluate_candidate(candidate, date_int=20260618)

    assert result["leading_cluster_status"] == "stale_ifind_snapshot"
    assert "stale_ifind_snapshot" in result["leading_cluster_risk_flags"]


def test_cluster_alias_mapping_works():
    candidate = _candidate()
    config = {
        "enabled": True,
        "ifind_cluster_alias": {"华为昇腾": "国产算力"},
        "cluster_priority": ["国产算力"],
        "min_sector_strength_for_active": 60,
        "min_sector_return_pct_for_active": 3,
        "min_catalyst_count_for_bonus": 1,
        "stale_days": 3,
        "market_structure": {"enabled": True, "allow_latest_fallback": False, "stale_days": 3},
    }
    with (
        mock.patch.object(LeadingClusterEvidenceBuilder, "load_config", return_value=config),
        mock.patch.object(
            LeadingClusterEvidenceBuilder,
            "_load_overlay_record",
            return_value=(
                {"ifind_signal_concepts": "华为昇腾", "ifind_updated_at": "2026-06-18T20:30:00"},
                {"missing": False, "used_fallback": False, "snapshot_date": 20260618},
            ),
        ),
        mock.patch.object(
            LeadingClusterEvidenceBuilder,
            "_load_sector_strength_map",
            return_value=(
                {"华为昇腾": {"concept": "华为昇腾", "avg_return_pct": 4.77, "amount_yuan": 58156450000.0, "member_count": 106, "sector_strength_score": 25.0}},
                {"missing": False, "used_fallback": False, "snapshot_date": 20260618},
            ),
        ),
        mock.patch.object(
            LeadingClusterEvidenceBuilder,
            "_load_theme_diffusion_map",
            return_value=({}, {"missing": True, "used_fallback": False, "snapshot_date": None}),
        ),
        mock.patch.object(
            LeadingClusterEvidenceBuilder,
            "_load_limitup_maps",
            return_value=({}, {}, {"missing": True, "used_fallback": False, "snapshot_date": None}),
        ),
        mock.patch.object(
            LeadingClusterEvidenceBuilder,
            "_load_catalyst_map",
            return_value=({}, {"missing": True, "used_fallback": False, "snapshot_date": None}),
        ),
        mock.patch.object(LeadingClusterEvidenceBuilder, "_snapshot_age_days", return_value=0),
        mock.patch.object(LeadingClusterEvidenceBuilder, "_cluster_rank", return_value=1),
    ):
        result = LeadingClusterEvidenceBuilder.evaluate_candidate(candidate, date_int=20260618)

    assert result["leading_cluster_name"] == "国产算力"


def test_signal_shortlist_enrichment_does_not_change_decision_counts():
    index_df = None
    etf_df = None
    trend = _candidate()
    trap = {
        "name": "工业富联",
        "order": 2,
        "amt_rank": 1,
        "scenario": "TRAP_HOT_SECTOR",
        "cp": 72,
        "data": {
            "code": "601138.SH",
            "target_type": "stock",
            "auction_pct": 1.5,
            "prev_pct": 3.2,
            "prev_vol_ratio": 1.3,
            "pos_5d": 72,
            "date_int": 20260618,
        },
    }
    reversal = {
        "name": "中证500",
        "order": 0,
        "amt_rank": 1,
        "scenario": "REVERSAL_OVERSOLD",
        "sa": 78,
        "data": {
            "code": "000905.SH",
            "target_type": "index",
            "auction_pct": -1.0,
            "prev_pct": -2.4,
            "prev_vol_ratio": 1.0,
            "pos_5d": 40,
            "date_int": 20260618,
        },
    }
    with mock.patch.object(
        LeadingClusterEvidenceBuilder,
        "enrich_candidate",
        side_effect=lambda candidate, date_int=None: candidate.update(
            {
                "leading_cluster_membership": False,
                "leading_cluster_name": "",
                "leading_cluster_rank": None,
                "leading_cluster_strength": None,
                "leading_cluster_date": date_int,
                "leading_cluster_evidence": [],
                "leading_cluster_missing_fields": ["missing_ifind_overlay"],
                "leading_cluster_risk_flags": [],
                "leading_cluster_status": "missing_ifind_overlay",
            }
        ),
    ):
        shortlist, _regime = SignalShortlistBuilder.build(
            {"trap": [trap], "reversal": [reversal], "trend": [trend]},
            index_df=index_df,
            etf_df=etf_df,
        )

    assert len(shortlist["trend"]) <= 1
    assert len(shortlist["reversal"]) <= 1
    assert "leading_cluster_status" in trend
    assert trend["leading_cluster_status"] == "missing_ifind_overlay"
