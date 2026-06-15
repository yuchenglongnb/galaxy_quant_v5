# -*- coding: utf-8 -*-
"""Safe AmazingData login config loading and sanitization helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, Mapping

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOTENV_PATH = ROOT / ".env"
SENSITIVE_KEYS = ("username", "password", "host", "port", "server_vip", "token")


def _read_dotenv(path: Path | None = None) -> Dict[str, str]:
    dotenv_path = Path(path or DEFAULT_DOTENV_PATH)
    if not dotenv_path.exists():
        return {}
    values: Dict[str, str] = {}
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _read_windows_persistent_env(scope: str) -> Dict[str, str]:
    if sys.platform != "win32":
        return {}
    try:
        import winreg
    except Exception:
        return {}

    hive = winreg.HKEY_CURRENT_USER if scope == "user" else winreg.HKEY_LOCAL_MACHINE
    subkey = r"Environment" if scope == "user" else r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
    values: Dict[str, str] = {}
    try:
        with winreg.OpenKey(hive, subkey) as key:
            for name in ("AD_USERNAME", "AD_PASSWORD", "AD_HOST", "AD_PORT"):
                try:
                    value, _ = winreg.QueryValueEx(key, name)
                except FileNotFoundError:
                    continue
                values[name] = str(value or "").strip()
    except Exception:
        return {}
    return values


def load_login_config(env: Mapping[str, str] | None = None, dotenv_path: Path | None = None) -> Dict[str, object]:
    source_env = dict(env or os.environ)
    dotenv_values = _read_dotenv(dotenv_path)
    user_env = _read_windows_persistent_env("user")
    machine_env = _read_windows_persistent_env("machine")

    def pick(key: str) -> str:
        env_value = str(source_env.get(key, "") or "").strip()
        if env_value:
            return env_value
        user_value = str(user_env.get(key, "") or "").strip()
        if user_value:
            return user_value
        machine_value = str(machine_env.get(key, "") or "").strip()
        if machine_value:
            return machine_value
        return str(dotenv_values.get(key, "") or "").strip()

    username = pick("AD_USERNAME")
    password = pick("AD_PASSWORD")
    host = pick("AD_HOST")
    port_raw = pick("AD_PORT")
    port = str(port_raw).strip()
    source = "missing"
    if username and password and host and port:
        env_keys = ("AD_USERNAME", "AD_PASSWORD", "AD_HOST", "AD_PORT")
        if all(str(source_env.get(key, "") or "").strip() for key in env_keys):
            source = "env"
        elif all(str(user_env.get(key, "") or "").strip() for key in env_keys):
            source = "windows_user_env"
        elif all(str(machine_env.get(key, "") or "").strip() for key in env_keys):
            source = "windows_machine_env"
        else:
            source = "dotenv"

    return {
        "username": username,
        "password": password,
        "host": host,
        "port": port,
        "config_source": source,
        "username_present": bool(username),
        "password_present": bool(password),
        "host_present": bool(host),
        "port_present": bool(port),
        "ready": bool(username and password and host and port),
    }


def sanitized_config_status(config: Mapping[str, object]) -> Dict[str, object]:
    return {
        "config_source": str(config.get("config_source", "missing")),
        "username_present": bool(config.get("username_present")),
        "password_present": bool(config.get("password_present")),
        "host_present": bool(config.get("host_present")),
        "port_present": bool(config.get("port_present")),
        "ready": bool(config.get("ready")),
    }


def sanitize_text(text: str, config: Mapping[str, object] | None = None) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    sanitized = raw
    if config:
        for key in ("username", "password", "host", "port"):
            value = str(config.get(key, "") or "").strip()
            if value:
                sanitized = sanitized.replace(value, "[REDACTED]")
    lowered = sanitized.lower()
    if "checklogonlegal" in lowered:
        return "login_failed: tgw_login_validation_failed"
    if "tgw init failed" in lowered or "internet mode of tgw init failed" in lowered:
        return "login_failed: tgw_init_failed"
    if "login fail" in lowered:
        return "login_failed: login_fail"
    if "server_vip" in lowered:
        return "login_failed: invalid_server_config"
    if "timed out" in lowered or lowered == "timeout":
        return "query_timeout"
    if any(marker in lowered for marker in SENSITIVE_KEYS):
        return "sensitive_error_redacted"
    lines = [line.strip() for line in sanitized.splitlines() if line.strip()]
    return lines[-1][:240] if lines else ""
