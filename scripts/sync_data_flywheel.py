"""Build provider-aware sync manifests from verified on-disk artifacts.

This tool does not contact a vendor by default. A completed function call is never
treated as a successful sync unless the expected cache files can be verified.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _row_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return max(sum(1 for _ in csv.reader(handle)) - 1, 0)
    except Exception:
        return 0


def inspect_date(
    date: str,
    store_root: Path,
    provider: str = "local_cache",
    fetch_returned=None,
    attempted: bool = False,
    provider_blocked: bool = False,
    sector_evidence_available: bool = False,
) -> dict:
    date = str(date)
    date_dir = Path(store_root) / date
    stocks_path = date_dir / "stocks.csv"
    indices_path = date_dir / "indices.csv"
    stocks_meta = _read_json(date_dir / "stocks.meta.json")
    indices_meta = _read_json(date_dir / "indices.meta.json")
    stocks_count = _row_count(stocks_path)
    indices_count = _row_count(indices_path)
    states = {
        str(stocks_meta.get("session_state", "") or ""),
        str(indices_meta.get("session_state", "") or ""),
    }
    states.discard("")
    session_state = states.pop() if len(states) == 1 else ("mixed" if states else "missing")
    complete = stocks_count > 0 and indices_count > 0 and session_state == "closed"
    partial = stocks_count > 0 or indices_count > 0

    if complete:
        sync_status = "skipped_existing_complete" if not attempted else "complete_candidate_daily"
        validation_level = "candidate_close"
    elif sector_evidence_available:
        sync_status = "sector_only"
        validation_level = "sector_only"
    elif provider_blocked:
        sync_status = "provider_blocked"
        validation_level = "missing"
    elif partial:
        sync_status = "partial_daily"
        validation_level = "missing"
    else:
        sync_status = "missing"
        validation_level = "missing"

    missing = []
    if not stocks_path.exists():
        missing.append("stocks.csv")
    if not indices_path.exists():
        missing.append("indices.csv")
    if session_state != "closed":
        missing.append("closed_session_state")
    return {
        "date": date,
        "provider": provider,
        "planned": True,
        "attempted": bool(attempted),
        "cache_complete_before": complete if not attempted else None,
        "stocks_exists": stocks_path.exists(),
        "indices_exists": indices_path.exists(),
        "stocks_row_count": stocks_count,
        "indices_row_count": indices_count,
        "session_state": session_state,
        "fetch_returned": fetch_returned,
        "cache_complete_after": complete,
        "sync_status": sync_status,
        "validation_level": validation_level,
        "missing_fields": missing,
        "error_type": "provider_login_blocked" if provider_blocked and not complete else "",
        "sanitized_error": "online_provider_unavailable" if provider_blocked and not complete else "",
    }


def build_manifest(dates, store_root, sector_only_dates=None, provider_blocked_dates=None):
    sector_only = {str(value) for value in sector_only_dates or []}
    blocked = {str(value) for value in provider_blocked_dates or []}
    records = [
        inspect_date(
            date,
            Path(store_root),
            provider=(
                "local_cache"
                if str(date) not in blocked and str(date) not in sector_only
                else ("ifind_mcp" if str(date) in sector_only else "amazingdata")
            ),
            provider_blocked=str(date) in blocked,
            sector_evidence_available=str(date) in sector_only,
        )
        for date in dates
    ]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "observation_only": True,
        "records": records,
        "summary": {
            status: sum(row["sync_status"] == status for row in records)
            for status in (
                "complete_candidate_daily",
                "skipped_existing_complete",
                "partial_daily",
                "provider_blocked",
                "sector_only",
                "missing",
            )
        },
    }


def _format_markdown(payload):
    lines = [
        "# Data Flywheel Availability",
        "",
        "Function completion is not treated as sync success. Candidate validation requires closed stocks and indices caches.",
        "",
        "| date | provider | status | validation | stocks | indices | state | missing |",
        "|---|---|---|---|---:|---:|---|---|",
    ]
    for row in payload["records"]:
        lines.append(
            f"| {row['date']} | {row['provider']} | {row['sync_status']} | {row['validation_level']} | "
            f"{row['stocks_row_count']} | {row['indices_row_count']} | {row['session_state']} | "
            f"{', '.join(row['missing_fields']) or '-'} |"
        )
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dates", required=True, help="Comma-separated YYYYMMDD values")
    parser.add_argument("--store-root", default="AmazingData_Store")
    parser.add_argument("--sector-only-dates", default="")
    parser.add_argument("--provider-blocked-dates", default="")
    parser.add_argument("--output-json")
    parser.add_argument("--output-md")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    split = lambda value: [item.strip() for item in value.split(",") if item.strip()]
    payload = build_manifest(
        split(args.dates),
        args.store_root,
        sector_only_dates=split(args.sector_only_dates),
        provider_blocked_dates=split(args.provider_blocked_dates),
    )
    if args.dry_run:
        print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
        return payload
    if args.output_json:
        path = Path(args.output_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.output_md:
        path = Path(args.output_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_format_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    main()
