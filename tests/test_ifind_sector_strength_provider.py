# -*- coding: utf-8 -*-

import pandas as pd

from providers.ifind_sector_strength_provider import IFindSectorStrengthProvider


def test_sector_strength_snapshot_normalizes_units_and_scores(tmp_path):
    provider = IFindSectorStrengthProvider(base_path=str(tmp_path / "store"))
    raw = pd.DataFrame(
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
            },
            {
                "日期": "20260618",
                "板块代码": "801088",
                "板块名称": "有色金属",
                "涨跌幅": "-0.53%",
                "成交金额": "253.6亿",
                "净主动买入额": "-2.18亿",
                "成分股个数": "126",
                "换手率": "1.42",
            },
        ]
    )

    snapshot = provider.normalize_snapshot(raw, default_date=20260618)

    first = snapshot.iloc[0]
    assert first["sector_name"] == "芯片概念"
    assert float(first["amount_yuan"]) > 1e12
    assert float(first["net_active_buy_yuan"]) > 1e10
    assert float(first["sector_strength_score"]) > 0

    second = snapshot.loc[snapshot["sector_name"] == "有色金属"].iloc[0]
    assert float(second["amount_yuan"]) == 253.6e8
    assert float(second["net_active_buy_yuan"]) == -2.18e8


def test_sector_strength_score_is_orderable(tmp_path):
    provider = IFindSectorStrengthProvider(base_path=str(tmp_path / "store"))
    raw = pd.DataFrame(
        [
            {"date": "20260618", "sector_name": "强板块", "pct": "2.5", "amount": "500亿", "net_active_buy": "20亿", "member_count": "100", "turnover_rate": "4.0"},
            {"date": "20260618", "sector_name": "弱板块", "pct": "-1.0", "amount": "30亿", "net_active_buy": "-5亿", "member_count": "50", "turnover_rate": "0.8"},
        ]
    )

    snapshot = provider.normalize_snapshot(raw, default_date=20260618)
    strong = snapshot.loc[snapshot["sector_name"] == "强板块", "sector_strength_score"].iloc[0]
    weak = snapshot.loc[snapshot["sector_name"] == "弱板块", "sector_strength_score"].iloc[0]
    assert float(strong) > float(weak)
