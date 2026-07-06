# -*- coding: utf-8 -*-
"""Run AmazingData login control-flow strategies in isolated subprocesses."""

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

from scripts.amazing_login_control_flow_probe import JSON_BEGIN, JSON_END, STRATEGY_CHOICES


DEFAULT_OUTPUT_DIR = ROOT / "reports" / "analysis" / "evaluations"
WORKER_SCRIPT = ROOT / "scripts" / "amazing_login_control_flow_probe.py"


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
            "safe_to_query": False,
        }
    body = raw[start + len(JSON_BEGIN) : end].strip()
    return json.loads(body)


def _strategy_list(strategies: str) -> list[str]:
    if not strategies or strategies == "all":
        return list(STRATEGY_CHOICES)
    return [item.strip() for item in strategies.split(",") if item.strip()]


def run_strategy(
    strategy: str,
    worker_python: str = "",
    worker_timeout: int = 45,
    login_style: str = "keyword-int-port",
    amazing_local_config: str = "",
) -> dict:
    python_exe = worker_python or sys.executable
    cmd = [python_exe, str(WORKER_SCRIPT), "--strategy", strategy, "--login-style", login_style]
    if amazing_local_config:
        cmd.extend(["--amazing-local-config", amazing_local_config])
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=int(worker_timeout),
            check=False,
        )
        payload = _extract_framed_json(completed.stdout)
        if strategy == "subprocess_exit_code_only" and payload.get("error_type") == "structured_json_missing":
            payload = {
                "strategy": strategy,
                "status": "system_exit" if completed.returncode == 0 else "failed",
                "system_exit_code": completed.returncode if completed.returncode == 0 else None,
                "login_returned": False,
                "safe_to_query": False,
                "permission_hypothesis": "possible",
                "post_system_exit_checks": {
                    "logout_callable": False,
                    "logout_returned": False,
                    "session_state_observable": False,
                },
                "notes": ["process_exited_without_framed_payload"],
            }
        payload.setdefault("strategy", strategy)
        payload["worker_returncode"] = completed.returncode
        payload["stderr_sanitized"] = _sanitize_text(completed.stderr)
        return payload
    except subprocess.TimeoutExpired:
        return {
            "strategy": strategy,
            "status": "failed",
            "error_type": "TimeoutExpired",
            "sanitized_error": "query_timeout",
            "safe_to_query": False,
            "permission_hypothesis": "possible",
            "post_system_exit_checks": {
                "logout_callable": False,
                "logout_returned": False,
                "session_state_observable": False,
            },
            "notes": ["worker_timeout"],
        }


def summarize(results: list[dict]) -> dict:
    safe = [row["strategy"] for row in results if row.get("safe_to_query") is True]
    system_exit = [row["strategy"] for row in results if row.get("status") == "system_exit"]
    failed = [row["strategy"] for row in results if row.get("status") == "failed"]
    if safe:
        decision = "amazingdata_query_allowed_after_followup"
    else:
        decision = "amazingdata_online_path_blocked_by_login_control_flow_or_permission"
    return {
        "safe_to_query": bool(safe),
        "safe_strategies": safe,
        "system_exit_strategies": system_exit,
        "failed_strategies": failed,
        "permission_hypothesis": "plausible_not_proven",
        "provider_fallback_decision": "prepare_ths_mcp_fallback" if not safe else "keep_amazingdata_gated",
        "amazingdata_online_path": "blocked" if not safe else "gated",
        "decision": decision,
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_markdown(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# P2.3F AmazingData Login Control-Flow Probe",
        "",
        "This report is diagnostic-only. It does not contain credential values, supplier logs, market data, trading instructions, or strategy changes.",
        "",
        "## Summary",
        "",
        f"- safe_to_query: `{payload['summary']['safe_to_query']}`",
        f"- AmazingData online path: `{payload['summary']['amazingdata_online_path']}`",
        f"- permission hypothesis: `{payload['summary']['permission_hypothesis']}`",
        f"- fallback decision: `{payload['summary']['provider_fallback_decision']}`",
        "",
        "## Strategy Results",
        "",
        "| strategy | status | system_exit_code | safe_to_query | permission_hypothesis | notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["results"]:
        notes = ", ".join(str(item) for item in row.get("notes", []))
        lines.append(
            f"| `{row.get('strategy', '')}` | `{row.get('status', '')}` | `{row.get('system_exit_code', '')}` | "
            f"`{row.get('safe_to_query', False)}` | `{row.get('permission_hypothesis', '')}` | `{notes}` |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "AmazingData online 09:35 backfill remains gated unless a strategy produces `safe_to_query=true`. Current fallback design should preserve the existing `stock_confirmation_0935.csv` artifact contract.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_probe(
    strategies: str,
    worker_python: str = "",
    worker_timeout: int = 45,
    login_style: str = "keyword-int-port",
    amazing_local_config: str = "",
) -> dict:
    results = [
        run_strategy(
            strategy,
            worker_python=worker_python,
            worker_timeout=worker_timeout,
            login_style=login_style,
            amazing_local_config=amazing_local_config,
        )
        for strategy in _strategy_list(strategies)
    ]
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "analysis_only": True,
        "strategies": _strategy_list(strategies),
        "login_style": login_style,
        "results": results,
        "summary": summarize(results),
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run AmazingData login control-flow probes.")
    parser.add_argument("--strategies", default="all")
    parser.add_argument("--worker-python", default="")
    parser.add_argument("--worker-timeout", type=int, default=45)
    parser.add_argument("--login-style", default="keyword-int-port")
    parser.add_argument("--amazing-local-config", default="")
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    payload = run_probe(
        strategies=args.strategies,
        worker_python=args.worker_python,
        worker_timeout=args.worker_timeout,
        login_style=args.login_style,
        amazing_local_config=args.amazing_local_config,
    )
    output_dir = Path(args.output_dir)
    json_path = Path(args.output_json) if args.output_json else output_dir / "amazing_login_control_flow_probe.json"
    md_path = Path(args.output_md) if args.output_md else output_dir / "amazing_login_control_flow_probe.md"
    payload["output_json"] = _repo_path(json_path)
    payload["output_md"] = _repo_path(md_path)
    if not args.dry_run:
        _write_json(json_path, payload)
        _write_markdown(md_path, payload)
    print(json.dumps({"dry_run": bool(args.dry_run), "result": payload}, ensure_ascii=False, indent=2))
    return payload


if __name__ == "__main__":
    main()
