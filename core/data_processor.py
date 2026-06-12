# -*- coding: utf-8 -*-
"""
数据处理器 - 指标计算和数据预处理
"""

import pandas as pd
import numpy as np
from config.settings import AuctionConfig, TechConfig


class DataProcessor:
    """数据预处理和指标计算"""

    @staticmethod
    def mark_price_discontinuities(df):
        """Mark ex-rights/stale-pre-close style gaps that must not enter CP/SA."""
        if df.empty:
            return df

        work = df.copy()
        code = work.get('code', pd.Series('', index=work.index)).fillna('').astype(str)
        name = work.get('name', pd.Series('', index=work.index)).fillna('').astype(str)
        auction_pct = pd.to_numeric(
            work.get('auction_pct', pd.Series(np.nan, index=work.index)),
            errors='coerce',
        )
        auction_price = pd.to_numeric(
            work.get('auction_price', work.get('open', pd.Series(np.nan, index=work.index))),
            errors='coerce',
        )
        prev_close = pd.to_numeric(
            work.get('prev_close', work.get('pre_close', pd.Series(np.nan, index=work.index))),
            errors='coerce',
        )

        limit = pd.Series(AuctionConfig.PRICE_DISCONTINUITY_LIMIT_MAIN, index=work.index)
        limit.loc[name.str.upper().str.contains('ST', na=False)] = AuctionConfig.PRICE_DISCONTINUITY_LIMIT_ST
        limit.loc[code.str.startswith(('300', '301', '688'))] = AuctionConfig.PRICE_DISCONTINUITY_LIMIT_GEM_STAR
        limit.loc[code.str.startswith(('4', '8'))] = AuctionConfig.PRICE_DISCONTINUITY_LIMIT_BSE

        work['price_discontinuity_limit_pct'] = limit
        no_matched_open = prev_close.gt(0) & (auction_price.isna() | (auction_price <= 0))
        gap_exceeds_limit = auction_pct.abs() > limit
        work['price_discontinuity'] = no_matched_open | gap_exceeds_limit
        work['price_discontinuity_reason'] = ''
        work.loc[no_matched_open, 'price_discontinuity_reason'] = 'no_matched_auction_price'
        work.loc[gap_exceeds_limit, 'price_discontinuity_reason'] = (
            work.loc[gap_exceeds_limit, 'price_discontinuity_reason']
            .replace('', 'auction_gap_exceeds_board_limit_or_preclose_stale')
        )
        return work
    
    @staticmethod
    def calc_indicators(df_window):
        """
        计算技术指标（兼容旧接口）
        """
        return DataProcessor.calc_basic_indicators(df_window)
    
    @staticmethod
    def calc_basic_indicators(df_window):
        """
        计算基础技术指标
        适用于个股和指数/ETF
        
        重要：优先使用API返回的pre_close（昨收价），
        只有在没有pre_close时才用shift计算
        """
        if df_window.empty:
            return df_window
            
        df = df_window.copy()
        df = df.sort_values(['code', 'date_int'])
        
        # 前日收盘价 - 优先使用API的pre_close，缺失时用shift补充
        # 先用shift计算（作为备选值）
        df['prev_close_shift'] = df.groupby('code')['close'].shift(1)
        
        if 'pre_close' in df.columns and df['pre_close'].notna().any():
            # 优先使用API的pre_close
            df['prev_close'] = df['pre_close']
            # 对于pre_close为NaN的行，用shift补充
            mask_na = df['prev_close'].isna()
            df.loc[mask_na, 'prev_close'] = df.loc[mask_na, 'prev_close_shift']
        else:
            # 完全没有pre_close，用shift计算
            df['prev_close'] = df['prev_close_shift']
        
        df = df.drop(columns=['prev_close_shift'])
        
        # 其他前日数据（仍用shift，这些不涉及除权）
        df['prev_amt'] = df.groupby('code')['amount'].shift(1)
        df['prev_open'] = df.groupby('code')['open'].shift(1)
        df['prev_high'] = df.groupby('code')['high'].shift(1)
        df['prev_low'] = df.groupby('code')['low'].shift(1)
        
        # 涨跌幅（如果没有pct列）
        if 'pct' not in df.columns:
            df['pct'] = 0.0
            mask = (df['prev_close'] > 0)
            df.loc[mask, 'pct'] = (df.loc[mask, 'close'] - df.loc[mask, 'prev_close']) / df.loc[mask, 'prev_close'] * 100
        
        # 量比
        df['vol_ratio'] = 1.0
        mask_v = (df['prev_amt'] > 0)
        df.loc[mask_v, 'vol_ratio'] = df.loc[mask_v, 'amount'] / df.loc[mask_v, 'prev_amt']
        
        # 涨停判断
        df = DataProcessor._calc_limit_up(df)
        
        # 前日涨停状态
        df['prev_is_limit_up'] = df.groupby('code')['is_limit_up'].shift(1).fillna(False)
        
        return df
    
    @staticmethod
    def _calc_limit_up(df):
        """计算涨停状态"""
        if 'high_limit' in df.columns:
            valid_limit = df['high_limit'].notnull() & (df['high_limit'] > 0)
            df['is_limit_up'] = False
            df.loc[valid_limit, 'is_limit_up'] = df.loc[valid_limit, 'close'] >= \
                (df.loc[valid_limit, 'high_limit'] - TechConfig.LIMIT_UP_MARGIN)
        else:
            # 根据代码推断涨跌停幅度
            cond_30cm = df['code'].str.startswith('8') | df['code'].str.startswith('4')
            cond_20cm = df['code'].str.startswith('688') | df['code'].str.startswith('30')
            df['limit_thresh'] = 9.9
            df.loc[cond_20cm, 'limit_thresh'] = 19.9
            df.loc[cond_30cm, 'limit_thresh'] = 29.9 
            df['is_limit_up'] = df['pct'] >= df['limit_thresh']
        
        return df
    
    @staticmethod
    def calc_industry_aggregates(df_stocks, date_list=None):
        """
        计算行业级别聚合指标
        
        返回:
            DataFrame: 行业-日期级别的聚合数据
        """
        if df_stocks.empty:
            return pd.DataFrame()
        
        agg = df_stocks.groupby(['date_int', 'industry']).agg({
            'is_limit_up': 'sum',
            'amount': 'sum',
            'close': 'mean',
            'open': 'mean',
            'pct': 'mean',
            'code': 'count'
        }).reset_index()
        
        agg = agg.rename(columns={'code': 'stock_count'})
        
        # 计算行业量比
        agg.sort_values(['industry', 'date_int'], inplace=True)
        agg['prev_amt'] = agg.groupby('industry')['amount'].shift(1)
        agg['vol_ratio'] = agg['amount'] / agg['prev_amt']
        agg['vol_ratio'] = agg['vol_ratio'].fillna(1.0)
        
        # 计算行业强度 = 成交额(亿) * 涨幅
        agg['strength'] = (agg['amount'] / 1e8) * agg['pct']
        
        return agg
    
    @staticmethod
    def merge_auction_with_daily(df_auction, df_daily):
        """
        合并竞价数据与日线数据
        
        返回:
            DataFrame: 合并后的数据，包含竞价和日线指标
        """
        if df_auction.empty or df_daily.empty:
            return pd.DataFrame()
        
        # 标准化竞价数据列名
        auction_price_col = next(
            (column for column in ('auction_price', 'open', 'last', 'close') if column in df_auction.columns),
            None,
        )
        if auction_price_col is None:
            return pd.DataFrame()
        
        auction_cols = ['code', auction_price_col, 'amount', 'pre_close']
        auction_cols += [
            column for column in ('auction_source', 'auction_amount_exact', 'auction_asof')
            if column in df_auction.columns
        ]
        auction_cols = [c for c in auction_cols if c in df_auction.columns]
        df_a = df_auction[auction_cols].copy()
        df_a = df_a.rename(columns={auction_price_col: 'auction_price', 'amount': 'auction_amount'})
        
        # 准备日线数据
        daily_cols = ['code', 'open', 'close', 'high', 'low', 'amount', 'pre_close', 'pct', 'industry', 'name']
        daily_cols = [c for c in daily_cols if c in df_daily.columns]
        df_d = df_daily[daily_cols].copy()
        df_d = df_d.rename(columns={'amount': 'daily_amount', 'close': 'daily_close'})
        
        # 合并
        merged = pd.merge(df_a, df_d, on='code', how='inner', suffixes=('_auc', '_day'))
        
        if merged.empty:
            return merged
        
        # 使用日线的pre_close
        if 'pre_close_day' in merged.columns:
            merged['pre_close'] = merged['pre_close_day']
        elif 'pre_close_auc' in merged.columns:
            merged['pre_close'] = merged['pre_close_auc']
        
        # 计算派生指标
        merged['auction_pct'] = (merged['auction_price'] - merged['pre_close']) / merged['pre_close'] * 100
        merged['auction_ratio'] = merged['auction_amount'] / merged['daily_amount'] * 100
        merged['close_pct'] = (merged['daily_close'] - merged['pre_close']) / merged['pre_close'] * 100
        merged['close_body'] = (merged['daily_close'] - merged['open']) / merged['pre_close'] * 100
        
        return merged
