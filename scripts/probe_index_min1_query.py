# -*- coding: utf-8 -*-
"""Probe index min1 query behavior with same-process and subprocess modes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.amazing_login_client import AmazingLoginError, bootstrap_amazingdata_client, logout_amazingdata_client
from core.amazing_login_config import sanitize_text
from core.calendar_helper import CalendarHelper
from core.snapshot_utils import iter_kline_frames
from scripts.backfill_intraday_cache import resolve_minimal_universe
from utils.encoding import configure_utf8_console

EVAL_DIR = ROOT / "reports" / "analysis" / "evaluations"


def split_code(code: str) -> Dict[str, str]:
    text = str(code or "").strip()
    if "." in text:
        symbol, market = text.split(".", 1)
    else:
        symbol, market = text, ""
    return {
        "original_code": text,
        "normalized_code": text.upper(),
        "query_code": text.upper(),
        "market": market.upper(),
        "symbol": symbol,
    }


def build_query_window(target_date: int) -> Dict[str, str]:
    return {
        "start": f"{int(target_date)} 09:30:00",
        "end": f"{int(target_date)} 10:00:00",
        "period": "min1",
        "query_window_effective": "full_day_query_kline_call_in_current_implementation",
    }


def classify_error(text: str, bootstrap_status: str = "success") -> str:
    lowered = str(text or "").lower()
    if bootstrap_status in {"config_missing", "bootstrap_failed"}:
        return "bootstrap_failed"
    if bootstrap_status == "login_failed":
        return "login_failed"
    if "checklogonlegal" in lowered or "login fail" in lowered or "tgw init failed" in lowered:
        return "login_failed"
    if "timeout" in lowered:
        return "query_timeout"
    if "invalid" in lowered and "code" in lowered:
        return "code_invalid"
    if lowered:
        return "query_failed"
    return "unknown_failed"


def build_result(
    code: str,
    target_date: int,
    probe_mode: str,
    status: str,
    stage: str,
    error_type: str,
    error: str,
    elapsed_sec: float,
    worker_bootstrap_status: str = "success",
    row_count: int = 0,
    first_trade_time: str = "",
    last_trade_time: str = "",
) -> dict:
    return {
        **split_code(code),
        "date": str(int(target_date)),
        "probe_mode": probe_mode,
        "status": status,
        "worker_bootstrap_status": worker_bootstrap_status,
        "stage": stage,
        "elapsed_sec": round(float(elapsed_sec), 4),
        "row_count": int(row_count),
        "first_trade_time": first_trade_time,
        "last_trade_time": last_trade_time,
        "error_type": error_type,
        "error": error,
    }


def bootstrap_market_data():
    ad, config = bootstrap_amazingdata_client()
    calendar = CalendarHelper.generate_workday_calendar(days=30)
    market = ad.MarketData(calendar)
    return ad, market, config


def run_query(market, code: str, target_date: int) -> pd.DataFrame:
    import AmazingData as ad

    result = market.query_kline(
        [str(code)],
        begin_date=int(target_date),
        end_date=int(target_date),
        period=ad.constant.Period.min1.value,
    )
    frames = list(iter_kline_frames(result or {}))
    frame = frames[0][1].copy() if frames else pd.DataFrame()
    if not frame.empty and "kline_time" in frame.columns:
        frame["kline_time"] = pd.to_datetime(frame["kline_time"], errors="coerce")
        frame = frame.dropna(subset=["kline_time"]).sort_values("kline_time")
    return frame


def frame_summary(frame: pd.DataFrame) -> Dict[str, object]:
    row_count = int(len(frame))
    first_trade_time = ""
    last_trade_time = ""
    if row_count and "kline_time" in frame.columns:
        first_trade_time = frame.iloc[0]["kline_time"].strftime("%H:%M:%S")
        last_trade_time = frame.iloc[-1]["kline_time"].strftime("%H:%M:%S")
    return {
        "row_count": row_count,
        "first_trade_time": first_trade_time,
        "last_trade_time": last_trade_time,
    }


def _probe_same_process(target_date: int, code: str) -> dict:
    started = time.time()
    bootstrap_status = "success"
    ad = None
    config = None
    try:
        ad, market, config = bootstrap_market_data()
        frame = run_query(market, code, target_date)
        summary = frame_summary(frame)
        status = "success" if summary["row_count"] > 0 else "empty"
        return build_result(
            code,
            target_date,
            "same-process",
            status=status,
            stage="query",
            error_type="",
            error="",
            elapsed_sec=time.time() - started,
            row_count=int(summary["row_count"]),
            first_trade_time=summary["first_trade_time"],
            last_trade_time=summary["last_trade_time"],
        )
    except AmazingLoginError as exc:
        bootstrap_status = exc.error_type
        return build_result(
            code,
            target_date,
            "same-process",
            status=exc.status,
            stage=exc.stage,
            error_type=exc.error_type,
            error=exc.message,
            elapsed_sec=time.time() - started,
            worker_bootstrap_status=exc.error_type,
        )
    except Exception as exc:
        error_type = classify_error(str(exc), bootstrap_status=bootstrap_status)
        stage = "query" if bootstrap_status == "success" else "login"
        return build_result(
            code,
            target_date,
            "same-process",
            status=error_type,
            stage=stage,
            error_type=error_type,
            error=sanitize_text(str(exc), config),
            elapsed_sec=time.time() - started,
            worker_bootstrap_status=bootstrap_status,
        )
    finally:
        logout_amazingdata_client(ad, config)


def _probe_worker(payload: dict) -> dict:
    code = str(payload["code"])
    target_date = int(payload["date"])
    started = time.time()
    bootstrap_status = "success"
    ad = None
    config = None
    try:
        ad, market, config = bootstrap_market_data()
        frame = run_query(market, code, target_date)
        summary = frame_summary(frame)
        status = "success" if summary["row_count"] > 0 else "empty"
        return build_result(
            code,
            target_date,
            "subprocess",
            status=status,
            stage="query",
            error_type="",
            error="",
            elapsed_sec=time.time() - started,
            row_count=int(summary["row_count"]),
            first_trade_time=summary["first_trade_time"],
            last_trade_time=summary["last_trade_time"],
        )
    except AmazingLoginError as exc:
        bootstrap_status = exc.error_type
        return build_result(
            code,
            target_date,
            "subprocess",
            status=exc.status,
            stage=exc.stage,
            error_type=exc.error_type,
            error=exc.message,
            elapsed_sec=time.time() - started,
            worker_bootstrap_status=exc.error_type,
        )
    except Exception as exc:
        error_type = classify_error(str(exc), bootstrap_status=bootstrap_status)
        worker_bootstrap_status = "login_failed" if error_type == "login_failed" else bootstrap_status
        stage = "query" if bootstrap_status == "success" else "login"
        return build_result(
            code,
            target_date,
            "subprocess",
            status=error_type,
            stage=stage,
            error_type=error_type,
            error=sanitize_text(str(exc), config),
            elapsed_sec=time.time() - started,
            worker_bootstrap_status=worker_bootstrap_status,
        )
    finally:
        logout_amazingdata_client(ad, config)


def _run_worker_subprocess(target_date: int, code: str, timeout_sec: int) -> dict:
    payload = {"date": int(target_date), "code": str(code)}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
        payload_path = fh.name
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as result_fh:
        result_path = result_fh.name
    cmd = [sys.executable, str(Path(__file__).resolve()), "--worker-json", payload_path, "--worker-result", result_path]
    started = time.time()
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=int(timeout_sec),
            check=False,
        )
        stdout = (completed.stdout or "").strip()
        result = None
        if Path(result_path).exists() and Path(result_path).stat().st_size > 0:
            result = json.loads(Path(result_path).read_text(encoding="utf-8"))
        else:
            json_text = ""
            for line in reversed(stdout.splitlines()):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    json_text = line
                    break
            if json_text:
                result = json.loads(json_text)
        if result is None:
            merged_error = sanitize_text(" ".join(part for part in [completed.stderr or "", stdout or ""] if part))
            error_type = classify_error(merged_error, bootstrap_status="bootstrap_failed")
            stage = "query" if error_type in {"query_failed", "query_timeout"} else "login"
            result = build_result(
                code,
                target_date,
                "subprocess",
                status=error_type,
                stage=stage,
                error_type=error_type,
                error=merged_error or error_type,
                elapsed_sec=time.time() - started,
                worker_bootstrap_status="bootstrap_failed" if error_type != "query_failed" else "success",
            )
        result["elapsed_sec"] = round(time.time() - started, 4)
        return result
    except subprocess.TimeoutExpired:
        return build_result(
            code,
            target_date,
            "subprocess",
            status="query_timeout",
            stage="query",
            error_type="query_timeout",
            error="query_timeout",
            elapsed_sec=time.time() - started,
            worker_bootstrap_status="unknown",
        )
    finally:
        try:
            Path(payload_path).unlink(missing_ok=True)
        except Exception:
            pass
        try:
            Path(result_path).unlink(missing_ok=True)
        except Exception:
            pass


def run_probe(target_date: int, codes: Iterable[str], timeout_sec: int, probe_mode: str) -> List[dict]:
    rows = []
    for code in codes:
        try:
            if probe_mode == "same-process":
                rows.append(_probe_same_process(target_date, code))
            else:
                rows.append(_run_worker_subprocess(target_date, code, timeout_sec))
        except Exception as exc:
            rows.append(
                build_result(
                    str(code),
                    target_date,
                    probe_mode,
                    status="unknown_failed",
                    stage="format_result",
                    error_type="unknown_failed",
                    error=sanitize_text(str(exc)),
                    elapsed_sec=0.0,
                    worker_bootstrap_status="unknown",
                )
            )
    return rows


def summarize_statuses(results: List[dict]) -> Dict[str, int]:
    keys = ("success", "empty", "query_timeout", "login_failed", "bootstrap_failed", "query_failed", "code_invalid", "unknown_failed")
    return {key: sum(1 for row in results if row.get("status") == key) for key in keys}


def diagnose_mode_results(results: List[dict]) -> str:
    statuses = [row.get("status", "") for row in results]
    if results and all(status == "login_failed" for status in statuses):
        return "all_failed_login_bootstrap"
    if results and all(status == "bootstrap_failed" for status in statuses):
        return "all_failed_bootstrap"
    if results and all(status == "query_timeout" for status in statuses):
        return "all_timeout"
    if results and all(status == "empty" for status in statuses):
        return "all_empty"
    if any(status == "success" for status in statuses):
        if any(status != "success" for status in statuses):
            return "mixed_success"
        return "success"
    if any(status == "query_failed" for status in statuses):
        return "all_query_failed" if all(status == "query_failed" for status in statuses) else "mixed_failure"
    return "mixed_failure"


def build_diagnosis_matrix(same_process_results: List[dict], subprocess_results: List[dict]) -> str:
    same_diag = diagnose_mode_results(same_process_results)
    sub_diag = diagnose_mode_results(subprocess_results)
    if same_diag in {"success", "mixed_success"} and sub_diag in {"all_failed_login_bootstrap", "all_failed_bootstrap", "mixed_failure"}:
        return "subprocess_bootstrap_issue"
    if same_diag in {"all_failed_login_bootstrap", "all_failed_bootstrap"} and sub_diag in {"all_failed_login_bootstrap", "all_failed_bootstrap"}:
        return "global_login_config_issue"
    if same_diag == "all_timeout" and sub_diag in {"all_failed_login_bootstrap", "all_failed_bootstrap"}:
        return "both_query_and_bootstrap_need_isolation"
    if same_diag in {"success", "mixed_success"} and sub_diag in {"success", "mixed_success"}:
        return "probe_ready_for_index_query_validation"
    return "needs_more_bootstrap_diagnosis"


def recommended_next_step(matrix_diagnosis: str) -> List[str]:
    mapping = {
        "subprocess_bootstrap_issue": [
            "same-process can already reach the real query path; fix subprocess bootstrap before touching index codes or batch splitting.",
            "Keep probe and backfill decoupled until the worker can reuse the project login path reliably.",
        ],
        "global_login_config_issue": [
            "Both the current process and subprocess workers are missing usable AmazingData login config; restore environment injection first.",
            "Until credentials are injected, do not attribute the probe failure to the index min1 API itself.",
        ],
        "both_query_and_bootstrap_need_isolation": [
            "The main-process query still blocks and subprocess bootstrap is also unresolved; diagnose the query path and login path separately.",
        ],
        "probe_ready_for_index_query_validation": [
            "Both probe modes are usable now; continue with single-code and multi-code index min1 validation.",
        ],
        "needs_more_bootstrap_diagnosis": [
            "Results are still mixed; compare same-process and subprocess initialization before deciding on query fallback.",
        ],
    }
    return mapping.get(matrix_diagnosis, [])


def write_outputs(
    target_date: int,
    timeout_sec: int,
    query_window: dict,
    same_process_results: List[dict],
    subprocess_results: List[dict],
) -> tuple[Path, Path]:
    matrix = build_diagnosis_matrix(same_process_results, subprocess_results)
    payload = {
        "date": str(int(target_date)),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "timeout_sec": int(timeout_sec),
        "query_window": query_window,
        "same_process": {
            "results": same_process_results,
            "summary": summarize_statuses(same_process_results),
            "diagnosis": diagnose_mode_results(same_process_results),
        },
        "subprocess": {
            "results": subprocess_results,
            "summary": summarize_statuses(subprocess_results),
            "diagnosis": diagnose_mode_results(subprocess_results),
        },
        "diagnosis_matrix": matrix,
        "recommended_next_step": recommended_next_step(matrix),
    }

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    json_path = EVAL_DIR / f"index_min1_probe_login_bootstrap_{int(target_date)}.json"
    md_path = EVAL_DIR / f"index_min1_probe_login_bootstrap_{int(target_date)}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Index Min1 Probe Login Bootstrap {int(target_date)}",
        "",
        "## 1. Probe Scope",
        "",
        f"- timeout_sec: `{int(timeout_sec)}`",
        f"- query_window.start: `{query_window['start']}`",
        f"- query_window.end: `{query_window['end']}`",
        f"- query_window.period: `{query_window['period']}`",
        f"- query_window_effective: `{query_window['query_window_effective']}`",
        "",
        "## 2. Same-Process Result",
        "",
        "| code | status | stage | elapsed_sec | row_count | error_type |",
        "| ---- | ------ | ----- | ----------: | --------: | ---------- |",
    ]
    for row in same_process_results:
        lines.append(
            f"| {row['query_code']} | {row['status']} | {row.get('stage') or '-'} | {float(row['elapsed_sec']):.4f} | {int(row['row_count'])} | {row['error_type'] or '-'} |"
        )
    lines.extend(
        [
            "",
            "## 3. Subprocess Result",
            "",
            "| code | status | worker_bootstrap_status | stage | elapsed_sec | row_count | error_type |",
            "| ---- | ------ | ----------------------- | ----- | ----------: | --------: | ---------- |",
        ]
    )
    for row in subprocess_results:
        lines.append(
            f"| {row['query_code']} | {row['status']} | {row.get('worker_bootstrap_status') or '-'} | {row.get('stage') or '-'} | "
            f"{float(row['elapsed_sec']):.4f} | {int(row['row_count'])} | {row['error_type'] or '-'} |"
        )
    lines.extend(
        [
            "",
            "## 4. Diagnosis Matrix",
            "",
            f"- same-process diagnosis: `{payload['same_process']['diagnosis']}`",
            f"- subprocess diagnosis: `{payload['subprocess']['diagnosis']}`",
            f"- matrix diagnosis: `{matrix}`",
            "",
            "## 5. Recommended Next Step",
            "",
        ]
    )
    if payload["recommended_next_step"]:
        lines.extend([f"- {item}" for item in payload["recommended_next_step"]])
    else:
        lines.append("- No additional recommendation.")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def parse_args():
    parser = argparse.ArgumentParser(description="Probe index min1 queries.")
    parser.add_argument("--date", type=int, default=0, help="Trade date YYYYMMDD")
    parser.add_argument("--codes", nargs="*", default=[], help="Explicit index codes")
    parser.add_argument("--from-plan", action="store_true", help="Resolve index codes from current minimal backfill plan")
    parser.add_argument("--timeout-sec", type=int, default=120, help="Hard timeout for each code subprocess")
    parser.add_argument(
        "--probe-mode",
        choices=("same-process", "subprocess", "both"),
        default="both",
        help="Probe execution mode.",
    )
    parser.add_argument("--worker-json", default="", help=argparse.SUPPRESS)
    parser.add_argument("--worker-result", default="", help=argparse.SUPPRESS)
    return parser.parse_args()


def resolve_codes(args) -> List[str]:
    codes = [str(code).strip().upper() for code in args.codes if str(code).strip()]
    if args.from_plan or not codes:
        from core.data_manager import DataManager

        dm = DataManager()
        universe = resolve_minimal_universe(int(args.date), dm)
        codes = universe["index_codes"]
    return codes


def main():
    configure_utf8_console()
    args = parse_args()

    if args.worker_json:
        payload = json.loads(Path(args.worker_json).read_text(encoding="utf-8"))
        result = _probe_worker(payload)
        if args.worker_result:
            Path(args.worker_result).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
        return

    if not args.date:
        raise SystemExit("--date is required")

    codes = resolve_codes(args)
    if not codes:
        raise SystemExit("No index codes to probe.")

    query_window = build_query_window(int(args.date))
    same_process_results: List[dict] = []
    subprocess_results: List[dict] = []
    if args.probe_mode in {"same-process", "both"}:
        same_process_results = run_probe(int(args.date), codes, int(args.timeout_sec), "same-process")
    if args.probe_mode in {"subprocess", "both"}:
        subprocess_results = run_probe(int(args.date), codes, int(args.timeout_sec), "subprocess")

    json_path, md_path = write_outputs(
        int(args.date),
        int(args.timeout_sec),
        query_window,
        same_process_results,
        subprocess_results,
    )
    print(
        json.dumps(
            {
                "json": str(json_path.relative_to(ROOT)),
                "md": str(md_path.relative_to(ROOT)),
                "date": str(int(args.date)),
                "codes": codes,
                "same_process_diagnosis": diagnose_mode_results(same_process_results) if same_process_results else "",
                "subprocess_diagnosis": diagnose_mode_results(subprocess_results) if subprocess_results else "",
                "diagnosis_matrix": build_diagnosis_matrix(same_process_results, subprocess_results),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
