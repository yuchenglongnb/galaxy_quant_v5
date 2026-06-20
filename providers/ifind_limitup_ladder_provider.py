# -*- coding: utf-8 -*-
"""Normalize iFinD market-structure limit-up ladder snapshots."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from config.settings import DBConfig
from providers.ifind_theme_provider import IFindThemeProvider, _split_items
from providers.qstock_provider import _normalize_a_code, _read_csv_auto


@dataclass
class IFindLimitupLadderProvider:
    """Standardize limit-up ladder raw CSV snapshots exported from iFinD MCP."""

    base_path: str = DBConfig.STORE_PATH

    OUTPUT_COLUMNS = [
        "date",
        "code",
        "name",
        "limitup",
        "limitup_days",
        "limitup_tier",
        "concepts",
        "signal_concepts",
        "ths_industry",
        "source",
        "missing_limitup_days",
    ]

    def __post_init__(self):
        self._theme_provider = IFindThemeProvider(base_path=self.base_path)

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

    def load_raw(self, path: str) -> pd.DataFrame:
        return _read_csv_auto(path)

    def normalize_snapshot(self, raw: pd.DataFrame, default_date: Optional[int] = None) -> pd.DataFrame:
        frame = raw.copy()
        frame = self._standardize_columns(frame)

        for col in ("code", "name", "limitup_days", "concepts", "signal_concepts", "ths_industry", "date"):
            if col not in frame.columns:
                frame[col] = ""

        frame["code"] = frame["code"].map(_normalize_a_code)
        frame["name"] = frame["name"].fillna("").astype(str).str.strip()
        frame["date"] = frame["date"].map(lambda value: self._normalize_date(value, default_date))

        frame["concepts"] = frame["concepts"].fillna("").map(
            lambda value: ";".join(sorted(set(_split_items(value))))
        )
        provided_signal = frame["signal_concepts"].fillna("").map(_split_items)
        frame["signal_concepts"] = [
            ";".join(signal_items if signal_items else self._theme_provider.filter_signal_concepts(_split_items(concepts)))
            for signal_items, concepts in zip(provided_signal, frame["concepts"])
        ]
        frame["ths_industry"] = frame["ths_industry"].fillna("").astype(str).str.strip()

        frame["limitup_days"] = frame["limitup_days"].map(self._normalize_limitup_days)
        frame["missing_limitup_days"] = frame["limitup_days"].isna()
        frame["limitup"] = True
        frame["limitup_tier"] = frame["limitup_days"].map(self._classify_tier)
        frame["source"] = "ifind.mcp.limitup_snapshot"

        result = (
            frame[self.OUTPUT_COLUMNS]
            .drop_duplicates(subset=["date", "code"], keep="last")
            .sort_values(["date", "limitup_days", "code"], ascending=[True, False, True], na_position="last")
            .reset_index(drop=True)
        )
        return result

    def apply_raw_snapshot(self, raw_path: str, date_int: Optional[int] = None) -> pd.DataFrame:
        raw = self.load_raw(raw_path)
        snapshot = self.normalize_snapshot(raw, default_date=date_int)
        inferred_date = self._resolve_date_int(snapshot, date_int)
        self._save(snapshot, "limitup_ladder_snapshot.csv", inferred_date)
        return snapshot

    def build_theme_distribution(self, snapshot: pd.DataFrame, date_int: Optional[int] = None) -> pd.DataFrame:
        rows = []
        for _, row in snapshot.iterrows():
            themes = self._theme_values(row) or ["unknown"]
            for theme in themes:
                rows.append(
                    {
                        "date": row.get("date", ""),
                        "theme": theme,
                        "code": row.get("code", ""),
                        "name": row.get("name", ""),
                        "limitup_days": row.get("limitup_days"),
                        "limitup_tier": row.get("limitup_tier", "未知"),
                    }
                )

        frame = pd.DataFrame(rows)
        if frame.empty:
            result = pd.DataFrame(
                columns=[
                    "date",
                    "theme",
                    "limitup_count",
                    "first_board_count",
                    "second_board_count",
                    "third_board_count",
                    "high_board_count",
                    "max_limitup_days",
                    "core_codes",
                    "core_names",
                ]
            )
        else:
            def count_tier(group: pd.DataFrame, tier_name: str) -> int:
                return int((group["limitup_tier"] == tier_name).sum())

            summaries = []
            for (date_value, theme), group in frame.groupby(["date", "theme"], dropna=False):
                ordered = group.sort_values(["limitup_days", "code"], ascending=[False, True], na_position="last")
                summaries.append(
                    {
                        "date": date_value,
                        "theme": theme,
                        "limitup_count": int(len(group)),
                        "first_board_count": count_tier(group, "1板"),
                        "second_board_count": count_tier(group, "2板"),
                        "third_board_count": count_tier(group, "3板"),
                        "high_board_count": count_tier(group, "高度板"),
                        "max_limitup_days": self._safe_max(group["limitup_days"]),
                        "core_codes": ";".join(ordered["code"].head(5).astype(str)),
                        "core_names": ";".join(ordered["name"].head(5).astype(str)),
                    }
                )
            result = pd.DataFrame(summaries).sort_values(
                ["limitup_count", "high_board_count", "third_board_count", "theme"],
                ascending=[False, False, False, True],
            ).reset_index(drop=True)

        inferred_date = self._resolve_date_int(snapshot, date_int)
        self._save(result, "theme_limitup_distribution.csv", inferred_date)
        return result

    @staticmethod
    def _normalize_date(value: object, default_date: Optional[int]) -> str:
        text = str(value or "").strip()
        if not text or text.upper() == "NAN":
            return str(default_date or "")
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) >= 8:
            return digits[:8]
        return str(default_date or text)

    @staticmethod
    def _normalize_limitup_days(value: object):
        text = str(value or "").strip()
        if not text or text.upper() == "NAN":
            return pd.NA
        try:
            number = int(float(text))
        except Exception:
            return pd.NA
        return number if number > 0 else pd.NA

    @staticmethod
    def _classify_tier(value: object) -> str:
        if pd.isna(value):
            return "未知"
        number = int(value)
        if number == 1:
            return "1板"
        if number == 2:
            return "2板"
        if number == 3:
            return "3板"
        if number >= 4:
            return "高度板"
        return "未知"

    @staticmethod
    def _safe_max(series: pd.Series):
        numeric = pd.to_numeric(series, errors="coerce").dropna()
        if numeric.empty:
            return pd.NA
        return int(numeric.max())

    @staticmethod
    def _resolve_date_int(snapshot: pd.DataFrame, date_int: Optional[int]) -> int:
        if date_int is not None:
            return int(date_int)
        if snapshot.empty:
            return int(pd.Timestamp.now().strftime("%Y%m%d"))
        first = str(snapshot.iloc[0].get("date", "") or "").strip()
        return int(first) if first.isdigit() and len(first) == 8 else int(pd.Timestamp.now().strftime("%Y%m%d"))

    @staticmethod
    def _theme_values(row) -> list[str]:
        signal_concepts = _split_items(row.get("signal_concepts", ""))
        if signal_concepts:
            return signal_concepts
        concepts = _split_items(row.get("concepts", ""))
        if concepts:
            return concepts
        ths_industry = str(row.get("ths_industry", "") or "").strip()
        return [ths_industry] if ths_industry else []

    @classmethod
    def _standardize_columns(cls, frame: pd.DataFrame) -> pd.DataFrame:
        alias_map = {
            "code": ["code", "证券代码", "股票代码", "浠ｇ爜", "璇佸埜浠ｇ爜", "鑲＄エ浠ｇ爜"],
            "name": ["name", "证券简称", "股票简称", "简称", "绠€绉?", "璇佸埜绠€绉?", "鑲＄エ绠€绉?"],
            "limitup_days": ["limitup_days", "连板天数", "连板", "杩炴澘澶╂暟"],
            "concepts": ["concepts", "所属概念", "概念", "鎵€灞炴蹇?"],
            "signal_concepts": ["signal_concepts"],
            "ths_industry": ["ths_industry", "所属同花顺行业", "同花顺行业", "鎵€灞炲悓鑺遍『琛屼笟"],
            "date": ["date", "日期", "鏃ユ湡"],
        }
        rename_map = {}
        for canonical, aliases in alias_map.items():
            matched = cls._find_column(frame.columns, aliases)
            if matched:
                rename_map[matched] = canonical
        return frame.rename(columns=rename_map)

    @staticmethod
    def _find_column(columns, aliases):
        lowered = {str(col).strip().lower(): col for col in columns}
        for alias in aliases:
            key = str(alias).strip().lower()
            if key in lowered:
                return lowered[key]
        for col in columns:
            text = str(col).strip().lower()
            for alias in aliases:
                alias_key = str(alias).strip().lower()
                if alias_key and alias_key in text:
                    return col
        return None
