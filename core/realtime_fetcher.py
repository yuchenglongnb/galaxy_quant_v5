# -*- coding: utf-8 -*-
"""
实时数据获取器 - 使用SubscribeData订阅实时快照

用于9:25竞价分析，解决历史快照/K线接口在盘前不可用的问题
"""

import os
import time
import pandas as pd
import AmazingData as ad
from typing import Union, List, Dict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from config.settings import AuctionConfig

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, desc=None, **kwargs):
        print(f"--- {desc} ---")
        return iterable


class RealtimeFetcher:
    """
    实时快照数据获取器
    
    使用SubscribeData订阅模式获取实时快照数据
    适用于9:25-9:30盘前竞价分析
    """
    
    def __init__(self, timeout=60):
        """
        初始化
        
        参数:
            timeout: 订阅超时时间（秒），默认60秒
        """
        self.timeout = timeout
        self.ad_base = ad.BaseData()
        self._data_buffer = {}  # code -> snapshot_data
        self._is_collecting = False
        
    def fetch_auction_snapshot(
        self,
        code_list: List[str],
        save_path: str = None,
        capture_seconds: float = AuctionConfig.REALTIME_CAPTURE_SECONDS,
    ) -> pd.DataFrame:
        """
        获取竞价快照数据
        
        使用实时订阅模式获取所有股票的当前快照
        
        参数:
            code_list: 股票代码列表
            save_path: 保存路径（可选）
            
        返回:
            DataFrame: 快照数据
        """
        print(f"  >>> 实时订阅模式获取快照数据...")
        print(f"      标的数量: {len(code_list)}")
        
        self._data_buffer = {}
        self._is_collecting = True
        
        # 分批订阅（每批500个，避免订阅过载）
        batch_size = 500
        batches = [code_list[i:i+batch_size] for i in range(0, len(code_list), batch_size)]
        
        start_time = time.time()
        
        for batch_idx, batch_codes in enumerate(batches):
            try:
                self._subscribe_batch(batch_codes, batch_idx, len(batches))
            except Exception as e:
                print(f"      ⚠️ 批次{batch_idx+1}订阅失败: {e}")
                continue
        
        elapsed = time.time() - start_time
        print(f"  ✓ 实时快照获取完成: {len(self._data_buffer)} 条, 耗时: {elapsed:.1f}s")
        
        # 转换为DataFrame
        if not self._data_buffer:
            return pd.DataFrame()
        
        rows = list(self._data_buffer.values())
        df = pd.DataFrame(rows)
        
        # 保存到文件
        if save_path and not df.empty:
            df.to_csv(save_path, index=False, encoding='utf-8-sig')
            print(f"  ✓ 保存到: {save_path}")
        
        return df
    
    def _subscribe_batch(self, batch_codes: List[str], batch_idx: int, total_batches: int):
        """
        订阅一批股票的快照数据
        
        注意：SubscribeData.run()是阻塞的，需要在回调中收集数据
        这里使用一个技巧：订阅后等待一小段时间收集数据，然后停止
        """
        collected_count = [0]  # 用列表包装以便在闭包中修改
        target_count = len(batch_codes)
        batch_start = time.time()
        
        sub_data = ad.SubscribeData()
        
        @sub_data.register(code_list=batch_codes, period=ad.constant.Period.snapshot.value)
        def on_snapshot(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):
            if not self._is_collecting:
                return
            
            try:
                # Keep replacing snapshots until the capture window closes. The
                # final callback after 09:25 is the actionable auction snapshot.
                code = getattr(data, 'code', None)
                if code:
                    snapshot = {
                        'code': code,
                        'trade_time': getattr(data, 'trade_time', None),
                        'pre_close': getattr(data, 'pre_close', 0),
                        'last': getattr(data, 'last', 0),
                        'open': getattr(data, 'open', 0),
                        'high': getattr(data, 'high', 0),
                        'low': getattr(data, 'low', 0),
                        'close': getattr(data, 'close', 0),
                        'volume': getattr(data, 'volume', 0),
                        'amount': getattr(data, 'amount', 0),
                        'high_limited': getattr(data, 'high_limited', 0),
                        'low_limited': getattr(data, 'low_limited', 0),
                        'auction_source': 'subscription_925',
                        'auction_amount_exact': True,
                        'auction_asof': datetime.now().isoformat(timespec='milliseconds'),
                    }
                    is_new = code not in self._data_buffer
                    self._data_buffer[code] = snapshot
                    if is_new:
                        collected_count[0] += 1
            except Exception as e:
                pass
        
        # 启动订阅（非阻塞方式，使用线程）
        import threading
        
        def run_subscription():
            try:
                sub_data.run()
            except:
                pass
        
        sub_thread = threading.Thread(target=run_subscription, daemon=True)
        sub_thread.start()
        
        # Wait through a short capture window even after initial coverage. This
        # allows late callbacks to replace virtual-auction snapshots with the
        # final matched snapshot available after 09:25.
        wait_interval = 0.1
        max_wait = min(self.timeout, 30)  # 每批最多等30秒
        waited = 0
        coverage_reached_at = None
        
        while waited < max_wait:
            time.sleep(wait_interval)
            waited += wait_interval
            
            if collected_count[0] >= target_count * AuctionConfig.REALTIME_CAPTURE_MIN_RATIO:
                coverage_reached_at = coverage_reached_at or waited
            if coverage_reached_at is not None and waited - coverage_reached_at >= capture_seconds:
                break
        
        # 停止订阅
        self._is_collecting = False
        
        batch_elapsed = time.time() - batch_start
        print(f"      批次 {batch_idx+1}/{total_batches}: {collected_count[0]}/{target_count} 条, {batch_elapsed:.1f}s")
        
        # 重新开启收集
        self._is_collecting = True


