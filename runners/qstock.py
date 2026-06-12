# -*- coding: utf-8 -*-
"""Runner for qstock side-cache tasks."""

from __future__ import annotations

from providers.qstock_provider import QStockProvider, QStockProviderError, QStockUnavailable
from providers.ths_concept_provider import ThsConceptError, ThsConceptProvider


class QStockRunner:
    """CLI facade for qstock optional data tasks."""

    def __init__(self):
        self.provider = QStockProvider()
        self.ths_provider = ThsConceptProvider()

    def run(self, args):
        if not args or args[0] in {"help", "-h", "--help"}:
            self.print_help()
            return None

        action = args[0].lower()
        options = args[1:]
        try:
            if action in {"concept", "concepts"}:
                return self._concept(options)
            if action in {"concept-index", "index"}:
                return self._concept_index(options)
            if action in {"map", "concept-map"}:
                return self._concept_map(options)
            if action in {"enrich-pool", "pool-concepts"}:
                return self._enrich_pool(options)
            if action in {"signal-concepts", "useful-concepts"}:
                return self._signal_concepts(options)
            if action in {"money", "concept-money"}:
                return self._concept_money(options)
            if action in {"realtime", "snapshot"}:
                return self._realtime(options)
            if action in {"change", "changes"}:
                return self._change(options)
            if action == "all":
                self._concept(options)
                self._concept_money(options)
                self._realtime(options)
                self._change(options)
                return self._concept_map(options)
            print(f"未知 qstock 子命令: {action}")
            self.print_help()
        except QStockUnavailable as exc:
            print(f"⚠️ {exc}")
            print("   当前项目已把 qstock 作为可选辅助源；未安装时主链路不受影响。")
        except QStockProviderError as exc:
            print(f"⚠️ {exc}")
            print("   qstock 依赖公开网页源，当前网络/代理不可用时会失败；主链路不受影响。")
        except Exception as exc:
            print(f"⚠️ qstock 任务失败: {exc}")
            print("   已按辅助源降级处理，主链路不受影响。")
        return None

    def _parse_int_option(self, args, name, default=None):
        prefix = f"--{name}="
        for arg in args:
            if arg.startswith(prefix):
                try:
                    return int(arg.split("=", 1)[1])
                except ValueError:
                    return default
        return default

    def _parse_flag_option(self, args):
        for arg in args:
            if arg.startswith("--flag="):
                return arg.split("=", 1)[1]
        return None

    def _parse_value_option(self, args, name, default=None):
        prefix = f"--{name}="
        for arg in args:
            if arg.startswith(prefix):
                return arg.split("=", 1)[1]
        return default

    def _concept(self, args):
        try:
            df = self.ths_provider.fetch_concept_list()
            print(f"✓ 同花顺概念列表: {len(df)} 条")
            return df
        except ThsConceptError as exc:
            print(f"⚠️ 同花顺轻量概念请求失败: {exc}")
            return None

    def _concept_map(self, args):
        limit = self._parse_int_option(args, "limit")
        try:
            df = self.ths_provider.fetch_concept_member_map(limit=limit)
            print(f"✓ 股票池-同花顺概念映射: {len(df)} 条")
            return df
        except ThsConceptError as exc:
            print(f"⚠️ 同花顺轻量概念映射失败: {exc}")
            return None

    def _enrich_pool(self, args):
        try:
            df = self.ths_provider.enrich_stock_pool_with_concepts()
            tagged = int((df.get("ths_concept_count", 0).fillna(0).astype(int) > 0).sum()) if not df.empty else 0
            signal_tagged = int((df.get("ths_signal_concept_count", 0).fillna(0).astype(int) > 0).sum()) if not df.empty else 0
            print(f"✓ 股票池已追加同花顺概念: 原始 {tagged}/{len(df)}，可用题材 {signal_tagged}/{len(df)}")
            return df
        except ThsConceptError as exc:
            print(f"⚠️ 股票池追加同花顺概念失败: {exc}")
            return None

    def _signal_concepts(self, args):
        try:
            df = self.ths_provider.build_signal_concept_table()
            print(f"✓ 股票池可用题材概念表: {len(df)} 条")
            return df
        except ThsConceptError as exc:
            print(f"⚠️ 生成可用题材概念表失败: {exc}")
            return None

    def _concept_money(self, args):
        n = self._parse_int_option(args, "n", default=5)
        try:
            df = self.ths_provider.fetch_concept_money(n=n or 5)
            print(f"✓ 同花顺概念资金流: {len(df)} 条")
            return df
        except ThsConceptError as exc:
            print(f"⚠️ 同花顺轻量概念资金流失败: {exc}")
            return None

    def _concept_index(self, args):
        concept = self._parse_value_option(args, "concept")
        start_year = self._parse_int_option(args, "start-year", default=2024) or 2024
        top_n = self._parse_int_option(args, "top", default=20) or 20
        try:
            if concept:
                df = self.ths_provider.fetch_concept_index_data(concept, start_year=start_year)
                print(f"✓ 同花顺概念指数 {concept}: {len(df)} 条")
            else:
                df = self.ths_provider.fetch_exposed_concept_index_data(top_n=top_n, start_year=start_year)
                print(f"✓ 股票池暴露概念指数: {len(df)} 条")
            return df
        except ThsConceptError as exc:
            print(f"⚠️ 同花顺轻量概念指数失败: {exc}")
            return None

    def _realtime(self, args):
        df = self.provider.fetch_realtime_snapshot()
        print(f"✓ 股票池实时快照: {len(df)} 条")
        return df

    def _change(self, args):
        flag = self._parse_flag_option(args)
        df = self.provider.fetch_realtime_change(flag)
        print(f"✓ 盘口异动: {len(df)} 条")
        return df

    def print_help(self):
        print(
            """
qstock 辅助数据命令:
  python main.py qstock concept              # 同花顺概念列表
  python main.py qstock money --n=5          # 同花顺概念资金流
  python main.py qstock map [--limit=50]     # 股票池映射到同花顺概念
  python main.py qstock enrich-pool          # 将同花顺概念追加到watchlists/stock_pool.csv
  python main.py qstock signal-concepts      # 生成过滤后的可用题材概念表
  python main.py qstock concept-index --concept=有机硅概念 --start-year=2024
  python main.py qstock concept-index --top=20 --start-year=2024
  python main.py qstock realtime             # 股票池实时快照
  python main.py qstock change [--flag=竞价上涨]
  python main.py qstock all                  # 拉取上述常用缓存

输出目录:
  概念相关: AmazingData_Store/YYYYMMDD/ths/
  qstock降级: AmazingData_Store/YYYYMMDD/qstock/
""".strip()
        )
