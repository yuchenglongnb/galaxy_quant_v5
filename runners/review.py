# -*- coding: utf-8 -*-
"""
盘后复盘运行器 - 独立的盘后复盘入口
"""

from runners.base import BaseRunner
from core.data_manager import DataManager
from analyzers.strategy import StrategyAnalyzer


class ReviewRunner(BaseRunner):
    """盘后复盘运行器"""
    
    def run(self, sync_first=True, lookback=5, force_refresh=False, **kwargs):
        """
        执行盘后复盘
        
        参数:
            sync_first: 是否先同步数据
            lookback: 回看天数
            force_refresh: 是否强制刷新交易日缓存
        """
        print(f"\n{'='*60}")
        print(f"  盘后全景复盘")
        print(f"{'='*60}")
        
        dm = DataManager()
        
        # 同步数据
        if sync_first:
            valid_days = dm.sync_recent_days(lookback=lookback)
        else:
            local_days = dm.get_local_daily_days()
            if len(local_days) >= lookback:
                valid_days = local_days
                print(f"  ✓ 使用本地完整日线缓存作为复盘日期集合: {valid_days[-lookback:]}")
            else:
                valid_days = dm.get_valid_trading_days(lookback=lookback, force_refresh=force_refresh)
        
        if len(valid_days) < 3:
            print("❌ 交易日数据不足（至少需要3天）")
            return None
        
        T = valid_days[-1]
        print(f"\n>>> 分析日期: {T}")
        
        # 执行分析
        analyzer = StrategyAnalyzer(dm)
        result = analyzer.analyze(T, valid_days=valid_days)
        
        if result is None:
            print("❌ 分析失败")
            return None
        
        # 打印报告
        self._print_report(result, T)
        
        return result
    
    def _print_report(self, result, T):
        """打印复盘报告"""
        print("\n" + "="*120)
        print(f"📊 A股全景策略报告 [{T}]")
        print("="*120)
        
        # Level 1: 指数环境
        indices = result['indices']
        print(f"\n【Level 1: 指数环境】 {indices['judgement']} (评分: {indices['total_score']})")
        print(f"  {'指数':<8} | {'T-2':<18} | {'T-1':<18} | {'T':<18} | {'趋势判断':<18} | 操作建议")
        print("  " + "-"*110)
        for item in indices['details']:
            print(f"  {item['name']:<8} | {item['T_2']:<18} | {item['T_1']:<18} | {item['T']:<18} | {item['trend']:<18} | {item['advice']}")
        
        # Level 2: ETF资金风向
        print("\n【Level 2: ETF 资金风向标】")
        print("  🔥 领涨 Top4:")
        for item in result['etf_top']:
            print(f"     • {item['name']:<12}: {item['pct']:<8} 量比{item['vol']:<5} ({item['status']})")
        print("  ❄️ 领跌 Top4:")
        for item in result['etf_bottom']:
            print(f"     • {item['name']:<12}: {item['pct']:<8} 量比{item['vol']:<5}")
        
        # Level 3: 行业主线
        print("\n【Level 3: 行业主线追踪】 (强度 = 成交额 * 涨幅)")
        print(f"  {'行业':<10} | {'T-2表现':<30} | {'T-1表现':<30} | {'T表现':<30} | 强度")
        print("  " + "-"*110)
        for row in result['mainlines']:
            print(f"  {row['industry']:<10} | {row['T_2']:<30} | {row['T_1']:<30} | {row['T']:<30} | {row['strength']}")
        
        # Level 4: 核心龙头矩阵
        print("\n【Level 4: 核心龙头矩阵】 (包含 🚀连板龙头 与 🐘成交中军)")
        print(f"  {'代码':<10} {'名称':<6} {'概念':<8} {'T-2表现':<20} {'T-1表现':<20} {'T表现':<20} {'成交额':<6} {'类型'}")
        print("  " + "-"*115)
        for row in result['core_matrix']:
            print(f"  {row['code']:<10} {row['name']:<6} {row['concept']:<8} {row['T_2']:<20} {row['T_1']:<20} {row['T']:<20} {row['amount']:<6} {row['type']}")
        
        print("="*120)


def main(sync_first=True, lookback=5):
    """独立运行入口"""
    with ReviewRunner() as runner:
        return runner.run(sync_first=sync_first, lookback=lookback)


if __name__ == "__main__":
    import sys
    sync_first = '--no-sync' not in sys.argv
    lookback = 5
    for arg in sys.argv[1:]:
        if arg.isdigit():
            lookback = int(arg)
    main(sync_first, lookback)
