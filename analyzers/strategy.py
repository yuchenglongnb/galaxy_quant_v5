# -*- coding: utf-8 -*-
"""
Post-close strategy analyzer.

This module powers the panoramic review report:
1. broad index environment
2. ETF capital leadership
3. mainline industry tracking
4. core leader matrix
"""

import numpy as np
import pandas as pd

from analyzers.base import BaseAnalyzer
from analyzers.technical import TechnicalAnalyzer
from config.settings import MarketConfig, StrategyConfig
from core.data_processor import DataProcessor


class StrategyAnalyzer(BaseAnalyzer):
    """Panoramic post-close strategy analyzer."""

    def analyze(self, target_date, **kwargs):
        valid_days = kwargs.get("valid_days", [target_date])

        if len(valid_days) < 3:
            print("⚠️ 交易日数据不足，至少需要3天")
            return None

        df_stocks = self.dm.load_stocks(valid_days)
        df_indices = self.dm.load_indices(valid_days)

        if df_stocks.empty or df_indices.empty:
            print("⚠️ 数据加载失败")
            return None

        df_stocks = DataProcessor.calc_indicators(df_stocks)
        df_indices = DataProcessor.calc_indicators(df_indices)

        indices_result = self._analyze_indices_trend(df_indices, valid_days)
        top_etf, bot_etf = self._analyze_etf_monitor(df_indices, valid_days)
        mainlines = self._analyze_mainline_industries(df_stocks, valid_days)
        structural_env = self._analyze_structural_environment(indices_result, top_etf, bot_etf, mainlines)

        mainline_names = [item["industry"] for item in mainlines]
        core_matrix = self._analyze_core_matrix(df_stocks, valid_days, mainline_names)

        return {
            "date": target_date,
            "indices": indices_result,
            "structural_env": structural_env,
            "etf_top": top_etf,
            "etf_bottom": bot_etf,
            "mainlines": mainlines,
            "core_matrix": core_matrix,
        }

    def _analyze_indices_trend(self, df_indices, valid_days):
        """Level 1A: broad index environment."""
        current_day, prev_day, prev2_day = valid_days[-1], valid_days[-2], valid_days[-3]
        results = []
        total_score = 0.0

        for code, name in MarketConfig.MAIN_INDICES.items():
            hist = df_indices[df_indices["code"] == code].sort_values("date_int")
            if hist.empty or current_day not in hist["date_int"].values:
                continue

            row_t = hist[hist["date_int"] == current_day].iloc[0]
            row_t1 = hist[hist["date_int"] == prev_day].iloc[0] if prev_day in hist["date_int"].values else None

            env_score = TechnicalAnalyzer.calc_env_score(row_t["pct"], row_t["vol_ratio"])
            total_score += env_score

            trend_tag = TechnicalAnalyzer.get_advanced_trend_tag(row_t, row_t1, hist)
            advice = TechnicalAnalyzer.get_strategy_advice(trend_tag, row_t["pct"], row_t["vol_ratio"])

            def format_day(row):
                if row is None:
                    return "-"
                if row["vol_ratio"] < 0.8:
                    vol_text = "缩量"
                elif row["vol_ratio"] > 1.2:
                    vol_text = "放量"
                else:
                    vol_text = "温和"
                return f"{row['pct']:+.2f}% {vol_text}"

            results.append(
                {
                    "name": name,
                    "T_2": format_day(hist[hist["date_int"] == prev2_day].iloc[0] if prev2_day in hist["date_int"].values else None),
                    "T_1": format_day(row_t1),
                    "T": format_day(row_t),
                    "trend": trend_tag,
                    "advice": advice,
                }
            )

        positive_count = 0
        negative_count = 0
        for item in results:
            pct = self._extract_pct(item.get("T"))
            if pct is None:
                continue
            if pct > 0:
                positive_count += 1
            elif pct < 0:
                negative_count += 1

        broad_env = self._classify_broad_environment(total_score, positive_count, negative_count)
        return {
            "judgement": broad_env["judgement"],
            "total_score": round(total_score, 1),
            "details": results,
            "broad_env": broad_env,
        }

    @staticmethod
    def _classify_broad_environment(total_score, positive_count=0, negative_count=0):
        if total_score >= 3 and positive_count >= 3:
            return {
                "label": "safe",
                "judgement": "🟢 环境安全 (积极做多)",
                "advice": "全市场环境偏正，允许更大范围顺势做多。",
            }
        if total_score <= -3 and negative_count >= 3:
            return {
                "label": "hostile",
                "judgement": "🔴 环境恶劣 (空仓观望)",
                "advice": "全市场承压，默认回避大面积做多。",
            }
        return {
            "label": "mixed",
            "judgement": "🟡 震荡环境 (轻指数重个股)",
            "advice": "广谱环境一般，优先做结构，不做普涨想象。",
        }

    def _analyze_structural_environment(self, indices_result, top_etf, bottom_etf, mainlines):
        """Level 1B: structural environment for leading clusters."""
        growth_positive = 0
        weak_broad = 0
        for item in indices_result.get("details", []):
            name = item.get("name")
            pct = self._extract_pct(item.get("T"))
            if name in {"创业板", "科创50"} and pct is not None and pct > 0.8:
                growth_positive += 1
            if name in {"上证", "北证50"} and pct is not None and pct < -0.3:
                weak_broad += 1

        strong_mainlines = 0
        for row in mainlines:
            pct = self._extract_pct(row.get("T"))
            if pct is not None and pct >= 2.5:
                strong_mainlines += 1

        strong_etf = sum(1 for item in top_etf if item.get("raw_pct", 0) >= 2.5)
        financial_drag = any(item.get("name") in {"证券", "银行", "金融地产"} for item in bottom_etf[:4])

        score = 0.0
        score += growth_positive * 1.5
        score += min(strong_mainlines, 3)
        score += min(strong_etf, 3) * 0.5
        score -= weak_broad * 0.5
        if financial_drag:
            score -= 0.5

        if score >= 5:
            if indices_result.get("broad_env", {}).get("label") == "safe":
                judgement = "🟢 结构强共振 (主线与指数同向)"
                advice = "主线和指数共振，可积极围绕最强方向做多。"
            else:
                judgement = "🟢 结构安全 (主线做多)"
                advice = "广谱一般但主线很强，适合围绕领先簇做多，不适合全市场铺开。"
        elif score >= 2.5:
            judgement = "🟡 结构偏强 (精选主线)"
            advice = "有主线但扩散不够，优先聚焦少数强簇和核心中军。"
        else:
            judgement = "🔴 结构一般 (谨慎轮动)"
            advice = "主线支撑不足，结构做多也应明显收缩。"

        return {
            "judgement": judgement,
            "score": round(score, 1),
            "advice": advice,
            "growth_positive_count": growth_positive,
            "weak_broad_count": weak_broad,
            "strong_mainline_count": strong_mainlines,
            "strong_etf_count": strong_etf,
            "financial_drag": financial_drag,
            "leading_industries": [row.get("industry") for row in mainlines[:5]],
        }

    @staticmethod
    def _extract_pct(text):
        if not text:
            return None
        try:
            pct_text = str(text).split("%", 1)[0].split()[-1]
            return float(pct_text)
        except Exception:
            return None

    def _analyze_etf_monitor(self, df_indices, date_list):
        """Level 2: ETF capital leadership."""
        current_day = date_list[-1]
        prev_day = date_list[-2] if len(date_list) > 1 else None

        rows = []
        for code, name in MarketConfig.THEME_ETFS.items():
            seq = df_indices[df_indices["code"] == code].sort_values("date_int")
            if seq.empty:
                continue
            row_t = seq[seq["date_int"] == current_day]
            if row_t.empty:
                continue
            row_t = row_t.iloc[0]
            row_prev = seq[seq["date_int"] == prev_day].iloc[0] if prev_day and prev_day in seq["date_int"].values else None

            status = TechnicalAnalyzer.get_sector_trend_tag(row_t, row_prev, seq)
            rows.append(
                {
                    "name": name,
                    "raw_pct": row_t["pct"],
                    "pct": f"{row_t['pct']:+.2f}%",
                    "vol": f"{row_t['vol_ratio']:.1f}",
                    "status": status,
                }
            )

        rows.sort(key=lambda item: item["raw_pct"], reverse=True)
        top_4 = rows[:4]
        bottom_4 = rows[-4:] if len(rows) >= 8 else rows[-4:]

        for item in bottom_4:
            item["status"] = ""

        return top_4, bottom_4

    def _analyze_mainline_industries(self, df_stocks, valid_days):
        """Level 3: mainline industry tracking."""
        current_day = valid_days[-1]
        prev_day = valid_days[-2] if len(valid_days) > 1 else None
        prev2_day = valid_days[-3] if len(valid_days) > 2 else None

        agg_full = DataProcessor.calc_industry_aggregates(df_stocks, valid_days)
        agg_t = agg_full[agg_full["date_int"] == current_day].copy()

        mainlines = (
            agg_t[agg_t["amount"] > StrategyConfig.MAINLINE_AMOUNT]
            .sort_values("strength", ascending=False)
            .head(5)
        )

        results = []
        for _, row in mainlines.iterrows():
            industry_name = row["industry"]
            industry_seq = agg_full[agg_full["industry"] == industry_name].sort_values("date_int")

            def get_ind_tag(day_int):
                if day_int not in industry_seq["date_int"].values:
                    return "-", 0
                pos_arr = np.where(industry_seq["date_int"].values == day_int)[0]
                if len(pos_arr) == 0:
                    return "-", 0
                pos = pos_arr[0]

                curr = industry_seq.iloc[pos]
                prev = industry_seq.iloc[pos - 1] if pos > 0 else None
                tag = TechnicalAnalyzer.get_sector_trend_tag(curr, prev, industry_seq)
                return f"{curr['pct']:+.1f}% ({int(curr['is_limit_up'])}板) {tag}", int(curr["is_limit_up"])

            t2_str, _ = get_ind_tag(prev2_day)
            t1_str, _ = get_ind_tag(prev_day)
            t_str, limit_up_cnt = get_ind_tag(current_day)

            results.append(
                {
                    "industry": industry_name,
                    "T_2": t2_str,
                    "T_1": t1_str,
                    "T": t_str,
                    "strength": int(row["strength"]),
                    "limit_up_cnt": limit_up_cnt,
                }
            )

        return results

    def _analyze_core_matrix(self, df_stocks, valid_days, mainline_industries):
        """Level 4: core leader matrix."""
        current_day = valid_days[-1]
        df_t = df_stocks[df_stocks["date_int"] == current_day].copy()

        cond_liquidity = df_t["amount"] > StrategyConfig.MIN_AMOUNT
        cond_mainline = df_t["industry"].isin(mainline_industries)

        cond_limit = df_t["is_limit_up"] | df_t["prev_is_limit_up"]
        pool_a = df_t[cond_liquidity & cond_mainline & cond_limit].copy()
        pool_a["score"] = pool_a["pct"] * 10
        pool_a.loc[pool_a["is_limit_up"], "score"] += 100
        pool_a.loc[pool_a["is_limit_up"] & pool_a["prev_is_limit_up"], "score"] += 200

        cond_trend = df_t["pct"] > 3.0
        pool_b = df_t[cond_liquidity & cond_mainline & cond_trend].copy()
        pool_b["weight_score"] = (pool_b["amount"] / 1e8) * pool_b["pct"]

        top_a = pool_a.sort_values("score", ascending=False).head(StrategyConfig.TOP_LIMIT_COUNT)["code"].tolist()
        top_b = pool_b.sort_values("weight_score", ascending=False).head(StrategyConfig.TOP_WEIGHT_COUNT)["code"].tolist()

        final_codes = []
        seen = set()
        for code in top_a + top_b:
            if code not in seen:
                final_codes.append(code)
                seen.add(code)

        matrix = []
        for code in final_codes:
            hist = df_stocks[df_stocks["code"] == code].sort_values("date_int")
            if current_day not in hist["date_int"].values:
                continue

            row_t = hist[hist["date_int"] == current_day].iloc[0]

            def get_day_tag(day_int):
                if day_int not in hist["date_int"].values:
                    return "-"
                idx = hist[hist["date_int"] == day_int].index[0]
                curr = hist.loc[idx]
                pos = hist.index.get_loc(idx)
                prev = hist.iloc[pos - 1] if pos > 0 else None
                tag = TechnicalAnalyzer.get_advanced_trend_tag(curr, prev, hist)
                return f"{curr['pct']:+.1f}% {tag}"

            stock_name = row_t.get("name", str(code))
            if pd.isna(stock_name):
                stock_name = str(code)

            stock_type = "🚀龙头" if code in top_a else "🐘中军"
            matrix.append(
                {
                    "code": code,
                    "name": str(stock_name)[:4],
                    "amount": f"{int(row_t['amount'] / 1e8)}亿",
                    "T_2": get_day_tag(valid_days[-3]) if len(valid_days) > 2 else "-",
                    "T_1": get_day_tag(valid_days[-2]) if len(valid_days) > 1 else "-",
                    "T": get_day_tag(current_day),
                    "concept": row_t["industry"][:6],
                    "type": stock_type,
                }
            )

        return matrix
