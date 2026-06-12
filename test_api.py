#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AmazingData API 接口测试脚本

测试各个接口在不同时间段的可用性，帮助确定最佳数据获取方案

测试内容:
1. get_code_info - 证券信息（含pre_close）
2. query_snapshot - 历史快照查询
3. query_kline - 历史K线查询
4. SubscribeData - 实时订阅

运行方式:
    python test_api.py              # 运行所有测试
    python test_api.py snapshot     # 只测试快照
    python test_api.py subscribe    # 只测试订阅
    python test_api.py kline        # 只测试K线
    python test_api.py info         # 只测试证券信息
"""

import sys
import time
import threading
from datetime import datetime
from typing import Union

import AmazingData as ad
import pandas as pd

from config.settings import DBConfig  # 导入登录配置


# 测试用股票代码（选几个有代表性的）
TEST_CODES = [
    '600519.SH',  # 贵州茅台
    '000001.SZ',  # 平安银行
    '300750.SZ',  # 宁德时代
    '688981.SH',  # 中芯国际
    '000858.SZ',  # 五粮液
]


def do_login():
    """执行登录"""
    print(f">>> 登录API...")
    try:
        ad.login(
            username=DBConfig.USERNAME,
            password=DBConfig.PASSWORD,
            host=DBConfig.IP,  # 注意：配置里是IP，接口参数是host
            port=DBConfig.PORT
        )
        print(f"  ✅ 登录成功")
        return True
    except Exception as e:
        print(f"  ❌ 登录失败: {e}")
        return False


def get_current_trading_date():
    """获取当前交易日"""
    ad_base = ad.BaseData()
    calendar = ad_base.get_calendar()
    today = int(datetime.now().strftime('%Y%m%d'))
    
    # 找到最近的交易日
    valid_days = [d for d in calendar if d <= today]
    return valid_days[-1] if valid_days else today


def test_code_info():
    """
    测试1: get_code_info
    获取证券基础信息，包含pre_close（昨收价）
    """
    print("\n" + "="*60)
    print("  测试1: get_code_info (证券信息)")
    print("="*60)
    
    try:
        ad_base = ad.BaseData()
        
        # 测试股票
        print("\n>>> 获取A股证券信息...")
        t0 = time.time()
        code_info = ad_base.get_code_info(security_type='EXTRA_STOCK_A')
        elapsed = time.time() - t0
        
        if code_info is not None and not code_info.empty:
            print(f"  ✅ 成功! 耗时: {elapsed:.2f}s")
            print(f"  数据量: {len(code_info)} 条")
            print(f"  列名: {code_info.columns.tolist()}")
            
            # 显示测试股票的数据
            code_info_reset = code_info.reset_index()
            code_info_reset.columns = ['code'] + list(code_info_reset.columns[1:])
            
            print(f"\n  测试股票数据:")
            for code in TEST_CODES:
                row = code_info_reset[code_info_reset['code'] == code]
                if not row.empty:
                    pre_close = row.iloc[0].get('pre_close', 'N/A')
                    high_limit = row.iloc[0].get('high_limited', 'N/A')
                    print(f"    {code}: pre_close={pre_close}, high_limit={high_limit}")
            
            return True
        else:
            print(f"  ❌ 返回空数据")
            return False
            
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return False


def test_query_snapshot():
    """
    测试2: query_snapshot
    历史快照查询
    """
    print("\n" + "="*60)
    print("  测试2: query_snapshot (历史快照)")
    print("="*60)
    
    try:
        ad_base = ad.BaseData()
        calendar = ad_base.get_calendar()
        ad_market = ad.MarketData(calendar)
        
        target_date = get_current_trading_date()
        print(f"\n>>> 查询日期: {target_date}")
        
        # 测试不同时间点
        time_points = [
            (92500000, "9:25:00 (竞价结束)"),
            (93000000, "9:30:00 (开盘)"),
            (100000000, "10:00:00"),
            (None, "全天"),
        ]
        
        for time_ms, desc in time_points:
            print(f"\n>>> 测试时间点: {desc}")
            t0 = time.time()
            
            try:
                if time_ms:
                    snapshot_dict = ad_market.query_snapshot(
                        TEST_CODES,
                        begin_date=target_date,
                        end_date=target_date,
                        begin_time=time_ms,
                        end_time=time_ms
                    )
                else:
                    snapshot_dict = ad_market.query_snapshot(
                        TEST_CODES,
                        begin_date=target_date,
                        end_date=target_date
                    )
                
                elapsed = time.time() - t0
                
                if snapshot_dict:
                    total_rows = sum(len(df) for df in snapshot_dict.values() if df is not None and not df.empty)
                    print(f"  ✅ 成功! 耗时: {elapsed:.2f}s, 数据: {total_rows} 条")
                    
                    # 显示样例数据
                    for code, df in snapshot_dict.items():
                        if df is not None and not df.empty:
                            row = df.iloc[0]
                            print(f"    {code}:")
                            print(f"      trade_time: {row.get('trade_time', 'N/A')}")
                            print(f"      pre_close: {row.get('pre_close', 'N/A')}")
                            print(f"      open: {row.get('open', 'N/A')}")
                            print(f"      last: {row.get('last', 'N/A')}")
                            print(f"      volume: {row.get('volume', 'N/A')}")
                            print(f"      amount: {row.get('amount', 'N/A')}")
                            print(f"      columns: {df.columns.tolist()}")
                            break
                else:
                    print(f"  ⚠️ 返回空数据 (耗时: {elapsed:.2f}s)")
                    
            except Exception as e:
                print(f"  ❌ 失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        return False


def test_query_kline():
    """
    测试3: query_kline
    历史K线查询
    """
    print("\n" + "="*60)
    print("  测试3: query_kline (历史K线)")
    print("="*60)
    
    try:
        ad_base = ad.BaseData()
        calendar = ad_base.get_calendar()
        ad_market = ad.MarketData(calendar)
        
        target_date = get_current_trading_date()
        print(f"\n>>> 查询日期: {target_date}")
        
        # 测试日K线
        print(f"\n>>> 测试日K线...")
        t0 = time.time()
        kline_dict = ad_market.query_kline(
            TEST_CODES,
            begin_date=target_date,
            end_date=target_date,
            period=ad.constant.Period.day.value
        )
        elapsed = time.time() - t0
        
        if kline_dict:
            total_rows = sum(len(df) for df in kline_dict.values() if df is not None and not df.empty)
            print(f"  ✅ 日K线成功! 耗时: {elapsed:.2f}s, 数据: {total_rows} 条")
            
            for code, df in kline_dict.items():
                if df is not None and not df.empty:
                    row = df.iloc[0]
                    print(f"    {code}:")
                    print(f"      kline_time: {row.get('kline_time', 'N/A')}")
                    print(f"      open: {row.get('open', 'N/A')}")
                    print(f"      close: {row.get('close', 'N/A')}")
                    print(f"      列名: {df.columns.tolist()}")
                    break
        else:
            print(f"  ⚠️ 日K线返回空数据")
        
        # 测试分钟K线
        print(f"\n>>> 测试1分钟K线...")
        t0 = time.time()
        kline_dict = ad_market.query_kline(
            TEST_CODES,
            begin_date=target_date,
            end_date=target_date,
            period=ad.constant.Period.min1.value
        )
        elapsed = time.time() - t0
        
        if kline_dict:
            total_rows = sum(len(df) for df in kline_dict.values() if df is not None and not df.empty)
            print(f"  ✅ 分钟K线成功! 耗时: {elapsed:.2f}s, 数据: {total_rows} 条")
            
            for code, df in kline_dict.items():
                if df is not None and not df.empty:
                    print(f"    {code}: {len(df)} 根K线")
                    print(f"      第一根: {df.iloc[0].get('kline_time', 'N/A')}")
                    print(f"      最后根: {df.iloc[-1].get('kline_time', 'N/A')}")
                    break
        else:
            print(f"  ⚠️ 分钟K线返回空数据")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_subscribe():
    """
    测试4: SubscribeData
    实时订阅快照
    """
    print("\n" + "="*60)
    print("  测试4: SubscribeData (实时订阅)")
    print("="*60)
    
    print(f"\n>>> 订阅测试股票: {TEST_CODES}")
    print(f">>> 订阅时长: 10秒")
    
    collected_data = {}
    is_collecting = True
    
    try:
        sub_data = ad.SubscribeData()
        
        @sub_data.register(code_list=TEST_CODES, period=ad.constant.Period.snapshot.value)
        def on_snapshot(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):
            if not is_collecting:
                return
            
            try:
                code = getattr(data, 'code', None)
                if code:
                    snapshot = {
                        'code': code,
                        'trade_time': getattr(data, 'trade_time', None),
                        'pre_close': getattr(data, 'pre_close', None),
                        'last': getattr(data, 'last', None),
                        'open': getattr(data, 'open', None),
                        'high': getattr(data, 'high', None),
                        'low': getattr(data, 'low', None),
                        'close': getattr(data, 'close', None),
                        'volume': getattr(data, 'volume', None),
                        'amount': getattr(data, 'amount', None),
                    }
                    collected_data[code] = snapshot
                    print(f"  📥 收到: {code}, last={snapshot['last']}, open={snapshot['open']}")
            except Exception as e:
                print(f"  ⚠️ 处理数据错误: {e}")
        
        # 启动订阅线程
        def run_sub():
            try:
                sub_data.run()
            except:
                pass
        
        sub_thread = threading.Thread(target=run_sub, daemon=True)
        sub_thread.start()
        
        # 等待10秒收集数据
        print("\n>>> 开始收集数据...")
        for i in range(10):
            time.sleep(1)
            print(f"  ... {i+1}/10秒, 已收集: {len(collected_data)} 条")
        
        is_collecting = False
        
        # 汇总结果
        print(f"\n>>> 订阅结果汇总:")
        if collected_data:
            print(f"  ✅ 成功收集 {len(collected_data)} 条数据")
            for code, data in collected_data.items():
                print(f"    {code}:")
                print(f"      trade_time: {data['trade_time']}")
                print(f"      pre_close: {data['pre_close']}")
                print(f"      open: {data['open']}")
                print(f"      last: {data['last']}")
            return True
        else:
            print(f"  ⚠️ 未收集到数据")
            print(f"  可能原因:")
            print(f"    1. 当前非交易时间（9:15-15:00）")
            print(f"    2. 网络连接问题")
            print(f"    3. API权限问题")
            return False
            
    except Exception as e:
        print(f"  ❌ 订阅测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_all():
    """运行所有测试"""
    print("\n" + "="*60)
    print("  AmazingData API 接口测试")
    print("="*60)
    print(f"  当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  测试股票: {TEST_CODES}")
    
    # 先登录
    if not do_login():
        print("❌ 登录失败，无法继续测试")
        return
    
    results = {}
    
    # 测试1: 证券信息
    results['code_info'] = test_code_info()
    
    # 测试2: 历史快照
    results['snapshot'] = test_query_snapshot()
    
    # 测试3: 历史K线
    results['kline'] = test_query_kline()
    
    # 测试4: 实时订阅
    results['subscribe'] = test_subscribe()
    
    # 汇总
    print("\n" + "="*60)
    print("  测试结果汇总")
    print("="*60)
    for name, success in results.items():
        status = "✅ 成功" if success else "❌ 失败"
        print(f"  {name}: {status}")
    
    # 建议
    print("\n" + "="*60)
    print("  9:25盘前数据获取建议")
    print("="*60)
    
    if results.get('subscribe'):
        print("  ⚡ 推荐: 使用实时订阅模式 (-s)")
        print("     命令: python main.py auction -r -s --sync")
    elif results.get('snapshot'):
        print("  📊 可用: 使用快照查询模式")
        print("     命令: python main.py auction -r --sync")
    elif results.get('kline'):
        print("  ⚠️ 回退: 使用K线模式（9:30后才有数据）")
        print("     命令: python main.py auction -r --sync")
    else:
        print("  ❌ 所有接口不可用，请检查网络和API权限")


def main():
    """主入口"""
    if len(sys.argv) < 2:
        test_all()
    else:
        # 单独测试时也需要登录
        if not do_login():
            print("❌ 登录失败，无法继续测试")
            return
            
        cmd = sys.argv[1].lower()
        if cmd == 'info':
            test_code_info()
        elif cmd == 'snapshot':
            test_query_snapshot()
        elif cmd == 'kline':
            test_query_kline()
        elif cmd == 'subscribe':
            test_subscribe()
        else:
            test_all()


if __name__ == '__main__':
    main()
