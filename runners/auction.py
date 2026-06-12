# -*- coding: utf-8 -*-
"""
竞价分析运行器 v2.0 - 独立的竞价分析入口

输出报告包含:
- 市场环境
- 四大指数监控 + 趋势研判
- ETF竞价监控 (含CP/SA)
- 行业竞价排行 (含CP/SA)
- 今日信号汇总 (诱多警报/反核机会)
- 验证统计
"""

import os
import json
import pandas as pd
from datetime import datetime

from runners.base import BaseRunner
from core.data_manager import DataManager
from analyzers.auction import AuctionAnalyzer
from ai.signal_labels import trap_subtype
from config.settings import UniverseConfig


class AuctionRunner(BaseRunner):
    """竞价分析运行器"""

    VALIDATION_CATEGORIES = (
        ("trap", "CP风险", "body_pct < 0"),
        ("reversal", "反核机会", "body_pct > 0"),
        ("trend", "趋势机会", "body_pct > 0"),
    )
    
    def run(self, target_date=None, sync_first=False, force_refresh=False, realtime=False, use_subscribe=False, **kwargs):
        """
        执行竞价分析
        
        参数:
            target_date: 目标日期（默认最新）
            sync_first: 是否先同步数据
            force_refresh: 是否强制刷新交易日缓存
            realtime: 是否实时模式（9:25盘前决策）
            use_subscribe: 是否使用实时订阅模式（推荐盘前使用，9:25立即可用）
        """
        mode_str = "实时决策" if realtime else "复盘分析"
        if use_subscribe:
            mode_str += "（订阅模式）"
        print(f"\n{'='*60}")
        print(f"  竞价分析 v2.0 - {mode_str}模式")
        print(f"{'='*60}")
        
        dm = DataManager()
        
        # 同步数据
        if sync_first:
            if realtime:
                # 实时模式：使用轻量级同步
                # use_subscribe=True 表示使用实时订阅（9:25立即可用）
                synced_date = dm.sync_realtime(target_date, use_subscribe=use_subscribe)
                if synced_date is None:
                    print("❌ 实时同步失败")
                    return None
                target_date = synced_date
                valid_days = dm.get_valid_trading_days(lookback=10, force_refresh=force_refresh)
            else:
                # 复盘模式：日线open即可还原早盘竞价价，默认不拉耗时较长的分钟数据
                valid_days = dm.sync_recent_days(lookback=5, latest_with_minute=False)
        else:
            local_days = dm.get_local_daily_days()
            target_int = int(target_date) if target_date is not None else None
            if not realtime and local_days and (target_int is None or target_int in local_days):
                valid_days = local_days
                print(f"  ✓ 使用本地完整日线缓存作为复盘日期集合: {valid_days[-5:]}")
            else:
                valid_days = dm.get_valid_trading_days(lookback=10, force_refresh=force_refresh)
        
        if not valid_days:
            print("❌ 无有效交易日数据")
            return None
        
        # 确定分析日期
        if target_date is None:
            target_date = valid_days[-1]
        
        print(f"\n>>> 分析日期: {target_date}")
        if realtime:
            print(f">>> ⏰ 实时模式: 仅使用竞价数据，不包含收盘结果")
        else:
            if not dm.ensure_daily_window_for_analysis(target_date, lookback=6):
                print("❌ 复盘窗口日线缓存刷新失败")
                return None
        
        # 执行分析
        analyzer = AuctionAnalyzer(dm)
        try:
            result = analyzer.analyze(target_date, realtime=realtime)
        except Exception as e:
            print(f"❌ 分析出错: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        if result is None:
            print("❌ 分析失败")
            return None
        
        # 打印报告
        if realtime:
            self._print_realtime_report(result)
        else:
            self._print_report_v2(result)
        self._save_data_quality_records(result)
        if result.get("realtime"):
            self._save_analysis_review(result)
        
        return result
    
    def _print_report_v2(self, result):
        """打印竞价分析报告 v2.0"""
        target_date = result['date']
        market_oar = result.get('market_oar', 1.0)
        
        # ═══════════════════════════════════════════════════════════
        # 报告标题
        # ═══════════════════════════════════════════════════════════
        print(f"\n{'═'*100}")
        print(f"{' '*35}📊 竞价分析报告 [{target_date}]")
        print(f"{'═'*100}")
        
        # ═══════════════════════════════════════════════════════════
        # 市场环境
        # ═══════════════════════════════════════════════════════════
        self._print_data_status(result)
        self._print_market_environment(result)
        
        # ═══════════════════════════════════════════════════════════
        # 四大指数监控 + 趋势研判
        # ═══════════════════════════════════════════════════════════
        self._print_indices_monitor(result)
        self._print_index_factor_monitor(result)
        
        # ═══════════════════════════════════════════════════════════
        # ETF竞价监控
        # ═══════════════════════════════════════════════════════════
        self._print_etf_monitor(result)
        self._print_stock_factor_monitor(result)
        
        # ═══════════════════════════════════════════════════════════
        # 行业竞价排行
        # ═══════════════════════════════════════════════════════════
        self._print_industry_ranking(result)
        
        # ═══════════════════════════════════════════════════════════
        # 今日信号汇总
        # ═══════════════════════════════════════════════════════════
        self._print_signals_summary(result)
        
        # ═══════════════════════════════════════════════════════════
        # 验证统计
        # ═══════════════════════════════════════════════════════════
        self._print_validation_stats(result)
        if not result.get('realtime'):
            self._save_validation_records(result)
        self._save_analysis_review(result)
        
        # ═══════════════════════════════════════════════════════════
        # 指标说明
        # ═══════════════════════════════════════════════════════════
        self._print_indicator_notes()
    
    def _print_data_status(self, result):
        status = result.get("data_status", {}) or {}
        state = status.get("session_state", "unknown")
        fetched_at = status.get("fetched_at") or "-"
        validation_state = "final" if status.get("post_close_validation") else "provisional"
        print("\n[数据状态]")
        print(f"  日期: {result.get('date')} | 缓存: {state} | fetched_at: {fetched_at} | 验证: {validation_state}")
        if state != "closed":
            print("  提示: 当前不是收盘态缓存，收盘/实体/验证结果只能作为盘中临时判断。")
        excluded = result.get("excluded_price_discontinuities", pd.DataFrame())
        if excluded is not None and not excluded.empty:
            labels = [
                f"{row.get('name', row.get('code', ''))}({self._to_float(row.get('auction_pct')):+.2f}%)"
                for _, row in excluded.iterrows()
            ]
            print(f"  价格断点剔除: {len(labels)} 只 | {', '.join(labels)}")

    def _print_market_environment(self, result):
        """打印市场环境"""
        market_oar = result.get('market_oar', 1.0)
        indices_df = result.get('indices_monitor', pd.DataFrame())
        regime = result.get("market_regime", {}) or {}
        regime_label = str(regime.get("label", "") or "")
        
        # OAR描述
        if regime_label == "hostile":
            oar_desc = f"{market_oar:.2f} (平量偏弱)"
            env_rating = "🔴 环境恶劣"
        elif regime_label == "strong_repair":
            oar_desc = f"{market_oar:.2f} ({'放量修复' if market_oar > 1 else '强修复'})"
            env_rating = "🟢 强修复日"
        elif regime_label == "risk_off":
            oar_desc = f"{market_oar:.2f} ({'缩量' if market_oar < 1 else '平量'})"
            env_rating = "🟠 风险偏好低"
        elif regime_label == "repair":
            oar_desc = f"{market_oar:.2f} ({'缩量' if market_oar < 1 else '平量'})"
            env_rating = "🟡 修复观察"
        elif market_oar < 0.8:
            oar_desc = f"{market_oar:.2f} (缩量)"
            env_rating = "🟡 存量博弈"
        elif market_oar > 1.2:
            oar_desc = f"{market_oar:.2f} (放量)"
            env_rating = "🟢 增量进场"
        else:
            oar_desc = f"{market_oar:.2f} (平量)"
            env_rating = "⚪ 正常波动"
        
        # 上证当日走势。旧的“趋势”字段描述的是T-2/T-1形态，放在市场环境里容易误导。
        sh_trend = "震荡"
        sh_ai = ""
        if not indices_df.empty:
            sh_row = indices_df[indices_df['指数'] == '上证']
            if not sh_row.empty:
                sh_trend = sh_row.iloc[0].get('走势', sh_row.iloc[0].get('趋势', '震荡'))
                sh_ai = sh_row.iloc[0].get('AI标签', '')
                if sh_ai and sh_ai != '-':
                    sh_trend = f"{sh_trend}/{sh_ai}"
        
        print(f"\n┌{'─'*98}┐")
        print(f"│ 【🌍 市场环境】{' '*81}│")
        print(f"│{' '*98}│")
        print(f"│   市场OAR: {oar_desc:<12}│  上证走势: {sh_trend:<18}│  环境评级: {env_rating:<15}│")
        print(f"│{' '*98}│")
        
        # 环境解读
        if regime_label == "hostile":
            advice = "💡 指数环境优先级最高。当前更像弱势延续或局部修复，默认不做大面积做多，只观察少数主线簇。"
        elif regime_label == "strong_repair":
            advice = "💡 连续承压后的强修复日，优先看科技或主线簇的一致性转强，让09:35确认去覆盖掉机械CP的保守误判。"
        elif regime_label == "risk_off":
            advice = "💡 风险偏好偏低，优先看指数/ETF承接和主线簇修复，普通反核与趋势应明显收缩。"
        elif regime_label == "repair":
            advice = "💡 低开后存在修复窗口，重点看主线簇是否形成一致转强，警惕个股CP假阳性。"
        elif market_oar < 0.9:
            advice = "💡 整体缩量环境下，资金博弈加剧。高开板块需警惕诱多，低开承接需验证持续性。"
        elif market_oar > 1.2:
            advice = "💡 放量环境下，资金活跃度高。关注主线板块的持续性，警惕追高风险。"
        else:
            advice = "💡 平量环境下，市场分歧较大。关注结构性机会，控制仓位。"
        
        print(f"│   {advice:<93}│")
        print(f"└{'─'*98}┘")
    
    def _print_indices_monitor(self, result):
        """打印四大指数监控 + 趋势研判"""
        indices_df = result.get('indices_monitor', pd.DataFrame())
        
        if indices_df.empty:
            print(f"\n【🎯 四大指数监控】无数据")
            return
        
        print(f"\n【🎯 四大指数监控】")
        print(f"┌{'─'*8}┬{'─'*8}┬{'─'*8}┬{'─'*8}┬{'─'*8}┬{'─'*8}┬{'─'*6}┬{'─'*12}┐")
        print(f"│{'指数':^8}│{'T-2':^8}│{'T-1':^8}│{'竞价':^8}│{'收盘':^8}│{'实体':^8}│{'OAR':^6}│{'走势':^10}│")
        print(f"├{'─'*8}┼{'─'*8}┼{'─'*8}┼{'─'*8}┼{'─'*8}┼{'─'*8}┼{'─'*6}┼{'─'*12}┤")
        
        for _, row in indices_df.iterrows():
            name = row.get('指数', '-')[:4]
            t2 = row.get('T-2', '-')
            t1 = row.get('T-1', '-')
            auction = row.get('竞价', '-')
            close = row.get('收盘', '-')
            body = row.get('实体', '-')
            oar = row.get('OAR', '-')
            status = row.get('走势', '-')
            print(f"│{name:^8}│{t2:^8}│{t1:^8}│{auction:^8}│{close:^8}│{body:^8}│{oar:^6}│{status:^10}│")
        
        print(f"└{'─'*8}┴{'─'*8}┴{'─'*8}┴{'─'*8}┴{'─'*8}┴{'─'*8}┴{'─'*6}┴{'─'*12}┘")
        
        # 趋势研判
        print(f"\n【📈 趋势研判】")
        print(f"┌{'─'*8}┬{'─'*16}┬{'─'*32}┐")
        print(f"│{'指数':^8}│{'形态特征':^14}│{'研判':^28}│")
        print(f"├{'─'*8}┼{'─'*16}┼{'─'*32}┤")
        
        for _, row in indices_df.iterrows():
            name = row.get('指数', '-')[:4]
            trend = row.get('趋势', '-')
            bias = row.get('研判', '-')[:26]
            print(f"│{name:^8}│{trend:^14}│ {bias:<29}│")
        
        print(f"└{'─'*8}┴{'─'*16}┴{'─'*32}┘")

        # AI旁路解读：保留硬规则，同时给出证据化语义解释
        if 'AI标签' in indices_df.columns:
            print(f"\n【🧠 AI旁路趋势解读】")
            print("  说明: 当前为本地解释器旁路输出，后续可替换为RAG/LLM；数值事实仍由程序计算。")
            for _, row in indices_df.iterrows():
                name = row.get('指数', '-')[:4]
                label = row.get('AI标签', '-')
                bias = row.get('AI偏向', '-')
                confidence = row.get('AI置信度', 0)
                evidence = row.get('AI证据', [])
                watch_points = row.get('AI观察', [])
                hard_trend = row.get('趋势', '-')
                print(f"  • {name}: {label} / {bias} (置信度 {confidence:.2f}) | 硬规则: {hard_trend}")
                if evidence:
                    print(f"    证据: {'；'.join(str(x) for x in evidence[:3])}")
                if watch_points:
                    print(f"    观察: {'；'.join(str(x) for x in watch_points[:3])}")

    def _print_index_factor_monitor(self, result):
        """打印指数 CP/SA 因子监控。"""
        df = result.get('index_factors', pd.DataFrame())
        if df.empty:
            print(f"\n【🧭 指数CP/SA监控】无数据")
            return

        print(f"\n【🧭 指数CP/SA监控】")
        print(f"┌{'─'*8}┬{'─'*8}┬{'─'*8}┬{'─'*8}┬{'─'*8}┬{'─'*6}┬{'─'*7}┬{'─'*5}┬{'─'*5}┬{'─'*8}┐")
        print(f"│{'指数':^8}│{'竞价':^8}│{'收盘':^8}│{'实体':^8}│{'量比':^8}│{'5日位':^6}│{'CP':^7}│{'SA':^5}│{'信号':^5}│{'T-1':^8}│")
        print(f"├{'─'*8}┼{'─'*8}┼{'─'*8}┼{'─'*8}┼{'─'*8}┼{'─'*6}┼{'─'*7}┼{'─'*5}┼{'─'*5}┼{'─'*8}┤")
        for _, row in df.head(20).iterrows():
            name = str(row.get('指数', '-'))[:4]
            print(
                f"│{name:^8}│{str(row.get('竞价', '-')):^8}│{str(row.get('收盘', '-')):^8}│"
                f"{str(row.get('实体', '-')):^8}│{str(row.get('量比', '-')):^8}│{str(row.get('5日位', '-')):^6}│"
                f"{str(row.get('CP', '--')):^7}│{str(row.get('SA', '--')):^5}│{str(row.get('信号', '-'))[:5]:^5}│{str(row.get('T-1', '-')):^8}│"
            )
        print(f"└{'─'*8}┴{'─'*8}┴{'─'*8}┴{'─'*8}┴{'─'*8}┴{'─'*6}┴{'─'*7}┴{'─'*5}┴{'─'*5}┴{'─'*8}┘")
    
    def _print_etf_monitor(self, result):
        """打印ETF竞价监控"""
        etf_df = result.get('etf_auction', pd.DataFrame())
        
        if etf_df.empty:
            print(f"\n【🔍 ETF竞价监控】无数据")
            return
        
        print(f"\n【🔍 ETF竞价监控】")
        print(f"┌{'─'*12}┬{'─'*8}┬{'─'*8}┬{'─'*8}┬{'─'*8}┬{'─'*8}┬{'─'*6}┬{'─'*7}┬{'─'*5}┬{'─'*5}┬{'─'*8}┐")
        print(f"│{'ETF':^12}│{'T-2':^8}│{'T-1':^8}│{'竞价':^8}│{'收盘':^8}│{'实体':^8}│{'量比':^6}│{'5日位':^7}│{'CP':^5}│{'SA':^5}│{'信号':^6}│")
        print(f"├{'─'*12}┼{'─'*8}┼{'─'*8}┼{'─'*8}┼{'─'*8}┼{'─'*8}┼{'─'*6}┼{'─'*7}┼{'─'*5}┼{'─'*5}┼{'─'*8}┤")
        
        # 选择显示列
        display_cols = ['ETF', 'T-2', 'T-1', '竞价', '收盘', '实体', '量比', '5日位', 'CP', 'SA', '信号']
        
        for _, row in etf_df.iterrows():
            name = str(row.get('ETF', '-'))[:6]
            t2 = str(row.get('T-2', '-'))
            t1 = str(row.get('T-1', '-'))
            auction = str(row.get('竞价', '-'))
            close = str(row.get('收盘', '-'))
            body = str(row.get('实体', '-'))
            vol = str(row.get('量比', '-'))
            pos = str(row.get('5日位', '-'))
            cp = str(row.get('CP', '--'))
            sa = str(row.get('SA', '--'))
            signal = str(row.get('信号', '-'))[:6]
            
            print(f"│{name:^12}│{t2:^8}│{t1:^8}│{auction:^8}│{close:^8}│{body:^8}│{vol:^6}│{pos:^7}│{cp:^5}│{sa:^5}│{signal:^6}│")
        
        print(f"└{'─'*12}┴{'─'*8}┴{'─'*8}┴{'─'*8}┴{'─'*8}┴{'─'*8}┴{'─'*6}┴{'─'*7}┴{'─'*5}┴{'─'*5}┴{'─'*8}┘")
        print(f"  💡 CP=拥挤兑现风险指数(高开诱多/强势后兑现) │ SA=承接反核指数(低开触发) │ 阈值: CP≥60🔴 SA≥50🟢")

    def _print_stock_factor_monitor(self, result):
        """打印自选股 CP/SA TopK。"""
        df = result.get('stock_factors', pd.DataFrame())
        if df.empty:
            print(f"\n【🎯 自选股CP/SA TopK】无数据")
            return

        print(f"\n【🎯 自选股CP/SA TopK】")
        print(f"┌{'─'*4}┬{'─'*9}┬{'─'*8}┬{'─'*10}┬{'─'*8}┬{'─'*8}┬{'─'*8}┬{'─'*7}┬{'─'*5}┬{'─'*5}┬{'─'*8}┐")
        print(f"│{'排':^4}│{'代码':^9}│{'名称':^8}│{'分组':^8}│{'竞价':^8}│{'收盘':^8}│{'实体':^8}│{'5日位':^7}│{'CP':^5}│{'SA':^5}│{'信号':^6}│")
        print(f"├{'─'*4}┼{'─'*9}┼{'─'*8}┼{'─'*10}┼{'─'*8}┼{'─'*8}┼{'─'*8}┼{'─'*7}┼{'─'*5}┼{'─'*5}┼{'─'*8}┤")
        for _, row in df.head(20).iterrows():
            print(
                f"│{str(row.get('排名', '-')):^4}│{str(row.get('代码', '-'))[:9]:^9}│{str(row.get('名称', '-'))[:4]:^8}│"
                f"{str(row.get('分组', '-'))[:5]:^10}│{str(row.get('竞价', '-')):^8}│{str(row.get('收盘', '-')):^8}│"
                f"{str(row.get('实体', '-')):^8}│{str(row.get('5日位', '-')):^7}│{str(row.get('CP', '--')):^5}│"
                f"{str(row.get('SA', '--')):^5}│{str(row.get('信号', '-'))[:6]:^6}│"
            )
        print(f"└{'─'*4}┴{'─'*9}┴{'─'*8}┴{'─'*10}┴{'─'*8}┴{'─'*8}┴{'─'*8}┴{'─'*7}┴{'─'*5}┴{'─'*5}┴{'─'*8}┘")
        print("  💡 自选股按 max(CP, SA) 排序；CP看拥挤兑现风险，SA看低开承接修复机会。")
    
    def _print_industry_ranking(self, result):
        """打印行业竞价排行"""
        industry_df = result.get('industry_report', pd.DataFrame())
        
        if industry_df.empty:
            print(f"\n【📊 行业竞价排行】无数据")
            return
        
        print(f"\n【📊 行业竞价排行 Top 15】")
        print(f"┌{'─'*4}┬{'─'*12}┬{'─'*9}┬{'─'*8}┬{'─'*8}┬{'─'*8}┬{'─'*8}┬{'─'*8}┬{'─'*7}┬{'─'*5}┬{'─'*5}┬{'─'*8}┐")
        print(f"│{'排名':^4}│{'板块':^10}│{'竞价额':^9}│{'T-2':^8}│{'T-1':^8}│{'竞价':^8}│{'收盘':^8}│{'实体':^8}│{'5日位':^7}│{'CP':^5}│{'SA':^5}│{'信号':^6}│")
        print(f"├{'─'*4}┼{'─'*12}┼{'─'*9}┼{'─'*8}┼{'─'*8}┼{'─'*8}┼{'─'*8}┼{'─'*8}┼{'─'*7}┼{'─'*5}┼{'─'*5}┼{'─'*8}┤")
        
        for _, row in industry_df.iterrows():
            rank = str(row.get('排名', '-'))
            name = str(row.get('板块', '-'))[:6]
            amt = str(row.get('竞价额', '-'))
            t2 = str(row.get('T-2', '-'))
            t1 = str(row.get('T-1', '-'))
            auction = str(row.get('竞价', '-'))
            close = str(row.get('收盘', '-'))
            body = str(row.get('实体', '-'))
            pos = str(row.get('5日位', '--'))
            cp = str(row.get('CP', '--'))
            sa = str(row.get('SA', '--'))
            signal = str(row.get('信号', '-'))[:6]
            
            print(f"│{rank:^4}│{name:^10}│{amt:^9}│{t2:^8}│{t1:^8}│{auction:^8}│{close:^8}│{body:^8}│{pos:^7}│{cp:^5}│{sa:^5}│{signal:^6}│")
        
        print(f"└{'─'*4}┴{'─'*12}┴{'─'*9}┴{'─'*8}┴{'─'*8}┴{'─'*8}┴{'─'*8}┴{'─'*8}┴{'─'*7}┴{'─'*5}┴{'─'*5}┴{'─'*8}┘")
        print(f"  💡 排名权重: Top3=1.0 │ Top5=0.7 │ Top10=0.3 │ 高开阈值: 主板0.3%/双创0.5%")
    
    def _print_signals_summary(self, result):
        """打印今日信号汇总"""
        raw_signals = result.get('signals', {})
        signals = result.get('shortlist', raw_signals)
        
        if not signals:
            return
        
        trap_signals = signals.get('trap', [])
        trap_observation = signals.get('trap_observation', [])
        reversal_signals = signals.get('reversal', [])
        reversal_high_confidence = signals.get('reversal_high_confidence', [])
        reversal_observation = signals.get('reversal_observation', reversal_signals)
        trend_signals = signals.get('trend', [])
        trend_observation = signals.get('trend_observation', [])
        
        if not trap_signals and not trap_observation and not reversal_signals and not reversal_high_confidence and not trend_signals and not trend_observation:
            return
        
        print(f"\n{'═'*100}")
        print(f"{' '*38}【🚨 今日信号汇总】")
        print(f"{'═'*100}")
        
        regime = result.get("market_regime", {}) or {}
        reversal_preference = regime.get("reversal_preference", "default")
        print(f"  [shortlist] regime={regime.get('label', 'unknown')} | "
              f"CP {len(trap_signals)}/{len(raw_signals.get('trap', []))} | "
              f"个股CP观察 {len(trap_observation)} | "
              f"高置信反核 {len(reversal_high_confidence)} | "
              f"普通反核 {len(reversal_observation)}/{len(raw_signals.get('reversal', []))} | "
              f"趋势 {len(trend_signals)}/{len(raw_signals.get('trend', []))}")
        self._print_intraday_confirmation_summary(result)

        # 诱多警报
        if trap_signals:
            print(f"\n▶ 🔴 CP风险警报 (高开诱多 / 强势后兑现)")
            for sig in trap_signals:
                if sig.get("action_priority") == "P0":
                    print("  ★ 最高优先级 CP Top1")
                self._print_signal_card(sig, 'trap')

        if trap_observation:
            print(f"\n▶ 🟠 个股CP观察池 (回避为主，不进入主执行区)")
            for sig in trap_observation:
                self._print_signal_card(sig, 'trap')
        
        if reversal_high_confidence:
            if reversal_preference == "high_confidence_structural_repair":
                print(f"\n▶ 🟢 结构修复高置信反核 (risk_off + 主线簇修复，优先指数 / ETF)")
            else:
                print(f"\n▶ 🟢 高置信反核 (risk_off + 超跌反弹，优先指数 / ETF)")
            for sig in reversal_high_confidence:
                self._print_signal_card(sig, 'reversal')

        # 普通反核观察
        if reversal_observation:
            if reversal_preference == "weak_reversal_observation":
                print(f"\n▶ 🟢 弱反核观察 (risk_off 下仅观察，不直接放大执行)")
            else:
                print(f"\n▶ 🟢 普通反核观察 (SA≥50 + 低开，盘后用实体验证)")
            for sig in reversal_observation:
                self._print_signal_card(sig, 'reversal')

        if trend_signals:
            print("\n▶ 🟡 趋势Top1观察")
            for sig in trend_signals:
                data = sig.get("data", {}) or {}
                subtype = "放量延续" if sig.get("scenario") == "TREND_ACCELERATE" else "温和延续"
                print(
                    f"  - {sig.get('type')} {sig.get('name')}: "
                    f"{subtype}, "
                    f"score={sig.get('action_score', 0):.1f}, "
                    f"竞价={self._to_float(data.get('auction_pct')):+.2f}%, "
                    f"T-1={self._to_float(data.get('prev_pct')):+.2f}%"
                )

    @staticmethod
    def _trap_subtype(data):
        return trap_subtype(data)
    
    def _print_signal_card(self, sig, signal_type):
        """打印单个信号卡片"""
        name = sig.get('name', '-')
        data = sig.get('data', {})
        commentary = sig.get('commentary') or {}
        
        cp = sig.get('cp')
        sa = sig.get('sa')
        amt_rank = sig.get('amt_rank')
        
        # 指标值
        if signal_type == 'trap':
            subtype = self._trap_subtype(data)
            indicator = f"CP={cp} · {subtype}" if cp else f"CP=-- · {subtype}"
        else:
            indicator = f"SA={sa}" if sa else "SA=--"
        
        # 关键数据
        auction_pct = data.get('auction_pct', 0)
        body_pct = data.get('body_pct', 0)
        prev_body_pct = data.get('prev_body_pct', 0)  # 使用实体涨跌幅
        prev_vol_ratio = data.get('prev_vol_ratio', 1.0)
        pos_5d = data.get('pos_5d', 50)
        
        # 排名信息
        rank_str = f"竞价额Top{amt_rank}" if amt_rank and amt_rank <= 15 else ""
        
        print(f"┌{'─'*98}┐")
        print(f"│ 【{name}】 {indicator:<80}│")
        print(f"│  {'┄'*94}│")
        
        # 概要行 - 使用昨日实体涨跌幅
        summary_parts = []
        if rank_str:
            summary_parts.append(rank_str)
        if prev_body_pct != 0:
            if prev_body_pct > 0:
                summary_parts.append(f"昨阳+{prev_body_pct:.2f}%后")
            else:
                summary_parts.append(f"昨阴{prev_body_pct:.2f}%后")
        summary_parts.append(f"{'高开' if auction_pct > 0.2 else '低开'}{auction_pct:+.2f}%")
        if body_pct != 0:
            summary_parts.append(f"→ 实体{body_pct:+.2f}%")
        if pos_5d != 50:
            summary_parts.append(f"│ 5日位置{pos_5d:.0f}%")
        
        summary = " │ ".join(summary_parts)
        print(f"│  {summary:<94}│")
        print(f"│{' '*98}│")
        
        # 昨日语境
        if commentary.get('context'):
            print(f"│  ◆ 昨日语境: {commentary['context']:<81}│")
        
        # 今日行为
        if commentary.get('action'):
            print(f"│  ◆ 今日行为: {commentary['action']:<81}│")
        
        print(f"│{' '*98}│")
        
        # 研判
        if signal_type == 'trap':
            prefix = "⚠️ 风险研判:"
        else:
            prefix = "✅ 机会研判:"
        
        if commentary.get('risk'):
            risk_text = commentary['risk']
            # 分行显示长文本
            if len(risk_text) > 80:
                print(f"│  {prefix} {risk_text[:75]:<80}│")
                print(f"│  {' '*12}{risk_text[75:]:<82}│")
            else:
                print(f"│  {prefix} {risk_text:<80}│")
        
        # 操作建议
        if commentary.get('advice'):
            print(f"│  📋 操作建议: {commentary['advice']:<80}│")
        
        print(f"└{'─'*98}┘")
    
    def _print_validation_stats(self, result):
        """打印验证统计"""
        signals = result.get('signals', {})
        
        if not signals:
            return

        rows = []
        for category, family, _rule in self.VALIDATION_CATEGORIES:
            items = signals.get(category, [])
            count = len(items)
            bodies = [self._to_float(s.get("data", {}).get("body_pct")) for s in items]
            success = sum(1 for body in bodies if self._validate_signal(category, body)["success"])
            rate = success / count * 100 if count > 0 else 0
            avg_body = sum(bodies) / count if count > 0 else 0
            rows.append((family, count, success, rate, avg_body))
        
        print(f"\n{'═'*100}")
        print(f"\n【📈 今日验证统计】")
        print(f"┌{'─'*12}┬{'─'*8}┬{'─'*10}┬{'─'*8}┬{'─'*14}┐")
        print(f"│{'信号类型':^10}│{'触发数':^8}│{'验证成功':^10}│{'胜率':^8}│{'平均实体涨幅':^12}│")
        print(f"├{'─'*12}┼{'─'*8}┼{'─'*10}┼{'─'*8}┼{'─'*14}┤")
        icons = {"CP风险": "🔴", "反核机会": "🟢", "趋势机会": "🟡"}
        for family, count, success, rate, avg_body in rows:
            label = f"{icons.get(family, '')} {family}"
            print(f"│{label:^10}│{count:^8}│{success:^10}│{rate:^6.0f}%│{avg_body:^+12.2f}%│")
        print(f"└{'─'*12}┴{'─'*8}┴{'─'*10}┴{'─'*8}┴{'─'*14}┘")
        print(f"  💡 验证标准: CP风险=实体<0 │ 反核机会=实体>0 │ 趋势机会=实体>0")

    def _save_validation_records(self, result):
        """保存每日信号验证明细和汇总，便于后续复盘分析。"""
        out_dir = os.path.join("reports", "validation")
        os.makedirs(out_dir, exist_ok=True)
        current_date = str(result.get("date", "unknown"))
        daily_dir = os.path.join(out_dir, "daily", current_date)
        os.makedirs(daily_dir, exist_ok=True)

        records = self._build_validation_records(result)
        if not records:
            self._save_factor_snapshots(result, daily_dir)
            print(f"  💾 当日特征快照目录: {os.path.abspath(daily_dir)}")
            return

        detail_path = os.path.join(out_dir, "auction_signal_validation.csv")
        summary_path = os.path.join(out_dir, "auction_signal_daily_summary.csv")
        metrics_path = os.path.join(out_dir, "auction_signal_metrics.csv")

        detail_df = pd.DataFrame(records)
        if os.path.exists(detail_path):
            old = pd.read_csv(detail_path, encoding="utf-8-sig")
            for col in detail_df.columns:
                if col not in old.columns:
                    old[col] = ""
            for col in old.columns:
                if col not in detail_df.columns:
                    detail_df[col] = ""
            old = old[detail_df.columns]
            old = old[old["date"].astype(str) != current_date]
            detail_df = pd.concat([old, detail_df], ignore_index=True)
        detail_df.to_csv(detail_path, index=False, encoding="utf-8-sig")

        summary_df = self._build_validation_summary(detail_df)
        summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
        metrics_df = self._build_validation_metrics(detail_df)
        metrics_df.to_csv(metrics_path, index=False, encoding="utf-8-sig")
        daily_detail = detail_df[detail_df["date"].astype(str) == current_date].copy()
        daily_summary = self._build_validation_summary(daily_detail)
        daily_metrics = self._build_validation_metrics(daily_detail, dates=[current_date])
        daily_detail_path = os.path.join(daily_dir, "signal_detail.csv")
        daily_summary_path = os.path.join(daily_dir, "signal_summary.csv")
        daily_metrics_path = os.path.join(daily_dir, "signal_metrics.csv")
        self._write_csv_safe(daily_detail, daily_detail_path)
        self._write_csv_safe(daily_summary, daily_summary_path)
        self._write_csv_safe(daily_metrics, daily_metrics_path)
        self._save_factor_snapshots(result, daily_dir)
        print(f"  💾 验证明细已保存: {os.path.abspath(detail_path)}")
        print(f"  💾 每日汇总已保存: {os.path.abspath(summary_path)}")
        print(f"  💾 类型指标已保存: {os.path.abspath(metrics_path)}")
        print(f"  💾 当日验证目录: {os.path.abspath(daily_dir)}")

    def _save_analysis_review(self, result):
        date = str(result.get("date", "unknown"))
        out_dir = os.path.join("reports", "analysis", "daily", date)
        os.makedirs(out_dir, exist_ok=True)

        records = self._build_validation_records(result)
        detail_df = pd.DataFrame(records)
        metrics_df = self._build_validation_metrics(detail_df, dates=[date])
        payload = self._json_sanitize(self._build_analysis_payload(result, detail_df, metrics_df))

        json_path = os.path.join(out_dir, "auction_review.json")
        md_path = os.path.join(out_dir, "auction_review.md")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self._format_analysis_markdown_v2(payload))

        self._save_analysis_lessons_v2(payload)
        print(f"  [analysis] 竞价分析沉淀: {os.path.abspath(md_path)}")

    def _build_analysis_payload(self, result, detail_df, metrics_df):
        status = result.get("data_status", {}) or {}
        market_oar = self._to_float(result.get("market_oar"), 1.0)
        provisional = status.get("session_state") != "closed"
        detail_records = [] if detail_df.empty else detail_df.to_dict(orient="records")
        metric_records = [] if metrics_df.empty else metrics_df.to_dict(orient="records")
        failures = [r for r in detail_records if str(r.get("validation_result")) == "failed"]
        successes = [r for r in detail_records if str(r.get("validation_result")) == "success"]
        matched_patterns = self._match_market_patterns(result, detail_df, metrics_df)
        analysis_context = dict(result)
        analysis_context["matched_patterns"] = matched_patterns

        return {
            "date": str(result.get("date")),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "data_status": status,
            "market_oar": market_oar,
            "market_regime": result.get("market_regime", {}),
            "environment_gate": self._build_environment_gate(result, detail_df),
            "intraday_confirmation_summary": self._build_intraday_confirmation_summary(result),
            "unmatched_auction_summary": self._build_unmatched_auction_summary(result),
            "leading_clusters": self._leading_clusters(result),
            "theme_cluster_summary": self._build_theme_cluster_summary(result, detail_df),
            "shortlist_score_summary": self._build_shortlist_score_summary(result, detail_df),
            "technical_route_comparison": self._build_technical_route_comparison(result, detail_df),
            "validation_scope": "provisional_intraday" if provisional else "post_close_final",
            "methodology_refs": self._methodology_refs(),
            "matched_patterns": matched_patterns,
            "pattern_progress": self._pattern_progress_summary(matched_patterns),
            "core_conclusion": self._derive_core_conclusion(result, detail_df),
            "metrics": metric_records,
            "notable_successes": self._pick_notable_records(successes, limit=8),
            "notable_failures": self._pick_notable_records(failures, limit=8),
            "analyst_judgment": self._derive_analyst_judgment(result, detail_df),
            "follow_up_points": self._derive_follow_up_points_v2(analysis_context, detail_df),
        }

    def _methodology_refs(self):
        return {
            "skill": os.path.join("skills", "auction-review-analyst", "SKILL.md"),
            "methodology": os.path.join("reports", "analysis", "methodology", "AUCTION_RESEARCH_METHOD.md"),
            "pattern_registry": os.path.join("reports", "analysis", "patterns", "market_pattern_registry.json"),
            "pattern_progress": os.path.join("reports", "analysis", "patterns", "pattern_progress.json"),
            "lesson_log": os.path.join("reports", "analysis", "lessons", "auction_lessons.jsonl"),
        }

    def _build_intraday_confirmation_summary(self, result):
        meta = result.get("intraday_confirmation", {}) or {}
        signal_meta = meta.get("signal_enrichment", {}) or {}
        summary = {
            "available": bool(meta.get("available")),
            "feature_timestamp": meta.get("feature_timestamp") or signal_meta.get("feature_timestamp"),
            "coverage_count": 0,
            "confirmed_strength_count": 0,
            "trend_enriched_count": int(signal_meta.get("enriched_count", 0) or 0),
            "trend_rejected_count": int(meta.get("rejected_count", 0) or 0),
            "trend_selected_after_confirmation": int(meta.get("selected_after_confirmation", 0) or 0),
            "path": meta.get("path", "") or signal_meta.get("path", ""),
        }
        path = summary["path"]
        if path and os.path.exists(path):
            try:
                confirm_df = pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str})
            except Exception:
                confirm_df = pd.DataFrame()
            if not confirm_df.empty:
                summary["coverage_count"] = int(len(confirm_df))
                if "execution_bias" in confirm_df.columns:
                    summary["confirmed_strength_count"] = int(
                        confirm_df["execution_bias"].astype(str).eq("confirmed_strength").sum()
                    )
        return summary

    def _build_unmatched_auction_summary(self, result):
        excluded = result.get("excluded_price_discontinuities", pd.DataFrame())
        if excluded is None or excluded.empty or "price_discontinuity_reason" not in excluded.columns:
            return {
                "count": 0,
                "sample_names": [],
            }
        unmatched = excluded[
            excluded["price_discontinuity_reason"].astype(str) == "no_matched_auction_price"
        ].copy()
        return {
            "count": int(len(unmatched)),
            "sample_names": unmatched.get("name", pd.Series(dtype=str)).fillna(
                unmatched.get("code", pd.Series(dtype=str))
            ).astype(str).head(10).tolist(),
        }

    def _load_pattern_registry(self):
        path = self._methodology_refs()["pattern_registry"]
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _metrics_by_category(self, metrics_df):
        if metrics_df is None or metrics_df.empty:
            return {}
        rows = {}
        for _, row in metrics_df.iterrows():
            rows[str(row.get("signal_category", ""))] = row.to_dict()
        return rows

    def _load_lessons(self):
        path = self._methodology_refs()["lesson_log"]
        if not os.path.exists(path):
            return []
        rows = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                if isinstance(item, dict):
                    rows.append(item)
        return rows

    def _leading_clusters(self, result):
        clusters = []
        for key in ("industry_report", "stock_report"):
            df = result.get(key)
            if df is None or df.empty:
                continue
            name_col = "板块" if "板块" in df.columns else "分组" if "分组" in df.columns else None
            body_col = "实体" if "实体" in df.columns else None
            if not name_col or not body_col:
                continue
            work = df[[name_col, body_col]].copy()
            work[body_col] = (
                work[body_col].astype(str).str.replace("%", "", regex=False).str.replace("+", "", regex=False)
            )
            work[body_col] = pd.to_numeric(work[body_col], errors="coerce")
            work = work.dropna(subset=[body_col])
            work = work[work[body_col] > 0]
            for name in work[name_col].astype(str).head(5).tolist():
                if name and name not in clusters:
                    clusters.append(name)
        return clusters

    def _match_market_patterns(self, result, detail_df, metrics_df):
        registry = {item.get("id"): item for item in self._load_pattern_registry() if item.get("id")}
        metrics = self._metrics_by_category(metrics_df)
        matched = []
        market_oar = self._to_float(result.get("market_oar"), 1.0)
        regime = str((result.get("market_regime", {}) or {}).get("label", ""))
        leading_clusters = self._leading_clusters(result)

        cp = metrics.get("trap", {})
        reversal = metrics.get("reversal", {})
        trend = metrics.get("trend", {})
        cp_rate = self._to_float(cp.get("success_rate"), 0.0)
        reversal_rate = self._to_float(reversal.get("success_rate"), 0.0)
        trend_rate = self._to_float(trend.get("success_rate"), 0.0)

        if (
            registry.get("repair_in_riskoff")
            and regime in {"risk_off", "mixed", "normal", ""}
            and 0.75 <= market_oar <= 1.05
            and reversal_rate >= 55.0
            and cp_rate <= 20.0
            and leading_clusters
        ):
            item = dict(registry["repair_in_riskoff"])
            item["match_confidence"] = 0.86
            item["matched_facts"] = {
                "market_oar": round(market_oar, 4),
                "market_regime": regime,
                "cp_success_rate": cp_rate,
                "reversal_success_rate": reversal_rate,
                "trend_success_rate": trend_rate,
                "leading_clusters": leading_clusters[:3],
            }
            matched.append(item)

        cp_failures = []
        if detail_df is not None and not detail_df.empty:
            cp_failures = detail_df[
                (detail_df["signal_category"] == "trap")
                & (detail_df["validation_result"] == "failed")
            ].to_dict(orient="records")
        if registry.get("cp_false_positive_in_theme_repair") and cp_failures and leading_clusters:
            item = dict(registry["cp_false_positive_in_theme_repair"])
            item["match_confidence"] = 0.78
            item["matched_facts"] = {
                "failed_cp_count": len(cp_failures),
                "examples": [row.get("name", "") for row in cp_failures[:3]],
                "leading_clusters": leading_clusters[:3],
            }
            matched.append(item)

        if registry.get("theme_cluster_repair") and len(leading_clusters) >= 2 and reversal_rate >= 50.0:
            item = dict(registry["theme_cluster_repair"])
            item["match_confidence"] = 0.81
            item["matched_facts"] = {
                "leading_clusters": leading_clusters[:5],
                "reversal_success_rate": reversal_rate,
                "trend_success_rate": trend_rate,
            }
            matched.append(item)

        return matched

    def _pattern_progress_summary(self, matched_patterns):
        lessons = self._load_lessons()
        summary = []
        for item in matched_patterns:
            pattern_id = str(item.get("id", "") or "")
            if not pattern_id:
                continue
            unique_dates = sorted({
                str(lesson.get("date", "") or "")
                for lesson in lessons
                if (
                    str(lesson.get("case", "") or "") == pattern_id
                    or (
                        str(lesson.get("signal_type", "") or "") == "market_env"
                        and str(lesson.get("case", "") or "") == pattern_id
                    )
                )
                and str(lesson.get("date", "") or "")
            })
            occurrence_count = len(unique_dates)
            if occurrence_count >= 3:
                recommendation = "candidate_for_rule_or_weight"
                note = "Same pattern has repeated at least 3 times; start evaluating rule, weight, or ranking upgrades."
            elif occurrence_count == 2:
                recommendation = "watch_closely"
                note = "Pattern has appeared twice; prioritize review if it appears again."
            else:
                recommendation = "observed_only"
                note = "Keep as methodology evidence first; do not hard-code yet."
            summary.append({
                "id": pattern_id,
                "name": item.get("name") or pattern_id,
                "occurrence_count": occurrence_count,
                "dates": unique_dates[-5:],
                "recommendation": recommendation,
                "note": note,
            })
        return summary

    def _derive_core_conclusion(self, result, detail_df):
        market_oar = self._to_float(result.get("market_oar"), 1.0)
        state = (result.get("data_status", {}) or {}).get("session_state", "unknown")
        regime = str((result.get("market_regime", {}) or {}).get("label", "") or "")
        cp_count = 0
        cp_success = 0
        if not detail_df.empty:
            cp_df = detail_df[detail_df["signal_category"] == "trap"]
            cp_count = len(cp_df)
            cp_success = int(cp_df["validation_success"].map(self._as_bool).sum()) if cp_count else 0

        if regime == "hostile":
            text = "环境恶劣，优先控制仓位和回避大面积做多，反核与趋势只保留极少数主线强样本观察。"
        elif regime == "strong_repair":
            text = "连续承压后的强修复日已经形成，主线簇一致转强时应降低机械CP权重，并允许09:35确认对早盘谨慎判断翻案。"
        elif regime == "repair":
            text = "低开后存在承接修复迹象，重点观察主线簇内部是否形成一致修复，而不是机械套用 CP 风险。"
        elif regime == "risk_off":
            text = "偏 risk-off 环境，优先看指数/ETF 承接质量和主线簇是否出现局部修复。"
        elif market_oar < 0.8 and cp_count >= 3 and cp_success >= max(1, cp_count * 0.6):
            text = "缩量环境下 CP 风险有效，资金更偏兑现而不是追高扩散。"
        elif market_oar > 1.2:
            text = "放量环境，信号需要区分主线延续和高位兑现。"
        else:
            text = "平量或正常波动环境，重点看实体方向对竞价信号的确认。"

        if state != "closed":
            text += " 当前为盘中快照，结论需等待收盘数据复核。"
        return text

    def _build_environment_gate(self, result, detail_df):
        regime = result.get("market_regime", {}) or {}
        label = str(regime.get("label", "") or "")
        reversal_rate = self._metric_success_rate(detail_df, "reversal")
        trend_rate = self._metric_success_rate(detail_df, "trend")
        broad_long_allowed = label not in {"hostile"}
        if label == "hostile":
            decision = "block_broad_longs"
            note = "指数环境恶劣，默认不做大面积做多，只保留极少数主线强样本观察。"
        elif label == "strong_repair":
            decision = "repair_breakout_enabled"
            note = "强修复日允许围绕主线簇和09:35确认结果做顺势跟踪，个股CP应明显降权。"
        elif label == "risk_off":
            decision = "selective_reversal_only"
            note = "优先观察指数/ETF 承接和主线簇修复，个股趋势与普通反核都应明显收缩。"
        elif label == "repair":
            decision = "theme_repair_focus"
            note = "允许围绕主线簇做选择性跟踪，但要警惕 CP 假阳性和弱修复回落。"
        elif label == "continuation":
            decision = "trend_enabled"
            note = "环境允许趋势延续，但仍需区分过热高开与真实强势。"
        else:
            decision = "mixed_wait_confirmation"
            note = "环境混合，优先等待更明确的主线簇和盘中确认。"
        return {
            "label": label or "mixed",
            "decision": decision,
            "broad_long_allowed": broad_long_allowed,
            "reversal_success_rate": reversal_rate,
            "trend_success_rate": trend_rate,
            "note": note,
        }

    def _build_theme_cluster_summary(self, result, detail_df):
        clusters = self._cluster_records(result, detail_df)
        if not clusters:
            return []
        rows = []
        for name, payload in sorted(
            clusters.items(),
            key=lambda item: (
                -(item[1]["success_count"] * 2 + item[1]["positive_body_count"]),
                -item[1]["avg_body_pct"],
                item[0],
            ),
        ):
            count = payload["count"]
            success_count = payload["success_count"]
            rows.append({
                "cluster": name,
                "sample_count": count,
                "success_count": success_count,
                "success_rate": round(success_count / count * 100, 2) if count else 0.0,
                "avg_body_pct": round(payload["avg_body_pct"], 4),
                "positive_body_count": payload["positive_body_count"],
                "sources": sorted(payload["sources"]),
                "examples": payload["examples"][:5],
            })
        return rows[:8]

    def _build_shortlist_score_summary(self, result, detail_df):
        if detail_df is None or detail_df.empty:
            return []
        actionable = detail_df[detail_df["actionable"].map(self._as_bool)].copy()
        if actionable.empty:
            return []
        rows = []
        for _, row in actionable.sort_values(["signal_order", "action_score"], ascending=[True, False]).head(12).iterrows():
            rows.append({
                "signal_category": row.get("signal_category", ""),
                "name": row.get("name", ""),
                "target_type": row.get("target_type", ""),
                "theme_cluster": row.get("theme_cluster", ""),
                "action_score": round(self._to_float(row.get("action_score")), 4),
                "score_regime_bonus": round(self._to_float(row.get("score_regime_bonus")), 4),
                "score_theme_cluster_bonus": round(self._to_float(row.get("score_theme_cluster_bonus")), 4),
                "score_group_regime_bonus": round(self._to_float(row.get("score_group_regime_bonus")), 4),
                "score_confirmation_bonus": round(self._to_float(row.get("score_confirmation_bonus")), 4),
                "score_reliability_penalty": round(self._to_float(row.get("score_reliability_penalty")), 4),
                "shortlist_reason": row.get("shortlist_reason", ""),
            })
        return rows

    def _build_technical_route_comparison(self, result, detail_df):
        regime = str((result.get("market_regime", {}) or {}).get("label", "") or "")
        confirm = result.get("intraday_confirmation", {}) or {}
        theme_clusters = self._leading_clusters(result)
        return [
            {
                "route": "hard_rules",
                "status": "active_core",
                "role": "CP / reversal / trend 的基础触发与环境门控",
                "strengths": [
                    "速度最快，适合主入口和批量回放",
                    "事实来源清楚，便于验证和复盘",
                ],
                "weaknesses": [
                    "语义表达僵硬，容易把强修复日误写成统一的高开诱多",
                    "对主线簇切换和上下文变化不够敏感",
                ],
                "current_takeaway": (
                    "继续保留为主链路，但只负责触发与门控，不再独占最终解释权。"
                ),
            },
            {
                "route": "regime_cluster_statistics",
                "status": "active_ranking",
                "role": "用历史分层样本给 trend / reversal 排序加权",
                "strengths": [
                    "能把环境和主线簇的历史表现喂回排序",
                    "比纯硬规则更贴近真实盘面结构",
                ],
                "weaknesses": [
                    "对样本量敏感，容易受阶段行情影响",
                    "需要持续补样本和做分层消融",
                ],
                "current_takeaway": (
                    f"当前已正式接入排序；本日 regime={regime or '-'}，leading_clusters={theme_clusters[:4] or ['-']}。"
                ),
            },
            {
                "route": "intraday_confirmation_0935",
                "status": "active_secondary_gate" if confirm.get("available") else "inactive_waiting_data",
                "role": "09:35 二次确认，修正 09:25 的早盘误判",
                "strengths": [
                    "对强修复日特别有价值，能减少机械 CP 误伤",
                    "直接使用成交与相对强弱，更接近执行层",
                ],
                "weaknesses": [
                    "不能替代 09:25 的盘前决策",
                    "依赖分时/快照数据完整性",
                ],
                "current_takeaway": (
                    "更适合做确认层和翻案层，而不是替代竞价主判断。"
                ),
            },
            {
                "route": "ai_semantic_interpretation",
                "status": "assistive_only",
                "role": "把硬规则与统计结果翻译成更贴近盘面的语义结论",
                "strengths": [
                    "能处理文案、子类型和复杂上下文",
                    "适合沉淀 lesson / pattern / skill",
                ],
                "weaknesses": [
                    "直接走外部 API 会慢，也可能输出不稳定",
                    "不能替代程序化事实计算与验证",
                ],
                "current_takeaway": (
                    "优先服务解释层、方法论沉淀层和盘后复盘，不直接接管主排序。"
                ),
            },
        ]

    def _cluster_records(self, result, detail_df):
        clusters = {}
        self._add_cluster_rows(
            clusters,
            result.get("stock_report", pd.DataFrame()),
            cluster_col="分组",
            name_col="名称",
            body_col="实体",
            source="stock_report",
        )
        self._add_cluster_rows(
            clusters,
            result.get("industry_report", pd.DataFrame()),
            cluster_col="板块",
            name_col="板块",
            body_col="实体",
            source="industry_report",
        )
        if detail_df is not None and not detail_df.empty and "theme_cluster" in detail_df.columns:
            for _, row in detail_df.iterrows():
                cluster = str(row.get("theme_cluster", "") or "").strip()
                if not cluster:
                    continue
                body = self._to_float(row.get("body_pct"))
                item = clusters.setdefault(cluster, {
                    "count": 0,
                    "success_count": 0,
                    "body_sum": 0.0,
                    "avg_body_pct": 0.0,
                    "positive_body_count": 0,
                    "sources": set(),
                    "examples": [],
                })
                item["count"] += 1
                item["body_sum"] += body
                item["avg_body_pct"] = item["body_sum"] / item["count"]
                item["positive_body_count"] += int(body > 0)
                item["success_count"] += int(self._as_bool(row.get("validation_success")))
                item["sources"].add("signal_detail")
                if row.get("name") and row.get("name") not in item["examples"]:
                    item["examples"].append(str(row.get("name")))
        return clusters

    def _add_cluster_rows(self, clusters, df, cluster_col, name_col, body_col, source):
        if df is None or df.empty or cluster_col not in df.columns or body_col not in df.columns:
            return
        work = df[[cluster_col, name_col, body_col]].copy()
        work[body_col] = (
            work[body_col]
            .astype(str)
            .str.replace("%", "", regex=False)
            .str.replace("+", "", regex=False)
        )
        work[body_col] = pd.to_numeric(work[body_col], errors="coerce")
        work = work.dropna(subset=[body_col])
        for _, row in work.iterrows():
            cluster = self._cluster_text(row.get(cluster_col, ""))
            if not cluster:
                continue
            body = self._to_float(row.get(body_col))
            item = clusters.setdefault(cluster, {
                "count": 0,
                "success_count": 0,
                "body_sum": 0.0,
                "avg_body_pct": 0.0,
                "positive_body_count": 0,
                "sources": set(),
                "examples": [],
            })
            item["count"] += 1
            item["body_sum"] += body
            item["avg_body_pct"] = item["body_sum"] / item["count"]
            item["positive_body_count"] += int(body > 0)
            item["success_count"] += int(body > 0)
            item["sources"].add(source)
            name = self._cluster_text(row.get(name_col, ""))
            if name and name not in item["examples"]:
                item["examples"].append(name)

    def _metric_success_rate(self, detail_df, category):
        if detail_df is None or detail_df.empty:
            return 0.0
        work = detail_df[detail_df["signal_category"] == category]
        if work.empty:
            return 0.0
        success = work["validation_success"].map(self._as_bool).sum()
        return round(float(success) / len(work) * 100, 2)

    @staticmethod
    def _cluster_text(value):
        if isinstance(value, pd.Series):
            value = next((item for item in value.tolist() if pd.notna(item) and str(item).strip()), "")
        if value is None:
            return ""
        try:
            if pd.isna(value):
                return ""
        except Exception:
            pass
        return str(value).strip()

    def _derive_analyst_judgment(self, result, detail_df):
        if detail_df.empty:
            return "本次未触发可验证信号，主要用于保存因子快照。"
        cp_df = detail_df[detail_df["signal_category"] == "trap"]
        rev_df = detail_df[detail_df["signal_category"] == "reversal"]
        trend_df = detail_df[detail_df["signal_category"] == "trend"]
        parts = []
        if not cp_df.empty:
            avg_body = pd.to_numeric(cp_df["body_pct"], errors="coerce").mean()
            parts.append(f"CP 风险平均实体 {avg_body:+.2f}%，用于衡量高开或强势后兑现是否成立。")
        if not rev_df.empty:
            avg_body = pd.to_numeric(rev_df["body_pct"], errors="coerce").mean()
            parts.append(f"反核机会平均实体 {avg_body:+.2f}%，关注低开后的承接质量。")
        if not trend_df.empty:
            avg_body = pd.to_numeric(trend_df["body_pct"], errors="coerce").mean()
            parts.append(f"趋势机会平均实体 {avg_body:+.2f}%，更适合跟踪独立强势标的。")
        return " ".join(parts)

    def _derive_follow_up_points(self, result, detail_df):
        points = []
        state = (result.get("data_status", {}) or {}).get("session_state", "unknown")
        if state != "closed":
            points.append("收盘后重新同步当日 closed 数据，并覆盖本日验证。")
        if not detail_df.empty:
            failed = detail_df[detail_df["validation_result"] == "failed"]
            if not failed.empty:
                names = "、".join(failed["name"].astype(str).head(5).tolist())
                points.append(f"复盘失败样本的触发条件和文案: {names}")
            cp_df = detail_df[detail_df["signal_category"] == "trap"]
            if not cp_df.empty:
                points.append("继续区分 CP 子类型: 高开诱多 vs 强势后弱开兑现。")
        matched_patterns = result.get("matched_patterns", []) if isinstance(result, dict) else []
        for item in matched_patterns[:2]:
            name = str(item.get("name") or item.get("id") or "").strip()
            if name:
                points.append(f"匹配市场模式: {name}")
        if not points:
            points.append("继续累积样本，观察同一阈值在不同 OAR 环境下的稳定性。")
        return points

    def _pick_notable_records(self, records, limit=8):
        def score(row):
            return abs(self._to_float(row.get("body_pct"))) + abs(self._to_float(row.get("cp"))) / 100
        rows = sorted(records, key=score, reverse=True)[:limit]
        keep = [
            "signal_category", "signal_family", "target_type", "name",
            "cp", "sa", "auction_pct", "close_pct", "body_pct",
            "validation_result", "trigger_reason",
        ]
        return [{k: row.get(k, "") for k in keep} for row in rows]

    def _format_analysis_markdown(self, payload):
        lines = [
            f"# Auction Review {payload.get('date')}",
            "",
            "## Data Status",
            f"- session_state: {payload.get('data_status', {}).get('session_state', 'unknown')}",
            f"- fetched_at: {payload.get('data_status', {}).get('fetched_at', '-')}",
            f"- validation_scope: {payload.get('validation_scope')}",
            f"- methodology: {payload.get('methodology_refs', {}).get('methodology', '-')}",
            f"- pattern_registry: {payload.get('methodology_refs', {}).get('pattern_registry', '-')}",
            "",
            "## Core Conclusion",
            f"- {payload.get('core_conclusion')}",
            "",
            "## Matched Patterns",
        ]
        matched_patterns = payload.get("matched_patterns", [])
        if matched_patterns:
            for item in matched_patterns:
                lines.append(
                    f"- {item.get('name') or item.get('id')} | confidence={item.get('match_confidence', '-')}"
                )
                facts = item.get("matched_facts", {}) or {}
                if facts:
                    lines.append(f"  facts: {facts}")
        else:
            lines.append("- none")
        lines.extend([
            "",
            "## Validation Metrics",
        ])
        for row in payload.get("metrics", []):
            lines.append(
                f"- {row.get('signal_family')}({row.get('signal_category')}): "
                f"{row.get('success_count')}/{row.get('trigger_count')}, "
                f"success_rate={row.get('success_rate')}%, avg_body={row.get('avg_body_pct')}"
            )
        lines.extend(["", "## Analyst Judgment", f"- {payload.get('analyst_judgment')}", "", "## Follow Up"])
        for point in payload.get("follow_up_points", []):
            lines.append(f"- {point}")
        lines.extend(["", "## Notable Failures"])
        for row in payload.get("notable_failures", []):
            lines.append(f"- {row.get('name')} {row.get('signal_family')} body={row.get('body_pct')} result={row.get('validation_result')}")
        lines.extend(["", "## Notable Successes"])
        for row in payload.get("notable_successes", []):
            lines.append(f"- {row.get('name')} {row.get('signal_family')} body={row.get('body_pct')} result={row.get('validation_result')}")
        lines.append("")
        return "\n".join(lines)

    def _save_analysis_lessons(self, payload):
        lessons_dir = os.path.join("reports", "analysis", "lessons")
        os.makedirs(lessons_dir, exist_ok=True)
        path = os.path.join(lessons_dir, "auction_lessons.jsonl")
        date = str(payload.get("date"))

        existing = []
        existing_keys = set()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        item = json.loads(line)
                    except Exception:
                        continue
                    existing.append(item)
                    existing_keys.add(self._lesson_key(item))

        new_items = []
        for row in payload.get("notable_failures", []):
            item = {
                "date": date,
                "source": "auction_review",
                "signal_type": row.get("signal_family", row.get("signal_category", "")),
                "case": row.get("name", ""),
                "facts": {
                    "cp": row.get("cp"),
                    "sa": row.get("sa"),
                    "auction_pct": row.get("auction_pct"),
                    "close_pct": row.get("close_pct"),
                    "body_pct": row.get("body_pct"),
                },
                "lesson": "Signal failed under current validation rule; review whether trigger subtype or threshold needs adjustment after repeated samples.",
                "suggested_change": "Keep as observation until similar failures repeat.",
                "status": "observed",
            }
            if self._lesson_key(item) not in existing_keys:
                new_items.append(item)
                existing_keys.add(self._lesson_key(item))

        for item in self._build_pattern_lessons(payload):
            if self._lesson_key(item) not in existing_keys:
                new_items.append(item)
                existing_keys.add(self._lesson_key(item))

        with open(path, "w", encoding="utf-8") as f:
            for item in existing + new_items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    @staticmethod
    def _lesson_key(item):
        return (
            str(item.get("date", "")),
            str(item.get("source", "")),
            str(item.get("signal_type", "")),
            str(item.get("case", "")),
        )

    def _build_pattern_lessons(self, payload):
        date = str(payload.get("date", ""))
        lessons = []
        for item in payload.get("matched_patterns", []):
            lessons.append({
                "date": date,
                "source": "auction_review",
                "signal_type": "market_pattern",
                "case": item.get("id", item.get("name", "")),
                "facts": item.get("matched_facts", {}),
                "lesson": f"Matched market pattern: {item.get('name') or item.get('id')}",
                "suggested_change": "Keep accumulating same-pattern samples before changing deterministic rules.",
                "status": str(item.get("status", "observed") or "observed"),
            })
        return lessons

    def _derive_follow_up_points_v2(self, result, detail_df):
        points = []
        state = (result.get("data_status", {}) or {}).get("session_state", "unknown")
        if state != "closed":
            points.append("收盘后重新同步当日 closed 数据，并覆盖本日验证。")
        if not detail_df.empty:
            failed = detail_df[detail_df["validation_result"] == "failed"]
            if not failed.empty:
                names = "、".join(failed["name"].astype(str).head(5).tolist())
                points.append(f"复盘失败样本的触发条件和文案需要继续回看: {names}")
            cp_df = detail_df[detail_df["signal_category"] == "trap"]
            if not cp_df.empty:
                points.append("继续拆分 CP 子类型: 高开诱多 vs 强势后弱开兑现。")
        unmatched = (result.get("unmatched_auction_summary", {}) or {}) if isinstance(result, dict) else {}
        if int(unmatched.get("count", 0) or 0) > 0:
            points.append(
                f"存在 {int(unmatched.get('count', 0) or 0)} 只未撮合/零价竞价快照，"
                "后续可结合累计汇总优化股票池与 9:25 可交易覆盖率。"
            )
        matched_patterns = result.get("matched_patterns", []) if isinstance(result, dict) else []
        for item in matched_patterns[:2]:
            name = str(item.get("name") or item.get("id") or "").strip()
            if name:
                points.append(f"匹配市场模式: {name}")
        pattern_progress = result.get("pattern_progress", []) if isinstance(result, dict) else []
        for item in pattern_progress[:2]:
            if item.get("recommendation") == "candidate_for_rule_or_weight":
                points.append(f"Pattern ready for upgrade review: {item.get('name')}")
            elif item.get("recommendation") == "watch_closely":
                points.append(f"Pattern needs one more repeated sample before upgrade review: {item.get('name')}")
        if not points:
            points.append("继续积累样本，观察同一阈值在不同 OAR 环境下的稳定性。")
        return points

    def _format_analysis_markdown_v2(self, payload):
        lines = [
            f"# Auction Review {payload.get('date')}",
            "",
            "## Data Status",
            f"- session_state: {payload.get('data_status', {}).get('session_state', 'unknown')}",
            f"- fetched_at: {payload.get('data_status', {}).get('fetched_at', '-')}",
            f"- validation_scope: {payload.get('validation_scope')}",
            f"- methodology: {payload.get('methodology_refs', {}).get('methodology', '-')}",
            f"- pattern_registry: {payload.get('methodology_refs', {}).get('pattern_registry', '-')}",
            f"- pattern_progress: {payload.get('methodology_refs', {}).get('pattern_progress', '-')}",
            "",
            "## Intraday Confirmation",
        ]
        confirm = payload.get("intraday_confirmation_summary", {}) or {}
        lines.extend([
            f"- available: {confirm.get('available')}",
            f"- feature_timestamp: {confirm.get('feature_timestamp')}",
            f"- coverage_count: {confirm.get('coverage_count')}",
            f"- confirmed_strength_count: {confirm.get('confirmed_strength_count')}",
            f"- trend_enriched_count: {confirm.get('trend_enriched_count')}",
            f"- trend_rejected_count: {confirm.get('trend_rejected_count')}",
            f"- trend_selected_after_confirmation: {confirm.get('trend_selected_after_confirmation')}",
            "",
            "## Unmatched Auction Snapshots",
        ])
        unmatched = payload.get("unmatched_auction_summary", {}) or {}
        lines.extend([
            f"- count: {unmatched.get('count', 0)}",
            f"- sample_names: {unmatched.get('sample_names', [])}",
            "",
            "## Core Conclusion",
            f"- {payload.get('core_conclusion')}",
            "",
            "## Matched Patterns",
        ])
        matched_patterns = payload.get("matched_patterns", [])
        if matched_patterns:
            for item in matched_patterns:
                lines.append(
                    f"- {item.get('name') or item.get('id')} | confidence={item.get('match_confidence', '-')}"
                )
                facts = item.get("matched_facts", {}) or {}
                if facts:
                    lines.append(f"  facts: {facts}")
        else:
            lines.append("- none")
        lines.extend(["", "## Pattern Progress"])
        pattern_progress = payload.get("pattern_progress", [])
        if pattern_progress:
            for item in pattern_progress:
                lines.append(
                    f"- {item.get('name')} | count={item.get('occurrence_count')} | "
                    f"recommendation={item.get('recommendation')}"
                )
                if item.get("dates"):
                    lines.append(f"  dates: {item.get('dates')}")
                if item.get("note"):
                    lines.append(f"  note: {item.get('note')}")
        else:
            lines.append("- none")
        lines.extend(["", "## Shortlist Score Drivers"])
        score_rows = payload.get("shortlist_score_summary", [])
        if score_rows:
            for row in score_rows:
                lines.append(
                    f"- {row.get('signal_category')} | {row.get('name')} | score={row.get('action_score')} | "
                    f"regime={row.get('score_regime_bonus')} | cluster={row.get('score_theme_cluster_bonus')} | "
                    f"group={row.get('score_group_regime_bonus')} | confirm={row.get('score_confirmation_bonus')} | "
                    f"reliability={row.get('score_reliability_penalty')}"
                )
                if row.get("theme_cluster"):
                    lines.append(f"  theme_cluster: {row.get('theme_cluster')}")
                if row.get("shortlist_reason"):
                    lines.append(f"  reason: {row.get('shortlist_reason')}")
        else:
            lines.append("- none")
        lines.extend(["", "## Technical Route Comparison"])
        for item in payload.get("technical_route_comparison", []):
            lines.append(
                f"- {item.get('route')} | status={item.get('status')} | role={item.get('role')}"
            )
            strengths = item.get("strengths", []) or []
            weaknesses = item.get("weaknesses", []) or []
            takeaway = item.get("current_takeaway", "")
            if strengths:
                lines.append(f"  strengths: {strengths}")
            if weaknesses:
                lines.append(f"  weaknesses: {weaknesses}")
            if takeaway:
                lines.append(f"  takeaway: {takeaway}")
        lines.extend(["", "## Validation Metrics"])
        for row in payload.get("metrics", []):
            lines.append(
                f"- {row.get('signal_family')}({row.get('signal_category')}): "
                f"{row.get('success_count')}/{row.get('trigger_count')}, "
                f"success_rate={row.get('success_rate')}%, avg_body={row.get('avg_body_pct')}"
            )
        lines.extend(["", "## Analyst Judgment", f"- {payload.get('analyst_judgment')}", "", "## Follow Up"])
        for point in payload.get("follow_up_points", []):
            lines.append(f"- {point}")
        lines.extend(["", "## Notable Failures"])
        for row in payload.get("notable_failures", []):
            lines.append(f"- {row.get('name')} {row.get('signal_family')} body={row.get('body_pct')} result={row.get('validation_result')}")
        lines.extend(["", "## Notable Successes"])
        for row in payload.get("notable_successes", []):
            lines.append(f"- {row.get('name')} {row.get('signal_family')} body={row.get('body_pct')} result={row.get('validation_result')}")
        lines.append("")
        return "\n".join(lines)

    def _save_analysis_lessons_v2(self, payload):
        lessons_dir = os.path.join("reports", "analysis", "lessons")
        os.makedirs(lessons_dir, exist_ok=True)
        path = os.path.join(lessons_dir, "auction_lessons.jsonl")
        date = str(payload.get("date"))

        existing = []
        existing_keys = set()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        item = json.loads(line)
                    except Exception:
                        continue
                    existing.append(item)
                    existing_keys.add(self._lesson_key(item))

        new_items = []
        for row in payload.get("notable_failures", []):
            item = {
                "date": date,
                "source": "auction_review",
                "signal_type": row.get("signal_family", row.get("signal_category", "")),
                "case": row.get("name", ""),
                "facts": {
                    "cp": row.get("cp"),
                    "sa": row.get("sa"),
                    "auction_pct": row.get("auction_pct"),
                    "close_pct": row.get("close_pct"),
                    "body_pct": row.get("body_pct"),
                },
                "lesson": "Signal failed under current validation rule; review whether trigger subtype or threshold needs adjustment after repeated samples.",
                "suggested_change": "Keep as observation until similar failures repeat.",
                "status": "observed",
            }
            if self._lesson_key(item) not in existing_keys:
                new_items.append(item)
                existing_keys.add(self._lesson_key(item))

        for item in self._build_pattern_lessons(payload):
            if self._lesson_key(item) not in existing_keys:
                new_items.append(item)
                existing_keys.add(self._lesson_key(item))

        with open(path, "w", encoding="utf-8") as f:
            for item in existing + new_items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        self._save_pattern_progress(payload)

    def _save_pattern_progress(self, payload):
        path = self._methodology_refs()["pattern_progress"]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        progress = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "date": str(payload.get("date", "")),
            "patterns": payload.get("pattern_progress", []),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)

    def _json_sanitize(self, value):
        if isinstance(value, dict):
            return {str(k): self._json_sanitize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._json_sanitize(v) for v in value]
        if isinstance(value, tuple):
            return [self._json_sanitize(v) for v in value]
        if hasattr(value, "item"):
            try:
                return value.item()
            except Exception:
                pass
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass
        return value

    def _build_validation_records(self, result):
        date = int(result.get("date", 0) or 0)
        status = result.get("data_status", {}) or {}
        signals = result.get("signals", {}) or {}
        log_path = ""
        if getattr(self, "_log_session", None) is not None:
            log_path = os.path.abspath(getattr(self._log_session, "log_path", "") or "")

        records = []
        for category, items in signals.items():
            family = self._signal_family(category)
            signal_order = self._signal_order(category)
            for sig in items:
                data = sig.get("data", {}) or {}
                body_pct = self._to_float(data.get("body_pct"))
                validation = self._validate_signal(category, body_pct)
                theme_cluster = self._infer_theme_cluster(sig, data)
                breakdown = sig.get("action_score_breakdown", {}) or {}
                records.append({
                    "date": date,
                    "signal_category": category,
                    "signal_family": family,
                    "signal_order": signal_order,
                    "signal_label": sig.get("signal", ""),
                    "target_type": sig.get("type", ""),
                    "target_order": sig.get("order", ""),
                    "name": sig.get("name", ""),
                    "scenario": sig.get("scenario", ""),
                    "trigger_reason": data.get("trigger_reason", ""),
                    "cp": data.get("cp"),
                    "sa": data.get("sa"),
                    "auction_pct": round(self._to_float(data.get("auction_pct")), 4),
                    "auction_source": data.get("auction_source", ""),
                    "auction_amount_exact": data.get("auction_amount_exact", ""),
                    "auction_asof": data.get("auction_asof", ""),
                    "close_pct": round(self._to_float(data.get("close_pct")), 4),
                    "body_pct": round(body_pct, 4),
                    "prev_pct": round(self._to_float(data.get("prev_pct")), 4),
                    "prev_body_pct": round(self._to_float(data.get("prev_body_pct")), 4),
                    "prev_vol_ratio": round(self._to_float(data.get("prev_vol_ratio"), 1.0), 4),
                    "vol_ratio": round(self._to_float(data.get("vol_ratio"), 1.0), 4),
                    "pos_5d": round(self._to_float(data.get("pos_5d"), 50), 4),
                    "amt_rank": data.get("amt_rank", sig.get("amt_rank", "")),
                    "score_amt_rank": sig.get("amt_rank", ""),
                    "validation_rule": validation["rule"],
                    "validation_success": validation["success"],
                    "validation_result": validation["result"],
                    "strong_validation_success": self._strong_validation_success(category, body_pct),
                    "candidate_generated_at": "auction",
                    "outcome_label_source": "post_close_body_pct",
                    "actionable": bool(sig.get("actionable", False)),
                    "action_score": round(self._to_float(sig.get("action_score")), 4),
                    "score_base": round(self._to_float(breakdown.get("base_score")), 4),
                    "score_rank_bonus": round(self._to_float(breakdown.get("rank_bonus")), 4),
                    "score_auction_bonus": round(self._to_float(breakdown.get("auction_bonus")), 4),
                    "score_prev_pct_bonus": round(self._to_float(breakdown.get("prev_pct_bonus")), 4),
                    "score_prev_vol_bonus": round(self._to_float(breakdown.get("prev_vol_bonus")), 4),
                    "score_position_bonus": round(self._to_float(breakdown.get("position_bonus")), 4),
                    "score_regime_bonus": round(self._to_float(breakdown.get("regime_bonus")), 4),
                    "score_theme_cluster_bonus": round(self._to_float(breakdown.get("theme_cluster_bonus")), 4),
                    "score_group_regime_bonus": round(self._to_float(breakdown.get("group_regime_bonus")), 4),
                    "score_confirmation_bonus": round(self._to_float(breakdown.get("confirmation_bonus")), 4),
                    "score_reliability_penalty": round(self._to_float(breakdown.get("reliability_penalty")), 4),
                    "shortlist_reason": sig.get("shortlist_reason", ""),
                    "action_filter_reason": sig.get("action_filter_reason", ""),
                    "market_regime": sig.get("market_regime", ""),
                    "theme_cluster": theme_cluster,
                    "theme_cluster_source": self._infer_theme_cluster_source(sig, data, theme_cluster),
                    "reversal_layer": sig.get("reversal_layer", ""),
                    "reversal_layer_rank": sig.get("reversal_layer_rank", ""),
                    "data_session_state": status.get("session_state", ""),
                    "data_fetched_at": status.get("fetched_at", ""),
                    "validation_scope": "post_close_final" if status.get("post_close_validation") else "provisional_intraday",
                    "log_path": log_path,
                })
        return records

    @staticmethod
    def _infer_theme_cluster(sig, data):
        for key in ("group", "industry", "theme_cluster"):
            value = data.get(key)
            if value:
                return str(value)
        for key in ("industry", "group"):
            value = sig.get(key)
            if value:
                return str(value)
        target_type = str(data.get("target_type", "") or sig.get("type", ""))
        if target_type == "industry":
            return str(sig.get("name", "") or "")
        if target_type in {"ETF", "index"}:
            return str(sig.get("name", "") or "")
        return ""

    @staticmethod
    def _infer_theme_cluster_source(sig, data, theme_cluster):
        if not theme_cluster:
            return ""
        if data.get("group"):
            return "data.group"
        if data.get("industry"):
            return "data.industry"
        if sig.get("industry"):
            return "signal.industry"
        if sig.get("group"):
            return "signal.group"
        return "signal.name"

    def _save_factor_snapshots(self, result, daily_dir):
        """保存每日全量特征快照，便于后续重新评估阈值。"""
        date = int(result.get("date", 0) or 0)
        status = result.get("data_status", {}) or {}
        snapshots = [
            ("factor_snapshot_index.csv", "index_factors", "index", "指数"),
            ("factor_snapshot_etf.csv", "etf_auction", "etf", "ETF"),
            ("factor_snapshot_stock.csv", "stock_factors", "stock", "名称"),
            ("factor_snapshot_industry_topk.csv", "industry_report", "industry", "板块"),
        ]
        for filename, result_key, universe_type, name_col in snapshots:
            df = result.get(result_key, pd.DataFrame())
            snapshot = self._build_factor_snapshot(date, result.get("market_oar", 0), df, universe_type, name_col)
            if not snapshot.empty:
                snapshot["data_session_state"] = status.get("session_state", "")
                snapshot["data_fetched_at"] = status.get("fetched_at", "")
                snapshot["validation_scope"] = "post_close_final" if status.get("post_close_validation") else "provisional_intraday"
                self._write_csv_safe(snapshot, os.path.join(daily_dir, filename))

        self._save_excluded_snapshot_records(result, daily_dir)

    def _save_data_quality_records(self, result):
        date = str(result.get("date", "") or "")
        if not date:
            return
        daily_dir = os.path.join("reports", "validation", "daily", date)
        os.makedirs(daily_dir, exist_ok=True)
        self._save_excluded_snapshot_records(result, daily_dir)
        self._save_confirmed_strength_records(result, daily_dir)
        self._refresh_unmatched_auction_summary()
        self._refresh_stock_pool_auction_reliability()
        self._refresh_confirmed_strength_summary()

    def _save_excluded_snapshot_records(self, result, daily_dir):
        excluded = result.get("excluded_price_discontinuities", pd.DataFrame())
        if excluded is None or excluded.empty:
            return
        excluded = self._attach_stock_pool_group(excluded)
        columns = [
            "code", "name", "group", "industry", "open", "close", "prev_close",
            "auction_pct", "body_pct", "price_discontinuity_limit_pct",
            "price_discontinuity_reason",
        ]
        existing = [column for column in columns if column in excluded.columns]
        excluded[existing].to_csv(
            os.path.join(daily_dir, "excluded_price_discontinuities.csv"),
            index=False,
            encoding="utf-8-sig",
        )
        unmatched = excluded[
            excluded.get("price_discontinuity_reason", "").astype(str) == "no_matched_auction_price"
        ].copy()
        if unmatched.empty:
            return
        unmatched_columns = [
            "code", "name", "group", "industry", "auction_source", "auction_amount_exact",
            "auction_price", "open", "last", "close", "prev_close", "pre_close",
            "auction_pct", "auction_coverage_ratio", "price_discontinuity_reason",
        ]
        existing_unmatched = [column for column in unmatched_columns if column in unmatched.columns]
        unmatched[existing_unmatched].to_csv(
            os.path.join(daily_dir, "unmatched_auction_snapshots.csv"),
            index=False,
            encoding="utf-8-sig",
        )

    def _save_confirmed_strength_records(self, result, daily_dir):
        intraday_meta = result.get("intraday_confirmation", {}) or {}
        signal_meta = intraday_meta.get("signal_enrichment", {}) or {}
        path = str(intraday_meta.get("path", "") or signal_meta.get("path", "") or "")
        if not path or not os.path.exists(path):
            return
        try:
            confirm_df = pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str})
        except Exception:
            return
        if confirm_df.empty or "execution_bias" not in confirm_df.columns:
            return
        confirmed = confirm_df[confirm_df["execution_bias"].astype(str) == "confirmed_strength"].copy()
        if confirmed.empty:
            return
        confirmed = self._attach_stock_pool_group(confirmed)
        trend_shortlist = result.get("shortlist", {}).get("trend", []) or []
        trend_by_code = {}
        for item in trend_shortlist:
            data = item.get("data", {}) or {}
            code = str(data.get("code", "") or "")
            if code:
                trend_by_code[code] = item
        confirmed["date"] = str(result.get("date", "") or "")
        confirmed["selected_in_trend_shortlist"] = confirmed["code"].astype(str).map(lambda code: code in trend_by_code)
        confirmed["trend_action_score"] = confirmed["code"].astype(str).map(
            lambda code: round(self._to_float((trend_by_code.get(code) or {}).get("action_score")), 4)
        )
        confirmed["trend_shortlist_reason"] = confirmed["code"].astype(str).map(
            lambda code: (trend_by_code.get(code) or {}).get("shortlist_reason", "")
        )
        columns = [
            "date", "code", "name", "group", "time_str", "feature_timestamp",
            "selected_in_trend_shortlist", "trend_action_score", "trend_shortlist_reason",
            "price_vs_open_pct", "rs_vs_etf_pct", "rs_vs_index_pct",
            "amount_1m_ratio", "amount_3m", "amount_5m", "volume_price_state",
            "benchmark_etf_code", "benchmark_index_code", "execution_bias", "realtime_source",
        ]
        existing = [column for column in columns if column in confirmed.columns]
        confirmed[existing].to_csv(
            os.path.join(daily_dir, "confirmed_strength_candidates.csv"),
            index=False,
            encoding="utf-8-sig",
        )

    def _refresh_unmatched_auction_summary(self):
        daily_root = os.path.join("reports", "validation", "daily")
        if not os.path.exists(daily_root):
            return
        rows = []
        for entry in sorted(os.listdir(daily_root)):
            csv_path = os.path.join(daily_root, entry, "unmatched_auction_snapshots.csv")
            if not os.path.exists(csv_path):
                continue
            try:
                df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype={"code": str})
            except Exception:
                continue
            if df.empty:
                continue
            df["date"] = entry
            rows.append(df)
        if not rows:
            return
        all_rows = pd.concat(rows, ignore_index=True)
        detail_path = os.path.join("reports", "validation", "unmatched_auction_snapshots_all.csv")
        self._write_csv_safe(all_rows, detail_path)

        work = all_rows.copy()
        for column in ("name", "group", "industry", "auction_source"):
            if column not in work.columns:
                work[column] = ""
        summary = (
            work.groupby("code", dropna=False)
            .agg(
                name=("name", "last"),
                group=("group", "last"),
                industry=("industry", "last"),
                days_missing=("date", "nunique"),
                total_occurrences=("date", "size"),
                latest_date=("date", "max"),
                auction_source=("auction_source", "last"),
            )
            .reset_index()
            .sort_values(["days_missing", "total_occurrences", "code"], ascending=[False, False, True])
        )
        summary_path = os.path.join("reports", "validation", "unmatched_auction_snapshot_summary.csv")
        self._write_csv_safe(summary, summary_path)
        self._write_csv_safe(
            self._aggregate_unmatched_by_dimension(work, "industry"),
            os.path.join("reports", "validation", "unmatched_auction_industry_summary.csv"),
        )
        self._write_csv_safe(
            self._aggregate_unmatched_by_dimension(work, "group"),
            os.path.join("reports", "validation", "unmatched_auction_group_summary.csv"),
        )

    def _refresh_stock_pool_auction_reliability(self):
        path = os.path.join("reports", "validation", "unmatched_auction_snapshots_all.csv")
        if not os.path.exists(path):
            return
        try:
            unmatched = pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str})
        except Exception:
            return
        if unmatched.empty or "date" not in unmatched.columns:
            return
        stock_pool = self._load_stock_pool_frame()
        if stock_pool.empty:
            return
        total_days = int(unmatched["date"].astype(str).nunique())
        if total_days <= 0:
            return
        work = unmatched.copy()
        work["date"] = work["date"].astype(str)
        summary = (
            work.groupby("code", dropna=False)
            .agg(
                days_missing=("date", "nunique"),
                total_occurrences=("date", "size"),
                latest_date=("date", "max"),
                latest_auction_source=("auction_source", "last"),
            )
            .reset_index()
        )
        merged = stock_pool.merge(summary, on="code", how="left")
        for column in ("days_missing", "total_occurrences"):
            merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0).astype(int)
        merged["latest_date"] = merged["latest_date"].fillna("")
        merged["latest_auction_source"] = merged["latest_auction_source"].fillna("")
        merged["observed_days"] = total_days
        merged["matched_days"] = (merged["observed_days"] - merged["days_missing"]).clip(lower=0)
        merged["missing_ratio"] = (merged["days_missing"] / merged["observed_days"]).round(4)
        merged["auction_reliability_score"] = ((1.0 - merged["missing_ratio"]) * 100).round(2)
        merged["preopen_signal_action"] = merged.apply(self._auction_reliability_action, axis=1)
        merged["preopen_signal_note"] = merged.apply(self._auction_reliability_note, axis=1)
        merged = merged.sort_values(
            ["missing_ratio", "days_missing", "code"],
            ascending=[False, False, True],
        )
        self._write_csv_safe(
            merged,
            os.path.join("reports", "validation", "stock_pool_auction_reliability.csv"),
        )

        action_summary = (
            merged.groupby("preopen_signal_action", dropna=False)
            .agg(
                code_count=("code", "nunique"),
                avg_reliability_score=("auction_reliability_score", "mean"),
                avg_missing_ratio=("missing_ratio", "mean"),
            )
            .reset_index()
            .sort_values(["code_count", "avg_missing_ratio"], ascending=[False, False])
        )
        action_summary["avg_reliability_score"] = action_summary["avg_reliability_score"].round(2)
        action_summary["avg_missing_ratio"] = action_summary["avg_missing_ratio"].round(4)
        self._write_csv_safe(
            action_summary,
            os.path.join("reports", "validation", "stock_pool_auction_reliability_action_summary.csv"),
        )

    def _refresh_confirmed_strength_summary(self):
        daily_root = os.path.join("reports", "validation", "daily")
        if not os.path.exists(daily_root):
            return
        rows = []
        for entry in sorted(os.listdir(daily_root)):
            csv_path = os.path.join(daily_root, entry, "confirmed_strength_candidates.csv")
            if not os.path.exists(csv_path):
                continue
            try:
                df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype={"code": str})
            except Exception:
                continue
            if df.empty:
                continue
            if "date" not in df.columns:
                df["date"] = entry
            rows.append(df)
        if not rows:
            return
        all_rows = pd.concat(rows, ignore_index=True)
        if "date" in all_rows.columns:
            all_rows["date"] = all_rows["date"].astype(str)
        for column in ("price_vs_open_pct", "rs_vs_etf_pct", "rs_vs_index_pct", "amount_1m_ratio"):
            if column in all_rows.columns:
                all_rows[column] = pd.to_numeric(all_rows[column], errors="coerce")
        if "selected_in_trend_shortlist" in all_rows.columns:
            all_rows["selected_in_trend_shortlist"] = all_rows["selected_in_trend_shortlist"].map(self._as_bool)
        regime_map = self._load_daily_review_context_map()
        if regime_map:
            context = pd.DataFrame.from_dict(regime_map, orient="index").reset_index().rename(columns={"index": "date"})
            context["date"] = context["date"].astype(str)
            all_rows = all_rows.merge(context, on="date", how="left")
        else:
            all_rows["market_regime"] = ""
            all_rows["environment_decision"] = ""
            all_rows["leading_clusters"] = ""
        self._write_csv_safe(
            all_rows,
            os.path.join("reports", "validation", "confirmed_strength_candidates_all.csv"),
        )
        work = all_rows.copy()
        for column in ("name", "group"):
            if column not in work.columns:
                work[column] = ""
        code_summary = (
            work.groupby("code", dropna=False)
            .agg(
                name=("name", "last"),
                group=("group", "last"),
                confirmed_days=("date", "nunique"),
                total_occurrences=("date", "size"),
                latest_date=("date", "max"),
                avg_price_vs_open_pct=("price_vs_open_pct", "mean"),
                avg_rs_vs_etf_pct=("rs_vs_etf_pct", "mean"),
                avg_rs_vs_index_pct=("rs_vs_index_pct", "mean"),
                avg_amount_1m_ratio=("amount_1m_ratio", "mean"),
                shortlisted_count=("selected_in_trend_shortlist", "sum"),
            )
            .reset_index()
            .sort_values(["confirmed_days", "shortlisted_count", "avg_amount_1m_ratio"], ascending=[False, False, False])
        )
        self._write_csv_safe(
            code_summary,
            os.path.join("reports", "validation", "confirmed_strength_code_summary.csv"),
        )
        group_summary = (
            work.groupby("group", dropna=False)
            .agg(
                confirmed_count=("code", "size"),
                confirmed_days=("date", "nunique"),
                unique_codes=("code", "nunique"),
                avg_price_vs_open_pct=("price_vs_open_pct", "mean"),
                avg_rs_vs_etf_pct=("rs_vs_etf_pct", "mean"),
                avg_rs_vs_index_pct=("rs_vs_index_pct", "mean"),
                avg_amount_1m_ratio=("amount_1m_ratio", "mean"),
                shortlisted_count=("selected_in_trend_shortlist", "sum"),
            )
            .reset_index()
            .sort_values(["confirmed_count", "shortlisted_count"], ascending=[False, False])
        )
        self._write_csv_safe(
            group_summary,
            os.path.join("reports", "validation", "confirmed_strength_group_summary.csv"),
        )
        if "market_regime" in work.columns:
            regime_summary = (
                work.groupby("market_regime", dropna=False)
                .agg(
                    confirmed_count=("code", "size"),
                    confirmed_days=("date", "nunique"),
                    unique_codes=("code", "nunique"),
                    shortlisted_count=("selected_in_trend_shortlist", "sum"),
                    avg_price_vs_open_pct=("price_vs_open_pct", "mean"),
                    avg_rs_vs_etf_pct=("rs_vs_etf_pct", "mean"),
                    avg_rs_vs_index_pct=("rs_vs_index_pct", "mean"),
                    avg_amount_1m_ratio=("amount_1m_ratio", "mean"),
                )
                .reset_index()
                .sort_values(["confirmed_count", "shortlisted_count"], ascending=[False, False])
            )
            self._write_csv_safe(
                regime_summary,
                os.path.join("reports", "validation", "confirmed_strength_regime_summary.csv"),
            )
            regime_group_summary = (
                work.groupby(["market_regime", "group"], dropna=False)
                .agg(
                    confirmed_count=("code", "size"),
                    confirmed_days=("date", "nunique"),
                    unique_codes=("code", "nunique"),
                    shortlisted_count=("selected_in_trend_shortlist", "sum"),
                    avg_price_vs_open_pct=("price_vs_open_pct", "mean"),
                    avg_rs_vs_etf_pct=("rs_vs_etf_pct", "mean"),
                    avg_rs_vs_index_pct=("rs_vs_index_pct", "mean"),
                    avg_amount_1m_ratio=("amount_1m_ratio", "mean"),
                )
                .reset_index()
                .sort_values(["confirmed_count", "shortlisted_count"], ascending=[False, False])
            )
            self._write_csv_safe(
                regime_group_summary,
                os.path.join("reports", "validation", "confirmed_strength_regime_group_summary.csv"),
            )

    @staticmethod
    def _aggregate_unmatched_by_dimension(work, column):
        if column not in work.columns:
            return pd.DataFrame()
        summary = (
            work.groupby(column, dropna=False)
            .agg(
                missing_count=("code", "size"),
                missing_days=("date", "nunique"),
                unique_codes=("code", "nunique"),
                latest_date=("date", "max"),
            )
            .reset_index()
            .sort_values(["missing_count", "unique_codes"], ascending=[False, False])
        )
        return summary

    def _attach_stock_pool_group(self, df):
        if df is None or df.empty or "code" not in df.columns:
            return df
        work = df.copy()
        if "group" in work.columns and work["group"].notna().any():
            return work
        group_map = self._load_stock_pool_group_map()
        if not group_map:
            return work
        work["group"] = work["code"].astype(str).map(group_map).fillna("")
        return work

    @staticmethod
    def _load_stock_pool_group_map():
        path = os.path.abspath(UniverseConfig.STOCK_POOL_PATH)
        if not os.path.exists(path):
            return {}
        try:
            df = pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str})
        except Exception:
            return {}
        if df.empty or "code" not in df.columns or "group" not in df.columns:
            return {}
        return (
            df[["code", "group"]]
            .dropna(subset=["code"])
            .assign(code=lambda x: x["code"].astype(str), group=lambda x: x["group"].fillna("").astype(str))
            .set_index("code")["group"]
            .to_dict()
        )

    @staticmethod
    def _load_stock_pool_frame():
        path = os.path.abspath(UniverseConfig.STOCK_POOL_PATH)
        if not os.path.exists(path):
            return pd.DataFrame()
        try:
            df = pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str})
        except Exception:
            return pd.DataFrame()
        if df.empty or "code" not in df.columns:
            return pd.DataFrame()
        for column in ("name", "group", "note"):
            if column not in df.columns:
                df[column] = ""
        return (
            df[["code", "name", "group", "note"]]
            .dropna(subset=["code"])
            .assign(
                code=lambda x: x["code"].astype(str),
                name=lambda x: x["name"].fillna("").astype(str),
                group=lambda x: x["group"].fillna("").astype(str),
                note=lambda x: x["note"].fillna("").astype(str),
            )
        )

    @staticmethod
    def _auction_reliability_action(row):
        missing_ratio = AuctionRunner._to_float(row.get("missing_ratio"))
        days_missing = int(AuctionRunner._to_float(row.get("days_missing"), 0))
        if days_missing >= 3 and missing_ratio >= 0.6:
            return "exclude_from_0925_decision"
        if days_missing >= 2 and missing_ratio >= 0.35:
            return "deprioritize_preopen_signal"
        if days_missing >= 1:
            return "observe_auction_reliability"
        return "normal"

    @staticmethod
    def _auction_reliability_note(row):
        days_missing = int(AuctionRunner._to_float(row.get("days_missing"), 0))
        observed_days = int(AuctionRunner._to_float(row.get("observed_days"), 0))
        action = str(row.get("preopen_signal_action", "") or "")
        if action == "exclude_from_0925_decision":
            return f"近{observed_days}个观测日中有{days_missing}天09:25无有效撮合价，盘前信号暂不可靠。"
        if action == "deprioritize_preopen_signal":
            return f"近{observed_days}个观测日中有{days_missing}天09:25无有效撮合价，盘前只做弱参考。"
        if action == "observe_auction_reliability":
            return f"近{observed_days}个观测日出现过{days_missing}天09:25无有效撮合价，继续观察。"
        return "近阶段09:25竞价撮合覆盖稳定，可正常参与盘前判断。"

    def _load_daily_review_context_map(self):
        root = os.path.join("reports", "analysis", "daily")
        if not os.path.isdir(root):
            return {}
        context = {}
        for date in sorted(os.listdir(root)):
            path = os.path.join(root, date, "auction_review.json")
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    review = json.load(f)
            except Exception:
                continue
            context[str(date)] = {
                "market_regime": str((review.get("market_regime", {}) or {}).get("label", "") or ""),
                "environment_decision": str((review.get("environment_gate", {}) or {}).get("decision", "") or ""),
                "leading_clusters": json.dumps(review.get("leading_clusters", []) or [], ensure_ascii=False),
            }
        return context

    @staticmethod
    def _write_csv_safe(df, path):
        abs_path = os.path.abspath(path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        df.to_csv(abs_path, index=False, encoding="utf-8-sig")

    def _build_factor_snapshot(self, date, market_oar, df, universe_type, name_col):
        if df is None or df.empty:
            return pd.DataFrame()
        rows = []
        for _, row in df.iterrows():
            data = row.get("_data", {}) or {}
            signal_text = str(row.get("信号", ""))
            scenario = str(row.get("_scenario", "") or "")
            signal_category = self._scenario_category(scenario)
            validation = self._validate_signal(signal_category, self._to_float(data.get("body_pct"))) if signal_category != "none" else {
                "rule": "",
                "success": "",
                "result": "",
            }
            rows.append({
                "date": date,
                "universe_type": universe_type,
                "code": row.get("代码", row.get("_code", "")),
                "name": row.get(name_col, row.get("_name", "")),
                "group": row.get("分组", ""),
                "theme_cluster": row.get("分组", row.get("板块", row.get(name_col, ""))),
                "rank": row.get("排名", row.get("_amt_rank", "")),
                "is_topk": bool(universe_type == "industry" or self._to_float(row.get("排名", row.get("_amt_rank", 999))) <= 20),
                "source": "auction_report",
                "prev2_pct": self._to_float(data.get("pct_t2")),
                "prev1_pct": self._to_float(data.get("prev_pct")),
                "prev_body_pct": self._to_float(data.get("prev_body_pct")),
                "prev_vol_ratio": self._to_float(data.get("prev_vol_ratio"), 1.0),
                "prev_close": self._to_float(data.get("prev_close")),
                "open": self._to_float(data.get("open")),
                "high": self._to_float(data.get("high")),
                "low": self._to_float(data.get("low")),
                "close": self._to_float(data.get("close")),
                "auction_pct": self._to_float(data.get("auction_pct")),
                "close_pct": self._to_float(data.get("close_pct")),
                "body_pct": self._to_float(data.get("body_pct")),
                "amount": self._to_float(data.get("amount")),
                "auction_amount": self._to_float(data.get("auction_amount_raw", self._to_float(data.get("auction_amt")) * 1e8)),
                "volume": self._to_float(data.get("volume")),
                "turnover_rate": self._to_float(data.get("turnover_rate")),
                "vol_ratio": self._to_float(data.get("vol_ratio"), 1.0),
                "oar": self._to_float(market_oar),
                "amount_rank": data.get("amt_rank", row.get("排名", row.get("_amt_rank", ""))),
                "pos_5d": self._to_float(data.get("pos_5d"), 50),
                "trend_state": data.get("trend_state", ""),
                "stock_count": data.get("stock_count", ""),
                "cp": data.get("cp"),
                "sa": data.get("sa"),
                "cp_triggered": signal_category == "trap",
                "sa_triggered": signal_category == "reversal",
                "trend_triggered": signal_category == "trend",
                "signal_category": signal_category,
                "signal_family": self._signal_family(signal_category) if signal_category != "none" else "",
                "signal_label": signal_text,
                "scenario": scenario,
                "validation_rule": validation["rule"],
                "validation_success": validation["success"],
                "validation_result": validation["result"],
                "strong_validation_success": self._strong_validation_success(signal_category, self._to_float(data.get("body_pct"))) if signal_category != "none" else "",
                "candidate_generated_at": "auction" if signal_category != "none" else "",
                "outcome_label_source": "post_close_body_pct" if signal_category != "none" else "",
            })
        return pd.DataFrame(rows)

    @staticmethod
    def _infer_signal_category(signal_text):
        if "CP风险" in signal_text or "诱多" in signal_text:
            return "trap"
        if "反核" in signal_text:
            return "reversal"
        if "趋势" in signal_text:
            return "trend"
        return "none"

    @staticmethod
    def _scenario_category(scenario):
        if scenario.startswith("TRAP"):
            return "trap"
        if scenario.startswith("REVERSAL"):
            return "reversal"
        if scenario.startswith("TREND"):
            return "trend"
        return "none"

    @staticmethod
    def _validate_signal(category, body_pct):
        if category == "trap":
            return {
                "rule": "body_pct < 0",
                "success": bool(body_pct < 0),
                "result": "success" if body_pct < 0 else "failed",
            }
        if category == "reversal":
            return {
                "rule": "body_pct > 0",
                "success": bool(body_pct > 0),
                "result": "success" if body_pct > 0 else "failed",
            }
        if category == "trend":
            return {
                "rule": "body_pct > 0",
                "success": bool(body_pct > 0),
                "result": "success" if body_pct > 0 else "failed",
            }
        return {
            "rule": "unclassified",
            "success": False,
            "result": "unknown",
        }

    @staticmethod
    def _strong_validation_success(category, body_pct):
        if category == "trap":
            return bool(body_pct < -2.0)
        if category in {"reversal", "trend"}:
            return bool(body_pct > 2.0)
        return False

    def _build_validation_summary(self, detail_df):
        if detail_df.empty:
            return pd.DataFrame()
        df = detail_df.copy()
        if "signal_family" not in df.columns:
            df["signal_family"] = df["signal_category"].map(self._signal_family)
        if "signal_order" not in df.columns:
            df["signal_order"] = df["signal_category"].map(self._signal_order)
        for col in ["body_pct", "auction_pct", "close_pct", "cp", "sa"]:
            if col not in df.columns:
                df[col] = 0
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["directed_body_pct"] = df["body_pct"] * df["signal_category"].map(
            {"trap": -1.0, "reversal": 1.0, "trend": 1.0}
        ).fillna(0.0)
        df["validation_success_bool"] = df["validation_success"].map(self._as_bool)
        summary = (
            df
            .groupby(["date", "signal_order", "signal_family", "signal_category", "target_type"], dropna=False)
            .agg(
                trigger_count=("validation_success_bool", "size"),
                success_count=("validation_success_bool", "sum"),
                avg_body_pct=("body_pct", "mean"),
                median_body_pct=("body_pct", "median"),
                avg_directed_body_pct=("directed_body_pct", "mean"),
                median_directed_body_pct=("directed_body_pct", "median"),
                avg_auction_pct=("auction_pct", "mean"),
                avg_close_pct=("close_pct", "mean"),
                avg_cp=("cp", "mean"),
                max_cp=("cp", "max"),
                avg_sa=("sa", "mean"),
                max_sa=("sa", "max"),
            )
            .reset_index()
        )
        summary["failure_count"] = summary["trigger_count"] - summary["success_count"]
        summary["success_rate"] = (summary["success_count"] / summary["trigger_count"] * 100).round(2)
        for col in ["avg_body_pct", "median_body_pct", "avg_directed_body_pct", "median_directed_body_pct", "avg_auction_pct", "avg_close_pct", "avg_cp", "max_cp", "avg_sa", "max_sa"]:
            summary[col] = summary[col].round(4)
        ordered_cols = [
            "date", "signal_family", "signal_category", "target_type",
            "trigger_count", "success_count", "failure_count", "success_rate",
            "avg_body_pct", "median_body_pct", "avg_directed_body_pct", "median_directed_body_pct",
            "avg_auction_pct", "avg_close_pct",
            "avg_cp", "max_cp", "avg_sa", "max_sa", "signal_order",
        ]
        return summary[ordered_cols].sort_values(["date", "signal_order", "target_type"])

    def _build_validation_metrics(self, detail_df, dates=None):
        if detail_df.empty:
            dates = dates or []
            df = pd.DataFrame()
        else:
            df = detail_df.copy()
            for col in ["body_pct", "auction_pct", "close_pct", "cp", "sa"]:
                if col not in df.columns:
                    df[col] = 0
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df["validation_success_bool"] = df["validation_success"].map(self._as_bool)
            df["directed_body_pct"] = df["body_pct"] * df["signal_category"].map(
                {"trap": -1.0, "reversal": 1.0, "trend": 1.0}
            ).fillna(0.0)
            if dates is None:
                dates = sorted(df["date"].astype(str).unique().tolist())

        rows = []
        for date in dates:
            day_df = df[df["date"].astype(str) == str(date)] if not df.empty else pd.DataFrame()
            for category, family, rule in self.VALIDATION_CATEGORIES:
                subset = day_df[day_df["signal_category"] == category] if not day_df.empty else pd.DataFrame()
                trigger_count = int(len(subset))
                success_count = int(subset["validation_success_bool"].sum()) if trigger_count else 0
                failure_count = trigger_count - success_count
                success_rate = round(success_count / trigger_count * 100, 2) if trigger_count else 0.0
                rows.append({
                    "date": str(date),
                    "signal_family": family,
                    "signal_category": category,
                    "validation_rule": rule,
                    "trigger_count": trigger_count,
                    "success_count": success_count,
                    "failure_count": failure_count,
                    "success_rate": success_rate,
                    "avg_body_pct": round(subset["body_pct"].mean(), 4) if trigger_count else "",
                    "median_body_pct": round(subset["body_pct"].median(), 4) if trigger_count else "",
                    "avg_directed_body_pct": round(subset["directed_body_pct"].mean(), 4) if trigger_count else "",
                    "median_directed_body_pct": round(subset["directed_body_pct"].median(), 4) if trigger_count else "",
                    "avg_auction_pct": round(subset["auction_pct"].mean(), 4) if trigger_count else "",
                    "avg_close_pct": round(subset["close_pct"].mean(), 4) if trigger_count else "",
                    "avg_cp": round(subset["cp"].mean(), 4) if trigger_count else "",
                    "max_cp": round(subset["cp"].max(), 4) if trigger_count else "",
                    "avg_sa": round(subset["sa"].mean(), 4) if trigger_count else "",
                    "max_sa": round(subset["sa"].max(), 4) if trigger_count else "",
                    "signal_order": self._signal_order(category),
                })
        return pd.DataFrame(rows).sort_values(["date", "signal_order"]) if rows else pd.DataFrame()

    @classmethod
    def _signal_family(cls, category):
        mapping = {key: family for key, family, _rule in cls.VALIDATION_CATEGORIES}
        return mapping.get(category, category)

    @classmethod
    def _signal_order(cls, category):
        mapping = {key: idx for idx, (key, _family, _rule) in enumerate(cls.VALIDATION_CATEGORIES)}
        return mapping.get(category, 99)

    @staticmethod
    def _as_bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return str(value).strip().lower() in {"true", "1", "yes", "y", "success"}

    @staticmethod
    def _to_float(value, default=0.0):
        try:
            if value is None or pd.isna(value):
                return default
            return float(value)
        except Exception:
            return default
    
    def _print_indicator_notes(self):
        """打印指标说明"""
        print(f"\n{'═'*100}")
        print(f"【💡 指标说明】")
        print(f"{'─'*100}")
        print(f"  CP (Crowding Pump) 拥挤兑现风险指数")
        print(f"     公式: (排名权重 × 5日位置 / OAR) × (1 + 昨实体涨幅 × 昨量比)")
        print(f"     触发: 竞价涨幅 > 高开阈值 (主板0.3% / 双创0.5%) 或 昨日大涨后平开/弱低开")
        print(f"     阈值: CP ≥ 60 为高风险")
        print(f"  {'─ '*48}")
        print(f"  SA (Support Absorption) 承接反核指数")
        print(f"     公式: 竞价额亿 × 排名权重 × (1 + |竞价跌幅|/0.5) × 恐慌系数")
        print(f"     触发: 竞价涨幅 < -0.3% (真正低开)")
        print(f"     阈值: SA ≥ 50 为高机会")
        print(f"  {'─ '*48}")
        print(f"  排名权重: Top3=1.0 │ Top5=0.7 │ Top10=0.3 │ 其他=0.1")
        print(f"  5日位置:  (收盘价-5日最低) / (5日最高-5日最低) × 100%")
        print(f"  昨日指标: 使用实体涨跌幅（反映真实获利/亏损盘）")
        print(f"{'═'*100}")
    
    # ═══════════════════════════════════════════════════════════
    # 实时模式报告输出
    # ═══════════════════════════════════════════════════════════
    
    def _print_realtime_report(self, result):
        """打印实时决策报告（9:25盘前）"""
        target_date = result['date']
        market_oar = result.get('market_oar', 1.0)
        
        # 报告标题
        print(f"\n{'═'*90}")
        print(f"{' '*25}⏰ 竞价实时决策报告 [{target_date}] 9:25")
        print(f"{'═'*90}")
        
        # 市场环境
        self._print_realtime_environment(result)
        
        # ETF竞价监控（简化版）
        self._print_realtime_etf(result)
        
        # 行业竞价排行（简化版）
        self._print_realtime_industry(result)
        
        # 信号汇总（核心）
        self._print_realtime_signals(result)
        
        # 操作建议
        self._print_realtime_actions(result)
    
    def _print_realtime_environment(self, result):
        """实时模式 - 市场环境"""
        market_oar = result.get('market_oar', 1.0)
        indices_df = result.get('indices_monitor', pd.DataFrame())
        
        # 预估OAR（实际9:25时用竞价金额比估算）
        if market_oar < 0.8:
            oar_desc = f"预估缩量"
            env_emoji = "🟡"
        elif market_oar > 1.2:
            oar_desc = f"预估放量"
            env_emoji = "🟢"
        else:
            oar_desc = f"预估平量"
            env_emoji = "⚪"
        
        print(f"\n┌{'─'*88}┐")
        print(f"│ 【🌍 市场环境预判】{' '*67}│")
        print(f"│{' '*88}│")
        print(f"│   {env_emoji} 量能预判: {oar_desc:<20}                                                │")
        print(f"│   💡 注意: OAR为预估值，实际量能需观察9:30-9:45成交情况                               │")
        print(f"└{'─'*88}┘")
    
    def _print_realtime_etf(self, result):
        """实时模式 - ETF竞价监控（无收盘/实体列）"""
        etf_df = result.get('etf_auction', pd.DataFrame())
        
        if etf_df.empty:
            return
        
        print(f"\n【🔍 ETF竞价监控】")
        print(f"┌{'─'*10}┬{'─'*8}┬{'─'*8}┬{'─'*8}┬{'─'*7}┬{'─'*6}┬{'─'*6}┬{'─'*8}┐")
        print(f"│{'ETF':^10}│{'T-2':^8}│{'T-1':^8}│{'竞价':^8}│{'5日位':^7}│{'CP':^6}│{'SA':^6}│{'信号':^6}│")
        print(f"├{'─'*10}┼{'─'*8}┼{'─'*8}┼{'─'*8}┼{'─'*7}┼{'─'*6}┼{'─'*6}┼{'─'*8}┤")
        
        for _, row in etf_df.iterrows():
            name = str(row.get('ETF', '-'))[:5]
            t2 = str(row.get('T-2', '-'))
            t1 = str(row.get('T-1', '-'))
            auction = str(row.get('竞价', '-'))
            pos = str(row.get('5日位', '-'))
            cp = str(row.get('CP', '--'))[:5]
            sa = str(row.get('SA', '--'))[:5]
            signal = str(row.get('信号', '-'))[:6]
            
            print(f"│{name:^10}│{t2:^8}│{t1:^8}│{auction:^8}│{pos:^7}│{cp:^6}│{sa:^6}│{signal:^6}│")
        
        print(f"└{'─'*10}┴{'─'*8}┴{'─'*8}┴{'─'*8}┴{'─'*7}┴{'─'*6}┴{'─'*6}┴{'─'*8}┘")
    
    def _print_realtime_industry(self, result):
        """实时模式 - 行业竞价排行（无收盘/实体列）"""
        industry_df = result.get('industry_report', pd.DataFrame())
        
        if industry_df.empty:
            return
        
        print(f"\n【📊 行业竞价排行 Top 15】")
        print(f"┌{'─'*4}┬{'─'*10}┬{'─'*9}┬{'─'*8}┬{'─'*8}┬{'─'*8}┬{'─'*6}┬{'─'*6}┬{'─'*8}┐")
        print(f"│{'排名':^4}│{'板块':^8}│{'竞价额':^9}│{'T-2':^8}│{'T-1':^8}│{'竞价':^8}│{'CP':^6}│{'SA':^6}│{'信号':^6}│")
        print(f"├{'─'*4}┼{'─'*10}┼{'─'*9}┼{'─'*8}┼{'─'*8}┼{'─'*8}┼{'─'*6}┼{'─'*6}┼{'─'*8}┤")
        
        for _, row in industry_df.iterrows():
            rank = str(row.get('排名', '-'))
            name = str(row.get('板块', '-'))[:5]
            amt = str(row.get('竞价额', '-'))
            t2 = str(row.get('T-2', '-'))
            t1 = str(row.get('T-1', '-'))
            auction = str(row.get('竞价', '-'))
            cp = str(row.get('CP', '--'))[:5]
            sa = str(row.get('SA', '--'))[:5]
            signal = str(row.get('信号', '-'))[:6]
            
            print(f"│{rank:^4}│{name:^8}│{amt:^9}│{t2:^8}│{t1:^8}│{auction:^8}│{cp:^6}│{sa:^6}│{signal:^6}│")
        
        print(f"└{'─'*4}┴{'─'*10}┴{'─'*9}┴{'─'*8}┴{'─'*8}┴{'─'*8}┴{'─'*6}┴{'─'*6}┴{'─'*8}┘")
    
    def _print_realtime_signals(self, result):
        """实时模式 - 信号汇总"""
        signals = result.get('signals', {})
        
        if not signals:
            return
        
        trap_signals = signals.get('trap', [])
        reversal_signals = signals.get('reversal', [])
        
        if not trap_signals and not reversal_signals:
            print(f"\n{'─'*90}")
            print(f"  ⚪ 今日无明显信号，建议观望")
            return
        
        print(f"\n{'═'*90}")
        print(f"{' '*30}【🚨 实时信号预判】")
        print(f"{'═'*90}")
        self._print_intraday_confirmation_summary(result)
        
        # 诱多警报
        if trap_signals:
            print(f"\n▶ 🔴 CP风险 (CP≥60) - 建议回避")
            for sig in trap_signals:
                self._print_realtime_signal_card(sig, 'trap')
        
        # 反核机会
        if reversal_signals:
            print(f"\n▶ 🟢 反核机会 (SA≥50) - 关注介入")
            for sig in reversal_signals:
                self._print_realtime_signal_card(sig, 'reversal')
    
    def _print_realtime_signal_card(self, sig, signal_type):
        """实时模式 - 信号卡片（预判模式）"""
        name = sig.get('name', '-')
        data = sig.get('data', {})
        commentary = sig.get('commentary') or {}
        
        cp = sig.get('cp')
        sa = sig.get('sa')
        amt_rank = sig.get('amt_rank')
        
        # 指标值
        if signal_type == 'trap':
            indicator = f"CP={cp:.1f}" if cp else "CP=--"
        else:
            indicator = f"SA={sa:.1f}" if sa else "SA=--"
        
        # 关键数据
        auction_pct = data.get('auction_pct', 0)
        prev_body_pct = data.get('prev_body_pct', 0)  # 使用实体涨跌幅
        pos_5d = data.get('pos_5d', 50)
        
        # 排名信息
        rank_str = f"Top{amt_rank}" if amt_rank and amt_rank <= 15 else ""
        
        print(f"┌{'─'*88}┐")
        print(f"│ 【{name}】 {indicator:<72}│")
        print(f"│  {'┄'*84}│")
        
        # 概要行 - 使用昨日实体涨跌幅
        summary_parts = []
        if rank_str:
            summary_parts.append(rank_str)
        if prev_body_pct != 0:
            # 显示昨日实体涨跌幅，区分阳线/阴线
            if prev_body_pct > 0:
                summary_parts.append(f"昨阳+{prev_body_pct:.2f}%")
            else:
                summary_parts.append(f"昨阴{prev_body_pct:.2f}%")
        summary_parts.append(f"今{'高开' if auction_pct > 0.2 else '低开'}{auction_pct:+.2f}%")
        if pos_5d != 50:
            summary_parts.append(f"5日位{pos_5d:.0f}%")
        
        summary = " │ ".join(summary_parts)
        print(f"│  {summary:<84}│")
        
        # 预判研判
        if signal_type == 'trap':
            print(f"│{' '*88}│")
            print(f"│  ⚠️ 风险预判: {commentary.get('risk', 'CP值偏高，存在拥挤兑现风险')[:70]:<70}│")
            print(f"│  📋 操作建议: 回避追高，等待回落确认                                               │")
        else:
            print(f"│{' '*88}│")
            print(f"│  ✅ 机会预判: {commentary.get('risk', 'SA值较高，有资金承接')[:70]:<70}│")
            print(f"│  📋 操作建议: 9:30-9:35站稳分时均线可介入，止损设开盘价下方1%                       │")
        
        print(f"└{'─'*88}┘")
    
    def _print_realtime_actions(self, result):
        """实时模式 - 操作建议汇总"""
        signals = result.get('signals', {})
        trap_signals = signals.get('trap', [])
        reversal_signals = signals.get('reversal', [])
        
        print(f"\n{'═'*90}")
        print(f"【📋 9:30操作建议】")
        print(f"{'─'*90}")
        
        if trap_signals:
            trap_names = [s['name'] for s in trap_signals[:3]]
            print(f"  🔴 回避: {', '.join(trap_names)}")
            print(f"     → 不追高，已持仓者逢高减仓")
        
        if reversal_signals:
            rev_names = [s['name'] for s in reversal_signals[:3]]
            print(f"  🟢 关注: {', '.join(rev_names)}")
            print(f"     → 9:30-9:35观察，站稳均线可轻仓介入")
        
        if not trap_signals and not reversal_signals:
            print(f"  ⚪ 无明显信号，建议观望等待")
        
        print(f"{'─'*90}")
        print(f"  ⏰ 关键时间: 9:30开盘 │ 9:35首次确认 │ 9:45二次确认")
        print(f"  💡 止损原则: 破开盘价1%止损 │ 破分时均线减仓")
        print(f"{'═'*90}")

    def _print_intraday_confirmation_summary(self, result):
        meta = result.get("intraday_confirmation", {}) or {}
        if not meta:
            return
        signal_meta = meta.get("signal_enrichment", {}) or {}
        available = bool(meta.get("available"))
        feature_timestamp = meta.get("feature_timestamp")
        if not available and not signal_meta:
            return

        path = meta.get("path", "") or signal_meta.get("path", "")
        confirm_df = self._load_confirmation_df(path) if path else pd.DataFrame()
        coverage = len(confirm_df) if not confirm_df.empty else 0
        confirmed_strength = 0
        if not confirm_df.empty and "execution_bias" in confirm_df.columns:
            confirmed_strength = int(confirm_df["execution_bias"].astype(str).eq("confirmed_strength").sum())

        enriched_count = int(signal_meta.get("enriched_count", 0) or 0)
        rejected_count = int(meta.get("rejected_count", 0) or 0)
        selected_after = int(meta.get("selected_after_confirmation", 0) or 0)
        ts_label = feature_timestamp or signal_meta.get("feature_timestamp") or "-"
        print(
            "  [09:35确认] "
            f"available={available} | ts={ts_label} | "
            f"覆盖={coverage} | confirmed_strength={confirmed_strength} | "
            f"趋势预加权={enriched_count} | reject={rejected_count} | 留存={selected_after}"
        )

    @staticmethod
    def _load_confirmation_df(path):
        try:
            return pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str})
        except Exception:
            return pd.DataFrame()


def main(target_date=None, sync_first=False, realtime=False):
    """独立运行入口"""
    with AuctionRunner() as runner:
        return runner.run(target_date=target_date, sync_first=sync_first, realtime=realtime)


if __name__ == "__main__":
    import sys
    target_date = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    sync_first = '--sync' in sys.argv
    realtime = '--realtime' in sys.argv or '-r' in sys.argv
    main(target_date, sync_first, realtime)
