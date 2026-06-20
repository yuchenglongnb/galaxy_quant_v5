# -*- coding: utf-8 -*-

import pandas as pd

from providers.ifind_limitup_ladder_provider import IFindLimitupLadderProvider


def test_limitup_snapshot_normalizes_missing_days_and_signal_concepts(tmp_path):
    provider = IFindLimitupLadderProvider(base_path=str(tmp_path / "store"))
    raw = pd.DataFrame(
        [
            {
                "证券代码": "001339.SZ",
                "证券简称": "智微智能",
                "连板天数": "3",
                "所属概念": "芯片;同花顺出海50;算力",
                "所属同花顺行业": "通信设备",
                "日期": "2026-06-18",
            },
            {
                "证券代码": "603989.SH",
                "证券简称": "艾华集团",
                "连板天数": "",
                "所属概念": "被动元件;消费电子",
                "所属同花顺行业": "电子元件",
                "日期": "20260618",
            },
        ]
    )

    snapshot = provider.normalize_snapshot(raw, default_date=20260618)

    assert list(snapshot["code"]) == ["001339.SZ", "603989.SH"]
    first = snapshot.iloc[0]
    assert first["limitup_tier"] == "3板"
    assert "芯片" in first["signal_concepts"]
    assert "同花顺出海50" not in first["signal_concepts"]

    second = snapshot.iloc[1]
    assert pd.isna(second["limitup_days"])
    assert bool(second["missing_limitup_days"]) is True
    assert second["limitup_tier"] == "未知"


def test_theme_distribution_counts_by_tier(tmp_path):
    provider = IFindLimitupLadderProvider(base_path=str(tmp_path / "store"))
    snapshot = pd.DataFrame(
        [
            {
                "date": "20260618",
                "code": "001339.SZ",
                "name": "智微智能",
                "limitup": True,
                "limitup_days": 3,
                "limitup_tier": "3板",
                "concepts": "芯片;算力",
                "signal_concepts": "芯片;算力",
                "ths_industry": "通信设备",
                "source": "ifind.mcp.limitup_snapshot",
                "missing_limitup_days": False,
            },
            {
                "date": "20260618",
                "code": "600171.SH",
                "name": "上海贝岭",
                "limitup": True,
                "limitup_days": 1,
                "limitup_tier": "1板",
                "concepts": "芯片",
                "signal_concepts": "芯片",
                "ths_industry": "半导体",
                "source": "ifind.mcp.limitup_snapshot",
                "missing_limitup_days": False,
            },
        ]
    )

    result = provider.build_theme_distribution(snapshot, date_int=20260618)
    chip = result.loc[result["theme"] == "芯片"].iloc[0]
    assert int(chip["limitup_count"]) == 2
    assert int(chip["first_board_count"]) == 1
    assert int(chip["third_board_count"]) == 1
