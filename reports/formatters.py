# -*- coding: utf-8 -*-
"""
报告格式化工具 - 统一的报告格式化
"""

import pandas as pd


class ReportFormatter:
    """报告格式化器"""
    
    @staticmethod
    def format_pct(value, decimals=2):
        """格式化百分比"""
        if pd.isna(value):
            return "-"
        return f"{value:+.{decimals}f}%"
    
    @staticmethod
    def format_amount(value, unit='亿'):
        """格式化金额"""
        if pd.isna(value):
            return "-"
        if unit == '亿':
            return f"{value/1e8:.1f}亿"
        elif unit == '万':
            return f"{value/1e4:.1f}万"
        return f"{value:.2f}"
    
    @staticmethod
    def format_vol_ratio(value):
        """格式化量比"""
        if pd.isna(value):
            return "-"
        if value < 0.7:
            return f"缩量({value:.1f})"
        elif value > 1.2:
            return f"放量({value:.1f})"
        return f"温和({value:.1f})"
    
    @staticmethod
    def get_vol_status(vol_ratio):
        """获取量能状态"""
        if vol_ratio < 0.8:
            return "缩量"
        elif vol_ratio > 1.2:
            return "放量"
        return "温和"
    
    @staticmethod
    def format_table(df, title=None, max_width=120):
        """格式化表格输出"""
        output = []
        if title:
            output.append(f"\n【{title}】")
        output.append(df.to_string(index=False))
        return '\n'.join(output)
    
    @staticmethod
    def format_section_header(title, width=60, char='='):
        """格式化章节标题"""
        return f"\n{char*width}\n  {title}\n{char*width}"
