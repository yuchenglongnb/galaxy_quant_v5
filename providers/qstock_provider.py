# -*- coding: utf-8 -*-
"""qstock optional data adapter.

The adapter is intentionally isolated from DataManager. It writes qstock data
to a side cache so AmazingData remains the canonical source for core reports.
"""

from __future__ import annotations

import os
import socket
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional

import pandas as pd

from config.settings import DBConfig, UniverseConfig


class QStockUnavailable(RuntimeError):
    """Raised when qstock is not installed in the active environment."""


class QStockProviderError(RuntimeError):
    """Raised when qstock is installed but cannot fetch or initialize."""


def _require_qstock():
    # qstock imports may touch Eastmoney immediately. In this environment the
    # Eastmoney IPv6 endpoint closes the connection, while IPv4 works. The
    # local Windows proxy can also break these public data requests, so qstock
    # side tasks default to direct IPv4 access.
    os.environ.setdefault("NO_PROXY", "*")
    os.environ.setdefault("no_proxy", "*")
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(key, None)

    original_getaddrinfo = socket.getaddrinfo

    def getaddrinfo_ipv4(*args, **kwargs):
        return [
            item for item in original_getaddrinfo(*args, **kwargs)
            if item[0] == socket.AF_INET
        ]

    socket.getaddrinfo = getaddrinfo_ipv4
    try:
        import qstock as qs  # type: ignore
    except ImportError as exc:
        raise QStockUnavailable(
            "qstock 未安装。可在 amazing 环境中安装: pip install qstock"
        ) from exc
    except Exception as exc:
        raise QStockProviderError(
            f"qstock 已安装，但初始化/联网请求失败: {exc}"
        ) from exc
    finally:
        socket.getaddrinfo = original_getaddrinfo
    return qs


def _read_csv_auto(path: str) -> pd.DataFrame:
    try:
        return pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(path, dtype=str, encoding="gb18030")


def _normalize_a_code(value: object) -> str:
    raw = str(value or "").strip().upper()
    if not raw or raw == "NAN":
        return ""
    if raw.startswith(("SH", "SZ", "BJ")) and len(raw) >= 8:
        code = raw[2:8]
        suffix = raw[:2]
        return f"{code}.{suffix}"
    if "." in raw:
        code, suffix = raw.split(".", 1)
        return f"{code.zfill(6)}.{suffix.upper()}"
    if raw.isdigit() and len(raw) == 6:
        if raw.startswith(("600", "601", "603", "605", "688", "689")):
            return f"{raw}.SH"
        if raw.startswith(("000", "001", "002", "003", "300", "301")):
            return f"{raw}.SZ"
        if raw.startswith(("4", "8")):
            return f"{raw}.BJ"
    return raw


def _compact_code(value: object) -> str:
    code = _normalize_a_code(value)
    return code.split(".", 1)[0] if "." in code else code


