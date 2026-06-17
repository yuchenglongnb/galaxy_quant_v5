# -*- coding: utf-8 -*-
"""CLI facade for local iFinD MCP-derived theme overlays."""

from __future__ import annotations

from providers.ifind_theme_provider import IFindThemeProvider
from providers.qstock_provider import _read_csv_auto


class IFindRunner:
    """Manage local overlay files produced from iFinD MCP snapshots."""

    def __init__(self):
        self.provider = IFindThemeProvider()

    def run(self, args):
        if not args or args[0] in {"help", "-h", "--help"}:
            self.print_help()
            return None
        action = args[0].lower()
        options = args[1:]
        if action in {"template", "init-overlay"}:
            return self._template(options)
        if action in {"apply-snapshot", "apply"}:
            return self._apply_snapshot(options)
        if action in {"exposure", "theme-exposure"}:
            return self._exposure(options)
        if action in {"merge-preview", "preview"}:
            return self._merge_preview(options)
        if action in {"coverage", "audit"}:
            return self._coverage(options)
        print(f"未知 ifind 子命令: {action}")
        self.print_help()
        return None

    @staticmethod
    def _parse_value_option(args, name, default=None):
        prefix = f"--{name}="
        for arg in args:
            if arg.startswith(prefix):
                return arg.split("=", 1)[1]
        return default

    def _template(self, args):
        output_path = self._parse_value_option(args, "output")
        df = self.provider.build_overlay_template(output_path=output_path)
        print(f"✓ iFinD overlay 模板已生成: {len(df)} 条")
        return df

    def _apply_snapshot(self, args):
        input_path = self._parse_value_option(args, "input")
        output_path = self._parse_value_option(args, "output")
        date_value = self._parse_value_option(args, "date")
        if not input_path:
            raise ValueError("缺少 --input=SNAPSHOT_CSV")
        df = _read_csv_auto(input_path)
        overlay = self.provider.apply_snapshot(
            df,
            output_path=output_path,
            date_int=int(date_value) if date_value else None,
        )
        print(f"✓ 已应用 iFinD snapshot: {len(overlay)} 条")
        return overlay

    def _exposure(self, args):
        input_path = self._parse_value_option(args, "input")
        date_value = self._parse_value_option(args, "date")
        overlay = self.provider.load_overlay(path=input_path) if input_path else self.provider.load_overlay()
        result = self.provider.build_concept_exposure(
            overlay=overlay,
            date_int=int(date_value) if date_value else None,
        )
        print(f"✓ 已生成 iFinD 题材暴露表: {len(result)} 条")
        return result

    def _merge_preview(self, args):
        output_path = self._parse_value_option(args, "output")
        merged = self.provider.merge_overlay_into_stock_pool(output_path=output_path)
        print(f"✓ 已生成股票池 + iFinD overlay 预览: {len(merged)} 条")
        return merged

    def _coverage(self, args):
        from scripts.evaluate_ifind_overlay_coverage import evaluate, write_outputs

        date_value = self._parse_value_option(args, "date")
        if not date_value:
            raise ValueError("缺少 --date=YYYYMMDD")
        top_missing = int(self._parse_value_option(args, "top-missing", 30))
        payload = evaluate(int(date_value), top_missing=top_missing)
        json_path, md_path = write_outputs(payload)
        print(f"✓ 已生成 iFinD overlay coverage: {json_path}")
        print(f"✓ 已生成 iFinD overlay coverage: {md_path}")
        return payload

    @staticmethod
    def print_help():
        print(
            """
ifind 题材补充命令:
  python main.py ifind template
  python main.py ifind apply-snapshot --input=PATH [--date=YYYYMMDD]
  python main.py ifind exposure [--input=PATH] [--date=YYYYMMDD]
  python main.py ifind merge-preview [--output=PATH]
  python main.py ifind coverage --date=YYYYMMDD [--top-missing=30]

说明:
  - 本命令不直接调用 iFinD MCP。
  - iFinD MCP 由 Codex 会话内查询后落为 CSV snapshot，再由本命令写入本地 overlay。
  - 默认 overlay 文件: watchlists/stock_pool_ifind_overlay.csv
""".strip()
        )
