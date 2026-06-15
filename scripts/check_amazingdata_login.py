# -*- coding: utf-8 -*-
"""Validate AmazingData credential bootstrap and login without querying market data."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.amazing_login_config import load_login_config, sanitize_text, sanitized_config_status
from utils.encoding import configure_utf8_console

EVAL_DIR = ROOT / "reports" / "analysis" / "evaluations"


def perform_login_check() -> dict:
    config = load_login_config()
    started = time.time()
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_sec": 0.0,
        "login_status": "config_missing",
        "error_type": "config_missing",
        "error": "",
        "config_status": sanitized_config_status(config),
    }
    if not config.get("ready"):
        payload["elapsed_sec"] = round(time.time() - started, 4)
        return payload

    ad = None
    try:
        import AmazingData as ad

        ad.login(
            username=str(config["username"]),
            password=str(config["password"]),
            host=str(config["host"]),
            port=int(str(config["port"])),
        )
        payload["login_status"] = "success"
        payload["error_type"] = ""
        payload["error"] = ""
        return payload
    except Exception as exc:
        payload["login_status"] = "login_failed"
        payload["error_type"] = "login_failed"
        payload["error"] = sanitize_text(str(exc), config)
        return payload
    finally:
        payload["elapsed_sec"] = round(time.time() - started, 4)
        if ad is not None:
            try:
                ad.logout(str(config["username"]))
            except Exception:
                pass


def write_outputs(payload: dict) -> tuple[Path, Path]:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    json_path = EVAL_DIR / "amazing_login_check.json"
    md_path = EVAL_DIR / "amazing_login_check.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    status = payload["config_status"]
    lines = [
        "# AmazingData Login Check",
        "",
        "## 1. Config Status",
        "",
        f"- config_source: `{status['config_source']}`",
        f"- username_present: `{status['username_present']}`",
        f"- password_present: `{status['password_present']}`",
        f"- host_present: `{status['host_present']}`",
        f"- port_present: `{status['port_present']}`",
        f"- ready: `{status['ready']}`",
        "",
        "## 2. Login Result",
        "",
        f"- login_status: `{payload['login_status']}`",
        f"- elapsed_sec: `{payload['elapsed_sec']}`",
        f"- error_type: `{payload['error_type'] or '-'}`",
        f"- error: `{payload['error'] or '-'}`",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main():
    configure_utf8_console()
    payload = perform_login_check()
    json_path, md_path = write_outputs(payload)
    print(
        json.dumps(
            {
                "json": str(json_path.relative_to(ROOT)),
                "md": str(md_path.relative_to(ROOT)),
                "login_status": payload["login_status"],
                "ready": payload["config_status"]["ready"],
                "config_source": payload["config_status"]["config_source"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