def _pick_col(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    return None


@dataclass
class QStockProvider:
    """Fetch qstock data into a per-day side cache."""

    base_path: str = DBConfig.STORE_PATH
    stock_pool_path: str = UniverseConfig.STOCK_POOL_PATH

    def _date_dir(self, date_int: Optional[int] = None) -> str:
        if date_int is None:
            date_int = int(pd.Timestamp.now().strftime("%Y%m%d"))
        path = os.path.join(self.base_path, str(date_int), "qstock")
        os.makedirs(path, exist_ok=True)
        return path

    def _save(self, df: pd.DataFrame, filename: str, date_int: Optional[int] = None) -> str:
        path = os.path.join(self._date_dir(date_int), filename)
        df.to_csv(path, index=False, encoding="utf-8-sig")
        return path

    def load_stock_pool(self) -> pd.DataFrame:
        if not os.path.exists(self.stock_pool_path):
            return pd.DataFrame(columns=["code", "name", "group", "note"])
        df = _read_csv_auto(self.stock_pool_path)
        if "code" not in df.columns:
            return pd.DataFrame(columns=["code", "name", "group", "note"])
        df["code"] = df["code"].map(_normalize_a_code)
        df["compact_code"] = df["code"].map(_compact_code)
        if "name" not in df.columns:
            df["name"] = ""
        if "group" not in df.columns:
            df["group"] = ""
        return df

    def fetch_concept_realtime(self, date_int: Optional[int] = None) -> pd.DataFrame:
        qs = _require_qstock()
        df = qs.realtime_data("概念板块")
        if df is None:
            df = pd.DataFrame()
        df = pd.DataFrame(df)
        df["source"] = "qstock.realtime_data(概念板块)"
        df["fetched_at"] = pd.Timestamp.now().isoformat(timespec="seconds")
        self._save(df, "concept_realtime.csv", date_int)
        return df

    def fetch_concept_money(self, n: int = 5, date_int: Optional[int] = None) -> pd.DataFrame:
        qs = _require_qstock()
        df = qs.ths_money("概念", n=n)
        if df is None:
            df = pd.DataFrame()
        df = pd.DataFrame(df)
        df["source"] = f"qstock.ths_money(概念,n={n})"
        df["fetched_at"] = pd.Timestamp.now().isoformat(timespec="seconds")
        self._save(df, f"concept_money_{n}d.csv", date_int)
        return df

    def fetch_realtime_snapshot(self, date_int: Optional[int] = None) -> pd.DataFrame:
        qs = _require_qstock()
        pool = self.load_stock_pool()
        codes = pool["compact_code"].dropna().unique().tolist()
        if not codes:
            df = pd.DataFrame()
        else:
            df = qs.realtime_data(code=codes)
            df = pd.DataFrame(df if df is not None else [])
        df["source"] = "qstock.realtime_data(stock_pool)"
        df["fetched_at"] = pd.Timestamp.now().isoformat(timespec="seconds")
        self._save(df, "stock_pool_realtime.csv", date_int)
        return df

    def fetch_realtime_change(self, flag=None, date_int: Optional[int] = None) -> pd.DataFrame:
        qs = _require_qstock()
        df = qs.realtime_change(flag)
        if df is None:
            df = pd.DataFrame()
        df = pd.DataFrame(df)
        df["source"] = f"qstock.realtime_change({flag})"
        df["fetched_at"] = pd.Timestamp.now().isoformat(timespec="seconds")
        suffix = "all" if flag is None else str(flag)
        self._save(df, f"realtime_change_{suffix}.csv", date_int)
        return df

    def fetch_concept_member_map(
        self,
        limit: Optional[int] = None,
        sleep_seconds: float = 0.2,
        date_int: Optional[int] = None,
    ) -> pd.DataFrame:
        """Map stock-pool names/codes to THS concepts.

        qstock exposes concept -> members. The reverse stock -> concepts map is
        built by scanning concept members and joining with the local stock pool.
        """
        qs = _require_qstock()
        pool = self.load_stock_pool()
        if pool.empty:
            mapped = pd.DataFrame(columns=["code", "name", "group", "concept", "concept_member_name"])
            self._save(mapped, "stock_concept_map.csv", date_int)
            return mapped

        pool_codes = set(pool["compact_code"].dropna())
        concept_names: List[str] = list(qs.ths_index_name("概念") or [])
        if limit:
            concept_names = concept_names[:limit]

        rows = []
        for idx, concept in enumerate(concept_names, start=1):
            try:
                members = qs.ths_index_member(concept)
                members = pd.DataFrame(members if members is not None else [])
            except Exception as exc:
                rows.append({"concept": concept, "error": str(exc)})
                continue

            if members.empty:
                continue
            code_col = _pick_col(members, ["代码", "code", "股票代码", "证券代码"])
            name_col = _pick_col(members, ["名称", "name", "股票简称", "证券简称"])
            if code_col is None and name_col is None:
                continue

            for _, member in members.iterrows():
                member_code = _compact_code(member.get(code_col, "")) if code_col else ""
                member_name = str(member.get(name_col, "")).strip() if name_col else ""
                if member_code in pool_codes:
                    rows.append(
                        {
                            "code_compact": member_code,
                            "concept": concept,
                            "concept_member_name": member_name,
                        }
                    )
            if sleep_seconds and idx < len(concept_names):
                time.sleep(sleep_seconds)

        mapped = pd.DataFrame(rows)
        if not mapped.empty and "code_compact" in mapped.columns:
            mapped = mapped.merge(
                pool[["code", "compact_code", "name", "group"]],
                left_on="code_compact",
                right_on="compact_code",
                how="left",
            )
            mapped = mapped[["code", "name", "group", "concept", "concept_member_name"]]
            mapped = mapped.sort_values(["code", "concept"]).reset_index(drop=True)
        self._save(mapped, "stock_concept_map.csv", date_int)

        summary = self.summarize_concept_exposure(mapped, date_int=date_int)
        self._save(summary, "stock_concept_exposure.csv", date_int)
        return mapped

    def summarize_concept_exposure(
        self,
        mapped: Optional[pd.DataFrame] = None,
        date_int: Optional[int] = None,
    ) -> pd.DataFrame:
        if mapped is None:
            path = os.path.join(self._date_dir(date_int), "stock_concept_map.csv")
            mapped = _read_csv_auto(path) if os.path.exists(path) else pd.DataFrame()
        if mapped.empty or "concept" not in mapped.columns:
            return pd.DataFrame(columns=["concept", "stock_count", "stocks"])
        summary = (
            mapped.dropna(subset=["concept"])
            .groupby("concept", as_index=False)
            .agg(
                stock_count=("code", "nunique"),
                stocks=("name", lambda x: ",".join(sorted(set(map(str, x))))),
            )
            .sort_values(["stock_count", "concept"], ascending=[False, True])
            .reset_index(drop=True)
        )
        return summary
