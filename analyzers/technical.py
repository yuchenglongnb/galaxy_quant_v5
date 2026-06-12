# -*- coding: utf-8 -*-
"""
技术分析器 - 趋势/形态识别
"""

from config.settings import TechConfig


class TechnicalAnalyzer:
    """技术形态分析器（兼容旧接口 TrendAnalyzer）"""
    
    @staticmethod
    def get_advanced_trend_tag(curr_row, prev_row, hist_window):
        """
        【个股】高级趋势标签识别
        结合5日结构、量能、K线形态进行综合判断
        """
        pct = curr_row.get('pct', 0)
        vol_ratio = curr_row.get('vol_ratio', 1.0)
        close = curr_row['close']
        open_p = curr_row['open']
        high = curr_row.get('high', close)
        is_limit = curr_row.get('is_limit_up', False)
        
        # 计算5日高低点
        if hist_window is not None and not hist_window.empty:
            recent_5 = hist_window.sort_values('date_int').tail(5)
            max_close_5d = recent_5['close'].max()
            min_close_5d = recent_5['close'].min()
        else:
            max_close_5d = close
            min_close_5d = close
            
        tags = []
        
        # 0. 涨跌停状态
        if is_limit:
            if prev_row is not None and prev_row.get('is_limit_up', False):
                return "🚀 连板"
            return "🚀 涨停"
        elif pct < -9.5:
            return "💚 跌停"

        # 1. 放量新高
        if close > max_close_5d * TechConfig.BREAKOUT_MARGIN and \
           vol_ratio > TechConfig.VOLUME_SURGE:
            tags.append("🚀 放量新高")
            
        # 2. 顶部背离
        elif close >= max_close_5d and vol_ratio < TechConfig.VOLUME_SHRINK:
            tags.append("⚠️ 顶部背离")
            
        # 3. 反包昨日
        elif prev_row is not None:
            prev_open = prev_row['open']
            prev_pct = prev_row.get('pct', 0)
            if prev_pct < -0.5 and pct > 0.3 and close > prev_open:
                tags.append("⚡ 反包昨日")
                
        # 4. 冲高回落
        prev_close_val = prev_row['close'] if prev_row is not None else open_p
        if high > prev_close_val * 1.02:
            upper_shadow = high - max(open_p, close)
            body = abs(close - open_p)
            if upper_shadow > body * 1.0 and (high - close) > (high - open_p) * 0.5:
                tags.append("🔴 冲高回落")
                 
        # 5. 二次探底
        if close <= min_close_5d * 1.01 and pct < -0.5:
            tags.append("🌊 二次探底")
             
        # 6. 基础状态
        if not tags:
            if pct > 5.0: tags.append("🔴 大阳")
            elif pct > 2.0 and vol_ratio > 1.2: tags.append("📈 放量上行")
            elif pct > 0.5: tags.append("📈 温和上涨")
            elif pct < -5.0: tags.append("📉 大阴")
            elif pct < -0.5: tags.append("📉 温和下跌")
            elif vol_ratio < 0.7: tags.append("😴 缩量震荡")
            else: tags.append("➡️ 震荡")
            
        return tags[0]

    @staticmethod
    def get_sector_trend_tag(curr_row, prev_row, hist_window):
        """
        【行业/ETF】趋势标签识别
        专门用于描述板块、行业、ETF等聚合数据的趋势特征
        """
        pct = curr_row.get('pct', 0)
        vol_ratio = curr_row.get('vol_ratio', 1.0)
        close = curr_row['close']
        open_p = curr_row['open']
        high = curr_row.get('high', close)
        
        # 计算涨停数（行业特有指标）
        limit_up_cnt = curr_row.get('is_limit_up', 0)
        prev_limit_cnt = prev_row.get('is_limit_up', 0) if prev_row is not None else 0
        
        # 计算5日高低点
        if hist_window is not None and not hist_window.empty:
            recent_5 = hist_window.sort_values('date_int').tail(5)
            max_close_5d = recent_5['close'].max()
            min_close_5d = recent_5['close'].min()
        else:
            max_close_5d = close
            min_close_5d = close
            
        tags = []
        
        # 1. 持续强势
        if prev_row is not None:
            prev_pct = prev_row.get('pct', 0)
            if pct > 1.5 and prev_pct > 1.5:
                if limit_up_cnt >= 2 or prev_limit_cnt >= 2:
                    return "🔥 持续强势"
                else:
                    return "🔥 连续领涨"
        
        # 2. 爆发领涨
        if pct > 3.0 and vol_ratio > 1.2:
            return "🔥 爆发领涨"
        
        # 3. 放量突破
        if close > max_close_5d * TechConfig.BREAKOUT_MARGIN and \
           vol_ratio > TechConfig.VOLUME_SURGE:
            tags.append("🚀 放量突破")
            
        # 4. 量价背离
        elif close >= max_close_5d and vol_ratio < TechConfig.VOLUME_SHRINK:
            tags.append("⚠️ 量价背离")
            
        # 5. 超跌反弹
        elif prev_row is not None:
            prev_pct = prev_row.get('pct', 0)
            prev_open = prev_row['open']
            if prev_pct < -1.0 and pct > 0.5 and close > prev_open:
                tags.append("⚡ 超跌反弹")
                
        # 6. 高位承压
        prev_close_val = prev_row['close'] if prev_row is not None else open_p
        if high > prev_close_val * 1.02:
            upper_shadow = high - max(open_p, close)
            body = abs(close - open_p)
            if upper_shadow > body * 1.0 and (high - close) > (high - open_p) * 0.5:
                tags.append("🔴 高位承压")
                 
        # 7. 回踩支撑
        if close <= min_close_5d * 1.01 and pct < -0.5:
            tags.append("🌊 回踩支撑")
             
        # 8. 基础状态
        if not tags:
            if pct > 3.0: 
                tags.append("📈 强势拉升")
            elif pct > 1.5 and vol_ratio > 1.2: 
                tags.append("📈 放量上攻")
            elif pct > 0.5: 
                tags.append("📈 温和上涨")
            elif pct < -3.0: 
                tags.append("📉 大幅回调")
            elif pct < -0.5: 
                tags.append("📉 小幅回落")
            elif vol_ratio < 0.7: 
                tags.append("😴 缩量整理")
            else: 
                tags.append("➡️ 横盘震荡")
            
        return tags[0]

    @staticmethod
    def calc_env_score(pct, vol_ratio):
        """计算环境评分"""
        score = 0
        if pct > 1.5: score += 2
        elif pct > 0.5: score += 1
        elif pct < -1.5: score -= 2
        elif pct < -0.5: score -= 1
        
        if vol_ratio > 1.5:
            score += 0.5 if pct > 0 else -0.5
        elif vol_ratio < 0.7:
            if pct > 1: score -= 0.3
        return round(score, 1)

    @staticmethod
    def get_strategy_advice(trend_tag, pct, vol_ratio):
        """根据趋势给出操作建议"""
        if "放量新高" in trend_tag or "放量上行" in trend_tag or "放量突破" in trend_tag:
            return "追高强势股,顺势做多"
        elif "反包" in trend_tag or "超跌反弹" in trend_tag:
            return "关注率先反包板块,低吸弹性股"
        elif "顶部背离" in trend_tag or "冲高回落" in trend_tag or "高位承压" in trend_tag or "量价背离" in trend_tag:
            return "减仓观望,规避高位股"
        elif "二次探底" in trend_tag or "回踩支撑" in trend_tag:
            return "等待企稳信号,暂不抄底"
        elif "震荡" in trend_tag or "横盘" in trend_tag:
            if vol_ratio < 0.8:
                return "缩量震荡,聚焦核心股低买高卖"
            else:
                return "震荡市,高抛低吸为主"
        elif "温和上涨" in trend_tag:
            return "持股待涨,适度加仓优质股"
        elif "温和下跌" in trend_tag or "小幅回落" in trend_tag:
            return "轻仓观望,避免追高"
        elif "大阳" in trend_tag or "强势拉升" in trend_tag:
            return "放量大阳,积极做多"
        elif "大阴" in trend_tag or "大幅回调" in trend_tag:
            return "放量大阴,次日关注反包机会"
        else:
            return "观察为主"


# 兼容旧接口
TrendAnalyzer = TechnicalAnalyzer
