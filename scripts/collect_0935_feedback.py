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
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_VALIDATION_ROOT = ROOT / "reports" / "validation" / "daily"
DEFAULT_STORE_ROOT = ROOT / "AmazingData_Store"
DEFAULT_OUTPUT_FILENAME = "stock_confirmation_0935.csv"
DEFAULT_META_FILENAME = "stock_confirmation_0935_meta.json"
WORKER_SCRIPT = ROOT / "scripts" / "amazing_0935_query_worker.py"
JSON_BEGIN = "__AMAZING_0935_JSON_BEGIN__"
JSON_END = "__AMAZING_0935_JSON_END__"
LOCAL_MODE = "local-existing-confirmation"
SNAPSHOT_MODE = "historical-snapshot-query"
MIN1_MODE = "historical-min1-kline"
GAP_MODE = "gap-only"
OFFLINE_MODES = {LOCAL_MODE, GAP_MODE}
ONLINE_MODES = {SNAPSHOT_MODE, MIN1_MODE}
ALL_MODES = OFFLINE_MODES | ONLINE_MODES


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


def _collection_confirmation_path(
    date: str,
    store_root: Path,
    source_confirmation_file: str = "",
    prefer_existing_0935_source: bool = False,
) -> Path:
    if source_confirmation_file:
        return Path(source_confirmation_file)
    base = store_root / str(date) / "intraday"
    latest = base / "stock_confirmation_latest.csv"
    if latest.exists():
        return latest
    if prefer_existing_0935_source:
        existing_0935 = base / DEFAULT_OUTPUT_FILENAME
        if existing_0935.exists():
            return existing_0935
    return latest


