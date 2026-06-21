# -*- coding: utf-8 -*-
"""Compute open-session relative-strength and amount confirmation features."""

from __future__ import annotations

import os
import unicodedata
from typing import Dict, Optional

import numpy as np
import pandas as pd

from config.settings import UniverseConfig


class IntradayConfirmationBuilder:
    """Build point-in-time execution features from accumulated minute snapshots."""

    DEFAULT_INDEX_CODE = "000001.SH"
    DEFAULT_INDEX_NAME = "上证指数"
    BOARD_INDEX_RULES = (
        ("688", ".SH", "000688.SH", "科创50", "STAR board fallback"),
        ("60", ".SH", "000001.SH", "上证指数", "SSE main-board fallback"),
        ("300", ".SZ", "399006.SZ", "创业板指", "ChiNext board fallback"),
        ("002", ".SZ", "399001.SZ", "深证成指", "SZSE main-board fallback"),
        ("001", ".SZ", "399001.SZ", "深证成指", "SZSE main-board fallback"),
        ("000", ".SZ", "399001.SZ", "深证成指", "SZSE main-board fallback"),
        ("8", ".BJ", "899050.BJ", "北证50", "BSE board fallback"),
        ("4", ".BJ", "899050.BJ", "北证50", "BSE board fallback"),
    )

    @classmethod
    def build(
        cls,
        stocks: pd.DataFrame,
        etfs: pd.DataFrame,
        indices: pd.DataFrame,
        benchmark_map: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        if stocks is None or stocks.empty:
            return pd.DataFrame()

        stock_features = cls._summarize(stocks)
        etf_features = cls._summarize(etfs)
        index_features = cls._summarize(indices)
        mapping = cls._normalize_benchmark_map(
            benchmark_map if benchmark_map is not None else cls.load_benchmark_map()
        )

        rows = []
        for _, stock in stock_features.iterrows():
            group = cls._normalize_group_key(stock.get("group", ""))
            benchmark = cls.resolve_benchmark(
                group=group,
                stock_code=str(stock.get("code", "") or ""),
                benchmark_map=mapping,
                existing_etf_code=str(stock.get("benchmark_etf_code", "") or ""),
                existing_index_code=str(stock.get("benchmark_index_code", "") or ""),
            )
            etf_code = benchmark.get("benchmark_etf_code", "")
            index_code = benchmark.get("benchmark_index_code", cls.DEFAULT_INDEX_CODE)
            etf = cls._lookup(etf_features, etf_code)
            index = cls._lookup(index_features, index_code)
            if index is None and index_code != cls.DEFAULT_INDEX_CODE:
                index_code = cls.DEFAULT_INDEX_CODE
                index = cls._lookup(index_features, index_code)
                benchmark["benchmark_index_code"] = index_code
                benchmark["benchmark_source"] = "default_index_fallback"
                benchmark["benchmark_fallback_level"] = "market_index"
                benchmark["benchmark_fallback_reason"] = "benchmark_index_not_found_in_intraday_cache"
                benchmark["board_index_code"] = ""
                benchmark["board_index_name"] = ""
                benchmark["board_index_fallback_used"] = False

            row = stock.to_dict()
            row.update(benchmark)
            row["rs_vs_etf_pct"] = cls._difference(stock, etf, "pct")
            row["rs_vs_index_pct"] = cls._difference(stock, index, "pct")
            row["rs_open_vs_etf_pct"] = cls._difference(stock, etf, "price_vs_open_pct")
            row["rs_open_vs_index_pct"] = cls._difference(stock, index, "price_vs_open_pct")
            row["volume_price_state"] = cls._volume_price_state(row)
            row["execution_bias"] = cls._execution_bias(row)
            rows.append(row)
        return pd.DataFrame(rows)

    @classmethod
    def load_benchmark_map(cls) -> pd.DataFrame:
        path = UniverseConfig.STOCK_BENCHMARK_MAP_PATH
        if not path or not os.path.exists(path):
            return pd.DataFrame()
        try:
            return pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
        except UnicodeDecodeError:
            return pd.read_csv(path, dtype=str, encoding="gb18030").fillna("")

    @classmethod
    def _summarize(cls, df: Optional[pd.DataFrame]) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        work = df.copy()
        for column in ["last", "open", "pre_close", "amount_1min", "time_int"]:
            if column not in work.columns:
                work[column] = 0
            work[column] = pd.to_numeric(work[column], errors="coerce").fillna(0.0)
        if "group" not in work.columns:
            work["group"] = ""
        work = work.sort_values(["code", "time_int"])

        rows = []
        for code, history in work.groupby("code", sort=False):
            latest = history.iloc[-1].copy()
            amounts = history["amount_1min"].clip(lower=0)
            recent_5 = amounts.tail(5)
            recent_3 = amounts.tail(3)
            previous_3 = amounts.iloc[max(0, len(amounts) - 6):max(0, len(amounts) - 3)]
            baseline = amounts.iloc[:-1]
            baseline = baseline[baseline > 0]

            latest["amount_1m"] = float(amounts.iloc[-1]) if len(amounts) else 0.0
            latest["amount_3m"] = float(recent_3.sum())
            latest["amount_5m"] = float(recent_5.sum())
            latest["amount_baseline_1m"] = float(baseline.median()) if len(baseline) else 0.0
            latest["amount_1m_ratio"] = cls._ratio(latest["amount_1m"], latest["amount_baseline_1m"])
            latest["amount_acceleration_3m"] = cls._ratio(recent_3.sum(), previous_3.sum())
            latest["pct"] = cls._pct(latest["last"], latest["pre_close"])
            latest["price_vs_open_pct"] = cls._pct(latest["last"], latest["open"])
            latest["feature_timestamp"] = int(latest["time_int"])
            latest["baseline_source"] = "same_day_prior_minutes"
            rows.append(latest)
        return pd.DataFrame(rows)

    @staticmethod
    def _normalize_benchmark_map(df: Optional[pd.DataFrame]) -> Dict[str, dict]:
        if df is None or df.empty or "group" not in df.columns:
            return {}
        rows = {}
        for _, row in df.iterrows():
            group = IntradayConfirmationBuilder._normalize_group_key(row.get("group", ""))
            if group:
                rows[group] = {
                    "benchmark_etf_code": str(row.get("benchmark_etf_code", "") or ""),
                    "benchmark_index_code": str(row.get("benchmark_index_code", "") or ""),
                    "benchmark_source": "group_benchmark_map",
                    "benchmark_fallback_level": "etf"
                    if str(row.get("benchmark_etf_code", "") or "")
                    else (
                        "sector_index"
                        if str(row.get("benchmark_index_code", "") or "")
                        else ""
                    ),
                    "board_index_code": "",
                    "board_index_name": "",
                    "board_index_fallback_used": False,
                    "benchmark_fallback_reason": "",
                }
        return rows

    @classmethod
    def resolve_benchmark(
        cls,
        group: str,
        stock_code: str,
        benchmark_map: Optional[Dict[str, dict]] = None,
        existing_etf_code: str = "",
        existing_index_code: str = "",
    ) -> dict:
        mapping = benchmark_map or {}
        normalized_group = cls._normalize_group_key(group)
        existing_etf_code = str(existing_etf_code or "")
        existing_index_code = str(existing_index_code or "")

        if existing_etf_code or existing_index_code:
            return {
                "benchmark_etf_code": existing_etf_code,
                "benchmark_index_code": existing_index_code or cls.DEFAULT_INDEX_CODE,
                "benchmark_source": "existing_signal_fields",
                "benchmark_fallback_level": (
                    "etf" if existing_etf_code else "sector_index"
                ),
                "board_index_code": "",
                "board_index_name": "",
                "board_index_fallback_used": False,
                "benchmark_fallback_reason": "",
            }

        mapped = mapping.get(normalized_group, {}) if normalized_group else {}
        mapped_etf_code = str(mapped.get("benchmark_etf_code", "") or "")
        mapped_index_code = str(mapped.get("benchmark_index_code", "") or "")
        if mapped_etf_code or mapped_index_code:
            result = dict(mapped)
            result["benchmark_etf_code"] = mapped_etf_code
            result["benchmark_index_code"] = mapped_index_code or cls.DEFAULT_INDEX_CODE
            result.setdefault("benchmark_source", "group_benchmark_map")
            if not result.get("benchmark_fallback_level"):
                result["benchmark_fallback_level"] = "etf" if mapped_etf_code else "sector_index"
            result.setdefault("board_index_code", "")
            result.setdefault("board_index_name", "")
            result.setdefault("board_index_fallback_used", False)
            result.setdefault("benchmark_fallback_reason", "")
            return result

        board_fallback = cls.resolve_board_index_fallback(stock_code)
        if board_fallback:
            return board_fallback

        return {
            "benchmark_etf_code": "",
            "benchmark_index_code": cls.DEFAULT_INDEX_CODE,
            "benchmark_source": "default_index_fallback",
            "benchmark_fallback_level": "market_index",
            "board_index_code": "",
            "board_index_name": "",
            "board_index_fallback_used": False,
            "benchmark_fallback_reason": "no_group_mapping_available",
        }

    @classmethod
    def resolve_board_index_fallback(cls, code: str) -> dict:
        normalized_code = str(code or "").strip().upper()
        if "." not in normalized_code:
            return {}
        ticker, suffix = normalized_code.split(".", 1)
        suffix = f".{suffix}"
        for prefix, expected_suffix, index_code, index_name, reason in cls.BOARD_INDEX_RULES:
            if suffix == expected_suffix and ticker.startswith(prefix):
                return {
                    "benchmark_etf_code": "",
                    "benchmark_index_code": index_code,
                    "benchmark_source": "board_index_fallback",
                    "benchmark_fallback_level": "board_index",
                    "board_index_code": index_code,
                    "board_index_name": index_name,
                    "board_index_fallback_used": True,
                    "benchmark_fallback_reason": reason,
                }
        return {}

    @staticmethod
    def _normalize_group_key(value) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return unicodedata.normalize("NFKC", text)

    @staticmethod
    def _lookup(df: pd.DataFrame, code: str):
        if df is None or df.empty or not code:
            return None
        rows = df[df["code"] == code]
        return rows.iloc[0] if not rows.empty else None

    @staticmethod
    def _difference(left, right, field):
        if right is None:
            return np.nan
        return round(float(left.get(field, 0.0)) - float(right.get(field, 0.0)), 4)

    @staticmethod
    def _pct(value, base):
        return round((float(value) / float(base) - 1.0) * 100.0, 4) if base else 0.0

    @staticmethod
    def _ratio(value, base):
        return round(float(value) / float(base), 4) if base else np.nan

    @staticmethod
    def _volume_price_state(row):
        move = float(row.get("price_vs_open_pct", 0.0))
        ratio = row.get("amount_1m_ratio")
        amplified = pd.notna(ratio) and float(ratio) >= 1.5
        if move > 0 and amplified:
            return "up_with_amount"
        if move < 0 and amplified:
            return "down_with_amount"
        if move > 0:
            return "up_without_amount"
        if move < 0:
            return "down_without_amount"
        return "flat"

    @staticmethod
    def _execution_bias(row):
        state = row.get("volume_price_state", "")
        rs_index = row.get("rs_vs_index_pct")
        rs_etf = row.get("rs_vs_etf_pct")
        relative_values = [value for value in [rs_index, rs_etf] if pd.notna(value)]
        relative_score = sum(value > 0 for value in relative_values) - sum(
            value < 0 for value in relative_values
        )
        if state == "up_with_amount" and relative_score > 0:
            return "confirmed_strength"
        if state == "down_with_amount" and relative_score < 0:
            return "confirmed_weakness"
        return "observe"
