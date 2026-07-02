# -*- coding: utf-8 -*-
"""Stage exported iFind market-structure raw files into the dated raw folder."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_ifind_raw_readiness import build_payload  # noqa: E402
from utils.encoding import configure_utf8_console  # noqa: E402


RAW_TARGETS = {
    "sector_raw": "sector_strength_raw.csv",
    "theme_raw": "theme_limitup_raw.csv",
    "limitup_raw": "limitup_ladder_raw.csv",
}


def raw_dir(date: str) -> Path:
    return ROOT / "AmazingData_Store" / str(date) / "ifind" / "raw"


def _copy_if_provided(source: str | None, target: Path) -> dict:
    if not source:
        return {"provided": False, "copied": False, "target": str(target)}
    source_path = Path(source)
    if not source_path.exists():
        return {
            "provided": True,
            "copied": False,
            "source": str(source_path),
            "target": str(target),
            "warning": "source_file_missing",
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target)
    return {
        "provided": True,
        "copied": True,
        "source": str(source_path),
        "target": str(target),
    }


def capture_raw_files(
    date: str,
    sector_raw: str | None = None,
    theme_raw: str | None = None,
    limitup_raw: str | None = None,
    source: str = "manual_export",
) -> dict:
    """Copy explicitly supplied raw exports and refresh the raw manifest."""
    out_dir = raw_dir(date)
    copied = {
        key: _copy_if_provided(path, out_dir / filename)
        for key, path, filename in [
            ("sector_raw", sector_raw, RAW_TARGETS["sector_raw"]),
            ("theme_raw", theme_raw, RAW_TARGETS["theme_raw"]),
            ("limitup_raw", limitup_raw, RAW_TARGETS["limitup_raw"]),
        ]
    }
    readiness_payload = build_payload([str(date)], source=source, write_manifest_files=True)
    warnings = [
        value["warning"]
        for value in copied.values()
        if value.get("warning")
    ]
    warnings.extend(readiness_payload.get("warnings", []))
    return {
        "date": str(date),
        "raw_dir": str(out_dir),
        "copied_files": copied,
        "readiness": readiness_payload["readiness_by_date"].get(str(date), "missing"),
        "manifest_path": readiness_payload.get("manifest_paths", {}).get(str(date), ""),
        "raw_readiness_payload": readiness_payload,
        "warnings": sorted(set(warnings)),
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Stage iFind market-structure raw files and update manifest.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--sector-raw", default="")
    parser.add_argument("--theme-raw", default="")
    parser.add_argument("--limitup-raw", default="")
    parser.add_argument("--source", default="manual_export")
    return parser.parse_args(argv)


def main(argv=None):
    configure_utf8_console()
    args = parse_args(argv)
    payload = capture_raw_files(
        args.date,
        sector_raw=args.sector_raw or None,
        theme_raw=args.theme_raw or None,
        limitup_raw=args.limitup_raw or None,
        source=args.source,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
