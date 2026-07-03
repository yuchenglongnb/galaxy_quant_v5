# -*- coding: utf-8 -*-
"""Analysis-only intraday path replay and distribution validation."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from reports.intraday_excursion import compute_intraday_excursion_fields


ROOT = Path(__file__).resolve().parents[1]
PATH_FIELDS = (
    "open_to_high_pct",
    "open_to_low_pct",
    "close_to_high_drawdown_pct",
    "intraday_range_pct",
    "mfe_pct",
    "mae_pct",
)
CASE_STUDIES = (
    ("科创50", "000688.SH"),
    ("创业板", "399006.SZ"),
    ("半导体设备 ETF", "159516.SZ"),
    ("半导体 ETF", "512480.SH"),
    ("消费电子 ETF", "159732.SZ"),
    ("金融科技", "159851.SZ"),
    ("证券", "512880.SH"),
)
PHASE_BUCKETS = {
    "20260626": "pre_retreat_setup",
    "20260629": "pre_retreat_setup",
    "20260630": "pre_retreat_setup",
    "20260701": "retreat_transition",
    "20260702": "retreat_confirmation",
}
SAFETY_DISCLAIMER = (
    "This report is analysis-only. It does not justify deterministic rule changes, "
    "CP threshold changes, exemption expansion, Trend active enablement, or trading advice."
)


def read_signal_detail(date: str, root: Path = ROOT) -> tuple[pd.DataFrame, Path | None, str]:
    candidates = [
        (
            root
            / "reports"
            / "validation"
            / "derived"
            / "signal_detail_manual_code_patch"
            / f"{date}_signal_detail.manual_code_patch.csv",
            "manual_code_patch",
        ),
        (
            root
            / "reports"
            / "validation"
            / "derived"
            / "signal_detail_code_backfilled"
            / f"{date}_signal_detail.code_backfilled.csv",
            "code_backfilled",
        ),
        (root / "reports" / "validation" / "daily" / date / "signal_detail.csv", "daily_signal_detail"),
    ]
    for path, quality in candidates:
        if path.exists():
            return pd.read_csv(path), path, quality
    return pd.DataFrame(), None, "missing"


def read_quote_frame(date: str, root: Path = ROOT) -> tuple[pd.DataFrame, list[str]]:
    frames: list[pd.DataFrame] = []
    inputs: list[str] = []
    for filename, universe in (("stocks.csv", "stock"), ("indices.csv", "index_or_etf")):
        path = root / "AmazingData_Store" / date / filename
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        inputs.append(str(path.relative_to(root)))
        if frame.empty:
            continue
        frame["quote_universe"] = universe
        if "name" not in frame.columns:
            frame["name"] = frame["code"].map(_known_code_names()).fillna(frame["code"])
        frames.append(frame)
    if not frames:
        return pd.DataFrame(), inputs
    quotes = pd.concat(frames, ignore_index=True, sort=False)
    quotes = quotes.drop_duplicates(subset=["code"], keep="first")
    return quotes, inputs


def build_daily_replay(date: str, root: Path = ROOT) -> tuple[pd.DataFrame, dict[str, Any]]:
    signals, signal_path, input_quality = read_signal_detail(date, root)
    quotes, quote_inputs = read_quote_frame(date, root)
    metadata = {
        "date": date,
        "signal_input": str(signal_path.relative_to(root)) if signal_path else None,
        "input_quality": input_quality,
        "quote_inputs": quote_inputs,
        "signal_rows": int(len(signals)),
    }
    if signals.empty:
        return pd.DataFrame(), metadata

    quote_by_code = quotes.set_index("code", drop=False) if "code" in quotes.columns else pd.DataFrame()
    quote_by_name = (
        quotes.dropna(subset=["name"]).drop_duplicates(subset=["name"], keep="first").set_index("name", drop=False)
        if "name" in quotes.columns
        else pd.DataFrame()
    )
    rows: list[dict[str, Any]] = []
    for idx, signal in signals.iterrows():
        row = signal.to_dict()
        row["date"] = str(row.get("date") or date)
        row["row_index"] = int(idx)
        row["input_quality"] = input_quality
        row["phase_bucket"] = PHASE_BUCKETS.get(str(row["date"]), "unbucketed")
        quote = _lookup_quote(row, quote_by_code, quote_by_name)
        quote_dict = quote.to_dict() if quote is not None else {}
        body_pct = _number(row.get("body_pct"))
        auction_pct = _number(row.get("auction_pct"))
        row.update(compute_intraday_excursion_fields(quote_dict, body_pct=body_pct, auction_pct=auction_pct))
        for field in ("open", "high", "low", "close", "pre_close"):
            row[f"quote_{field}"] = quote_dict.get(field)
        row["quote_joined"] = quote is not None
        rows.append(row)
    return pd.DataFrame(rows), metadata


def build_t1_replay(prev_date: str, date: str, root: Path = ROOT) -> tuple[pd.DataFrame, dict[str, Any]]:
    signals, signal_path, input_quality = read_signal_detail(prev_date, root)
    quotes, quote_inputs = read_quote_frame(date, root)
    metadata = {
        "prev_date": prev_date,
        "date": date,
        "signal_input": str(signal_path.relative_to(root)) if signal_path else None,
        "input_quality": input_quality,
        "quote_inputs": quote_inputs,
        "candidate_count": int(len(signals)),
    }
    if signals.empty:
        metadata.update(_empty_join_quality())
        return pd.DataFrame(), metadata

    quote_by_code = quotes.set_index("code", drop=False) if "code" in quotes.columns else pd.DataFrame()
    rows: list[dict[str, Any]] = []
    join_quality = _empty_join_quality()
    join_quality["candidate_count"] = int(len(signals))

    for idx, signal in signals.iterrows():
        row = signal.to_dict()
        row["prev_date"] = prev_date
        row["date"] = date
        row["row_index"] = int(idx)
        scope = _first_text(row.get("manual_resolution_scope"))
        status = _first_text(row.get("manual_resolution_status"))
        code = _first_text(row.get("manual_resolution_code"), row.get("code"))
        if scope == "industry_without_code":
            join_quality["manual_scope_excluded_count"] += 1
            row["t1_join_status"] = "manual_scope_excluded"
            rows.append(row)
            continue
        if status == "pending" or scope == "blocked":
            join_quality["pending_blocked_count"] += 1
            row["t1_join_status"] = "pending_blocked"
            rows.append(row)
            continue
        if not code or code not in quote_by_code.index:
            join_quality["unmatched_count"] += 1
            row["t1_join_status"] = "unmatched"
            rows.append(row)
            continue

        quote_dict = quote_by_code.loc[code].to_dict()
        join_quality["resolved_code_denominator"] += 1
        join_quality["primary_code_join_count"] += 1
        row["t1_join_status"] = "code_joined"
        for field in ("open", "high", "low", "close", "pre_close"):
            row[f"t1_{field}"] = quote_dict.get(field)
        pre_close = _number(quote_dict.get("pre_close"))
        open_price = _number(quote_dict.get("open"))
        close = _number(quote_dict.get("close"))
        row["t1_open_return"] = _round(_pct(open_price, pre_close)) if _valid_pair(open_price, pre_close) else None
        row["t1_close_return"] = _round(_pct(close, pre_close)) if _valid_pair(close, pre_close) else None
        t1_body = _pct(close, open_price) if _valid_pair(close, open_price) else None
        fields = compute_intraday_excursion_fields(quote_dict, body_pct=t1_body, auction_pct=row["t1_open_return"])
        for key, value in fields.items():
            row[f"t1_{key}"] = value
        rows.append(row)

    metadata.update(join_quality)
    metadata["fallback_name_join_count"] = 0
    return pd.DataFrame(rows), metadata


def build_input_coverage(dates: list[str], root: Path = ROOT) -> list[dict[str, Any]]:
    coverage: list[dict[str, Any]] = []
    for idx, date in enumerate(dates):
        signals, signal_path, input_quality = read_signal_detail(date, root)
        stocks_path = root / "AmazingData_Store" / date / "stocks.csv"
        indices_path = root / "AmazingData_Store" / date / "indices.csv"
        next_date = dates[idx + 1] if idx + 1 < len(dates) else None
        next_stocks = root / "AmazingData_Store" / next_date / "stocks.csv" if next_date else None
        next_indices = root / "AmazingData_Store" / next_date / "indices.csv" if next_date else None
        present_path_fields = [field for field in [*PATH_FIELDS, "signal_path_type"] if field in signals.columns]
        coverage.append(
            {
                "date": date,
                "signal_detail_source": str(signal_path.relative_to(root)) if signal_path else None,
                "signal_detail_quality": input_quality,
                "signal_rows": int(len(signals)),
                "stocks_ohlc_present": stocks_path.exists(),
                "indices_ohlc_present": indices_path.exists(),
                "path_fields_already_present": present_path_fields,
                "path_fields_computed_from_ohlc": bool(len(signals) and stocks_path.exists() and indices_path.exists()),
                "t1_next_date": next_date,
                "t1_next_day_ohlc_available": bool(next_date and next_stocks and next_indices and next_stocks.exists() and next_indices.exists()),
                "notes": _coverage_notes(signals, signal_path, stocks_path, indices_path),
            }
        )
    return coverage


def build_replay_payload(dates: list[str], root: Path = ROOT) -> dict[str, Any]:
    dates = [str(date) for date in dates]
    daily_frames: list[pd.DataFrame] = []
    daily_inputs: list[dict[str, Any]] = []
    for date in dates:
        frame, metadata = build_daily_replay(date, root)
        daily_frames.append(frame)
        daily_inputs.append(metadata)

    t1_frames: list[pd.DataFrame] = []
    t1_metadata: list[dict[str, Any]] = []
    for prev_date, date in zip(dates, dates[1:]):
        frame, metadata = build_t1_replay(prev_date, date, root)
        t1_frames.append(frame)
        t1_metadata.append(metadata)

    daily_all = pd.concat(daily_frames, ignore_index=True, sort=False) if daily_frames else pd.DataFrame()
    t1_all = pd.concat(t1_frames, ignore_index=True, sort=False) if t1_frames else pd.DataFrame()
    return {
        "metadata": {
            "start_date": dates[0] if dates else None,
            "end_date": dates[-1] if dates else None,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "analysis_only": True,
        },
        "date_range": {"start": dates[0] if dates else None, "end": dates[-1] if dates else None},
        "analysis_only": True,
        "safety_disclaimer": SAFETY_DISCLAIMER,
        "inputs": daily_inputs,
        "input_coverage": build_input_coverage(dates, root),
        "metric_definitions": metric_definitions(),
        "denominator_reconciliation": denominator_reconciliation(),
        "daily_path_summary": summarize_paths(daily_all),
        "daily_signal_summary": summarize_signal_level(daily_all),
        "signal_family_summary": summarize_signal_family(daily_all),
        "phase_summary": summarize_phase_level(daily_all),
        "t1_pairs": t1_metadata,
        "t1_signal_summary": summarize_t1(t1_all),
        "representative_cases": build_case_studies(dates, root),
        "case_studies": build_case_studies(dates, root),
        "limitations": [
            "Only local closed-day cache is used.",
            "The sample window is limited by locally available signal_detail and OHLC files.",
            "Path labels are validation descriptors, not strategy rules.",
            "Earlier dates without code-backfilled signal_detail may have lower T+1 code-keyed coverage.",
        ],
        "conclusion": [
            "broader_window_intraday_path_distribution_completed",
            "analysis_only_no_rule_change",
            "metric_denominator_reconciliation_included",
            "broader_window_validation_required_before_rule_proposal",
        ],
    }


def summarize_paths(frame: pd.DataFrame, *, path_col: str = "signal_path_type") -> list[dict[str, Any]]:
    if frame.empty or path_col not in frame.columns:
        return []
    working = _numeric_working_frame(frame, ["body_pct", *PATH_FIELDS])
    if "signal_family" not in working.columns:
        working["signal_family"] = working.get("signal_category", "unknown")
    summaries: list[dict[str, Any]] = []
    group_cols = [col for col in ("date", "signal_family", path_col) if col in working.columns]
    for keys, group in working.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        item = dict(zip(group_cols, keys))
        item["count"] = int(len(group))
        item.update(_numeric_summary(group, ["body_pct", *PATH_FIELDS]))
        item["representative_worst_body"] = _sample_records(group, "body_pct", ascending=True, limit=5)
        item["representative_largest_drawdown"] = _sample_records(group, "close_to_high_drawdown_pct", ascending=True, limit=5)
        item["representative_largest_open_to_low"] = _sample_records(group, "open_to_low_pct", ascending=True, limit=5)
        summaries.append(_json_ready(item))
    return summaries


def summarize_signal_level(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    working = _numeric_working_frame(frame, ["body_pct", *PATH_FIELDS])
    summaries: list[dict[str, Any]] = []
    for (date, signal_family), group in working.groupby(["date", "signal_family"], dropna=False):
        item = {
            "date": str(date),
            "signal_family": signal_family,
            "count": int(len(group)),
            "path_type_distribution": _value_counts(group.get("signal_path_type")),
        }
        item.update(_numeric_summary(group, ["body_pct", *PATH_FIELDS]))
        summaries.append(_json_ready(item))
    return summaries


def summarize_signal_family(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    working = _numeric_working_frame(frame, ["body_pct", *PATH_FIELDS])
    summaries: list[dict[str, Any]] = []
    for signal_family, group in working.groupby("signal_family", dropna=False):
        item = {
            "signal_family": signal_family,
            "count": int(len(group)),
            "path_type_distribution": _value_counts(group.get("signal_path_type")),
            "worst_body_samples": _sample_records(group, "body_pct", ascending=True, limit=5),
            "largest_drawdown_samples": _sample_records(group, "close_to_high_drawdown_pct", ascending=True, limit=5),
            "largest_open_to_low_samples": _sample_records(group, "open_to_low_pct", ascending=True, limit=5),
        }
        item.update(_numeric_summary(group, ["body_pct", *PATH_FIELDS]))
        summaries.append(_json_ready(item))
    return summaries


def summarize_phase_level(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty or "phase_bucket" not in frame.columns:
        return []
    working = _numeric_working_frame(frame, ["body_pct", *PATH_FIELDS])
    summaries: list[dict[str, Any]] = []
    for (phase_bucket, signal_family), group in working.groupby(["phase_bucket", "signal_family"], dropna=False):
        item = {
            "phase_bucket": phase_bucket,
            "signal_family": signal_family,
            "count": int(len(group)),
            "path_type_distribution": _value_counts(group.get("signal_path_type")),
        }
        item.update(_numeric_summary(group, ["body_pct", "open_to_low_pct", "close_to_high_drawdown_pct"]))
        summaries.append(_json_ready(item))
    return summaries


def summarize_t1(frame: pd.DataFrame) -> list[dict[str, Any]]:
    joined = frame[frame.get("t1_join_status") == "code_joined"].copy() if "t1_join_status" in frame.columns else pd.DataFrame()
    if joined.empty:
        return []
    for column in ["t1_open_return", "t1_close_return", "t1_open_to_low_pct", "t1_close_to_high_drawdown_pct"]:
        joined[column] = pd.to_numeric(joined.get(column), errors="coerce")
    summaries: list[dict[str, Any]] = []
    for signal_family, group in joined.groupby("signal_family", dropna=False):
        close_returns = group["t1_close_return"].dropna()
        item = {
            "signal_family": signal_family,
            "resolved_count": int(len(group)),
            "avg_t1_open_return": _round(group["t1_open_return"].mean()),
            "avg_t1_close_return": _round(close_returns.mean()) if not close_returns.empty else None,
            "median_t1_close_return": _round(close_returns.median()) if not close_returns.empty else None,
            "t1_close_positive_rate": _round((close_returns > 0).mean() * 100) if not close_returns.empty else None,
            "avg_t1_open_to_low_pct": _round(group["t1_open_to_low_pct"].mean()),
            "avg_t1_close_to_high_drawdown_pct": _round(group["t1_close_to_high_drawdown_pct"].mean()),
            "t1_path_type_distribution": _value_counts(group.get("t1_signal_path_type")),
        }
        summaries.append(_json_ready(item))
    return summaries


def build_case_studies(dates: Iterable[str], root: Path = ROOT) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for date in dates:
        quotes, _ = read_quote_frame(date, root)
        if quotes.empty:
            continue
        quote_by_code = quotes.set_index("code", drop=False)
        for label, code in CASE_STUDIES:
            if code not in quote_by_code.index:
                continue
            quote = quote_by_code.loc[code].to_dict()
            pre_close = _number(quote.get("pre_close"))
            open_price = _number(quote.get("open"))
            close = _number(quote.get("close"))
            auction_pct = _pct(open_price, pre_close) if _valid_pair(open_price, pre_close) else None
            body_pct = _pct(close, open_price) if _valid_pair(close, open_price) else None
            fields = compute_intraday_excursion_fields(quote, body_pct=body_pct, auction_pct=auction_pct)
            cases.append(
                _json_ready(
                    {
                        "date": date,
                        "name": label,
                        "code": code,
                        "auction_pct": _round(auction_pct),
                        "body_pct": _round(body_pct),
                        **fields,
                        "observation": _case_observation(fields.get("signal_path_type")),
                    }
                )
            )
    return cases


def render_markdown(payload: dict[str, Any]) -> str:
    start = payload["date_range"]["start"]
    end = payload["date_range"]["end"]
    lines = [
        f"# {start}-{end} Intraday Path Distribution Validation",
        "",
        SAFETY_DISCLAIMER,
        "",
        "## Scope and Safety Boundary",
        "",
        "- This is a validation/reporting framework, not a strategy-change workflow.",
        "- It does not change CP threshold, CP exemption, reversal trigger, Trend active status, ranking, shortlist, evaluator logic, lesson files, pattern files, or registry files.",
        "",
        "## Input Coverage Table",
        "",
    ]
    lines.extend(
        _markdown_table(
            payload.get("input_coverage", []),
            [
                "date",
                "signal_detail_quality",
                "signal_rows",
                "stocks_ohlc_present",
                "indices_ohlc_present",
                "path_fields_computed_from_ohlc",
                "t1_next_date",
                "t1_next_day_ohlc_available",
                "notes",
            ],
        )
    )
    lines.extend(["", "## Metric Definition and Denominator Reconciliation", ""])
    lines.extend(["|metric|definition|", "|---|---|"])
    for key, value in payload.get("metric_definitions", {}).items():
        lines.append(f"|`{key}`|{value}|")
    lines.append("")
    lines.append(payload.get("denominator_reconciliation", {}).get("p1_5b_metric_note", ""))
    for item in payload.get("denominator_reconciliation", {}).get("denominator_rules", []):
        lines.append(f"- {item}")
    lines.append("")

    lines.extend(["## Broader-window Daily Summary", ""])
    lines.extend(
        _markdown_table(
            payload.get("daily_signal_summary", []),
            [
                "date",
                "signal_family",
                "count",
                "avg_body_pct",
                "positive_body_rate",
                "avg_open_to_low_pct",
                "avg_close_to_high_drawdown_pct",
                "path_type_distribution",
            ],
        )
    )
    lines.extend(["", "## Signal-family Path Distribution", ""])
    lines.extend(
        _markdown_table(
            payload.get("signal_family_summary", []),
            [
                "signal_family",
                "count",
                "avg_body_pct",
                "positive_body_rate",
                "avg_open_to_low_pct",
                "avg_close_to_high_drawdown_pct",
                "path_type_distribution",
            ],
        )
    )
    lines.extend(["", "## Date-phase Path Distribution", ""])
    lines.extend(
        _markdown_table(
            payload.get("phase_summary", []),
            [
                "phase_bucket",
                "signal_family",
                "count",
                "avg_body_pct",
                "avg_open_to_low_pct",
                "avg_close_to_high_drawdown_pct",
                "path_type_distribution",
            ],
        )
    )
    lines.extend(["", "## T+1 Broader-window Replay", ""])
    lines.extend(
        _markdown_table(
            payload.get("t1_pairs", []),
            [
                "prev_date",
                "date",
                "candidate_count",
                "resolved_code_denominator",
                "manual_scope_excluded_count",
                "pending_blocked_count",
                "primary_code_join_count",
                "fallback_name_join_count",
                "unmatched_count",
            ],
        )
    )
    lines.append("")
    if payload.get("t1_signal_summary"):
        lines.extend(
            _markdown_table(
                payload["t1_signal_summary"],
                [
                    "signal_family",
                    "resolved_count",
                    "avg_t1_close_return",
                    "median_t1_close_return",
                    "t1_close_positive_rate",
                    "avg_t1_open_to_low_pct",
                    "avg_t1_close_to_high_drawdown_pct",
                    "t1_path_type_distribution",
                ],
            )
        )
    else:
        lines.append("T+1 path replay is unavailable from local code-keyed inputs.")
    lines.append("")

    lines.extend(["## Comparison with P1.5B Two-day Replay", ""])
    lines.append(
        "P1.5B used a focused 20260701-20260702 sample. This broader report keeps the same metric definitions but adds input coverage, denominator reconciliation, and phase buckets. Differences versus earlier manual summaries should be read as denominator or metric-base differences unless reconciled by row-level audit."
    )
    lines.extend(["", "## Representative Cases", ""])
    lines.extend(
        _markdown_table(
            payload.get("representative_cases", []),
            [
                "date",
                "name",
                "code",
                "auction_pct",
                "body_pct",
                "open_to_high_pct",
                "open_to_low_pct",
                "close_to_high_drawdown_pct",
                "signal_path_type",
                "observation",
            ],
        )
    )
    lines.extend(["", "## Limitations", ""])
    for item in payload.get("limitations", []):
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Next Step Recommendation",
            "",
            "P1.5D: Broader-window Path Stability Review and Rule-Proposal Gate Design. Keep it analysis-only; design gates for future proposals instead of modifying rules.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(payload: dict[str, Any], output: Path, json_output: Path | None = None) -> None:
    payload = {"analysis_only": True, **payload}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_markdown(payload), encoding="utf-8")
    if json_output is not None:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(_json_ready(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def metric_definitions() -> dict[str, str]:
    return {
        "body_pct": "Same-day open-to-close body return: close / open - 1.",
        "close_pct": "Same-day close return versus previous close when source output provides it.",
        "gap_pct": "Open versus previous close when pre_close is available.",
        "close_from_prev_close_pct": "Close versus previous close when pre_close is available.",
        "t1_body_pct": "T+1 close / T+1 open - 1, used by intraday path fields.",
        "t1_open_return": "T+1 open / T+1 pre_close - 1.",
        "t1_close_return": "T+1 close / T+1 pre_close - 1.",
        "t1_close_positive_rate": "Share of resolved code-joined candidates with t1_close_return > 0.",
    }


def denominator_reconciliation() -> dict[str, Any]:
    return {
        "p1_5b_metric_note": (
            "P1.5B t1_close_return is computed from T+1 close versus T+1 pre_close. "
            "Earlier manual summaries may have mixed close/open body return, close-vs-prior-close return, "
            "or different resolved denominators."
        ),
        "denominator_rules": [
            "manual_resolution_scope=industry_without_code is excluded from code-level denominator.",
            "manual_resolution_status=pending is counted as pending_blocked and excluded from resolved denominator.",
            "primary code join is required for T+1 return metrics.",
            "name fallback is not used in this analysis framework.",
            "unmatched rows are counted explicitly and excluded from return metrics.",
        ],
        "possible_reasons_for_manual_summary_difference": [
            "Different denominator after manual_scope_excluded or pending_blocked handling.",
            "Different return base: T+1 close versus pre_close, T+1 close versus open, or T+1 close versus T close.",
            "Different signal-family mapping or inclusion of industry/sector rows.",
            "Different treatment of unmatched or fallback rows.",
        ],
    }


def expand_date_range(start_date: str, end_date: str, root: Path = ROOT) -> list[str]:
    candidates: set[str] = set()
    for base in (root / "reports" / "validation" / "daily", root / "AmazingData_Store"):
        if base.exists():
            candidates.update(path.name for path in base.iterdir() if path.is_dir())
    return sorted(date for date in candidates if start_date <= date <= end_date)


def _lookup_quote(row: dict[str, Any], quote_by_code: pd.DataFrame, quote_by_name: pd.DataFrame) -> pd.Series | None:
    code = _first_text(row.get("manual_resolution_code"), row.get("code"))
    if code and not quote_by_code.empty and code in quote_by_code.index:
        return quote_by_code.loc[code]
    name = _first_text(row.get("name"))
    if name and not quote_by_name.empty and name in quote_by_name.index:
        return quote_by_name.loc[name]
    return None


def _known_code_names() -> dict[str, str]:
    return {
        "000688.SH": "科创50",
        "399006.SZ": "创业板",
        "000001.SH": "上证",
        "899050.BJ": "北证50",
        "159516.SZ": "半导体设备 ETF",
        "512480.SH": "半导体 ETF",
        "159732.SZ": "消费电子 ETF",
        "159851.SZ": "金融科技",
        "512880.SH": "证券",
        "159915.SZ": "创业板 ETF",
        "159206.SZ": "卫星",
    }


def _coverage_notes(signals: pd.DataFrame, signal_path: Path | None, stocks_path: Path, indices_path: Path) -> list[str]:
    notes: list[str] = []
    if signal_path is None:
        notes.append("missing_signal_detail")
    if signals.empty:
        notes.append("empty_signal_detail")
    if not stocks_path.exists():
        notes.append("missing_stocks_ohlc")
    if not indices_path.exists():
        notes.append("missing_indices_ohlc")
    if not notes:
        notes.append("usable")
    return notes


def _empty_join_quality() -> dict[str, int]:
    return {
        "candidate_count": 0,
        "resolved_code_denominator": 0,
        "manual_scope_excluded_count": 0,
        "pending_blocked_count": 0,
        "primary_code_join_count": 0,
        "fallback_name_join_count": 0,
        "unmatched_count": 0,
    }


def _numeric_working_frame(frame: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    working = frame.copy()
    for column in columns:
        if column not in working.columns:
            working[column] = None
        working[column] = pd.to_numeric(working[column], errors="coerce")
    return working


def _numeric_summary(frame: pd.DataFrame, columns: Iterable[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for column in columns:
        if column not in frame.columns:
            result[f"avg_{column}"] = None
            result[f"median_{column}"] = None
            continue
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        result[f"avg_{column}"] = _round(values.mean()) if not values.empty else None
        result[f"median_{column}"] = _round(values.median()) if not values.empty else None
        if column == "body_pct":
            result["positive_body_rate"] = _round((values > 0).mean() * 100) if not values.empty else None
    return result


def _sample_records(frame: pd.DataFrame, column: str, *, ascending: bool, limit: int = 3) -> list[dict[str, Any]]:
    if column not in frame.columns:
        return []
    working = frame.copy()
    working[column] = pd.to_numeric(working[column], errors="coerce")
    working = working.dropna(subset=[column]).sort_values(column, ascending=ascending).head(limit)
    fields = ["date", "name", "signal_family", "body_pct", column, "signal_path_type"]
    return [_json_ready({field: row.get(field) for field in fields if field in row}) for _, row in working.iterrows()]


def _value_counts(series: Any) -> dict[str, int]:
    if series is None:
        return {}
    counts = pd.Series(series).fillna("unknown").astype(str).value_counts()
    return {str(index): int(value) for index, value in counts.items()}


def _case_observation(path_type: Any) -> str:
    mapping = {
        "one_way_selloff": "该样本表现为开盘后继续走弱，支持退潮样本的后验观察。",
        "low_open_rebound_failed": "该样本显示盘中反抽不足以修复收盘弱势。",
        "high_open_trap": "该路径更接近高开或冲高后回落。",
        "rush_up_fade": "该路径显示盘中上冲后回落。",
        "close_near_low": "该样本收盘贴近低位，显示日内承接偏弱。",
        "close_near_high": "该样本收盘贴近高位，未呈现典型退潮路径。",
        "range_chop": "该样本为区间震荡路径，需要放入更大窗口比较。",
    }
    return mapping.get(str(path_type), "该样本路径信息不足，暂不做方向性解释。")


def _markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> list[str]:
    if not rows:
        return ["No local rows available."]
    lines = ["|" + "|".join(columns) + "|", "|" + "|".join(["---"] * len(columns)) + "|"]
    for row in rows:
        values = [_format_cell(row.get(column)) for column in columns]
        lines.append("|" + "|".join(values) + "|")
    return lines


def _format_cell(value: Any) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{key}:{val}" for key, val in value.items())
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if isinstance(value, float):
        return f"{value:.4f}"
    if value is None:
        return ""
    return str(value).replace("|", "/")


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(result):
        return None
    return result


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, float) and pd.isna(value):
            continue
        text = str(value).strip()
        if text and text.lower() != "nan":
            return text
    return ""


def _valid_pair(numerator: float | None, denominator: float | None) -> bool:
    return numerator is not None and denominator is not None and denominator > 0


def _pct(numerator: float, denominator: float) -> float:
    return (numerator / denominator - 1.0) * 100.0


def _round(value: Any) -> float | None:
    number = _number(value)
    return round(number, 4) if number is not None else None


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if pd.isna(value) if not isinstance(value, (dict, list, tuple, str)) else False:
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except ValueError:
            return value
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build analysis-only intraday path replay report.")
    parser.add_argument("--dates", nargs="+")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--output")
    parser.add_argument("--output-md")
    parser.add_argument("--json-output")
    parser.add_argument("--output-json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.dates and (args.start_date or args.end_date):
        raise SystemExit("--dates cannot be combined with --start-date/--end-date")
    if args.dates:
        dates = [str(date) for date in args.dates]
    elif args.start_date and args.end_date:
        dates = expand_date_range(str(args.start_date), str(args.end_date), ROOT)
    else:
        raise SystemExit("Provide either --dates or --start-date and --end-date")
    output = args.output_md or args.output
    if not output:
        raise SystemExit("Provide --output-md or --output")
    payload = build_replay_payload(dates, ROOT)
    json_arg = args.output_json or args.json_output
    write_outputs(payload, Path(output), Path(json_arg) if json_arg else None)


if __name__ == "__main__":
    main()
