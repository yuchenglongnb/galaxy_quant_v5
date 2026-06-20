# -*- coding: utf-8 -*-

from pathlib import Path
from unittest import mock

import json
import pandas as pd

import scripts.evaluate_leading_cluster_evidence as eval_module
from analyzers.evaluators.leading_cluster_evidence import LeadingClusterEvidenceBuilder


def _write_csv(path: Path, rows):
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def setup_function():
    LeadingClusterEvidenceBuilder.reset_cache()


def test_date_aware_loading_prefers_requested_date(tmp_path):
    store_root = Path(tmp_path) / "AmazingData_Store"
    for day, pct in (("20260618", 8.2), ("20260620", 1.0)):
        day_dir = store_root / day / "ifind"
        day_dir.mkdir(parents=True)
        _write_csv(
            day_dir / "stock_theme_snapshot.csv",
            [{"code": "300476.SZ", "ifind_signal_concepts": "PCB概念", "ifind_updated_at": f"{day[:4]}-{day[4:6]}-{day[6:]}T20:30:00"}],
        )
        _write_csv(
            day_dir / "sector_strength_snapshot.csv",
            [{"date": day, "sector_name": "PCB概念", "pct": pct, "amount_yuan": 4.37e11, "member_count": 220, "sector_strength_score": 48.0 if day == "20260618" else 10.0}],
        )
        _write_csv(
            day_dir / "theme_limitup_distribution.csv",
            [{"date": day, "theme": "PCB概念", "limitup_count": 4 if day == "20260618" else 1, "first_board_count": 2, "second_board_count": 1 if day == "20260618" else 0, "third_board_count": 0, "high_board_count": 1 if day == "20260618" else 0, "max_limitup_days": 4, "core_codes": "300476.SZ", "core_names": "胜宏科技"}],
        )
        _write_csv(
            day_dir / "limitup_ladder_snapshot.csv",
            [{"date": day, "code": "300476.SZ", "name": "胜宏科技", "limitup_days": 2, "limitup_tier": "2板", "concepts": "PCB概念", "signal_concepts": "PCB概念", "ths_industry": "元件"}],
        )

    candidate = {
        "name": "胜宏科技",
        "signal_category": "trend",
        "scenario": "TREND_CONTINUE",
        "date_int": 20260618,
        "data": {"code": "300476.SZ", "name": "胜宏科技", "group": "印制电路板", "target_type": "stock", "date_int": 20260618},
    }

    with mock.patch("config.settings.DBConfig.STORE_PATH", str(store_root)):
        LeadingClusterEvidenceBuilder.reset_cache()
        result = LeadingClusterEvidenceBuilder.evaluate_candidate(candidate, date_int=20260618)

    assert result["leading_cluster_date"] == 20260618
    assert "ifind_snapshot_date_fallback" not in result["leading_cluster_risk_flags"]


def test_fallback_latest_marks_risk_flag(tmp_path):
    store_root = Path(tmp_path) / "AmazingData_Store"
    day_dir = store_root / "20260620" / "ifind"
    day_dir.mkdir(parents=True)
    _write_csv(
        day_dir / "stock_theme_snapshot.csv",
        [{"code": "300476.SZ", "ifind_signal_concepts": "PCB概念", "ifind_updated_at": "2026-06-20T20:30:00"}],
    )
    _write_csv(
        day_dir / "sector_strength_snapshot.csv",
        [{"date": "20260620", "sector_name": "PCB概念", "pct": 8.2, "amount_yuan": 4.37e11, "member_count": 220, "sector_strength_score": 48.0}],
    )

    candidate = {
        "name": "胜宏科技",
        "signal_category": "trend",
        "scenario": "TREND_CONTINUE",
        "date_int": 20260618,
        "data": {"code": "300476.SZ", "name": "胜宏科技", "group": "印制电路板", "target_type": "stock", "date_int": 20260618},
    }

    with mock.patch("config.settings.DBConfig.STORE_PATH", str(store_root)):
        LeadingClusterEvidenceBuilder.reset_cache()
        result = LeadingClusterEvidenceBuilder.evaluate_candidate(candidate, date_int=20260618)

    assert "ifind_snapshot_date_fallback" in result["leading_cluster_risk_flags"]


def test_evaluation_script_generates_json(tmp_path):
    root = Path(tmp_path)
    detail_dir = root / "reports" / "validation" / "daily" / "20260618"
    ifind_dir = root / "AmazingData_Store" / "20260618" / "ifind"
    detail_dir.mkdir(parents=True)
    ifind_dir.mkdir(parents=True)

    _write_csv(
        detail_dir / "signal_detail.csv",
        [
            {
                "date": 20260618,
                "signal_category": "trend",
                "scenario": "TREND_CONTINUE",
                "universe_type": "stock",
                "code": "300476.SZ",
                "name": "胜宏科技",
                "group": "印制电路板",
                "theme_cluster": "印制电路板",
            }
        ],
    )
    _write_csv(
        ifind_dir / "stock_theme_snapshot.csv",
        [{"code": "300476.SZ", "ifind_signal_concepts": "PCB概念", "ifind_updated_at": "2026-06-18T20:30:00"}],
    )
    _write_csv(
        ifind_dir / "sector_strength_snapshot.csv",
        [{"date": "20260618", "sector_name": "PCB概念", "pct": 8.2, "amount_yuan": 4.37e11, "member_count": 220, "sector_strength_score": 48.0}],
    )
    _write_csv(
        ifind_dir / "theme_limitup_distribution.csv",
        [{"date": "20260618", "theme": "PCB概念", "limitup_count": 4, "first_board_count": 2, "second_board_count": 1, "third_board_count": 0, "high_board_count": 1, "max_limitup_days": 4, "core_codes": "300476.SZ", "core_names": "胜宏科技"}],
    )
    _write_csv(
        ifind_dir / "limitup_ladder_snapshot.csv",
        [{"date": "20260618", "code": "300476.SZ", "name": "胜宏科技", "limitup_days": 2, "limitup_tier": "2板", "concepts": "PCB概念", "signal_concepts": "PCB概念", "ths_industry": "元件"}],
    )

    with (
        mock.patch.object(eval_module, "ROOT", root),
        mock.patch("config.settings.DBConfig.STORE_PATH", str(root / "AmazingData_Store")),
    ):
        LeadingClusterEvidenceBuilder.reset_cache()
        payload = eval_module.evaluate(20260618)
        json_path, md_path = eval_module.write_outputs(payload)

    assert payload["candidate_total"] == 1
    assert payload["market_structure_hit_rate"] == 1.0
    assert json.loads(json_path.read_text(encoding="utf-8"))["date"] == "20260618"
    assert md_path.exists()
