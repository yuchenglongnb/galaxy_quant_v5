# -*- coding: utf-8 -*-
"""Dry-run repair helper for malformed T+1 backtest validation CSV input."""

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

from utils.encoding import configure_utf8_console  # noqa: E402


VALIDATION_PATH = ROOT / "reports" / "validation" / "auction_signal_validation.csv"
EVAL_ROOT = ROOT / "reports" / "analysis" / "evaluations"


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def scan_and_optionally_repair(path: Path, dry_run: bool = True) -> dict:
    clean_rows = []
    bad_rows = []
    header = []
    if path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            header = next(reader, [])
            expected = len(header)
            for line_no, row in enumerate(reader, start=2):
                if len(row) == expected:
                    clean_rows.append(row)
                else:
                    bad_rows.append(
                        {
                            "line": line_no,
                            "expected_fields": expected,
                            "actual_fields": len(row),
                            "sample": row[:8],
                        }
                    )
    else:
        expected = 0
    stem = "t1backtest_input_integrity_repair"
    repaired_path = EVAL_ROOT / f"{stem}_clean_temp.csv"
    quarantine_path = EVAL_ROOT / f"{stem}_bad_rows.json"
    repair_success = False
    if not dry_run:
        EVAL_ROOT.mkdir(parents=True, exist_ok=True)
        with repaired_path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows(clean_rows)
        quarantine_path.write_text(json.dumps(bad_rows, ensure_ascii=False, indent=2), encoding="utf-8")
        repair_success = True
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_file": _display_path(path) if path.exists() else str(path),
        "dry_run": dry_run,
        "expected_fields": expected,
        "clean_row_count": len(clean_rows),
        "bad_row_count": len(bad_rows),
        "bad_rows": bad_rows,
        "original_overwritten": False,
        "repair_attempted": not dry_run,
        "repair_success": repair_success,
        "repaired_temp_copy": str(repaired_path.relative_to(ROOT)) if repair_success else "",
        "quarantine_path": str(quarantine_path.relative_to(ROOT)) if repair_success else "",
        "conclusion": [
            "dry_run_only" if dry_run else "temp_repaired_copy_created",
            "original_csv_not_overwritten",
            "bad_rows_quarantined" if repair_success else "bad_rows_quarantine_available_on_non_dry_run",
        ],
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Dry-run malformed T+1 input repair.")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--write-temp", action="store_true", help="Write clean temp copy and bad-row quarantine.")
    return parser.parse_args(argv)


def main(argv=None):
    configure_utf8_console()
    args = parse_args(argv)
    payload = scan_and_optionally_repair(VALIDATION_PATH, dry_run=not args.write_temp)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
