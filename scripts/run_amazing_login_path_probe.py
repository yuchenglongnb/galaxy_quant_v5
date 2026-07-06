# -*- coding: utf-8 -*-
"""Run AmazingData login path probes in isolated subprocesses."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.amazing_login_path_probe import JSON_BEGIN, JSON_END, STYLE_CHOICES


DEFAULT_OUTPUT_DIR = ROOT / "reports" / "analysis" / "evaluations"
WORKER_SCRIPT = ROOT / "scripts" / "amazing_login_path_probe.py"


def _repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _sanitize_text(text: str) -> str:
    lowered = str(text or "").lower()
    if any(marker in lowered for marker in ("password", "token", "secret", "host=", "port=", "username")):
        return "sensitive_error_redacted"
    try:
        from core.amazing_login_config import load_login_config, sanitize_text

        return sanitize_text(text, load_login_config())
    except Exception:
        return str(text or "")[-240:]


def _extract_framed_json(text: str) -> dict:
    raw = str(text or "")
    start = raw.rfind(JSON_BEGIN)
    end = raw.rfind(JSON_END)
    if start == -1 or end == -1 or end <= start:
        return {
            "status": "failed",
            "error_type": "structured_json_missing",
            "sanitized_error": "structured_json_missing",
        }
    body = raw[start + len(JSON_BEGIN) : end].strip()
    return json.loads(body)


def _style_list(styles: str) -> list[str]:
    if not styles or styles == "all":
        return list(STYLE_CHOICES)
    return [item.strip() for item in styles.split(",") if item.strip()]


def run_style(style: str, worker_python: str = "", worker_timeout: int = 45, amazing_local_config: str = "") -> dict:
    python_exe = worker_python or sys.executable
    cmd = [python_exe, str(WORKER_SCRIPT), "--style", style]
    if amazing_local_config:
        cmd.extend(["--amazing-local-config", amazing_local_config])
    try:
        result = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=int(worker_timeout),
            check=False,
        )
        payload = _extract_framed_json(result.stdout)
        payload["worker_returncode"] = result.returncode
        payload["stderr_sanitized"] = _sanitize_text(result.stderr)
        payload.setdefault("style", style)
        return payload
    except subprocess.TimeoutExpired:
        return {
            "style": style,
            "status": "failed",
            "error_type": "TimeoutExpired",
            "sanitized_error": "query_timeout",
            "system_exit_code": None,
            "ambiguous_success": False,
            "login_returned": False,
            "logout_attempted": False,
            "config_status": {},
            "notes": ["worker_timeout"],
        }


def summarize(results: list[dict]) -> dict:
    successful = [row["style"] for row in results if row.get("status") == "ok"]
    system_exit = [row["style"] for row in results if row.get("status") == "system_exit"]
    failed = [row["style"] for row in results if row.get("status") == "failed"]
    if successful:
        diagnosis = "successful_login_style_found"
    elif system_exit and all(row.get("system_exit_code") == 0 for row in results if row.get("status") == "system_exit"):
        diagnosis = "all_available_styles_system_exit_0_or_failed"
    elif system_exit:
        diagnosis = "system_exit_login_path"
    else:
        diagnosis = "all_styles_failed"
    return {
        "successful_styles": successful,
        "system_exit_styles": system_exit,
        "failed_styles": failed,
        "diagnosis": diagnosis,
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_markdown(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# P2.3E AmazingData Login Path Probe",
        "",
        "This report is diagnostic-only. It does not contain credential values, supplier logs, market data, trading instructions, or strategy changes.",
        "",
        "## Summary",
        "",
        f"- diagnosis: `{payload['summary']['diagnosis']}`",
        f"- successful_styles: `{', '.join(payload['summary']['successful_styles']) or '-'}`",
        f"- system_exit_styles: `{', '.join(payload['summary']['system_exit_styles']) or '-'}`",
        f"- failed_styles: `{', '.join(payload['summary']['failed_styles']) or '-'}`",
        "",
        "## Style Results",
        "",
        "| style | status | system_exit_code | ambiguous_success | login_returned | logout_attempted | error_type | sanitized_error |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["results"]:
        lines.append(
            f"| `{row.get('style', '')}` | `{row.get('status', '')}` | `{row.get('system_exit_code', '')}` | "
            f"`{row.get('ambiguous_success', False)}` | `{row.get('login_returned', False)}` | "
            f"`{row.get('logout_attempted', False)}` | `{row.get('error_type', '')}` | `{row.get('sanitized_error', '')}` |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "`SystemExit(0)` is classified as ambiguous login control flow, not as a successful login. Query/backfill is gated behind a style with `status=ok`.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_probe(styles: str, worker_python: str = "", worker_timeout: int = 45, amazing_local_config: str = "") -> dict:
    results = [
        run_style(
            style,
            worker_python=worker_python,
            worker_timeout=worker_timeout,
            amazing_local_config=amazing_local_config,
        )
        for style in _style_list(styles)
    ]
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "analysis_only": True,
        "styles": _style_list(styles),
        "results": results,
        "summary": summarize(results),
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run AmazingData login path style probes.")
    parser.add_argument("--styles", default="all")
    parser.add_argument("--worker-python", default="")
    parser.add_argument("--worker-timeout", type=int, default=45)
    parser.add_argument("--amazing-local-config", default="")
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    payload = run_probe(
        styles=args.styles,
        worker_python=args.worker_python,
        worker_timeout=args.worker_timeout,
        amazing_local_config=args.amazing_local_config,
    )
    output_dir = Path(args.output_dir)
    json_path = Path(args.output_json) if args.output_json else output_dir / "amazing_login_path_probe.json"
    md_path = Path(args.output_md) if args.output_md else output_dir / "amazing_login_path_probe.md"
    payload["output_json"] = _repo_path(json_path)
    payload["output_md"] = _repo_path(md_path)
    if not args.dry_run:
        _write_json(json_path, payload)
        _write_markdown(md_path, payload)
    print(json.dumps({"dry_run": bool(args.dry_run), "result": payload}, ensure_ascii=False, indent=2))
    return payload


if __name__ == "__main__":
    main()
