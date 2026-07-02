# -*- coding: utf-8 -*-
"""Check iFind market-structure raw files and write readiness manifests."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.encoding import configure_utf8_console  # noqa: E402


EVAL_ROOT = ROOT / "reports" / "analysis" / "evaluations"
RAW_FILENAMES = {
    "sector": "sector_strength_raw.csv",
    "theme": "theme_limitup_raw.csv",
    "ladder": "limitup_ladder_raw.csv",
}
REQUIRED_FIELDS = {
    "sector_strength_raw.csv": {
        "sector_name",
        "pct",
        "turnover_rate",
        "amount_yuan",
        "dde_net_buy_yuan",
        "limitup_count",
        "member_count",
    },
    "theme_limitup_raw.csv": {
        "theme_name",
        "limitup_count",
        "second_board_count",
        "third_board_count",
        "highest_board",
    },
    "limitup_ladder_raw.csv": {
        "code",
        "name",
        "board_count",
        "theme",
        "group",
        "limitup_time",
    },
}


def _resolve_dates(args) -> list[str]:
    if args.dates:
        return [item.strip() for item in args.dates.split(",") if item.strip()]
    if args.date:
        return [args.date.strip()]
    start = datetime.strptime(args.start_date, "%Y%m%d").date()
    end = datetime.strptime(args.end_date, "%Y%m%d").date()
    dates = []
    cursor = start
    while cursor <= end:
        dates.append(cursor.strftime("%Y%m%d"))
        cursor += timedelta(days=1)
    return dates


def _raw_dir(date: str) -> Path:
    return ROOT / "AmazingData_Store" / str(date) / "ifind" / "raw"


def _csv_meta(path: Path, required_fields: set[str]) -> dict:
    if not path.exists():
        return {
            "exists": False,
            "rows": 0,
            "columns": [],
            "required_fields_missing": sorted(required_fields),
            "missing_reason": "not_available",
        }
    columns = []
    rows = 0
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            columns = [str(item) for item in next(reader, [])]
            rows = sum(1 for _ in reader)
    except Exception as exc:
        return {
            "exists": True,
            "rows": 0,
            "columns": columns,
            "required_fields_missing": sorted(required_fields),
            "read_error": str(exc),
            "missing_reason": "read_error",
        }
    missing = sorted(required_fields - set(columns))
    return {
        "exists": True,
        "rows": rows,
        "columns": columns,
        "required_fields_missing": missing,
    }


def _readiness(files: dict) -> str:
    sector_ready = files["sector_strength_raw.csv"].get("exists") and not files["sector_strength_raw.csv"].get("required_fields_missing")
    theme_ready = files["theme_limitup_raw.csv"].get("exists") and not files["theme_limitup_raw.csv"].get("required_fields_missing")
    ladder_ready = files["limitup_ladder_raw.csv"].get("exists") and not files["limitup_ladder_raw.csv"].get("required_fields_missing")
    if sector_ready and theme_ready and ladder_ready:
        return "full_ready"
    if sector_ready:
        return "sector_only"
    if theme_ready:
        return "theme_only"
    if ladder_ready:
        return "ladder_only"
    return "missing"


def build_manifest(date: str, source: str = "manual_export") -> dict:
    raw_dir = _raw_dir(date)
    files = {}
    for filename, required in REQUIRED_FIELDS.items():
        files[filename] = _csv_meta(raw_dir / filename, required)
        files[filename]["schema_version"] = "v1"
    readiness = _readiness(files)
    warnings = []
    for filename, meta in files.items():
        if not meta.get("exists"):
            warnings.append(f"{filename}:missing")
        elif meta.get("required_fields_missing"):
            warnings.append(f"{filename}:required_fields_missing")
    return {
        "date": str(date),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "schema_version": "v1",
        "raw_dir": str(raw_dir),
        "files": files,
        "readiness": readiness,
        "warnings": warnings,
    }


def write_manifest(manifest: dict) -> Path:
    raw_dir = Path(manifest["raw_dir"])
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / "raw_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_payload(date_list: list[str], source: str = "manual_export", write_manifest_files: bool = True) -> dict:
    manifests = {}
    manifest_paths = {}
    for date in date_list:
        manifest = build_manifest(date, source=source)
        manifests[date] = manifest
        if write_manifest_files:
            manifest_paths[date] = str(write_manifest(manifest))
    readiness_by_date = {date: manifest["readiness"] for date, manifest in manifests.items()}
    file_status_by_date = {date: manifest["files"] for date, manifest in manifests.items()}
    missing_raw_by_date = {
        date: [
            filename
            for filename, meta in manifest["files"].items()
            if not meta.get("exists")
        ]
        for date, manifest in manifests.items()
    }
    required_fields_missing_by_date = {
        date: {
            filename: meta.get("required_fields_missing", [])
            for filename, meta in manifest["files"].items()
            if meta.get("required_fields_missing")
        }
        for date, manifest in manifests.items()
    }
    full_ready = [date for date, status in readiness_by_date.items() if status == "full_ready"]
    sector_only = [date for date, status in readiness_by_date.items() if status == "sector_only"]
    missing = [date for date, status in readiness_by_date.items() if status == "missing"]
    warnings = sorted({warning for manifest in manifests.values() for warning in manifest.get("warnings", [])})
    return {
        "dates": date_list,
        "readiness_by_date": readiness_by_date,
        "file_status_by_date": file_status_by_date,
        "missing_raw_by_date": missing_raw_by_date,
        "required_fields_missing_by_date": required_fields_missing_by_date,
        "sector_only_ready_dates": sector_only,
        "full_ready_dates": full_ready,
        "missing_dates": missing,
        "manifest_paths": manifest_paths,
        "recommended_actions": _recommended_actions(readiness_by_date, required_fields_missing_by_date),
        "conclusion": [
            "do_not_fabricate_snapshot",
            "keep_cp_rules_unchanged",
        ],
        "warnings": warnings,
    }


def _recommended_actions(readiness_by_date: dict, missing_fields: dict) -> list[str]:
    actions = []
    if any(status == "missing" for status in readiness_by_date.values()):
        actions.append("collect_ifind_raw_exports")
    if any(status == "sector_only" for status in readiness_by_date.values()):
        actions.append("allow_sector_only_snapshot_rebuild")
    if any(fields for fields in missing_fields.values()):
        actions.append("fix_raw_schema_fields")
    if any(status == "full_ready" for status in readiness_by_date.values()):
        actions.append("ready_for_market_structure_snapshot_rebuild")
    if not actions:
        actions.append("no_action")
    return actions


def write_outputs(payload: dict) -> tuple[Path, Path]:
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    start = min(payload["dates"]) if payload["dates"] else ""
    end = max(payload["dates"]) if payload["dates"] else ""
    suffix = start if start == end else f"{start}_{end}"
    json_path = EVAL_ROOT / f"ifind_raw_readiness_{suffix}.json"
    md_path = EVAL_ROOT / f"ifind_raw_readiness_{suffix}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def _render_markdown(payload: dict) -> str:
    lines = [
        "# iFind Raw Readiness",
        "",
        f"- dates: `{payload['dates']}`",
        f"- full_ready_dates: `{payload['full_ready_dates']}`",
        f"- sector_only_ready_dates: `{payload['sector_only_ready_dates']}`",
        f"- missing_dates: `{payload['missing_dates']}`",
        f"- recommended_actions: `{payload['recommended_actions']}`",
        f"- conclusion: `{payload['conclusion']}`",
        "",
        "## Readiness By Date",
        "",
    ]
    for date, status in payload["readiness_by_date"].items():
        lines.append(f"- {date}: `{status}`")
    lines.extend(["", "## Required Fields Missing", ""])
    for date, fields in payload["required_fields_missing_by_date"].items():
        lines.append(f"- {date}: `{fields}`")
    return "\n".join(lines) + "\n"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate iFind market-structure raw readiness.")
    parser.add_argument("--date", default="")
    parser.add_argument("--dates", default="")
    parser.add_argument("--start-date", default="")
    parser.add_argument("--end-date", default="")
    parser.add_argument("--source", default="manual_export")
    parser.add_argument("--no-write-manifest", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    configure_utf8_console()
    args = parse_args(argv)
    if not args.date and not args.dates and not (args.start_date and args.end_date):
        raise ValueError("Provide --date, --dates, or --start-date/--end-date")
    payload = build_payload(
        _resolve_dates(args),
        source=args.source,
        write_manifest_files=not args.no_write_manifest,
    )
    json_path, md_path = write_outputs(payload)
    print(json.dumps({"json": str(json_path), "md": str(md_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
