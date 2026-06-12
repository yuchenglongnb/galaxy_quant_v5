# -*- coding: utf-8 -*-
"""Historical snapshot backfill runner for opening-session confirmation."""

from __future__ import annotations

import os

from runners.base import BaseRunner


class SnapshotBackfillRunner(BaseRunner):
    """Rebuild 09:25-09:35 confirmation files from historical snapshots."""

    def run(self, target_date=None, force=False, **kwargs):
        from core.data_manager import DataManager

        dm = DataManager()
        valid_days = dm.get_valid_trading_days(lookback=5)
        if target_date is None:
            if not valid_days:
                print("❌ 无有效交易日")
                return None
            target_date = int(valid_days[-1])
        else:
            target_date = int(target_date)

        print("\n" + "=" * 60)
        print(f"  Snapshot 回补 09:25-09:35 [{target_date}]")
        print("=" * 60)

        result = dm.rebuild_intraday_confirmation_from_snapshot(target_date, force=force)
        intraday_dir = os.path.join(dm.base_path, str(target_date), "intraday")

        print(f"  输出目录: {os.path.abspath(intraday_dir)}")
        if isinstance(result, dict):
            print(f"  回补结果: {result}")
        return result

