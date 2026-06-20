# -*- coding: utf-8 -*-

import json
from pathlib import Path
from unittest import mock

import pandas as pd

import scripts.evaluate_ifind_market_structure as structure_module
from providers.ifind_limitup_ladder_provider import IFindLimitupLadderProvider
from providers.ifind_sector_strength_provider import IFindSectorStrengthProvider


def test_market_structure_script_generates_outputs(tmp_path):
    root = Path(tmp_path)
    limitup_raw = root / "limitup_raw.csv"
    sector_raw = root / "sector_raw.csv"

    pd.DataFrame(
        [
            {
                "证券代码": "001339.SZ",
                "证券简称": "智微智能",
                "连板天数": "3",
                "所属概念": "芯片;算力",
                "所属同花顺行业": "通信设备",
                "日期": "20260618",
            },
            {
                "证券代码": "600171.SH",
                "证券简称": "上海贝岭",
                "连板天数": "1",
                "所属概念": "芯片",
                "所属同花顺行业": "半导体",
                "日期": "20260618",
            },
        ]
    ).to_csv(limitup_raw, index=False, encoding="utf-8-sig")

    pd.DataFrame(
        [
            {
                "日期": "20260618",
                "板块代码": "001042_301085",
                "板块名称": "芯片概念",
                "涨跌幅": "1.56%",
                "成交金额": "1.5784万亿",
                "净主动买入额": "107.1316亿",
                "成分股个数": "892",
                "换手率": "5.9668",
            }
        ]
    ).to_csv(sector_raw, index=False, encoding="utf-8-sig")

    with (
        mock.patch.object(structure_module, "ROOT", root),
        mock.patch.object(
            structure_module,
            "IFindLimitupLadderProvider",
            return_value=IFindLimitupLadderProvider(base_path=str(root / "AmazingData_Store")),
        ),
        mock.patch.object(
            structure_module,
            "IFindSectorStrengthProvider",
            return_value=IFindSectorStrengthProvider(base_path=str(root / "AmazingData_Store")),
        ),
    ):
        payload = structure_module.evaluate(20260618, str(limitup_raw), str(sector_raw))
        json_path, md_path = structure_module.write_outputs(payload)

    assert payload["date"] == "20260618"
    assert payload["limitup_ladder_summary"][0]["limitup_tier"] == "1板"
    assert payload["top_themes_by_limitup_diffusion"][0]["theme"] == "芯片"
    assert payload["top_sectors_by_strength"][0]["sector_name"] == "芯片概念"
    assert payload["recommended_leading_cluster_inputs"][0]["cluster"] == "芯片"
    assert json.loads(json_path.read_text(encoding="utf-8"))["date"] == "20260618"
    assert md_path.exists()
