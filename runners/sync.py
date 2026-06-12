# -*- coding: utf-8 -*-
"""
数据同步运行器 - 独立的数据同步入口
"""

from runners.base import BaseRunner
from core.data_manager import DataManager


class SyncRunner(BaseRunner):
    """数据同步运行器"""
    
    def run(self, lookback=5, with_minute=False, minute_parts=None, force=False,
            target_dates=None, **kwargs):
        """
        执行数据同步
        
        参数:
            lookback: 回看天数
            with_minute: 是否同步分钟数据（竞价分析用）
            minute_parts: 分钟数据类型，支持 auction/noon/close
            force: 是否强制重拉已有文件
        """
        print(f"\n{'='*60}")
        print(f"  数据同步 - 最近 {lookback} 个交易日")
        print(f"{'='*60}")
        if with_minute:
            print(f"  分钟数据: {minute_parts or ['auction', 'noon', 'close']}")
        if force:
            print("  模式: 强制刷新")
        
        dm = DataManager()
        if target_dates:
            valid_days = [int(day) for day in target_dates]
            print(f"[Sync] 显式日期计划: {valid_days}")
            for day in valid_days:
                dm.fetch_daily_all(
                    day,
                    with_minute=with_minute,
                    minute_parts=minute_parts,
                    force=force,
                )
        else:
            valid_days = dm.sync_recent_days(
                lookback=lookback,
                latest_with_minute=with_minute,
                minute_parts=minute_parts,
                force=force,
            )
        
        print(f"\n✅ 同步完成: {valid_days}")
        return dm, valid_days


def main(lookback=5, with_minute=False, minute_parts=None, force=False):
    """独立运行入口"""
    with SyncRunner() as runner:
        return runner.run(lookback=lookback, with_minute=with_minute, minute_parts=minute_parts, force=force)


if __name__ == "__main__":
    import sys
    lookback = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    with_minute = '--minute' in sys.argv
    force = '--force' in sys.argv
    main(lookback, with_minute, force=force)
