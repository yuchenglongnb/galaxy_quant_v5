# -*- coding: utf-8 -*-
"""Subprocess worker for AmazingData 09:35 historical queries.

The worker prints a framed JSON payload to stdout and writes no repository
files. It is intentionally narrow: query only requested candidate codes and
return normalized row dictionaries for the parent collector.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

JSON_BEGIN = "__AMAZING_0935_JSON_BEGIN__"
JSON_END = "__AMAZING_0935_JSON_END__"


def emit(payload: dict) -> None:
    print(JSON_BEGIN)
    print(json.dumps(payload, ensure_ascii=False, default=str))
    print(JSON_END)


def _safe_error(exc: BaseException) -> str:
    try:
        from core.amazing_login_config import sanitize_text

        return sanitize_text(str(exc))
    except Exception:
        return type(exc).__name__


def _query_snapshot(request: dict) -> list[dict]:
    from scripts.collect_0935_feedback import _query_historical_snapshot_rows

    return _query_historical_snapshot_rows(
        codes=[str(code) for code in request.get("codes", [])],
        date=str(request.get("date", "")),
        query_window_start=str(request.get("query_window_start", "93500000")),
        query_window_end=str(request.get("query_window_end", "93559999")),
        amazing_local_config=str(request.get("amazing_local_config", "") or ""),
        login_style=str(request.get("login_style", "keyword-int-port") or "keyword-int-port"),
    )


def _query_min1(request: dict) -> list[dict]:
    from scripts.collect_0935_feedback import _query_historical_min1_rows

    return _query_historical_min1_rows(
        codes=[str(code) for code in request.get("codes", [])],
        date=str(request.get("date", "")),
        amazing_local_config=str(request.get("amazing_local_config", "") or ""),
        login_style=str(request.get("login_style", "keyword-int-port") or "keyword-int-port"),
    )


def run(request: dict) -> dict:
    mode = str(request.get("mode", ""))
    date = str(request.get("date", ""))
    codes = [str(code) for code in request.get("codes", []) if str(code).strip()]
    if not codes:
        return {
            "status": "missing_candidate_codes",
            "date": date,
            "mode": mode,
            "row_count": 0,
            "rows": [],
            "warnings": ["no_candidate_codes"],
        }
    try:
        if mode == "historical-snapshot-query":
            rows = _query_snapshot(request)
        elif mode == "historical-min1-kline":
            rows = _query_min1(request)
        else:
            return {
                "status": "unsupported_mode",
                "date": date,
                "mode": mode,
                "row_count": 0,
                "rows": [],
                "warnings": [],
            }
        return {
            "status": "ok",
            "date": date,
            "mode": mode,
            "row_count": len(rows),
            "rows": rows,
            "warnings": [],
        }
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
            raise
        return {
            "status": "query_failed",
            "date": date,
            "mode": mode,
            "error_type": type(exc).__name__,
            "sanitized_error": _safe_error(exc),
            "row_count": 0,
            "rows": [],
            "warnings": [],
        }


def main() -> int:
    try:
        request = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError as exc:
        emit({
            "status": "invalid_request_json",
            "error_type": type(exc).__name__,
            "sanitized_error": "invalid_request_json",
            "row_count": 0,
            "rows": [],
            "warnings": [],
        })
        return 0
    emit(run(request))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