class RealtimeFetcherSimple:
    """
    简化版实时数据获取器
    
    使用get_code_info获取pre_close + 历史K线的open作为竞价价格
    这是一个备选方案，当实时订阅不可用时使用
    """
    
    def __init__(self):
        self.ad_base = ad.BaseData()
        self.ad_market = None
        
    def fetch_auction_data(self, code_list: List[str], target_date: int, save_path: str = None) -> pd.DataFrame:
        """
        获取竞价数据（备选方案）
        
        组合使用:
        1. get_code_info: 获取pre_close（昨收价）、涨跌停价
        2. query_kline: 获取当日K线的open（开盘价）
        
        参数:
            code_list: 股票代码列表
            target_date: 目标日期
            save_path: 保存路径
            
        返回:
            DataFrame: 竞价数据
        """
        print(f"  >>> 组合模式获取竞价数据...")
        
        # 1. 获取证券信息（pre_close）
        print(f"      获取证券信息...")
        try:
            code_info = self.ad_base.get_code_info(security_type='EXTRA_STOCK_A')
            if code_info is not None and not code_info.empty:
                code_info = code_info.reset_index()
                code_info.columns = ['code'] + list(code_info.columns[1:])
            else:
                code_info = pd.DataFrame()
        except Exception as e:
            print(f"      ⚠️ 获取证券信息失败: {e}")
            code_info = pd.DataFrame()
        
        # 2. 获取当日K线（open）
        print(f"      获取日K线...")
        try:
            calendar = self.ad_base.get_calendar()
            self.ad_market = ad.MarketData(calendar)
            
            kline_dict = self.ad_market.query_kline(
                code_list[:100],  # 先测试少量
                begin_date=target_date,
                end_date=target_date,
                period=ad.constant.Period.day.value
            )
            
            kline_rows = []
            if kline_dict:
                for code, df in kline_dict.items():
                    if df is not None and not df.empty:
                        row = df.iloc[0].to_dict()
                        row['code'] = code
                        kline_rows.append(row)
            
            df_kline = pd.DataFrame(kline_rows) if kline_rows else pd.DataFrame()
            
        except Exception as e:
            print(f"      ⚠️ 获取K线失败: {e}")
            df_kline = pd.DataFrame()
        
        # 3. 合并数据
        if code_info.empty and df_kline.empty:
            return pd.DataFrame()
        
        if not df_kline.empty:
            df = df_kline.copy()
            if not code_info.empty and 'pre_close' in code_info.columns:
                pre_close_map = code_info.set_index('code')['pre_close'].to_dict()
                df['pre_close'] = df['code'].map(pre_close_map)
        else:
            df = code_info.copy()
        
        if save_path and not df.empty:
            df.to_csv(save_path, index=False, encoding='utf-8-sig')
            print(f"  ✓ 保存到: {save_path}")
        
        return df


def test_realtime_fetcher():
    """测试实时数据获取器"""
    print("=" * 60)
    print("  测试实时快照订阅")
    print("=" * 60)
    
    # 获取股票列表
    ad_base = ad.BaseData()
    code_list = ad_base.get_code_list(security_type='EXTRA_STOCK_A')
    print(f"股票数量: {len(code_list)}")
    
    # 测试少量股票
    test_codes = code_list[:50]
    
    fetcher = RealtimeFetcher(timeout=30)
    df = fetcher.fetch_auction_snapshot(test_codes)
    
    print(f"\n获取结果: {len(df)} 条")
    if not df.empty:
        print(df.head())
        print(f"\n列: {df.columns.tolist()}")


if __name__ == '__main__':
    test_realtime_fetcher()
