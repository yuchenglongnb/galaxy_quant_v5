# -*- coding: utf-8 -*-
"""Normalize iFinD market-structure sector-strength snapshots."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from config.settings import DBConfig
from providers.qstock_provider import _read_csv_auto


@dataclass
class IFindSectorStrengthProvider:
    """Standardize sector-strength raw CSV snapshots exported from iFinD MCP."""

    base_path: str = DBConfig.STORE_PATH

    OUTPUT_COLUMNS = [
        "date",
        "sector_code",
        "sector_name",
        "pct",
        "amount_yuan",
        "net_active_buy_yuan",
        "dde_net_buy_yuan",
        "member_count",
        "turnover_rate",
        "limitup_count",
        "limitup_ratio",
        "sector_strength_score",
        "source",
    ]

    COLUMN_ALIASES = {
        "date": ["date", "日期", "交易日期"],
        "sector_code": ["sector_code", "板块代码", "概念代码", "sector id"],
        "sector_name": ["sector_name", "板块名称", "概念名称", "concept", "name", "名称"],
        "pct": ["pct", "涨跌幅", "涨幅", "pctchg"],
        "amount_yuan": ["amount_yuan", "成交金额", "成交额", "amount"],
        "net_active_buy_yuan": [
            "net_active_buy_yuan",
            "净主动买入额",
            "主力净额",
            "近1日主力净额",
            "net_active_buy",
        ],
        "dde_net_buy_yuan": [
            "dde_net_buy_yuan",
            "DDE大单净额",
            "DDE大单净额(合计)",
            "dde",
        ],
        "member_count": ["member_count", "成分股个数", "股票数", "member num"],
        "turnover_rate": ["turnover_rate", "换手率", "turnover"],
        "limitup_count": ["limitup_count", "涨停股票数量", "涨停家数", "limit up count"],
    }

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
        frame = self._standardize_columns(raw.copy())
        for col in self.OUTPUT_COLUMNS:
            if col not in frame.columns and col not in {"source", "sector_strength_score", "limitup_ratio"}:
                frame[col] = ""

        frame["date"] = frame["date"].map(lambda value: self._normalize_date(value, default_date))
        frame["sector_code"] = frame["sector_code"].fillna("").astype(str).str.strip()
        frame["sector_name"] = frame["sector_name"].fillna("").astype(str).str.strip()
        frame["pct"] = frame["pct"].map(self._parse_pct)
        frame["amount_yuan"] = frame["amount_yuan"].map(self._parse_amount)
        frame["net_active_buy_yuan"] = frame["net_active_buy_yuan"].map(self._parse_amount)
        frame["dde_net_buy_yuan"] = frame["dde_net_buy_yuan"].map(self._parse_amount)
        frame["member_count"] = frame["member_count"].map(self._parse_int)
        frame["turnover_rate"] = frame["turnover_rate"].map(self._parse_pct)
        frame["limitup_count"] = frame["limitup_count"].map(self._parse_int)
        frame["limitup_ratio"] = frame.apply(self._build_limitup_ratio, axis=1)
        frame["sector_strength_score"] = frame.apply(self._score_row, axis=1)
        frame["source"] = "ifind.mcp.sector_strength_snapshot"

        return (
            frame[self.OUTPUT_COLUMNS]
            .drop_duplicates(subset=["date", "sector_code", "sector_name"], keep="last")
            .sort_values(["date", "sector_strength_score", "sector_name"], ascending=[True, False, True], na_position="last")
            .reset_index(drop=True)
        )

    def apply_raw_snapshot(self, raw_path: str, date_int: Optional[int] = None) -> pd.DataFrame:
        raw = self.load_raw(raw_path)
        snapshot = self.normalize_snapshot(raw, default_date=date_int)
        inferred_date = self._resolve_date_int(snapshot, date_int)
        self._save(snapshot, "sector_strength_snapshot.csv", inferred_date)
        return snapshot

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
    def _parse_pct(value: object):
        text = str(value or "").strip().replace(",", "")
        if not text or text.upper() == "NAN":
            return pd.NA
        text = text.replace("%", "")
        try:
            return float(text)
        except Exception:
            return pd.NA

    @staticmethod
    def _parse_int(value: object):
        text = str(value or "").strip().replace(",", "")
        if not text or text.upper() == "NAN":
            return pd.NA
        try:
            return int(float(text))
        except Exception:
            return pd.NA

    @staticmethod
    def _parse_amount(value: object):
        text = str(value or "").strip().replace(",", "")
        if not text or text.upper() == "NAN":
            return pd.NA
        multiplier = 1.0
        if text.endswith("万亿"):
            multiplier = 1e12
            text = text[:-2]
        elif text.endswith("亿"):
            multiplier = 1e8
            text = text[:-1]
        elif text.endswith("万"):
            multiplier = 1e4
            text = text[:-1]
        elif text.endswith("元"):
            text = text[:-1]
        try:
            return float(text) * multiplier
        except Exception:
            return pd.NA

    @staticmethod
    def _build_limitup_ratio(row: pd.Series):
        count = row.get("limitup_count")
        members = row.get("member_count")
        if pd.isna(count) or pd.isna(members):
            return pd.NA
        try:
            members_value = float(members)
            if members_value <= 0:
                return pd.NA
            return round(float(count) / members_value, 6)
        except Exception:
            return pd.NA

    @staticmethod
    def _score_component(value: object, scale: float, cap: float) -> float:
        if pd.isna(value):
            return 0.0
        clipped = max(min(float(value) / scale, cap), -cap)
        return clipped

    @classmethod
    def _score_row(cls, row: pd.Series) -> float:
        pct_score = cls._score_component(row.get("pct"), scale=1.0, cap=35.0)
        amount_value = row.get("amount_yuan")
        amount_score = 0.0 if pd.isna(amount_value) else max(min(math.log10(max(float(amount_value), 1.0)) - 8.0, 20.0), 0.0)
        net_buy_value = row.get("net_active_buy_yuan")
        if pd.isna(net_buy_value):
            net_buy_value = row.get("dde_net_buy_yuan")
        net_buy_score = 0.0 if pd.isna(net_buy_value) else max(min(float(net_buy_value) / 1e8, 25.0), -20.0)
        turnover_score = cls._score_component(row.get("turnover_rate"), scale=0.5, cap=20.0)
        limitup_ratio = row.get("limitup_ratio")
        breadth_score = 0.0 if pd.isna(limitup_ratio) else max(min(float(limitup_ratio) * 10.0, 20.0), 0.0)
        return round(pct_score + amount_score + net_buy_score + turnover_score + breadth_score, 2)

    @staticmethod
    def _resolve_date_int(snapshot: pd.DataFrame, date_int: Optional[int]) -> int:
        if date_int is not None:
            return int(date_int)
        if snapshot.empty:
            return int(pd.Timestamp.now().strftime("%Y%m%d"))
        first = str(snapshot.iloc[0].get("date", "") or "").strip()
        return int(first) if first.isdigit() and len(first) == 8 else int(pd.Timestamp.now().strftime("%Y%m%d"))

    @classmethod
    def _standardize_columns(cls, frame: pd.DataFrame) -> pd.DataFrame:
        rename_map = {}
        for canonical, aliases in cls.COLUMN_ALIASES.items():
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
