# -*- coding: utf-8 -*-
"""Dry-run validation for exported iFind sector-strength raw CSV files."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.encoding import configure_utf8_console  # noqa: E402


EVAL_ROOT = ROOT / "reports" / "analysis" / "evaluations"
TEMPLATE_PATH = ROOT / "reports" / "analysis" / "templates" / "sector_strength_raw_template.csv"
REQUIRED_FIELDS = [
    "sector_name",
    "pct",
    "turnover_rate",
    "amount_yuan",
    "dde_net_buy_yuan",
    "limitup_count",
    "member_count",
]
OPTIONAL_FIELDS = [
    "limitup_ratio",
    "sector_code",
    "main_net_inflow_yuan",
    "rank",
    "source",
]
COLUMN_ALIASES = {
    "板块名称": "sector_name",
    "概念名称": "sector_name",
    "名称": "sector_name",
    "涨跌幅": "pct",
    "涨幅": "pct",
    "换手率": "turnover_rate",
    "成交额": "amount_yuan",
    "DDE净额": "dde_net_buy_yuan",
    "DDE大单净额": "dde_net_buy_yuan",
    "主力净流入": "main_net_inflow_yuan",
    "涨停家数": "limitup_count",
    "涨停股票数量": "limitup_count",
    "成分股数量": "member_count",
    "股票数": "member_count",
}


def _csv_meta(path: Path) -> dict:
    if not path.exists():
        return {
            "exists": False,
            "rows": 0,
            "columns": [],
            "warnings": ["raw_file_missing"],
        }
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            columns = [str(item).strip() for item in next(reader, [])]
            rows = sum(1 for _ in reader)
        return {
            "exists": True,
            "rows": rows,
            "columns": columns,
            "warnings": [],
        }
    except Exception as exc:
        return {
            "exists": True,
            "rows": 0,
            "columns": [],
            "warnings": ["raw_file_read_error"],
            "read_error": str(exc),
        }


def suggested_column_mapping(columns: list[str]) -> dict:
    mapping = {}
    for column in columns:
        if column in REQUIRED_FIELDS or column in OPTIONAL_FIELDS:
            continue
        target = COLUMN_ALIASES.get(column)
        if target:
            mapping[column] = target
    return mapping


def validate_export(date: str, raw_file: str | Path) -> dict:
    path = Path(raw_file)
    meta = _csv_meta(path)
    columns = meta.get("columns", [])
    present = set(columns)
    missing = [field for field in REQUIRED_FIELDS if field not in present]
    optional_present = [field for field in OPTIONAL_FIELDS if field in present]
    mapping = suggested_column_mapping(columns)
    ready = bool(meta.get("exists")) and not missing
    warnings = list(meta.get("warnings", []))
    if missing:
        warnings.append("required_fields_missing")
    if mapping:
        warnings.append("column_alias_mapping_suggested")
    conclusion = [
        "do_not_fabricate_raw",
        "do_not_fabricate_snapshot",
        "keep_cp_rules_unchanged",
        "dry_run_only",
    ]
    if ready:
        conclusion.append("sector_only_ready_candidate")
    else:
        conclusion.append("sector_only_blocked")
    return {
        "date": str(date),
        "raw_file": str(path),
        "exists": bool(meta.get("exists")),
        "rows": meta.get("rows", 0),
        "columns": columns,
        "required_fields": REQUIRED_FIELDS,
        "required_fields_missing": missing,
        "optional_fields_present": optional_present,
        "suggested_column_mapping": mapping,
        "sector_only_ready_candidate": ready,
        "sector_only_blocked": not ready,
        "warnings": sorted(set(warnings)),
        "conclusion": conclusion,
    }


def write_outputs(payload: dict) -> tuple[Path, Path]:
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    date = payload["date"]
    json_path = EVAL_ROOT / f"sector_strength_raw_export_dry_run_{date}.json"
    md_path = EVAL_ROOT / f"sector_strength_raw_export_dry_run_{date}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def _render_markdown(payload: dict) -> str:
    lines = [
        f"# Sector Strength Raw Export Dry Run {payload['date']}",
        "",
        f"- raw_file: `{payload['raw_file']}`",
        f"- exists: `{payload['exists']}`",
        f"- rows: `{payload['rows']}`",
        f"- sector_only_ready_candidate: `{payload['sector_only_ready_candidate']}`",
        f"- sector_only_blocked: `{payload['sector_only_blocked']}`",
        f"- required_fields_missing: `{payload['required_fields_missing']}`",
        f"- suggested_column_mapping: `{payload['suggested_column_mapping']}`",
        f"- warnings: `{payload['warnings']}`",
        f"- conclusion: `{payload['conclusion']}`",
    ]
    return "\n".join(lines) + "\n"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Dry-run validate an iFind sector-strength raw export.")
    parser.add_argument("--date", default="TEMPLATE")
    parser.add_argument("--file", default="")
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    configure_utf8_console()
    args = parse_args(argv)
    raw_file = TEMPLATE_PATH if args.template else args.file
    if not raw_file:
        raise ValueError("Provide --file PATH or use --template")
    payload = validate_export(args.date, raw_file)
    if args.no_write:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    json_path, md_path = write_outputs(payload)
    print(json.dumps({"json": str(json_path), "md": str(md_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
