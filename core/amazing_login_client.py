# -*- coding: utf-8 -*-
"""Shared AmazingData login helper aligned with the working SDK path."""

from __future__ import annotations

from typing import Mapping, Tuple

from core.amazing_login_config import load_login_config, sanitize_text, sanitized_config_status


class AmazingLoginError(RuntimeError):
    """Structured login/bootstrap error without leaking credentials."""

    def __init__(self, status: str, stage: str, error_type: str, message: str):
        super().__init__(message or error_type)
        self.status = status
        self.stage = stage
        self.error_type = error_type
        self.message = message or error_type


def bootstrap_amazingdata_client() -> Tuple[object, Mapping[str, object]]:
    """Load config and run AmazingData login using the same signature as test_api.py."""
    config = load_login_config()
    if not config.get("ready"):
        raise AmazingLoginError(
            status="bootstrap_failed",
            stage="load_config",
            error_type="config_missing",
            message="AmazingData credentials are not available in the current process.",
        )
    try:
        import AmazingData as ad
    except Exception as exc:
        raise AmazingLoginError(
            status="bootstrap_failed",
            stage="load_config",
            error_type="bootstrap_import_failed",
            message=sanitize_text(str(exc), config),
        ) from exc

    try:
        ad.login(
            username=str(config["username"]),
            password=str(config["password"]),
            host=str(config["host"]),
            port=int(str(config["port"])),
        )
    except Exception as exc:
        raise AmazingLoginError(
            status="login_failed",
            stage="login",
            error_type="login_failed",
            message=sanitize_text(str(exc), config),
        ) from exc
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
