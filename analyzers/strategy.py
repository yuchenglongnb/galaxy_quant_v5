# -*- coding: utf-8 -*-
"""
策略分析器 - 盘后复盘核心逻辑
包含：指数环境、ETF资金风向、行业主线、核心龙头矩阵
"""

import pandas as pd
import numpy as np

from analyzers.base import BaseAnalyzer
from analyzers.technical import TechnicalAnalyzer
from core.data_processor import DataProcessor
from config.settings import MarketConfig, StrategyConfig


class StrategyAnalyzer(BaseAnalyzer):
    """策略分析器 - 盘后全景复盘"""
    
    def analyze(self, target_date, **kwargs):
        """
        执行盘后复盘分析
        
        参数:
            target_date: 目标日期
            valid_days: 有效交易日列表（至少3天）
            
        返回:
            dict: 包含各层级分析结果
        """
        valid_days = kwargs.get('valid_days', [target_date])
        
        if len(valid_days) < 3:
            print("⚠️ 交易日数据不足，至少需要3天")
            return None
        
        # 加载数据
        df_stocks = self.dm.load_stocks(valid_days)
        df_indices = self.dm.load_indices(valid_days)
        
        if df_stocks.empty or df_indices.empty:
            print("⚠️ 数据加载失败")
            return None
        
        # 计算指标
        df_stocks = DataProcessor.calc_indicators(df_stocks)
        df_indices = DataProcessor.calc_indicators(df_indices)
        
        # 各层级分析
        indices_result = self._analyze_indices_trend(df_indices, valid_days)
        top_etf, bot_etf = self._analyze_etf_monitor(df_indices, valid_days)
        mainlines = self._analyze_mainline_industries(df_stocks, valid_days)
        
        mainline_names = [x['industry'] for x in mainlines]
        core_matrix = self._analyze_core_matrix(df_stocks, valid_days, mainline_names)
        
        return {
            'date': target_date,
            'indices': indices_result,
            'etf_top': top_etf,
            'etf_bottom': bot_etf,
            'mainlines': mainlines,
            'core_matrix': core_matrix
        }
    
    def _analyze_indices_trend(self, df_indices, valid_days):
        """Level 1: 指数环境分析"""
        T, T_1, T_2 = valid_days[-1], valid_days[-2], valid_days[-3]
        results = []
        total_score = 0
        
        for code, name in MarketConfig.MAIN_INDICES.items():
            hist = df_indices[df_indices['code'] == code].sort_values('date_int')
            if hist.empty or T not in hist['date_int'].values: 
                continue
            
            row_t = hist[hist['date_int'] == T].iloc[0]
            row_t1 = hist[hist['date_int'] == T_1].iloc[0] if T_1 in hist['date_int'].values else None
            
            env_score = TechnicalAnalyzer.calc_env_score(row_t['pct'], row_t['vol_ratio'])
            total_score += env_score
            
            trend_tag = TechnicalAnalyzer.get_advanced_trend_tag(row_t, row_t1, hist)
            advice = TechnicalAnalyzer.get_strategy_advice(trend_tag, row_t['pct'], row_t['vol_ratio'])
            
            def format_day(row):
                if row is None: return "-"
                v_status = "缩量" if row['vol_ratio'] < 0.8 else ("放量" if row['vol_ratio'] > 1.2 else "温和")
                return f"{row['pct']:+.2f}% {v_status}"
                
            results.append({
                "name": name,
                "T_2": format_day(hist[hist['date_int'] == T_2].iloc[0] if T_2 in hist['date_int'].values else None),
                "T_1": format_day(row_t1),
                "T": format_day(row_t),
                "trend": trend_tag,
                "advice": advice
            })
        
        if total_score >= 3: 
            judgement = "🟢 环境安全 (积极做多)"
        elif total_score <= -3: 
            judgement = "🔴 环境恶劣 (空仓观望)"
        else: 
            judgement = "🟡 震荡环境 (轻指数重个股)"
        
        return {"judgement": judgement, "total_score": round(total_score, 1), "details": results}

    def _analyze_etf_monitor(self, df_indices, date_list):
        """Level 2: ETF资金风向"""
        T = date_list[-1]
        T_1 = date_list[-2] if len(date_list) > 1 else None
        
        res = []
        for code, name in MarketConfig.THEME_ETFS.items():
            seq = df_indices[df_indices['code'] == code].sort_values('date_int')
            if seq.empty: 
                continue
            row_t = seq[seq['date_int'] == T]
            if row_t.empty: 
                continue
            row_t = row_t.iloc[0]
            row_prev = seq[seq['date_int'] == T_1].iloc[0] if T_1 and T_1 in seq['date_int'].values else None
            
            status = TechnicalAnalyzer.get_sector_trend_tag(row_t, row_prev, seq)
            
            res.append({
                "name": name,
                "raw_pct": row_t['pct'],
                "pct": f"{row_t['pct']:+.2f}%",
                "vol": f"{row_t['vol_ratio']:.1f}",
                "status": status
            })
        
        res.sort(key=lambda x: x['raw_pct'], reverse=True)
        top_4 = res[:4]
        bottom_4 = res[-4:] if len(res) >= 8 else res[-4:]
        
        for item in bottom_4:
            item['status'] = "" 
            
        return top_4, bottom_4

    def _analyze_mainline_industries(self, df_stocks, valid_days):
        """Level 3: 行业主线追踪"""
        T = valid_days[-1]
        T_1 = valid_days[-2] if len(valid_days) > 1 else None
        T_2 = valid_days[-3] if len(valid_days) > 2 else None
        
        agg_full = DataProcessor.calc_industry_aggregates(df_stocks, valid_days)
        
        agg_t = agg_full[agg_full['date_int'] == T].copy()
        
        mainlines = agg_t[agg_t['amount'] > StrategyConfig.MAINLINE_AMOUNT]\
                          .sort_values('strength', ascending=False).head(5)
        
        results = []
        for _, row in mainlines.iterrows():
            ind_name = row['industry']
            ind_seq = agg_full[agg_full['industry'] == ind_name].sort_values('date_int')
            
            def get_ind_tag(d_int):
                if d_int not in ind_seq['date_int'].values: 
                    return "-", 0
                
                pos_arr = np.where(ind_seq['date_int'].values == d_int)[0]
                if len(pos_arr) == 0: 
                    return "-", 0
                pos = pos_arr[0]
                
                curr = ind_seq.iloc[pos]
                prev = ind_seq.iloc[pos - 1] if pos > 0 else None
                
                tag = TechnicalAnalyzer.get_sector_trend_tag(curr, prev, ind_seq)
                return f"{curr['pct']:+.1f}% ({int(curr['is_limit_up'])}板) {tag}", int(curr['is_limit_up'])
                
            t2_str, _ = get_ind_tag(T_2)
            t1_str, _ = get_ind_tag(T_1)
            t_str, lu_cnt = get_ind_tag(T)
            
            results.append({
                "industry": ind_name,
                "T_2": t2_str,
                "T_1": t1_str,
                "T": t_str,
                "strength": int(row['strength']),
                "limit_up_cnt": lu_cnt
            })
            
        return results

    def _analyze_core_matrix(self, df_stocks, valid_days, mainline_industries):
        """Level 4: 核心龙头矩阵"""
        T = valid_days[-1]
        df_t = df_stocks[df_stocks['date_int'] == T].copy()
        
        cond_liquidity = (df_t['amount'] > StrategyConfig.MIN_AMOUNT)
        cond_mainline = df_t['industry'].isin(mainline_industries)
        
        # 策略A: 连板/涨停核心
        cond_limit = (df_t['is_limit_up']) | (df_t['prev_is_limit_up'])
        pool_a = df_t[cond_liquidity & cond_mainline & cond_limit].copy()
        pool_a['score'] = pool_a['pct'] * 10
        pool_a.loc[pool_a['is_limit_up'], 'score'] += 100
        pool_a.loc[pool_a['is_limit_up'] & pool_a['prev_is_limit_up'], 'score'] += 200
        
        # 策略B: 权重/中军核心
        cond_trend = (df_t['pct'] > 3.0)
        pool_b = df_t[cond_liquidity & cond_mainline & cond_trend].copy()
        pool_b['weight_score'] = (pool_b['amount'] / 1e8) * pool_b['pct']
        
        top_a = pool_a.sort_values('score', ascending=False).head(StrategyConfig.TOP_LIMIT_COUNT)['code'].tolist()
        top_b = pool_b.sort_values('weight_score', ascending=False).head(StrategyConfig.TOP_WEIGHT_COUNT)['code'].tolist()
        
        # 去重
        final_codes = []
        seen = set()
        for c in top_a:
            if c not in seen:
                final_codes.append(c)
                seen.add(c)
        for c in top_b:
            if c not in seen:
                final_codes.append(c)
                seen.add(c)
        
        # 生成矩阵
        matrix = []
        for code in final_codes:
            hist = df_stocks[df_stocks['code'] == code].sort_values('date_int')
            if T not in hist['date_int'].values: 
                continue
            
            row_t = hist[hist['date_int'] == T].iloc[0]
            
            def get_day_tag(d_int):
                if d_int not in hist['date_int'].values: 
                    return "-"
                idx = hist[hist['date_int'] == d_int].index[0]
                curr = hist.loc[idx]
                prev = None
                pos = hist.index.get_loc(idx)
                if pos > 0: 
                    prev = hist.iloc[pos-1]
                    
                tag = TechnicalAnalyzer.get_advanced_trend_tag(curr, prev, hist)
                return f"{curr['pct']:+.1f}% {tag}"
                
            stock_name = row_t.get('name', str(code))
            if pd.isna(stock_name): 
                stock_name = str(code)
            
            s_type = "🚀龙头" if code in top_a else "🐘中军"
            
            matrix.append({
                "code": code,
                "name": str(stock_name)[:4],
                "amount": f"{int(row_t['amount']/1e8)}亿",
                "T_2": get_day_tag(valid_days[-3]) if len(valid_days) > 2 else "-",
                "T_1": get_day_tag(valid_days[-2]) if len(valid_days) > 1 else "-",
                "T": get_day_tag(T),
                "concept": row_t['industry'][:6],
                "type": s_type
            })
            
        return matrix
