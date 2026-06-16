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


def bootstrap_amazingdata_client(heartbeat: HeartbeatCallback | None = None) -> Tuple[object, Mapping[str, object]]:
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
    try:
        ad.login(
            username=str(config["username"]),
            password=str(config["password"]),
            host=str(config["host"]),
            port=int(str(config["port"])),
        )
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