def _coalesce(row: dict, *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return ""


def _float(value) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except Exception:
        return None


def _pct(numerator, denominator) -> str:
    num = _float(numerator)
    den = _float(denominator)
    if num is None or den in (None, 0):
        return ""
    return f"{((num - den) / den) * 100:.4f}"


def _query_time_to_hhmmss(value: str | int | None, default: int = 93500) -> int:
    if value in (None, ""):
        return default
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if not digits:
        return default
    if len(digits) <= 4:
        digits = digits.zfill(4) + "00"
    elif len(digits) >= 12:
        digits = digits[-6:]
    elif len(digits) >= 8:
        digits = digits.zfill(9)[:6]
    else:
        digits = digits.zfill(6)[:6]
    try:
        return int(digits)
    except ValueError:
        return default


def _time_to_str(value) -> str:
    text = str(value or "").strip()
    if not text:
        return "09:35:00"
    if " " in text:
        text = text.split(" ")[-1]
    text = text.replace("T", " ").split(" ")[-1].split(".")[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 6:
        digits = digits[-6:]
        return f"{digits[0:2]}:{digits[2:4]}:{digits[4:6]}"
    return text


def _snapshot_result_rows(result, target_hhmmss: int, floor_hhmmss: int, ceil_hhmmss: int) -> list[dict]:
    from core.snapshot_utils import snapshot_rows_near_time

    return snapshot_rows_near_time(result, target_hhmmss, floor_hhmmss, ceil_hhmmss)


def _kline_result_rows(result) -> list[dict]:
    from core.snapshot_utils import iter_kline_frames

    rows = []
    for code, frame in iter_kline_frames(result):
        if frame is None or frame.empty:
            continue
        work = frame.copy()
        time_col = "kline_time" if "kline_time" in work.columns else "trade_time" if "trade_time" in work.columns else ""
        if time_col:
            try:
                import pandas as pd

                work[time_col] = pd.to_datetime(work[time_col], errors="coerce")
                work = work.dropna(subset=[time_col]).sort_values(time_col)
            except Exception:
                pass
        row = work.iloc[0].to_dict()
        row["code"] = str(row.get("code") or code)
        rows.append(row)
    return rows


def _load_amazing_market(amazing_local_config: str = ""):
    from core.amazing_login_client import build_login_invocation
    from core.amazing_login_config import load_login_config, sanitize_text
    from core.calendar_helper import CalendarHelper

    config = load_login_config(dotenv_path=Path(amazing_local_config) if amazing_local_config else None)
    if not config.get("ready"):
        raise RuntimeError("AmazingData credentials are not available in the current process.")
    try:
        import AmazingData as ad
    except BaseException as exc:
        raise RuntimeError(sanitize_text(str(exc), config)) from exc
    login_args, login_kwargs, _ = build_login_invocation(config, "keyword-int-port")
    try:
        ad.login(*login_args, **login_kwargs)
    except BaseException as exc:
        raise RuntimeError(sanitize_text(str(exc), config)) from exc
    calendar = CalendarHelper.generate_workday_calendar(days=60)
    return ad, config, ad.MarketData(calendar)


def _logout_amazing(ad_module, config: dict | None):
    if not ad_module or not config:
        return
    try:
        ad_module.logout(str(config.get("username", "")))
    except Exception:
        pass


def _query_historical_snapshot_rows(
    codes: list[str],
    date: str,
    query_window_start: str,
    query_window_end: str,
    amazing_local_config: str = "",
) -> list[dict]:
    ad_module = None
    config = None
    try:
        ad_module, config, market = _load_amazing_market(amazing_local_config)
        result = market.query_snapshot(
            codes,
            begin_date=int(date),
            end_date=int(date),
            begin_time=int(query_window_start),
            end_time=int(query_window_end),
        )
        return _snapshot_result_rows(
            result,
            target_hhmmss=_query_time_to_hhmmss("093500"),
            floor_hhmmss=_query_time_to_hhmmss(query_window_start),
            ceil_hhmmss=_query_time_to_hhmmss(query_window_end),
        )
    finally:
        _logout_amazing(ad_module, config)


def _query_historical_min1_rows(
    codes: list[str],
    date: str,
    amazing_local_config: str = "",
) -> list[dict]:
    ad_module = None
    config = None
    try:
        ad_module, config, market = _load_amazing_market(amazing_local_config)
        period = ad_module.constant.Period.min1.value
        result = market.query_kline(
            codes,
            begin_date=int(date),
            end_date=int(date),
            period=period,
            begin_time=935,
            end_time=935,
        )
        return _kline_result_rows(result)
    finally:
        _logout_amazing(ad_module, config)


def _normalize_query_rows(rows: list[dict], mode: str) -> list[dict]:
    normalized = []
    for row in rows:
        if mode == SNAPSHOT_MODE:
            last = _coalesce(row, "last", "last_price", "price", "close")
            open_price = _coalesce(row, "open", "open_price")
            time_value = _coalesce(row, "trade_time", "time", "datetime")
            data_source = "amazingdata_query_snapshot"
            policy = "strict_0935_snapshot"
        else:
            last = _coalesce(row, "close", "last", "price")
            open_price = _coalesce(row, "open")
            time_value = _coalesce(row, "kline_time", "trade_time", "time")
            data_source = "amazingdata_query_kline_min1"
            policy = "min1_0935_bar"
        normalized.append(
            {
                "code": _coalesce(row, "code", "symbol", "wind_code"),
                "name": _coalesce(row, "name", "sec_name", "security_name"),
                "time_int": str(_query_time_to_hhmmss(time_value)),
                "time_str": _time_to_str(time_value),
                "pre_close": _coalesce(row, "pre_close", "preclose", "prev_close"),
                "open": open_price,
                "last": last,
                "pct": _coalesce(row, "pct", "change_pct", "pct_chg"),
                "price_vs_open_pct": _coalesce(row, "price_vs_open_pct") or _pct(last, open_price),
                "amount_1m_ratio": _coalesce(row, "amount_1m_ratio", "amount_ratio"),
                "rs_vs_index_pct": _coalesce(row, "rs_vs_index_pct"),
                "rs_vs_etf_pct": _coalesce(row, "rs_vs_etf_pct"),
                "volume_price_state": _coalesce(row, "volume_price_state"),
                "benchmark_etf_code": _coalesce(row, "benchmark_etf_code"),
                "benchmark_index_code": _coalesce(row, "benchmark_index_code"),
                "board_index_name": _coalesce(row, "board_index_name", "benchmark_name"),
                "benchmark_source": _coalesce(row, "benchmark_source"),
                "_data_source": data_source,
                "_timepoint_policy": policy,
            }
        )
    return normalized


def _extract_framed_json(text: str) -> dict:
    raw = str(text or "")
    start = raw.rfind(JSON_BEGIN)
    end = raw.rfind(JSON_END)
    if start == -1 or end == -1 or end <= start:
        raise ValueError("structured_json_missing")
    body = raw[start + len(JSON_BEGIN) : end].strip()
    return json.loads(body)


def _run_query_worker(
    mode: str,
    date: str,
    codes: list[str],
    query_window_start: str,
    query_window_end: str,
    amazing_local_config: str,
    worker_python: str,
    worker_timeout: int,
) -> tuple[list[dict], list[str]]:
    python_exe = worker_python or sys.executable
    request = {
        "date": str(date),
        "codes": codes,
        "mode": mode,
        "query_window_start": int(query_window_start),
        "query_window_end": int(query_window_end),
        "amazing_local_config": amazing_local_config or "",
    }
    try:
        result = subprocess.run(
            [python_exe, str(WORKER_SCRIPT)],
            input=json.dumps(request, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=int(worker_timeout),
            cwd=str(ROOT),
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("worker_timeout")
    payload = _extract_framed_json(result.stdout)
    status = str(payload.get("status", ""))
    if status != "ok":
        raise RuntimeError(str(payload.get("sanitized_error") or status or "worker_query_failed"))
    warnings = [str(item) for item in payload.get("warnings", [])]
    return list(payload.get("rows", []) or []), warnings


def _standardize_row(date: str, candidate: dict, confirmation: dict | None, mode: str, data_source: str = "") -> dict:
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
        "data_source": data_source or confirmation.get("_data_source", "") if confirmation else "",
        "collection_mode": mode,
        "data_available": str(available),
        "missing_reason": "" if available else "missing_local_confirmation_match",
    }


def _collect_confirmation_rows(
    mode: str,
    date: str,
    candidates: list[dict],
    store_root: Path,
    source_confirmation_file: str,
    prefer_existing_0935_source: bool,
    allow_online_query: bool,
    query_window_start: str,
    query_window_end: str,
    amazing_local_config: str,
    query_backend: str,
    worker_python: str,
    worker_timeout: int,
) -> tuple[list[dict], str, str, str, list[str]]:
    notes = []
    if mode == GAP_MODE:
        return [], "", "gap_only", "gap_only", notes
    if mode == LOCAL_MODE:
        path = _collection_confirmation_path(date, store_root, source_confirmation_file, prefer_existing_0935_source)
        return _read_csv(path), _repo_path(path) if path.exists() else "", "local_existing_confirmation", "min1_0935_bar", notes
    if mode in ONLINE_MODES and not allow_online_query:
        notes.append("online_query_blocked_without_allow_online_query")
        return [], "", "online_query_blocked", "not_executed", notes
    codes = sorted({str(row.get("code", "") or "").strip() for row in candidates if str(row.get("code", "") or "").strip()})
    if not codes:
        notes.append("no_candidate_codes_for_online_query")
        return [], "", "missing_candidate_codes", "not_executed", notes
    if query_backend == "subprocess":
        rows, worker_warnings = _run_query_worker(
            mode=mode,
            date=date,
            codes=codes,
            query_window_start=query_window_start,
            query_window_end=query_window_end,
            amazing_local_config=amazing_local_config,
            worker_python=worker_python,
            worker_timeout=worker_timeout,
        )
        notes.extend(f"worker_warning:{item}" for item in worker_warnings)
        if mode == SNAPSHOT_MODE:
            return _normalize_query_rows(rows, mode), "AmazingData.worker.query_snapshot", "amazingdata_query_snapshot", "strict_0935_snapshot", notes
        return _normalize_query_rows(rows, mode), "AmazingData.worker.query_kline_min1", "amazingdata_query_kline_min1", "min1_0935_bar", notes
    if mode == SNAPSHOT_MODE:
        rows = _query_historical_snapshot_rows(codes, date, query_window_start, query_window_end, amazing_local_config)
        return _normalize_query_rows(rows, mode), "AmazingData.query_snapshot", "amazingdata_query_snapshot", "strict_0935_snapshot", notes
    rows = _query_historical_min1_rows(codes, date, amazing_local_config)
    return _normalize_query_rows(rows, mode), "AmazingData.query_kline_min1", "amazingdata_query_kline_min1", "min1_0935_bar", notes


def collect_for_date(
    date: str,
    validation_root: Path = DEFAULT_VALIDATION_ROOT,
    store_root: Path = DEFAULT_STORE_ROOT,
    mode: str = "local-existing-confirmation",
    candidate_source: str = "",
    source_confirmation_file: str = "",
    prefer_existing_0935_source: bool = False,
    allow_online_query: bool = False,
    query_window_start: str = "93500000",
    query_window_end: str = "93559999",
    timepoint_policy: str = "",
    amazing_local_config: str = "",
    query_backend: str = "direct",
    worker_python: str = "",
    worker_timeout: int = 60,
    output_filename: str = DEFAULT_OUTPUT_FILENAME,
    write_latest_copy: bool = False,
    dry_run: bool = False,
) -> dict:
    if mode not in ALL_MODES:
        return {
            "date": str(date),
            "status": "unsupported_mode",
            "mode": mode,
            "message": "Unsupported 09:35 collection mode.",
        }
    date = str(date)
    candidate_path = _candidate_source(date, validation_root, candidate_source)
    candidates = _read_csv(candidate_path)
    try:
        confirmations, confirmation_source, data_source, inferred_policy, notes = _collect_confirmation_rows(
            mode=mode,
            date=date,
            candidates=candidates,
            store_root=store_root,
            source_confirmation_file=source_confirmation_file,
            prefer_existing_0935_source=prefer_existing_0935_source,
            allow_online_query=allow_online_query,
            query_window_start=query_window_start,
            query_window_end=query_window_end,
            amazing_local_config=amazing_local_config,
            query_backend=query_backend,
            worker_python=worker_python,
            worker_timeout=worker_timeout,
        )
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
            raise
        return {
            "date": date,
            "status": "query_failed",
            "mode": mode,
            "error_type": type(exc).__name__,
            "error": str(exc)[:240],
            "candidate_source": _repo_path(candidate_path),
            "candidate_count": len(candidates),
            "would_write": False,
        }
    if data_source == "online_query_blocked":
        return {
            "date": date,
            "status": "online_query_not_allowed",
            "mode": mode,
            "candidate_source": _repo_path(candidate_path),
            "candidate_count": len(candidates),
            "message": "Pass --allow-online-query to execute historical AmazingData query modes, or use gap-only to write gap artifacts.",
            "would_write": False,
        }
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
        rows.append(_standardize_row(date, candidate, match, mode, data_source=data_source))

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
        "data_source": confirmation_source,
        "collection_mode": mode,
        "query_window": f"{query_window_start}-{query_window_end}" if mode == SNAPSHOT_MODE else "0935",
        "timepoint_policy": timepoint_policy or inferred_policy,
        "strict_point_snapshot": bool((timepoint_policy or inferred_policy) == "strict_0935_snapshot"),
        "notes": [
            "standardized_offline_artifact",
            "5min_0935_bar_not_used_as_strict_point_value",
            "labels_are_feedback_evidence_not_trading_instructions",
        ]
        + notes,
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
        "confirmation_source": confirmation_source,
        "output_csv": _repo_path(output_path),
        "output_meta": _repo_path(meta_path),
        "candidate_count": len(candidates),
        "matched_count": matched,
        "missing_count": meta["missing_count"],
        "collection_mode": mode,
        "timepoint_policy": meta["timepoint_policy"],
        "status": "ok",
        "would_write": not dry_run,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Collect standardized 09:35 feedback artifacts from local sources.")
    parser.add_argument("--date", default="")
    parser.add_argument("--dates", default="")
    parser.add_argument("--candidate-source", default="")
    parser.add_argument("--source-confirmation-file", default="")
    parser.add_argument("--validation-root", default=str(DEFAULT_VALIDATION_ROOT))
    parser.add_argument("--store-root", default=str(DEFAULT_STORE_ROOT))
    parser.add_argument("--mode", default="local-existing-confirmation")
    parser.add_argument("--target-timepoint", default="0935")
    parser.add_argument("--query-window-start", default="93500000")
    parser.add_argument("--query-window-end", default="93559999")
    parser.add_argument("--timepoint-policy", default="")
    parser.add_argument("--amazing-local-config", default="")
    parser.add_argument("--allow-online-query", action="store_true")
    parser.add_argument("--query-backend", choices=("direct", "subprocess"), default="direct")
    parser.add_argument("--worker-python", default="")
    parser.add_argument("--worker-timeout", type=int, default=60)
    parser.add_argument("--prefer-existing-0935-source", action="store_true")
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
            source_confirmation_file=args.source_confirmation_file if len(dates) == 1 else "",
            prefer_existing_0935_source=args.prefer_existing_0935_source,
            allow_online_query=args.allow_online_query,
            query_window_start=args.query_window_start,
            query_window_end=args.query_window_end,
            timepoint_policy=args.timepoint_policy,
            amazing_local_config=args.amazing_local_config,
            query_backend=args.query_backend,
            worker_python=args.worker_python,
            worker_timeout=args.worker_timeout,
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
