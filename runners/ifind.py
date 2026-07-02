# -*- coding: utf-8 -*-
"""CLI facade for local iFinD MCP-derived snapshots."""

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
        if action in {"market-structure", "structure"}:
            return self._market_structure(options)
        if action in {"raw-readiness", "raw"}:
            return self._raw_readiness(options)
        print(f"Unknown ifind subcommand: {action}")
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
        print(f"[ok] built iFinD overlay template: {len(df)} rows")
        return df

    def _apply_snapshot(self, args):
        input_path = self._parse_value_option(args, "input")
        output_path = self._parse_value_option(args, "output")
        date_value = self._parse_value_option(args, "date")
        if not input_path:
            raise ValueError("Missing --input=SNAPSHOT_CSV")
        df = _read_csv_auto(input_path)
        overlay = self.provider.apply_snapshot(
            df,
            output_path=output_path,
            date_int=int(date_value) if date_value else None,
        )
        print(f"[ok] applied iFinD theme snapshot: {len(overlay)} rows")
        return overlay

    def _exposure(self, args):
        input_path = self._parse_value_option(args, "input")
        date_value = self._parse_value_option(args, "date")
        overlay = self.provider.load_overlay(path=input_path) if input_path else self.provider.load_overlay()
        result = self.provider.build_concept_exposure(
            overlay=overlay,
            date_int=int(date_value) if date_value else None,
        )
        print(f"[ok] built iFinD theme exposure: {len(result)} rows")
        return result

    def _merge_preview(self, args):
        output_path = self._parse_value_option(args, "output")
        merged = self.provider.merge_overlay_into_stock_pool(output_path=output_path)
        print(f"[ok] built stock-pool merge preview: {len(merged)} rows")
        return merged

    def _coverage(self, args):
        from scripts.evaluate_ifind_overlay_coverage import evaluate, write_outputs

        date_value = self._parse_value_option(args, "date")
        if not date_value:
            raise ValueError("Missing --date=YYYYMMDD")
        top_missing = int(self._parse_value_option(args, "top-missing", 30))
        payload = evaluate(int(date_value), top_missing=top_missing)
        json_path, md_path = write_outputs(payload)
        print(f"[ok] iFinD overlay coverage json: {json_path}")
        print(f"[ok] iFinD overlay coverage md: {md_path}")
        return payload

    def _market_structure(self, args):
        from scripts.evaluate_ifind_market_structure import evaluate, write_outputs

        date_value = self._parse_value_option(args, "date")
        limitup_raw = self._parse_value_option(args, "limitup-raw")
        sector_raw = self._parse_value_option(args, "sector-raw")
        sector_only = "--sector-only" in args
        if not date_value:
            raise ValueError("Missing --date=YYYYMMDD")
        if not sector_raw:
            raise ValueError("Missing --sector-raw=PATH")
        if not limitup_raw and not sector_only:
            raise ValueError("Missing --limitup-raw=PATH")
        payload = evaluate(
            int(date_value),
            limitup_raw=limitup_raw,
            sector_raw=sector_raw,
            sector_only=sector_only,
        )
        json_path, md_path = write_outputs(payload)
        print(f"[ok] iFinD market structure json: {json_path}")
        print(f"[ok] iFinD market structure md: {md_path}")
        return payload

    def _raw_readiness(self, args):
        from scripts.evaluate_ifind_raw_readiness import build_payload, write_outputs

        date_value = self._parse_value_option(args, "date")
        dates_value = self._parse_value_option(args, "dates")
        start_date = self._parse_value_option(args, "start-date")
        end_date = self._parse_value_option(args, "end-date")
        source = self._parse_value_option(args, "source", "manual_export")
        if dates_value:
            dates = [item.strip() for item in dates_value.split(",") if item.strip()]
        elif date_value:
            dates = [date_value]
        elif start_date and end_date:
            from datetime import datetime, timedelta

            start = datetime.strptime(start_date, "%Y%m%d").date()
            end = datetime.strptime(end_date, "%Y%m%d").date()
            dates = []
            cursor = start
            while cursor <= end:
                dates.append(cursor.strftime("%Y%m%d"))
                cursor += timedelta(days=1)
        else:
            raise ValueError("Missing --date=YYYYMMDD or --start-date=YYYYMMDD --end-date=YYYYMMDD")
        payload = build_payload(dates, source=source, write_manifest_files="--no-write-manifest" not in args)
        json_path, md_path = write_outputs(payload)
        print(f"[ok] iFinD raw readiness json: {json_path}")
        print(f"[ok] iFinD raw readiness md: {md_path}")
        return payload

    @staticmethod
    def print_help():
        print(
            """
ifind local workflow:
  python main.py ifind template
  python main.py ifind apply-snapshot --input=PATH [--date=YYYYMMDD]
  python main.py ifind exposure [--input=PATH] [--date=YYYYMMDD]
  python main.py ifind merge-preview [--output=PATH]
  python main.py ifind coverage --date=YYYYMMDD [--top-missing=30]
  python main.py ifind raw-readiness --date=YYYYMMDD
  python main.py ifind raw-readiness --start-date=YYYYMMDD --end-date=YYYYMMDD
  python main.py ifind market-structure --date=YYYYMMDD --limitup-raw=PATH --sector-raw=PATH
  python main.py ifind market-structure --date=YYYYMMDD --sector-raw=PATH --sector-only

Notes:
  - This command does not call iFinD MCP directly.
  - MCP queries should be exported to CSV snapshots first, then consumed locally.
  - The repository only standardizes persisted CSV snapshots and writes local cache/report outputs.
""".strip()
        )
