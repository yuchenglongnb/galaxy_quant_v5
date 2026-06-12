# -*- coding: utf-8 -*-
"""Lightweight THS concept provider without importing qstock."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

from config.settings import ConceptConfig, DBConfig, UniverseConfig
from providers.qstock_provider import (
    _compact_code,
    _normalize_a_code,
    _pick_col,
    _read_csv_auto,
)


class ThsConceptError(RuntimeError):
    """Raised when THS concept data cannot be fetched or parsed."""


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _parse_number(value):
    if pd.isna(value):
        return None
    text = str(value).strip().replace(",", "")
    if not text or text in {"--", "-"}:
        return None
    multiplier = 1.0
    if text.endswith("%"):
        text = text[:-1]
    if text.endswith("亿"):
        multiplier = 100000000.0
        text = text[:-1]
    elif text.endswith("万"):
        multiplier = 10000.0
        text = text[:-1]
    try:
        return float(text) * multiplier
    except ValueError:
        return value


def _split_concepts(value) -> list:
    if pd.isna(value):
        return []
    return [item.strip() for item in str(value).split(";") if item.strip()]


@dataclass
class ThsConceptProvider:
    """Fetch THS concept data directly from 10jqka web endpoints."""

    base_path: str = DBConfig.STORE_PATH
    stock_pool_path: str = UniverseConfig.STOCK_POOL_PATH
    timeout: int = 15

    def __post_init__(self):
        self.session = requests.Session()
        self.session.trust_env = False

    def _date_dir(self, date_int: Optional[int] = None) -> str:
        if date_int is None:
            date_int = int(pd.Timestamp.now().strftime("%Y%m%d"))
        path = os.path.join(self.base_path, str(date_int), "ths")
        os.makedirs(path, exist_ok=True)
        return path

    def _save(self, df: pd.DataFrame, filename: str, date_int: Optional[int] = None) -> str:
        path = os.path.join(self._date_dir(date_int), filename)
        df.to_csv(path, index=False, encoding="utf-8-sig")
        return path

    def _ths_js_path(self) -> Optional[Path]:
        candidates = [
            Path(sys.prefix) / "Lib" / "site-packages" / "qstock" / "data" / "ths.js",
            Path(sys.prefix) / "lib" / "site-packages" / "qstock" / "data" / "ths.js",
        ]
        for path in candidates:
            if path.exists():
                return path
        return None

    def _hexin_v(self) -> str:
        path = self._ths_js_path()
        if not path:
            return ""
        try:
            from py_mini_racer import py_mini_racer

            js = path.read_text(encoding="utf-8", errors="ignore")
            ctx = py_mini_racer.MiniRacer()
            ctx.eval(js)
            return str(ctx.call("v"))
        except Exception:
            return ""

    def _headers(self, host: str = "q.10jqka.com.cn", referer: str = "http://q.10jqka.com.cn"):
        v_code = self._hexin_v()
        headers = {
            "Accept": "text/html, */*; q=0.01",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Host": host,
            "Pragma": "no-cache",
            "Referer": referer,
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            ),
            "X-Requested-With": "XMLHttpRequest",
        }
        if v_code:
            headers["hexin-v"] = v_code
            headers["Cookie"] = f"v={v_code}"
        return headers

    def _get(self, url: str, host: str = "q.10jqka.com.cn", referer: str = "http://q.10jqka.com.cn"):
        try:
            response = self.session.get(
                url,
                headers=self._headers(host=host, referer=referer),
                timeout=self.timeout,
            )
            response.raise_for_status()
            if "10jqka.com.cn" in url:
                response.encoding = "gbk"
            else:
                response.encoding = response.apparent_encoding or response.encoding
            return response
        except Exception as exc:
            raise ThsConceptError(f"请求同花顺失败: {url} | {exc}") from exc

    def _html_table(self, html: str) -> pd.DataFrame:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if table is None:
            return pd.DataFrame()
        headers = [x.get_text(strip=True) for x in table.find_all("th")]
        rows = []
        for tr in table.find_all("tr"):
            cells = [x.get_text(strip=True) for x in tr.find_all("td")]
            if cells:
                rows.append(cells)
        if not rows:
            return pd.DataFrame(columns=headers)
        if headers and len(headers) == len(rows[0]):
            return pd.DataFrame(rows, columns=headers)
        return pd.DataFrame(rows)

    def load_stock_pool(self) -> pd.DataFrame:
        if not os.path.exists(self.stock_pool_path):
            return pd.DataFrame(columns=["code", "name", "group", "note", "compact_code"])
        df = _read_csv_auto(self.stock_pool_path)
        if "code" not in df.columns:
            return pd.DataFrame(columns=["code", "name", "group", "note", "compact_code"])
        df["code"] = df["code"].map(_normalize_a_code)
        df["compact_code"] = df["code"].map(_compact_code)
        if "name" not in df.columns:
            df["name"] = ""
        if "group" not in df.columns:
            df["group"] = ""
        return df

    def fetch_concept_list(self, date_int: Optional[int] = None) -> pd.DataFrame:
        first_url = "http://q.10jqka.com.cn/gn/index/field/addtime/order/desc/page/1/ajax/1/"
        first = self._get(first_url)
        soup = BeautifulSoup(first.text, "html.parser")
        page_info = soup.find("span", attrs={"class": "page_info"})
        total_pages = 1
        if page_info and "/" in page_info.get_text(strip=True):
            total_pages = int(page_info.get_text(strip=True).split("/")[-1])

        frames = []
        for page in range(1, total_pages + 1):
            url = f"http://q.10jqka.com.cn/gn/index/field/addtime/order/desc/page/{page}/ajax/1/"
            response = first if page == 1 else self._get(url)
            df = self._html_table(response.text)
            if df.empty:
                continue
            df = _clean_columns(df)
            soup = BeautifulSoup(response.text, "html.parser")
            links = []
            table = soup.find("table")
            if table:
                for tr in table.find_all("tr"):
                    cells = tr.find_all("td")
                    a_tag = cells[1].find("a") if len(cells) > 1 else None
                    href = a_tag.get("href", "") if a_tag else ""
                    if href:
                        links.append(href)
            if links and len(links) == len(df):
                df["url"] = links
                df["concept_code"] = df["url"].str.extract(r"/code/(\d+)/")
            frames.append(df)
        result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        rename = {
            "日期": "date",
            "概念名称": "concept",
            "成分股数量": "member_count",
        }
        result = result.rename(columns={k: v for k, v in rename.items() if k in result.columns})
        if "concept" in result.columns:
            result = result.drop_duplicates(subset=["concept"], keep="first")
        result["source"] = "ths.direct.concept_list"
        result["fetched_at"] = pd.Timestamp.now().isoformat(timespec="seconds")
        self._save(result, "concept_list.csv", date_int)
        return result

    def concept_code_map(self, date_int: Optional[int] = None) -> dict:
        path = os.path.join(self._date_dir(date_int), "concept_list.csv")
        df = _read_csv_auto(path) if os.path.exists(path) else self.fetch_concept_list(date_int)
        if "concept" not in df.columns or "concept_code" not in df.columns:
            return {}
        return dict(zip(df["concept"], df["concept_code"].astype(str)))

    def fetch_concept_members(self, concept, date_int: Optional[int] = None) -> pd.DataFrame:
        code_map = self.concept_code_map(date_int)
        symbol = str(concept).strip()
        if not symbol.isdigit():
            symbol = str(code_map.get(symbol, ""))
        if not symbol:
            raise ThsConceptError(f"未知同花顺概念: {concept}")
        url = f"http://q.10jqka.com.cn/gn/detail/code/{symbol}/"
        response = self._get(url)
        df = self._html_table(response.text)
        df = _clean_columns(df)
        df["concept"] = concept
        df["concept_code"] = symbol
        return df

    def fetch_concept_member_map(
        self,
        limit: Optional[int] = None,
        sleep_seconds: float = 0.2,
        date_int: Optional[int] = None,
    ) -> pd.DataFrame:
        concepts = self.fetch_concept_list(date_int)
        if "concept" not in concepts.columns:
            raise ThsConceptError("概念列表缺少 concept 字段")
        names = concepts["concept"].dropna().astype(str).tolist()
        if limit:
            names = names[:limit]

        pool = self.load_stock_pool()
        pool_codes = set(pool["compact_code"].dropna().astype(str))
        rows = []
        errors = []
        for idx, concept in enumerate(names, start=1):
            try:
                members = self.fetch_concept_members(concept, date_int)
            except Exception as exc:
                errors.append({"concept": concept, "error": str(exc)})
                continue
            code_col = _pick_col(members, ["代码", "code", "股票代码", "证券代码"])
            name_col = _pick_col(members, ["名称", "name", "股票简称", "证券简称", "股票名称"])
            if code_col is None:
                continue
            for _, row in members.iterrows():
                member_code = _compact_code(row.get(code_col, ""))
                if member_code in pool_codes:
                    rows.append(
                        {
                            "code_compact": member_code,
                            "concept": concept,
                            "concept_member_name": str(row.get(name_col, "")).strip() if name_col else "",
                        }
                    )
            if sleep_seconds and idx < len(names):
                time.sleep(sleep_seconds)

        mapped = pd.DataFrame(rows)
        if not mapped.empty:
            mapped = mapped.merge(
                pool[["code", "compact_code", "name", "group"]],
                left_on="code_compact",
                right_on="compact_code",
                how="left",
            )
            mapped = mapped[["code", "name", "group", "concept", "concept_member_name"]]
            mapped = mapped.sort_values(["code", "concept"]).reset_index(drop=True)
        self._save(mapped, "stock_concept_map.csv", date_int)
        self._save(pd.DataFrame(errors), "stock_concept_map_errors.csv", date_int)
        self._save(self.summarize_concept_exposure(mapped), "stock_concept_exposure.csv", date_int)
        return mapped

    def summarize_concept_exposure(self, mapped: pd.DataFrame) -> pd.DataFrame:
        if mapped.empty or "concept" not in mapped.columns:
            return pd.DataFrame(columns=["concept", "stock_count", "stocks"])
        return (
            mapped.groupby("concept", as_index=False)
            .agg(
                stock_count=("code", "nunique"),
                stocks=("name", lambda x: ",".join(sorted(set(map(str, x))))),
            )
            .sort_values(["stock_count", "concept"], ascending=[False, True])
            .reset_index(drop=True)
        )

    def enrich_stock_pool_with_concepts(
        self,
        date_int: Optional[int] = None,
        output_path: Optional[str] = None,
    ) -> pd.DataFrame:
        """Append THS concept tags to the local stock pool CSV."""
        pool = self.load_stock_pool()
        if pool.empty:
            return pool

        map_path = os.path.join(self._date_dir(date_int), "stock_concept_map.csv")
        if os.path.exists(map_path):
            mapped = _read_csv_auto(map_path)
        else:
            mapped = self.fetch_concept_member_map(date_int=date_int)

        if mapped.empty or "code" not in mapped.columns or "concept" not in mapped.columns:
            pool["ths_concepts"] = ""
            pool["ths_concept_count"] = 0
            pool["ths_signal_concepts"] = ""
            pool["ths_signal_concept_count"] = 0
        else:
            concept_map = (
                mapped.dropna(subset=["code", "concept"])
                .groupby("code")["concept"]
                .apply(lambda s: ";".join(sorted(set(map(str, s)))))
                .to_dict()
            )
            pool["ths_concepts"] = pool["code"].map(concept_map).fillna("")
            pool["ths_concept_count"] = pool["ths_concepts"].map(
                lambda value: 0 if not value else len(str(value).split(";"))
            )
            pool["ths_signal_concepts"] = pool["ths_concepts"].map(
                lambda value: ";".join(self.filter_signal_concepts(_split_concepts(value)))
            )
            pool["ths_signal_concept_count"] = pool["ths_signal_concepts"].map(
                lambda value: 0 if not value else len(str(value).split(";"))
            )

        output_path = output_path or self.stock_pool_path
        cols = [
            "code",
            "name",
            "group",
            "note",
            "ths_concepts",
            "ths_concept_count",
            "ths_signal_concepts",
            "ths_signal_concept_count",
        ]
        for col in cols:
            if col not in pool.columns:
                pool[col] = ""
        pool[cols].to_csv(output_path, index=False, encoding="utf-8-sig")
        return pool[cols]

    def filter_signal_concepts(self, concepts: Iterable[str]) -> list:
        """Keep THS concepts that are useful as market theme labels."""
        useful = []
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

    def build_signal_concept_table(self, date_int: Optional[int] = None) -> pd.DataFrame:
        """Join stock-pool useful concepts with THS concept money data."""
        pool = self.load_stock_pool()
        if "ths_signal_concepts" not in pool.columns:
            pool = self.enrich_stock_pool_with_concepts(date_int=date_int)

        rows = []
        for _, row in pool.iterrows():
            for concept in _split_concepts(row.get("ths_signal_concepts", "")):
                rows.append(
                    {
                        "code": row.get("code", ""),
                        "name": row.get("name", ""),
                        "group": row.get("group", ""),
                        "concept": concept,
                    }
                )
        signal = pd.DataFrame(rows)
        if signal.empty:
            self._save(signal, "stock_signal_concepts.csv", date_int)
            return signal

        money_path = os.path.join(self._date_dir(date_int), "concept_money_5d.csv")
        if os.path.exists(money_path):
            money = _read_csv_auto(money_path)
            concept_col = "concept" if "concept" in money.columns else "行业" if "行业" in money.columns else None
            if concept_col:
                money = money.rename(columns={concept_col: "concept"})
                keep_cols = [
                    col for col in ["concept", "序号", "公司家数", "行业指数", "阶段涨跌幅", "净额(亿)"]
                    if col in money.columns
                ]
                signal = signal.merge(money[keep_cols], on="concept", how="left")

        self._save(signal, "stock_signal_concepts.csv", date_int)
        return signal

    def fetch_concept_money(self, n: Optional[int] = 5, date_int: Optional[int] = None) -> pd.DataFrame:
        if n is None:
            url = "http://data.10jqka.com.cn/funds/gnzjl/field/tradezdf/order/desc/ajax/1/free/1/"
        else:
            url = f"http://data.10jqka.com.cn/funds/gnzjl/board/{n}/field/tradezdf/order/desc/page/1/ajax/1/free/1/"
        response = self._get(url, host="data.10jqka.com.cn", referer="http://data.10jqka.com.cn/funds/gnzjl/")
        soup = BeautifulSoup(response.text, "html.parser")
        page_info = soup.find("span", attrs={"class": "page_info"})
        total_pages = 1
        if page_info and "/" in page_info.get_text(strip=True):
            total_pages = int(page_info.get_text(strip=True).split("/")[-1])

        frames = []
        for page in range(1, total_pages + 1):
            if n is None:
                page_url = f"http://data.10jqka.com.cn/funds/gnzjl/field/tradezdf/order/desc/page/{page}/ajax/1/free/1/"
            else:
                page_url = f"http://data.10jqka.com.cn/funds/gnzjl/board/{n}/field/tradezdf/order/desc/page/{page}/ajax/1/free/1/"
            page_response = response if page == 1 else self._get(
                page_url, host="data.10jqka.com.cn", referer="http://data.10jqka.com.cn/funds/gnzjl/"
            )
            frames.append(_clean_columns(self._html_table(page_response.text)))
        result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if "行业" in result.columns and "concept" not in result.columns:
            result = result.rename(columns={"行业": "concept"})
        result["money_window"] = n if n is not None else "realtime"
        result["source"] = "ths.direct.concept_money"
        result["fetched_at"] = pd.Timestamp.now().isoformat(timespec="seconds")
        for col in result.columns:
            if col not in {"概念名称", "领涨股", "source", "fetched_at", "money_window"}:
                result[col] = result[col].map(_parse_number)
        suffix = f"{n}d" if n is not None else "realtime"
        self._save(result, f"concept_money_{suffix}.csv", date_int)
        return result

    def fetch_concept_index_data(
        self,
        concept,
        start_year: int = 2024,
        date_int: Optional[int] = None,
    ) -> pd.DataFrame:
        code_map = self.concept_code_map(date_int)
        concept_name = str(concept).strip()
        symbol = concept_name if concept_name.isdigit() else str(code_map.get(concept_name, ""))
        if not symbol:
            raise ThsConceptError(f"未知同花顺概念: {concept}")
        detail = self._get(f"http://q.10jqka.com.cn/gn/detail/code/{symbol}/")
        soup = BeautifulSoup(detail.text, "html.parser")
        board = soup.find("div", attrs={"class": "board-hq"})
        if board is None or not board.find("span"):
            raise ThsConceptError(f"无法解析概念指数代码: {concept}")
        index_code = board.find("span").get_text(strip=True)

        frames = []
        current_year = pd.Timestamp.now().year
        for year in range(int(start_year), current_year + 1):
            url = f"http://d.10jqka.com.cn/v4/line/bk_{index_code}/01/{year}.js"
            response = self._get(url, host="d.10jqka.com.cn", referer="http://q.10jqka.com.cn")
            raw = response.text
            match = re.search(r"\{.*\}", raw)
            if not match:
                continue
            data = json.loads(match.group(0))
            rows = [x.split(",") for x in data.get("data", "").split(";") if x]
            if not rows:
                continue
            frame = pd.DataFrame(rows)
            frame = frame.iloc[:, :7]
            frame.columns = ["date", "open", "high", "low", "close", "volume", "amount"]
            frames.append(frame)
        result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if not result.empty:
            result["concept"] = concept_name
            result["concept_code"] = symbol
            result["index_code"] = index_code
            for col in ["open", "high", "low", "close", "volume", "amount"]:
                result[col] = pd.to_numeric(result[col], errors="coerce")
        safe_name = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", concept_name)
        self._save(result, f"concept_index_{safe_name}.csv", date_int)
        return result

    def fetch_exposed_concept_index_data(
        self,
        top_n: int = 20,
        start_year: int = 2024,
        date_int: Optional[int] = None,
    ) -> pd.DataFrame:
        exposure_path = os.path.join(self._date_dir(date_int), "stock_concept_exposure.csv")
        if not os.path.exists(exposure_path):
            self.fetch_concept_member_map(limit=None, date_int=date_int)
        exposure = _read_csv_auto(exposure_path)
        if exposure.empty or "concept" not in exposure.columns:
            return pd.DataFrame()
        concepts = exposure.head(top_n)["concept"].tolist()
        frames = []
        for concept in concepts:
            try:
                frames.append(self.fetch_concept_index_data(concept, start_year=start_year, date_int=date_int))
            except Exception:
                continue
            time.sleep(0.1)
        result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        self._save(result, "concept_index_exposed.csv", date_int)
        return result
