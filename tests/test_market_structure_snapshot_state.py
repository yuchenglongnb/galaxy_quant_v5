# -*- coding: utf-8 -*-

from pathlib import Path
from unittest.mock import patch

import pandas as pd

import scripts.evaluate_cp_exemption as cp_eval
import scripts.evaluate_leading_cluster_evidence as lc_eval


def _write_csv(path: Path, rows):
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def test_sector_breadth_ready_status_when_sector_snapshot_has_breadth_and_money_flow(tmp_path):
    ifind_dir = Path(tmp_path) / "AmazingData_Store" / "20260616" / "ifind"
    ifind_dir.mkdir(parents=True)
    _write_csv(
        ifind_dir / "sector_strength_snapshot.csv",
        [{
            "date": "20260616",
            "sector_name": "芯片概念",
            "amount_yuan": 1.0,
            "net_active_buy_yuan": 2.0,
            "limitup_count": 3,
        }],
    )

    with (
        patch.object(cp_eval, "ROOT", Path(tmp_path)),
        patch.object(lc_eval, "ROOT", Path(tmp_path)),
    ):
        cp_state = cp_eval._market_structure_snapshot_state(20260616)
        lc_state = lc_eval._market_structure_snapshot_state(20260616)

    assert cp_state["snapshot_status"] == "sector_breadth_ready"
    assert cp_state["snapshot_ready"] is True
    assert lc_state["snapshot_status"] == "sector_breadth_ready"
    assert lc_state["snapshot_ready"] is True


def test_sector_only_partial_when_breadth_fields_are_missing(tmp_path):
    ifind_dir = Path(tmp_path) / "AmazingData_Store" / "20260616" / "ifind"
    ifind_dir.mkdir(parents=True)
    _write_csv(
        ifind_dir / "sector_strength_snapshot.csv",
        [{
            "date": "20260616",
            "sector_name": "芯片概念",
            "amount_yuan": 1.0,
        }],
    )

    with (
        patch.object(cp_eval, "ROOT", Path(tmp_path)),
        patch.object(lc_eval, "ROOT", Path(tmp_path)),
    ):
        cp_state = cp_eval._market_structure_snapshot_state(20260616)
        lc_state = lc_eval._market_structure_snapshot_state(20260616)

    assert cp_state["snapshot_status"] == "sector_only_partial"
    assert lc_state["snapshot_status"] == "sector_only_partial"
