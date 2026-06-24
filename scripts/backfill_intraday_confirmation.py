# -*- coding: utf-8 -*-
"""Replay-date intraday confirmation backfill with stage isolation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.data_manager import DataManager
from scripts.backfill_intraday_cache import resolve_minimal_universe
from scripts.diagnose_intraday_confirmation_backfill import build_payload as build_diag_payload
from scripts.diagnose_trend_gate_coverage import build_payload as build_trend_payload
from analyzers.auction import AuctionAnalyzer
from utils.encoding import configure_utf8_console

EVAL_DIR = ROOT / "reports" / "analysis" / "evaluations"
PROGRESS_PATH = EVAL_DIR / "intraday_backfill_progress.jsonl"
PROBE_PATH = EVAL_DIR / "amazing_kline_time_param_probe_20260616.json"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _written_files(target_date: int) -> list[str]:
    intraday_dir = ROOT / "AmazingData_Store" / str(int(target_date)) / "intraday"
    files = []
    for name in ("stocks_1min.csv", "etf_1min.csv", "indices_1min.csv", "stock_confirmation_latest.csv"):
        path = intraday_dir / name
        if path.exists():
            files.append(str(path.relative_to(ROOT)))
    return files


def _parse_only_codes(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _has_sector_positive_evidence(candidate: dict) -> bool:
    evidence = set(candidate.get("leading_cluster_evidence", []) or [])
    return bool(
        evidence
        & {
            "sector_strength_score_confirmed",
            "sector_breadth_strength_confirmed",
            "sector_limitup_breadth_confirmed",
            "sector_money_flow_confirmed",
        }
    )


def _rank_stock_candidates(target_date: int, dm: DataManager, selection_priority: str) -> list[str]:
    if selection_priority == "original":
        return []

    analyzer = AuctionAnalyzer(dm)
    result = analyzer.analyze(int(target_date), realtime=False)
    if result is None:
        return []

    trend_signals = list(((result.get("signals") or {}).get("trend")) or [])
    stock_signals = [
        signal
        for signal in trend_signals
        if str(((signal.get("data") or {}).get("target_type", "") or "")).lower() == "stock"
    ]
    ranked_rows = []
    for index, signal in enumerate(stock_signals):
        data = signal.get("data", {}) or {}
        code = str(data.get("code", "") or "")
        if not code:
            continue
        leading_status = str(signal.get("leading_cluster_status", "") or "")
        leading_strength = float(signal.get("leading_cluster_strength", 0) or 0.0)
        action_score = float(signal.get("action_score", 0) or 0.0)
        trend_filter_decision = str(signal.get("trend_filter_decision", "keep") or "keep")
        sector_positive = _has_sector_positive_evidence(signal)
        cp_decision = str(signal.get("cp_risk_decision", "") or "")
        leading_rank = 0
        if leading_status == "active":
            leading_rank = 2
        elif leading_status == "partial":
            leading_rank = 1
        cp_rank = 1 if cp_decision in {"crowded_observe", "leading_cluster_exempt"} else 0
        ranked_rows.append(
            {
                "code": code,
                "original_index": index,
                "leading_rank": leading_rank,
                "leading_strength": leading_strength,
                "sector_positive": 1 if sector_positive else 0,
                "action_score": action_score,
                "cp_rank": cp_rank,
                "trend_keep": 1 if trend_filter_decision == "keep" else 0,
            }
        )

    if selection_priority == "leading_cluster":
        ranked_rows.sort(
            key=lambda row: (
                -row["leading_rank"],
                -row["sector_positive"],
                -row["cp_rank"],
                -row["leading_strength"],
                -row["action_score"],
                row["original_index"],
            )
        )
    elif selection_priority == "sector_positive":
        ranked_rows.sort(
            key=lambda row: (
                -row["sector_positive"],
                -row["leading_rank"],
                -row["cp_rank"],
                -row["leading_strength"],
                -row["action_score"],
                row["original_index"],
            )
        )
    elif selection_priority == "trend_score":
        ranked_rows.sort(
            key=lambda row: (
                -row["action_score"],
                -row["leading_rank"],
                -row["sector_positive"],
                -row["trend_keep"],
                row["original_index"],
            )
        )
    else:
        return []

    seen = set()
    ordered_codes = []
    for row in ranked_rows:
        code = row["code"]
        if code in seen:
            continue
        seen.add(code)
        ordered_codes.append(code)
    return ordered_codes


def _filter_universe(
    universe: dict,
    stage: str,
    max_stocks: int,
    only_codes: list[str],
    selection_priority: str = "original",
) -> dict:
    filtered = dict(universe)
    stock_codes = list(universe.get("stock_codes", []))
    etf_codes = list(universe.get("etf_codes", []))
    index_codes = list(universe.get("index_codes", []))
    only_set = set(only_codes or [])
    prioritized_stock_codes = list(universe.get("prioritized_stock_codes", []) or [])

    if selection_priority != "original" and prioritized_stock_codes:
        ordered = [code for code in prioritized_stock_codes if code in stock_codes]
        remaining = [code for code in stock_codes if code not in set(ordered)]
        stock_codes = ordered + remaining

    if only_set:
        stock_codes = [code for code in stock_codes if code in only_set]
        etf_codes = [code for code in etf_codes if code in only_set]
        index_codes = [code for code in index_codes if code in only_set]

    if max_stocks and int(max_stocks) > 0:
        stock_codes = stock_codes[: int(max_stocks)]

    if stage == "index":
        etf_codes = []
        stock_codes = []
    elif stage == "etf":
        index_codes = []
        stock_codes = []
    elif stage == "stock":
        index_codes = []
        etf_codes = []
    elif stage == "confirmation":
        index_codes = []
        etf_codes = []

    filtered["stock_codes"] = stock_codes
    filtered["etf_codes"] = etf_codes
    filtered["index_codes"] = index_codes
    filtered["selection_priority"] = str(selection_priority or "original")
    filtered["selected_stock_preview"] = stock_codes[: min(len(stock_codes), 20)]
    return filtered


def _summarize_stage_events(date: int, start_index: int, stage: str) -> dict:
    rows = [
        row
        for row in _read_jsonl(PROGRESS_PATH)[start_index:]
        if str(row.get("date", "")) == str(int(date))
    ]
    stage_rows = rows if stage == "all" else [row for row in rows if str(row.get("stage", "")).startswith(stage)]
    batches = [
        row for row in rows
        if str(row.get("stage", "")).endswith("_batch")
    ]
    return {
        "events": stage_rows,
        "slow_batches": [
            row for row in batches
            if str(row.get("warning", "") or "").startswith("batch_elapsed_exceeded")
        ],
        "failed_batches": [row for row in batches if row.get("status") == "failed"],
    }


def _load_probe_payload(target_date: int, code: str) -> dict:
    path = EVAL_DIR / f"amazing_kline_time_param_probe_{int(target_date)}.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if str(payload.get("code", "")) != str(code):
        return {}
    return payload


def _write_bootstrap_compare_report(target_date: int, code: str, payload: dict) -> None:
    probe_payload = _load_probe_payload(int(target_date), str(code))
    cases = []
    for item in probe_payload.get("results", []) if probe_payload else []:
        cases.append(
            {
                "mode": f"probe_worker:{item.get('case', '')}",
                "status": item.get("status", ""),
                "row_count": int(item.get("row_count", 0) or 0),
                "elapsed_sec": float(item.get("elapsed_sec", 0.0) or 0.0),
                "error": item.get("error", ""),
            }
        )
    stage_isolation = payload.get("stage_isolation", {}) or {}
    stage_events = stage_isolation.get("events", []) or []
    batch_events = [row for row in stage_events if str(row.get("stage", "")).endswith("_batch")]
    latest_batch = batch_events[-1] if batch_events else {}
    cases.append(
        {
            "mode": "backfill_isolated_query" if payload.get("isolated_query") else "backfill_default",
            "status": payload.get("rebuild_result", {}).get("reason")
            or ("ok" if payload.get("written_files") else "failed"),
            "row_count": int(latest_batch.get("row_count", 0) or 0),
            "elapsed_sec": float(latest_batch.get("elapsed_sec", 0.0) or 0.0),
            "error": latest_batch.get("error", "") or "",
        }
    )
    compare = {
        "date": str(int(target_date)),
        "code": str(code),
        "cases": cases,
        "conclusion": "",
    }
    json_path = EVAL_DIR / f"intraday_backfill_bootstrap_compare_{int(target_date)}.json"
    md_path = EVAL_DIR / f"intraday_backfill_bootstrap_compare_{int(target_date)}.md"
    json_path.write_text(json.dumps(compare, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"# Intraday Backfill Bootstrap Compare {int(target_date)}",
        "",
        f"- code: `{code}`",
        "",
        "| mode | status | row_count | elapsed_sec | error |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for item in cases:
        lines.append(
            f"| {item['mode']} | {item['status']} | {int(item['row_count'])} | "
            f"{float(item['elapsed_sec']):.4f} | {item['error'] or '-'} |"
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")


def run_backfill(
    target_date: int,
    execute: bool,
    force: bool,
    stage: str,
    max_stocks: int,
    only_codes: list[str],
    begin_time: int,
    end_time: int,
    batch_size: int,
    skip_existing: bool,
    warn_after_sec: float,
    isolated_query: bool,
    selection_priority: str = "original",
) -> dict:
    dm = DataManager()
    universe = resolve_minimal_universe(int(target_date), dm)
    universe["prioritized_stock_codes"] = _rank_stock_candidates(int(target_date), dm, selection_priority)
    filtered_universe = _filter_universe(
        universe,
        stage,
        max_stocks=max_stocks,
        only_codes=only_codes,
        selection_priority=selection_priority,
    )
    before = build_diag_payload(int(target_date))
    progress_start = len(_read_jsonl(PROGRESS_PATH))

    result = {
        "date": str(int(target_date)),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "execute": bool(execute),
        "force": bool(force),
        "dry_run": not bool(execute),
        "stage": stage,
        "begin_time": int(begin_time),
        "end_time": int(end_time),
        "batch_size": int(batch_size),
        "max_stocks": int(max_stocks or 0),
        "only_codes": list(only_codes or []),
        "skip_existing": bool(skip_existing),
        "warn_after_sec": float(warn_after_sec or 0.0),
        "isolated_query": bool(isolated_query),
        "selection_priority": str(selection_priority or "original"),
        "universe": filtered_universe,
        "before": before,
        "rebuild_result": {
            "rebuilt": False,
            "skipped": True,
            "reason": "dry_run",
        },
        "written_files": [],
        "after_confirmation_available": before["current_confirmation_available"],
        "after_signal_enriched_count": 0,
        "after_rs_vs_etf_coverage": 0.0,
        "after_rs_vs_index_coverage": 0.0,
        "after_amount_1m_ratio_coverage": 0.0,
        "after_shadow_distribution": {},
        "stage_isolation": {
            "events": [],
            "slow_batches": [],
            "failed_batches": [],
        },
    }

    if execute:
        rebuild = dm.rebuild_intraday_confirmation_from_snapshot(
            int(target_date),
            force=force,
            stock_codes=filtered_universe.get("stock_codes") or None,
            etf_codes=filtered_universe.get("etf_codes") or None,
            index_codes=filtered_universe.get("index_codes") or None,
            mode="minimal",
            data_kind="min1",
            warn_after_sec=warn_after_sec,
            progress_path=str(PROGRESS_PATH),
            stage=stage,
            begin_hhmm=begin_time,
            end_hhmm=end_time,
            batch_size=batch_size,
            max_stocks=max_stocks,
            only_codes=only_codes,
            skip_existing=skip_existing,
            isolated_query=isolated_query,
        )
        result["rebuild_result"] = rebuild
        result["written_files"] = _written_files(int(target_date))
        result["stage_isolation"] = _summarize_stage_events(int(target_date), progress_start, stage)

        after_diag = build_diag_payload(int(target_date))
        after_trend = build_trend_payload(int(target_date))
        result["after"] = after_diag
        result["after_confirmation_available"] = after_diag["current_confirmation_available"]
        result["after_signal_enriched_count"] = int(
            ((after_trend.get("intraday_confirmation_status") or {}).get("signal_enriched_count", 0) or 0)
        )
        overall = after_trend.get("overall_coverage", {}) or {}
        result["after_rs_vs_etf_coverage"] = float(overall.get("rs_vs_etf_coverage", 0.0) or 0.0)
        result["after_rs_vs_index_coverage"] = float(overall.get("rs_vs_index_coverage", 0.0) or 0.0)
        result["after_amount_1m_ratio_coverage"] = float(overall.get("amount_1m_ratio_coverage", 0.0) or 0.0)
        result["after_shadow_distribution"] = dict(overall.get("shadow_distribution", {}) or {})
        if stage == "index" and len(filtered_universe.get("index_codes", []) or []) == 1:
            _write_bootstrap_compare_report(
                int(target_date),
                str((filtered_universe.get("index_codes") or [""])[0]),
                result,
            )

    return result


def write_outputs(payload: dict) -> tuple[Path, Path]:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "execute" if payload["execute"] else "dry_run"
    json_path = EVAL_DIR / f"intraday_confirmation_backfill_{payload['date']}_{payload['stage']}_{suffix}.json"
    md_path = EVAL_DIR / f"intraday_confirmation_backfill_{payload['date']}_{payload['stage']}_{suffix}.md"
    stage_json = EVAL_DIR / f"intraday_backfill_stage_isolation_{payload['date']}.json"
    stage_md = EVAL_DIR / f"intraday_backfill_stage_isolation_{payload['date']}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    stage_json.write_text(json.dumps(payload["stage_isolation"], ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Intraday Confirmation Backfill {payload['date']}",
        "",
        f"- execute: `{payload['execute']}`",
        f"- dry_run: `{payload['dry_run']}`",
        f"- force: `{payload['force']}`",
        f"- stage: `{payload['stage']}`",
        f"- begin_time: `{payload['begin_time']}`",
        f"- end_time: `{payload['end_time']}`",
        f"- batch_size: `{payload['batch_size']}`",
        f"- max_stocks: `{payload['max_stocks']}`",
        f"- only_codes: `{payload['only_codes']}`",
        f"- skip_existing: `{payload['skip_existing']}`",
        f"- isolated_query: `{payload['isolated_query']}`",
        f"- selection_priority: `{payload['selection_priority']}`",
        "",
        "## Before",
        "",
        f"- stock_trend_total: `{payload['before']['stock_trend_total']}`",
        f"- current_confirmation_available: `{payload['before']['current_confirmation_available']}`",
        f"- missing_stock_intraday_count: `{payload['before']['missing_stock_intraday_count']}`",
        f"- missing_benchmark_etf_intraday_count: `{payload['before']['missing_benchmark_etf_intraday_count']}`",
        f"- missing_benchmark_index_intraday_count: `{payload['before']['missing_benchmark_index_intraday_count']}`",
        f"- board_index_codes_used: `{payload['before']['board_index_codes_used']}`",
        f"- selected_stock_preview: `{payload['universe'].get('selected_stock_preview', [])}`",
        "",
        "## Rebuild Result",
        "",
        f"- result: `{payload['rebuild_result']}`",
        f"- written_files: `{payload['written_files']}`",
        "",
        "## After",
        "",
        f"- after_confirmation_available: `{payload['after_confirmation_available']}`",
        f"- after_signal_enriched_count: `{payload['after_signal_enriched_count']}`",
        f"- after_rs_vs_etf_coverage: `{payload['after_rs_vs_etf_coverage']}`",
        f"- after_rs_vs_index_coverage: `{payload['after_rs_vs_index_coverage']}`",
        f"- after_amount_1m_ratio_coverage: `{payload['after_amount_1m_ratio_coverage']}`",
        f"- after_shadow_distribution: `{payload['after_shadow_distribution']}`",
        "",
        "## Stage Isolation",
        "",
        f"- event_count: `{len(payload['stage_isolation']['events'])}`",
        f"- slow_batches: `{len(payload['stage_isolation']['slow_batches'])}`",
        f"- failed_batches: `{len(payload['stage_isolation']['failed_batches'])}`",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")

    stage_lines = [
        f"# Intraday Backfill Stage Isolation {payload['date']}",
        "",
        f"- stage: `{payload['stage']}`",
        "",
        "## Stage Events",
        "",
        "| stage | status | elapsed_sec | code_count | row_count | warning | error |",
        "| --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["stage_isolation"]["events"]:
        stage_lines.append(
            f"| {row.get('stage','')} | {row.get('status','')} | {float(row.get('elapsed_sec', 0.0) or 0.0):.4f} | "
            f"{int(row.get('code_count', 0) or 0)} | {int(row.get('row_count', 0) or 0)} | "
            f"{row.get('warning', '') or '-'} | {row.get('error', '') or '-'} |"
        )
    stage_lines.extend(["", "## Slow Batches", ""])
    if payload["stage_isolation"]["slow_batches"]:
        for row in payload["stage_isolation"]["slow_batches"]:
            stage_lines.append(f"- {row}")
    else:
        stage_lines.append("- none")
    stage_lines.extend(["", "## Failed Batches", ""])
    if payload["stage_isolation"]["failed_batches"]:
        for row in payload["stage_isolation"]["failed_batches"]:
            stage_lines.append(f"- {row}")
    else:
        stage_lines.append("- none")
    stage_md.write_text("\n".join(stage_lines), encoding="utf-8")
    _update_expansion_report(payload)
    return json_path, md_path


def _update_expansion_report(payload: dict) -> None:
    if not payload.get("execute"):
        return
    stage = str(payload.get("stage", "") or "")
    if stage not in {"stock", "confirmation"}:
        return
    date = str(payload.get("date", "") or "")
    if not date:
        return
    json_path = EVAL_DIR / f"intraday_confirmation_expansion_{date}.json"
    md_path = EVAL_DIR / f"intraday_confirmation_expansion_{date}.md"
    existing = {"date": date, "runs": [], "conclusion": ""}
    if json_path.exists():
        try:
            existing = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {"date": date, "runs": [], "conclusion": ""}
    runs = list(existing.get("runs", []) or [])
    if stage == "stock":
        run_row = {
            "stage": stage,
            "max_stocks": int(payload.get("max_stocks", 0) or 0),
            "selection_priority": str(payload.get("selection_priority", "original") or "original"),
            "signal_enriched_count": int(payload.get("after_signal_enriched_count", 0) or 0),
            "rs_vs_index_coverage": float(payload.get("after_rs_vs_index_coverage", 0.0) or 0.0),
            "amount_1m_ratio_coverage": float(payload.get("after_amount_1m_ratio_coverage", 0.0) or 0.0),
            "rs_vs_etf_coverage": float(payload.get("after_rs_vs_etf_coverage", 0.0) or 0.0),
            "shadow_distribution": dict(payload.get("after_shadow_distribution", {}) or {}),
            "slow_batches": int(len((payload.get("stage_isolation") or {}).get("slow_batches", []) or [])),
            "failed_batches": int(len((payload.get("stage_isolation") or {}).get("failed_batches", []) or [])),
            "selected_stock_preview": list((payload.get("universe") or {}).get("selected_stock_preview", []) or []),
            "created_at": str(payload.get("created_at", "") or ""),
        }
        runs = [
            row
            for row in runs
            if not (
                int(row.get("max_stocks", 0) or 0) == run_row["max_stocks"]
                and str(row.get("selection_priority", "original") or "original") == run_row["selection_priority"]
            )
        ]
        runs.append(run_row)
    elif runs:
        latest = max(
            runs,
            key=lambda row: (int(row.get("max_stocks", 0) or 0), str(row.get("created_at", "") or "")),
        )
        latest["signal_enriched_count"] = int(payload.get("after_signal_enriched_count", 0) or 0)
        latest["rs_vs_index_coverage"] = float(payload.get("after_rs_vs_index_coverage", 0.0) or 0.0)
        latest["amount_1m_ratio_coverage"] = float(payload.get("after_amount_1m_ratio_coverage", 0.0) or 0.0)
        latest["rs_vs_etf_coverage"] = float(payload.get("after_rs_vs_etf_coverage", 0.0) or 0.0)
        latest["shadow_distribution"] = dict(payload.get("after_shadow_distribution", {}) or {})
        latest["confirmation_rebuilt_at"] = str(payload.get("created_at", "") or "")
    runs.sort(key=lambda row: (int(row.get("max_stocks", 0) or 0), str(row.get("selection_priority", ""))))
    existing["runs"] = runs
    existing["conclusion"] = (
        "confirmation coverage is improving under isolated-query replay; "
        "active mode remains disabled until rs/index and amount coverage lift further."
    )
    json_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Intraday Confirmation Expansion {date}",
        "",
        "| max_stocks | selection_priority | signal_enriched_count | rs_vs_index_coverage | amount_1m_ratio_coverage | rs_vs_etf_coverage | shadow_distribution | slow_batches | failed_batches |",
        "| ---: | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |",
    ]
    for row in runs:
        lines.append(
            f"| {int(row['max_stocks'])} | {row['selection_priority']} | {int(row['signal_enriched_count'])} | "
            f"{float(row['rs_vs_index_coverage']):.4f} | {float(row['amount_1m_ratio_coverage']):.4f} | "
            f"{float(row['rs_vs_etf_coverage']):.4f} | {row['shadow_distribution']} | "
            f"{int(row['slow_batches'])} | {int(row['failed_batches'])} |"
        )
    lines.extend(["", f"- conclusion: `{existing['conclusion']}`"])
    md_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(description="Backfill replay-date intraday confirmation cache.")
    parser.add_argument("--date", required=True, help="Replay trade date YYYYMMDD")
    parser.add_argument("--execute", action="store_true", help="Actually write local intraday cache and confirmation files")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing intraday outputs")
    parser.add_argument("--stage", choices=["all", "index", "etf", "stock", "confirmation"], default="all")
    parser.add_argument("--max-stocks", type=int, default=0)
    parser.add_argument("--only-codes", default="")
    parser.add_argument("--begin-time", type=int, default=930)
    parser.add_argument("--end-time", type=int, default=935)
    parser.add_argument("--batch-size", type=int, default=120)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--warn-after-sec", type=float, default=60.0)
    parser.add_argument("--isolated-query", action="store_true")
    parser.add_argument(
        "--selection-priority",
        choices=["original", "leading_cluster", "sector_positive", "trend_score"],
        default="original",
    )
    return parser.parse_args()


def main():
    configure_utf8_console()
    args = parse_args()
    payload = run_backfill(
        int(args.date),
        execute=args.execute,
        force=args.force,
        stage=args.stage,
        max_stocks=args.max_stocks,
        only_codes=_parse_only_codes(args.only_codes),
        begin_time=args.begin_time,
        end_time=args.end_time,
        batch_size=args.batch_size,
        skip_existing=args.skip_existing,
        warn_after_sec=args.warn_after_sec,
        isolated_query=args.isolated_query,
        selection_priority=args.selection_priority,
    )
    json_path, md_path = write_outputs(payload)
    print(
        json.dumps(
            {
                "json": str(json_path.relative_to(ROOT)),
                "md": str(md_path.relative_to(ROOT)),
                "execute": payload["execute"],
                "dry_run": payload["dry_run"],
                "stage": payload["stage"],
                "selection_priority": payload["selection_priority"],
                "written_files": payload["written_files"],
                "after_confirmation_available": payload["after_confirmation_available"],
                "after_signal_enriched_count": payload["after_signal_enriched_count"],
                "slow_batches": len(payload["stage_isolation"]["slow_batches"]),
                "failed_batches": len(payload["stage_isolation"]["failed_batches"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
