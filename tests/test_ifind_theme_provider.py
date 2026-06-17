# -*- coding: utf-8 -*-

from pathlib import Path

import pandas as pd

from providers.ifind_theme_provider import IFindThemeProvider


def _write_pool(path: Path):
    path.write_text(
        "code,name,group,note\n"
        "601138.SH,工业富联,消费电子零部件及组装,test\n"
        "300476.SZ,胜宏科技,印制电路板,test\n",
        encoding="utf-8-sig",
    )


def test_apply_snapshot_normalizes_and_filters_signal_concepts(tmp_path):
    pool_path = tmp_path / "stock_pool.csv"
    overlay_path = tmp_path / "stock_pool_ifind_overlay.csv"
    _write_pool(pool_path)

    provider = IFindThemeProvider(
        base_path=str(tmp_path / "store"),
        stock_pool_path=str(pool_path),
        overlay_path=str(overlay_path),
    )
    snapshot = pd.DataFrame(
        [
            {
                "证券代码": "601138.SH",
                "证券简称": "工业富联",
                "所属同花顺行业": "电子",
                "所属申万行业": "电子",
                "所属概念": "人工智能,同花顺果指数,东数西算(算力),2025年报预增",
                "更新时间": "2026-06-16T20:30:00",
            },
            {
                "证券代码": "300476.SZ",
                "证券简称": "胜宏科技",
                "所属同花顺行业": "电子",
                "所属申万行业": "电子",
                "所属概念": "AI手机,PCB概念,人形机器人,同花顺出海50",
                "更新时间": "2026-06-16T20:30:00",
            },
        ]
    )

    overlay = provider.apply_snapshot(snapshot, date_int=20260616)

    assert len(overlay) == 2
    row = overlay.loc[overlay["code"] == "601138.SH"].iloc[0]
    assert row["ifind_ths_industry"] == "电子"
    assert "人工智能" in row["ifind_signal_concepts"]
    assert "同花顺果指数" not in row["ifind_signal_concepts"]
    assert "2025年报预增" not in row["ifind_signal_concepts"]


def test_build_concept_exposure_summarizes_overlay(tmp_path):
    provider = IFindThemeProvider(
        base_path=str(tmp_path / "store"),
        stock_pool_path=str(tmp_path / "stock_pool.csv"),
        overlay_path=str(tmp_path / "overlay.csv"),
    )
    overlay = pd.DataFrame(
        [
            {
                "code": "601138.SH",
                "name": "工业富联",
                "ifind_ths_industry": "电子",
                "ifind_sw_industry": "电子",
                "ifind_concepts": "人工智能;东数西算(算力)",
                "ifind_concept_count": 2,
                "ifind_signal_concepts": "人工智能;东数西算(算力)",
                "ifind_signal_concept_count": 2,
                "ifind_updated_at": "2026-06-16T20:30:00",
                "ifind_source": "ifind.mcp.manual_snapshot",
                "ifind_notes": "",
            },
            {
                "code": "300476.SZ",
                "name": "胜宏科技",
                "ifind_ths_industry": "电子",
                "ifind_sw_industry": "电子",
                "ifind_concepts": "AI手机;PCB概念;人工智能",
                "ifind_concept_count": 3,
                "ifind_signal_concepts": "AI手机;PCB概念;人工智能",
                "ifind_signal_concept_count": 3,
                "ifind_updated_at": "2026-06-16T20:30:00",
                "ifind_source": "ifind.mcp.manual_snapshot",
                "ifind_notes": "",
            },
        ]
    )

    exposure = provider.build_concept_exposure(overlay=overlay)

    top = exposure.iloc[0]
    assert top["concept"] == "人工智能"
    assert int(top["stock_count"]) == 2


def test_merge_overlay_joins_on_code_not_name(tmp_path):
    pool_path = tmp_path / "stock_pool.csv"
    overlay_path = tmp_path / "stock_pool_ifind_overlay.csv"
    _write_pool(pool_path)
    overlay_path.write_text(
        "code,name,ifind_ths_industry,ifind_sw_industry,ifind_concepts,ifind_concept_count,ifind_signal_concepts,ifind_signal_concept_count,ifind_updated_at,ifind_source,ifind_notes\n"
        "601138.SH,FII工业富联,电子,电子,人工智能,1,人工智能,1,2026-06-16T20:30:00,ifind.mcp.manual_snapshot,\n",
        encoding="utf-8-sig",
    )
    provider = IFindThemeProvider(
        base_path=str(tmp_path / "store"),
        stock_pool_path=str(pool_path),
        overlay_path=str(overlay_path),
    )

    merged = provider.merge_overlay_into_stock_pool(output_path=str(tmp_path / "merged.csv"))

    row = merged.loc[merged["code"] == "601138.SH"].iloc[0]
    assert row["name"] == "工业富联"
    assert row["ifind_ths_industry"] == "电子"
