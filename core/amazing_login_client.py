# -*- coding: utf-8 -*-
"""Shared AmazingData login helper aligned with the working SDK path."""

from __future__ import annotations

from typing import Callable, Mapping, Tuple

from core.amazing_login_config import load_login_config, sanitize_text, sanitized_config_status


class AmazingLoginError(RuntimeError):
    """Structured login/bootstrap error without leaking credentials."""

    def __init__(self, status: str, stage: str, error_type: str, message: str):
        super().__init__(message or error_type)
        self.status = status
        self.stage = stage
        self.error_type = error_type
        self.message = message or error_type


HeartbeatCallback = Callable[[str, Mapping[str, object] | None], None]
LOGIN_STYLE_CHOICES = (
    "positional-str-port",
    "positional-int-port",
    "keyword-str-port",
    "keyword-int-port",
)


def _emit_heartbeat(callback: HeartbeatCallback | None, stage: str, extra: Mapping[str, object] | None = None) -> None:
    if callback is None:
        return
    callback(stage, extra or {})


def _classify_bootstrap_error(exc: BaseException, phase: str, config: Mapping[str, object]) -> AmazingLoginError:
    if isinstance(exc, KeyboardInterrupt):
        raise exc
    if isinstance(exc, SystemExit):
        code = getattr(exc, "code", "")
        code_text = "" if code in (None, "") else str(code)
        message = f"system_exit_during_{phase}"
        if code_text:
            message = f"{message}:{code_text}"
        return AmazingLoginError(
            status="login_failed" if phase == "login" else "bootstrap_failed",
            stage=phase if phase == "login" else "load_config",
            error_type=f"system_exit_during_{phase}",
            message=message,
        )
    return AmazingLoginError(
        status="login_failed" if phase == "login" else "bootstrap_failed",
        stage=phase if phase == "login" else "load_config",
        error_type="login_failed" if phase == "login" else "bootstrap_import_failed",
        message=sanitize_text(str(exc), config),
    )


def build_login_invocation(config: Mapping[str, object], login_style: str) -> tuple[tuple[object, ...], dict[str, object], dict[str, str]]:
    if login_style not in LOGIN_STYLE_CHOICES:
        raise ValueError(f"Unsupported login_style: {login_style}")
    username = str(config["username"])
    password = str(config["password"])
    host = str(config["host"])
    port_str = str(config["port"])
    port_value: object = port_str if login_style.endswith("str-port") else int(port_str)
    meta = {
        "login_style": login_style,
        "username_type": type(username).__name__,
        "host_type": type(host).__name__,
        "port_type": type(port_value).__name__,
    }
    if login_style.startswith("positional"):
        return (username, password, host, port_value), {}, meta
    return (), {"username": username, "password": password, "host": host, "port": port_value}, meta


def trace_amazingdata_login(login_style: str = "keyword-int-port", heartbeat: HeartbeatCallback | None = None) -> dict:
    _emit_heartbeat(heartbeat, "load_config_start")
    config = load_login_config()
    trace = {
        "login_style": login_style,
        "config_source": str(config.get("config_source", "missing")),
        "ready": bool(config.get("ready")),
        "login_start": False,
        "login_returned": False,
        "login_result_type": "",
        "login_result_is_none": False,
        "login_result_repr_sanitized": "",
        "system_exit_during_login": False,
        "system_exit_code": None,
        "after_login_marker_reached": False,
        "status": "config_missing",
        "error_type": "config_missing",
        "error": "",
        "stage": "load_config",
        "port_type": "",
        "host_type": "str",
        "username_type": "str",
    }
    if not config.get("ready"):
        return trace
    _emit_heartbeat(heartbeat, "load_config_done", {"config_source": trace["config_source"]})
    _emit_heartbeat(heartbeat, "import_ad_start")
    try:
        import AmazingData as ad
    except BaseException as exc:
        err = _classify_bootstrap_error(exc, "import_ad", config)
        trace.update(
            {
                "status": err.status,
                "error_type": err.error_type,
                "error": err.message,
                "stage": err.stage,
            }
        )
        return trace
    _emit_heartbeat(heartbeat, "import_ad_done")
    login_args, login_kwargs, meta = build_login_invocation(config, login_style)
    trace.update(meta)
    trace["login_start"] = True
    _emit_heartbeat(heartbeat, "login_start", {"login_style": login_style, "port_type": trace["port_type"]})
    try:
        result = ad.login(*login_args, **login_kwargs)
        trace["login_returned"] = True
        trace["login_result_type"] = type(result).__name__
        trace["login_result_is_none"] = result is None
        trace["login_result_repr_sanitized"] = sanitize_text(repr(result), config)
        trace["status"] = "success"
        trace["error_type"] = ""
        trace["error"] = ""
        trace["stage"] = "login"
        _emit_heartbeat(heartbeat, "login_returned", {"result_type": trace["login_result_type"]})
    except BaseException as exc:
        err = _classify_bootstrap_error(exc, "login", config)
        trace["status"] = err.status
        trace["error_type"] = err.error_type
        trace["error"] = err.message
        trace["stage"] = err.stage
        if isinstance(exc, SystemExit):
            trace["system_exit_during_login"] = True
            trace["system_exit_code"] = getattr(exc, "code", None)
        _emit_heartbeat(heartbeat, "login_baseexception", {"error_type": trace["error_type"]})
        return trace
    trace["after_login_marker_reached"] = True
    _emit_heartbeat(heartbeat, "after_login_marker", {"after_login_marker_reached": True})
    try:
        ad.logout(str(config["username"]))
    except Exception:
        pass
    return trace


def bootstrap_amazingdata_client(
    heartbeat: HeartbeatCallback | None = None,
    login_style: str = "keyword-int-port",
) -> Tuple[object, Mapping[str, object]]:
    """Load config and run AmazingData login using the same signature as test_api.py."""
    _emit_heartbeat(heartbeat, "load_config_start")
    config = load_login_config()
    if not config.get("ready"):
        raise AmazingLoginError(
            status="bootstrap_failed",
            stage="load_config",
            error_type="config_missing",
            message="AmazingData credentials are not available in the current process.",
        )
    _emit_heartbeat(heartbeat, "load_config_done", {"config_source": str(config.get("config_source", ""))})
    _emit_heartbeat(heartbeat, "import_ad_start")
    try:
        import AmazingData as ad
    except BaseException as exc:
        raise _classify_bootstrap_error(exc, "import_ad", config) from exc
    _emit_heartbeat(heartbeat, "import_ad_done")

    _emit_heartbeat(heartbeat, "login_start")
    login_args, login_kwargs, _ = build_login_invocation(config, login_style)
    try:
        ad.login(*login_args, **login_kwargs)
    except BaseException as exc:
        raise _classify_bootstrap_error(exc, "login", config) from exc
    _emit_heartbeat(heartbeat, "login_done")
    return ad, config


def logout_amazingdata_client(ad_module, config: Mapping[str, object] | None) -> None:
    if ad_module is None or not config or not config.get("ready"):
        return
    try:
        ad_module.logout(str(config["username"]))
    except Exception:
        pass


def sanitized_login_context(config: Mapping[str, object]) -> Mapping[str, object]:
    return sanitized_config_status(config)
