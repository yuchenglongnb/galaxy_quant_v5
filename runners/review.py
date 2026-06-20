# -*- coding: utf-8 -*-
"""Post-close panoramic review runner."""

from analyzers.strategy import StrategyAnalyzer
from core.data_manager import DataManager
from runners.base import BaseRunner


class ReviewRunner(BaseRunner):
    """Independent entry for post-close panoramic review."""

    def run(self, sync_first=True, lookback=5, force_refresh=False, **kwargs):
        print(f"\n{'=' * 60}")
        print("  盘后全景复盘")
        print(f"{'=' * 60}")

        dm = DataManager()

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

        target_date = valid_days[-1]
        print(f"\n>>> 分析日期: {target_date}")

        analyzer = StrategyAnalyzer(dm)
        result = analyzer.analyze(target_date, valid_days=valid_days)
        if result is None:
            print("❌ 分析失败")
            return None

        self._print_report(result, target_date)
        return result

    def _print_report(self, result, target_date):
        print("\n" + "=" * 120)
        print(f"📊 A股全景策略报告 [{target_date}]")
        print("=" * 120)

        indices = result["indices"]
        broad_env = indices.get("broad_env", {})
        structural_env = result.get("structural_env", {})

        print(f"\n【Level 1: 指数环境】 {indices['judgement']} (评分: {indices['total_score']})")
        if broad_env:
            print(f"  广谱环境: {broad_env.get('judgement', indices['judgement'])}")
            print(f"  广谱解读: {broad_env.get('advice', '')}")
        if structural_env:
            print(f"  结构环境: {structural_env.get('judgement', '-') } (评分: {structural_env.get('score', '-')})")
            print(f"  结构解读: {structural_env.get('advice', '')}")
            leaders = structural_env.get("leading_industries", [])
            if leaders:
                print(f"  主线簇: {', '.join(leaders)}")

        print(f"  {'指数':<8} | {'T-2':<18} | {'T-1':<18} | {'T':<18} | {'趋势判断':<18} | 操作建议")
        print("  " + "-" * 110)
        for item in indices["details"]:
            print(
                f"  {item['name']:<8} | {item['T_2']:<18} | {item['T_1']:<18} | "
                f"{item['T']:<18} | {item['trend']:<18} | {item['advice']}"
            )

        print("\n【Level 2: ETF 资金风向标】")
        print("  🔥 领涨 Top4:")
        for item in result["etf_top"]:
            print(f"     • {item['name']:<12}: {item['pct']:<8} 量比{item['vol']:<5} ({item['status']})")
        print("  ❄️ 领跌 Top4:")
        for item in result["etf_bottom"]:
            print(f"     • {item['name']:<12}: {item['pct']:<8} 量比{item['vol']:<5}")

        print("\n【Level 3: 行业主线追踪】 (强度 = 成交额 * 涨幅)")
        print(f"  {'行业':<10} | {'T-2表现':<30} | {'T-1表现':<30} | {'T表现':<30} | 强度")
        print("  " + "-" * 110)
        for row in result["mainlines"]:
            print(f"  {row['industry']:<10} | {row['T_2']:<30} | {row['T_1']:<30} | {row['T']:<30} | {row['strength']}")

        print("\n【Level 4: 核心龙头矩阵】 (包含 🚀连板龙头 与 🐘成交中军)")
        print(f"  {'代码':<10} {'名称':<6} {'概念':<8} {'T-2表现':<20} {'T-1表现':<20} {'T表现':<20} {'成交额':<6} {'类型'}")
        print("  " + "-" * 115)
        for row in result["core_matrix"]:
            print(
                f"  {row['code']:<10} {row['name']:<6} {row['concept']:<8} "
                f"{row['T_2']:<20} {row['T_1']:<20} {row['T']:<20} {row['amount']:<6} {row['type']}"
            )

        print("=" * 120)


def main(sync_first=True, lookback=5):
    with ReviewRunner() as runner:
        return runner.run(sync_first=sync_first, lookback=lookback)


if __name__ == "__main__":
    import sys

    sync_first = "--no-sync" not in sys.argv
    lookback = 5
    for arg in sys.argv[1:]:
        if arg.isdigit():
            lookback = int(arg)
    main(sync_first, lookback)
