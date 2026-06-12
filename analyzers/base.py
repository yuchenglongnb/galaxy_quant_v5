# -*- coding: utf-8 -*-
"""
分析器基类 - 所有分析器的抽象基类
"""

from abc import ABC, abstractmethod
import pandas as pd


class BaseAnalyzer(ABC):
    """分析器基类"""
    
    def __init__(self, data_manager):
        """
        参数:
            data_manager: DataManager 实例
        """
        self.dm = data_manager
    
    @abstractmethod
    def analyze(self, target_date, **kwargs):
        """
        执行分析
        
        参数:
            target_date: 目标日期
            **kwargs: 其他参数
            
        返回:
            分析结果
        """
        pass
    
    def load_required_data(self, date_list, data_types):
        """
        加载所需数据
        
        参数:
            date_list: 日期列表
            data_types: 数据类型列表 ['stocks', 'indices', 'auction', ...]
            
        返回:
            dict: {data_type: DataFrame}
        """
        data = {}
        for dt in data_types:
            if dt == 'stocks':
                data[dt] = self.dm.load_stocks(date_list)
            elif dt == 'indices':
                data[dt] = self.dm.load_indices(date_list)
            elif dt == 'industry':
                data[dt] = self.dm.load_industry(date_list)
            elif dt == 'auction':
                data[dt] = self.dm.load_auction(date_list)
            elif dt == 'noon':
                data[dt] = self.dm.load_noon(date_list)
            elif dt == 'close':
                data[dt] = self.dm.load_close(date_list)
            else:
                data[dt] = self.dm.load_data(date_list, dt)
        return data
