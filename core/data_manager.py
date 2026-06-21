# -*- coding: utf-8 -*-
"""
数据管理器 - 统一数据获取/存储/加载
优化：使用分钟K线替代快照（提速100倍）
"""

import json
import os
import pandas as pd
import time
import AmazingData as ad
from datetime import datetime
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from config.settings import DBConfig, MarketConfig, UniverseConfig
from core.calendar_helper import CalendarHelper
from core.snapshot_utils import latest_snapshot_rows, snapshot_rows_near_time

try:
    from tqdm import tqdm
except ImportError:
    class _Progress:
        def __init__(self, iterable=None, desc=None, total=None, **kwargs):
            self.iterable = iterable
            self.desc = desc
            if desc:
                print(f"--- {desc} ---")

        def __iter__(self):
            return iter(self.iterable or [])

        def update(self, n=1):
            return None

        def close(self):
            return None

    def tqdm(iterable=None, desc=None, **kwargs):
        return _Progress(iterable=iterable, desc=desc, **kwargs)


class DataManager:
    """数据管理器"""

    A_SHARE_CLOSE_CUTOFF = (15, 0)
    HK_CLOSE_CUTOFF = (16, 0)
    
    def __init__(self, base_path=DBConfig.STORE_PATH, max_workers=DBConfig.MAX_WORKERS):
        self.base_path = base_path
        self.max_workers = max_workers
        
        os.makedirs(self.base_path, exist_ok=True)
        print(f"[DataManager] 数据仓库: {os.path.abspath(self.base_path)}")
        
        self.ad_base = ad.BaseData()
        self.ad_info = ad.InfoData()
        
        self.calendar = CalendarHelper.generate_workday_calendar(days=400)
        print(f"  ✓ 工作日日历: {len(self.calendar)} 天")
        
        self.ad_market = ad.MarketData(self.calendar)
        
        # 缓存
        self._industry_cache = None
        self._industry_code_cache = None
        self._name_map_cache = None
        self._valid_days_cache = None

    # ================= 工具方法 =================
    
    def _get_date_dir(self, date_int, create=True):
        d_dir = os.path.join(self.base_path, str(date_int))
        if create:
            os.makedirs(d_dir, exist_ok=True)
        return d_dir

    def _file_ready(self, path, min_size=128):
        """Return True when a cached CSV exists and is not obviously empty."""
        return os.path.exists(path) and os.path.getsize(path) >= min_size

    def _infer_close_cutoff(self, date_dir=None, filename=None):
        """Infer same-day market close cutoff from a cached file when possible."""
        path = os.path.join(date_dir, filename) if date_dir and filename else ""
        if not path or not os.path.exists(path):
            return self.A_SHARE_CLOSE_CUTOFF
        try:
            sample = pd.read_csv(path, dtype=str, usecols=["code"], nrows=50)
            codes = sample.get("code")
            if codes is not None and codes.astype(str).str.upper().str.endswith(".HK").any():
                return self.HK_CLOSE_CUTOFF
        except Exception:
            return self.A_SHARE_CLOSE_CUTOFF
        return self.A_SHARE_CLOSE_CUTOFF

    def _session_state_for_date(self, target_date, date_dir=None, filename=None):
        """Return whether a same-day daily bar should be treated as intraday or closed."""
        now = datetime.now()
        today = int(now.strftime("%Y%m%d"))
        target_date = int(target_date)
        if target_date < today:
            return "closed"
        if target_date > today:
            return "future"
        cutoff = self._infer_close_cutoff(date_dir=date_dir, filename=filename)
        return "closed" if (now.hour, now.minute) >= cutoff else "intraday"

    def _meta_path(self, date_dir, filename):
        stem = os.path.splitext(filename)[0]
        return os.path.join(date_dir, f"{stem}.meta.json")

    def _read_cache_meta(self, date_dir, filename):
        path = self._meta_path(date_dir, filename)
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_cache_meta(self, date_dir, filename, target_date, row_count):
        meta = {
            "filename": filename,
            "date_int": int(target_date),
            "row_count": int(row_count),
            "session_state": self._session_state_for_date(
                target_date,
                date_dir=date_dir,
                filename=filename,
            ),
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
        }
        with open(self._meta_path(date_dir, filename), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    def _effective_session_state(self, date_dir, filename, target_date, meta=None):
        """Promote stale same-day intraday sidecars to closed once local close passes."""
        meta = meta or self._read_cache_meta(date_dir, filename)
        raw_state = str(meta.get("session_state", "") or "")
        inferred_state = self._session_state_for_date(
            target_date,
            date_dir=date_dir,
            filename=filename,
        )
        if raw_state == "closed":
            return "closed"
        if inferred_state == "closed":
            return "closed"
        if raw_state:
            return raw_state
        return inferred_state

    def _daily_file_complete(self, date_dir, filename, min_size, target_date):
        path = os.path.join(date_dir, filename)
        if not self._file_ready(path, min_size):
            return False
        if filename == "stocks.csv" and not UniverseConfig.USE_ALL_STOCKS_DAILY:
            try:
                sample = pd.read_csv(path, dtype=str, nrows=50)
                if "industry" not in sample.columns or sample["industry"].dropna().empty:
                    return False
            except Exception:
                return False

        required_state = self._session_state_for_date(
            target_date,
            date_dir=date_dir,
            filename=filename,
        )
        if required_state != "closed":
            return True

        meta = self._read_cache_meta(date_dir, filename)
        if meta:
            return self._effective_session_state(
                date_dir,
                filename,
                target_date,
                meta=meta,
            ) == "closed"

        # Legacy files have no sidecar. Historical dates are accepted; same-day
        # post-close files are refreshed once so intraday daily bars cannot stick.
        today = int(datetime.now().strftime("%Y%m%d"))
        return int(target_date) < today

    def _daily_files_complete(self, date_dir, target_date):
        required = {
            "stocks.csv": 10_000,
            "indices.csv": 500,
        }
        return all(
            self._daily_file_complete(date_dir, name, size, target_date)
            for name, size in required.items()
        )

    def get_daily_cache_status(self, target_date):
        """Return explicit daily-cache status for report watermarking and validation."""
        target_date = int(target_date)
        date_dir = self._get_date_dir(target_date, create=False)
        files = {}
        for filename in ("stocks.csv", "indices.csv"):
            path = os.path.join(date_dir, filename)
            meta = self._read_cache_meta(date_dir, filename)
            effective_state = self._effective_session_state(
                date_dir,
                filename,
                target_date,
                meta=meta,
            )
            files[filename] = {
                "exists": os.path.exists(path),
                "size": os.path.getsize(path) if os.path.exists(path) else 0,
                "meta": meta,
                "effective_session_state": effective_state,
                "complete": self._daily_file_complete(
                    date_dir,
                    filename,
                    10_000 if filename == "stocks.csv" else 500,
                    target_date,
                ),
            }

        states = [
            info.get("effective_session_state", "")
            for info in files.values()
            if info.get("effective_session_state")
        ]
        if not all(info["exists"] for info in files.values()):
            session_state = "missing"
        elif not all(info["complete"] for info in files.values()):
            session_state = "incomplete"
        elif "intraday" in states:
            session_state = "intraday"
        elif states and all(state == "closed" for state in states):
            session_state = "closed"
        else:
            session_state = self._session_state_for_date(target_date, date_dir=date_dir)

        fetched_at = max(
            [info["meta"].get("fetched_at", "") for info in files.values() if info["meta"].get("fetched_at")]
            or [""]
        )
        return {
            "date": target_date,
            "session_state": session_state,
            "fetched_at": fetched_at,
            "post_close_validation": session_state == "closed",
            "files": files,
        }

    def ensure_daily_cache_for_analysis(self, target_date):
        """Refresh daily cache before replay analysis when same-day data is stale."""
        date_dir = self._get_date_dir(target_date, create=False)
        if self._daily_files_complete(date_dir, target_date):
            return True

        print("  ⚠️ 复盘日线缓存不是收盘态，自动补同步当天日线...")
        return self.fetch_daily_all(target_date, with_minute=False, force=False)

    def ensure_daily_window_for_analysis(self, target_date, lookback=6):
        """Ensure the full replay window has usable daily stocks and indices data."""
        target_date = int(target_date)
        window_days = self.get_analysis_window_days(target_date, lookback=lookback)
        if len(window_days) < lookback:
            print(f"❌ 复盘窗口不足：需要至少 {lookback} 个交易日")
            return False
        missing = []
        for d in window_days:
            date_dir = self._get_date_dir(d, create=False)
            if not self._daily_files_complete(date_dir, d):
                missing.append(d)

        if not missing:
            print(f"  ✓ 复盘窗口日线完整: {window_days}")
            return True

        print(f"  ⚠️ 复盘窗口日线缺失/非收盘态，自动补同步: {missing}")
        ok = True
        for d in missing:
            ok = self.fetch_daily_all(d, with_minute=False, force=False) and ok

        if not ok:
            print("❌ 复盘窗口日线补同步失败")
            return False

        still_missing = []
        for d in window_days:
            date_dir = self._get_date_dir(d, create=False)
            if not self._daily_files_complete(date_dir, d):
                still_missing.append(d)

        if still_missing:
            print(f"❌ 复盘窗口仍不完整: {still_missing}")
            return False

        print(f"  ✓ 复盘窗口日线已补齐: {window_days}")
        return True

    def get_local_daily_days(self):
        """Return locally cached dates with usable daily stock and index files."""
        if not os.path.isdir(self.base_path):
            return []
        days = []
        for name in os.listdir(self.base_path):
            if not str(name).isdigit() or len(str(name)) != 8:
                continue
            day = int(name)
            if self._daily_files_complete(self._get_date_dir(day, create=False), day):
                days.append(day)
        return sorted(set(days))

    @staticmethod
    def _slice_window_days(candidate_days, target_date, lookback):
        candidate_days = [int(day) for day in candidate_days]
        target_date = int(target_date)
        if target_date not in candidate_days:
            return []
        idx = candidate_days.index(target_date)
        if idx < lookback - 1:
            return []
        return candidate_days[idx - lookback + 1:idx + 1]

    def get_analysis_window_days(self, target_date, lookback=6):
        """Return a replay window, falling back to complete local historical caches."""
        target_date = int(target_date)
        local_days = self.get_local_daily_days()
        local_window = self._slice_window_days(local_days, target_date, lookback)
        if len(local_window) >= lookback:
            return local_window

        recent_days = self.get_valid_trading_days(lookback=max(lookback + 5, 10))
        remote_window = self._slice_window_days(recent_days, target_date, lookback)
        if len(remote_window) >= lookback:
            return remote_window

        if target_date not in local_days and target_date not in recent_days:
            print(f"❌ {target_date} 不在有效交易日或本地完整缓存中")
            return []
        return local_window or remote_window

    def _minute_files_complete(self, date_dir, minute_parts):
        for part in minute_parts:
            if UniverseConfig.MINUTE_INCLUDE_STOCK_POOL:
                if not self._file_ready(os.path.join(date_dir, f"stocks_{part}.csv"), 1_000):
                    return False
            if UniverseConfig.MINUTE_INCLUDE_ETFS or UniverseConfig.MINUTE_INCLUDE_MAIN_INDICES:
                if not self._file_ready(os.path.join(date_dir, f"indices_{part}.csv"), 500):
                    return False
        return True

    def _normalize_to_df(self, data):
        if data is None: 
            return pd.DataFrame()
        if isinstance(data, pd.DataFrame): 
            return data
        if isinstance(data, dict):
            if not data: 
                return pd.DataFrame()
            valid_dfs = [df for df in data.values() if df is not None and not df.empty]
            if not valid_dfs: 
                return pd.DataFrame()
            return pd.concat(valid_dfs, ignore_index=True)
        return pd.DataFrame()

    def get_valid_trading_days(self, lookback=10, force_refresh=False):
        """
        获取有效交易日
        
        优化：优先从本地缓存读取，避免每次都调用API
        """
        # 1. 检查内存缓存
        if self._valid_days_cache is not None and len(self._valid_days_cache) >= lookback and not force_refresh:
            return self._valid_days_cache
        
        # 2. 检查本地文件缓存
        cache_file = os.path.join(self.base_path, "_trading_days_cache.txt")
        if os.path.exists(cache_file) and not force_refresh:
            try:
                with open(cache_file, 'r') as f:
                    lines = f.readlines()
                    if len(lines) >= 2:
                        cache_date = int(lines[0].strip())
                        # 缓存有效期：当天有效
                        today = int(pd.Timestamp.now().strftime('%Y%m%d'))
                        if cache_date == today:
                            cached_days = [int(d.strip()) for d in lines[1:] if d.strip()]
                            if len(cached_days) >= lookback:
                                self._valid_days_cache = cached_days
                                print(f"  ✓ 交易日缓存: {cached_days[-5:]} (从本地加载)")
                                return cached_days
                            print(f"  ⚠️ 交易日缓存仅 {len(cached_days)} 天，不足 {lookback} 天，自动刷新")
            except:
                pass
        
        # 3. 调用API验证
        print(">>> 验证最近交易日...")
        valid = CalendarHelper.filter_valid_trading_days(
            self.calendar, self.ad_market, check_count=lookback+5
        )
        self._valid_days_cache = valid
        print(f"  ✓ 最近交易日: {valid[-5:]}")
        
        # 4. 保存到本地缓存
        try:
            today = int(pd.Timestamp.now().strftime('%Y%m%d'))
            with open(cache_file, 'w') as f:
                f.write(f"{today}\n")
                for d in valid:
                    f.write(f"{d}\n")
        except:
            pass
        
        return valid

    def get_stock_list(self):
        """获取A股列表"""
        return self.ad_base.get_code_list(security_type='EXTRA_STOCK_A')

    def _normalize_code(self, code):
        code = str(code).strip()
        if not code or code.lower() == "nan":
            return ""
        if "." in code:
            return code.upper()
        if code.startswith(("6", "9")):
            return f"{code}.SH"
        if code.startswith(("0", "2", "3")):
            return f"{code}.SZ"
        if code.startswith(("4", "8")):
            return f"{code}.BJ"
        return code.upper()

    def _load_code_pool(self, path):
        if not path or not os.path.exists(path):
            return []
        try:
            try:
                df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
            except UnicodeDecodeError:
                df = pd.read_csv(path, dtype=str, encoding="gb18030")
            if df.empty:
                return []
            code_col = "code" if "code" in df.columns else df.columns[0]
            codes = [self._normalize_code(x) for x in df[code_col].dropna().tolist()]
            return sorted({x for x in codes if x})
        except Exception as e:
            print(f"  ⚠️ 股票池读取失败: {path} | {e}")
            return []

    def get_stock_pool_group_map(self):
        """Return code -> group mapping from the configured stock pool."""
        path = UniverseConfig.STOCK_POOL_PATH
        if not path or not os.path.exists(path):
            return {}
        try:
            try:
                df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
            except UnicodeDecodeError:
                df = pd.read_csv(path, dtype=str, encoding="gb18030")
            if df.empty or "group" not in df.columns:
                return {}
            code_col = "code" if "code" in df.columns else df.columns[0]
            df["code_norm"] = df[code_col].map(self._normalize_code)
            df = df[df["code_norm"].notna() & (df["code_norm"] != "")]
            return df.set_index("code_norm")["group"].fillna("其他").to_dict()
        except Exception as e:
            print(f"  ⚠️ 股票池分组读取失败: {path} | {e}")
            return {}

    def get_stock_universe(self):
        """Return configured stock universe, falling back to all stocks."""
        all_stocks = self.get_stock_list()
        if UniverseConfig.USE_ALL_STOCKS_DAILY:
            return all_stocks

        pool = self._load_code_pool(UniverseConfig.STOCK_POOL_PATH)
        if not pool:
            print("  ⚠️ 股票池为空，回退到全市场股票列表")
            return all_stocks

        all_set = set(all_stocks)
        selected = [code for code in pool if code in all_set]
        missing = [code for code in pool if code not in all_set]
        if missing:
            suffix = "..." if len(missing) > 10 else ""
            print(f"  ⚠️ 股票池无效代码: {missing[:10]}{suffix}")
        if not selected:
            print("  ⚠️ 股票池没有有效A股代码，回退到全市场股票列表")
            return all_stocks
        return selected

    def get_minute_stock_universe(self):
        if UniverseConfig.MINUTE_INCLUDE_STOCK_POOL:
            return self.get_stock_universe()
        return []

    def get_index_minute_universe(self):
        codes = []
        if UniverseConfig.MINUTE_INCLUDE_ETFS:
            codes.extend(MarketConfig.THEME_ETFS.keys())
        if UniverseConfig.MINUTE_INCLUDE_MAIN_INDICES:
            codes.extend(MarketConfig.MAIN_INDICES.keys())
        return sorted(set(codes))

    # ================= 映射表 =================

    def get_industry_codes(self):
        """获取行业指数代码"""
        if self._industry_code_cache is not None:
            return self._industry_code_cache
        try:
            raw = self.ad_info.get_industry_base_info(is_local=False)
            df = self._normalize_to_df(raw)
            if not df.empty and 'INDEX_CODE' in df.columns:
                self._industry_code_cache = df['INDEX_CODE'].unique().tolist()
                return self._industry_code_cache
        except Exception as e:
            print(f"⚠️ 获取行业指数代码失败: {e}")
        return []

    def get_industry_map(self):
        """获取股票->行业映射"""
        if self._industry_cache is not None:
            return self._industry_cache

        print(">>> 构建行业映射...")
        stock_to_ind = {}
        
        try:
            raw_ind_base = self.ad_info.get_industry_base_info(is_local=False)
            ind_base = self._normalize_to_df(raw_ind_base)
            
            if not ind_base.empty:
                target_levels = ind_base[ind_base['LEVEL_TYPE'].isin([1, 2])]
                ind_code_name_map = {}
                for _, row in target_levels.iterrows():
                    name = row.get('LEVEL2_NAME') if pd.notna(row.get('LEVEL2_NAME')) else row['LEVEL1_NAME']
                    ind_code_name_map[row['INDEX_CODE']] = name
                
                const_dict = self.ad_info.get_industry_constituent(list(ind_code_name_map.keys()), is_local=False)
                
                if const_dict:
                    for ind_code, df in const_dict.items():
                        if df is None or df.empty: 
                            continue
                        ind_name = ind_code_name_map.get(ind_code)
                        if not ind_name: 
                            continue
                        for stock in df['CON_CODE'].unique():
                            stock_to_ind[stock] = ind_name
        except Exception as e:
            print(f"⚠️ 行业映射构建异常: {e}")

        # 加载自定义概念
        if os.path.exists(DBConfig.CUSTOM_CONCEPT_PATH):
            try:
                try:
                    custom_df = pd.read_csv(DBConfig.CUSTOM_CONCEPT_PATH, dtype={'code': str, 'concept': str}, encoding='utf-8')
                except UnicodeDecodeError:
                    custom_df = pd.read_csv(DBConfig.CUSTOM_CONCEPT_PATH, dtype={'code': str, 'concept': str}, encoding='gb18030')
                for _, row in custom_df.iterrows():
                    if pd.notna(row['code']) and pd.notna(row['concept']):
                        stock_to_ind[row['code']] = row['concept']
                print(f"  ✓ 自定义概念: {len(custom_df)} 条")
            except:
                pass

        self._industry_cache = stock_to_ind
        print(f"  ✓ 行业映射: {len(stock_to_ind)} 条")
        return stock_to_ind

    def get_name_map(self, all_stocks=None):
        """获取股票名称映射"""
        if self._name_map_cache is not None:
            return self._name_map_cache
        
        if all_stocks is None:
            all_stocks = self.get_stock_list()
            
        try:
            base_info = self._normalize_to_df(self.ad_info.get_stock_basic(all_stocks))
            code_col = 'MARKET_CODE' if 'MARKET_CODE' in base_info.columns else 'code'
            self._name_map_cache = base_info.set_index(code_col)['SECURITY_NAME'].to_dict()
        except:
            self._name_map_cache = {}
        return self._name_map_cache

    # ================= 数据获取：日线 =================

    def _fetch_batch_kline(self, batch_codes, target_date, period, ind_map=None):
        try:
            k_res = self.ad_market.query_kline(batch_codes, target_date, target_date, period)
            rows = []
            if k_res:
                for code, df in k_res.items():
                    if df is None or df.empty: 
                        continue
                    row = df.iloc[-1].to_dict()
                    row['code'] = code
                    if ind_map:
                        row['industry'] = ind_map.get(code, '其他')
                    rows.append(row)
            return rows
        except:
            return []

    def _run_batch_task(self, task_func, all_codes, desc, batch_size=600, timeout_seconds=None):
        batch_list = [all_codes[i:i + batch_size] for i in range(0, len(all_codes), batch_size)]
        all_rows = []
        timeout_seconds = timeout_seconds or getattr(DBConfig, "BATCH_TASK_TIMEOUT_SECONDS", 180)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(task_func, b): b for b in batch_list}
            pending = set(futures)
            progress = tqdm(total=len(batch_list), desc=desc)
            last_done = time.time()
            while pending:
                done, pending = wait(pending, timeout=5, return_when=FIRST_COMPLETED)
                if not done:
                    if time.time() - last_done > timeout_seconds:
                        print(f"  ⚠️ {desc} 超过 {timeout_seconds}s 无完成批次，取消剩余 {len(pending)} 批")
                        for future in pending:
                            future.cancel()
                        break
                    continue
                last_done = time.time()
                for future in done:
                    progress.update(1)
                    try:
                        result = future.result()
                        if result:
                            all_rows.extend(result)
                    except:
                        pass
            progress.close()
            for future in pending:
                future.cancel()
        return all_rows

    def fetch_stocks_daily(self, target_date, all_codes, ind_map, name_map, date_dir, force=False):
        """获取个股日线"""
        save_path = os.path.join(date_dir, "stocks.csv")
        if self._daily_file_complete(date_dir, "stocks.csv", 10_000, target_date) and not force:
            print(f"  ✓ stocks.csv 已存在")
            return
        
        rows = self._run_batch_task(
            lambda b: self._fetch_batch_kline(b, target_date, ad.constant.Period.day.value, ind_map),
            all_codes, f"[{target_date}] 个股日线"
        )
        
        if rows:
            df = pd.DataFrame(rows)
            df['name'] = df['code'].map(name_map).fillna(df['code'])
            
            # 补充涨跌停价和昨收价
            try:
                raw_status = self.ad_info.get_history_stock_status(
                    all_codes, begin_date=target_date, end_date=target_date, is_local=False
                )
                status_df = self._normalize_to_df(raw_status)
                if not status_df.empty:
                    # 重命名列：包含pre_close（昨收价）
                    rename = {
                        'MARKET_CODE': 'code', 
                        'HIGH_LIMITED': 'high_limit', 
                        'LOW_LIMITED': 'low_limit',
                        'PRE_CLOSE': 'pre_close'  # 添加昨收价
                    }
                    status_df = status_df.rename(columns=rename)
                    cols = [c for c in ['code', 'high_limit', 'low_limit', 'pre_close'] if c in status_df.columns]
                    if cols:
                        df = pd.merge(df, status_df[cols], on='code', how='left')
                        print(f"    ✓ 补充昨收价: {'pre_close' in df.columns}")
            except Exception as e:
                print(f"    ⚠️ 补充证券信息失败: {e}")
            
            # ⚠️ 注意：不使用get_code_info()获取pre_close
            # 因为get_code_info()返回的是"当前实时昨收价"而非历史日期的昨收价
            # 对于历史数据会导致错误（所有历史日期的pre_close都变成最新的值）
            # 
            # 正确的做法：在calc_basic_indicators中使用shift(1)计算
            # 或在load_stocks加载多天数据后，用前一天close作为当天pre_close
            if 'pre_close' not in df.columns or df['pre_close'].isna().all():
                print(f"    ⚠️ 无昨收价数据，将在数据处理阶段通过shift计算")
            
            df.to_csv(save_path, index=False, encoding='utf-8-sig')
            self._write_cache_meta(date_dir, "stocks.csv", target_date, len(df))
            print(f"  ✓ 个股日线: {len(df)} 条")

    def fetch_indices_daily(self, target_date, date_dir, force=False):
        """获取指数/ETF日线"""
        save_path = os.path.join(date_dir, "indices.csv")
        if self._daily_file_complete(date_dir, "indices.csv", 500, target_date) and not force:
            print(f"  ✓ indices.csv 已存在")
            return
        
        target_codes = list(set(list(MarketConfig.MAIN_INDICES.keys()) + list(MarketConfig.THEME_ETFS.keys())))
        
        # 获取2天的数据，用T-1的close作为T的pre_close
        rows = self._fetch_indices_with_preclose(target_codes, target_date)
        
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(save_path, index=False, encoding='utf-8-sig')
            self._write_cache_meta(date_dir, "indices.csv", target_date, len(df))
            print(f"  ✓ 指数/ETF日线: {len(rows)} 条")
    
    def _fetch_indices_with_preclose(self, target_codes, target_date):
        """
        获取指数/ETF日线，正确计算pre_close
        
        方法：获取2天的K线数据，用前一天的close作为当天的pre_close
        """
        try:
            # 获取最近5个交易日，确保能找到T-1
            valid_days = self.get_valid_trading_days(lookback=10)
            if not valid_days:
                return []

            previous_days = [day for day in valid_days if int(day) < int(target_date)]
            if not previous_days:
                # 没有前一天数据，只能用当天
                begin_date = target_date
            else:
                # Explicit date sync may run before the trading-day cache has
                # learned about today. The latest known preceding session is
                # still sufficient to derive today's pre-close.
                begin_date = previous_days[-1]
            
            # 获取2天的K线
            k_res = self.ad_market.query_kline(
                target_codes, begin_date, target_date,
                ad.constant.Period.day.value
            )
            
            if not k_res:
                return []
            
            rows = []
            for code, df in k_res.items():
                if df is None or df.empty:
                    continue
                
                # 转换日期格式用于比较
                if 'kline_time' in df.columns:
                    df['date_int'] = pd.to_datetime(df['kline_time']).dt.strftime('%Y%m%d').astype(int)
                    
                    # 获取目标日期的数据
                    today_data = df[df['date_int'] == target_date]
                    if today_data.empty:
                        continue
                    
                    row = today_data.iloc[0].to_dict()
                    row['code'] = code
                    
                    # 获取前一天的close作为pre_close
                    yesterday_data = df[df['date_int'] == begin_date]
                    if not yesterday_data.empty and begin_date != target_date:
                        row['pre_close'] = yesterday_data.iloc[0].get('close', row.get('open', 0))
                    else:
                        # 没有前一天数据，用当天open作为pre_close（近似）
                        row['pre_close'] = row.get('open', 0)
                    
                    # 移除临时字段
                    row.pop('date_int', None)
                    rows.append(row)
            
            return rows
            
        except Exception as e:
            print(f"    ⚠️ 获取指数/ETF失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def fetch_industry_daily(self, target_date, industry_codes, date_dir, force=False):
        """获取行业指数日行情"""
        save_path = os.path.join(date_dir, "industry_daily.csv")
        if self._file_ready(save_path, 5_000) and not force:
            print(f"  ✓ industry_daily.csv 已存在")
            return
        
        print(f"  > 获取 {len(industry_codes)} 个行业指数...")
        try:
            industry_daily = self.ad_info.get_industry_daily(
                industry_codes, is_local=False, 
                begin_date=target_date, end_date=target_date
            )
            
            if industry_daily:
                rows = []
                for code, df in industry_daily.items():
                    if df is not None and not df.empty:
                        row = df.iloc[-1].to_dict()
                        row['code'] = code
                        rows.append(row)
                if rows:
                    pd.DataFrame(rows).to_csv(save_path, index=False, encoding='utf-8-sig')
                    print(f"  ✓ 行业指数: {len(rows)} 条")
        except Exception as e:
            print(f"⚠️ 行业指数获取失败: {e}")

    # ================= 数据获取：分钟K线（竞价用） =================

    def _auction_cache_ready(self, save_path, exact_only=False):
        """Return whether a persisted auction cache is suitable for reuse."""
        if not self._file_ready(save_path, 64):
            return False
        meta_path = os.path.splitext(save_path)[0] + ".meta.json"
        if not os.path.exists(meta_path):
            return not exact_only
        try:
            with open(meta_path, "r", encoding="utf-8") as fh:
                meta = json.load(fh)
        except Exception:
            return not exact_only
        return bool(meta.get("auction_amount_exact")) if exact_only else True

    @staticmethod
    def _write_auction_cache(df, save_path, source, exact, asof):
        """Persist auction data with a source label so approximate data is visible."""
        work = df.copy()
        work["auction_source"] = source
        work["auction_amount_exact"] = bool(exact)
        work["auction_asof"] = asof
        work.to_csv(save_path, index=False, encoding="utf-8-sig")
        meta = {
            "filename": os.path.basename(save_path),
            "auction_source": source,
            "auction_amount_exact": bool(exact),
            "auction_asof": asof,
            "row_count": int(len(work)),
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
        }
        with open(os.path.splitext(save_path)[0] + ".meta.json", "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=2)

    def _fetch_batch_minute_kline(self, batch_codes, target_date, target_time):
        """
        批量获取分钟K线指定时间
        
        注意：
        - 集合竞价(9:25)可能没有独立K线，数据会包含在9:30的第一根K线中
        - 如果target_time=925且无数据，会自动fallback到930
        """
        try:
            k_res = self.ad_market.query_kline(
                batch_codes, target_date, target_date, 
                ad.constant.Period.min1.value
            )
            rows = []
            if k_res:
                for code, df in k_res.items():
                    if df is None or df.empty:
                        continue
                    if 'kline_time' in df.columns:
                        df['time_int'] = df['kline_time'].astype(str).str[11:16].str.replace(':', '').astype(int)
                        
                        # 尝试获取目标时间的数据
                        target_rows = df[df['time_int'] == target_time]
                        
                        # 如果是925且无数据，fallback到930（集合竞价数据在第一根K线）
                        if target_rows.empty and target_time == 925:
                            target_rows = df[df['time_int'] == 930]
                        
                        # 如果是1500且无数据，尝试1459（最后一根分钟K线）
                        if target_rows.empty and target_time == 1500:
                            target_rows = df[df['time_int'] == 1459]
                        
                        if not target_rows.empty:
                            row = target_rows.iloc[0].to_dict()
                            row['code'] = code
                            row['last'] = row.get('close', 0)
                            del row['time_int']
                            rows.append(row)
            return rows
        except:
            return []
    
    def _fetch_batch_snapshot(self, batch_codes, target_date, target_hhmmss, window_seconds=5):
        """
        批量获取历史快照数据
        
        参数:
            batch_codes: 代码列表
            target_date: 日期 (YYYYMMDD)
            target_time_ms: 时间戳，格式为HHMMSS000（9位，含毫秒）
                           例如: 92500000 表示 9:25:00.000
        
        返回:
            list: 快照数据行
        """
        try:
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

            snapshot_res = self.ad_market.query_snapshot(
                batch_codes,
                begin_date=target_date,
                end_date=target_date,
                begin_time=_encode(begin_total) * 1000,
                end_time=_encode(end_total) * 1000
            )
            rows = snapshot_rows_near_time(
                snapshot_res,
                target_hhmmss=int(target_hhmmss),
                floor_hhmmss=_encode(begin_total),
                ceil_hhmmss=_encode(end_total),
            )
            for row in rows:
                # 快照数据中open就是开盘价（集合竞价结束价）
                row['auction_price'] = row.get('open', row.get('last', 0))
            return rows
        except Exception as e:
            # 静默失败，返回空列表
            return []

    def fetch_stocks_auction_snapshot(self, target_date, all_codes, date_dir):
        """
        使用快照接口获取竞价数据（9:25）
        
        优势：
        - 精确获取9:25时刻的数据
        - 包含open（开盘价）和pre_close（昨收价）
        - 比分钟K线更快、更准确
        """
        save_path = os.path.join(date_dir, "stocks_auction.csv")
        if self._auction_cache_ready(save_path, exact_only=True):
            print(f"  ✓ stocks_auction.csv 已存在")
            return True
        
        # 9:25:00.000 的时间戳
        auction_time = 92500
        
        rows = self._run_batch_task(
            lambda b: self._fetch_batch_snapshot(b, target_date, auction_time),
            all_codes, f"[{target_date}] 个股竞价快照", batch_size=300
        )
        
        if rows:
            df = pd.DataFrame(rows)
            self._write_auction_cache(
                df, save_path, source="historical_snapshot_925",
                exact=True, asof="09:25:00",
            )
            print(f"  ✓ 个股竞价快照: {len(rows)} 条")
            return True
        else:
            print(f"  ⚠️ 快照数据为空，尝试分钟K线...")
            return False

    def rebuild_intraday_confirmation_from_snapshot(
        self,
        target_date,
        force=False,
        stock_codes=None,
        etf_codes=None,
        index_codes=None,
        mode="minimal",
        data_kind="min1",
        warn_after_sec=None,
        progress_path=None,
        stage="all",
        begin_hhmm=930,
        end_hhmm=935,
        batch_size=120,
        max_stocks=0,
        only_codes=None,
        skip_existing=False,
        isolated_query=False,
    ):
        """Backfill 09:25-09:35 intraday confirmation files from historical snapshots."""
        try:
            from core.intraday_monitor import IntradayMonitor

            monitor = IntradayMonitor(base_path=self.base_path)
            return monitor.rebuild_opening_session_from_snapshot(
                date_int=int(target_date),
                start_hhmm=925,
                end_hhmm=935,
                force=force,
                stock_codes=stock_codes,
                etf_codes=etf_codes,
                index_codes=index_codes,
                mode=mode,
                data_kind=data_kind,
                warn_after_sec=warn_after_sec,
                progress_path=progress_path,
                stage=stage,
                begin_hhmm=begin_hhmm,
                end_hhmm_window=end_hhmm,
                batch_size=batch_size,
                max_stocks=max_stocks,
                only_codes=only_codes,
                skip_existing=skip_existing,
                isolated_query=isolated_query,
            )
        except Exception as exc:
            print(f"  ⚠️ snapshot 回补 09:35 确认失败: {exc}")
            return {"rebuilt": False, "reason": str(exc)}

    def fetch_stocks_minute(self, target_date, all_codes, time_point, suffix, date_dir, force=False):
        """获取个股分钟数据"""
        save_path = os.path.join(date_dir, f"stocks_{suffix}.csv")
        if suffix == "auction" and self._auction_cache_ready(save_path, exact_only=True):
            print(f"  ✓ stocks_{suffix}.csv 已存在精确竞价缓存，保留不覆盖")
            return True
        if self._file_ready(save_path, 1_000) and not force:
            print(f"  ✓ stocks_{suffix}.csv 已存在")
            return True
        
        rows = self._run_batch_task(
            lambda b: self._fetch_batch_minute_kline(b, target_date, time_point),
            all_codes, f"[{target_date}] 个股{suffix}", batch_size=300
        )
        
        if rows:
            df = pd.DataFrame(rows)
            if suffix == "auction":
                self._write_auction_cache(
                    df, save_path, source="minute_930_includes_first_minute",
                    exact=False, asof="09:30",
                )
            else:
                df.to_csv(save_path, index=False, encoding='utf-8-sig')
            print(f"  ✓ 个股{suffix}: {len(rows)} 条")
            return True
        print(f"  ⚠️ 个股{suffix}: 无可用分钟数据")
        return False

    def fetch_indices_minute(self, target_date, codes, time_point, suffix, date_dir, force=False):
        """Fetch minute data for configured indices and ETFs."""
        save_path = os.path.join(date_dir, f"indices_{suffix}.csv")
        if suffix == "auction" and self._auction_cache_ready(save_path, exact_only=True):
            print(f"  ✓ indices_{suffix}.csv 已存在精确竞价缓存，保留不覆盖")
            return True
        if self._file_ready(save_path, 500) and not force:
            print(f"  ✓ indices_{suffix}.csv 已存在")
            return True
        if not codes:
            return True

        rows = self._run_batch_task(
            lambda b: self._fetch_batch_minute_kline(b, target_date, time_point),
            codes, f"[{target_date}] 指数/ETF{suffix}", batch_size=300
        )

        if rows:
            df = pd.DataFrame(rows)
            if suffix == "auction":
                self._write_auction_cache(
                    df, save_path, source="minute_930_includes_first_minute",
                    exact=False, asof="09:30",
                )
            else:
                df.to_csv(save_path, index=False, encoding='utf-8-sig')
            print(f"  ✓ 指数/ETF{suffix}: {len(rows)} 条")
            return True
        print(f"  ⚠️ 指数/ETF{suffix}: 无可用分钟数据")
        return False

    # ================= 主流程 =================

    def fetch_daily_all(self, target_date, with_minute=False, minute_parts=None, force=False):
        """同步指定日期数据"""
        date_dir = self._get_date_dir(target_date)
        print(f"\n>>> 同步 [{target_date}] ...")
        t_start = time.time()

        if minute_parts is None:
            minute_parts = ["auction", "noon", "close"] if with_minute else []
        minute_parts = list(minute_parts)

        daily_complete = self._daily_files_complete(date_dir, target_date)
        minute_complete = (not minute_parts) or self._minute_files_complete(date_dir, minute_parts)
        if daily_complete and minute_complete and not force:
            print(f"  ✓ 本地数据完整，跳过同步")
            print(f"\n[{target_date}] 完成! 耗时: {time.time()-t_start:.1f}s")
            return True
        
        all_stocks = self.get_stock_universe()
        if not all_stocks:
            print("❌ 获取股票列表失败")
            return False
        
        industry_codes = []
        ind_map = {}
        name_map = {}
        if not daily_complete or force:
            if UniverseConfig.SYNC_INDUSTRY_DAILY:
                industry_codes = self.get_industry_codes()
                ind_map = self.get_industry_map()
            else:
                ind_map = self.get_stock_pool_group_map()
            name_map = self.get_name_map(all_stocks)
            print(f"  个股: {len(all_stocks)}, 行业: {len(industry_codes)}")
        else:
            print(f"  个股: {len(all_stocks)}，日线已完整，仅检查分钟数据")

        # 日线数据
        if not daily_complete or force:
            print("\n--- [日线] ---")
            self.fetch_stocks_daily(target_date, all_stocks, ind_map, name_map, date_dir, force=force)
            self.fetch_indices_daily(target_date, date_dir, force=force)
            if UniverseConfig.SYNC_INDUSTRY_DAILY:
                self.fetch_industry_daily(target_date, industry_codes, date_dir, force=force)
            else:
                print("  ✓ 行业指数日线跳过（由ETF池表征板块资金）")
        else:
            print("  ✓ 日线数据完整，跳过日线")
        
        # 分钟数据（竞价分析用）
        if minute_parts:
            print("\n--- [分钟数据] ---")
            minute_time_map = {
                "auction": MarketConfig.TIME_AUCTION,
                "noon": MarketConfig.TIME_NOON,
                "close": MarketConfig.TIME_CLOSE,
            }
            for part in minute_parts:
                if part not in minute_time_map:
                    print(f"  ⚠️ 未知分钟类型: {part}")
                    continue
                minute_stock_codes = self.get_minute_stock_universe()
                minute_index_codes = self.get_index_minute_universe()
                if minute_stock_codes:
                    self.fetch_stocks_minute(
                        target_date, minute_stock_codes, minute_time_map[part], part, date_dir, force=force
                    )
                if minute_index_codes:
                    self.fetch_indices_minute(
                        target_date, minute_index_codes, minute_time_map[part], part, date_dir, force=force
                    )

        print(f"\n[{target_date}] 完成! 耗时: {time.time()-t_start:.1f}s")
        return True

    def sync_recent_days(self, lookback=5, latest_with_minute=False, minute_parts=None, force=False):
        """同步最近N个交易日"""
        valid_days = self.get_valid_trading_days(lookback=lookback)
        sync_days = valid_days[-lookback:]
        print(f"[Sync] 计划: {sync_days}")
        
        for d in sync_days:
            is_latest = (d == sync_days[-1])
            self.fetch_daily_all(
                d,
                with_minute=(is_latest and latest_with_minute),
                minute_parts=(minute_parts if is_latest and latest_with_minute else []),
                force=force,
            )
        
        return sync_days
    
    def sync_realtime(self, target_date=None, use_subscribe=False):
        """
        轻量级实时同步 - 专为9:25盘前决策优化
        
        数据获取策略（按优先级）：
        1. use_subscribe=True: 9:25实时订阅快照，纯竞价成交额
        2. 9:25历史快照，纯竞价成交额
        3. 9:30分钟K线第一根，包含竞价和第一分钟成交额，仅降级使用
        4. 日K线估算，仅降级使用
        
        参数:
            target_date: 目标日期，默认为最新交易日
            use_subscribe: 是否使用实时订阅模式
        
        返回:
            int: 同步的目标日期
        """
        print(f"\n{'='*60}")
        print(f"  ⚡ 实时轻量同步（盘前优化版）")
        print(f"{'='*60}")
        
        t_start = time.time()
        
        # 获取最新交易日
        valid_days = self.get_valid_trading_days(lookback=5)
        if not valid_days:
            print("❌ 无有效交易日")
            return None
        
        if target_date is None:
            now = datetime.now()
            today = int(now.strftime("%Y%m%d"))
            target_date = today if now.weekday() < 5 and (now.hour, now.minute) >= (9, 25) else valid_days[-1]
        
        print(f">>> 目标日期: {target_date}")
        
        # 检查历史数据是否存在
        history_days = [d for d in valid_days if d < target_date][-4:]  # T-1到T-4
        missing_history = []
        for d in history_days:
            stocks_file = os.path.join(self._get_date_dir(d, create=False), "stocks.csv")
            if not os.path.exists(stocks_file):
                missing_history.append(d)
        
        if missing_history:
            print(f"⚠️ 缺少历史数据: {missing_history}")
            print(f"   请先执行: python main.py sync 5")
            return None
        
        print(f"  ✓ 历史数据完整: {history_days}")
        
        # 同步当天数据
        date_dir = self._get_date_dir(target_date)
        
        all_stocks = self.get_stock_universe()
        if not all_stocks:
            print("❌ 获取股票列表失败")
            return None
        
        ind_map = self.get_industry_map() if UniverseConfig.SYNC_INDUSTRY_DAILY else {}
        
        print(f"  个股: {len(all_stocks)}, 行业: {len(ind_map)}")
        
        # ============ 竞价数据获取 ============
        auction_path = os.path.join(date_dir, "stocks_auction.csv")
        
        # 判断当前时间，选择最佳数据源
        now = datetime.now()
        is_auction_time = (now.hour == 9 and 25 <= now.minute < 30)  # 9:25-9:30
        
        if use_subscribe or is_auction_time:
            # 方案1: 实时订阅模式（9:25-9:30最佳，获取纯竞价成交额）
            print("\n>>> 同步竞价数据（实时订阅模式）...")
            if is_auction_time:
                print("  ⏰ 当前在竞价时段(9:25-9:30)，使用实时订阅获取纯竞价数据")
            success = self._fetch_auction_subscribe(all_stocks, auction_path)
        else:
            success = False

        # 方案2: 精确历史快照。9:25刚结束时可能尚未入库，因此放在订阅之后。
        if not success:
            print("\n>>> 同步竞价数据（9:25历史快照模式）...")
            success = self.fetch_stocks_auction_snapshot(target_date, all_stocks, date_dir)

        # 方案3: 9:30分钟K线降级，amount包含竞价和第一分钟。
        if not success and (now.hour, now.minute) >= (9, 30):
            print("\n>>> 降级同步竞价数据（9:30分钟K线，包含第一分钟成交额）...")
            success = self._fetch_auction_from_minute(target_date, all_stocks, auction_path)
        
        # 方案4: 回退到日K线+估算
        if not success:
            print(">>> 回退到日K线模式（估算竞价额）...")
            success = self._fetch_auction_from_daily_estimated(target_date, all_stocks, auction_path)
        
        # 同步指数/ETF日线
        print("\n>>> 同步指数/ETF...")
        self.fetch_indices_daily(target_date, date_dir)
        
        print(f"\n✅ 实时同步完成! 耗时: {time.time()-t_start:.1f}s")
        return target_date
    
    def _fetch_auction_from_minute(self, target_date, code_list, save_path):
        """
        从分钟K线获取竞价降级数据
        
        原理：根据开发手册，"开盘集合竞价数据的成交量包含在当日第一根K线"
        第一根分钟K线(9:30)的amount = 竞价成交额 + 第一分钟成交额
        
        注意：该 amount 不是纯竞价成交额，不能用于严格的 9:25 决策。
        
        返回:
            bool: 是否成功
        """
        if self._auction_cache_ready(save_path):
            print(f"  ✓ stocks_auction.csv 已存在")
            return True
        
        try:
            # 1. 获取证券信息（pre_close）
            print(f"  >>> 获取证券信息（pre_close）...")
            t0 = time.time()
            code_info = self.ad_base.get_code_info(security_type='EXTRA_STOCK_A')
            
            if code_info is None or code_info.empty:
                print(f"  ⚠️ 获取证券信息失败")
                return False
            
            code_info = code_info.reset_index()
            code_info.columns = ['code'] + list(code_info.columns[1:])
            pre_close_map = code_info.set_index('code')['pre_close'].to_dict()
            print(f"  ✓ 证券信息: {len(pre_close_map)} 条, 耗时: {time.time()-t0:.1f}s")
            
            # 2. 获取分钟K线（第一根，包含竞价数据）
            print(f"  >>> 获取分钟K线（第一根）...")
            t0 = time.time()
            
            rows = self._run_batch_task(
                lambda b: self._fetch_batch_minute_first(b, target_date),
                code_list, f"分钟K线", batch_size=500
            )
            
            if not rows:
                print(f"  ⚠️ 分钟K线数据为空")
                return False
            
            print(f"  ✓ 分钟K线: {len(rows)} 条, 耗时: {time.time()-t0:.1f}s")
            
            # 3. 合并数据
            df = pd.DataFrame(rows)
            df['pre_close'] = df['code'].map(pre_close_map)
            
            # 过滤无效数据
            df = df[df['pre_close'].notna() & (df['pre_close'] > 0)]
            
            if df.empty:
                print(f"  ⚠️ 合并后数据为空")
                return False
            
            # 保存
            self._write_auction_cache(
                df, save_path, source="minute_930_includes_first_minute",
                exact=False, asof="09:30",
            )
            print(f"  ✓ 竞价数据: {len(df)} 条")
            return True
            
        except Exception as e:
            print(f"  ⚠️ 获取失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _fetch_batch_minute_first(self, batch_codes, target_date):
        """
        批量获取分钟K线的第一根（包含竞价数据）
        """
        try:
            k_res = self.ad_market.query_kline(
                batch_codes, target_date, target_date,
                ad.constant.Period.min1.value
            )
            rows = []
            if k_res:
                for code, df in k_res.items():
                    if df is None or df.empty:
                        continue
                    # 取第一根K线（9:30，包含竞价成交量）
                    row = df.iloc[0]
                    rows.append({
                        'code': code,
                        'open': row.get('open', 0),
                        'high': row.get('high', 0),
                        'low': row.get('low', 0),
                        'close': row.get('close', 0),
                        'volume': row.get('volume', 0),
                        'amount': row.get('amount', 0),  # 竞价+第一分钟成交额
                    })
            return rows
        except:
            return []
    
    def _fetch_auction_from_daily_estimated(self, target_date, code_list, save_path):
        """
        从日K线获取竞价数据（估算模式，备选方案）
        
        注意：日K线的amount是全天成交额，这里用3%估算竞价成交额
        仅作为备选方案，当分钟K线不可用时使用
        
        返回:
            bool: 是否成功
        """
        if self._auction_cache_ready(save_path):
            print(f"  ✓ stocks_auction.csv 已存在")
            return True
        
        try:
            # 1. 获取证券信息（pre_close）
            print(f"  >>> 获取证券信息（pre_close）...")
            t0 = time.time()
            code_info = self.ad_base.get_code_info(security_type='EXTRA_STOCK_A')
            
            if code_info is None or code_info.empty:
                print(f"  ⚠️ 获取证券信息失败")
                return False
            
            # 转换为字典
            code_info = code_info.reset_index()
            code_info.columns = ['code'] + list(code_info.columns[1:])
            pre_close_map = code_info.set_index('code')['pre_close'].to_dict()
            print(f"  ✓ 证券信息: {len(pre_close_map)} 条, 耗时: {time.time()-t0:.1f}s")
            
            # 2. 获取日K线（open）
            print(f"  >>> 获取日K线（open）...")
            t0 = time.time()
            
            rows = self._run_batch_task(
                lambda b: self._fetch_batch_daily_open(b, target_date),
                code_list, f"日K线open", batch_size=500
            )
            
            if not rows:
                print(f"  ⚠️ 日K线数据为空")
                return False
            
            print(f"  ✓ 日K线: {len(rows)} 条, 耗时: {time.time()-t0:.1f}s")
            
            # 3. 合并数据
            df = pd.DataFrame(rows)
            df['pre_close'] = df['code'].map(pre_close_map)
            
            # ⚠️ 关键修改：估算竞价成交额（日成交额的3%）
            df['amount'] = df['amount'] * 0.03
            print(f"  ⚠️ 使用估算模式: amount = 日成交额 × 3%")
            
            # 过滤无效数据
            df = df[df['pre_close'].notna() & (df['pre_close'] > 0)]
            
            if df.empty:
                print(f"  ⚠️ 合并后数据为空")
                return False
            
            # 保存
            self._write_auction_cache(
                df, save_path, source="daily_amount_estimated",
                exact=False, asof="daily",
            )
            print(f"  ✓ 竞价数据: {len(df)} 条")
            return True
            
        except Exception as e:
            print(f"  ⚠️ 获取失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _fetch_batch_daily_open(self, batch_codes, target_date):
        """
        批量获取日K线的open（开盘价=竞价价格）
        """
        try:
            k_res = self.ad_market.query_kline(
                batch_codes, target_date, target_date,
                ad.constant.Period.day.value
            )
            rows = []
            if k_res:
                for code, df in k_res.items():
                    if df is None or df.empty:
                        continue
                    row = df.iloc[0]
                    rows.append({
                        'code': code,
                        'open': row.get('open', 0),
                        'high': row.get('high', 0),
                        'low': row.get('low', 0),
                        'close': row.get('close', 0),
                        'volume': row.get('volume', 0),
                        'amount': row.get('amount', 0),
                    })
            return rows
        except:
            return []
    
    def _fetch_auction_subscribe(self, code_list, save_path):
        """
        使用实时订阅模式获取竞价数据
        
        返回:
            bool: 是否成功
        """
        if self._auction_cache_ready(save_path, exact_only=True):
            print(f"  ✓ stocks_auction.csv 已存在")
            return True
        
        try:
            from core.realtime_fetcher import RealtimeFetcher
            
            fetcher = RealtimeFetcher(timeout=60)
            df = fetcher.fetch_auction_snapshot(code_list)
            
            if df.empty:
                print(f"  ⚠️ 实时订阅无数据")
                return False
            
            self._write_auction_cache(
                df, save_path, source="subscription_925",
                exact=True, asof=datetime.now().isoformat(timespec="seconds"),
            )
            print(f"  ✓ 实时订阅获取: {len(df)} 条")
            return True
            
        except Exception as e:
            print(f"  ⚠️ 实时订阅失败: {e}")
            return False
    
    def sync_realtime_full(self, target_date=None):
        """
        完整实时同步 - 用于收盘后复盘
        
        同步所有数据：日线、竞价、午盘、收盘
        """
        print(f"\n{'='*60}")
        print(f"  📊 完整同步（收盘后复盘）")
        print(f"{'='*60}")
        
        t_start = time.time()
        
        valid_days = self.get_valid_trading_days(lookback=5)
        if not valid_days:
            print("❌ 无有效交易日")
            return None
        
        if target_date is None:
            target_date = valid_days[-1]
        
        print(f">>> 目标日期: {target_date}")
        
        # 完整同步
        self.fetch_daily_all(target_date, with_minute=True)
        
        print(f"\n✅ 完整同步完成! 耗时: {time.time()-t_start:.1f}s")
        return target_date

    # ================= 数据加载 =================

    def load_data(self, date_list, data_type="stocks"):
        """通用数据加载"""
        dfs = []
        filename = f"{data_type}.csv"
        for d in date_list:
            date_dir = self._get_date_dir(d, create=False)
            fpath = os.path.join(date_dir, filename)
            if os.path.exists(fpath):
                try:
                    df = pd.read_csv(fpath, dtype={'code': str, 'name': str})
                    df['date_int'] = d
                    dfs.append(df)
                except: 
                    continue
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    def load_stocks(self, date_list):
        return self.load_data(date_list, "stocks")
    
    def load_indices(self, date_list):
        return self.load_data(date_list, "indices")
    
    def load_industry(self, date_list):
        return self.load_data(date_list, "industry_daily")
    
    def load_auction(self, date_list):
        return self.load_data(date_list, "stocks_auction")
    
    def load_noon(self, date_list):
        return self.load_data(date_list, "stocks_noon")
    
    def load_close(self, date_list):
        return self.load_data(date_list, "stocks_close")
    
    # 兼容旧接口
    def load_window_data(self, date_list, data_type="stocks"):
        return self.load_data(date_list, data_type)
