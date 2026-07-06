# -*- coding: utf-8 -*-
"""Probe AmazingData login control flow without market data queries.

The worker is diagnostic-only. It isolates SystemExit(0), logout behavior, and
subprocess exit semantics around ad.login without creating MarketData or
querying vendor data.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

JSON_BEGIN = "__AMAZING_LOGIN_CONTROL_FLOW_JSON_BEGIN__"
JSON_END = "__AMAZING_LOGIN_CONTROL_FLOW_JSON_END__"

STRATEGY_CHOICES = (
    "catch_system_exit_continue",
    "catch_system_exit_then_logout",
    "subprocess_exit_code_only",
    "existing_success_script_parity",
    "vendor_permission_hypothesis",
)


def emit(payload: dict) -> None:
    print(JSON_BEGIN)
    print(json.dumps(payload, ensure_ascii=False, default=str))
    print(JSON_END)


def _safe_error(exc: BaseException, config: dict | None = None) -> str:
    try:
        from core.amazing_login_config import sanitize_text

        return sanitize_text(str(exc), config)
    except Exception:
        return type(exc).__name__


def _load_ready_config(amazing_local_config: str = "") -> tuple[dict, dict]:
    from core.amazing_login_config import load_login_config, sanitized_config_status

    config = load_login_config(dotenv_path=Path(amazing_local_config) if amazing_local_config else None)
    return config, sanitized_config_status(config)


def _login_args(config: dict, login_style: str):
    from core.amazing_login_client import build_login_invocation

    return build_login_invocation(config, login_style)


def _base_result(strategy: str, config_status: dict | None = None) -> dict:
    return {
        "strategy": strategy,
        "status": "inconclusive",
        "system_exit_code": None,
        "login_returned": False,
        "post_system_exit_checks": {
            "logout_callable": False,
            "logout_returned": False,
            "session_state_observable": False,
        },
        "permission_hypothesis": "possible",
        "safe_to_query": False,
        "config_status": config_status or {},
        "notes": [],
    }


def _login_once(strategy: str, login_style: str, amazing_local_config: str = "", attempt_logout_after_exit: bool = False) -> dict:
    config = None
    config_status = {}
    result = _base_result(strategy)
    try:
        config, config_status = _load_ready_config(amazing_local_config)
        result["config_status"] = config_status
        if not config.get("ready"):
            result.update({"status": "failed", "error_type": "config_missing", "sanitized_error": "config_missing"})
            return result
        import AmazingData as ad

        logout_callable = callable(getattr(ad, "logout", None))
        result["post_system_exit_checks"]["logout_callable"] = logout_callable
        args, kwargs, _meta = _login_args(config, login_style)
        try:
            ad.login(*args, **kwargs)
            result["status"] = "ok"
            result["login_returned"] = True
            result["safe_to_query"] = True
            result["permission_hypothesis"] = "not_indicated_by_login"
        except SystemExit as exc:
            result["status"] = "system_exit"
            result["system_exit_code"] = getattr(exc, "code", None)
            result["notes"].append("system_exit_0_is_not_safe_to_query_by_default")
            if attempt_logout_after_exit and logout_callable:
                try:
                    ad.logout(str(config.get("username", "")))
                    result["post_system_exit_checks"]["logout_returned"] = True
                except BaseException as logout_exc:
                    if isinstance(logout_exc, KeyboardInterrupt):
                        raise
                    result["post_system_exit_checks"]["logout_returned"] = False
                    result["notes"].append(f"logout_after_system_exit:{type(logout_exc).__name__}")
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            result["status"] = "failed"
            result["error_type"] = type(exc).__name__
            result["sanitized_error"] = _safe_error(exc, config)
        return result
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
            raise
        result["config_status"] = config_status
        result["status"] = "failed"
        result["error_type"] = type(exc).__name__
        result["sanitized_error"] = _safe_error(exc, config)
        return result


def _subprocess_exit_code_only(strategy: str, login_style: str, amazing_local_config: str = "") -> dict:
    # This mode intentionally does not catch SystemExit around ad.login.
    config, config_status = _load_ready_config(amazing_local_config)
    if not config.get("ready"):
        result = _base_result(strategy, config_status)
        result.update({"status": "failed", "error_type": "config_missing", "sanitized_error": "config_missing"})
        return result
    import AmazingData as ad

    args, kwargs, _meta = _login_args(config, login_style)
    ad.login(*args, **kwargs)
    result = _base_result(strategy, config_status)
    result.update({"status": "ok", "login_returned": True, "safe_to_query": True, "permission_hypothesis": "not_indicated_by_login"})
    return result


def _existing_success_script_parity(strategy: str) -> dict:
    result = _base_result(strategy)
    result.update(
        {
            "status": "inconclusive",
            "permission_hypothesis": "possible",
            "notes": [
                "existing scripts show direct and helper login paths, but current P2.3E result has no successful login style",
                "no market data query executed",
            ],
        }
    )
    return result


def _vendor_permission_hypothesis(strategy: str) -> dict:
    result = _base_result(strategy)
    result.update(
        {
            "status": "inconclusive",
            "permission_hypothesis": "plausible_not_proven",
            "notes": [
                "manual_requires_login_before_api_calls",
                "manual_indicates_sdk_credentials_ip_port_require_official_permission",
                "config_ready_only_means_values_exist_not_permission_granted",
            ],
        }
    )
    return result


def run_strategy(strategy: str, login_style: str = "keyword-int-port", amazing_local_config: str = "") -> dict:
    if strategy == "catch_system_exit_continue":
        return _login_once(strategy, login_style, amazing_local_config, attempt_logout_after_exit=False)
    if strategy == "catch_system_exit_then_logout":
        return _login_once(strategy, login_style, amazing_local_config, attempt_logout_after_exit=True)
    if strategy == "subprocess_exit_code_only":
        return _subprocess_exit_code_only(strategy, login_style, amazing_local_config)
    if strategy == "existing_success_script_parity":
        return _existing_success_script_parity(strategy)
    if strategy == "vendor_permission_hypothesis":
        return _vendor_permission_hypothesis(strategy)
    result = _base_result(strategy)
    result.update({"status": "failed", "error_type": "unsupported_strategy", "sanitized_error": "unsupported_strategy"})
    return result


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Probe one AmazingData login control-flow strategy.")
    parser.add_argument("--strategy", required=True, choices=STRATEGY_CHOICES)
    parser.add_argument("--login-style", default="keyword-int-port")
    parser.add_argument("--amazing-local-config", default="")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    payload = run_strategy(args.strategy, args.login_style, args.amazing_local_config)
    emit(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
