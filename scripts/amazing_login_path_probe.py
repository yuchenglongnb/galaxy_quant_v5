# -*- coding: utf-8 -*-
"""Probe AmazingData login invocation styles without querying market data.

This worker is diagnostic-only. It never writes repository files and never
prints credential values. A caller should run it in a subprocess per style so
SDK SystemExit behavior stays isolated.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

JSON_BEGIN = "__AMAZING_LOGIN_PATH_JSON_BEGIN__"
JSON_END = "__AMAZING_LOGIN_PATH_JSON_END__"

STYLE_CHOICES = (
    "style_a_build_login_invocation_keyword_int_port",
    "style_b_build_login_invocation_positional_int_port",
    "style_c_direct_keyword_args",
    "style_d_positional_args",
    "style_e_existing_project_helper_exact",
)

STYLE_TO_LOGIN_STYLE = {
    "style_a_build_login_invocation_keyword_int_port": "keyword-int-port",
    "style_b_build_login_invocation_positional_int_port": "positional-int-port",
}


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


def _system_exit_payload(style: str, exc: SystemExit, config_status: dict) -> dict:
    code = getattr(exc, "code", None)
    return {
        "style": style,
        "status": "system_exit",
        "error_type": "SystemExit",
        "sanitized_error": str(code),
        "system_exit_code": code,
        "ambiguous_success": code == 0,
        "login_returned": False,
        "logout_attempted": False,
        "config_status": config_status,
        "notes": ["system_exit_0_is_ambiguous_not_success"] if code == 0 else [],
    }


def _load_config(amazing_local_config: str = "") -> tuple[dict, dict]:
    from core.amazing_login_config import load_login_config, sanitized_config_status

    config = load_login_config(dotenv_path=Path(amazing_local_config) if amazing_local_config else None)
    return config, sanitized_config_status(config)


def run_style(style: str, amazing_local_config: str = "") -> dict:
    if style not in STYLE_CHOICES:
        return {
            "style": style,
            "status": "failed",
            "error_type": "unsupported_style",
            "sanitized_error": "unsupported_style",
            "system_exit_code": None,
            "ambiguous_success": False,
            "login_returned": False,
            "logout_attempted": False,
            "config_status": {},
            "notes": [],
        }
    config = None
    ad_module = None
    config_status: dict = {}
    try:
        from core.amazing_login_client import bootstrap_amazingdata_client, build_login_invocation

        config, config_status = _load_config(amazing_local_config)
        if not config.get("ready"):
            return {
                "style": style,
                "status": "failed",
                "error_type": "config_missing",
                "sanitized_error": "config_missing",
                "system_exit_code": None,
                "ambiguous_success": False,
                "login_returned": False,
                "logout_attempted": False,
                "config_status": config_status,
                "notes": [],
            }
        if style == "style_e_existing_project_helper_exact":
            try:
                ad_module, config = bootstrap_amazingdata_client()
            except SystemExit as exc:
                return _system_exit_payload(style, exc, config_status)
            except BaseException as exc:
                if isinstance(exc, KeyboardInterrupt):
                    raise
                error_type = getattr(exc, "error_type", type(exc).__name__)
                message = getattr(exc, "message", _safe_error(exc, config))
                status = "system_exit" if "system_exit" in str(error_type) else "failed"
                return {
                    "style": style,
                    "status": status,
                    "error_type": str(error_type),
                    "sanitized_error": str(message),
                    "system_exit_code": 0 if "system_exit" in str(error_type) and str(message).endswith(":0") else None,
                    "ambiguous_success": "system_exit" in str(error_type) and str(message).endswith(":0"),
                    "login_returned": False,
                    "logout_attempted": False,
                    "config_status": config_status,
                    "notes": ["system_exit_0_is_ambiguous_not_success"] if "system_exit" in str(error_type) and str(message).endswith(":0") else [],
                }
        else:
            try:
                import AmazingData as ad

                ad_module = ad
            except BaseException as exc:
                if isinstance(exc, KeyboardInterrupt):
                    raise
                return {
                    "style": style,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "sanitized_error": _safe_error(exc, config),
                    "system_exit_code": None,
                    "ambiguous_success": False,
                    "login_returned": False,
                    "logout_attempted": False,
                    "config_status": config_status,
                    "notes": [],
                }
            try:
                if style in STYLE_TO_LOGIN_STYLE:
                    args, kwargs, _meta = build_login_invocation(config, STYLE_TO_LOGIN_STYLE[style])
                    ad_module.login(*args, **kwargs)
                elif style == "style_c_direct_keyword_args":
                    ad_module.login(
                        username=str(config["username"]),
                        password=str(config["password"]),
                        host=str(config["host"]),
                        port=int(str(config["port"])),
                    )
                elif style == "style_d_positional_args":
                    ad_module.login(
                        str(config["username"]),
                        str(config["password"]),
                        str(config["host"]),
                        int(str(config["port"])),
                    )
            except SystemExit as exc:
                return _system_exit_payload(style, exc, config_status)
            except BaseException as exc:
                if isinstance(exc, KeyboardInterrupt):
                    raise
                return {
                    "style": style,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "sanitized_error": _safe_error(exc, config),
                    "system_exit_code": None,
                    "ambiguous_success": False,
                    "login_returned": False,
                    "logout_attempted": False,
                    "config_status": config_status,
                    "notes": [],
                }
        logout_attempted = False
        if ad_module is not None:
            try:
                ad_module.logout(str(config.get("username", "")))
                logout_attempted = True
            except Exception:
                logout_attempted = True
        return {
            "style": style,
            "status": "ok",
            "error_type": "",
            "sanitized_error": "",
            "system_exit_code": None,
            "ambiguous_success": False,
            "login_returned": True,
            "logout_attempted": logout_attempted,
            "config_status": config_status,
            "notes": [],
        }
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
            raise
        return {
            "style": style,
            "status": "failed",
            "error_type": type(exc).__name__,
            "sanitized_error": _safe_error(exc, config),
            "system_exit_code": None,
            "ambiguous_success": False,
            "login_returned": False,
            "logout_attempted": False,
            "config_status": config_status,
            "notes": [],
        }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Probe one AmazingData login style.")
    parser.add_argument("--style", required=True, choices=STYLE_CHOICES)
    parser.add_argument("--amazing-local-config", default="")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    emit(run_style(args.style, args.amazing_local_config))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
