#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GalaxyQuant - A股量化分析系统

用法:
    python main.py sync [天数]           # 完整同步数据
    python main.py sync --date=YYYYMMDD  # 显式同步指定交易日
    python main.py auction [--sync]      # 竞价分析（复盘模式）
    python main.py auction -r --sync     # 竞价分析（实时模式，快照查询）
    python main.py auction -r -s --sync  # 竞价分析（实时模式，订阅模式⚡）
    python main.py review [--no-sync]    # 盘后复盘
    python main.py weekly [开始日] [结束日] # 周度竞价特征复盘
    python main.py t1backtest [开始日] [结束日] # T+1可实现收益回测
    python main.py monitor               # ⭐盘中监测（整合竞价分析）
    python main.py monitor --summary     # 盘中监测 + 市场概览
    python main.py monitor -d            # ⭐守护模式（后台持续运行，到点自动启动）
    python main.py monitor --no-auction  # 仅监测，跳过竞价分析
    python main.py monitor --test        # 测试采集（单次）
    python main.py snapshot-backfill 20260608 --force  # 历史快照回补09:25-09:35确认层
    python main.py all                   # 同步 + 复盘 + 竞价
    python main.py refresh               # 刷新交易日缓存
    python main.py status                # 查看市场状态

选项:
    --sync         先同步数据再分析
    --no-sync      跳过数据同步
    --refresh      强制刷新交易日缓存
    --minute       同步最新交易日全部分钟数据（auction/noon/close）
    --minute=auction|noon|close|all  只同步指定分钟数据
    --force        强制重拉已有缓存
    --realtime     实时决策模式（9:25盘前）
    -r             --realtime 的简写
    --subscribe    使用实时订阅模式（推荐盘前使用，9:25立即可用）
    -s             --subscribe 的简写
    --summary      显示市场概览（monitor命令）
    --no-auction   跳过竞价分析（monitor命令）
    --test         测试模式（monitor命令）
    --daemon, -d   守护模式，后台持续运行（monitor命令）
    --interval=N   自定义采集间隔秒数（monitor命令）
    --entry=open_proxy|intraday_0935|intraday_0945
                   T+1回测入场口径，默认日线open代理
    --all-candidates
                   T+1回测包含全部研究候选，默认仅使用可执行短名单

守护模式说明 (--daemon / -d):
    程序可以在任意时间启动，自动等待到下一个交易日9:25开始工作。
    - 收盘后启动：等待到下一个交易日9:25
    - 盘前启动：等待到当天9:25
    - 交易中启动：立即开始监测
    - 每个交易日结束后自动等待下一个交易日
    - 支持跳过周末，按 Ctrl+C 可随时退出

数据获取模式说明:
    1. 快照查询模式（默认）: 使用query_snapshot查询历史快照
       - 优点: 稳定可靠
       - 缺点: 9:25时当天数据可能未入库
       
    2. 订阅模式（-s）: 使用SubscribeData实时订阅 ⚡推荐
       - 优点: 9:25立即可用，数据最新
       - 缺点: 需要保持网络连接
       
    3. K线模式（回退）: 使用query_kline获取分钟K线
       - 优点: 数据稳定
       - 缺点: 9:30才有第一根K线

盘中监测工作流程（monitor命令）:
    9:25  → 自动同步个股竞价数据（~5000只）
          → 执行竞价分析，输出CP/SA信号
    9:26  → 进入监测循环，每分钟采集指数+ETF
    ...
    15:00 → 收盘，自动退出（守护模式下等待下一个交易日）

示例:
    python main.py sync 5                  # 首次完整同步（收盘后执行）
    python main.py monitor -d --summary    # ⭐推荐：守护模式，持续运行
    python main.py monitor --summary       # 普通模式，需在交易时间启动
    python main.py monitor --no-auction    # 仅监测，不执行竞价分析
    python main.py status                  # 查看当前市场状态
