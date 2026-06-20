# -*- coding: utf-8 -*-
"""Compare AmazingData query behavior across implicit and explicit login modes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.amazing_login_client import (
    AmazingLoginError,
    bootstrap_amazingdata_client,
    build_login_invocation,
    logout_amazingdata_client,
)
from core.amazing_login_config import load_login_config, sanitize_text, sanitized_config_status
from utils.encoding import configure_utf8_console

EVAL_DIR = ROOT / "reports" / "analysis" / "evaluations"
DEFAULT_STOCK_CODE = "600519.SH"
DEFAULT_INDEX_CODE = "000001.SH"

LOGIN_MODE_CHOICES = (
    "implicit_query",
    "explicit_login_continue",
    "explicit_login_strict",
)
DATA_CASES = (
    "stock_day",
    "index_day",
    "stock_min1",
    "index_min1",
)


def get_calendar_helper():
    from core.calendar_helper import CalendarHelper

    return CalendarHelper


def get_iter_kline_frames():
    from core.snapshot_utils import iter_kline_frames

    return iter_kline_frames


def get_data_manager_class():
    from core.data_manager import DataManager

    return DataManager


def build_query_cases(target_date: int, stock_code: str, index_code: str) -> List[dict]:
    return [
        {
            "case": "stock_day",
            "code": str(stock_code),
            "security_type": "stock",
            "period_name": "day",
            "query_window_effective": "single_day_query_kline_call",
        },
        {
            "case": "index_day",
            "code": str(index_code),
            "security_type": "index",
            "period_name": "day",
            "query_window_effective": "single_day_query_kline_call",
        },
        {
            "case": "stock_min1",
            "code": str(stock_code),
            "security_type": "stock",
            "period_name": "min1",
            "query_window_effective": "full_day_query_kline_call_in_current_implementation",
        },
        {
            "case": "index_min1",
            "code": str(index_code),
            "security_type": "index",
            "period_name": "min1",
            "query_window_effective": "full_day_query_kline_call_in_current_implementation",
        },
    ]


def build_query_window(target_date: int, period_name: str) -> Dict[str, str]:
    if period_name == "min1":
        effective = "full_day_query_kline_call_in_current_implementation"
        return {
            "start": f"{int(target_date)} 09:30:00",
            "end": f"{int(target_date)} 10:00:00",
            "period": period_name,
            "query_window_effective": effective,
        }
    return {
        "start": f"{int(target_date)} 00:00:00",
        "end": f"{int(target_date)} 23:59:59",
        "period": period_name,
        "query_window_effective": "single_day_query_kline_call",
    }


def classify_login_exception(exc: BaseException) -> tuple[str, str]:
    if isinstance(exc, SystemExit):
        return "system_exit_during_login", f"system_exit_during_login:{getattr(exc, 'code', '')}"
    return "login_failed", str(exc or "login_failed")


def classify_query_exception(exc: BaseException, config: Mapping[str, object]) -> tuple[str, str]:
    lowered = str(exc or "").lower()
    if "timeout" in lowered:
        return "query_timeout", sanitize_text(str(exc), config)
    return "query_failed", sanitize_text(str(exc), config)


def build_result(
    *,
    target_date: int,
    login_mode: str,
    query_case: str,
    code: str,
    security_type: str,
    period_name: str,
    status: str,
    stage: str,
    error_type: str,
    error: str,
    elapsed_sec: float,
    login_returned: bool | None = None,
    login_exception_type: str = "",
    login_exception_message: str = "",
    row_count: int = 0,
    first_trade_time: str = "",
    last_trade_time: str = "",
    execution_model: str = "",
    config_status: Mapping[str, object] | None = None,
    query_window_effective: str = "",
) -> dict:
    return {
        "date": str(int(target_date)),
        "login_mode": login_mode,
        "query_case": query_case,
        "code": code,
        "security_type": security_type,
        "period": period_name,
        "status": status,
        "stage": stage,
        "error_type": error_type,
        "error": error,
        "elapsed_sec": round(float(elapsed_sec), 4),
        "login_returned": login_returned,
        "login_exception_type": login_exception_type,
        "login_exception_message": login_exception_message,
        "row_count": int(row_count),
        "first_trade_time": first_trade_time,
        "last_trade_time": last_trade_time,
        "execution_model": execution_model,
        "config_status": dict(config_status or {}),
        "query_window_effective": query_window_effective,
    }


def summarize_frame(frame) -> Dict[str, object]:
    row_count = int(len(frame))
    first_trade_time = ""
    last_trade_time = ""
    if row_count and "kline_time" in frame.columns:
        first = frame.iloc[0]["kline_time"]
        last = frame.iloc[-1]["kline_time"]
        first_trade_time = first.strftime("%H:%M:%S") if hasattr(first, "strftime") else str(first)
        last_trade_time = last.strftime("%H:%M:%S") if hasattr(last, "strftime") else str(last)
    return {
        "row_count": row_count,
        "first_trade_time": first_trade_time,
        "last_trade_time": last_trade_time,
    }


def query_kline_frame(market, code: str, target_date: int, period_value: int):
    import AmazingData as ad
    import pandas as pd

    if str(period_value) == "day":
        period_value = ad.constant.Period.day.value
    elif str(period_value) == "min1":
        period_value = ad.constant.Period.min1.value
    result = market.query_kline([str(code)], int(target_date), int(target_date), period_value)
    frames = list(get_iter_kline_frames()(result or {}))
    frame = frames[0][1].copy() if frames else pd.DataFrame()
    if not frame.empty and "kline_time" in frame.columns:
        frame["kline_time"] = pd.to_datetime(frame["kline_time"], errors="coerce")
        frame = frame.dropna(subset=["kline_time"]).sort_values("kline_time")
    return frame


def create_market_without_explicit_login():
    manager = get_data_manager_class()()
    return {
        "ad": None,
        "config": load_login_config(),
        "base": manager.ad_base,
        "market": manager.ad_market,
        "manager": manager,
        "login_returned": None,
        "login_exception_type": "",
        "login_exception_message": "",
        "execution_model": "datamanager_marketdata",
    }


def create_market_with_explicit_login(login_mode: str):
    import AmazingData as ad

    config = load_login_config()
    login_returned = False
    login_exception_type = ""
    login_exception_message = ""
    execution_model = "explicit_login_marketdata"

    login_args, login_kwargs, _ = build_login_invocation(config, "keyword-int-port")
    try:
        ad.login(*login_args, **login_kwargs)
        login_returned = True
    except BaseException as exc:
        login_exception_type, login_exception_message = classify_login_exception(exc)
        login_exception_message = sanitize_text(login_exception_message, config)
        if login_mode == "explicit_login_strict":
            raise AmazingLoginError(
                status="login_failed",
                stage="login",
                error_type=login_exception_type,
                message=login_exception_message,
            ) from exc

    calendar = get_calendar_helper().generate_workday_calendar(days=30)
    return {
        "ad": ad,
        "config": config,
        "base": ad.BaseData(),
        "market": ad.MarketData(calendar),
        "login_returned": login_returned,
        "login_exception_type": login_exception_type,
        "login_exception_message": login_exception_message,
        "execution_model": execution_model,
    }


def run_single_query(target_date: int, login_mode: str, query_case: dict) -> dict:
    started = time.time()
    config = load_login_config()
    config_status = sanitized_config_status(config)
    stage = "bootstrap"
    ad_module = None
    bootstrap = None
    try:
        if login_mode == "implicit_query":
            bootstrap = create_market_without_explicit_login()
        elif login_mode in {"explicit_login_continue", "explicit_login_strict"}:
            bootstrap = create_market_with_explicit_login(login_mode)
        else:
            raise ValueError(f"Unsupported login mode: {login_mode}")
        ad_module = bootstrap.get("ad")
        stage = "query"
        frame = query_kline_frame(
            bootstrap["market"],
            query_case["code"],
            target_date,
            query_case["period_name"],
        )
        summary = summarize_frame(frame)
        status = "success" if summary["row_count"] > 0 else "empty"
        return build_result(
            target_date=target_date,
            login_mode=login_mode,
            query_case=query_case["case"],
            code=query_case["code"],
            security_type=query_case["security_type"],
            period_name=query_case["period_name"],
            status=status,
            stage="query",
            error_type="",
            error="",
            elapsed_sec=time.time() - started,
            login_returned=bootstrap.get("login_returned"),
            login_exception_type=bootstrap.get("login_exception_type", ""),
            login_exception_message=bootstrap.get("login_exception_message", ""),
            row_count=summary["row_count"],
            first_trade_time=summary["first_trade_time"],
            last_trade_time=summary["last_trade_time"],
            execution_model=bootstrap.get("execution_model", ""),
            config_status=config_status,
            query_window_effective=query_case.get("query_window_effective", ""),
        )
    except AmazingLoginError as exc:
        return build_result(
            target_date=target_date,
            login_mode=login_mode,
            query_case=query_case["case"],
            code=query_case["code"],
            security_type=query_case["security_type"],
            period_name=query_case["period_name"],
            status=exc.status,
            stage=exc.stage,
            error_type=exc.error_type,
            error=exc.message,
            elapsed_sec=time.time() - started,
            login_returned=False,
            login_exception_type=exc.error_type,
            login_exception_message=exc.message,
            execution_model="explicit_login_marketdata",
            config_status=config_status,
            query_window_effective=query_case.get("query_window_effective", ""),
        )
    except BaseException as exc:
        error_type, message = classify_query_exception(exc, config)
        login_returned = bootstrap.get("login_returned") if bootstrap else None
        login_exception_type = bootstrap.get("login_exception_type", "") if bootstrap else ""
        login_exception_message = bootstrap.get("login_exception_message", "") if bootstrap else ""
        execution_model = bootstrap.get("execution_model", "") if bootstrap else ""
        return build_result(
            target_date=target_date,
            login_mode=login_mode,
            query_case=query_case["case"],
            code=query_case["code"],
            security_type=query_case["security_type"],
            period_name=query_case["period_name"],
            status=error_type,
            stage=stage,
            error_type=error_type,
            error=message,
            elapsed_sec=time.time() - started,
            login_returned=login_returned,
            login_exception_type=login_exception_type,
            login_exception_message=login_exception_message,
            execution_model=execution_model,
            config_status=config_status,
            query_window_effective=query_case.get("query_window_effective", ""),
        )
    finally:
        if ad_module is not None:
            logout_amazingdata_client(ad_module, config)


def run_probe(
    target_date: int,
    stock_code: str,
    index_code: str,
    login_modes: Iterable[str],
    selected_cases: Iterable[str] | None = None,
) -> dict:
    cases = build_query_cases(target_date, stock_code, index_code)
    selected = {str(item) for item in (selected_cases or []) if str(item)}
    if selected:
        cases = [item for item in cases if item["case"] in selected]
    results = []
    for login_mode in login_modes:
        for query_case in cases:
            results.append(run_single_query(target_date, login_mode, query_case))
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "date": str(int(target_date)),
        "stock_code": stock_code,
        "index_code": index_code,
        "results": results,
        "scope": {
            "login_modes": list(login_modes),
            "cases": [item["case"] for item in cases],
        },
    }


def run_probe_isolated(
    target_date: int,
    stock_code: str,
    index_code: str,
    login_modes: Iterable[str],
    selected_cases: Iterable[str] | None = None,
    case_timeout_sec: int = 45,
) -> dict:
    cases = build_query_cases(target_date, stock_code, index_code)
    selected = {str(item) for item in (selected_cases or []) if str(item)}
    if selected:
        cases = [item for item in cases if item["case"] in selected]
    query_case_map = {item["case"]: item for item in cases}
    results = []
    for login_mode in login_modes:
        for query_case_name in query_case_map:
            results.append(
                run_single_query_subprocess(
                    target_date=target_date,
                    login_mode=login_mode,
                    query_case_name=query_case_name,
                    stock_code=stock_code,
                    index_code=index_code,
                    timeout_sec=case_timeout_sec,
                )
            )
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "date": str(int(target_date)),
        "stock_code": stock_code,
        "index_code": index_code,
        "results": results,
        "scope": {
            "login_modes": list(login_modes),
            "cases": [item["case"] for item in cases],
            "case_timeout_sec": int(case_timeout_sec),
            "execution_strategy": "per_case_subprocess",
        },
    }


def run_single_query_subprocess(
    *,
    target_date: int,
    login_mode: str,
    query_case_name: str,
    stock_code: str,
    index_code: str,
    timeout_sec: int,
) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        result_path = Path(fh.name)
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        str(int(target_date)),
        "--stock-code",
        stock_code,
        "--index-code",
        index_code,
        "--login-modes",
        login_mode,
        "--cases",
        query_case_name,
        "--worker-result",
        str(result_path),
    ]
    started = time.time()
    try:
        subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=int(timeout_sec),
            check=False,
        )
        if result_path.exists() and result_path.stat().st_size > 0:
            return json.loads(result_path.read_text(encoding="utf-8"))
        query_case = next(
            item for item in build_query_cases(target_date, stock_code, index_code) if item["case"] == query_case_name
        )
        return build_result(
            target_date=target_date,
            login_mode=login_mode,
            query_case=query_case_name,
            code=query_case["code"],
            security_type=query_case["security_type"],
            period_name=query_case["period_name"],
            status="unknown_failed",
            stage="worker_result",
            error_type="worker_result_missing",
            error="worker_result_missing",
            elapsed_sec=time.time() - started,
            execution_model="per_case_subprocess",
            config_status=sanitized_config_status(load_login_config()),
            query_window_effective=query_case.get("query_window_effective", ""),
        )
    except subprocess.TimeoutExpired:
        query_case = next(
            item for item in build_query_cases(target_date, stock_code, index_code) if item["case"] == query_case_name
        )
        return build_result(
            target_date=target_date,
            login_mode=login_mode,
            query_case=query_case_name,
            code=query_case["code"],
            security_type=query_case["security_type"],
            period_name=query_case["period_name"],
            status="query_timeout",
            stage="query",
            error_type="case_timeout",
            error=f"case_timeout_after_{int(timeout_sec)}s",
            elapsed_sec=time.time() - started,
            execution_model="per_case_subprocess",
            config_status=sanitized_config_status(load_login_config()),
            query_window_effective=query_case.get("query_window_effective", ""),
        )
    finally:
        result_path.unlink(missing_ok=True)


def summarize_results(results: Iterable[Mapping[str, object]]) -> Dict[str, object]:
    distribution: Dict[str, int] = {}
    by_mode: Dict[str, Dict[str, int]] = {}
    for row in results:
        status = str(row.get("status", "unknown"))
        login_mode = str(row.get("login_mode", "unknown"))
        distribution[status] = distribution.get(status, 0) + 1
        mode_bucket = by_mode.setdefault(login_mode, {})
        mode_bucket[status] = mode_bucket.get(status, 0) + 1

    diagnosis = "unknown"
    mode_statuses = {
        mode: {row.get("status") for row in results if row.get("login_mode") == mode}
        for mode in LOGIN_MODE_CHOICES
    }
    implicit_ok = bool(mode_statuses.get("implicit_query", set()) & {"success", "empty"})
    continue_ok = bool(mode_statuses.get("explicit_login_continue", set()) & {"success", "empty"})
    strict_login_fail = bool(mode_statuses.get("explicit_login_strict", set()) & {"login_failed", "login_timeout", "bootstrap_failed"})
    implicit_timeout = "query_timeout" in mode_statuses.get("implicit_query", set())
    continue_timeout = "query_timeout" in mode_statuses.get("explicit_login_continue", set())

    if implicit_ok and strict_login_fail:
        diagnosis = "implicit_query_works_explicit_login_path_fails"
    elif implicit_timeout and continue_timeout and strict_login_fail:
        diagnosis = "query_path_times_out_even_without_successful_explicit_login"
    elif implicit_ok and continue_ok:
        diagnosis = "query_service_reachable_explicit_login_return_not_required"
    elif all(statuses <= {"login_failed", "login_timeout", "bootstrap_failed"} for statuses in mode_statuses.values()):
        diagnosis = "all_modes_blocked_before_query"
    elif any(row.get("query_case") == "index_min1" and row.get("status") in {"query_failed", "query_timeout"} for row in results):
        diagnosis = "index_min1_specific_query_issue"

    return {
        "status_distribution": distribution,
        "mode_distribution": by_mode,
        "diagnosis": diagnosis,
    }


def write_outputs(payload: dict) -> tuple[Path, Path]:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    target_date = int(payload["date"])
    json_path = EVAL_DIR / f"amazing_query_mode_probe_{target_date}.json"
    md_path = EVAL_DIR / f"amazing_query_mode_probe_{target_date}.md"
    summary = summarize_results(payload["results"])
    enriched = dict(payload)
    enriched["summary"] = summary
    json_path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# AmazingData Query Mode Differential Probe",
        "",
        "## 1. Scope",
        "",
        f"- date: `{payload['date']}`",
        f"- stock_code: `{payload['stock_code']}`",
        f"- index_code: `{payload['index_code']}`",
        f"- login_modes: `{', '.join(payload['scope']['login_modes'])}`",
        "",
        "## 2. Per-Query Result",
        "",
        "| login_mode | query_case | code | status | stage | login_returned | login_exception_type | row_count | elapsed_sec |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: | ---: |",
    ]
    for row in payload["results"]:
        lines.append(
            f"| {row.get('login_mode', '-')} | {row.get('query_case', '-')} | {row.get('code', '-')} | "
            f"{row.get('status', '-')} | {row.get('stage', '-')} | {row.get('login_returned', '-')} | "
            f"{row.get('login_exception_type', '-') or '-'} | {row.get('row_count', 0)} | "
            f"{row.get('elapsed_sec', 0)} |"
        )
    lines.extend(
        [
            "",
            "## 3. Diagnosis",
            "",
            f"- diagnosis: `{summary['diagnosis']}`",
            "",
            "## 4. Recommended Next Step",
            "",
        ]
    )
    diagnosis = summary["diagnosis"]
    if diagnosis == "implicit_query_works_explicit_login_path_fails":
        lines.append("- DataManager-style implicit query path is more reliable than explicit login. Prefer validating remote query availability through that path next.")
    elif diagnosis == "query_service_reachable_explicit_login_return_not_required":
        lines.append("- Query service appears reachable even when explicit login control flow is unusual. Treat ad.login return semantics as a separate SDK issue.")
    elif diagnosis == "all_modes_blocked_before_query":
        lines.append("- All modes are blocked before usable query results. Keep focus on AmazingData login/bootstrap behavior rather than index min1.")
    elif diagnosis == "query_path_times_out_even_without_successful_explicit_login":
        lines.append("- Strict explicit login fails, but implicit and continue modes both reach a long-running query path. This points away from index-only blame and toward a broader query-path or service-mode issue.")
    elif diagnosis == "index_min1_specific_query_issue":
        lines.append("- Query path is partly alive; next isolate index min1 specifics instead of general login bootstrap.")
    else:
        lines.append("- Query-mode differential is still inconclusive. Compare DataManager live sync path against this probe before touching backfill.")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare AmazingData query behavior across login modes.")
    parser.add_argument("date", type=int, nargs="?", default=20260615, help="Trading date in YYYYMMDD format.")
    parser.add_argument("--stock-code", default=DEFAULT_STOCK_CODE, help="Stock code for stock day/min1 queries.")
    parser.add_argument("--index-code", default=DEFAULT_INDEX_CODE, help="Index code for index day/min1 queries.")
    parser.add_argument(
        "--login-modes",
        nargs="+",
        choices=LOGIN_MODE_CHOICES,
        default=list(LOGIN_MODE_CHOICES),
        help="Login/query modes to compare.",
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        choices=DATA_CASES,
        default=list(DATA_CASES),
        help="Query cases to run.",
    )
    parser.add_argument("--case-timeout-sec", type=int, default=45, help="Per-case timeout for CLI isolated execution.")
    parser.add_argument("--worker-result", default="", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    configure_utf8_console()
    args = parse_args()
    if args.worker_result:
        payload = run_probe(args.date, args.stock_code, args.index_code, args.login_modes, args.cases)
        result = payload["results"][0] if payload["results"] else {}
        Path(args.worker_result).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return 0
    payload = run_probe_isolated(
        args.date,
        args.stock_code,
        args.index_code,
        args.login_modes,
        args.cases,
        args.case_timeout_sec,
    )
    json_path, md_path = write_outputs(payload)
    print(
        json.dumps(
            {
                "json": str(json_path.relative_to(ROOT)),
                "md": str(md_path.relative_to(ROOT)),
                "diagnosis": summarize_results(payload["results"])["diagnosis"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
