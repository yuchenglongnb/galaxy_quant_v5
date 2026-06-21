# -*- coding: utf-8 -*-
"""Probe AmazingData query_kline time parameter formats."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.amazing_login_client import bootstrap_amazingdata_client, logout_amazingdata_client
from core.calendar_helper import CalendarHelper
from core.snapshot_utils import iter_kline_frames
from utils.encoding import configure_utf8_console

EVAL_DIR = ROOT / "reports" / "analysis" / "evaluations"
PROGRESS_PATH = EVAL_DIR / "amazing_kline_time_param_probe_progress.jsonl"
CASE_ORDER = ("no_window", "hhmm", "snapshot_like")


def _append_progress(payload: dict) -> None:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    with PROGRESS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _log_event(case: str, status: str, started: float, **extra) -> None:
    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "case": case,
        "status": status,
        "elapsed_sec": round(time.time() - started, 4),
    }
    payload.update(extra)
    _append_progress(payload)


def build_cases() -> list[dict]:
    return [
        {"case": "no_window", "begin_time": None, "end_time": None},
        {"case": "hhmm", "begin_time": 930, "end_time": 935},
        {"case": "snapshot_like", "begin_time": 93000000, "end_time": 93500000},
    ]


def summarize_frame(frame) -> tuple[int, str, str]:
    row_count = int(len(frame))
    first_trade_time = ""
    last_trade_time = ""
    if row_count and "kline_time" in frame.columns:
        series = frame["kline_time"]
        first_trade_time = str(series.iloc[0])
        last_trade_time = str(series.iloc[-1])
    return row_count, first_trade_time, last_trade_time


def run_worker(target_date: int, code: str, case: str) -> dict:
    started = time.time()
    _log_event(case, "worker_start", started, code=code, date=str(target_date))
    ad = None
    config = None
    try:
        ad, config = bootstrap_amazingdata_client()
        calendar = CalendarHelper.generate_workday_calendar(days=30)
        market = ad.MarketData(calendar)

        import AmazingData as amazing
        import pandas as pd

        kwargs = {
            "begin_date": int(target_date),
            "end_date": int(target_date),
            "period": amazing.constant.Period.min1.value,
        }
        case_meta = next(item for item in build_cases() if item["case"] == case)
        if case_meta["begin_time"] is not None:
            kwargs["begin_time"] = int(case_meta["begin_time"])
            kwargs["end_time"] = int(case_meta["end_time"])

        _log_event(case, "query_start", started, query_kwargs=kwargs)
        result = market.query_kline([str(code)], **kwargs)
        frames = list(iter_kline_frames(result or {}))
        frame = frames[0][1].copy() if frames else pd.DataFrame()
        if not frame.empty and "kline_time" in frame.columns:
            frame["kline_time"] = pd.to_datetime(frame["kline_time"], errors="coerce")
            frame = frame.dropna(subset=["kline_time"]).sort_values("kline_time")
        row_count, first_trade_time, last_trade_time = summarize_frame(frame)
        status = "ok" if row_count > 0 else "empty"
        _log_event(case, "query_done", started, row_count=row_count)
        return {
            "case": case,
            "code": str(code),
            "date": str(int(target_date)),
            "begin_time": case_meta["begin_time"],
            "end_time": case_meta["end_time"],
            "elapsed_sec": round(time.time() - started, 4),
            "row_count": row_count,
            "first_trade_time": first_trade_time,
            "last_trade_time": last_trade_time,
            "status": status,
            "error": "",
        }
    except Exception as exc:
        _log_event(case, "query_failed", started, error=str(exc))
        return {
            "case": case,
            "code": str(code),
            "date": str(int(target_date)),
            "begin_time": next(item for item in build_cases() if item["case"] == case)["begin_time"],
            "end_time": next(item for item in build_cases() if item["case"] == case)["end_time"],
            "elapsed_sec": round(time.time() - started, 4),
            "row_count": 0,
            "first_trade_time": "",
            "last_trade_time": "",
            "status": "failed",
            "error": str(exc),
        }
    finally:
        logout_amazingdata_client(ad, config)


def run_parent(target_date: int, code: str, timeout_sec: float) -> dict:
    started = time.time()
    results = []
    python_exe = sys.executable
    for case_meta in build_cases():
        case = case_meta["case"]
        case_started = time.time()
        _log_event(case, "case_start", case_started, code=code, date=str(target_date))
        fd, tmp_name = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        result_path = Path(tmp_name)
        command = [
            python_exe,
            str(Path(__file__).resolve()),
            "--worker-case",
            case,
            "--date",
            str(int(target_date)),
            "--code",
            str(code),
            "--result-path",
            str(result_path),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=str(ROOT),
                check=False,
                timeout=float(timeout_sec),
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            raw_text = result_path.read_text(encoding="utf-8").strip() if result_path.exists() else ""
            if raw_text:
                payload = json.loads(raw_text)
            elif str(completed.stdout or "").strip():
                payload = _extract_json_from_stdout(str(completed.stdout or "").strip()) or {
                    "case": case,
                    "code": str(code),
                    "date": str(int(target_date)),
                    "begin_time": case_meta["begin_time"],
                    "end_time": case_meta["end_time"],
                    "elapsed_sec": round(time.time() - case_started, 4),
                    "row_count": 0,
                    "first_trade_time": "",
                    "last_trade_time": "",
                    "status": "failed",
                    "error": "missing_worker_result",
                }
            else:
                payload = {
                    "case": case,
                    "code": str(code),
                    "date": str(int(target_date)),
                    "begin_time": case_meta["begin_time"],
                    "end_time": case_meta["end_time"],
                    "elapsed_sec": round(time.time() - case_started, 4),
                    "row_count": 0,
                    "first_trade_time": "",
                    "last_trade_time": "",
                    "status": "failed",
                    "error": "missing_worker_result",
                }
            _log_event(case, "case_done", case_started, row_count=payload.get("row_count", 0), status_text=payload.get("status", ""))
        except subprocess.TimeoutExpired:
            payload = {
                "case": case,
                "code": str(code),
                "date": str(int(target_date)),
                "begin_time": case_meta["begin_time"],
                "end_time": case_meta["end_time"],
                "elapsed_sec": round(time.time() - case_started, 4),
                "row_count": 0,
                "first_trade_time": "",
                "last_trade_time": "",
                "status": "timeout",
                "error": f"timeout_after_{float(timeout_sec):.1f}s",
            }
            _log_event(case, "case_timeout", case_started, timeout_sec=float(timeout_sec))
        finally:
            try:
                result_path.unlink(missing_ok=True)
            except Exception:
                pass
        results.append(payload)

    output = {
        "date": str(int(target_date)),
        "code": str(code),
        "timeout_sec": float(timeout_sec),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "results": results,
        "elapsed_sec": round(time.time() - started, 4),
    }
    return output


def write_outputs(payload: dict) -> tuple[Path, Path]:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    json_path = EVAL_DIR / f"amazing_kline_time_param_probe_{payload['date']}.json"
    md_path = EVAL_DIR / f"amazing_kline_time_param_probe_{payload['date']}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Amazing Kline Time Param Probe {payload['date']}",
        "",
        f"- code: `{payload['code']}`",
        f"- timeout_sec: `{payload['timeout_sec']}`",
        "",
        "| case | begin_time | end_time | status | elapsed_sec | row_count | error |",
        "| --- | ---: | ---: | --- | ---: | ---: | --- |",
    ]
    for item in payload["results"]:
        lines.append(
            f"| {item['case']} | {item['begin_time'] if item['begin_time'] is not None else '-'} | "
            f"{item['end_time'] if item['end_time'] is not None else '-'} | {item['status']} | "
            f"{float(item['elapsed_sec']):.4f} | {int(item['row_count'])} | {item['error'] or '-'} |"
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def _extract_json_from_stdout(text: str) -> dict | None:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    for line in reversed(lines):
        if not line.startswith("{"):
            continue
        try:
            return json.loads(line)
        except Exception:
            continue
    return None


def parse_args():
    parser = argparse.ArgumentParser(description="Probe AmazingData query_kline begin_time/end_time formats.")
    parser.add_argument("--date", required=True, help="Trade date YYYYMMDD")
    parser.add_argument("--code", default="000001.SH", help="Security code")
    parser.add_argument("--timeout-sec", type=float, default=20.0, help="Per-case subprocess timeout")
    parser.add_argument("--worker-case", choices=CASE_ORDER)
    parser.add_argument("--result-path", default="")
    return parser.parse_args()


def main():
    configure_utf8_console()
    args = parse_args()
    if args.worker_case:
        payload = run_worker(int(args.date), str(args.code), str(args.worker_case))
        Path(args.result_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False))
        return

    payload = run_parent(int(args.date), str(args.code), float(args.timeout_sec))
    json_path, md_path = write_outputs(payload)
    print(
        json.dumps(
            {
                "json": str(json_path.relative_to(ROOT)),
                "md": str(md_path.relative_to(ROOT)),
                "results": payload["results"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
