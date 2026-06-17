# -*- coding: utf-8 -*-
"""Local adapter for iFinD MCP-derived stock-theme snapshots.

This provider does not call MCP directly. Codex can use MCP in-session to
export/update snapshots, while the repository only depends on persisted CSVs.
That keeps AmazingData as the core market-data source and uses iFinD as a
theme/sector enrichment overlay for the tracked stock pool.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable, Optional

import pandas as pd

from config.settings import ConceptConfig, DBConfig, UniverseConfig
from providers.qstock_provider import _normalize_a_code, _read_csv_auto


def _split_items(value: object) -> list[str]:
    if pd.isna(value):
        return []
    text = str(value).strip()
    if not text:
        return []
    normalized = re.sub(r"[;,，、|]+", ";", text)
    return [item.strip() for item in normalized.split(";") if item.strip()]


@dataclass
class IFindThemeProvider:
    """Persist and apply iFinD stock-theme overlays to the local stock pool."""

    base_path: str = DBConfig.STORE_PATH
    stock_pool_path: str = UniverseConfig.STOCK_POOL_PATH
    overlay_path: str = "./watchlists/stock_pool_ifind_overlay.csv"

    OVERLAY_COLUMNS = [
        "code",
        "name",
        "ifind_ths_industry",
        "ifind_sw_industry",
        "ifind_concepts",
        "ifind_concept_count",
        "ifind_signal_concepts",
        "ifind_signal_concept_count",
        "ifind_updated_at",
        "ifind_source",
        "ifind_notes",
    ]

    def _date_dir(self, date_int: Optional[int] = None) -> str:
        if date_int is None:
            date_int = int(pd.Timestamp.now().strftime("%Y%m%d"))
        path = os.path.join(self.base_path, str(date_int), "ifind")
        os.makedirs(path, exist_ok=True)
        return path

    def _save(self, df: pd.DataFrame, filename: str, date_int: Optional[int] = None) -> str:
        path = os.path.join(self._date_dir(date_int), filename)
        df.to_csv(path, index=False, encoding="utf-8-sig")
        return path

    def load_stock_pool(self) -> pd.DataFrame:
        if not os.path.exists(self.stock_pool_path):
            return pd.DataFrame(columns=["code", "name", "group", "note"])
        pool = _read_csv_auto(self.stock_pool_path)
        if "code" not in pool.columns:
            return pd.DataFrame(columns=["code", "name", "group", "note"])
        pool["code"] = pool["code"].map(_normalize_a_code)
        return pool

    def load_overlay(self, path: Optional[str] = None) -> pd.DataFrame:
        path = path or self.overlay_path
        if not os.path.exists(path):
            return pd.DataFrame(columns=self.OVERLAY_COLUMNS)
        overlay = _read_csv_auto(path)
        for col in self.OVERLAY_COLUMNS:
            if col not in overlay.columns:
                overlay[col] = ""
        overlay["code"] = overlay["code"].map(_normalize_a_code)
        return overlay[self.OVERLAY_COLUMNS]

    def filter_signal_concepts(self, concepts: Iterable[str]) -> list[str]:
        useful: list[str] = []
        for concept in concepts:
            name = str(concept).strip()
            if not name:
                continue
            if name in ConceptConfig.THS_EXCLUDE_EXACT:
                continue
            if any(keyword in name for keyword in ConceptConfig.THS_EXCLUDE_KEYWORDS):
                continue
            if any(re.fullmatch(pattern, name) for pattern in ConceptConfig.THS_EXCLUDE_REGEX):
                continue
            useful.append(name)
        return sorted(set(useful))

    def normalize_snapshot(self, snapshot: pd.DataFrame) -> pd.DataFrame:
        frame = snapshot.copy()
        rename_map = {
            "证券代码": "code",
            "证券简称": "name",
            "所属同花顺行业": "ifind_ths_industry",
            "所属申万行业": "ifind_sw_industry",
            "所属概念": "ifind_concepts",
            "更新时间": "ifind_updated_at",
            "来源": "ifind_source",
            "备注": "ifind_notes",
        }
        frame = frame.rename(columns={k: v for k, v in rename_map.items() if k in frame.columns})
        for col in ("code", "name", "ifind_ths_industry", "ifind_sw_industry", "ifind_concepts"):
            if col not in frame.columns:
                frame[col] = ""
        frame["code"] = frame["code"].map(_normalize_a_code)
        if "ifind_updated_at" not in frame.columns:
            frame["ifind_updated_at"] = pd.Timestamp.now().isoformat(timespec="seconds")
        if "ifind_source" not in frame.columns:
            frame["ifind_source"] = "ifind.mcp.manual_snapshot"
        if "ifind_notes" not in frame.columns:
            frame["ifind_notes"] = ""

        frame["ifind_concepts"] = frame["ifind_concepts"].fillna("").map(
            lambda value: ";".join(sorted(set(_split_items(value))))
        )
        frame["ifind_concept_count"] = frame["ifind_concepts"].map(
            lambda value: 0 if not value else len(_split_items(value))
        )
        frame["ifind_signal_concepts"] = frame["ifind_concepts"].map(
            lambda value: ";".join(self.filter_signal_concepts(_split_items(value)))
        )
        frame["ifind_signal_concept_count"] = frame["ifind_signal_concepts"].map(
            lambda value: 0 if not value else len(_split_items(value))
        )
        for col in self.OVERLAY_COLUMNS:
            if col not in frame.columns:
                frame[col] = ""
        frame = frame[self.OVERLAY_COLUMNS].drop_duplicates(subset=["code"], keep="last")
        frame = frame.sort_values(["code", "name"]).reset_index(drop=True)
        return frame

    def apply_snapshot(
        self,
        snapshot: pd.DataFrame,
        output_path: Optional[str] = None,
        date_int: Optional[int] = None,
    ) -> pd.DataFrame:
        overlay = self.normalize_snapshot(snapshot)
        output_path = output_path or self.overlay_path
        overlay.to_csv(output_path, index=False, encoding="utf-8-sig")
        self._save(overlay, "stock_theme_snapshot.csv", date_int=date_int)
        exposure = self.build_concept_exposure(overlay, date_int=date_int)
        self._save(exposure, "stock_theme_exposure.csv", date_int=date_int)
        return overlay

    def build_concept_exposure(
        self,
        overlay: Optional[pd.DataFrame] = None,
        date_int: Optional[int] = None,
    ) -> pd.DataFrame:
        if overlay is None:
            overlay = self.load_overlay()
        rows = []
        for _, row in overlay.iterrows():
            for concept in _split_items(row.get("ifind_signal_concepts", "")):
                rows.append(
                    {
                        "concept": concept,
                        "code": row.get("code", ""),
                        "name": row.get("name", ""),
                        "ifind_ths_industry": row.get("ifind_ths_industry", ""),
                    }
                )
        exposed = pd.DataFrame(rows)
        if exposed.empty:
            result = pd.DataFrame(columns=["concept", "stock_count", "stocks", "industries"])
        else:
            result = (
                exposed.groupby("concept", as_index=False)
                .agg(
                    stock_count=("code", "nunique"),
                    stocks=("name", lambda s: ";".join(sorted(set(map(str, s))))),
                    industries=("ifind_ths_industry", lambda s: ";".join(sorted(set(x for x in map(str, s) if x)))),
                )
                .sort_values(["stock_count", "concept"], ascending=[False, True])
                .reset_index(drop=True)
            )
        if date_int is not None:
            self._save(result, "stock_theme_exposure.csv", date_int=date_int)
        return result

    def merge_overlay_into_stock_pool(self, output_path: Optional[str] = None) -> pd.DataFrame:
        pool = self.load_stock_pool()
        overlay = self.load_overlay()
        if pool.empty:
            return pool
        overlay_cols = [col for col in overlay.columns if col != "name"]
        merged = pool.merge(overlay[overlay_cols], on="code", how="left")
        output_path = output_path or os.path.join("watchlists", "stock_pool_ifind_merged_preview.csv")
        merged.to_csv(output_path, index=False, encoding="utf-8-sig")
        return merged

    def build_overlay_template(self, output_path: Optional[str] = None) -> pd.DataFrame:
        pool = self.load_stock_pool()
        template = pool[["code", "name"]].copy() if not pool.empty else pd.DataFrame(columns=["code", "name"])
        template["ifind_ths_industry"] = ""
        template["ifind_sw_industry"] = ""
        template["ifind_concepts"] = ""
        template["ifind_concept_count"] = 0
        template["ifind_signal_concepts"] = ""
        template["ifind_signal_concept_count"] = 0
        template["ifind_updated_at"] = ""
        template["ifind_source"] = "ifind.mcp.manual_snapshot"
        template["ifind_notes"] = ""
        output_path = output_path or self.overlay_path
        template.to_csv(output_path, index=False, encoding="utf-8-sig")
        return template
