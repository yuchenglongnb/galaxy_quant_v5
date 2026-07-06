# -*- coding: utf-8 -*-
"""Staged AmazingData 09:35 worker preflight probe.

This worker is diagnostic-only. It reads one JSON request from stdin, emits
stage markers plus a final framed JSON payload, and writes no repository files.
Credential/config values are never echoed.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STAGE_MARKER = "__AMAZING_PREFLIGHT_STAGE__"
DONE_MARKER = "__AMAZING_PREFLIGHT_DONE__"


def _print_json(marker: str, payload: dict) -> None:
    print(marker)
    print(json.dumps(payload, ensure_ascii=False, default=str))
    sys.stdout.flush()


def emit_stage(stage: str, status: str = "ok", **extra) -> dict:
    payload = {"stage": stage, "status": status}
    payload.update(extra)
    _print_json(STAGE_MARKER, payload)
    return payload


def emit_done(payload: dict) -> None:
    _print_json(DONE_MARKER, payload)


def _safe_error(exc: BaseException, config: dict | None = None) -> str:
    try:
        from core.amazing_login_config import sanitize_text

        return sanitize_text(str(exc), config)
    except Exception:
        return type(exc).__name__


def _fail(stages: list[dict], stage: str, exc: BaseException, config: dict | None = None) -> dict:
    payload = emit_stage(
        stage,
        "failed",
        error_type=type(exc).__name__,
        sanitized_error=_safe_error(exc, config),
    )
    stages.append(payload)
    return {
        "status": "failed",
        "first_failing_stage": stage,
        "error_type": type(exc).__name__,
        "sanitized_error": _safe_error(exc, config),
        "stages": stages,
    }


def _mode_to_query_kind(mode: str) -> str:
    if mode == "snapshot-preflight":
        return "historical-snapshot-query"
    if mode == "min1-preflight":
        return "historical-min1-kline"
    return mode


def run(request: dict) -> dict:
    stages: list[dict] = []
    config = None
    ad_module = None
    mode = str(request.get("mode", "import-only") or "import-only")
    date = str(request.get("date", "") or "")
    codes = [str(code).strip() for code in request.get("codes", []) if str(code).strip()]
    max_codes = int(request.get("max_codes", 3) or 3)
    codes = codes[:max(max_codes, 0)]

    try:
        stages.append(emit_stage("process_start", "ok", mode=mode, date=date, code_count=len(codes)))
        stages.append(emit_stage("repo_sys_path", "ok", root="repo_root"))

        try:
            from core.amazing_login_client import build_login_invocation
            from core.amazing_login_config import load_login_config, sanitized_config_status
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            return _fail(stages, "import_project_helpers", exc)
        stages.append(emit_stage("import_project_helpers", "ok"))

        try:
            config_path = str(request.get("amazing_local_config", "") or "")
            config = load_login_config(dotenv_path=Path(config_path) if config_path else None)
            status = sanitized_config_status(config)
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            return _fail(stages, "load_login_config", exc)
        stages.append(emit_stage("load_login_config", "ok", **status))

        if mode == "import-only":
            return {
                "status": "ok",
                "mode": mode,
                "date": date,
                "row_count": 0,
                "rows": [],
                "first_failing_stage": "",
                "stages": stages,
            }

        try:
            import AmazingData as ad

            ad_module = ad
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            return _fail(stages, "import_amazingdata", exc, config)
        stages.append(emit_stage("import_amazingdata", "ok"))

        if not config.get("ready"):
            exc = RuntimeError("AmazingData credentials are not available in the current process.")
            return _fail(stages, "login", exc, config)

        login_args, login_kwargs, meta = build_login_invocation(config, "keyword-int-port")
        try:
            ad_module.login(*login_args, **login_kwargs)
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            return _fail(stages, "login", exc, config)
        stages.append(emit_stage("login", "ok", login_style=meta.get("login_style"), port_type=meta.get("port_type")))

        if mode == "login-only":
            return {
                "status": "ok",
                "mode": mode,
                "date": date,
                "row_count": 0,
                "rows": [],
                "first_failing_stage": "",
                "stages": stages,
            }

        try:
            from core.calendar_helper import CalendarHelper

            calendar = CalendarHelper.generate_workday_calendar(days=60)
            market = ad_module.MarketData(calendar)
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            return _fail(stages, "marketdata_init", exc, config)
        stages.append(emit_stage("marketdata_init", "ok"))

        if not codes:
            exc = RuntimeError("no_candidate_codes")
            return _fail(stages, "query_snapshot" if mode == "snapshot-preflight" else "query_kline", exc, config)

        query_kind = _mode_to_query_kind(mode)
        try:
            from scripts.collect_0935_feedback import (
                _kline_result_rows,
                _normalize_query_rows,
                _query_time_to_hhmmss,
                _snapshot_result_rows,
            )

            if mode == "snapshot-preflight":
                start = int(request.get("query_window_start", 93500000) or 93500000)
                end = int(request.get("query_window_end", 93559999) or 93559999)
                result = market.query_snapshot(
                    codes,
                    begin_date=int(date),
                    end_date=int(date),
                    begin_time=start,
                    end_time=end,
                )
                stages.append(emit_stage("query_snapshot", "ok", code_count=len(codes)))
                raw_rows = _snapshot_result_rows(
                    result,
                    target_hhmmss=_query_time_to_hhmmss("093500"),
                    floor_hhmmss=_query_time_to_hhmmss(start),
                    ceil_hhmmss=_query_time_to_hhmmss(end),
                )
            elif mode == "min1-preflight":
                period = ad_module.constant.Period.min1.value
                result = market.query_kline(
                    codes,
                    begin_date=int(date),
                    end_date=int(date),
                    period=period,
                    begin_time=935,
                    end_time=935,
                )
                stages.append(emit_stage("query_kline", "ok", code_count=len(codes)))
                raw_rows = _kline_result_rows(result)
            else:
                exc = RuntimeError(f"unsupported_preflight_mode:{mode}")
                return _fail(stages, "query_mode", exc, config)
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            return _fail(stages, "query_snapshot" if mode == "snapshot-preflight" else "query_kline", exc, config)

        try:
            rows = _normalize_query_rows(raw_rows, query_kind)
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            return _fail(stages, "normalize_rows", exc, config)
        stages.append(emit_stage("normalize_rows", "ok", row_count=len(rows)))

        return {
            "status": "ok",
            "mode": mode,
            "date": date,
            "row_count": len(rows),
            "rows": rows,
            "first_failing_stage": "",
            "stages": stages,
        }
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
            raise
        return {
            "status": "failed",
            "mode": mode,
            "date": date,
            "first_failing_stage": "worker_unhandled_exception",
            "error_type": type(exc).__name__,
            "sanitized_error": _safe_error(exc, config),
            "traceback_type": "redacted",
            "stages": stages,
        }
    finally:
        if ad_module is not None and config:
            try:
                ad_module.logout(str(config.get("username", "")))
            except Exception:
                pass


def main() -> int:
    try:
        request = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError as exc:
        payload = {
            "status": "failed",
            "mode": "invalid-request",
            "first_failing_stage": "request_json_parse",
            "error_type": type(exc).__name__,
            "sanitized_error": "invalid_request_json",
            "stages": [],
        }
        emit_done(payload)
        return 0
    payload = run(request)
    payload.pop("traceback", None)
    emit_done(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
