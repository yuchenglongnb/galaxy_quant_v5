# -*- coding: utf-8 -*-

import json
from pathlib import Path
from unittest import mock

import pandas as pd

import scripts.evaluate_ifind_market_structure as structure_module
from providers.ifind_sector_strength_provider import IFindSectorStrengthProvider


def test_market_structure_script_supports_sector_only_mode(tmp_path):
    root = Path(tmp_path)
    sector_raw = root / "sector_raw.csv"

    pd.DataFrame(
        [
            {
                "日期": "20260616",
                "板块代码": "001042_308832",
                "板块名称": "PCB概念",
                "涨跌幅": "11.94%",
                "成交金额": "4373.9886亿",
                "DDE大单净额(合计)": "29.6381亿",
                "成分股个数": "220",
                "换手率": "5.40",
                "涨停股票数量": "7",
            }
        ]
    ).to_csv(sector_raw, index=False, encoding="utf-8-sig")

    with (
        mock.patch.object(structure_module, "ROOT", root),
        mock.patch.object(
            structure_module,
            "IFindSectorStrengthProvider",
            return_value=IFindSectorStrengthProvider(base_path=str(root / "AmazingData_Store")),
        ),
    ):
        payload = structure_module.evaluate(20260616, None, str(sector_raw), sector_only=True)
        json_path, md_path = structure_module.write_outputs(payload)

    assert payload["sector_only"] is True
    assert payload["limitup_ladder_summary"] == []
    assert payload["top_themes_by_limitup_diffusion"] == []
    assert payload["top_sectors_by_strength"][0]["sector_name"] == "PCB概念"
    assert "limitup_ladder_snapshot" not in payload["generated_files"]
    assert json.loads(json_path.read_text(encoding="utf-8"))["sector_only"] is True
    assert md_path.exists()
