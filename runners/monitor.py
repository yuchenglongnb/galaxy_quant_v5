# -*- coding: utf-8 -*-
"""
盘中监测运行器 - 整合竞价分析 + 持续监测

功能：
1. 9:25 自动同步个股竞价数据 + 执行竞价分析（CP/SA信号）
2. 9:25-15:00 每分钟采集指数、ETF和股票池实时数据
3. 支持断点续传（程序重启后从上次中断处继续）
4. 支持实时显示市场概览

使用:
    python main.py monitor              # 启动盘中监测（含竞价分析）
    python main.py monitor --summary    # 监测并显示市场概览
    python main.py monitor --no-auction # 跳过竞价分析，仅监测
    python main.py monitor --test       # 测试模式（采集一次后退出）

注意：
    - 需要在交易时间内运行 (9:25-15:00)
    - 首次运行前请确保已同步历史数据: python main.py sync 5
    - 建议使用终端多路复用器（tmux/screen）保持运行
"""

import os
import sys
import time
import signal
from datetime import datetime, timedelta
from typing import Optional

from runners.base import BaseRunner
from core.intraday_monitor import IntradayMonitor, MarketState, MarketPhase
from config.settings import DBConfig, MonitorConfig


class MonitorRunner(BaseRunner):
    """
    盘中监测运行器（整合版）
    
    工作流程：
    1. 启动时检查市场状态
    2. 如果在9:25-9:30且未执行过竞价分析 → 执行竞价采集+分析
    3. 进入主循环：每分钟采集指数、ETF和股票池快照
    4. 收盘后自动退出
    """
    
    def __init__(self):
        super().__init__()
        self._running = True
        self._monitor: Optional[IntradayMonitor] = None
        self._auction_done = False  # 标记竞价分析是否已完成
        self._dm = None  # DataManager实例
        
        # 注册信号处理（优雅退出）
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """信号处理器 - 优雅退出"""
        print("\n\n⚠️ 收到退出信号，正在保存数据...")
        self._running = False
    
    def run(self, show_summary: bool = False, test_mode: bool = False, 
            skip_auction: bool = False, interval: int = 60,
            use_subscribe: bool = True, daemon: bool = False) -> bool:
        """
        启动盘中监测（整合竞价分析）
        
        参数:
            show_summary: 是否显示市场概览
            test_mode: 测试模式（采集一次后退出）
            skip_auction: 跳过竞价分析（仅监测）
            interval: 采集间隔（秒），默认60秒
            use_subscribe: 竞价采集是否使用订阅模式
            daemon: 守护模式（后台等待，到点自动运行）
            
        返回:
            bool: 是否正常完成
        """
        print("="*60)
        print("  GalaxyQuant - 盘中实时监测（整合版）")
        print("="*60)
        
        # 初始化DataManager
        from core.data_manager import DataManager
        self._dm = DataManager()
        
        # 初始化监测器
        self._monitor = IntradayMonitor(DBConfig.STORE_PATH)
        
        # 检查当前市场状态
        phase = MarketState.get_current_phase()
        phase_name = MarketState.get_phase_name(phase)
        print(f"\n当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"市场状态: {phase_name}")
        
        # ============ 守护模式：支持任意时间启动 ============
        if daemon:
            print(f"\n🌙 守护模式已启用，程序将持续运行")
            return self._daemon_loop(show_summary, skip_auction, interval, use_subscribe)
        
        # ============ 普通模式：检查交易时间 ============
        if phase == MarketPhase.CLOSED:
            print("\n❌ 已收盘，无法启动监测")
            print("   请在交易时间 (9:25-15:00) 运行此命令")
            print("   或使用 --daemon 模式后台等待下一个交易日")
            return False
        
        if phase == MarketPhase.PRE_OPEN:
            print("\n⏳ 尚未到采集时间，等待9:25...")
            self._wait_until_time(9, 25)
        
        if phase == MarketPhase.CALL_AUCTION:
            print("\n⏳ 集合竞价中，等待9:25竞价结束...")
            self._wait_until_time(9, 25)
        
        # 检查历史数据
        if not self._check_history_data():
            return False
        
        # 测试模式
        if test_mode:
            return self._run_test_mode(show_summary, skip_auction, use_subscribe)
        
        # 主循环
        return self._main_loop(show_summary, skip_auction, interval, use_subscribe)
    
    def _daemon_loop(self, show_summary: bool, skip_auction: bool, 
                     interval: int, use_subscribe: bool) -> bool:
        """
        守护模式主循环
        
        逻辑：
        1. 如果在交易时间 → 直接进入监测
        2. 如果已收盘 → 等待到下一个交易日9:25
        3. 如果盘前 → 等待到9:25
        4. 每个交易日结束后，重置状态，等待下一个交易日
        """
        print("   程序将在每个交易日9:25自动启动监测")
        print("   按 Ctrl+C 可随时退出\n")
        
        while self._running:
            phase = MarketState.get_current_phase()
            now = datetime.now()
            
            # ============ 情况1: 在交易时间内 ============
            if MarketState.should_collect():
                print(f"\n{'='*60}")
                print(f"  📅 {now.strftime('%Y-%m-%d')} 交易日监测")
                print(f"{'='*60}")
                
                # 检查历史数据
                if not self._check_history_data():
                    print("  ⚠️ 历史数据不完整，等待下一个交易日...")
                    self._wait_until_next_trading_day()
                    continue
                
                # 重置竞价分析状态
                self._auction_done = False
                
                # 执行当日监测
                self._main_loop(show_summary, skip_auction, interval, use_subscribe)
                
                # 当日监测结束，等待下一个交易日
                print(f"\n💤 今日监测结束，等待下一个交易日...")
                self._wait_until_next_trading_day()
                
            # ============ 情况2: 盘前等待 ============
            elif phase in [MarketPhase.PRE_OPEN, MarketPhase.CALL_AUCTION]:
                print(f"\r  ⏳ 等待开盘... 当前: {now.strftime('%H:%M:%S')}", end="", flush=True)
                self._wait_until_time(9, 25)
                
            # ============ 情况3: 已收盘，等待下一个交易日 ============
            else:
                self._wait_until_next_trading_day()
        
        print("\n\n👋 守护进程已退出")
        return True
    
    def _wait_until_next_trading_day(self):
        """
        等待到下一个交易日的9:25
        
        使用简单策略：等待到下一个工作日的9:25
        （实际交易日判断可能需要更复杂的逻辑）
        """
        now = datetime.now()
        
        # 计算下一个9:25的时间
        if now.hour >= 15:
            # 今天已收盘，等到明天
            next_day = now + timedelta(days=1)
        else:
            # 还没到今天的9:25
            next_day = now
        
        # 跳过周末
        while next_day.weekday() >= 5:  # 5=周六, 6=周日
            next_day += timedelta(days=1)
        
        target = next_day.replace(hour=9, minute=25, second=0, microsecond=0)
        
        # 如果目标时间已过，再加一天
        if target <= now:
            target += timedelta(days=1)
            while target.weekday() >= 5:
                target += timedelta(days=1)
            target = target.replace(hour=9, minute=25, second=0, microsecond=0)
        
        wait_seconds = (target - now).total_seconds()
        
        print(f"\n  📅 下次启动时间: {target.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  ⏰ 等待时间: {wait_seconds/3600:.1f} 小时")
        print(f"  💡 提示: 按 Ctrl+C 可随时退出\n")
        
        # 长时间等待，每分钟检查一次
        while wait_seconds > 0 and self._running:
            sleep_time = min(wait_seconds, 60)
            time.sleep(sleep_time)
            wait_seconds -= sleep_time
            
            # 每小时打印一次状态
            now = datetime.now()
            remaining = (target - now).total_seconds()
            if remaining > 0 and int(remaining) % 3600 < 60:
                print(f"  ⏳ {now.strftime('%H:%M')} - 距离开盘还有 {remaining/3600:.1f} 小时")
    
    def _check_history_data(self) -> bool:
        """检查历史数据是否完整"""
        valid_days = self._dm.get_valid_trading_days(lookback=5)
        if not valid_days:
            print("\n❌ 无有效交易日数据")
            return False
        
        # 检查T-1到T-4的数据
        today = valid_days[-1]
        history_days = [d for d in valid_days if d < today][-4:]
        
        missing = []
        for d in history_days:
            stocks_file = os.path.join(DBConfig.STORE_PATH, str(d), "stocks.csv")
            if not os.path.exists(stocks_file):
                missing.append(d)
        
        if missing:
            print(f"\n❌ 缺少历史数据: {missing}")
            print(f"   请先执行: python main.py sync 5")
            return False
        
        print(f"  ✓ 历史数据完整: {history_days}")
        return True
    
    def _run_test_mode(self, show_summary: bool, skip_auction: bool, 
                       use_subscribe: bool) -> bool:
        """测试模式 - 执行一次完整流程后退出"""
        print("\n🧪 测试模式：执行单次采集...")
        
        # 如果在竞价时段且未跳过竞价分析
        phase = MarketState.get_current_phase()
        if phase == MarketPhase.AUCTION_END and not skip_auction:
            print("\n--- 执行竞价分析 ---")
            self._run_auction_analysis(use_subscribe)
        
        # 采集指数+ETF
        result = self._monitor.collect_once()
        self._monitor.print_status(result)
        
        if show_summary:
            idx_df, etf_df, _ = self._monitor.fetch_current_snapshot()
            self._monitor.print_market_summary(idx_df, etf_df)
        
        print(f"\n✅ 测试完成")
        print(f"   指数数据: {result['idx_path']}")
        print(f"   ETF数据: {result['etf_path']}")
        return True
    
    def _main_loop(self, show_summary: bool, skip_auction: bool, 
                   interval: int, use_subscribe: bool) -> bool:
        """
        主采集循环
        
        逻辑：
        1. 9:25-9:30：执行竞价分析（一次性）
        2. 每分钟：采集指数+ETF快照
        3. 可选：定期显示市场概览
        4. 收盘后退出
        """
        print("\n" + "-"*60)
        print("  开始实时监测 (Ctrl+C 退出)")
        print("-"*60)
        print(f"  采集间隔: {interval}秒")
        print(
            f"  监测标的: {len(self._monitor.target_indices)}只指数 + "
            f"{len(self._monitor.target_etfs)}只ETF + "
            f"{len(self._monitor.target_stocks)}只股票池标的"
        )
        print(f"  竞价分析: {'跳过' if skip_auction else '启用'}")
        print()
        
        collect_count = 0
        last_summary_time = 0
        
        while self._running:
            phase = MarketState.get_current_phase()
            
            # 收盘退出
            if phase == MarketPhase.CLOSED:
                print("\n🔔 已收盘，监测结束")
                break
            
            # ============ 9:25-9:30 竞价分析（仅执行一次）============
            if phase == MarketPhase.AUCTION_END and not self._auction_done and not skip_auction:
                self._run_auction_analysis(use_subscribe)
                self._auction_done = True
            
            # ============ 计算实际间隔 ============
            if phase == MarketPhase.NOON_BREAK:
                actual_interval = interval * MonitorConfig.NOON_INTERVAL_MULT
            else:
                actual_interval = interval
            
            # ============ 等待到下一个采集点 ============
            self._wait_next_interval(actual_interval)
            
            if not self._running:
                break
            
            # ============ 执行采集 ============
            try:
                result = self._monitor.collect_once()
                collect_count += 1
                self._monitor.print_status(result)
                
                # ============ 定期显示市场概览 ============
                now = time.time()
                if show_summary and (now - last_summary_time >= MonitorConfig.SUMMARY_INTERVAL * 60):
                    idx_df, etf_df, _ = self._monitor.fetch_current_snapshot()
                    self._monitor.print_market_summary(idx_df, etf_df)
                    last_summary_time = now
                    
            except Exception as e:
                print(f"  ⚠️ 采集异常: {e}")
                time.sleep(5)
        
        # 统计
        print("\n" + "="*60)
        print(f"  监测结束，共采集 {collect_count} 次")
        if self._auction_done:
            print(f"  竞价分析: ✅ 已执行")
        print("="*60)
        
        return True
    
    def _run_auction_analysis(self, use_subscribe: bool = True):
        """
        执行竞价分析（同步个股数据 + CP/SA分析）
        
        这是盘中监测与竞价分析的整合点
        """
        print("\n" + "="*60)
        print("  📊 执行竞价分析（9:25数据）")
        print("="*60)
        
        try:
            # 1. 同步竞价数据（个股）
            print("\n>>> 同步个股竞价数据...")
            target_date = self._dm.sync_realtime(use_subscribe=use_subscribe)
            
            if target_date is None:
                print("  ⚠️ 竞价数据同步失败，跳过分析")
                return
            
            # 2. 执行竞价分析
            print("\n>>> 执行竞价分析...")
            from analyzers.auction import AuctionAnalyzer
            analyzer = AuctionAnalyzer(self._dm)
            result = analyzer.analyze(target_date, realtime=True)
            
            if result is None:
                print("  ⚠️ 竞价分析失败")
                return
            
            # 3. 打印分析结果
            self._print_auction_signals(result)
            
            print("\n" + "="*60)
            print("  ✅ 竞价分析完成，进入盘中监测...")
            print("="*60)
            
        except Exception as e:
            print(f"  ⚠️ 竞价分析出错: {e}")
            import traceback
            traceback.print_exc()
    
    def _print_auction_signals(self, result: dict):
        """打印竞价分析信号摘要（简化版）"""
        signals = result.get('signals', {})
        
        # 陷阱信号
        trap_signals = signals.get('trap', [])
        if trap_signals:
            print("\n  🚨 【诱多陷阱预警】")
            for sig in trap_signals[:5]:
                name = sig.get('name', sig.get('industry', ''))
                cp = sig.get('cp', 0)
                # 修复：auction_pct存储在data字典内部
                pct = sig.get('data', {}).get('auction_pct', 0)
                print(f"     ⚠️ {name}: CP={cp:.0f} 竞价涨幅={pct:+.1f}%")
        
        # 反转信号
        reversal_signals = signals.get('reversal', [])
        if reversal_signals:
            print("\n  💎 【低吸反转机会】")
            for sig in reversal_signals[:5]:
                name = sig.get('name', sig.get('industry', ''))
                sa = sig.get('sa', 0)
                # 修复：auction_pct存储在data字典内部
                pct = sig.get('data', {}).get('auction_pct', 0)
                print(f"     🔥 {name}: SA={sa:.0f} 竞价涨幅={pct:+.1f}%")
        
        # 趋势信号
        trend_signals = signals.get('trend', [])
        if trend_signals:
            print("\n  📈 【强势趋势延续】")
            for sig in trend_signals[:3]:
                name = sig.get('name', sig.get('industry', ''))
                # 修复：auction_pct存储在data字典内部
                pct = sig.get('data', {}).get('auction_pct', 0)
                print(f"     🚀 {name}: 竞价涨幅={pct:+.1f}%")
        
        if not trap_signals and not reversal_signals and not trend_signals:
            print("\n  ℹ️ 今日无明显信号")
    
    def _wait_until_time(self, hour: int, minute: int):
        """等待到指定时间"""
        while self._running:
            now = datetime.now()
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            if now >= target:
                return
            
            diff = (target - now).total_seconds()
            if diff > 60:
                print(f"\r  等待中... 距离 {hour:02d}:{minute:02d} 还有 {int(diff//60)} 分钟", end="", flush=True)
                time.sleep(30)
            else:
                print(f"\r  等待中... 距离 {hour:02d}:{minute:02d} 还有 {int(diff)} 秒    ", end="", flush=True)
                time.sleep(1)
        print()
    
    def _wait_next_interval(self, interval: int):
        """等待到下一个采集间隔（对齐到整分钟）"""
        now = datetime.now()
        
        # 计算下一个整分钟
        next_minute = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        
        # 如果间隔大于60秒，对齐到间隔整数倍
        if interval > 60:
            minutes_per_interval = interval // 60
            current_minute = next_minute.minute
            target_minute = ((current_minute // minutes_per_interval) + 1) * minutes_per_interval
            if target_minute >= 60:
                next_minute = next_minute.replace(hour=next_minute.hour + 1, minute=target_minute % 60)
            else:
                next_minute = next_minute.replace(minute=target_minute)
        
        wait_seconds = (next_minute - now).total_seconds()
        
        if wait_seconds > 0:
            while wait_seconds > 0 and self._running:
                sleep_time = min(wait_seconds, 5)
                time.sleep(sleep_time)
                wait_seconds -= sleep_time


class QuickMonitor:
    """快速监测工具 - 无需登录，用于查看当前市场状态"""
    
    @staticmethod
    def show_status():
        """显示当前市场状态"""
        phase = MarketState.get_current_phase()
        phase_name = MarketState.get_phase_name(phase)
        
        print(f"\n当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"市场状态: {phase_name}")
        
        if MarketState.is_trading_time():
            print("状态: 🟢 可交易")
        elif phase == MarketPhase.NOON_BREAK:
            print("状态: 🟡 午休中")
        elif phase in [MarketPhase.PRE_OPEN, MarketPhase.CALL_AUCTION]:
            print("状态: 🟡 等待开盘")
        else:
            print("状态: 🔴 已收盘")
    
    @staticmethod
    def show_schedule():
        """显示今日采集计划"""
        print("\n📅 今日工作流程:")
        print("-" * 50)
        schedule = [
            ("09:25", "🔔 竞价结束", "同步个股竞价 + 执行CP/SA分析"),
            ("09:26-09:30", "📊 竞价时段", "每分钟采集指数+ETF"),
            ("09:30-11:30", "📈 上午交易", "每分钟采集指数+ETF"),
            ("11:30-13:00", "😴 午间休市", "每5分钟采集（降频）"),
            ("13:00-14:57", "📈 下午交易", "每分钟采集指数+ETF"),
            ("14:57-15:00", "🔔 收盘竞价", "每分钟采集指数+ETF"),
            ("15:00", "🏁 收盘", "监测结束"),
        ]
        for time_str, phase, action in schedule:
            print(f"  {time_str:<14} {phase:<10} {action}")
