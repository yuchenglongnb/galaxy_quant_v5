# -*- coding: utf-8 -*-
"""
盘中监测器 - 实时采集指数和ETF分钟数据

功能：
1. 9:25-15:00 每分钟采集四大指数和主题ETF的实时快照
2. 计算分钟级增量数据（成交量、成交额）
3. 持久化存储到CSV，支持断点续传

数据结构:
    intraday/
    ├── indices_1min.csv    # 指数分钟数据
    └── etf_1min.csv        # ETF分钟数据

使用:
    monitor = IntradayMonitor(data_manager)
    snapshot = monitor.fetch_current_snapshot()
    monitor.save_minute_data(snapshot)
"""

import json
import os
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum

from config.settings import DBConfig, MarketConfig, UniverseConfig
from core.intraday_confirmation import IntradayConfirmationBuilder
from core.amazing_kline_query import query_min1_kline_once
from core.snapshot_utils import (
    iter_kline_frames,
    iter_snapshot_frames,
    latest_snapshot_rows,
    snapshot_rows_near_time,
    trade_time_to_hhmmss,
)


class MarketPhase(Enum):
    """市场交易阶段"""
    PRE_OPEN = "pre_open"           # 开盘前 (< 9:15)
    CALL_AUCTION = "call_auction"   # 集合竞价 (9:15-9:25)
    AUCTION_END = "auction_end"     # 竞价结束 (9:25-9:30)
    CONTINUOUS_AM = "continuous_am" # 上午连续竞价 (9:30-11:30)
    NOON_BREAK = "noon_break"       # 午休 (11:30-13:00)
    CONTINUOUS_PM = "continuous_pm" # 下午连续竞价 (13:00-14:57)
    CLOSE_AUCTION = "close_auction" # 收盘集合竞价 (14:57-15:00)
    CLOSED = "closed"               # 已收盘 (>= 15:00)


class MarketState:
    """
    市场状态机 - 判断当前交易阶段
    
    用于控制不同阶段的采集策略
    """
    
    @staticmethod
    def get_current_phase(now: datetime = None) -> MarketPhase:
        """
        获取当前市场阶段
        
        参数:
            now: 指定时间，默认为当前时间
            
        返回:
            MarketPhase 枚举值
        """
        if now is None:
            now = datetime.now()
        
        hour, minute = now.hour, now.minute
        time_int = hour * 100 + minute  # HHMM格式
        
        if time_int < 915:
            return MarketPhase.PRE_OPEN
        elif 915 <= time_int < 925:
            return MarketPhase.CALL_AUCTION
        elif 925 <= time_int < 930:
            return MarketPhase.AUCTION_END
        elif 930 <= time_int < 1130:
            return MarketPhase.CONTINUOUS_AM
        elif 1130 <= time_int < 1300:
            return MarketPhase.NOON_BREAK
        elif 1300 <= time_int < 1457:
            return MarketPhase.CONTINUOUS_PM
        elif 1457 <= time_int < 1500:
            return MarketPhase.CLOSE_AUCTION
        else:
            return MarketPhase.CLOSED
    
    @staticmethod
    def is_trading_time(now: datetime = None) -> bool:
        """判断是否在交易时间（含集合竞价）"""
        phase = MarketState.get_current_phase(now)
        return phase in [
            MarketPhase.AUCTION_END,      # 9:25-9:30 竞价结束，可采集
            MarketPhase.CONTINUOUS_AM,    # 9:30-11:30
            MarketPhase.CONTINUOUS_PM,    # 13:00-14:57
            MarketPhase.CLOSE_AUCTION,    # 14:57-15:00
        ]
    
    @staticmethod
    def should_collect(now: datetime = None) -> bool:
        """判断是否应该采集数据（含午休）"""
        phase = MarketState.get_current_phase(now)
        # 午休期间也可以采集，但频率可以降低
        return phase not in [MarketPhase.PRE_OPEN, MarketPhase.CALL_AUCTION, MarketPhase.CLOSED]
    
    @staticmethod
    def get_phase_name(phase: MarketPhase) -> str:
        """获取阶段中文名称"""
        names = {
            MarketPhase.PRE_OPEN: "盘前",
            MarketPhase.CALL_AUCTION: "集合竞价",
            MarketPhase.AUCTION_END: "竞价结束",
            MarketPhase.CONTINUOUS_AM: "上午连续竞价",
            MarketPhase.NOON_BREAK: "午间休市",
            MarketPhase.CONTINUOUS_PM: "下午连续竞价",
            MarketPhase.CLOSE_AUCTION: "收盘集合竞价",
            MarketPhase.CLOSED: "已收盘",
        }
        return names.get(phase, "未知")


