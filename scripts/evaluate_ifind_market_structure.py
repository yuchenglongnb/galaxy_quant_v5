# -*- coding: utf-8 -*-
"""Evaluate iFinD market-structure snapshots exported to local CSV files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from providers.ifind_limitup_ladder_provider import IFindLimitupLadderProvider
from providers.ifind_sector_strength_provider import IFindSectorStrengthProvider
from utils.encoding import configure_utf8_console


def _top_theme_rows(theme_distribution: pd.DataFrame, limit: int = 10) -> list[dict]:
    if theme_distribution.empty:
        return []
    return theme_distribution.head(limit).to_dict(orient="records")


def _top_sector_rows(sector_snapshot: pd.DataFrame, limit: int = 10) -> list[dict]:
    if sector_snapshot.empty:
        return []
    return sector_snapshot.head(limit).to_dict(orient="records")


def _tier_summary(limitup_snapshot: pd.DataFrame) -> list[dict]:
    if limitup_snapshot.empty:
        return []
    order = ["1板", "2板", "3板", "高度板", "未知"]
    counts = (
        limitup_snapshot.groupby("limitup_tier", as_index=False)
        .agg(count=("code", "count"))
        .set_index("limitup_tier")
        .reindex(order, fill_value=0)
        .reset_index()
    )
    return counts.to_dict(orient="records")


def _normalize_key(text: object) -> str:
    raw = str(text or "").strip().lower()
    return raw.replace("概念", "").replace("板块", "").replace("主题", "").replace(" ", "")


def _recommended_clusters(theme_distribution: pd.DataFrame, sector_snapshot: pd.DataFrame, limit: int = 8) -> list[dict]:
    sector_by_key = {}
    for _, row in sector_snapshot.iterrows():
        key = _normalize_key(row.get("sector_name", ""))
        if key and key not in sector_by_key:
            sector_by_key[key] = row

    rows = []
    for _, row in theme_distribution.head(limit).iterrows():
        theme = row.get("theme", "")
        key = _normalize_key(theme)
        sector_row = sector_by_key.get(key)
        evidence = ["limitup_ladder_diffusion"]
        if sector_row is not None:
            evidence.append("sector_strength_confirmed")
        rows.append(
            {
                "cluster": theme,
                "evidence": evidence,
                "related_themes": [theme],
                "core_codes": [code for code in str(row.get("core_codes", "")).split(";") if code],
                "core_names": [name for name in str(row.get("core_names", "")).split(";") if name],
                "sector_strength_score": None if sector_row is None else sector_row.get("sector_strength_score"),
            }
        )
    return rows


def evaluate(date_int: int, limitup_raw: str, sector_raw: str) -> dict:
    limitup_provider = IFindLimitupLadderProvider()
    sector_provider = IFindSectorStrengthProvider()

    limitup_snapshot = limitup_provider.apply_raw_snapshot(limitup_raw, date_int=date_int)
    theme_distribution = limitup_provider.build_theme_distribution(limitup_snapshot, date_int=date_int)
    sector_snapshot = sector_provider.apply_raw_snapshot(sector_raw, date_int=date_int)

    payload = {
        "date": str(date_int),
        "data_sources": {
            "limitup_raw": str(Path(limitup_raw)),
            "sector_raw": str(Path(sector_raw)),
        },
        "limitup_ladder_summary": _tier_summary(limitup_snapshot),
        "top_themes_by_limitup_diffusion": _top_theme_rows(theme_distribution),
        "top_sectors_by_strength": _top_sector_rows(sector_snapshot),
        "recommended_leading_cluster_inputs": _recommended_clusters(theme_distribution, sector_snapshot),
        "generated_files": {
            "limitup_ladder_snapshot": str(ROOT / "AmazingData_Store" / str(date_int) / "ifind" / "limitup_ladder_snapshot.csv"),
            "sector_strength_snapshot": str(ROOT / "AmazingData_Store" / str(date_int) / "ifind" / "sector_strength_snapshot.csv"),
            "theme_limitup_distribution": str(ROOT / "AmazingData_Store" / str(date_int) / "ifind" / "theme_limitup_distribution.csv"),
        },
    }
    return payload


def write_outputs(payload: dict) -> tuple[Path, Path]:
    date_int = payload["date"]
    out_dir = ROOT / "reports" / "analysis" / "evaluations"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"ifind_market_structure_{date_int}.json"
    md_path = out_dir / f"ifind_market_structure_{date_int}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# iFinD Market Structure {date_int}",
        "",
        "## Data Sources",
        "",
        f"- limitup_raw: `{payload['data_sources']['limitup_raw']}`",
        f"- sector_raw: `{payload['data_sources']['sector_raw']}`",
        "",
        "## Limit-up Ladder Summary",
        "",
        "| tier | count |",
        "|---|---:|",
    ]
    for row in payload["limitup_ladder_summary"]:
        lines.append(f"| {row.get('limitup_tier', '')} | {row.get('count', 0)} |")

    lines.extend(
        [
            "",
            "## Top Themes by Limit-up Diffusion",
            "",
            "| theme | limitup_count | second_board_count | third_board_count | high_board_count | max_limitup_days | core_names |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in payload["top_themes_by_limitup_diffusion"]:
        lines.append(
            f"| {row.get('theme', '')} | {row.get('limitup_count', 0)} | {row.get('second_board_count', 0)} | "
            f"{row.get('third_board_count', 0)} | {row.get('high_board_count', 0)} | {row.get('max_limitup_days', '')} | "
            f"{row.get('core_names', '')} |"
        )

    lines.extend(
        [
            "",
            "## Top Sectors by Strength",
            "",
            "| sector_name | pct | amount_yuan | net_active_buy_yuan | turnover_rate | member_count | sector_strength_score |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload["top_sectors_by_strength"]:
        lines.append(
            f"| {row.get('sector_name', '')} | {row.get('pct', '')} | {row.get('amount_yuan', '')} | "
            f"{row.get('net_active_buy_yuan', '')} | {row.get('turnover_rate', '')} | {row.get('member_count', '')} | "
            f"{row.get('sector_strength_score', '')} |"
        )

    lines.extend(
        [
            "",
            "## Recommended Leading Cluster Inputs",
            "",
            "```json",
            json.dumps(payload["recommended_leading_cluster_inputs"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## Generated Files",
            "",
        ]
    )
    for name, path in payload["generated_files"].items():
        lines.append(f"- {name}: `{path}`")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main():
    configure_utf8_console()
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, type=int)
    parser.add_argument("--limitup-raw", required=True)
    parser.add_argument("--sector-raw", required=True)
    args = parser.parse_args()

    payload = evaluate(args.date, args.limitup_raw, args.sector_raw)
    json_path, md_path = write_outputs(payload)
    print(f"[ok] market structure json: {json_path}")
    print(f"[ok] market structure md: {md_path}")


if __name__ == "__main__":
    main()
