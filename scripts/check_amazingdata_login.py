# -*- coding: utf-8 -*-
"""Validate AmazingData credential bootstrap and login without querying market data."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.amazing_login_client import AmazingLoginError, bootstrap_amazingdata_client, logout_amazingdata_client
from core.amazing_login_config import load_login_config, sanitize_text, sanitized_config_status
from utils.encoding import configure_utf8_console

EVAL_DIR = ROOT / "reports" / "analysis" / "evaluations"


def emit_heartbeat(heartbeat_path: Path | None, stage: str, started: float, extra: dict | None = None) -> None:
    if heartbeat_path is None:
        return
    payload = {
        "stage": stage,
        "elapsed_sec": round(time.time() - started, 4),
    }
    if extra:
        payload.update(extra)
    with heartbeat_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def read_last_heartbeat(heartbeat_path: Path | None) -> dict:
    if heartbeat_path is None or not heartbeat_path.exists():
        return {}
    lines = [line.strip() for line in heartbeat_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return {}
    try:
        return json.loads(lines[-1])
    except Exception:
        return {}


def perform_login_check(heartbeat_path: Path | None = None) -> dict:
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
    emit_heartbeat(heartbeat_path, "login_check_start", started)
    try:
        ad, _ = bootstrap_amazingdata_client(
            heartbeat=lambda stage, extra=None: emit_heartbeat(heartbeat_path, stage, started, dict(extra or {}))
        )
        payload["login_status"] = "success"
        payload["error_type"] = ""
        payload["error"] = ""
    except AmazingLoginError as exc:
        payload["login_status"] = exc.status
        payload["error_type"] = exc.error_type
        payload["error"] = exc.message
        emit_heartbeat(
            heartbeat_path,
            f"{exc.stage}_failed",
            started,
            {"error_type": exc.error_type},
        )
    finally:
        payload["elapsed_sec"] = round(time.time() - started, 4)
        logout_amazingdata_client(ad, config)
        emit_heartbeat(heartbeat_path, "login_check_done", started, {"login_status": payload["login_status"]})
    return payload


def classify_subprocess_failure(output: str, config: dict) -> dict:
    sanitized = sanitize_text(output, config)
    lowered = str(output or "").lower()
    if "login fail" in lowered or "tgw init failed" in lowered or "checklogonlegal" in lowered:
        return {
            "login_status": "login_failed",
            "error_type": "login_failed",
            "error": sanitized or "login_failed",
        }
    return {
        "login_status": "bootstrap_failed",
        "error_type": "bootstrap_failed",
        "error": sanitized or "bootstrap_failed",
    }


def run_login_check_isolated(timeout_sec: int = 90) -> dict:
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

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        result_path = Path(fh.name)
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as hb_fh:
        heartbeat_path = Path(hb_fh.name)
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--worker-result",
        str(result_path),
        "--heartbeat-path",
        str(heartbeat_path),
    ]
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=os.environ.copy(),
            timeout=int(timeout_sec),
            check=False,
        )
        if result_path.exists() and result_path.stat().st_size > 0:
            child_payload = json.loads(result_path.read_text(encoding="utf-8"))
            child_payload["elapsed_sec"] = round(time.time() - started, 4)
            child_payload["last_heartbeat_stage"] = read_last_heartbeat(heartbeat_path).get("stage", "")
            return child_payload
        merged_output = " ".join(part for part in [completed.stdout or "", completed.stderr or ""] if part).strip()
        payload.update(classify_subprocess_failure(merged_output, config))
        payload["elapsed_sec"] = round(time.time() - started, 4)
        payload["last_heartbeat_stage"] = read_last_heartbeat(heartbeat_path).get("stage", "")
        return payload
    except subprocess.TimeoutExpired:
        last_heartbeat = read_last_heartbeat(heartbeat_path)
        payload["login_status"] = "bootstrap_failed"
        payload["error_type"] = "bootstrap_timeout"
        payload["error"] = "bootstrap_timeout"
        payload["last_heartbeat_stage"] = last_heartbeat.get("stage", "")
        payload["elapsed_sec"] = round(time.time() - started, 4)
        return payload
    finally:
        result_path.unlink(missing_ok=True)
        heartbeat_path.unlink(missing_ok=True)


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
    if "--worker" in sys.argv:
        result_path = ""
        heartbeat_path = None
        if "--worker-result" in sys.argv:
            idx = sys.argv.index("--worker-result")
            if idx + 1 < len(sys.argv):
                result_path = sys.argv[idx + 1]
        if "--heartbeat-path" in sys.argv:
            idx = sys.argv.index("--heartbeat-path")
            if idx + 1 < len(sys.argv):
                heartbeat_path = Path(sys.argv[idx + 1])
        emit_heartbeat(heartbeat_path, "worker_process_start", time.time(), {"check": "login"})
        payload = perform_login_check(heartbeat_path=heartbeat_path)
        if result_path:
            Path(result_path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False))
        return

    payload = run_login_check_isolated()
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
