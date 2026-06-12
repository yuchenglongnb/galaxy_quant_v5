# -*- coding: utf-8 -*-
"""
竞价分析器 v2.0 - 行业竞价分析核心逻辑

核心指标：
- CP (Crowding Pump): 拥挤诱多指数 - 捕捉高开诱多陷阱
- SA (Support Absorption): 承接反核指数 - 捕捉低开反转机会

指标说明：
- 竞价涨幅: (开盘价 - 昨收) / 昨收 * 100，反映集合竞价情绪
- 竞价额: 行业内所有个股开盘成交额之和
- 竞价占比: 竞价额 / 全天成交额，反映早盘资金活跃度
- 实体涨跌: (收盘价 - 开盘价) / 昨收，反映日内走势
- 5日位置: (收盘-5日最低) / (5日最高-5日最低)，反映相对位置
"""

import os

import pandas as pd
import numpy as np

from analyzers.base import BaseAnalyzer
from analyzers.factors import AuctionFactors, ScenarioIdentifier, CommentaryGenerator
from analyzers.signal_shortlist import SignalShortlistBuilder
from ai.feature_builder import IndexFeatureBuilder
from ai.local_interpreter import LocalIndexInterpreter
from ai.signal_feature_builder import SignalFeatureBuilder
from core.data_processor import DataProcessor
from config.settings import MarketConfig, AuctionConfig


