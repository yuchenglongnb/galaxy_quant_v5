# -*- coding: utf-8 -*-
"""Build timepoint-specific 09:35 feedback artifacts.

This script is analysis-only. It reads daily validation candidates and local
intraday confirmation files, then writes standardized 09:35 feedback artifacts.
It does not log in to data vendors, run sync/rebuild/backfill, write lessons,
patterns, registries, evaluator/config/strategy files, or issue trading advice.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VALIDATION_ROOT = ROOT / "reports" / "validation" / "daily"
DEFAULT_STORE_ROOT = ROOT / "AmazingData_Store"
DEFAULT_OUTPUT_FILENAME = "stock_confirmation_0935.csv"
DEFAULT_META_FILENAME = "stock_confirmation_0935_meta.json"


OUTPUT_FIELDS = [
    "date",
    "code",
    "name",
    "target_type",
    "source_signal_category",
    "source_signal_family",
    "timepoint",
    "time_int",
    "time_str",
    "pre_close",
    "open",
    "last",
    "pct",
    "price_vs_open_pct",
    "amount_1m_ratio",
    "rs_vs_index_pct",
    "rs_vs_etf_pct",
    "volume_price_state",
    "benchmark_code",
    "benchmark_name",
    "benchmark_source",
    "data_source",
    "collection_mode",
    "data_available",
    "missing_reason",
]


def _repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in OUTPUT_FIELDS})


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _index_confirmation(rows: list[dict]) -> tuple[dict[str, dict], dict[str, dict]]:
    by_code = {}
    by_name = {}
    for row in rows:
        code = str(row.get("code", "") or "").strip()
        name = str(row.get("name", "") or "").strip()
        if code:
            by_code[code] = row
        if name:
            by_name[name] = row
    return by_code, by_name


def _candidate_source(date: str, validation_root: Path, explicit: str = "") -> Path:
    if explicit:
        return Path(explicit)
    return validation_root / str(date) / "signal_detail.csv"


def _existing_confirmation_path(date: str, store_root: Path) -> Path:
    base = store_root / str(date) / "intraday"
    preferred = base / DEFAULT_OUTPUT_FILENAME
    if preferred.exists():
        return preferred
    return base / "stock_confirmation_latest.csv"


def _standardize_row(date: str, candidate: dict, confirmation: dict | None, mode: str) -> dict:
    code = str(candidate.get("code", "") or "").strip()
    name = str(candidate.get("name", "") or "").strip()
    if confirmation:
        code = code or str(confirmation.get("code", "") or "").strip()
        name = name or str(confirmation.get("name", "") or "").strip()
    available = confirmation is not None
    return {
        "date": date,
        "code": code,
        "name": name,
        "target_type": candidate.get("target_type", ""),
        "source_signal_category": candidate.get("signal_category", "") or candidate.get("category", ""),
        "source_signal_family": candidate.get("signal_family", ""),
        "timepoint": "0935",
        "time_int": confirmation.get("time_int", "935") if confirmation else "935",
        "time_str": confirmation.get("time_str", "09:35:00") if confirmation else "09:35:00",
        "pre_close": confirmation.get("pre_close", "") if confirmation else "",
        "open": confirmation.get("open", "") if confirmation else "",
        "last": confirmation.get("last", "") if confirmation else "",
        "pct": confirmation.get("pct", "") if confirmation else "",
        "price_vs_open_pct": confirmation.get("price_vs_open_pct", "") if confirmation else "",
        "amount_1m_ratio": confirmation.get("amount_1m_ratio", "") if confirmation else "",
        "rs_vs_index_pct": confirmation.get("rs_vs_index_pct", "") if confirmation else "",
        "rs_vs_etf_pct": confirmation.get("rs_vs_etf_pct", "") if confirmation else "",
        "volume_price_state": confirmation.get("volume_price_state", "") if confirmation else "",
        "benchmark_code": confirmation.get("benchmark_etf_code", "") or confirmation.get("benchmark_index_code", "") if confirmation else "",
        "benchmark_name": confirmation.get("board_index_name", "") if confirmation else "",
        "benchmark_source": confirmation.get("benchmark_source", "") if confirmation else "",
        "data_source": "local_existing_confirmation" if confirmation else "",
        "collection_mode": mode,
        "data_available": str(available),
        "missing_reason": "" if available else "missing_local_confirmation_match",
    }


def collect_for_date(
    date: str,
    validation_root: Path = DEFAULT_VALIDATION_ROOT,
    store_root: Path = DEFAULT_STORE_ROOT,
    mode: str = "local-existing-confirmation",
    candidate_source: str = "",
    output_filename: str = DEFAULT_OUTPUT_FILENAME,
    write_latest_copy: bool = False,
    dry_run: bool = False,
) -> dict:
    if mode not in {"local-existing-confirmation", "gap-only"}:
        return {
            "date": str(date),
            "status": "unsupported_offline_mode",
            "mode": mode,
            "message": "Online AmazingData query/subscription modes are intentionally not executed by this hook.",
        }
    date = str(date)
    candidate_path = _candidate_source(date, validation_root, candidate_source)
    confirmation_path = _existing_confirmation_path(date, store_root)
    candidates = _read_csv(candidate_path)
    confirmations = [] if mode == "gap-only" else _read_csv(confirmation_path)
    by_code, by_name = _index_confirmation(confirmations)
    rows = []
    matched = 0
    for candidate in candidates:
        code = str(candidate.get("code", "") or "").strip()
        name = str(candidate.get("name", "") or "").strip()
        match = by_code.get(code) if code else None
        match = match or (by_name.get(name) if name else None)
        if match:
            matched += 1
        rows.append(_standardize_row(date, candidate, match, mode))

    output_dir = store_root / date / "intraday"
    output_path = output_dir / output_filename
    meta_path = output_dir / DEFAULT_META_FILENAME
    meta = {
        "date": date,
        "target_timepoint": "0935",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_source": _repo_path(candidate_path),
        "candidate_count": len(candidates),
        "matched_count": matched,
        "missing_count": max(len(candidates) - matched, 0),
        "data_source": _repo_path(confirmation_path) if confirmation_path.exists() and mode != "gap-only" else "",
        "collection_mode": mode,
        "query_window": "09:30-09:35",
        "timepoint_policy": "min1_0935_bar",
        "notes": [
            "standardized_offline_artifact",
            "5min_0935_bar_not_used_as_strict_point_value",
            "labels_are_feedback_evidence_not_trading_instructions",
        ],
        "output_csv": _repo_path(output_path),
        "output_meta": _repo_path(meta_path),
    }
    if not dry_run:
        _write_csv(output_path, rows)
        _write_json(meta_path, meta)
        if write_latest_copy:
            shutil.copyfile(output_path, output_dir / "stock_confirmation_latest.csv")
    return {
        "date": date,
        "dry_run": dry_run,
        "candidate_source": _repo_path(candidate_path),
        "confirmation_source": _repo_path(confirmation_path) if confirmation_path.exists() else "",
        "output_csv": _repo_path(output_path),
        "output_meta": _repo_path(meta_path),
        "candidate_count": len(candidates),
        "matched_count": matched,
        "missing_count": meta["missing_count"],
        "collection_mode": mode,
        "would_write": not dry_run,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Collect standardized 09:35 feedback artifacts from local sources.")
    parser.add_argument("--date", default="")
    parser.add_argument("--dates", default="")
    parser.add_argument("--candidate-source", default="")
    parser.add_argument("--validation-root", default=str(DEFAULT_VALIDATION_ROOT))
    parser.add_argument("--store-root", default=str(DEFAULT_STORE_ROOT))
    parser.add_argument("--mode", default="local-existing-confirmation")
    parser.add_argument("--target-timepoint", default="0935")
    parser.add_argument("--output-filename", default=DEFAULT_OUTPUT_FILENAME)
    parser.add_argument("--write-latest-copy", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    dates = [date.strip() for date in args.dates.split(",") if date.strip()]
    if args.date:
        dates.append(args.date.strip())
    if not dates:
        raise SystemExit("At least one --date or --dates value is required.")
    results = [
        collect_for_date(
            date=date,
            validation_root=Path(args.validation_root),
            store_root=Path(args.store_root),
            mode=args.mode,
            candidate_source=args.candidate_source if len(dates) == 1 else "",
            output_filename=args.output_filename,
            write_latest_copy=args.write_latest_copy,
            dry_run=args.dry_run,
        )
        for date in dates
    ]
    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
    return results


if __name__ == "__main__":
    main()
