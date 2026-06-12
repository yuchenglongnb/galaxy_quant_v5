# -*- coding: utf-8 -*-
"""
日历工具 - 交易日历管理
"""

import datetime
import AmazingData as ad


class CalendarHelper:
    """交易日历工具"""
    
    @staticmethod
    def generate_workday_calendar(days=400):
        """生成工作日日历"""
        today = datetime.date.today()
        start = today - datetime.timedelta(days=days)
        calendar = []
        current = start
        while current <= today:
            if current.weekday() < 5:
                calendar.append(int(current.strftime("%Y%m%d")))
            current += datetime.timedelta(days=1)
        return calendar
    
    @staticmethod
    def filter_valid_trading_days(calendar, ad_market, check_count=10):
        """验证有效交易日"""
        valid_days = []
        recent_days = sorted(calendar)[-check_count:]
        for d in reversed(recent_days):
            try:
                result = ad_market.query_kline(["000001.SH"], d, d, ad.constant.Period.day.value)
                if result and "000001.SH" in result:
                    df = result["000001.SH"]
                    if df is not None and not df.empty:
                        valid_days.append(d)
            except:
                pass
        return sorted(valid_days)
    
    @staticmethod
    def get_date_range(valid_days, lookback=5):
        """获取日期范围"""
        if len(valid_days) < lookback:
            return valid_days
        return valid_days[-lookback:]