class AuctionAnalyzer(BaseAnalyzer):
    """竞价分析器"""
    
    def analyze(self, target_date, realtime=False, **kwargs):
        """
        执行竞价分析 v2.0
        
        参数:
            target_date: 目标日期 (YYYYMMDD)
            realtime: 是否实时模式（9:25盘前决策，没有收盘数据）
            
        返回:
            dict: 包含指数监控、ETF分析、行业排行、信号汇总等
        """
        # 确保target_date是整数
        target_date = int(target_date)

        # Historical replay needs a complete T daily window. At 09:25 the
        # current daily bar does not exist yet, so realtime mode appends today
        # to the latest five completed local sessions.
        if realtime:
            completed_days = [day for day in self.dm.get_local_daily_days() if day < target_date]
            date_list = completed_days[-5:] + [target_date]
        else:
            date_list = self.dm.get_analysis_window_days(target_date, lookback=6)
        if len(date_list) < 5:
            print(f"⚠️ 需要至少5天数据来计算5日位置")
            return None
        
        # 获取最近3天日期
        T = int(date_list[-1])
        T_1 = int(date_list[-2])
        T_2 = int(date_list[-3])
        
        # ============ 核心优化：轻量同步模式 ============
        if realtime:
            # 实时模式：不加载今日stocks，从auction+历史数据构建
            df_stocks, df_today = self._load_realtime_data(date_list, target_date)
        else:
            # 复盘模式：加载完整日线数据
            df_stocks = self.dm.load_stocks(date_list)
            if df_stocks.empty:
                print(f"⚠️ 无法加载 {target_date} 个股数据")
                return None
            df_today = None  # 稍后从df_stocks提取
        
        # 加载指数数据（指数数据在盘前也会更新）
        df_indices = self.dm.load_indices(date_list)
        
        # 尝试加载分钟数据（竞价、午盘）
        df_auction = self.dm.load_auction([target_date])
        df_noon = self.dm.load_noon([target_date]) if not realtime else pd.DataFrame()
        
        # 计算指标（包括prev_close）
        if not df_stocks.empty:
            df_stocks = DataProcessor.calc_indicators(df_stocks)
            df_stocks = self._calc_position_5d(df_stocks)
        df_indices = DataProcessor.calc_indicators(df_indices)
        
        # 计算5日位置
        df_indices = self._calc_position_5d(df_indices)
        
        # 获取今日数据
        if df_today is None:
            df_today = df_stocks[df_stocks['date_int'] == target_date].copy()
        
        df_indices_today = df_indices[df_indices['date_int'] == target_date].copy()
        
        if df_today.empty and not realtime:
            print(f"⚠️ {target_date} 无有效个股数据")
            return None
        
        # 计算竞价涨幅（实时模式下_load_realtime_data已经计算，跳过）
        if not df_today.empty and not realtime:
            df_today = self._calc_auction_metrics(df_today, df_auction, df_noon)
        elif not df_today.empty and realtime and 'auction_pct' not in df_today.columns:
            # 实时模式但没有auction_pct，需要计算
            df_today = self._calc_auction_metrics(df_today, df_auction, df_noon)

        # Corporate actions and stale pre-close values can produce impossible
        # opening gaps. Preserve them for audit, but never feed them into CP/SA
        # stock ranking or industry aggregation.
        excluded_price_discontinuities = pd.DataFrame()
        if not df_today.empty:
            df_today = DataProcessor.mark_price_discontinuities(df_today)
            excluded_price_discontinuities = df_today[df_today['price_discontinuity']].copy()
            if not excluded_price_discontinuities.empty:
                unmatched = excluded_price_discontinuities[
                    excluded_price_discontinuities['price_discontinuity_reason'] == 'no_matched_auction_price'
                ].copy()
                gap_rows = excluded_price_discontinuities[
                    excluded_price_discontinuities['price_discontinuity_reason'] != 'no_matched_auction_price'
                ].copy()
                if not unmatched.empty:
                    unmatched_sample = ", ".join(
                        unmatched['name'].fillna(unmatched['code']).astype(str).head(8).tolist()
                    )
                    print(
                        f"  ⚠️ 未撮合/零价竞价快照 {len(unmatched)} 只"
                        + (f": {unmatched_sample}" if unmatched_sample else "")
                    )
                if not gap_rows.empty:
                    labels = [
                        f"{row.get('name', row.get('code', ''))}({self._to_float(row.get('auction_pct'), np.nan):+.2f}%)"
                        for _, row in gap_rows.iterrows()
                    ]
                    print(f"  ⚠️ 剔除价格断点 {len(labels)} 只: {', '.join(labels)}")
                    print("     原因: 疑似除权除息或昨收价失真，不参与个股/行业 CP、SA 计算")
                df_today = df_today[~df_today['price_discontinuity']].copy()
        
        # 计算市场OAR（上证量比作为基准）
        market_oar = self._get_market_oar(df_indices_today)
        
        # 获取T-1和T-2的数据用于趋势分析
        df_t1 = df_stocks[df_stocks['date_int'] == T_1].copy() if not df_stocks.empty and len(date_list) >= 2 else pd.DataFrame()
        df_t2 = df_stocks[df_stocks['date_int'] == T_2].copy() if not df_stocks.empty and len(date_list) >= 3 else pd.DataFrame()
        
        # 0. 四大指数监控
        indices_monitor = self._analyze_main_indices(df_indices, date_list, target_date)
        index_factor_result = self._analyze_index_factors(df_indices, date_list, target_date, market_oar, realtime=realtime)
        
        # 1. ETF竞价监控（含CP/SA）
        etf_result = self._analyze_etf_auction_v2(df_indices, date_list, target_date, market_oar, realtime=realtime)
        
        # 2. 行业竞价排行（含CP/SA）- 传入已计算auction_pct的df_today
        industry_result = self._calc_industry_auction_v2(df_today, df_t1, df_t2, market_oar, realtime=realtime)
        stock_factor_result = self._analyze_stock_factors(df_today, df_t1, df_t2, market_oar, realtime=realtime, top_k=None)
        
        # 3. 行业走势分析（仅复盘模式）
        reversals = self._find_reversal_industries(df_today) if not realtime else pd.DataFrame()
        
        # 4. 行业相关性分析（仅复盘模式）
        correlation = self._calc_industry_correlation(df_today) if not realtime else pd.DataFrame()
        
        # 5. 生成信号汇总
        signals = self._generate_signals(index_factor_result, etf_result, stock_factor_result, industry_result, market_oar, realtime=realtime)
        signal_confirmation_meta = self._enrich_signals_with_intraday_confirmation(signals, target_date)
        shortlist, market_regime = SignalShortlistBuilder.build(
            signals,
            index_df=index_factor_result,
            etf_df=etf_result,
        )
        confirmation_meta = self._apply_intraday_confirmation(shortlist, target_date)
        confirmation_meta["signal_enrichment"] = signal_confirmation_meta
        self._build_shortlist_commentary(shortlist, market_oar)
        
        return {
            'date': target_date,
            'market_oar': market_oar,
            'realtime': realtime,
            'data_status': self.dm.get_daily_cache_status(target_date),
            'indices_monitor': indices_monitor,
            'index_factors': index_factor_result,
            'etf_auction': etf_result,
            'stock_factors': stock_factor_result,
            'excluded_price_discontinuities': excluded_price_discontinuities,
            'industry_report': industry_result,
            'reversals': reversals,
            'correlation': correlation,
            'signals': signals,
            'shortlist': shortlist,
            'market_regime': market_regime,
            'intraday_confirmation': confirmation_meta,
        }

    def _apply_intraday_confirmation(self, shortlist, target_date):
        """Apply 09:35-style confirmation to stock trend candidates when minute data exists."""
        confirm_df, meta = self._load_intraday_confirmation_frame(target_date)
        if confirm_df.empty:
            return meta
        latest_timestamp = confirm_df["feature_timestamp"].dropna().max()

        if pd.isna(latest_timestamp) or float(latest_timestamp) < 935:
            return meta

        trend_candidates = shortlist.get("trend", [])
        kept = []
        rejected = shortlist.setdefault("trend_observation", [])
        for candidate in trend_candidates:
            data = candidate.get("data", {}) or {}
            if data.get("target_type") != "stock":
                kept.append(candidate)
                continue
            code = str(data.get("code", "") or "")
            matched = confirm_df[confirm_df["code"] == code] if code and "code" in confirm_df.columns else pd.DataFrame()
            if matched.empty:
                candidate["confirmation_state"] = "missing"
                candidate["confirmation_reason"] = "intraday_confirmation_missing"
                kept.append(candidate)
                continue
            row = matched.sort_values("feature_timestamp").iloc[-1]
            confirmed = self._is_confirmed_trend(row)
            candidate["confirmation_state"] = "confirmed" if confirmed else "rejected"
            candidate["confirmation_reason"] = self._describe_confirmation_reason(row, confirmed)
            candidate["confirmation_data"] = self._row_to_confirmation_data(row)
            if confirmed:
                candidate["action_score"] = round(candidate.get("action_score", 0) + 5.0, 2)
                kept.append(candidate)
            else:
                candidate["actionable"] = False
                candidate["action_filter_reason"] = "intraday_confirmation_rejected"
                rejected.append(candidate)
                meta["rejected_count"] += 1

        shortlist["trend"] = kept
        meta["applied"] = True
        meta["selected_after_confirmation"] = len(kept)
        return meta

    def _enrich_signals_with_intraday_confirmation(self, signals, target_date):
        """Attach 09:35 confirmation features before shortlist scoring."""
        confirm_df, meta = self._load_intraday_confirmation_frame(target_date)
        meta["enriched_count"] = 0
        if confirm_df.empty:
            return meta
        latest_timestamp = confirm_df["feature_timestamp"].dropna().max()
        if pd.isna(latest_timestamp) or float(latest_timestamp) < 935 or "code" not in confirm_df.columns:
            return meta

        latest_by_code = (
            confirm_df.sort_values("feature_timestamp")
            .drop_duplicates(subset=["code"], keep="last")
            .set_index("code")
        )
        for signal in signals.get("trend", []):
            data = signal.get("data", {}) or {}
            if data.get("target_type") != "stock":
                continue
            code = str(data.get("code", "") or "")
            if not code or code not in latest_by_code.index:
                continue
            row = latest_by_code.loc[code]
            confirmation_data = self._row_to_confirmation_data(row)
            signal["confirmation_data"] = confirmation_data
            signal["confirmation_state"] = (
                "confirmed" if confirmation_data["execution_bias"] == "confirmed_strength" else "observe"
            )
            data["confirmation_data"] = confirmation_data
            data["confirmation_bias"] = confirmation_data["execution_bias"]
            data["confirmation_price_vs_open_pct"] = confirmation_data["price_vs_open_pct"]
            data["confirmation_rs_vs_etf_pct"] = confirmation_data["rs_vs_etf_pct"]
            data["confirmation_rs_vs_index_pct"] = confirmation_data["rs_vs_index_pct"]
            data["confirmation_amount_1m_ratio"] = confirmation_data["amount_1m_ratio"]
            meta["enriched_count"] += 1
        return meta

    def _load_intraday_confirmation_frame(self, target_date):
        meta = {
            "available": False,
            "path": "",
            "feature_timestamp": None,
            "applied": False,
            "selected_after_confirmation": 0,
            "rejected_count": 0,
        }
        path = os.path.join(
            self.dm.base_path,
            str(int(target_date)),
            "intraday",
            "stock_confirmation_latest.csv",
        )
        if not os.path.exists(path):
            intraday_dir = os.path.dirname(path)
            local_intraday_ready = any(
                os.path.exists(os.path.join(intraday_dir, filename))
                for filename in (
                    "stocks_1min.csv",
                    "stock_confirmation_history.csv",
                    "etf_1min.csv",
                    "indices_1min.csv",
                )
            )
            if not local_intraday_ready:
                meta["rebuild_attempted"] = False
                meta["rebuild_skipped_reason"] = "local_replay_without_intraday_cache"
                return pd.DataFrame(), meta
            rebuild = self.dm.rebuild_intraday_confirmation_from_snapshot(target_date, force=False)
            meta["rebuild_attempted"] = True
            meta["rebuild_result"] = rebuild
            if not os.path.exists(path):
                return pd.DataFrame(), meta
        try:
            confirm_df = pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str})
        except Exception:
            return pd.DataFrame(), meta
        if confirm_df.empty:
            return pd.DataFrame(), meta
        if "feature_timestamp" in confirm_df.columns:
            confirm_df["feature_timestamp"] = pd.to_numeric(confirm_df["feature_timestamp"], errors="coerce")
        else:
            confirm_df["feature_timestamp"] = np.nan
        latest_timestamp = confirm_df["feature_timestamp"].dropna().max()
        meta["available"] = True
        meta["path"] = path
        meta["feature_timestamp"] = int(latest_timestamp) if pd.notna(latest_timestamp) else None
        return confirm_df, meta

    def _row_to_confirmation_data(self, row):
        return {
            "feature_timestamp": int(row.get("feature_timestamp", 0) or 0),
            "execution_bias": str(row.get("execution_bias", "") or ""),
            "price_vs_open_pct": round(self._to_float(row.get("price_vs_open_pct")), 4),
            "rs_vs_etf_pct": round(self._to_float(row.get("rs_vs_etf_pct")), 4),
            "rs_vs_index_pct": round(self._to_float(row.get("rs_vs_index_pct")), 4),
            "amount_1m_ratio": round(self._to_float(row.get("amount_1m_ratio")), 4),
        }

    @staticmethod
    def _is_confirmed_trend(row):
        bias = str(row.get("execution_bias", "") or "")
        price_vs_open = AuctionAnalyzer._to_float(row.get("price_vs_open_pct"))
        rs_vs_etf = AuctionAnalyzer._to_float(row.get("rs_vs_etf_pct"))
        rs_vs_index = AuctionAnalyzer._to_float(row.get("rs_vs_index_pct"))
        amount_1m_ratio = AuctionAnalyzer._to_float(row.get("amount_1m_ratio"))
        relative_ok = rs_vs_etf > 0 or rs_vs_index > 0
        amount_ok = amount_1m_ratio >= 1.0 if amount_1m_ratio == amount_1m_ratio else False
        return bias == "confirmed_strength" and price_vs_open >= 0 and relative_ok and amount_ok

    @staticmethod
    def _describe_confirmation_reason(row, confirmed):
        parts = [
            f"bias={row.get('execution_bias', '')}",
            f"open={AuctionAnalyzer._to_float(row.get('price_vs_open_pct')):+.2f}%",
            f"rs_etf={AuctionAnalyzer._to_float(row.get('rs_vs_etf_pct')):+.2f}%",
            f"rs_idx={AuctionAnalyzer._to_float(row.get('rs_vs_index_pct')):+.2f}%",
            f"amt1m={AuctionAnalyzer._to_float(row.get('amount_1m_ratio')):.2f}",
        ]
        return ("confirmed: " if confirmed else "rejected: ") + ", ".join(parts)
    
    def _load_realtime_data(self, date_list, target_date):
        """
        实时模式数据加载
        
        轻量同步模式下，没有今日stocks.csv，需要：
        1. 加载T-5到T-1的历史stocks数据
        2. 从auction数据+T-1数据构建今日数据
        
        支持多种数据格式：
        - 日K线模式：有open字段和pre_close字段
        - 快照数据：有open字段和pre_close字段
        - 分钟K线：close字段是当时价格，无pre_close
        
        返回:
            (df_stocks, df_today): 历史数据和今日数据
        """
        # 加载历史数据（T-5到T-1）
        history_dates = [d for d in date_list if d < target_date]
        df_stocks = self.dm.load_stocks(history_dates)
        
        if df_stocks.empty:
            print(f"⚠️ 无法加载历史个股数据")
            return pd.DataFrame(), pd.DataFrame()
        
        # 加载竞价数据
        df_auction = self.dm.load_auction([target_date])
        
        if df_auction.empty:
            print(f"⚠️ 无法加载竞价数据")
            return df_stocks, pd.DataFrame()
        
        # 从T-1获取行业信息（昨收价优先从auction数据获取）
        T_1 = int(date_list[-2])
        df_t1 = df_stocks[df_stocks['date_int'] == T_1].copy()
        
        if df_t1.empty:
            print(f"⚠️ 无法获取T-1数据")
            return df_stocks, pd.DataFrame()
        
        # 构建行业映射
        industry_map = df_t1.set_index('code')['industry'].to_dict() if 'industry' in df_t1.columns else {}
        
        # 构建名称映射
        name_map = df_t1.set_index('code')['name'].to_dict() if 'name' in df_t1.columns else {}
        
        # 构建昨收价映射（T-1的close作为备选）
        prev_close_backup = df_t1.set_index('code')['close'].to_dict()
        
        # 构建今日数据
        df_today = df_auction.copy()
        df_today['date_int'] = target_date
        coverage_ratio = len(df_auction) / len(prev_close_backup) if prev_close_backup else 0.0
        print(f"  ✓ 竞价股票池覆盖率: {len(df_auction)}/{len(prev_close_backup)} ({coverage_ratio:.1%})")
        if coverage_ratio < AuctionConfig.REALTIME_CAPTURE_MIN_RATIO:
            print("  ⚠️ 竞价覆盖率不足，仅对已返回标的生成观察候选；不宜代表完整股票池")
        if 'auction_source' in df_today.columns:
            sources = sorted(set(df_today['auction_source'].dropna().astype(str)))
            exact_ratio = (
                df_today.get('auction_amount_exact', pd.Series(dtype=bool))
                .astype(str).str.lower().eq('true').mean()
            )
            print(f"  ✓ 竞价数据来源: {sources} | 精确竞价额占比: {exact_ratio:.1%}")
            if exact_ratio < 1:
                print("  ⚠️ 当前包含降级竞价额，仅适合观察；09:25实时决策优先使用订阅或历史快照")
        
        # 判断数据来源并提取开盘价
        if 'open' in df_auction.columns and df_auction['open'].notna().any():
            # 日K线或快照数据：open就是开盘价（竞价价格）
            df_today['open'] = df_auction['open']
            print(f"  ✓ 使用open字段作为竞价价格")
        elif 'close' in df_auction.columns:
            # 分钟K线：close是当时价格
            df_today['open'] = df_auction['close']
            print(f"  ✓ 使用close字段作为竞价价格")
        else:
            df_today['open'] = df_auction.get('last', 0)
            print(f"  ✓ 使用last字段作为竞价价格")
        
        # 昨收价：优先使用auction数据的pre_close，否则用T-1的close
        if 'pre_close' in df_auction.columns and df_auction['pre_close'].notna().any():
            df_today['prev_close'] = df_auction['pre_close']
            print(f"  ✓ 使用auction数据的pre_close")
        else:
            df_today['prev_close'] = df_today['code'].map(prev_close_backup)
            print(f"  ✓ 使用T-1 close作为昨收价")
        
        price_candidates = []
        price_labels = []
        for column in ('auction_price', 'open', 'last', 'close'):
            if column not in df_auction.columns:
                continue
            series = pd.to_numeric(df_auction[column], errors='coerce')
            price_candidates.append(series.where(series > 0))
            price_labels.append(column)
        if price_candidates:
            df_today['auction_price'] = pd.concat(price_candidates, axis=1).bfill(axis=1).iloc[:, 0]
            df_today['open'] = df_today['auction_price']
            valid_price_count = int(df_today['auction_price'].notna().sum())
            print(f"  ✓ 使用 {price_labels} 优先级构建竞价价格，有效 {valid_price_count}/{len(df_today)}")
        else:
            df_today['auction_price'] = np.nan
            df_today['open'] = np.nan
            print("  ⚠️ 未找到可用竞价价格字段")

        df_today['pre_close'] = df_today['prev_close']  # 兼容两种命名
        df_today['industry'] = df_today['code'].map(industry_map).fillna('其他')
        df_today['name'] = df_today['code'].map(name_map).fillna(df_today['code'])
        
        # 实时模式下，close/high/low处理
        if 'close' not in df_today.columns or df_today['close'].isna().all():
            df_today['close'] = df_today['open']
        if 'high' not in df_today.columns or df_today['high'].isna().all():
            df_today['high'] = df_today['open']
        if 'low' not in df_today.columns or df_today['low'].isna().all():
            df_today['low'] = df_today['open']
        
        # 过滤无效数据（没有昨收价的）
        df_today = df_today[df_today['prev_close'].notna() & (df_today['prev_close'] > 0)]
        
        # ============ 补充实时模式需要的列 ============
        # 竞价成交额
        if 'amount' in df_today.columns:
            df_today['auction_amount'] = df_today['amount']
        else:
            df_today['auction_amount'] = 0
            df_today['amount'] = 0
        
        # pct（涨跌幅）：实时模式=竞价涨幅
        valid_open_mask = (
            (df_today['prev_close'] > 0)
            & df_today['open'].notna()
            & (df_today['open'] > 0)
        )
        df_today['pct'] = np.where(
            valid_open_mask,
            (df_today['open'] - df_today['prev_close']) / df_today['prev_close'] * 100,
            np.nan
        )
        
        # body_pct（实体涨幅）：实时模式下为0（还没有日内波动）
        df_today['body_pct'] = 0.0
        
        # auction_pct（竞价涨幅）：与pct相同
        df_today['auction_pct'] = df_today['pct']
        df_today['auction_price_valid'] = valid_open_mask
        
        # vol_ratio（量比）：实时模式下设为1.0
        df_today['vol_ratio'] = 1.0
        df_today['auction_coverage_ratio'] = coverage_ratio
        
        print(f"  ✓ 实时数据构建: {len(df_today)} 只个股")
        
        return df_stocks, df_today
    
    def _calc_position_5d(self, df):
        """计算竞价时点可知的5日位置，避免目标日收盘价泄漏。"""
        if df.empty:
            return df
        
        df = df.sort_values(['code', 'date_int'])
        
        # 历史区间只允许使用T-1及更早收盘价，今日参考价使用竞价后已知的开盘价。
        df['high_5d'] = df.groupby('code')['close'].transform(
            lambda x: x.shift(1).rolling(5, min_periods=1).max()
        )
        df['low_5d'] = df.groupby('code')['close'].transform(
            lambda x: x.shift(1).rolling(5, min_periods=1).min()
        )
        
        range_5d = df['high_5d'] - df['low_5d']
        reference_price = df['open'].fillna(df['close'])
        df['pos_5d'] = np.where(
            range_5d > 0,
            ((reference_price - df['low_5d']) / range_5d * 100).clip(0, 100),
            50
        )
        
        return df
    
    def _get_market_oar(self, df_indices_today):
        """获取市场OAR（上证量比）"""
        if df_indices_today.empty:
            return 1.0
        
        sh = df_indices_today[df_indices_today['code'] == '000001.SH']
        if sh.empty:
            return 1.0
        
        return float(sh.iloc[0].get('vol_ratio', 1.0) or 1.0)

    def _analyze_index_factors(self, df_indices, date_list, target_date, market_oar, realtime=False):
        """四大指数 CP/SA 因子监控。"""
        return self._analyze_security_factors(
            source_df=df_indices,
            date_list=date_list,
            code_name_map=MarketConfig.MAIN_INDICES,
            target_col='指数',
            target_type='index',
            default_rank=4,
            market_oar=market_oar,
            realtime=realtime,
            top_k=None,
        )

    def _analyze_stock_factors(self, df_today, df_t1, df_t2, market_oar, realtime=False, top_k=None):
        """自选股 CP/SA 因子监控，按风险/机会强度取 TopK。"""
        if df_today.empty:
            return pd.DataFrame()

        today = df_today.copy()
        if 'code' not in today.columns:
            return pd.DataFrame()

        today = today[today.get('auction_pct', pd.Series(index=today.index)).notna()].copy()
        if today.empty:
            return pd.DataFrame()

        today = today.sort_values('auction_amount' if 'auction_amount' in today.columns else 'amount', ascending=False).reset_index(drop=True)
        today['amt_rank'] = today.index + 1

        t1 = df_t1.copy()
        t2 = df_t2.copy()
        t1_map = t1.set_index('code') if not t1.empty and 'code' in t1.columns else pd.DataFrame()
        t2_map = t2.set_index('code') if not t2.empty and 'code' in t2.columns else pd.DataFrame()

        results = []
        for _, row in today.iterrows():
            code = row.get('code', '')
            row_t1 = t1_map.loc[code] if not t1_map.empty and code in t1_map.index else None
            row_t2 = t2_map.loc[code] if not t2_map.empty and code in t2_map.index else None
            name = row.get('name', code)

            prev_pct = self._safe_float(row_t1.get('pct', 0) if row_t1 is not None else 0)
            prev_body_pct = self._calc_row_body_pct(row_t1)
            prev_vol_ratio = self._safe_float(row_t1.get('vol_ratio', 1.0) if row_t1 is not None else 1.0, 1.0)
            pct_t2 = self._safe_float(row_t2.get('pct', 0) if row_t2 is not None else 0)
            auction_pct = self._safe_float(row.get('auction_pct', row.get('pct', 0)))
            close_pct = self._safe_float(row.get('pct', 0))
            body_pct = self._safe_float(row.get('body_pct', close_pct - auction_pct))
            vol_ratio = self._safe_float(row.get('vol_ratio', 1.0), 1.0)
            pos_5d = self._safe_float(row.get('pos_5d', 50), 50)
            auction_amt = self._safe_float(row.get('auction_amount', 0)) / 1e8
            trend_state = self._get_trend_state(pct_t2, prev_pct, prev_body_pct)

            factor_data = {
                'amt_rank': int(row.get('amt_rank', 99) or 99),
                'pos_5d': pos_5d,
                'auction_pct': auction_pct,
                'prev_pct': prev_pct,
                'prev_body_pct': prev_body_pct,
                'prev_vol_ratio': prev_vol_ratio,
                'auction_amt': auction_amt,
                'is_gem': str(code).startswith(('300', '301', '688')),
                'body_pct': body_pct,
                'close_pct': close_pct,
                'vol_ratio': vol_ratio,
                'pct_t2': pct_t2,
                'trend_state': trend_state,
                'prev_close': self._safe_float(row.get('prev_close', row.get('pre_close', 0))),
                'open': self._safe_float(row.get('open', 0)),
                'high': self._safe_float(row.get('high', 0)),
                'low': self._safe_float(row.get('low', 0)),
                'close': self._safe_float(row.get('close', 0)),
                'amount': self._safe_float(row.get('amount', 0)),
                'volume': self._safe_float(row.get('volume', row.get('vol', 0))),
                'turnover_rate': self._safe_float(row.get('turnover_rate', row.get('turnover', 0))),
            }
            cp = AuctionFactors.calc_cp(factor_data, market_oar)
            sa = AuctionFactors.calc_sa(factor_data, market_oar)
            factor_data['cp'] = cp
            factor_data['sa'] = sa

            scenario = ScenarioIdentifier.identify(factor_data, market_oar, realtime=realtime)
            signal_info = ScenarioIdentifier.get_signal_type(scenario)
            signal = signal_info[0] if signal_info else self._get_realtime_signal(auction_pct, cp, sa) if realtime else self._get_simple_signal(auction_pct, body_pct, vol_ratio)

            results.append({
                '排名': int(row.get('amt_rank', 99)),
                '代码': code,
                '名称': name,
                '分组': row.get('industry', row.get('group', '-')),
                '竞价额': f"{auction_amt:.2f}亿",
                'T-2': f"{pct_t2:+.2f}%",
                'T-1': f"{prev_pct:+.2f}%",
                '竞价': f"{auction_pct:+.2f}%",
                '收盘': f"{close_pct:+.2f}%",
                '实体': f"{body_pct:+.2f}%",
                '量比': round(vol_ratio, 2),
                '5日位': f"{pos_5d:.0f}%",
                'CP': cp if cp is not None else '--',
                'SA': sa if sa is not None else '--',
                '信号': signal,
                '_scenario': scenario,
                '_data': factor_data,
                '_name': name,
                '_code': code,
                '_amt_rank': int(row.get('amt_rank', 99)),
            })

        if not results:
            return pd.DataFrame()
        df = pd.DataFrame(results)
        df['_sort_score'] = df.apply(lambda r: max(self._safe_float(r.get('CP')), self._safe_float(r.get('SA'))), axis=1)
        df = df.sort_values(['_sort_score', '排名'], ascending=[False, True])
        if top_k:
            df = df.head(top_k)
        return df.drop(columns=['_sort_score'])

    def _analyze_security_factors(self, source_df, date_list, code_name_map, target_col, target_type, default_rank, market_oar, realtime=False, top_k=None):
        """Shared CP/SA factor calculation for index-like securities."""
        if source_df.empty or len(date_list) < 3:
            return pd.DataFrame()

        T = int(date_list[-1])
        T_1 = int(date_list[-2])
        T_2 = int(date_list[-3])
        results = []
        for code, name in code_name_map.items():
            hist = source_df[source_df['code'] == code].copy()
            if hist.empty:
                continue
            hist['date_int'] = hist['date_int'].astype(int)
            row_t = self._first_row(hist, T)
            row_t1 = self._first_row(hist, T_1)
            row_t2 = self._first_row(hist, T_2)
            if row_t is None:
                continue
            prev_close = self._safe_float(row_t.get('prev_close', 0))
            if prev_close <= 0:
                continue

            auction_pct = (self._safe_float(row_t.get('open', 0)) - prev_close) / prev_close * 100
            close_pct = self._safe_float(row_t.get('pct', 0))
            body_pct = (self._safe_float(row_t.get('close', 0)) - self._safe_float(row_t.get('open', 0))) / prev_close * 100
            prev_pct = self._safe_float(row_t1.get('pct', 0) if row_t1 is not None else 0)
            prev_body_pct = self._calc_row_body_pct(row_t1)
            prev_vol_ratio = self._safe_float(row_t1.get('vol_ratio', 1.0) if row_t1 is not None else 1.0, 1.0)
            pct_t2 = self._safe_float(row_t2.get('pct', 0) if row_t2 is not None else 0)
            vol_ratio = self._safe_float(row_t.get('vol_ratio', 1.0), 1.0)
            pos_5d = self._safe_float(row_t.get('pos_5d', 50), 50)
            trend_state = self._get_trend_state(pct_t2, prev_pct, prev_body_pct)

            factor_data = {
                'amt_rank': default_rank,
                'pos_5d': pos_5d,
                'auction_pct': auction_pct,
                'prev_pct': prev_pct,
                'prev_body_pct': prev_body_pct,
                'prev_vol_ratio': prev_vol_ratio,
                'auction_amt': 0,
                'is_gem': code.startswith(('399006', '000688')),
                'body_pct': body_pct,
                'close_pct': close_pct,
                'vol_ratio': vol_ratio,
                'pct_t2': pct_t2,
                'trend_state': trend_state,
                'prev_close': prev_close,
                'open': self._safe_float(row_t.get('open', 0)),
                'high': self._safe_float(row_t.get('high', 0)),
                'low': self._safe_float(row_t.get('low', 0)),
                'close': self._safe_float(row_t.get('close', 0)),
                'amount': self._safe_float(row_t.get('amount', 0)),
                'volume': self._safe_float(row_t.get('volume', row_t.get('vol', 0))),
                'turnover_rate': self._safe_float(row_t.get('turnover_rate', row_t.get('turnover', 0))),
            }
            cp = AuctionFactors.calc_cp(factor_data, market_oar)
            sa = AuctionFactors.calc_etf_sa(factor_data, market_oar)
            factor_data['cp'] = cp
            factor_data['sa'] = sa
            scenario = ScenarioIdentifier.identify(factor_data, market_oar, realtime=realtime)
            signal_info = ScenarioIdentifier.get_signal_type(scenario)
            signal = signal_info[0] if signal_info else self._get_realtime_signal(auction_pct, cp, sa) if realtime else self._get_simple_signal(auction_pct, body_pct, vol_ratio)

            results.append({
                target_col: name,
                'T-2': f"{pct_t2:+.2f}%",
                'T-1': f"{prev_pct:+.2f}%",
                '竞价': f"{auction_pct:+.2f}%",
                '收盘': f"{close_pct:+.2f}%",
                '实体': f"{body_pct:+.2f}%",
                '量比': round(vol_ratio, 2),
                '5日位': f"{pos_5d:.0f}%",
                'CP': cp if cp is not None else '--',
                'SA': sa if sa is not None else '--',
                '信号': signal,
                '_scenario': scenario,
                '_data': factor_data,
                '_name': name,
                '_code': code,
                '_amt_rank': default_rank,
            })

        df = pd.DataFrame(results)
        if df.empty:
            return df
        if top_k:
            df['_sort_score'] = df.apply(lambda r: max(self._safe_float(r.get('CP')), self._safe_float(r.get('SA'))), axis=1)
            df = df.sort_values('_sort_score', ascending=False).head(top_k).drop(columns=['_sort_score'])
        return df

    @staticmethod
    def _safe_float(value, default=0.0):
        try:
            if value is None or pd.isna(value):
                return default
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _first_row(df, date_int):
        row = df[df['date_int'] == int(date_int)]
        return None if row.empty else row.iloc[0]

    def _calc_row_body_pct(self, row):
        if row is None:
            return 0.0
        prev_close = self._safe_float(row.get('prev_close', 0))
        if prev_close <= 0:
            return 0.0
        return (self._safe_float(row.get('close', 0)) - self._safe_float(row.get('open', 0))) / prev_close * 100
    
    def _analyze_etf_auction_v2(self, df_indices, date_list, target_date, market_oar, realtime=False):
        """
        ETF竞价监控 v2.0 - 含T-2/T-1趋势和CP/SA指标
        
        参数:
            realtime: 是否实时模式（不显示收盘、实体列）
        """
        if df_indices.empty or len(date_list) < 3:
            return pd.DataFrame()
        
        T = int(date_list[-1])
        T_1 = int(date_list[-2])
        T_2 = int(date_list[-3])
        
        def safe_get(row, key, default=0):
            if row is None:
                return default
            val = row.get(key, default) if hasattr(row, 'get') else default
            if pd.isna(val):
                return default
            return float(val)
        
        results = []
        for code, name in MarketConfig.ETF_MONITORS.items():
            hist = df_indices[df_indices['code'] == code].copy()
            if hist.empty:
                continue
            
            hist['date_int'] = hist['date_int'].astype(int)
            hist = hist.sort_values('date_int')
            
            row_t = hist[hist['date_int'] == T]
            row_t1 = hist[hist['date_int'] == T_1]
            row_t2 = hist[hist['date_int'] == T_2]
            
            if row_t.empty:
                continue
            
            row_t = row_t.iloc[0]
            row_t1 = row_t1.iloc[0] if not row_t1.empty else None
            row_t2 = row_t2.iloc[0] if not row_t2.empty else None
            
            # 今日指标
            prev_close = safe_get(row_t, 'prev_close', 0)
            if prev_close <= 0:
                continue
            
            open_price = safe_get(row_t, 'open', 0)
            close_price = safe_get(row_t, 'close', 0)
            
            auction_pct = (open_price - prev_close) / prev_close * 100
            close_pct = safe_get(row_t, 'pct', 0)
            body_pct = (close_price - open_price) / prev_close * 100
            vol_ratio = safe_get(row_t, 'vol_ratio', 1.0)
            pos_5d = safe_get(row_t, 'pos_5d', 50)
            
            # 昨日指标
            prev_pct = safe_get(row_t1, 'pct', 0) if row_t1 is not None else 0
            prev_body_pct = 0
            if row_t1 is not None:
                prev_close_t1 = safe_get(row_t1, 'prev_close', 0)
                if prev_close_t1 > 0:
                    prev_body_pct = (safe_get(row_t1, 'close', 0) - safe_get(row_t1, 'open', 0)) / prev_close_t1 * 100
            prev_vol_ratio = safe_get(row_t1, 'vol_ratio', 1.0) if row_t1 is not None else 1.0
            
            # T-2指标
            pct_t2 = safe_get(row_t2, 'pct', 0) if row_t2 is not None else 0
            
            # 趋势状态
            trend_state = self._get_trend_state(pct_t2, prev_pct, prev_body_pct)
            
            # 计算CP/SA
            # CP仍使用通用公式（排名权重按Top4-5水平）
            # SA使用ETF专用公式（基于技术面，不依赖竞价额）
            
            factor_data = {
                'amt_rank': 4,  # ETF视为Top4-5级别，权重0.7
                'pos_5d': pos_5d,
                'auction_pct': auction_pct,
                'prev_pct': prev_pct,
                'prev_body_pct': prev_body_pct,
                'prev_vol_ratio': prev_vol_ratio,
                'auction_amt': 0,  # ETF SA不再依赖竞价额
                'is_gem': code.startswith('159'),  # 创业板ETF
                'body_pct': body_pct,
                'close_pct': close_pct,
                'vol_ratio': vol_ratio,
                'pct_t2': pct_t2,
                'trend_state': trend_state,
                'prev_close': prev_close,
                'open': open_price,
                'high': safe_get(row_t, 'high', 0),
                'low': safe_get(row_t, 'low', 0),
                'close': close_price,
                'amount': safe_get(row_t, 'amount', 0),
                'volume': safe_get(row_t, 'volume', safe_get(row_t, 'vol', 0)),
                'turnover_rate': safe_get(row_t, 'turnover_rate', safe_get(row_t, 'turnover', 0)),
            }
            
            cp = AuctionFactors.calc_cp(factor_data, market_oar)
            sa = AuctionFactors.calc_etf_sa(factor_data, market_oar)  # 使用ETF专用SA公式
            
            # 生成信号
            factor_data['cp'] = cp
            factor_data['sa'] = sa
            scenario = ScenarioIdentifier.identify(factor_data, market_oar, realtime=realtime)
            signal_info = ScenarioIdentifier.get_signal_type(scenario)
            
            # 实时模式下用简化的信号判断（没有body_pct）
            if realtime:
                signal = signal_info[0] if signal_info else self._get_realtime_signal(auction_pct, cp, sa)
            else:
                signal = signal_info[0] if signal_info else self._get_simple_signal(auction_pct, body_pct, vol_ratio)
            
            # 走势状态（实时模式下为预判）
            if realtime:
                status = self._get_auction_status(auction_pct, prev_pct)
            else:
                status = self._get_walk_status(auction_pct, body_pct, close_pct)
            
            row_data = {
                'ETF': name,
                'T-2': f"{pct_t2:+.2f}%",
                'T-1': f"{prev_pct:+.2f}%",
                '竞价': f"{auction_pct:+.2f}%",
                '5日位': f"{pos_5d:.0f}%",
                'CP': cp if cp is not None else '--',
                'SA': sa if sa is not None else '--',
                '信号': signal,
                # 用于信号汇总的原始数据
                '_scenario': scenario,
                '_data': factor_data,
                '_name': name,
                '_code': code,
            }
            
            # 复盘模式添加收盘和实体
            if not realtime:
                row_data['收盘'] = f"{close_pct:+.2f}%"
                row_data['实体'] = f"{body_pct:+.2f}%"
                row_data['量比'] = round(vol_ratio, 2)
            
            results.append(row_data)
        
        if not results:
            return pd.DataFrame()
        
        df = pd.DataFrame(results)
        return df
    
    def _get_realtime_signal(self, auction_pct, cp, sa):
        """实时模式下的简化信号判断（没有body_pct）"""
        if cp is not None and cp >= 60:
            return '🔴CP风险'
        elif sa is not None and sa >= 50:
            return '🟢反核'
        elif auction_pct > 0.5:
            return '🟡高开'
        elif auction_pct < -0.5:
            return '🟡低开'
        else:
            return '⚪观望'
    
    def _get_auction_status(self, auction_pct, prev_pct):
        """实时模式下的竞价状态描述"""
        if auction_pct > 1.0:
            return "⬆️大幅高开"
        elif auction_pct > 0.3:
            return "↗️高开"
        elif auction_pct < -1.0:
            return "⬇️大幅低开"
        elif auction_pct < -0.3:
            return "↘️低开"
        else:
            return "➡️平开"
    
    def _calc_industry_auction_v2(self, df_today, df_t1, df_t2, market_oar, realtime=False):
        """
        行业竞价排行 v2.0 - 含T-2/T-1趋势和CP/SA指标
        
        参数:
            df_today: 今日数据（已计算auction_pct）
            df_t1: 昨日数据
            df_t2: 前日数据
            market_oar: 市场OAR
        """
        if 'industry' not in df_today.columns:
            return pd.DataFrame()
        
        # 今日行业聚合
        valid_df = df_today[df_today['auction_pct'].notna() & (df_today['auction_pct'] > -99)].copy()
        if valid_df.empty:
            return pd.DataFrame()
        
        agg_t = valid_df.groupby('industry').agg({
            'auction_amount': 'sum',
            'amount': 'sum',
            'auction_pct': 'mean',
            'pct': 'mean',
            'body_pct': 'mean',
            'code': 'count'
        }).reset_index()
        agg_t = agg_t.rename(columns={'code': 'stock_count'})
        agg_t = agg_t[agg_t['stock_count'] >= AuctionConfig.MIN_STOCK_COUNT]
        
        # 计算竞价额排名
        agg_t = agg_t.sort_values('auction_amount', ascending=False).reset_index(drop=True)
        agg_t['amt_rank'] = agg_t.index + 1
        
        # 昨日行业聚合
        if not df_t1.empty and 'industry' in df_t1.columns:
            agg_t1 = df_t1.groupby('industry').agg({
                'pct': 'mean',
                'vol_ratio': 'mean'
            }).reset_index()
            # 计算昨日实体涨幅
            if 'prev_close' in df_t1.columns and 'open' in df_t1.columns and 'close' in df_t1.columns:
                df_t1_copy = df_t1.copy()
                df_t1_copy['body_pct_calc'] = np.where(
                    df_t1_copy['prev_close'] > 0,
                    (df_t1_copy['close'] - df_t1_copy['open']) / df_t1_copy['prev_close'] * 100,
                    0
                )
                agg_t1_body = df_t1_copy.groupby('industry')['body_pct_calc'].mean().reset_index()
                agg_t1_body = agg_t1_body.rename(columns={'body_pct_calc': 'body_pct'})
                agg_t1 = agg_t1.merge(agg_t1_body, on='industry', how='left')
            else:
                agg_t1['body_pct'] = 0
        else:
            agg_t1 = pd.DataFrame()
        
        # 前日行业聚合
        if not df_t2.empty and 'industry' in df_t2.columns:
            agg_t2 = df_t2.groupby('industry').agg({
                'pct': 'mean'
            }).reset_index()
        else:
            agg_t2 = pd.DataFrame()
        
        # 合并数据
        if not agg_t1.empty:
            # 先重命名列，避免 merge 时的混乱
            agg_t1_renamed = agg_t1.rename(columns={
                'pct': 'pct_t1', 
                'body_pct': 'body_pct_t1', 
                'vol_ratio': 'vol_ratio_t1'
            })
            agg_t = agg_t.merge(
                agg_t1_renamed[['industry', 'pct_t1', 'body_pct_t1', 'vol_ratio_t1']],
                on='industry', how='left'
            )
        else:
            agg_t['pct_t1'] = 0
            agg_t['body_pct_t1'] = 0
            agg_t['vol_ratio_t1'] = 1.0
        
        if not agg_t2.empty:
            agg_t = agg_t.merge(
                agg_t2[['industry', 'pct']].rename(columns={'pct': 'pct_t2'}),
                on='industry', how='left'
            )
        else:
            agg_t['pct_t2'] = 0
        
        # 填充缺失值
        for col in ['pct_t1', 'body_pct_t1', 'pct_t2']:
            if col in agg_t.columns:
                agg_t[col] = agg_t[col].fillna(0)
            else:
                agg_t[col] = 0
        
        if 'vol_ratio_t1' in agg_t.columns:
            agg_t['vol_ratio_t1'] = agg_t['vol_ratio_t1'].fillna(1.0)
        else:
            agg_t['vol_ratio_t1'] = 1.0
        
        # 计算CP/SA和信号
        results = []
        for _, row in agg_t.iterrows():
            trend_state = self._get_trend_state(row['pct_t2'], row['pct_t1'], row['body_pct_t1'])
            
            factor_data = {
                'amt_rank': row['amt_rank'],
                'pos_5d': 50,  # 行业没有5日位置，默认50
                'auction_pct': row['auction_pct'],
                'prev_pct': row['pct_t1'],
                'prev_body_pct': row['body_pct_t1'],
                'prev_vol_ratio': row['vol_ratio_t1'],
                'auction_amt': row['auction_amount'] / 1e8,
                'is_gem': False,
                'body_pct': row['body_pct'],
                'close_pct': row['pct'],
                'vol_ratio': row['vol_ratio_t1'],
                'pct_t2': row['pct_t2'],
                'trend_state': trend_state,
                'amount': row['amount'],
                'auction_amount_raw': row['auction_amount'],
                'stock_count': row['stock_count'],
            }
            
            cp = AuctionFactors.calc_cp(factor_data, market_oar)
            sa = AuctionFactors.calc_sa(factor_data, market_oar)
            
            factor_data['cp'] = cp
            factor_data['sa'] = sa
            scenario = ScenarioIdentifier.identify(factor_data, market_oar, realtime=realtime)
            signal_info = ScenarioIdentifier.get_signal_type(scenario)
            
            # 实时模式下用简化的信号判断
            if realtime:
                signal = signal_info[0] if signal_info else self._get_realtime_signal(row['auction_pct'], cp, sa)
            else:
                signal = signal_info[0] if signal_info else self._get_simple_signal(row['auction_pct'], row['body_pct'], row['vol_ratio_t1'])
            
            row_data = {
                '排名': int(row['amt_rank']),
                '板块': row['industry'],
                '竞价额': f"{row['auction_amount']/1e8:.2f}亿",
                'T-2': f"{row['pct_t2']:+.2f}%",
                'T-1': f"{row['pct_t1']:+.2f}%",
                '竞价': f"{row['auction_pct']:+.2f}%",
                '5日位': '--',
                'CP': cp if cp is not None else '--',
                'SA': sa if sa is not None else '--',
                '信号': signal,
                # 用于信号汇总的原始数据
                '_scenario': scenario,
                '_data': factor_data,
                '_name': row['industry'],
                '_code': '',
                '_amt_rank': row['amt_rank']
            }
            
            # 复盘模式添加收盘和实体
            if not realtime:
                row_data['收盘'] = f"{row['pct']:+.2f}%"
                row_data['实体'] = f"{row['body_pct']:+.2f}%"
            
            results.append(row_data)
        
        return pd.DataFrame(results).head(15)
    
    def _get_trend_state(self, pct_t2, pct_t1, body_t1):
        """获取趋势状态"""
        if pct_t1 > 0.5 and pct_t2 > 0.5:
            return '连涨'
        elif pct_t1 < -0.5 and pct_t2 < -0.5:
            return '连跌'
        elif pct_t2 < -0.5 and pct_t1 > 0.5:
            return '反弹'
        elif body_t1 > 1.5:
            return '昨涨'
        elif body_t1 < -1.5:
            return '昨跌'
        else:
            return '震荡'
    
    def _get_simple_signal(self, auction_pct, body_pct, vol_ratio=1.0):
        """获取简单信号"""
        if body_pct > 2.0:
            if auction_pct < -0.3:
                return '🟢反核'
            else:
                return '🟢趋势'
        elif body_pct > 1.0:
            return '🟢修复'
        elif body_pct < -1.0:
            if auction_pct > 0.3:
                return '🔴CP风险'
            else:
                return '🟡弱势'
        elif vol_ratio < 0.7:
            return '⚪弱势'
        else:
            return '🟡观望'
    
    def _get_walk_status(self, auction_pct, body_pct, close_pct):
        """获取走势状态"""
        if auction_pct > 0.2:
            if body_pct > 0.3:
                return "🔥高开高走"
            elif body_pct < -0.3:
                return "⚠️高开低走"
            else:
                return "➡️高开平走"
        elif auction_pct < -0.2:
            if body_pct > 0.3:
                return "🔺低开高走"
            elif close_pct < auction_pct:
                return "❄️低开低走"
            else:
                return "➡️低开平走"
        else:
            if body_pct > 0.3:
                return "📈平开高走"
            elif body_pct < -0.3:
                return "📉平开低走"
            else:
                return "➡️平开震荡"
    
    def _generate_signals(self, index_df, etf_df, stock_df, industry_df, market_oar, realtime=False):
        """
        生成信号汇总
        
        参数:
            realtime: 是否实时模式
        
        返回:
            dict: {trap: [...], reversal: [...], trend: [...]}
            - trap按CP降序排列
            - reversal按SA降序排列
        """
        signals = {
            'trap': [],      # 诱多警报
            'reversal': [],  # 反核机会
            'trend': []      # 趋势延续
        }
        
        self._append_signal_rows(signals, index_df, market_oar, realtime, target_type='index', display_type='指数', order=0)
        self._append_signal_rows(signals, etf_df, market_oar, realtime, target_type='ETF', display_type='ETF', order=1)
        self._append_signal_rows(signals, stock_df, market_oar, realtime, target_type='stock', display_type='个股', order=2)
        self._append_signal_rows(signals, industry_df, market_oar, realtime, target_type='industry', display_type='行业', order=3)
        
        # 排序只能使用竞价时点可见字段，避免复盘排序引入收盘实体泄漏。
        signals['trap'] = sorted(signals['trap'], key=lambda x: (x.get('order', 9), -(x.get('cp') or 0)))
        signals['reversal'] = sorted(signals['reversal'], key=lambda x: (x.get('order', 9), -(x.get('sa') or 0)))
        signals['trend'] = sorted(
            signals['trend'],
            key=lambda x: (
                x.get('order', 9),
                x.get('amt_rank') if x.get('amt_rank') is not None else 9999,
                -x.get('data', {}).get('auction_pct', 0),
            ),
        )
        
        return signals

    def _append_signal_rows(self, signals, df, market_oar, realtime, target_type, display_type, order):
        if df is None or df.empty or '_scenario' not in df.columns:
            return
        for _, row in df.iterrows():
            scenario = row.get('_scenario')
            if not scenario:
                continue
            signal_info = ScenarioIdentifier.get_signal_type(scenario)
            if not signal_info:
                continue
            signal_type, category = signal_info
            signal_data = dict(row['_data'])
            signal_data['name'] = row['_name']
            signal_data['target_type'] = target_type
            signal_data['trigger_reason'] = SignalFeatureBuilder.build(
                name=row['_name'],
                target_type=target_type,
                scenario=scenario,
                category=category,
                row=signal_data,
                market_oar=market_oar,
            )['hard_rule']['trigger_reason']
            if scenario == ScenarioIdentifier.TRAP_OVERHEATED_ACCELERATION:
                signal_data['trigger_reason'] = 'overheated_acceleration_risk'
            signals[category].append({
                'name': row['_name'],
                'type': display_type,
                'order': order,
                'scenario': scenario,
                'signal': signal_type,
                'cp': row['_data'].get('cp'),
                'sa': row['_data'].get('sa'),
                'amt_rank': row.get('_amt_rank'),
                'data': signal_data,
                'commentary': None,
                'realtime': realtime
            })

    @staticmethod
    def _build_shortlist_commentary(shortlist, market_oar):
        for category in ("trap", "reversal", "trend"):
            items = shortlist.get(category, [])
            for signal in items:
                signal['commentary'] = CommentaryGenerator.generate(
                    signal.get('data', {}),
                    signal.get('scenario'),
                    market_oar,
                )

    @staticmethod
    def _to_float(value, default=0.0):
        try:
            if pd.isna(value):
                return default
            return float(value)
        except (TypeError, ValueError):
            return default
    
    def _analyze_main_indices(self, df_indices, date_list, target_date):
        """
        四大指数监控 - 分析近三日趋势和当日竞价情况
        
        优化：
        1. 阈值差异化（上证 vs 双创 vs 北证）
        2. 量价关系研判
        3. 量价背离警示
        
        返回:
            DataFrame: 指数监控结果
        """
        # 辅助函数：安全获取数值
        def safe_get(row, key, default=0):
            if row is None:
                return default
            val = row.get(key, default) if hasattr(row, 'get') else row[key] if key in row else default
            if pd.isna(val):
                return default
            return float(val)
        
        if df_indices.empty or len(date_list) < 3:
            return pd.DataFrame()
        
        # 确保date_list中的日期是整数，取最后3天（T-2, T-1, T）
        T = int(date_list[-1])      # 今日
        T_1 = int(date_list[-2])    # 昨日
        T_2 = int(date_list[-3])    # 前日
        
        # 打印可用的指数代码
        available_codes = df_indices['code'].unique().tolist()
        
        results = []
        for code, name in MarketConfig.MAIN_INDICES.items():
            # 查找该指数的数据
            hist = df_indices[df_indices['code'] == code].copy()
            if hist.empty:
                continue
            
            # 确保date_int是整数类型
            hist['date_int'] = hist['date_int'].astype(int)
            hist = hist.sort_values('date_int')
            
            # 获取三日数据
            row_t = hist[hist['date_int'] == T]
            row_t1 = hist[hist['date_int'] == T_1]
            row_t2 = hist[hist['date_int'] == T_2]
            
            if row_t.empty:
                continue
            
            row_t = row_t.iloc[0]
            row_t1 = row_t1.iloc[0] if not row_t1.empty else None
            row_t2 = row_t2.iloc[0] if not row_t2.empty else None
            
            # 计算今日指标
            prev_close = safe_get(row_t, 'prev_close', 0)
            if prev_close <= 0:
                continue
            
            open_price = safe_get(row_t, 'open', 0)
            close_price = safe_get(row_t, 'close', 0)
            
            auction_pct = (open_price - prev_close) / prev_close * 100
            close_pct = safe_get(row_t, 'pct', 0)
            body_pct = (close_price - open_price) / prev_close * 100
            vol_ratio = safe_get(row_t, 'vol_ratio', 1.0)
            
            # 分析近三日趋势（传入指数代码用于阈值差异化）
            try:
                trend_desc, trend_bias, warning = self._analyze_trend_bias(
                    row_t, row_t1, row_t2, auction_pct, vol_ratio, index_code=code
                )
            except Exception as e:
                print(f"⚠️ 分析 {name} 趋势出错: {e}")
                trend_desc, trend_bias, warning = "未知", "⚪观望", ""
            
            # 判断当日走势（使用差异化阈值）
            if code == '000001.SH':
                high_thresh, low_thresh = 0.2, -0.2
            elif code in ['399006.SZ', '000688.SH']:
                high_thresh, low_thresh = 0.5, -0.5
            else:
                high_thresh, low_thresh = 0.8, -0.8
            
            if auction_pct > high_thresh:
                if close_pct > auction_pct:
                    status = "🔥高开高走"
                elif body_pct < -0.3:
                    status = "⚠️高开低走"
                else:
                    status = "➡️高开平走"
            elif auction_pct < low_thresh:
                if body_pct > 0.3:
                    status = "🔺低开高走"
                elif close_pct < auction_pct:
                    status = "❄️低开低走"
                else:
                    status = "➡️低开平走"
            else:
                if body_pct > 0.3:
                    status = "📈平开高走"
                elif body_pct < -0.3:
                    status = "📉平开低走"
                else:
                    status = "➡️平开震荡"
            
            # 量能状态 & OAR（用量比近似）
            oar = vol_ratio
            if vol_ratio > 1.5:
                vol_desc = "极度放量"
            elif vol_ratio > 1.2:
                vol_desc = "放量"
            elif vol_ratio > 0.8:
                vol_desc = "平量"
            elif vol_ratio > 0.6:
                vol_desc = "缩量"
            else:
                vol_desc = "极度缩量"

            ai_insight = {}
            try:
                ai_context = IndexFeatureBuilder.build(
                    code=code,
                    name=name,
                    hist=hist,
                    row_t=row_t,
                    row_t1=row_t1,
                    row_t2=row_t2,
                    auction_pct=auction_pct,
                    close_pct=close_pct,
                    body_pct=body_pct,
                    vol_ratio=vol_ratio,
                )
                ai_insight = LocalIndexInterpreter.interpret(ai_context)
            except Exception as e:
                ai_insight = {
                    "label": "AI解读失败",
                    "bias": "观察",
                    "confidence": 0.0,
                    "evidence": [str(e)],
                    "watch_points": [],
                    "invalid_if": [],
                    "report_text": "",
                }
            
            results.append({
                '指数': name,
                'T-2': f"{safe_get(row_t2, 'pct', 0):+.2f}%" if row_t2 is not None else '-',
                'T-1': f"{safe_get(row_t1, 'pct', 0):+.2f}%" if row_t1 is not None else '-',
                '竞价': f"{auction_pct:+.2f}%",
                '收盘': f"{close_pct:+.2f}%",
                '实体': f"{body_pct:+.2f}%",
                'OAR': f"{oar:.2f}",
                '走势': status,
                '趋势': trend_desc,
                '研判': trend_bias,
                '警示': warning,
                'AI标签': ai_insight.get('label', '-'),
                'AI偏向': ai_insight.get('bias', '-'),
                'AI置信度': ai_insight.get('confidence', 0),
                'AI证据': ai_insight.get('evidence', []),
                'AI观察': ai_insight.get('watch_points', []),
                'AI失效': ai_insight.get('invalid_if', []),
                'AI解读': ai_insight.get('report_text', ''),
            })
        
        if not results:
            return pd.DataFrame()
        
        return pd.DataFrame(results)
    
    def _analyze_trend_bias(self, row_t, row_t1, row_t2, auction_pct, vol_ratio, index_code=None):
        """
        分析近三日趋势，结合今日竞价量价关系，给出偏多/偏空判断
        
        优化点：
        1. 指数与个股的阈值差异化（上证 vs 双创）
        2. 用量比近似OAR（竞价金额比）
        3. 量价背离警示
        
        返回:
            (趋势描述, 偏向判断, 警示信息)
        """
        if row_t1 is None:
            return "数据不足", "⚪观望", ""
        
        # ==================== 1. 阈值差异化 ====================
        # 根据指数类型设置不同阈值
        if index_code in ['000001.SH']:  # 上证指数
            high_open_thresh = 0.2   # 高开阈值
            strong_open_thresh = 0.5 # 强势高开
            low_open_thresh = -0.2   # 低开阈值
            vol_type = "主板"
        elif index_code in ['399006.SZ', '000688.SH']:  # 创业板、科创50
            high_open_thresh = 0.5
            strong_open_thresh = 1.0
            low_open_thresh = -0.5
            vol_type = "双创"
        elif index_code in ['899050.BJ']:  # 北证50
            high_open_thresh = 0.8
            strong_open_thresh = 1.5
            low_open_thresh = -0.8
            vol_type = "北证"
        else:  # 默认（ETF等）
            high_open_thresh = 0.3
            strong_open_thresh = 0.8
            low_open_thresh = -0.3
            vol_type = "ETF"
        
        # ==================== 2. 计算基础指标 ====================
        # 安全获取数值，确保是Python标量而非pandas对象
        def safe_get(row, key, default=0):
            if row is None:
                return default
            val = row.get(key, default) if hasattr(row, 'get') else row[key] if key in row else default
            if pd.isna(val):
                return default
            return float(val)
        
        pct_t1 = safe_get(row_t1, 'pct', 0)
        pct_t2 = safe_get(row_t2, 'pct', 0) if row_t2 is not None else 0
        
        # 昨日实体涨幅
        body_t1 = 0
        prev_close_t1 = safe_get(row_t1, 'prev_close', 0)
        if prev_close_t1 > 0:
            open_t1 = safe_get(row_t1, 'open', 0)
            close_t1 = safe_get(row_t1, 'close', 0)
            body_t1 = (close_t1 - open_t1) / prev_close_t1 * 100
        
        # 量能状态（用量比近似OAR）
        # OAR > 1.2 放量, 0.8-1.2 平量, < 0.8 缩量
        vol_ratio = float(vol_ratio) if not pd.isna(vol_ratio) else 1.0
        if vol_ratio > 1.5:
            vol_state = "极度放量"
            vol_score = 2
        elif vol_ratio > 1.2:
            vol_state = "放量"
            vol_score = 1
        elif vol_ratio > 0.8:
            vol_state = "平量"
            vol_score = 0
        elif vol_ratio > 0.6:
            vol_state = "缩量"
            vol_score = -1
        else:
            vol_state = "极度缩量"
            vol_score = -2
        
        # ==================== 3. 判断趋势状态 ====================
        # 趋势判断（优化：加入弱反弹、反弹夭折场景）
        if pct_t1 > 0.5 and pct_t2 > 0.5:
            trend = "Up"
            trend_desc = "连涨"
        elif pct_t1 < -0.5 and pct_t2 < -0.5:
            trend = "Down"
            trend_desc = "连跌"
        elif pct_t2 < -0.5 and pct_t1 > 0.5:
            # 前日跌，昨日涨 = 弱反弹
            trend = "WeakBounce"
            trend_desc = "弱反弹"
        elif pct_t2 > 0.5 and pct_t1 < -0.5:
            # 前日涨，昨日跌 = 反弹夭折
            trend = "FailedBounce"
            trend_desc = "反弹夭折"
        elif body_t1 > 1.5:
            trend = "Up"
            trend_desc = "昨大阳"
        elif body_t1 < -1.5:
            trend = "Down"
            trend_desc = "昨大阴"
        elif pct_t1 > 1.0:
            trend = "Up"
            trend_desc = "昨涨"
        elif pct_t1 < -1.0:
            trend = "Down"
            trend_desc = "昨跌"
        else:
            trend = "Range"
            trend_desc = "震荡"
        
        # 昨日K线形态描述
        if body_t1 > 1.5:
            pattern = "大阳线"
        elif body_t1 > 0.5:
            pattern = "阳线"
        elif body_t1 < -1.5:
            pattern = "大阴线"
        elif body_t1 < -0.5:
            pattern = "阴线"
        else:
            pattern = "十字星"
        
        # 完整趋势描述
        full_trend = f"{trend_desc}+{pattern}"
        
        # ==================== 4. 开盘缺口判断 ====================
        auction_pct = float(auction_pct) if not pd.isna(auction_pct) else 0
        if auction_pct > strong_open_thresh:
            gap_state = "强势高开"
        elif auction_pct > high_open_thresh:
            gap_state = "高开"
        elif auction_pct > -abs(low_open_thresh):
            gap_state = "平开"
        elif auction_pct > -strong_open_thresh:
            gap_state = "低开"
        else:
            gap_state = "大幅低开"
        
        # ==================== 5. 量价背离警示 ====================
        warning = ""
        
        # 缩量新高警示
        close_t = safe_get(row_t, 'close', 0)
        high_t = safe_get(row_t, 'high', close_t)
        high_t1 = safe_get(row_t1, 'high', 0) if row_t1 is not None else 0
        high_t2 = safe_get(row_t2, 'high', 0) if row_t2 is not None else 0
        high_3d = max(high_t, high_t1, high_t2)
        
        if high_3d > 0 and close_t >= high_3d * 0.995 and vol_ratio < 0.7:
            warning = "⚠️缩量新高"
        
        # 地量地价警示
        low_t = safe_get(row_t, 'low', close_t)
        low_t1 = safe_get(row_t1, 'low', float('inf')) if row_t1 is not None else float('inf')
        low_t2 = safe_get(row_t2, 'low', float('inf')) if row_t2 is not None else float('inf')
        low_3d = min(low_t, low_t1, low_t2)
        
        if low_3d < float('inf') and close_t <= low_3d * 1.005 and vol_ratio < 0.7:
            warning = "⚠️地量地价"
        
        # 极端情绪警报（双创特有）
        if vol_type in ["双创", "北证"] and abs(auction_pct) > 1.5:
            warning = "🚨极端情绪"
        
        # ==================== 6. 核心研判逻辑 ====================
        bias = self._get_bias_signal(trend, gap_state, vol_state, vol_ratio, 
                                      auction_pct, high_open_thresh, low_open_thresh)
        
        return full_trend, bias, warning
    
    def _get_bias_signal(self, trend, gap_state, vol_state, vol_ratio, 
                         auction_pct, high_thresh, low_thresh):
        """
        根据趋势、缺口、量能生成偏向信号
        
        场景逻辑（优化版）：
        A: 强势进攻 (昨大阳/连涨 + 高开)
        B: 弱势反转 (昨大阴/连跌 + 高开) - 关键博弈点
        C: 恐慌延续 (昨大阴/连跌 + 低开)
        D: 获利回吐 (昨大阳/连涨 + 低开)
        E: 弱反弹分化 (前日跌+昨日涨)
        F: 反弹夭折延续 (前日涨+昨日跌)
        G: 震荡突破/破位
        """
        
        # ========== 场景A: 强势进攻 (上涨趋势 + 高开) ==========
        if trend == "Up" and auction_pct > high_thresh:
            if vol_ratio > 1.2:
                return "🟢强更强(增量逼空，顺势做多)"
            elif vol_ratio < 0.8:
                # 指数缩量高开 = 一致性预期极强
                return "🟡缩量加速(一致预期，破开盘价则止盈)"
            else:
                return "🟢温和接力(健康上涨)"
        
        # ========== 场景B: 弱势反转 (下跌趋势 + 高开) - 关键博弈点 ==========
        elif trend == "Down" and auction_pct > high_thresh:
            if vol_ratio > 1.5:
                # 需要更大的放量确认
                return "🟢暴力反核(主力进场，日内反转信号)"
            elif vol_ratio < 0.8:
                # 无量高开 = 骗炮
                return "🔴骗炮诱多！(无量空拉，警惕回落杀跌)"
            else:
                return "🟡弱反修复(观察能否站稳分时均线)"
        
        # ========== 场景C: 恐慌延续 (下跌趋势 + 低开) ==========
        elif trend == "Down" and auction_pct < -abs(low_thresh):
            if vol_ratio > 1.5:
                # 带量下杀可能是恐慌出清
                return "🟡恐慌出清(带量下杀，关注30分V型底)"
            elif vol_ratio < 0.8:
                # 缩量阴跌最危险
                return "🔴阴跌无底(流动性枯竭，坚决回避)"
            else:
                return "🔴惯性下跌(趋势延续)"
        
        # ========== 场景D: 获利回吐 (上涨趋势 + 低开) ==========
        elif trend == "Up" and auction_pct < -abs(low_thresh):
            if vol_ratio > 1.2:
                # 放量低开 = 主力出货
                return "🔴乌云盖顶！(主力借竞价出货，日内看空)"
            elif vol_ratio < 0.8:
                # 缩量低开 = 洗盘
                return "🟡良性回踩(缩量洗盘，关注昨收支撑)"
            else:
                return "🟡正常调整(消化获利盘)"
        
        # ========== 场景E: 弱反弹分化 (前日跌+昨日涨) ==========
        elif trend == "WeakBounce":
            if auction_pct > high_thresh:
                if vol_ratio > 1.2:
                    return "🟢反弹确认(放量高开，有望延续)"
                else:
                    return "🟡反弹待验(缩量高开，等待确认)"
            elif auction_pct < -abs(low_thresh):
                return "🔴反弹夭折(低开回落，趋势延续下跌)"
            else:
                if vol_ratio > 1.2:
                    return "🟡多空争夺(放量平开，观察方向)"
                else:
                    return "🟡弱反观察(平开缩量，等待信号)"
        
        # ========== 场景F: 反弹夭折延续 (前日涨+昨日跌) ==========
        elif trend == "FailedBounce":
            if auction_pct > high_thresh:
                if vol_ratio > 1.5:
                    return "🟢止跌反击(强势高开，主力护盘)"
                else:
                    return "🟡反弹乏力(高开缩量，持续性存疑)"
            elif auction_pct < -abs(low_thresh):
                return "🔴加速下跌(低开破位，趋势恶化)"
            else:
                return "🟡弱势震荡(等待方向明确)"
        
        # ========== 场景G: 震荡市突破/破位 ==========
        elif trend == "Range":
            if auction_pct > high_thresh:
                if vol_ratio > 1.2:
                    return "🟢向上突破(放量确认，偏多)"
                else:
                    return "🟡假突破?(缩量高开，等9:45确认)"
            elif auction_pct < -abs(low_thresh):
                if vol_ratio > 1.2:
                    return "🔴向下破位(放量确认，偏空)"
                else:
                    return "🟡假破位?(缩量低开，等9:45确认)"
            else:
                if vol_ratio < 0.7:
                    return "⚪缩量震荡(方向不明，观望)"
                else:
                    return "⚪震荡等待(9:45后确认方向)"
        
        # ========== 默认：平开情况 ==========
        else:
            if trend == "Up":
                if vol_ratio > 1.2:
                    return "🟡放量平开(多空分歧，观察方向)"
                elif vol_ratio < 0.8:
                    return "🟡缩量平开(消化涨幅，正常)"
                else:
                    return "🟡平开整理(涨势放缓)"
            elif trend == "Down":
                if vol_ratio > 1.2:
                    return "🟡放量平开(止跌信号，关注)"
                elif vol_ratio < 0.8:
                    return "🟡缩量平开(空头衰竭，可能企稳)"
                else:
                    return "🟡平开观察(等待方向)"
            else:
                return "⚪继续震荡(无明确方向)"
    
    def _calc_auction_metrics(self, df, df_auction=None, df_noon=None):
        """
        计算竞价相关指标
        
        核心公式：
        - 竞价涨幅 = (open - prev_close) / prev_close * 100
        - 午盘涨幅 = (noon_price - prev_close) / prev_close * 100
        - 实体涨跌 = (close - open) / prev_close * 100
        """
        # 确保有prev_close
        if 'prev_close' not in df.columns:
            print("⚠️ 缺少 prev_close 列")
            return df
        
        # 竞价涨幅 = 开盘涨幅（集合竞价结束价 = 开盘价）
        valid_mask = (df['prev_close'] > 0) & df['prev_close'].notna()
        
        df['auction_pct'] = np.nan
        df.loc[valid_mask, 'auction_pct'] = (
            (df.loc[valid_mask, 'open'] - df.loc[valid_mask, 'prev_close']) 
            / df.loc[valid_mask, 'prev_close'] * 100
        )
        
        # 实体涨跌 = 日内涨跌
        df['body_pct'] = np.nan
        df.loc[valid_mask, 'body_pct'] = (
            (df.loc[valid_mask, 'close'] - df.loc[valid_mask, 'open']) 
            / df.loc[valid_mask, 'prev_close'] * 100
        )
        
        # 合并竞价分钟数据（如果有）
        if df_auction is not None and not df_auction.empty:
            # Opening-auction price is the matched open. Minute fallback close is
            # already contaminated by the first continuous-trading minute.
            auction_price_col = next(
                (column for column in ('auction_price', 'open', 'last', 'close') if column in df_auction.columns),
                None,
            )
            auction_amt_col = 'amount' if 'amount' in df_auction.columns else None
            if auction_price_col is None:
                return df
            
            df_auction_slim = df_auction[['code', auction_price_col]].copy()
            if auction_amt_col:
                df_auction_slim['auction_amount_raw'] = df_auction[auction_amt_col]
            for column in ('auction_source', 'auction_amount_exact', 'auction_asof'):
                if column in df_auction.columns:
                    df_auction_slim[column] = df_auction[column]
            df_auction_slim = df_auction_slim.rename(columns={auction_price_col: 'auction_price'})
            
            df = df.merge(df_auction_slim, on='code', how='left')
            
            # 如果有竞价成交额，计算真实竞价占比
            if 'auction_amount_raw' in df.columns:
                df['auction_amount'] = df['auction_amount_raw'].fillna(0)
            else:
                # 估算：竞价成交额约占全天2-5%，根据开盘涨幅调整
                auction_ratio = 0.02 + df['auction_pct'].abs() * 0.005
                auction_ratio = auction_ratio.clip(0.01, 0.10)
                df['auction_amount'] = df['amount'] * auction_ratio
        else:
            # 无分钟数据时，根据开盘涨幅估算竞价占比
            # 涨幅越大，竞价越活跃
            auction_ratio = 0.02 + df['auction_pct'].abs() * 0.005
            auction_ratio = auction_ratio.clip(0.01, 0.10)
            df['auction_amount'] = df['amount'] * auction_ratio
        
        # 合并午盘数据（如果有）
        df['noon_pct'] = np.nan
        if df_noon is not None and not df_noon.empty:
            noon_price_col = 'close' if 'close' in df_noon.columns else 'last'
            df_noon_slim = df_noon[['code', noon_price_col]].copy()
            df_noon_slim = df_noon_slim.rename(columns={noon_price_col: 'noon_price'})
            
            df = df.merge(df_noon_slim, on='code', how='left')
            
            # 计算午盘涨幅
            if 'noon_price' in df.columns:
                noon_valid = valid_mask & df['noon_price'].notna() & (df['noon_price'] > 0)
                df.loc[noon_valid, 'noon_pct'] = (
                    (df.loc[noon_valid, 'noon_price'] - df.loc[noon_valid, 'prev_close']) 
                    / df.loc[noon_valid, 'prev_close'] * 100
                )
        
        return df
    
    def _analyze_etf_auction(self, df_indices):
        """
        ETF竞价监控
        
        返回:
            DataFrame: ETF竞价状态
        """
        if df_indices.empty:
            return pd.DataFrame()
        
        results = []
        for code, name in MarketConfig.THEME_ETFS.items():
            row = df_indices[df_indices['code'] == code]
            if row.empty:
                continue
            row = row.iloc[0]
            
            # 计算指标
            prev_close = row.get('prev_close', 0)
            if prev_close <= 0:
                continue
            
            open_price = row['open']
            close_price = row['close']
            
            auction_pct = (open_price - prev_close) / prev_close * 100
            close_pct = row.get('pct', 0)
            body_pct = (close_price - open_price) / prev_close * 100  # 实体涨幅
            vol_ratio = row.get('vol_ratio', 1.0)
            
            # 判断状态（阈值：高开/低开 0.2%，平开 -0.2%~0.2%）
            if auction_pct > 0.2:  # 高开
                if close_pct > auction_pct:
                    status = "🔥高开高走"
                elif close_pct < auction_pct - 0.3:
                    status = "⚠️高开低走"
                else:
                    status = "➡️高开平走"
            elif auction_pct < -0.2:  # 低开
                if close_pct > auction_pct + 0.3:
                    status = "🔺低开高走"
                elif close_pct < auction_pct:
                    status = "❄️低开低走"
                else:
                    status = "➡️低开平走"
            else:  # 平开 (-0.2% ~ 0.2%)
                if body_pct > 0.3:
                    status = "📈平开高走"
                elif body_pct < -0.3:
                    status = "📉平开低走"
                else:
                    status = "➡️平开震荡"
            
            results.append({
                'ETF': name,
                '竞价涨幅': round(auction_pct, 2),
                '收盘涨跌': round(close_pct, 2),
                '实体涨幅': round(body_pct, 2),
                '量比': round(vol_ratio, 2),
                '状态': status
            })
        
        if not results:
            return pd.DataFrame()
        
        df = pd.DataFrame(results)
        # 按实体涨幅绝对值排序
        df['abs_body'] = df['实体涨幅'].abs()
        df = df.sort_values('abs_body', ascending=False)
        df = df.drop(columns=['abs_body'])
        return df
    
    def _calc_industry_auction(self, df):
        """
        计算行业竞价排行
        
        返回:
            DataFrame: 行业竞价排行榜
        """
        if 'industry' not in df.columns:
            print("⚠️ 缺少行业字段")
            return pd.DataFrame()
        
        # 过滤有效数据
        valid_df = df[df['auction_pct'].notna() & (df['auction_pct'] > -99)].copy()
        
        if valid_df.empty:
            print("⚠️ 无有效竞价数据")
            return pd.DataFrame()
        
        # 行业聚合
        agg_cols = {
            'auction_amount': 'sum',      # 竞价额
            'amount': 'sum',              # 日成交额
            'auction_pct': 'mean',        # 竞价涨幅均值
            'pct': 'mean',                # 收盘涨跌均值
            'body_pct': 'mean',           # 实体涨跌均值
            'code': 'count'               # 个股数
        }
        
        # 如果有午盘涨幅，也聚合
        if 'noon_pct' in valid_df.columns and valid_df['noon_pct'].notna().any():
            agg_cols['noon_pct'] = 'mean'
        
        agg = valid_df.groupby('industry').agg(agg_cols).reset_index()
        agg = agg.rename(columns={'code': 'stock_count'})
        
        # 过滤小行业
        agg = agg[agg['stock_count'] >= AuctionConfig.MIN_STOCK_COUNT]
        
        # 计算竞价占比
        agg['auction_ratio'] = agg['auction_amount'] / agg['amount'] * 100
        
        # 排序
        agg = agg.sort_values('auction_amount', ascending=False)
        
        # 格式化输出
        result_dict = {
            '板块名称': agg['industry'],
            '竞价额(亿)': (agg['auction_amount'] / 1e8).round(2),
            '竞价占比(%)': agg['auction_ratio'].round(2),
            '竞价涨幅(%)': agg['auction_pct'].round(2),
        }
        
        # 如果有午盘涨幅，添加到结果
        if 'noon_pct' in agg.columns:
            result_dict['午盘涨幅(%)'] = agg['noon_pct'].round(2)
        
        result_dict['收盘涨跌(%)'] = agg['pct'].round(2)
        result_dict['实体涨跌(%)'] = agg['body_pct'].round(2)
        result_dict['个股数'] = agg['stock_count'].astype(int)
        
        result = pd.DataFrame(result_dict)
        
        return result.head(AuctionConfig.TOP_INDUSTRY_COUNT)
    
    def _find_reversal_industries(self, df):
        """
        发现行业走势特征
        
        包含：
        - 🔥高开高走：竞价涨，收盘继续涨
        - ⚠️高开低走：竞价涨，收盘跌
        - 🔺低开高走：竞价跌，收盘涨
        - ❄️低开低走：竞价跌，收盘继续跌
        - 📈平开高走：竞价平，收盘涨
        - 📉平开低走：竞价平，收盘跌
        """
        if 'industry' not in df.columns:
            return pd.DataFrame()
        
        # 过滤有效数据
        valid_df = df[df['auction_pct'].notna() & (df['auction_pct'] > -99)].copy()
        
        if valid_df.empty:
            return pd.DataFrame()
        
        # 行业聚合
        agg = valid_df.groupby('industry').agg({
            'auction_pct': 'mean',
            'pct': 'mean',
            'body_pct': 'mean',
            'code': 'count'
        }).reset_index()
        
        agg = agg.rename(columns={'code': 'stock_count'})
        agg = agg[agg['stock_count'] >= AuctionConfig.MIN_STOCK_COUNT]
        
        # 判断走势类型（阈值：高开/低开 0.15%，平开 -0.15%~0.15%）
        def get_trend_type(row):
            auction = row['auction_pct']
            close = row['pct']
            body = row['body_pct']
            
            if auction > 0.15:  # 高开
                if close > auction:
                    return "🔥高开高走"
                elif body < -0.3:
                    return "⚠️高开低走"
                else:
                    return "➡️高开平走"
            elif auction < -0.15:  # 低开
                if body > 0.3:
                    return "🔺低开高走"
                elif close < auction:
                    return "❄️低开低走"
                else:
                    return "➡️低开平走"
            else:  # 平开
                if body > 0.3:
                    return "📈平开高走"
                elif body < -0.3:
                    return "📉平开低走"
                else:
                    return "➡️平开震荡"
        
        agg['类型'] = agg.apply(get_trend_type, axis=1)
        
        # 过滤掉平开震荡（不够有特点）
        reversals = agg[agg['类型'] != '➡️平开震荡'].copy()
        
        if reversals.empty:
            return pd.DataFrame()
        
        # 按实体涨幅绝对值排序
        reversals['abs_body'] = reversals['body_pct'].abs()
        reversals = reversals.sort_values('abs_body', ascending=False)
        
        # 格式化输出
        result = pd.DataFrame({
            '行业': reversals['industry'],
            '竞价涨幅': reversals['auction_pct'].round(2),
            '收盘涨跌': reversals['pct'].round(2),
            '实体涨幅': reversals['body_pct'].round(2),
            '个股数': reversals['stock_count'].astype(int),
            '类型': reversals['类型']
        })
        
        return result
    
    def _calc_industry_correlation(self, df):
        """
        计算行业竞价与收盘的相关性
        
        相关性高 = 竞价表现好的股票收盘也好（动量延续）
        相关性低 = 竞价与收盘无关（日内反转）
        """
        if 'industry' not in df.columns:
            return pd.DataFrame()
        
        # 过滤有效数据
        valid_df = df[
            df['auction_pct'].notna() & 
            df['pct'].notna() & 
            (df['auction_pct'] > -99)
        ].copy()
        
        if valid_df.empty:
            return pd.DataFrame()
        
        results = []
        for industry, group in valid_df.groupby('industry'):
            if len(group) < AuctionConfig.MIN_STOCK_COUNT:
                continue
            
            # 计算相关性（需要方差非零）
            auction_std = group['auction_pct'].std()
            close_std = group['pct'].std()
            
            if auction_std > 0.01 and close_std > 0.01:
                corr = group['auction_pct'].corr(group['pct'])
            else:
                corr = np.nan
            
            results.append({
                '行业': industry,
                '相关性': round(corr, 3) if not np.isnan(corr) else np.nan,
                '样本数': len(group),
                '竞价均值': round(group['auction_pct'].mean(), 2),
                '收盘均值': round(group['pct'].mean(), 2)
            })
        
        if not results:
            return pd.DataFrame()
        
        result = pd.DataFrame(results)
        
        # 过滤掉NaN，按相关性排序
        valid_result = result[result['相关性'].notna()]
        valid_result = valid_result.sort_values('相关性', ascending=False)
        
        return valid_result