class IntradayMonitor:
    """
    盘中监测器
    
    负责采集、计算和存储指数/ETF的分钟级数据
    """
    
    def __init__(self, base_path: str = DBConfig.STORE_PATH):
        """
        初始化监测器
        
        参数:
            base_path: 数据存储根目录
        """
        self.base_path = base_path
        
        # 监测标的
        self.target_indices = list(MarketConfig.MAIN_INDICES.keys())
        self.target_etfs = list(MarketConfig.THEME_ETFS.keys())
        self.stock_pool = self._load_stock_pool()
        self.target_stocks = self.stock_pool["code"].tolist()
        
        # 名称映射
        self.name_map = {
            **MarketConfig.MAIN_INDICES,
            **MarketConfig.THEME_ETFS,
            **dict(zip(self.stock_pool["code"], self.stock_pool["name"])),
        }
        self.group_map = dict(zip(self.stock_pool["code"], self.stock_pool["group"]))
        self._stock_pre_close_map: Optional[Dict[str, float]] = None
        self._index_pre_close_map: Optional[Dict[str, float]] = None
        
        # 上一分钟数据缓存（用于计算增量）
        self._prev_data: Dict[str, dict] = {}
        self._counter_date = int(datetime.now().strftime("%Y%m%d"))
        self._empty_snapshot_rounds = 0
        
        # 延迟导入AmazingData
        import AmazingData as ad
        
        # API实例
        self.calendar = self._generate_calendar()
        self.ad_base = ad.BaseData()
        self.ad_market = ad.MarketData(self.calendar)
        restored_count = self._restore_previous_counters(self._counter_date)
        
        print(f"[IntradayMonitor] 初始化完成")
        print(f"  监测指数: {len(self.target_indices)} 只")
        print(f"  监测ETF: {len(self.target_etfs)} 只")
        print(f"  监测股票池: {len(self.target_stocks)} 只")
        if restored_count:
            print(f"  断点恢复: {restored_count} 只标的累计值")
    
    @staticmethod
    def _load_stock_pool() -> pd.DataFrame:
        """Load the configured stock pool for lightweight minute monitoring."""
        columns = ["code", "name", "group"]
        path = UniverseConfig.STOCK_POOL_PATH
        if not path or not os.path.exists(path):
            return pd.DataFrame(columns=columns)
        try:
            try:
                df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
            except UnicodeDecodeError:
                df = pd.read_csv(path, dtype=str, encoding="gb18030")
            if "code" not in df.columns:
                return pd.DataFrame(columns=columns)
            for column in columns:
                if column not in df.columns:
                    df[column] = ""
            df = df[columns].fillna("")
            return df[df["code"] != ""].drop_duplicates("code")
        except Exception as exc:
            print(f"  warning: stock pool load failed: {path} | {exc}")
            return pd.DataFrame(columns=columns)

    def _generate_calendar(self) -> List[int]:
        """生成工作日日历（返回整数格式以匹配API要求）"""
        dates = pd.bdate_range(
            end=pd.Timestamp.now(), 
            periods=400, 
            freq='B'
        )
        return [int(d.strftime('%Y%m%d')) for d in dates]
    
    def _get_intraday_dir(self, date_int: int = None) -> str:
        """获取盘中数据存储目录"""
        if date_int is None:
            date_int = int(datetime.now().strftime('%Y%m%d'))
        
        intraday_dir = os.path.join(self.base_path, str(date_int), "intraday")
        os.makedirs(intraday_dir, exist_ok=True)
        return intraday_dir

    def _default_backfill_progress_path(self) -> str:
        project_root = os.path.dirname(os.path.abspath(self.base_path))
        eval_dir = os.path.join(project_root, "reports", "analysis", "evaluations")
        os.makedirs(eval_dir, exist_ok=True)
        return os.path.join(eval_dir, "intraday_backfill_progress.jsonl")

    def _append_backfill_progress(self, progress_path: Optional[str], payload: Dict):
        target = progress_path or self._default_backfill_progress_path()
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    @staticmethod
    def _encode_snapshot_hhmmss_millis(hhmmss: int) -> int:
        return int(hhmmss or 0) * 1000

    @staticmethod
    def _encode_kline_hhmm(hhmm: int) -> int:
        return int(hhmm or 0)

    def _log_backfill_event(
        self,
        date_int: int,
        stage: str,
        status: str,
        elapsed_sec: float = 0.0,
        code_count: int = 0,
        row_count: int = 0,
        output_path: str = "",
        error: str = "",
        progress_path: Optional[str] = None,
        warning: str = "",
        extra: Optional[Dict] = None,
    ):
        payload = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "date": str(int(date_int)),
            "stage": stage,
            "status": status,
            "elapsed_sec": round(float(elapsed_sec or 0.0), 4),
            "code_count": int(code_count or 0),
            "row_count": int(row_count or 0),
            "output_path": output_path or "",
            "error": error or "",
            "warning": warning or "",
        }
        if extra:
            payload.update(extra)
        self._append_backfill_progress(progress_path, payload)

        warning_text = f" warning={warning}" if warning else ""
        error_text = f" error={error}" if error else ""
        output_text = f" output={output_path}" if output_path else ""
        print(
            f"[{int(date_int)}][{stage}] {status}"
            f" elapsed={payload['elapsed_sec']:.2f}s"
            f" codes={payload['code_count']}"
            f" rows={payload['row_count']}"
            f"{warning_text}{output_text}{error_text}"
        )

    def _run_backfill_stage(
        self,
        date_int: int,
        stage: str,
        code_count: int,
        runner,
        progress_path: Optional[str],
        warn_after_sec: Optional[float] = None,
        output_path: str = "",
        extra: Optional[Dict] = None,
    ):
        self._log_backfill_event(
            date_int,
            stage=stage,
            status="start",
            code_count=code_count,
            output_path=output_path,
            progress_path=progress_path,
            extra=extra,
        )
        started = time.time()
        try:
            result = runner()
            elapsed = time.time() - started
            if isinstance(result, pd.DataFrame):
                row_count = len(result)
            elif isinstance(result, (list, tuple)):
                row_count = len(result)
            elif isinstance(result, dict) and "row_count" in result:
                row_count = int(result.get("row_count", 0) or 0)
            else:
                row_count = 0
            warning = ""
            if warn_after_sec and elapsed >= float(warn_after_sec):
                warning = "stage_elapsed_exceeded_warn_after_sec"
            self._log_backfill_event(
                date_int,
                stage=stage,
                status="done",
                elapsed_sec=elapsed,
                code_count=code_count,
                row_count=row_count,
                output_path=output_path,
                progress_path=progress_path,
                warning=warning,
                extra=extra,
            )
            return result
        except Exception as exc:
            elapsed = time.time() - started
            self._log_backfill_event(
                date_int,
                stage=stage,
                status="failed",
                elapsed_sec=elapsed,
                code_count=code_count,
                output_path=output_path,
                error=str(exc),
                progress_path=progress_path,
                extra=extra,
            )
            raise
    
    def fetch_index_snapshot(self) -> pd.DataFrame:
        """
        获取指数实时快照
        
        返回:
            DataFrame: 包含指数实时数据
        """
        today = int(datetime.now().strftime('%Y%m%d'))
        now = datetime.now()
        begin_time, end_time = self._snapshot_window(now)
        rows = self._fetch_realtime_rows(
            self.target_indices,
            today=today,
            begin_time=begin_time,
            end_time=end_time,
            pre_close_map=self._get_index_like_pre_close_map(today),
        )
        for row in rows:
            code = row["code"]
            row["name"] = self.name_map.get(code, code)
            row["type"] = "index"
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    
    def fetch_etf_snapshot(self) -> pd.DataFrame:
        """
        获取ETF实时快照
        
        返回:
            DataFrame: 包含ETF实时数据
        """
        today = int(datetime.now().strftime('%Y%m%d'))
        now = datetime.now()
        begin_time, end_time = self._snapshot_window(now)
        rows = self._fetch_realtime_rows(
            self.target_etfs,
            today=today,
            begin_time=begin_time,
            end_time=end_time,
            pre_close_map=self._get_index_like_pre_close_map(today),
        )
        for row in rows:
            code = row["code"]
            row["name"] = self.name_map.get(code, code)
            row["type"] = "etf"
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    
    def fetch_stock_snapshot(self) -> pd.DataFrame:
        """Fetch realtime snapshots for the configured stock pool."""
        if not self.target_stocks:
            return pd.DataFrame()
        today = int(datetime.now().strftime('%Y%m%d'))
        now = datetime.now()
        begin_time, end_time = self._snapshot_window(now)
        rows = self._fetch_realtime_rows(
            self.target_stocks,
            today=today,
            begin_time=begin_time,
            end_time=end_time,
            pre_close_map=self._get_stock_pre_close_map(),
        )
        for row in rows:
            code = row["code"]
            row["name"] = self.name_map.get(code, code)
            row["group"] = self.group_map.get(code, "")
            row["type"] = "stock"
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    @staticmethod
    def _snapshot_window(now: datetime) -> Tuple[int, int]:
        """Build HHMMSS000 bounds without arithmetic on decimal time encoding."""
        start = now - timedelta(minutes=1)
        encode = lambda value: int(value.strftime("%H%M%S")) * 1000
        return encode(start), encode(now)

    def fetch_current_snapshot(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        获取当前时刻的所有监测标的快照
        
        返回:
            Tuple[DataFrame, DataFrame]: (指数数据, ETF数据)
        """
        idx_df = self.fetch_index_snapshot()
        etf_df = self.fetch_etf_snapshot()
        stock_df = self.fetch_stock_snapshot()
        return idx_df, etf_df, stock_df

    def _fetch_realtime_rows(
        self,
        code_list: List[str],
        today: int,
        begin_time: int,
        end_time: int,
        pre_close_map: Optional[Dict[str, float]] = None,
    ) -> List[dict]:
        """Use snapshot first, then fill missing names with same-day min1 bars."""
        if not code_list:
            return []
        snapshot_rows = self._fetch_snapshot_rows(code_list, today, begin_time, end_time)
        rows_by_code = {str(row.get("code", "")): row for row in snapshot_rows if row.get("code")}
        missing_codes = [code for code in code_list if code not in rows_by_code]
        if missing_codes:
            fallback_rows = self._fetch_latest_minute_kline_rows(
                missing_codes,
                today=today,
                pre_close_map=pre_close_map or {},
            )
            for row in fallback_rows:
                code = str(row.get("code", ""))
                if code:
                    rows_by_code[code] = row
        return [rows_by_code[code] for code in code_list if code in rows_by_code]

    def _fetch_snapshot_rows(
        self,
        code_list: List[str],
        today: int,
        begin_time: int,
        end_time: int,
    ) -> List[dict]:
        try:
            result = self.ad_market.query_snapshot(
                code_list=code_list,
                begin_date=today,
                end_date=today,
                begin_time=begin_time,
                end_time=end_time,
            )
            rows = latest_snapshot_rows(result)
            for row in rows:
                row["realtime_source"] = "snapshot"
            if rows:
                return rows
        except Exception:
            pass

        # Some AmazingData deployments return empty rows for narrow one-minute
        # windows during live trading even though a same-day latest snapshot is
        # available. Fall back to the latest snapshot of the day so the minute
        # differencing pipeline can still persist cumulative counters.
        try:
            result = self.ad_market.query_snapshot(
                code_list=code_list,
                begin_date=today,
                end_date=today,
            )
            rows = latest_snapshot_rows(result)
            for row in rows:
                row["realtime_source"] = "snapshot_day_fallback"
            return rows
        except Exception:
            return []

    def _fetch_latest_minute_kline_rows(
        self,
        code_list: List[str],
        today: int,
        pre_close_map: Dict[str, float],
    ) -> List[dict]:
        """
        Fallback to same-day min1 bars.

        query_kline returns per-minute bars, so we rebuild cumulative volume and
        amount before passing the rows to the existing minute-delta pipeline.
        """
        try:
            import AmazingData as ad

            kline_dict = self.ad_market.query_kline(
                code_list,
                begin_date=today,
                end_date=today,
                period=ad.constant.Period.min1.value,
            )
        except Exception:
            return []

        rows = []
        for code, df in iter_kline_frames(kline_dict or {}):
            if df is None or df.empty:
                continue
            work = df.copy()
            for column in ("open", "high", "low", "close", "volume", "amount", "pre_close"):
                if column in work.columns:
                    work[column] = pd.to_numeric(work[column], errors="coerce")
            latest = work.iloc[-1]
            first = work.iloc[0]
            high = (
                float(work["high"].dropna().max())
                if "high" in work.columns and not work["high"].dropna().empty
                else float(latest.get("high", 0) or 0)
            )
            low = (
                float(work["low"].dropna().min())
                if "low" in work.columns and not work["low"].dropna().empty
                else float(latest.get("low", 0) or 0)
            )
            volume = float(work["volume"].fillna(0).sum()) if "volume" in work.columns else 0.0
            amount = float(work["amount"].fillna(0).sum()) if "amount" in work.columns else 0.0
            pre_close = latest.get("pre_close")
            if pd.isna(pre_close) or not pre_close:
                pre_close = pre_close_map.get(code, 0.0)
            close_value = float(latest.get("close", latest.get("last", 0)) or 0.0)
            rows.append(
                {
                    "code": code,
                    "trade_time": latest.get("kline_time", ""),
                    "pre_close": float(pre_close or 0.0),
                    "open": float(first.get("open", latest.get("open", 0)) or 0.0),
                    "high": high,
                    "low": low,
                    "last": close_value,
                    "close": close_value,
                    "volume": volume,
                    "amount": amount,
                    "realtime_source": "kline_min1_fallback",
                }
            )
        return rows

    def _get_stock_pre_close_map(self) -> Dict[str, float]:
        if self._stock_pre_close_map is not None:
            return self._stock_pre_close_map
        try:
            code_info = self.ad_base.get_code_info(security_type="EXTRA_STOCK_A")
            if code_info is None or code_info.empty:
                self._stock_pre_close_map = {}
                return self._stock_pre_close_map
            df = code_info.reset_index()
            df.columns = ["code"] + list(df.columns[1:])
            if "pre_close" not in df.columns:
                self._stock_pre_close_map = {}
                return self._stock_pre_close_map
            df["pre_close"] = pd.to_numeric(df["pre_close"], errors="coerce")
            self._stock_pre_close_map = (
                df[["code", "pre_close"]]
                .dropna(subset=["code"])
                .set_index("code")["pre_close"]
                .fillna(0.0)
                .to_dict()
            )
        except Exception:
            self._stock_pre_close_map = {}
        return self._stock_pre_close_map

    def _get_index_like_pre_close_map(self, today: int) -> Dict[str, float]:
        if self._index_pre_close_map is not None:
            return self._index_pre_close_map
        path = os.path.join(self.base_path, str(today), "indices.csv")
        if not os.path.exists(path):
            self._index_pre_close_map = {}
            return self._index_pre_close_map
        try:
            df = pd.read_csv(path, encoding="utf-8-sig")
            if "code" not in df.columns or "pre_close" not in df.columns:
                self._index_pre_close_map = {}
                return self._index_pre_close_map
            df["pre_close"] = pd.to_numeric(df["pre_close"], errors="coerce")
            self._index_pre_close_map = (
                df[["code", "pre_close"]]
                .dropna(subset=["code"])
                .set_index("code")["pre_close"]
                .fillna(0.0)
                .to_dict()
            )
        except Exception:
            self._index_pre_close_map = {}
        return self._index_pre_close_map
    
    def _restore_previous_counters(self, date_int: int = None) -> int:
        """Restore cumulative counters from today's persisted snapshots after restart."""
        if date_int is None:
            date_int = int(datetime.now().strftime("%Y%m%d"))
        intraday_dir = os.path.join(self.base_path, str(date_int), "intraday")
        for filename in ("indices_1min.csv", "etf_1min.csv", "stocks_1min.csv"):
            path = os.path.join(intraday_dir, filename)
            if not os.path.exists(path):
                continue
            try:
                df = pd.read_csv(path, encoding="utf-8-sig")
            except (OSError, pd.errors.EmptyDataError):
                continue
            if df.empty or "code" not in df.columns:
                continue
            for column in ("time_int", "volume", "amount"):
                if column not in df.columns:
                    df[column] = 0
                df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)
            latest = df.sort_values("time_int").groupby("code", as_index=False).tail(1)
            for _, row in latest.iterrows():
                self._prev_data[str(row["code"])] = {
                    "volume": float(row.get("volume", 0) or 0),
                    "amount": float(row.get("amount", 0) or 0),
                    "time_int": int(row.get("time_int", 0) or 0),
                    "restored": True,
                }
        return len(self._prev_data)

    def _ensure_counter_date(self, date_int: int) -> None:
        """Reset in-memory cumulative counters when a daemon crosses trading days."""
        if getattr(self, "_counter_date", None) == int(date_int):
            return
        self._counter_date = int(date_int)
        self._prev_data = {}
        self._stock_pre_close_map = None
        self._index_pre_close_map = None
        self._restore_previous_counters(self._counter_date)

    def _calc_derived_fields(
        self,
        df: pd.DataFrame,
        now: datetime = None,
        update_cache: bool = True,
    ) -> pd.DataFrame:
        """
        计算衍生字段
        
        新增字段:
        - pct: 涨跌幅
        - time_str: 时间字符串 (HH:MM:SS)
        - time_int: 时间整数 (HHMM)
        - volume_1min: 分钟成交量（增量）
        - amount_1min: 分钟成交额（增量）
        """
        if df.empty:
            return df
        
        df = df.copy()
        
        # 涨跌幅
        if 'last' in df.columns and 'pre_close' in df.columns:
            df['pct'] = ((df['last'] / df['pre_close']) - 1) * 100
            df['pct'] = df['pct'].round(2)
        
        # 时间处理
        now = now or datetime.now()
        if update_cache:
            self._ensure_counter_date(int(now.strftime("%Y%m%d")))
        df['time_str'] = now.strftime('%H:%M:%S')
        df['time_int'] = now.hour * 100 + now.minute
        df['collect_time'] = now
        
        # 计算分钟增量
        for idx, row in df.iterrows():
            code = row['code']
            volume = self._safe_counter(row.get('volume', 0))
            amount = self._safe_counter(row.get('amount', 0))
            source = "first_snapshot"
            counter_reset = False
            
            if code in self._prev_data:
                prev = self._prev_data[code]
                volume_delta = volume - self._safe_counter(prev.get('volume', 0))
                amount_delta = amount - self._safe_counter(prev.get('amount', 0))
                counter_reset = volume_delta < 0 or amount_delta < 0
                if counter_reset:
                    volume_delta = 0
                    amount_delta = 0
                    source = "counter_reset"
                elif prev.get("restored"):
                    source = "restored_previous_snapshot"
                else:
                    source = "previous_snapshot"
                df.at[idx, 'volume_1min'] = volume_delta
                df.at[idx, 'amount_1min'] = amount_delta
            else:
                # 第一次采集，增量为0
                df.at[idx, 'volume_1min'] = 0
                df.at[idx, 'amount_1min'] = 0
            df.at[idx, 'increment_source'] = source
            df.at[idx, 'counter_reset'] = counter_reset
            
            # 更新缓存
            if update_cache:
                self._prev_data[code] = {
                    'volume': volume,
                    'amount': amount,
                    'time_int': df.at[idx, 'time_int'],
                    'restored': False,
                }
        
        return df

    @staticmethod
    def _safe_counter(value) -> float:
        try:
            if value is None or pd.isna(value):
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _append_new_minutes(path: str, df: pd.DataFrame) -> int:
        """Append only snapshots newer than the persisted minute for each code."""
        if df is None or df.empty:
            return 0
        work = df.copy()
        if os.path.exists(path):
            try:
                existing = pd.read_csv(path, encoding="utf-8-sig")
            except (OSError, pd.errors.EmptyDataError):
                existing = pd.DataFrame()
            columns = list(dict.fromkeys([*existing.columns, *work.columns]))
            if columns != list(existing.columns):
                existing = existing.reindex(columns=columns, fill_value="")
                existing.to_csv(path, index=False, encoding="utf-8-sig")
            work = work.reindex(columns=columns, fill_value="")
            if not existing.empty and {"code", "time_int"}.issubset(existing.columns):
                existing["time_int"] = pd.to_numeric(existing["time_int"], errors="coerce").fillna(0)
                last_saved = existing.groupby("code")["time_int"].max().to_dict()
                work = work[
                    work.apply(
                        lambda row: float(row.get("time_int", 0)) > float(last_saved.get(row.get("code"), -1)),
                        axis=1,
                    )
                ]
        if work.empty:
            return 0
        work.to_csv(
            path,
            mode="a" if os.path.exists(path) else "w",
            header=not os.path.exists(path),
            index=False,
            encoding="utf-8-sig",
        )
        return len(work)
    
    def save_minute_data(self, idx_df: pd.DataFrame, etf_df: pd.DataFrame,
                         stock_df: pd.DataFrame = None,
                         date_int: int = None) -> Tuple[str, str, str]:
        """
        保存分钟数据到CSV（追加模式）
        
        参数:
            idx_df: 指数数据
            etf_df: ETF数据
            date_int: 日期，默认今天
            
        返回:
            Tuple[str, str]: (指数文件路径, ETF文件路径)
        """
        intraday_dir = self._get_intraday_dir(date_int)
        
        idx_path = os.path.join(intraday_dir, "indices_1min.csv")
        etf_path = os.path.join(intraday_dir, "etf_1min.csv")
        stock_path = os.path.join(intraday_dir, "stocks_1min.csv")
        
        # 选择要保存的列
        save_columns = [
            'code', 'name', 'time_int', 'time_str',
            'pre_close', 'open', 'high', 'low', 'last',
            'volume', 'amount', 'volume_1min', 'amount_1min',
            'increment_source', 'counter_reset', 'pct', 'group',
            'realtime_source'
        ]
        
        # 保存指数数据
        if not idx_df.empty:
            idx_df = self._calc_derived_fields(idx_df)
            cols_to_save = [c for c in save_columns if c in idx_df.columns]
            idx_save = idx_df[cols_to_save]
            
            self._append_new_minutes(idx_path, idx_save)
        
        # 保存ETF数据
        if not etf_df.empty:
            etf_df = self._calc_derived_fields(etf_df)
            cols_to_save = [c for c in save_columns if c in etf_df.columns]
            etf_save = etf_df[cols_to_save]
            
            self._append_new_minutes(etf_path, etf_save)
        
        if stock_df is not None and not stock_df.empty:
            stock_df = self._calc_derived_fields(stock_df)
            cols_to_save = [c for c in save_columns if c in stock_df.columns]
            stock_save = stock_df[cols_to_save]
            self._append_new_minutes(stock_path, stock_save)

        return idx_path, etf_path, stock_path

    def rebuild_opening_session_from_snapshot(
        self,
        date_int: int = None,
        start_hhmm: int = 925,
        end_hhmm: int = 935,
        force: bool = False,
        stock_codes: Optional[List[str]] = None,
        etf_codes: Optional[List[str]] = None,
        index_codes: Optional[List[str]] = None,
        mode: str = "minimal",
        data_kind: str = "min1",
        warn_after_sec: Optional[float] = None,
        progress_path: Optional[str] = None,
        stage: str = "all",
        begin_hhmm: int = 930,
        end_hhmm_window: int = 935,
        batch_size: int = 120,
        max_stocks: int = 0,
        only_codes: Optional[List[str]] = None,
        skip_existing: bool = False,
        isolated_query: bool = False,
    ) -> Dict:
        """
        Rebuild 09:25-09:35 minute snapshots from historical level-1 snapshots.

        This serves as a post-close backfill path when the live monitor missed
        intraday files, allowing the 09:35 confirmation layer to remain usable.
        """
        date_int = int(date_int or datetime.now().strftime("%Y%m%d"))
        intraday_dir = self._get_intraday_dir(date_int)
        latest_path = os.path.join(intraday_dir, "stock_confirmation_latest.csv")
        stage = str(stage or "all").strip().lower()
        if os.path.exists(latest_path) and not force and stage == "all":
            return {"rebuilt": True, "skipped": True, "reason": "confirmation_exists"}

        progress_path = progress_path or self._default_backfill_progress_path()
        self._log_backfill_event(
            date_int,
            stage="day_start",
            status="start",
            progress_path=progress_path,
            extra={
                "mode": mode,
                "data_kind": data_kind,
                "start_hhmm": int(start_hhmm),
                "end_hhmm": int(end_hhmm),
                "stage": stage,
                "begin_hhmm": int(begin_hhmm),
                "end_hhmm_window": int(end_hhmm_window),
                "batch_size": int(batch_size),
                "max_stocks": int(max_stocks or 0),
                "skip_existing": bool(skip_existing),
                "bootstrap_mode": "isolated_query" if isolated_query else "shared_client",
            },
        )

        if mode == "full":
            selected_indices = list(self.target_indices)
            selected_etfs = list(self.target_etfs)
            selected_stocks = list(self.target_stocks)
        else:
            selected_indices = [str(code) for code in (index_codes or []) if str(code)]
            selected_etfs = [str(code) for code in (etf_codes or []) if str(code)]
            selected_stocks = [str(code) for code in (stock_codes or []) if str(code)]

        if only_codes:
            selected_only = {str(code).strip() for code in only_codes if str(code).strip()}
            selected_indices = [code for code in selected_indices if code in selected_only]
            selected_etfs = [code for code in selected_etfs if code in selected_only]
            selected_stocks = [code for code in selected_stocks if code in selected_only]
        if max_stocks and int(max_stocks) > 0:
            selected_stocks = selected_stocks[: int(max_stocks)]

        self._log_backfill_event(
            date_int,
            stage="universe",
            status="done",
            progress_path=progress_path,
            extra={
                "mode": mode,
                "data_kind": data_kind,
                "stock_code_count": len(selected_stocks),
                "etf_code_count": len(selected_etfs),
                "index_code_count": len(selected_indices),
                "requested_stage": stage,
                "stock_codes": selected_stocks[:50],
                "etf_codes": selected_etfs[:30],
                "index_codes": selected_indices[:30],
            },
        )

        try:
            idx_path = os.path.join(intraday_dir, "indices_1min.csv")
            etf_path = os.path.join(intraday_dir, "etf_1min.csv")
            stock_path = os.path.join(intraday_dir, "stocks_1min.csv")
            idx_df = pd.DataFrame()
            etf_df = pd.DataFrame()
            stock_df = pd.DataFrame()

            if stage in {"all", "index"}:
                if skip_existing and os.path.exists(idx_path) and not force:
                    self._log_backfill_event(
                        date_int,
                        stage="index_min1",
                        status="skipped",
                        code_count=len(selected_indices),
                        progress_path=progress_path,
                        output_path=idx_path,
                        extra={"reason": "skip_existing"},
                    )
                else:
                    idx_df = self._rebuild_opening_minutes_backfill(
                        date_int=date_int,
                        code_list=selected_indices,
                        code_type="index",
                        data_kind=data_kind,
                        warn_after_sec=warn_after_sec,
                        progress_path=progress_path,
                        begin_hhmm=begin_hhmm,
                        end_hhmm=end_hhmm_window,
                        batch_size=batch_size,
                        isolated_query=isolated_query,
                    )

            if stage in {"all", "etf"}:
                if skip_existing and os.path.exists(etf_path) and not force:
                    self._log_backfill_event(
                        date_int,
                        stage="etf_min1",
                        status="skipped",
                        code_count=len(selected_etfs),
                        progress_path=progress_path,
                        output_path=etf_path,
                        extra={"reason": "skip_existing"},
                    )
                else:
                    etf_df = self._rebuild_opening_minutes_backfill(
                        date_int=date_int,
                        code_list=selected_etfs,
                        code_type="etf",
                        data_kind=data_kind,
                        warn_after_sec=warn_after_sec,
                        progress_path=progress_path,
                        begin_hhmm=begin_hhmm,
                        end_hhmm=end_hhmm_window,
                        batch_size=batch_size,
                        isolated_query=isolated_query,
                    )

            if stage in {"all", "stock"}:
                if skip_existing and os.path.exists(stock_path) and not force:
                    self._log_backfill_event(
                        date_int,
                        stage="stock_min1",
                        status="skipped",
                        code_count=len(selected_stocks),
                        progress_path=progress_path,
                        output_path=stock_path,
                        extra={"reason": "skip_existing"},
                    )
                else:
                    stock_df = self._rebuild_opening_minutes_backfill(
                        date_int=date_int,
                        code_list=selected_stocks,
                        code_type="stock",
                        data_kind=data_kind,
                        warn_after_sec=warn_after_sec,
                        progress_path=progress_path,
                        begin_hhmm=begin_hhmm,
                        end_hhmm=end_hhmm_window,
                        batch_size=batch_size,
                        isolated_query=isolated_query,
                    )

            if stage in {"all", "index"} and not idx_df.empty:
                self._run_backfill_stage(
                    date_int,
                    stage="write_indices_1min",
                    code_count=len(selected_indices),
                    runner=lambda: (
                        idx_df.to_csv(idx_path, index=False, encoding="utf-8-sig"),
                        {"row_count": len(idx_df)},
                    )[1],
                    progress_path=progress_path,
                    warn_after_sec=warn_after_sec,
                    output_path=idx_path,
                )
            if stage in {"all", "etf"} and not etf_df.empty:
                self._run_backfill_stage(
                    date_int,
                    stage="write_etf_1min",
                    code_count=len(selected_etfs),
                    runner=lambda: (
                        etf_df.to_csv(etf_path, index=False, encoding="utf-8-sig"),
                        {"row_count": len(etf_df)},
                    )[1],
                    progress_path=progress_path,
                    warn_after_sec=warn_after_sec,
                    output_path=etf_path,
                )
            if stage in {"all", "stock"} and not stock_df.empty:
                self._run_backfill_stage(
                    date_int,
                    stage="write_stocks_1min",
                    code_count=len(selected_stocks),
                    runner=lambda: (
                        stock_df.to_csv(stock_path, index=False, encoding="utf-8-sig"),
                        {"row_count": len(stock_df)},
                    )[1],
                    progress_path=progress_path,
                    warn_after_sec=warn_after_sec,
                    output_path=stock_path,
                )

            confirmation_path = latest_path
            confirmation_history_path = os.path.join(intraday_dir, "stock_confirmation_history.csv")
            if stage in {"all", "confirmation"}:
                if skip_existing and os.path.exists(confirmation_path) and not force:
                    self._log_backfill_event(
                        date_int,
                        stage="build_confirmation_latest",
                        status="skipped",
                        code_count=len(selected_stocks),
                        progress_path=progress_path,
                        output_path=confirmation_path,
                        extra={"reason": "skip_existing"},
                    )
                else:
                    self._run_backfill_stage(
                        date_int,
                        stage="build_confirmation_latest",
                        code_count=len(selected_stocks),
                        runner=lambda: self._save_confirmation_with_count(date_int),
                        progress_path=progress_path,
                        warn_after_sec=warn_after_sec,
                        output_path=confirmation_path,
                    )
        except Exception as exc:
            self._log_backfill_event(
                date_int,
                stage="day_failed",
                status="failed",
                progress_path=progress_path,
                error=str(exc),
                extra={"mode": mode, "data_kind": data_kind},
            )
            raise

        self._log_backfill_event(
            date_int,
            stage="day_done",
            status="done",
            progress_path=progress_path,
            extra={"mode": mode, "data_kind": data_kind},
        )
        return {
            "rebuilt": True,
            "skipped": False,
            "date": date_int,
            "index_count": len(idx_df),
            "etf_count": len(etf_df),
            "stock_count": len(stock_df),
            "confirmation_path": confirmation_path,
            "confirmation_history_path": confirmation_history_path,
            "source": "historical_snapshot_minute" if data_kind != "min1" else "historical_min1_only",
            "mode": mode,
            "data_kind": data_kind,
            "progress_path": progress_path,
            "stage": stage,
            "bootstrap_mode": "isolated_query" if isolated_query else "shared_client",
        }

    def _save_confirmation_with_count(self, date_int: int) -> Dict:
        latest_path, history_path = self.save_intraday_confirmation(date_int)
        row_count = 0
        if os.path.exists(latest_path):
            try:
                row_count = len(pd.read_csv(latest_path, encoding="utf-8-sig"))
            except Exception:
                row_count = 0
        return {
            "row_count": row_count,
            "confirmation_path": latest_path,
            "confirmation_history_path": history_path,
        }

    def _rebuild_opening_minutes_backfill(
        self,
        date_int: int,
        code_list: List[str],
        code_type: str,
        data_kind: str = "min1",
        warn_after_sec: Optional[float] = None,
        progress_path: Optional[str] = None,
        begin_hhmm: int = 930,
        end_hhmm: int = 935,
        batch_size: int = 120,
        isolated_query: bool = False,
    ) -> pd.DataFrame:
        if not code_list:
            return pd.DataFrame()

        kinds = {item.strip().lower() for item in str(data_kind or "min1").split(",") if item.strip()}
        use_snapshot = "snapshot" in kinds
        use_min1 = "min1" in kinds

        snapshot_rows = []
        if use_snapshot:
            snapshot_rows = self._run_backfill_stage(
                date_int,
                stage=f"{code_type}_snapshot",
                code_count=len(code_list),
                runner=lambda: self._fetch_snapshot_point_rows(code_list, date_int, target_hhmmss=92500),
                progress_path=progress_path,
                warn_after_sec=warn_after_sec,
            )
        else:
            self._log_backfill_event(
                date_int,
                stage=f"{code_type}_snapshot",
                status="skipped",
                code_count=len(code_list),
                progress_path=progress_path,
                extra={"reason": "data_kind_without_snapshot"},
            )

        kline_rows = pd.DataFrame()
        if use_min1:
            kline_rows = self._run_backfill_stage(
                date_int,
                stage=f"{code_type}_min1",
                code_count=len(code_list),
                runner=lambda: self._fetch_opening_minute_bars(
                    code_list,
                    date_int,
                    begin_hhmm=begin_hhmm,
                    end_hhmm=end_hhmm,
                    batch_size=batch_size,
                    progress_path=progress_path,
                    warn_after_sec=warn_after_sec,
                    stage_name=f"{code_type}_min1",
                    isolated_query=isolated_query,
                ),
                progress_path=progress_path,
                warn_after_sec=warn_after_sec,
            )
        else:
            self._log_backfill_event(
                date_int,
                stage=f"{code_type}_min1",
                status="skipped",
                code_count=len(code_list),
                progress_path=progress_path,
                extra={"reason": "data_kind_without_min1"},
            )

        if not snapshot_rows and kline_rows.empty:
            return pd.DataFrame()

        snapshot_map = {str(row.get("code", "")): row for row in snapshot_rows if row.get("code")}
        pre_close_map = (
            self._get_stock_pre_close_map()
            if code_type == "stock"
            else self._get_index_like_pre_close_map(int(date_int))
        )

        rows = []
        for code in code_list:
            code = str(code)
            k_hist = kline_rows[kline_rows["code"] == code].copy() if not kline_rows.empty else pd.DataFrame()
            snap = snapshot_map.get(code, {})
            auction_amount = self._safe_counter(snap.get("amount", 0))
            auction_volume = self._safe_counter(snap.get("volume", 0))
            pre_close = self._safe_counter(snap.get("pre_close", pre_close_map.get(code, 0)))
            auction_open = self._safe_counter(snap.get("open", snap.get("last", 0)))
            auction_last = self._safe_counter(snap.get("last", auction_open))

            if pre_close <= 0 and not k_hist.empty and "pre_close" in k_hist.columns:
                first_pre_close = pd.to_numeric(k_hist["pre_close"], errors="coerce").dropna()
                if not first_pre_close.empty:
                    pre_close = float(first_pre_close.iloc[0])

            if auction_open > 0 and pre_close > 0:
                rows.append(
                    {
                        "code": code,
                        "name": self.name_map.get(code, code),
                        "time_int": 925,
                        "time_str": "09:25:00",
                        "pre_close": pre_close,
                        "open": auction_open,
                        "high": self._safe_counter(snap.get("high", auction_open)),
                        "low": self._safe_counter(snap.get("low", auction_open)),
                        "last": auction_last if auction_last > 0 else auction_open,
                        "volume": auction_volume,
                        "amount": auction_amount,
                        "volume_1min": 0.0,
                        "amount_1min": 0.0,
                        "increment_source": "historical_snapshot_925",
                        "counter_reset": False,
                        "pct": round((auction_open / pre_close - 1.0) * 100.0, 4),
                        "group": self.group_map.get(code, "") if code_type == "stock" else "",
                        "realtime_source": "historical_snapshot_925",
                    }
                )

            if k_hist.empty:
                continue

            for column in ("open", "high", "low", "close", "volume", "amount", "pre_close"):
                if column not in k_hist.columns:
                    k_hist[column] = 0.0
                k_hist[column] = pd.to_numeric(k_hist[column], errors="coerce").fillna(0.0)
            if "kline_time" in k_hist.columns:
                k_hist["_kline_hhmmss"] = k_hist["kline_time"].map(trade_time_to_hhmmss)
                k_hist["time_int"] = (
                    pd.to_numeric(k_hist["_kline_hhmmss"], errors="coerce").fillna(0).astype(int) // 100
                )
            k_hist = k_hist[(k_hist["time_int"] >= 930) & (k_hist["time_int"] <= 935)].copy()
            if k_hist.empty:
                continue
            k_hist = k_hist.sort_values("time_int")

            cumulative_amount = auction_amount
            cumulative_volume = auction_volume
            for _, bar in k_hist.iterrows():
                cumulative_amount += self._safe_counter(bar.get("amount", 0))
                cumulative_volume += self._safe_counter(bar.get("volume", 0))
                bar_pre_close = self._safe_counter(bar.get("pre_close", 0))
                if bar_pre_close <= 0:
                    bar_pre_close = pre_close
                bar_open = self._safe_counter(bar.get("open", 0))
                bar_close = self._safe_counter(bar.get("close", 0))
                if bar_pre_close <= 0 or bar_open <= 0:
                    continue
                rows.append(
                    {
                        "code": code,
                        "name": self.name_map.get(code, code),
                        "time_int": int(bar.get("time_int", 0)),
                        "time_str": f"{int(bar.get('time_int', 0)) // 100:02d}:{int(bar.get('time_int', 0)) % 100:02d}:00",
                        "pre_close": bar_pre_close,
                        "open": bar_open,
                        "high": self._safe_counter(bar.get("high", 0)),
                        "low": self._safe_counter(bar.get("low", 0)),
                        "last": bar_close,
                        "volume": cumulative_volume,
                        "amount": cumulative_amount,
                        "volume_1min": self._safe_counter(bar.get("volume", 0)),
                        "amount_1min": self._safe_counter(bar.get("amount", 0)),
                        "increment_source": "min1_after_snapshot_925" if use_snapshot else "min1_only_replay",
                        "counter_reset": False,
                        "pct": round((bar_close / bar_pre_close - 1.0) * 100.0, 4) if bar_pre_close > 0 else 0.0,
                        "group": self.group_map.get(code, "") if code_type == "stock" else "",
                        "realtime_source": "historical_snapshot_925_plus_min1" if use_snapshot else "historical_min1_only",
                    }
                )

        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows)

    def _fetch_snapshot_point_rows(
        self,
        code_list: List[str],
        date_int: int,
        target_hhmmss: int,
        window_seconds: int = 5,
    ) -> List[dict]:
        rows = []
        batch_size = 120
        for i in range(0, len(code_list), batch_size):
            batch = code_list[i:i + batch_size]
            hour = int(target_hhmmss) // 10000
            minute = (int(target_hhmmss) // 100) % 100
            second = int(target_hhmmss) % 100
            total_seconds = hour * 3600 + minute * 60 + second
            begin_total = max(0, total_seconds - int(window_seconds))
            end_total = total_seconds + int(window_seconds)

            def _encode(total):
                hh = total // 3600
                mm = (total % 3600) // 60
                ss = total % 60
                return hh * 10000 + mm * 100 + ss

            try:
                result = self.ad_market.query_snapshot(
                    code_list=batch,
                    begin_date=int(date_int),
                    end_date=int(date_int),
                    begin_time=self._encode_snapshot_hhmmss_millis(_encode(begin_total)),
                    end_time=self._encode_snapshot_hhmmss_millis(_encode(end_total)),
                )
            except Exception:
                continue
            rows.extend(
                snapshot_rows_near_time(
                    result,
                    target_hhmmss=int(target_hhmmss),
                    floor_hhmmss=_encode(begin_total),
                    ceil_hhmmss=_encode(end_total),
                )
            )
        return rows

    def _fetch_opening_minute_bars(
        self,
        code_list: List[str],
        date_int: int,
        begin_hhmm: int = 930,
        end_hhmm: int = 935,
        batch_size: int = 120,
        progress_path: Optional[str] = None,
        warn_after_sec: Optional[float] = None,
        stage_name: str = "min1",
        isolated_query: bool = False,
    ) -> pd.DataFrame:
        if not code_list:
            return pd.DataFrame()
        if isolated_query:
            return query_min1_kline_once(
                date_int=int(date_int),
                code_list=list(code_list),
                begin_time=int(begin_hhmm),
                end_time=int(end_hhmm),
                batch_size=int(batch_size),
                progress_path=progress_path,
                stage=stage_name,
                warn_after_sec=warn_after_sec,
            )
        rows = []

        for i in range(0, len(code_list), batch_size):
            batch = code_list[i:i + batch_size]
            batch_started = time.time()
            self._log_backfill_event(
                date_int,
                stage=f"{stage_name}_batch",
                status="start",
                code_count=len(batch),
                progress_path=progress_path,
                extra={"batch_codes": batch},
            )
            try:
                import AmazingData as ad

                result = self.ad_market.query_kline(
                    batch,
                    begin_date=int(date_int),
                    end_date=int(date_int),
                    period=ad.constant.Period.min1.value,
                    begin_time=self._encode_kline_hhmm(begin_hhmm),
                    end_time=self._encode_kline_hhmm(end_hhmm),
                )
            except Exception:
                self._log_backfill_event(
                    date_int,
                    stage=f"{stage_name}_batch",
                    status="failed",
                    elapsed_sec=time.time() - batch_started,
                    code_count=len(batch),
                    progress_path=progress_path,
                    error="query_kline_failed",
                    extra={"batch_codes": batch},
                )
                continue

            batch_rows = 0
            for code, frame in iter_kline_frames(result or {}):
                if frame is None or frame.empty:
                    continue
                work = frame.copy()
                work["code"] = code
                if "kline_time" in work.columns:
                    work["_kline_hhmmss"] = work["kline_time"].map(trade_time_to_hhmmss)
                    work["time_int"] = (
                        pd.to_numeric(work["_kline_hhmmss"], errors="coerce").fillna(0).astype(int) // 100
                    )
                    work = work[(work["time_int"] >= int(begin_hhmm)) & (work["time_int"] <= int(end_hhmm))].copy()
                batch_rows += len(work)
                rows.append(work)
            batch_elapsed = time.time() - batch_started
            warning = "batch_elapsed_exceeded_warn_after_sec" if warn_after_sec and batch_elapsed >= float(warn_after_sec) else ""
            self._log_backfill_event(
                date_int,
                stage=f"{stage_name}_batch",
                status="done",
                elapsed_sec=batch_elapsed,
                code_count=len(batch),
                row_count=batch_rows,
                progress_path=progress_path,
                warning=warning,
                extra={"batch_codes": batch},
            )
        if not rows:
            return pd.DataFrame()
        return pd.concat(rows, ignore_index=True)

    def _rebuild_snapshot_minutes(
        self,
        code_list: List[str],
        date_int: int,
        begin_time: int,
        end_time: int,
        code_type: str,
    ) -> pd.DataFrame:
        if not code_list:
            return pd.DataFrame()
        target_minutes = [925, 930, 931, 932, 933, 934, 935]
        rows = []
        batch_size = 80
        for i in range(0, len(code_list), batch_size):
            batch = code_list[i:i + batch_size]
            batch_rows = []
            for minute in target_minutes:
                hhmmss = minute * 100
                begin_target = max(begin_time, (hhmmss - 2) * 1000)
                end_target = min(end_time, (hhmmss + 2) * 1000)
                try:
                    result = self.ad_market.query_snapshot(
                        code_list=batch,
                        begin_date=int(date_int),
                        end_date=int(date_int),
                        begin_time=self._encode_snapshot_hhmmss_millis(int(begin_target) // 1000),
                        end_time=self._encode_snapshot_hhmmss_millis(int(end_target) // 1000),
                    )
                except Exception:
                    continue
                selected = snapshot_rows_near_time(
                    result,
                    target_hhmmss=hhmmss,
                    floor_hhmmss=max(0, hhmmss - 2),
                    ceil_hhmmss=hhmmss + 2,
                )
                for row in selected:
                    row["time_int"] = minute
                    batch_rows.append(row)
            if not batch_rows:
                continue
            batch_df = pd.DataFrame(batch_rows)
            for code, frame in batch_df.groupby("code", sort=False):
                minute_rows = self._snapshot_frame_to_minutes(frame, code, code_type)
                if minute_rows.empty:
                    continue
                rows.append(minute_rows)
        if not rows:
            return pd.DataFrame()
        return pd.concat(rows, ignore_index=True)

    def _snapshot_frame_to_minutes(self, frame: pd.DataFrame, code: str, code_type: str) -> pd.DataFrame:
        if frame is None or frame.empty:
            return pd.DataFrame()
        work = frame.copy()
        if "code" in work.columns:
            work["code"] = work["code"].fillna(code)
        else:
            work["code"] = code
        work["_hhmmss"] = work.get("trade_time").map(trade_time_to_hhmmss)
        work = work[work["_hhmmss"].notna()].copy()
        if work.empty:
            return pd.DataFrame()

        work["_hhmmss"] = work["_hhmmss"].astype(int)
        work["time_int"] = (work["_hhmmss"] // 100).astype(int)
        work = work[(work["time_int"] >= 925) & (work["time_int"] <= 935)].copy()
        if work.empty:
            return pd.DataFrame()
        work = work.sort_values(["time_int", "_hhmmss"])
        minute = work.groupby("time_int", as_index=False).tail(1).copy()

        for column in ("pre_close", "open", "high", "low", "last", "close", "volume", "amount"):
            if column not in minute.columns:
                minute[column] = 0.0
            minute[column] = pd.to_numeric(minute[column], errors="coerce").fillna(0.0)

        minute["name"] = minute["code"].map(self.name_map).fillna(minute["code"])
        minute["group"] = minute["code"].map(self.group_map).fillna("") if code_type == "stock" else ""
        minute["type"] = code_type
        minute["time_str"] = minute["time_int"].astype(str).str.zfill(4).str.slice(0, 2) + ":" + minute["time_int"].astype(str).str.zfill(4).str.slice(2, 4) + ":00"
        minute["pct"] = np.where(
            minute["pre_close"] > 0,
            (minute["last"] / minute["pre_close"] - 1.0) * 100.0,
            0.0,
        ).round(4)
        minute["volume_1min"] = minute["volume"].diff().fillna(0.0).clip(lower=0.0)
        minute["amount_1min"] = minute["amount"].diff().fillna(0.0).clip(lower=0.0)
        minute["increment_source"] = "historical_snapshot_diff"
        minute["counter_reset"] = False
        minute["realtime_source"] = "historical_snapshot_minute"
        columns = [
            "code", "name", "time_int", "time_str", "pre_close", "open", "high",
            "low", "last", "volume", "amount", "volume_1min", "amount_1min",
            "increment_source", "counter_reset", "pct", "group", "realtime_source",
        ]
        return minute[columns].reset_index(drop=True)
    
    def load_intraday_data(self, date_int: int = None, data_type: str = 'index') -> pd.DataFrame:
        """
        加载盘中历史数据
        
        参数:
            date_int: 日期
            data_type: 'index' 或 'etf'
            
        返回:
            DataFrame: 历史分钟数据
        """
        intraday_dir = self._get_intraday_dir(date_int)
        
        if data_type == 'index':
            path = os.path.join(intraday_dir, "indices_1min.csv")
        elif data_type == 'etf':
            path = os.path.join(intraday_dir, "etf_1min.csv")
        else:
            path = os.path.join(intraday_dir, "stocks_1min.csv")
        
        if os.path.exists(path):
            return pd.read_csv(path, encoding='utf-8-sig')
        return pd.DataFrame()
    
    def get_last_collect_time(self, date_int: int = None) -> Optional[int]:
        """
        获取最后采集时间（用于断点续传）
        
        返回:
            int: 最后采集的时间 (HHMM格式)，无记录返回None
        """
        idx_df = self.load_intraday_data(date_int, 'index')
        if idx_df.empty:
            return None
        return idx_df['time_int'].max()

    def save_intraday_confirmation(self, date_int: int = None) -> Tuple[str, str]:
        """Persist the latest stock relative-strength and amount confirmations."""
        intraday_dir = self._get_intraday_dir(date_int)
        latest_path = os.path.join(intraday_dir, "stock_confirmation_latest.csv")
        history_path = os.path.join(intraday_dir, "stock_confirmation_history.csv")
        features = IntradayConfirmationBuilder.build(
            self.load_intraday_data(date_int, "stock"),
            self.load_intraday_data(date_int, "etf"),
            self.load_intraday_data(date_int, "index"),
        )
        if features.empty:
            return latest_path, history_path
        features.to_csv(latest_path, index=False, encoding="utf-8-sig")
        self._append_new_minutes(history_path, features)
        return latest_path, history_path
    
    def collect_once(self) -> Dict:
        """
        执行一次数据采集
        
        返回:
            dict: 采集结果统计
        """
        start = time.time()
        
        idx_df, etf_df, stock_df = self.fetch_current_snapshot()
        idx_path, etf_path, stock_path = self.save_minute_data(idx_df, etf_df, stock_df)
        confirmation_path, confirmation_history_path = self.save_intraday_confirmation()
        
        elapsed = time.time() - start
        
        result = {
            'time': datetime.now().strftime('%H:%M:%S'),
            'index_count': len(idx_df),
            'etf_count': len(etf_df),
            'stock_count': len(stock_df),
            'elapsed': round(elapsed, 2),
            'idx_path': idx_path,
            'etf_path': etf_path,
            'stock_path': stock_path,
            'confirmation_path': confirmation_path,
            'confirmation_history_path': confirmation_history_path,
        }
        result["source_counts"] = {
            "index": idx_df.get("realtime_source", pd.Series(dtype=str)).value_counts().to_dict() if not idx_df.empty else {},
            "etf": etf_df.get("realtime_source", pd.Series(dtype=str)).value_counts().to_dict() if not etf_df.empty else {},
            "stock": stock_df.get("realtime_source", pd.Series(dtype=str)).value_counts().to_dict() if not stock_df.empty else {},
        }
        if not idx_df.empty or not etf_df.empty or not stock_df.empty:
            self._empty_snapshot_rounds = 0
        else:
            self._empty_snapshot_rounds = getattr(self, "_empty_snapshot_rounds", 0) + 1
        result["empty_snapshot_rounds"] = self._empty_snapshot_rounds
        
        return result
    
    def print_status(self, result: Dict):
        """打印采集状态"""
        phase = MarketState.get_current_phase()
        phase_name = MarketState.get_phase_name(phase)
        
        print(f"  [{result['time']}] {phase_name} | "
              f"指数:{result['index_count']}只 ETF:{result['etf_count']}只 "
              f"股票:{result.get('stock_count', 0)}只 | "
              f"耗时:{result['elapsed']}s")
        source_counts = result.get("source_counts", {})
        fallback_total = sum(
            counts.get("kline_min1_fallback", 0)
            for counts in source_counts.values()
            if isinstance(counts, dict)
        )
        if fallback_total:
            print(f"    min1 fallback: {fallback_total}")
        empty_rounds = result.get("empty_snapshot_rounds", 0)
        if empty_rounds in {3, 10} or (empty_rounds > 0 and empty_rounds % 30 == 0):
            print(f"  ⚠️ 连续 {empty_rounds} 轮快照为空，请检查 AmazingData 返回结构或行情连接")
    
    def print_market_summary(self, idx_df: pd.DataFrame, etf_df: pd.DataFrame):
        """
        打印市场摘要
        
        显示指数涨跌和ETF涨跌排行
        """
        print("\n" + "="*60)
        print("  📊 市场实时概览")
        print("="*60)
        
        # 指数概览
        if not idx_df.empty and 'pct' in idx_df.columns:
            idx_df = self._calc_derived_fields(idx_df, update_cache=False)
            print("\n  【四大指数】")
            for _, row in idx_df.iterrows():
                pct = row.get('pct', 0)
                symbol = '🔺' if pct > 0 else ('🔻' if pct < 0 else '➖')
                name = row.get('name', row['code'])
                print(f"    {symbol} {name}: {pct:+.2f}%")
        
        # ETF涨跌榜
        if not etf_df.empty and 'pct' in etf_df.columns:
            etf_df = self._calc_derived_fields(etf_df, update_cache=False)
            etf_sorted = etf_df.sort_values('pct', ascending=False)
            
            print("\n  【ETF涨幅榜 TOP5】")
            for _, row in etf_sorted.head(5).iterrows():
                pct = row.get('pct', 0)
                name = row.get('name', row['code'])
                print(f"    🔥 {name}: {pct:+.2f}%")
            
            print("\n  【ETF跌幅榜 TOP5】")
            for _, row in etf_sorted.tail(5).iterrows():
                pct = row.get('pct', 0)
                name = row.get('name', row['code'])
                print(f"    💧 {name}: {pct:+.2f}%")
        
        print()


# 便捷函数
def get_market_phase() -> MarketPhase:
    """获取当前市场阶段"""
    return MarketState.get_current_phase()


def is_trading_time() -> bool:
    """判断是否在交易时间"""
    return MarketState.is_trading_time()
