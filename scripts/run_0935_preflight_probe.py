# -*- coding: utf-8 -*-
"""Run AmazingData 09:35 preflight probes against a candidate universe.

This parent runner is analysis-only. It invokes the preflight worker, captures
framed JSON/stage markers, writes sanitized probe reports, and never writes
09:35 confirmation artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_VALIDATION_ROOT = ROOT / "reports" / "validation" / "daily"
DEFAULT_OUTPUT_DIR = ROOT / "reports" / "analysis" / "evaluations"
WORKER_SCRIPT = ROOT / "scripts" / "amazing_0935_preflight_probe.py"
STAGE_MARKER = "__AMAZING_PREFLIGHT_STAGE__"
DONE_MARKER = "__AMAZING_PREFLIGHT_DONE__"


def _repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _candidate_source(date: str, validation_root: Path, explicit: str = "") -> Path:
    if explicit:
        return Path(explicit)
    return validation_root / str(date) / "signal_detail.csv"


def _read_candidate_codes(path: Path, max_codes: int) -> tuple[list[str], int]:
    if not path.exists():
        return [], 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    codes: list[str] = []
    for row in rows:
        code = str(row.get("code", "") or "").strip()
        if code and code not in codes:
            codes.append(code)
        if len(codes) >= max_codes:
            break
    return codes, len(rows)


def _sanitize_text(text: str) -> str:
    lowered = str(text or "").lower()
    if any(marker in lowered for marker in ("password", "token", "secret", "host=", "port=", "username")):
        return "sensitive_error_redacted"
    try:
        from core.amazing_login_config import load_login_config, sanitize_text

        return sanitize_text(text, load_login_config())
    except Exception:
        return str(text or "")[-240:]


def _extract_marked_payloads(text: str, marker: str) -> list[dict]:
    payloads: list[dict] = []
    parts = str(text or "").split(marker)
    for part in parts[1:]:
        lines = [line for line in part.strip().splitlines() if line.strip()]
        if not lines:
            continue
        try:
            payloads.append(json.loads(lines[0]))
        except json.JSONDecodeError:
            continue
    return payloads


def _extract_done_payload(text: str) -> dict:
    payloads = _extract_marked_payloads(text, DONE_MARKER)
    if not payloads:
        return {
            "status": "failed",
            "first_failing_stage": "preflight_done_marker_missing",
            "error_type": "structured_json_missing",
            "sanitized_error": "structured_json_missing",
            "row_count": 0,
            "rows": [],
        }
    return payloads[-1]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_markdown(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stages = payload.get("stages", [])
    lines = [
        "# P2.3D AmazingData 09:35 Preflight Probe",
        "",
        "This report is diagnostic-only. It does not contain credentials, supplier logs, full-market dumps, trading instructions, or strategy changes.",
        "",
        "## Summary",
        "",
        f"- date: `{payload.get('date', '')}`",
        f"- mode: `{payload.get('mode', '')}`",
        f"- status: `{payload.get('status', '')}`",
        f"- candidate source: `{payload.get('candidate_source', '')}`",
        f"- candidate rows: `{payload.get('candidate_count', 0)}`",
        f"- probed codes: `{payload.get('probe_code_count', 0)}`",
        f"- first failing stage: `{payload.get('first_failing_stage', '') or 'none'}`",
        f"- row count: `{payload.get('row_count', 0)}`",
        "",
        "## Stage Results",
        "",
        "| stage | status | notes |",
        "| --- | --- | --- |",
    ]
    for stage in stages:
        note = stage.get("sanitized_error") or stage.get("error_type") or stage.get("row_count") or stage.get("ready") or ""
        lines.append(f"| `{stage.get('stage', '')}` | `{stage.get('status', '')}` | `{note}` |")
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- Candidate-only diagnostic probe.",
            "- No full-market query.",
            "- No lesson, pattern, registry, evaluator, config, strategy, or trading-execution writes.",
            "- Probe labels are posterior data-availability diagnostics, not trading advice.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_probe(
    date: str,
    mode: str,
    candidate_source: Path,
    max_codes: int = 3,
    worker_python: str = "",
    worker_timeout: int = 60,
    amazing_local_config: str = "",
    query_window_start: str = "93500000",
    query_window_end: str = "93559999",
) -> dict:
    codes, candidate_count = _read_candidate_codes(candidate_source, max_codes)
    if not candidate_source.exists():
        return {
            "status": "candidate_source_missing",
            "date": date,
            "mode": mode,
            "candidate_source": _repo_path(candidate_source),
            "candidate_count": 0,
            "probe_code_count": 0,
            "first_failing_stage": "candidate_source",
            "stages": [],
            "rows": [],
            "row_count": 0,
        }
    request = {
        "date": str(date),
        "codes": codes,
        "mode": mode,
        "query_window_start": int(query_window_start),
        "query_window_end": int(query_window_end),
        "amazing_local_config": amazing_local_config or "",
        "max_codes": int(max_codes),
    }
    python_exe = worker_python or sys.executable
    try:
        result = subprocess.run(
            [python_exe, str(WORKER_SCRIPT)],
            input=json.dumps(request, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=int(worker_timeout),
            cwd=str(ROOT),
            check=False,
        )
        stages = _extract_marked_payloads(result.stdout, STAGE_MARKER)
        payload = _extract_done_payload(result.stdout)
        payload["stages"] = payload.get("stages") or stages
        payload["worker_returncode"] = result.returncode
        payload["stderr_sanitized"] = _sanitize_text(result.stderr)
    except subprocess.TimeoutExpired:
        payload = {
            "status": "failed",
            "mode": mode,
            "date": date,
            "first_failing_stage": "worker_timeout",
            "error_type": "TimeoutExpired",
            "sanitized_error": "query_timeout",
            "stages": [],
            "rows": [],
            "row_count": 0,
        }
    payload.update(
        {
            "date": date,
            "mode": mode,
            "candidate_source": _repo_path(candidate_source),
            "candidate_count": candidate_count,
            "probe_code_count": len(codes),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "analysis_only": True,
            "no_full_market_query": True,
        }
    )
    return payload


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run AmazingData 09:35 preflight probe.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--candidate-source", default="")
    parser.add_argument("--validation-root", default=str(DEFAULT_VALIDATION_ROOT))
    parser.add_argument("--mode", choices=("import-only", "login-only", "snapshot-preflight", "min1-preflight"), default="import-only")
    parser.add_argument("--max-codes", type=int, default=3)
    parser.add_argument("--worker-python", default="")
    parser.add_argument("--worker-timeout", type=int, default=60)
    parser.add_argument("--amazing-local-config", default="")
    parser.add_argument("--query-window-start", default="93500000")
    parser.add_argument("--query-window-end", default="93559999")
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    candidate = _candidate_source(args.date, Path(args.validation_root), args.candidate_source)
    payload = run_probe(
        date=args.date,
        mode=args.mode,
        candidate_source=candidate,
        max_codes=args.max_codes,
        worker_python=args.worker_python,
        worker_timeout=args.worker_timeout,
        amazing_local_config=args.amazing_local_config,
        query_window_start=args.query_window_start,
        query_window_end=args.query_window_end,
    )
    output_dir = Path(args.output_dir)
    json_path = Path(args.output_json) if args.output_json else output_dir / f"amazing_0935_preflight_{args.date}.json"
    md_path = Path(args.output_md) if args.output_md else output_dir / f"amazing_0935_preflight_{args.date}.md"
    payload["output_json"] = _repo_path(json_path)
    payload["output_md"] = _repo_path(md_path)
    if not args.dry_run:
        _write_json(json_path, payload)
        _write_markdown(md_path, payload)
    print(json.dumps({"dry_run": bool(args.dry_run), "result": payload}, ensure_ascii=False, indent=2))
    return payload


if __name__ == "__main__":
    main()