"""

import sys
import time

from utils.encoding import configure_utf8_console


def _should_prefer_local_auction_replay(target_date, sync_first, force_refresh, realtime, use_subscribe):
    """Prefer local closed-cache replay for post-close auction analysis."""
    if sync_first or force_refresh or realtime or use_subscribe:
        return False
    try:
        from core.data_manager import DataManager

        dm = DataManager()
        local_days = dm.get_local_daily_days()
        if not local_days:
            return False
        if target_date is not None:
            return int(target_date) in local_days
        return True
    except Exception:
        return False


def _should_prefer_local_review_replay(lookback, force_refresh):
    """Prefer local closed-cache replay for post-close review analysis."""
    if force_refresh:
        return False
    try:
        from core.data_manager import DataManager
        dm = DataManager()
        local_days = dm.get_local_daily_days()
        return len(local_days) >= max(int(lookback), 3)
    except Exception:
        return False


def cmd_sync(args):
    """数据同步命令"""
    from runners.sync import SyncRunner

    lookback = 5
    minute_parts = []
    force = '--force' in args
    target_dates = []
    
    for arg in args:
        if arg.isdigit():
            lookback = int(arg)
        elif arg == '--minute':
            minute_parts = ['auction', 'noon', 'close']
        elif arg.startswith('--minute='):
            value = arg.split('=', 1)[1].strip().lower()
            if value == 'all':
                minute_parts = ['auction', 'noon', 'close']
            else:
                minute_parts = [x.strip() for x in value.split(',') if x.strip()]
        elif arg.startswith('--date='):
            value = arg.split('=', 1)[1].strip()
            target_dates.extend([x.strip() for x in value.split(',') if x.strip().isdigit() and len(x.strip()) == 8])
    
    with SyncRunner() as runner:
        return runner.run(
            lookback=lookback,
            with_minute=bool(minute_parts),
            minute_parts=minute_parts,
            force=force,
            target_dates=target_dates,
        )


def cmd_auction(args):
    """竞价分析命令"""
    from runners.auction import AuctionRunner

    target_date = None
    sync_first = '--sync' in args
    force_refresh = '--refresh' in args
    realtime = '--realtime' in args or '-r' in args
    use_subscribe = '--subscribe' in args or '-s' in args
    needs_login = sync_first or force_refresh or realtime or use_subscribe
    
    for arg in args:
        if arg.isdigit() and len(arg) == 8:
            target_date = int(arg)

    prefer_local_replay = _should_prefer_local_auction_replay(
        target_date=target_date,
        sync_first=sync_first,
        force_refresh=force_refresh,
        realtime=realtime,
        use_subscribe=use_subscribe,
    )
    if prefer_local_replay:
        print(">>> 检测到本地完整缓存，auction 主入口优先使用本地复盘模式")

    with AuctionRunner(auto_login=needs_login and not prefer_local_replay) as runner:
        return runner.run(target_date=target_date, sync_first=sync_first, 
                         force_refresh=force_refresh, realtime=realtime,
                         use_subscribe=use_subscribe)


def cmd_review(args):
    """盘后复盘命令"""
    from runners.review import ReviewRunner

    sync_first = '--no-sync' not in args
    lookback = 5
    force_refresh = '--refresh' in args
    
    for arg in args:
        if arg.isdigit() and len(arg) <= 2:
            lookback = int(arg)
    
    prefer_local_replay = _should_prefer_local_review_replay(
        lookback=lookback,
        force_refresh=force_refresh,
    )
    if prefer_local_replay:
        print(">>> 检测到本地完整缓存，review 主入口优先使用本地复盘模式")
        sync_first = False

    with ReviewRunner(auto_login=sync_first and not prefer_local_replay) as runner:
        return runner.run(sync_first=sync_first, lookback=lookback, force_refresh=force_refresh)


def cmd_weekly(args):
    """生成周度竞价特征复盘。"""
    from reports.weekly_review import run_weekly_review

    dates = [arg for arg in args if arg.isdigit() and len(arg) == 8]
    start_date = dates[0] if len(dates) >= 1 else None
    end_date = dates[1] if len(dates) >= 2 else None
    return run_weekly_review(start_date=start_date, end_date=end_date)


def cmd_ablation(args):
    """Run auction-only shortlist ablations from closed validation samples."""
    from reports.auction_ablation import run_auction_ablation

    dates = [arg for arg in args if arg.isdigit() and len(arg) == 8]
    start_date = dates[0] if len(dates) >= 1 else None
    end_date = dates[1] if len(dates) >= 2 else None
    return run_auction_ablation(start_date=start_date, end_date=end_date)


def cmd_regime(args):
    """Build regime/cluster win-rate summaries from closed validation samples."""
    from reports.regime_cluster_review import run_regime_cluster_review

    dates = [arg for arg in args if arg.isdigit() and len(arg) == 8]
    start_date = dates[0] if len(dates) >= 1 else None
    end_date = dates[1] if len(dates) >= 2 else None
    return run_regime_cluster_review(start_date=start_date, end_date=end_date)


def cmd_t1backtest(args):
    """Build T+1 executable-return labels from closed auction signals."""
    from reports.t1_backtest import run_t1_backtest

    dates = [arg for arg in args if arg.isdigit() and len(arg) == 8]
    start_date = dates[0] if len(dates) >= 1 else None
    end_date = dates[1] if len(dates) >= 2 else None
    entry_mode = "open_proxy"
    for arg in args:
        if arg.startswith("--entry="):
            entry_mode = arg.split("=", 1)[1].strip().lower()
    actionable_only = "--all-candidates" not in args
    return run_t1_backtest(
        start_date=start_date,
        end_date=end_date,
        entry_mode=entry_mode,
        actionable_only=actionable_only,
    )


def cmd_refresh(args):
    """刷新交易日缓存"""
    from core.data_manager import DataManager
    print("="*60)
    print("  刷新交易日缓存")
    print("="*60)
    dm = DataManager()
    dm.get_valid_trading_days(lookback=10, force_refresh=True)
    print("✅ 缓存刷新完成")


def cmd_monitor(args):
    """盘中实时监测命令（整合竞价分析）"""
    from runners.monitor import MonitorRunner

    show_summary = '--summary' in args
    test_mode = '--test' in args
    skip_auction = '--no-auction' in args
    use_subscribe = '--no-subscribe' not in args  # 默认使用订阅模式
    daemon = '--daemon' in args or '-d' in args   # 守护模式
    
    # 解析采集间隔
    interval = 60
    for arg in args:
        if arg.startswith('--interval='):
            try:
                interval = int(arg.split('=')[1])
            except:
                pass
    
    with MonitorRunner() as runner:
        return runner.run(
            show_summary=show_summary,
            test_mode=test_mode,
            skip_auction=skip_auction,
            interval=interval,
            use_subscribe=use_subscribe,
            daemon=daemon
        )


def cmd_snapshot_backfill(args):
    """历史 snapshot 回补 09:25-09:35 确认层。"""
    from runners.snapshot_backfill import SnapshotBackfillRunner

    target_date = None
    force = '--force' in args
    for arg in args:
        if arg.isdigit() and len(arg) == 8:
            target_date = int(arg)

    with SnapshotBackfillRunner(auto_login=True) as runner:
        return runner.run(target_date=target_date, force=force)


def cmd_status(args):
    """查看市场状态"""
    from runners.monitor import QuickMonitor

    QuickMonitor.show_status()
    QuickMonitor.show_schedule()


def cmd_qstock(args):
    """qstock 辅助数据源命令"""
    from runners.qstock import QStockRunner

    runner = QStockRunner()
    return runner.run(args)


def cmd_ifind(args):
    """iFinD MCP 题材补充层命令"""
    from runners.ifind import IFindRunner

    runner = IFindRunner()
    return runner.run(args)


def cmd_all(args):
    """完整流程"""
    from runners.auction import AuctionRunner
    from runners.review import ReviewRunner

    print("="*60)
    print("  GalaxyQuant - 完整分析流程")
    print("="*60)
    
    # 1. 同步数据
    dm, valid_days = cmd_sync(['5'])
    
    if not valid_days or len(valid_days) < 3:
        print("❌ 数据同步失败或数据不足")
        return
    
    # 2. 盘后复盘
    with ReviewRunner() as runner:
        runner.run(sync_first=False)
    
    # 3. 竞价分析
    with AuctionRunner() as runner:
        runner.run(sync_first=False)
    
    print("\n✅ 完整分析流程执行完毕")


def print_help():
    """打印帮助信息"""
    print(__doc__)


def main():
    """主入口"""
    configure_utf8_console()
    if len(sys.argv) < 2:
        print_help()
        return
    
    cmd = sys.argv[1].lower()
    args = sys.argv[2:]
    
    commands = {
        'sync': cmd_sync,
        'auction': cmd_auction,
        'review': cmd_review,
        'weekly': cmd_weekly,
        'ablation': cmd_ablation,
        'regime': cmd_regime,
        't1backtest': cmd_t1backtest,
        'monitor': cmd_monitor,
        'snapshot-backfill': cmd_snapshot_backfill,
        'qstock': cmd_qstock,
        'ifind': cmd_ifind,
        'status': cmd_status,
        'all': cmd_all,
        'refresh': cmd_refresh,
        'help': lambda x: print_help(),
        '-h': lambda x: print_help(),
        '--help': lambda x: print_help(),
    }
    
    if cmd in commands:
        start_time = time.time()
        try:
            commands[cmd](args)
        except KeyboardInterrupt:
            print("\n⚠️ 用户中断")
        except Exception as e:
            print(f"\n❌ 执行错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print(f"\n⏱️ 总耗时: {time.time() - start_time:.1f}s")
    else:
        print(f"未知命令: {cmd}")
        print_help()


if __name__ == "__main__":
    main()
