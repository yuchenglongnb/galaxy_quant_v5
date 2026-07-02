# -*- coding: utf-8 -*-
"""Quarantine malformed rows from the global T+1 validation CSV."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_t1backtest_input_integrity import classify_bad_row  # noqa: E402
from utils.encoding import configure_utf8_console  # noqa: E402


DEFAULT_INPUT = ROOT / "reports" / "validation" / "auction_signal_validation.csv"
EVAL_ROOT = ROOT / "reports" / "analysis" / "evaluations"
QUARANTINE_ROOT = ROOT / "reports" / "validation" / "quarantine"


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def scan_bad_rows(path: Path) -> tuple[list[str], list[list[str]], list[dict], int]:
    header: list[str] = []
    clean_rows: list[list[str]] = []
    bad_rows: list[dict] = []
    if not path.exists():
        return header, clean_rows, bad_rows, 0
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, [])
        expected = len(header)
        for line_number, row in enumerate(reader, start=2):
            if len(row) == expected:
                clean_rows.append(row)
                continue
            bad_rows.append(
                {
                    "line_number": line_number,
                    "expected_fields": expected,
                    "actual_fields": len(row),
                    "raw_preview": ",".join(row[:8]),
                    "suspected_root_cause": classify_bad_row(expected, len(row)),
                }
            )
    return header, clean_rows, bad_rows, len(header)


def build_payload(input_file: Path, dry_run: bool = True, write_temp_copy: bool = False) -> dict:
    header, clean_rows, bad_rows, expected_fields = scan_bad_rows(input_file)
    clean_path = QUARANTINE_ROOT / "auction_signal_validation.clean.csv"
    bad_rows_path = QUARANTINE_ROOT / "auction_signal_validation.bad_rows.csv"
    wrote_clean = False
    wrote_bad = False
    if write_temp_copy and not dry_run:
        QUARANTINE_ROOT.mkdir(parents=True, exist_ok=True)
        with clean_path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows(clean_rows)
        with bad_rows_path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "line_number",
                    "expected_fields",
                    "actual_fields",
                    "raw_preview",
                    "suspected_root_cause",
                ],
            )
            writer.writeheader()
            writer.writerows(bad_rows)
        wrote_clean = True
        wrote_bad = True
    conclusions = [
        "bad_csv_quarantine_required" if bad_rows else "bad_csv_clean",
        "original_file_not_modified",
        "no_strategy_rule_change",
        "cp_evaluator_change_not_required",
        "trend_evaluator_change_not_required",
        "lesson_pattern_not_written",
    ]
    if dry_run:
        conclusions.append("dry_run_only")
    elif wrote_clean:
        conclusions.append("clean_temp_copy_written")
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "input_file": _display_path(input_file),
        "malformed_row_count": len(bad_rows),
        "bad_rows": bad_rows,
        "clean_row_count": len(clean_rows),
        "expected_fields": expected_fields,
        "quarantine_recommended": bool(bad_rows),
        "dry_run": dry_run,
        "original_file_modified": False,
        "clean_temp_copy_written": wrote_clean,
        "bad_rows_file_written": wrote_bad,
        "planned_clean_temp_copy": _display_path(clean_path),
        "planned_bad_rows_file": _display_path(bad_rows_path),
        "recommended_next_actions": [
            "review_bad_rows_file_before_any_repair",
            "use_clean_temp_copy_for_diagnostics_only",
            "keep_original_validation_csv_unchanged",
        ],
        "warnings": ["original_csv_not_overwritten"],
        "conclusion": conclusions,
    }


def write_reports(payload: dict) -> tuple[Path, Path]:
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = EVAL_ROOT / "t1backtest_bad_row_quarantine.json"
    md_path = EVAL_ROOT / "t1backtest_bad_row_quarantine.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def render_markdown(payload: dict) -> str:
    lines = [
        "# T+1 Backtest Bad Row Quarantine",
        "",
        f"- input_file: `{payload['input_file']}`",
        f"- malformed_row_count: `{payload['malformed_row_count']}`",
        f"- clean_row_count: `{payload['clean_row_count']}`",
        f"- dry_run: `{payload['dry_run']}`",
        f"- original_file_modified: `{payload['original_file_modified']}`",
        "",
        "## Bad Rows",
        "",
    ]
    for row in payload["bad_rows"]:
        lines.append(
            f"- line {row['line_number']}: expected {row['expected_fields']}, "
            f"actual {row['actual_fields']}, cause `{row['suspected_root_cause']}`"
        )
    lines.extend(["", "## Conclusion", ""])
    lines.extend(f"- {item}" for item in payload["conclusion"])
    return "\n".join(lines) + "\n"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Quarantine malformed T+1 backtest validation rows.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--write-temp-copy", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    configure_utf8_console()
    args = parse_args(argv)
    input_file = Path(args.input)
    if not input_file.is_absolute():
        input_file = ROOT / input_file
    dry_run = not args.write_temp_copy
    payload = build_payload(input_file, dry_run=dry_run, write_temp_copy=args.write_temp_copy)
    json_path, md_path = write_reports(payload)
    print(
        json.dumps(
            {
                "json": _display_path(json_path),
                "md": _display_path(md_path),
                "malformed_row_count": payload["malformed_row_count"],
                "clean_temp_copy_written": payload["clean_temp_copy_written"],
                "original_file_modified": payload["original_file_modified"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
