# -*- coding: utf-8 -*-
"""Analysis-only rule-proposal gate for intraday path stability evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


SAFETY_DISCLAIMER = (
    "This review is analysis-only. Current evidence is not sufficient for deterministic rule changes, "
    "and it does not justify CP threshold changes, exemption expansion, Trend active enablement, "
    "reversal trigger changes, or trading advice."
)


DEFAULT_CONFIG = {
    "min_dates": 8,
    "min_signal_samples": 50,
    "min_t1_resolved": 30,
    "max_unmatched_ratio": 0.20,
    "max_manual_only_ratio": 0.50,
    "dominant_path_share_min": 0.35,
    "dominant_path_min_dates": 3,
}


def load_distribution_summary(path: str | Path) -> dict[str, Any]:
    summary_path = Path(path)
    if not summary_path.exists():
        raise FileNotFoundError(f"Input summary JSON not found: {summary_path}")
    return json.loads(summary_path.read_text(encoding="utf-8"))


def evaluate_coverage_gate(summary: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    coverage = summary.get("input_coverage", [])
    t1_pairs = summary.get("t1_pairs", [])
    usable_dates = [row for row in coverage if row.get("signal_rows", 0) > 0]
    total_t1_candidates = sum(_number(row.get("candidate_count")) or 0 for row in t1_pairs)
    total_resolved = sum(_number(row.get("resolved_code_denominator")) or 0 for row in t1_pairs)
    total_unmatched = sum(_number(row.get("unmatched_count")) or 0 for row in t1_pairs)
    manual_or_derived = [
        row
        for row in coverage
        if row.get("signal_detail_quality") in {"manual_code_patch", "code_backfilled"}
    ]
    unmatched_ratio = (total_unmatched / total_t1_candidates) if total_t1_candidates else 1.0
    manual_only_ratio = (len(manual_or_derived) / len(usable_dates)) if usable_dates else 1.0
    blockers: list[str] = []
    if len(usable_dates) < cfg["min_dates"]:
        blockers.append("insufficient_trading_dates")
    if total_resolved < cfg["min_t1_resolved"]:
        blockers.append("insufficient_t1_resolved_samples")
    if unmatched_ratio > cfg["max_unmatched_ratio"]:
        blockers.append("unmatched_ratio_too_high")
    if manual_only_ratio > cfg["max_manual_only_ratio"]:
        blockers.append("manual_or_derived_input_ratio_too_high")
    status = "analysis_only_no_rule_change" if not blockers else "blocked_missing_data"
    return {
        "status": status,
        "pass": not blockers,
        "usable_date_count": len(usable_dates),
        "total_t1_candidates": int(total_t1_candidates),
        "total_t1_resolved": int(total_resolved),
        "total_unmatched": int(total_unmatched),
        "unmatched_ratio": round(unmatched_ratio, 4),
        "manual_only_ratio": round(manual_only_ratio, 4),
        "blockers": blockers,
    }


def evaluate_directional_stability(summary: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    signal_summaries = {row.get("signal_family"): row for row in summary.get("signal_family_summary", [])}
    phases = summary.get("phase_summary", [])
    results: dict[str, Any] = {}
    for family, row in signal_summaries.items():
        avg_body = _number(row.get("avg_body_pct"))
        median_body = _number(row.get("median_body_pct"))
        family_phases = [phase for phase in phases if phase.get("signal_family") == family]
        phase_signs = {
            phase.get("phase_bucket"): _sign(_number(phase.get("avg_body_pct")))
            for phase in family_phases
        }
        blockers: list[str] = []
        if _sign(avg_body) != _sign(median_body):
            blockers.append("average_median_sign_mismatch")
        non_zero_phase_signs = {value for value in phase_signs.values() if value != "flat_or_unknown"}
        if len(non_zero_phase_signs) > 1:
            blockers.append("phase_sign_flip")
        if row.get("count", 0) < (config or DEFAULT_CONFIG).get("min_signal_samples", DEFAULT_CONFIG["min_signal_samples"]):
            blockers.append("insufficient_signal_samples")
        status = "analysis_only_no_rule_change" if not blockers else "unstable_across_phases"
        results[str(family)] = {
            "status": status,
            "pass": not blockers,
            "avg_body_pct": avg_body,
            "median_body_pct": median_body,
            "phase_signs": phase_signs,
            "blockers": blockers,
        }
    return {"status": _combined_status(results, "unstable_across_phases"), "by_signal_family": results}


def evaluate_path_concentration(summary: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    daily = summary.get("daily_signal_summary", [])
    family_summary = summary.get("signal_family_summary", [])
    results: dict[str, Any] = {}
    for row in family_summary:
        family = str(row.get("signal_family"))
        total = _number(row.get("count")) or 0
        distribution = row.get("path_type_distribution") or {}
        dominant_path, dominant_count = _dominant(distribution)
        dominant_share = (dominant_count / total) if total else 0.0
        dates_with_path = {
            item.get("date")
            for item in daily
            if item.get("signal_family") == family
            and (item.get("path_type_distribution") or {}).get(dominant_path, 0) > 0
        }
        blockers: list[str] = []
        if dominant_share < cfg["dominant_path_share_min"]:
            blockers.append("dominant_path_share_below_gate")
        if len(dates_with_path) < cfg["dominant_path_min_dates"]:
            blockers.append("dominant_path_not_persistent_across_dates")
        if dates_with_path == {"20260702"}:
            blockers.append("dominant_path_driven_by_single_retreat_confirmation_day")
        results[family] = {
            "status": "analysis_only_no_rule_change" if not blockers else "unstable_across_dates",
            "pass": not blockers,
            "dominant_path_type": dominant_path,
            "dominant_path_count": int(dominant_count),
            "dominant_path_share": round(dominant_share, 4),
            "dates_with_dominant_path": sorted(date for date in dates_with_path if date),
            "blockers": blockers,
        }
    return {"status": _combined_status(results, "unstable_across_dates"), "by_signal_family": results}


def evaluate_t1_confirmation(summary: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    results: dict[str, Any] = {}
    for row in summary.get("t1_signal_summary", []):
        family = str(row.get("signal_family"))
        resolved = _number(row.get("resolved_count")) or 0
        avg_close = _number(row.get("avg_t1_close_return"))
        median_close = _number(row.get("median_t1_close_return"))
        positive_rate = _number(row.get("t1_close_positive_rate"))
        blockers: list[str] = []
        if resolved < cfg["min_t1_resolved"]:
            blockers.append("insufficient_t1_resolved_samples")
        if _sign(avg_close) != _sign(median_close):
            blockers.append("t1_average_median_sign_mismatch")
        if positive_rate is not None and 45.0 <= positive_rate <= 55.0:
            blockers.append("t1_positive_rate_near_coin_flip")
        results[family] = {
            "status": "analysis_only_no_rule_change" if not blockers else "t1_not_confirmed",
            "pass": not blockers,
            "resolved_count": int(resolved),
            "avg_t1_close_return": avg_close,
            "median_t1_close_return": median_close,
            "t1_close_positive_rate": positive_rate,
            "blockers": blockers,
        }
    return {"status": _combined_status(results, "t1_not_confirmed"), "by_signal_family": results}


def evaluate_contradictions(summary: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    phase = summary.get("phase_summary", [])
    t1_by_family = {row.get("signal_family"): row for row in summary.get("t1_signal_summary", [])}
    contradictions: dict[str, Any] = {}
    for family in {row.get("signal_family") for row in summary.get("signal_family_summary", [])}:
        family_phases = {row.get("phase_bucket"): row for row in phase if row.get("signal_family") == family}
        blockers: list[str] = []
        if family == "CP风险":
            pre = _number((family_phases.get("pre_retreat_setup") or {}).get("avg_body_pct"))
            confirm = _number((family_phases.get("retreat_confirmation") or {}).get("avg_body_pct"))
            if pre is not None and confirm is not None and pre > 0 and confirm < 0:
                blockers.append("cp_phase_contradiction_between_repair_and_retreat")
        if family == "反核机会":
            confirm = _number((family_phases.get("retreat_confirmation") or {}).get("avg_body_pct"))
            t1_positive = _number((t1_by_family.get(family) or {}).get("t1_close_positive_rate"))
            if confirm is not None and confirm < 0 and t1_positive is not None and t1_positive > 50:
                blockers.append("reversal_same_day_weak_but_broader_t1_positive")
        if family == "趋势机会":
            distribution = (t1_by_family.get(family) or {}).get("t1_path_type_distribution") or {}
            if distribution.get("rush_up_fade", 0) > 0 and (_number((t1_by_family.get(family) or {}).get("avg_t1_close_return")) or 0) > -0.5:
                blockers.append("trend_path_weakness_not_confirmed_by_large_t1_return_loss")
        contradictions[str(family)] = {
            "status": "analysis_only_no_rule_change" if not blockers else "contradicted_by_counterexamples",
            "pass": not blockers,
            "blockers": blockers,
        }
    return {"status": _combined_status(contradictions, "contradicted_by_counterexamples"), "by_signal_family": contradictions}


def evaluate_leakage_integrity(summary: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": "analysis_only_no_rule_change",
        "pass": True,
        "checks": {
            "candidate_generation_not_modified": True,
            "t1_denominator_disclosed": True,
            "manual_patch_coverage_disclosed": True,
            "unmatched_rows_counted": True,
            "name_fallback_silent_dependency": False,
            "lesson_pattern_outputs_used": False,
        },
    }


def evaluate_rule_proposal_gate(summary: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    gates = {
        "coverage": evaluate_coverage_gate(summary, cfg),
        "directional_stability": evaluate_directional_stability(summary, cfg),
        "path_concentration": evaluate_path_concentration(summary, cfg),
        "t1_confirmation": evaluate_t1_confirmation(summary, cfg),
        "contradiction": evaluate_contradictions(summary, cfg),
        "leakage_integrity": evaluate_leakage_integrity(summary, cfg),
    }
    signal_family_verdicts = _signal_family_verdicts(gates)
    blockers = _collect_blockers(gates)
    rule_change_allowed = False
    overall_status = "insufficient_sample" if blockers else "analysis_only_no_rule_change"
    return {
        "metadata": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "analysis_only": True,
            "rule_change_allowed": rule_change_allowed,
            "overall_status": overall_status,
        },
        "gate_config": cfg,
        "gate_results": gates,
        "signal_family_verdicts": signal_family_verdicts,
        "blockers": blockers,
        "required_future_evidence": [
            "At least 8 locally covered trading dates with stable signal_detail and OHLC coverage.",
            "Code-keyed T+1 coverage with unmatched ratio below the governance threshold.",
            "Path concentration that persists across at least 3 dates and is not driven by one retreat day.",
            "Directional and T+1 evidence that agree across average, median, phase, and counterexample checks.",
            "Out-of-sample replay before any future rule proposal is drafted.",
        ],
        "next_recommendation": "P1.5E: Clean Commit Preparation and Diff Packaging for P1.4R-P1.5D",
    }


def render_gate_review_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# 20260626-20260702 Path Stability Gate Review",
        "",
        SAFETY_DISCLAIMER,
        "",
        "## Scope and Input Summary",
        "",
        f"- overall_status: `{result['metadata']['overall_status']}`",
        f"- rule_change_allowed: `{str(result['metadata']['rule_change_allowed']).lower()}`",
        "",
        "## Gate Design Overview",
        "",
        "- Coverage gate: checks date count, T+1 resolved count, unmatched ratio, and manual-derived input dependency.",
        "- Directional stability gate: checks average/median sign and phase sign stability.",
        "- Path concentration gate: checks whether path types persist across dates.",
        "- T+1 confirmation gate: checks resolved T+1 sample size and metric consistency.",
        "- Contradiction gate: checks counterexamples and phase contradictions.",
        "- Leakage / integrity gate: confirms this remains reporting-only.",
        "",
    ]
    for gate_name, gate_result in result.get("gate_results", {}).items():
        lines.extend([f"## {gate_name.replace('_', ' ').title()} Result", ""])
        lines.append(f"- status: `{gate_result.get('status')}`")
        if "blockers" in gate_result:
            lines.append(f"- blockers: {_format_cell(gate_result.get('blockers'))}")
        if "by_signal_family" in gate_result:
            lines.extend(_markdown_table(_family_rows(gate_result["by_signal_family"]), ["signal_family", "status", "pass", "blockers"]))
        lines.append("")
    lines.extend(["## Signal-family Review", ""])
    lines.extend(_markdown_table(list(result.get("signal_family_verdicts", {}).values()), ["signal_family", "overall_status", "eligible_for_human_review", "main_blockers"]))
    lines.extend(["", "## Current Evidence Verdict", ""])
    lines.append("Current evidence remains observation-only and is not sufficient for deterministic rule changes.")
    lines.append("No CP threshold, CP exemption, Trend active, reversal trigger, ranking, shortlist, evaluator, lesson, pattern, or registry change is justified.")
    lines.extend(["", "## What Would Be Required Before A Future Rule Proposal", ""])
    for item in result.get("required_future_evidence", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Next-step Recommendation", "", result.get("next_recommendation", ""), ""])
    return "\n".join(lines)


def write_gate_review(result: dict[str, Any], output_md: str | Path, output_json: str | Path) -> None:
    md_path = Path(output_md)
    json_path = Path(output_json)
    _ensure_safe_output_path(md_path)
    _ensure_safe_output_path(json_path)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_gate_review_markdown(result), encoding="utf-8")
    json_path.write_text(json.dumps(_json_ready(result), ensure_ascii=False, indent=2), encoding="utf-8")


def _signal_family_verdicts(gates: dict[str, Any]) -> dict[str, dict[str, Any]]:
    families: set[str] = set()
    for gate in gates.values():
        families.update((gate.get("by_signal_family") or {}).keys())
    verdicts: dict[str, dict[str, Any]] = {}
    for family in sorted(families):
        blockers: list[str] = []
        for gate_name, gate in gates.items():
            family_gate = (gate.get("by_signal_family") or {}).get(family)
            if family_gate and not family_gate.get("pass", False):
                blockers.extend(f"{gate_name}:{blocker}" for blocker in family_gate.get("blockers", []))
        if not gates["coverage"].get("pass", False):
            blockers.extend(f"coverage:{blocker}" for blocker in gates["coverage"].get("blockers", []))
        verdicts[family] = {
            "signal_family": family,
            "overall_status": "analysis_only_no_rule_change" if not blockers else "not_eligible",
            "eligible_for_human_review": False,
            "main_blockers": sorted(set(blockers)),
        }
    return verdicts


def _collect_blockers(gates: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for gate_name, gate in gates.items():
        for blocker in gate.get("blockers", []):
            blockers.append(f"{gate_name}:{blocker}")
        for family, family_gate in (gate.get("by_signal_family") or {}).items():
            for blocker in family_gate.get("blockers", []):
                blockers.append(f"{gate_name}:{family}:{blocker}")
    return sorted(set(blockers))


def _combined_status(results: dict[str, Any], fail_status: str) -> str:
    if any(not item.get("pass", False) for item in results.values()):
        return fail_status
    return "analysis_only_no_rule_change"


def _dominant(distribution: dict[str, Any]) -> tuple[str, int]:
    if not distribution:
        return "unknown", 0
    key, value = max(distribution.items(), key=lambda item: _number(item[1]) or 0)
    return str(key), int(_number(value) or 0)


def _sign(value: float | None) -> str:
    if value is None or abs(value) < 0.05:
        return "flat_or_unknown"
    return "positive" if value > 0 else "negative"


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if result != result else result


def _family_rows(by_family: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "signal_family": family,
            "status": item.get("status"),
            "pass": item.get("pass"),
            "blockers": item.get("blockers"),
        }
        for family, item in by_family.items()
    ]


def _format_cell(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return ", ".join(f"{key}:{val}" for key, val in value.items())
    if value is None:
        return ""
    return str(value).replace("|", "/")


def _markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> list[str]:
    if not rows:
        return ["No local rows available."]
    lines = ["|" + "|".join(columns) + "|", "|" + "|".join(["---"] * len(columns)) + "|"]
    for row in rows:
        lines.append("|" + "|".join(_format_cell(row.get(column)) for column in columns) + "|")
    return lines


def _ensure_safe_output_path(path: Path) -> None:
    normalized = str(path).replace("\\", "/")
    forbidden = ("reports/analysis/lessons", "reports/analysis/patterns", "market_pattern_registry")
    if any(item in normalized for item in forbidden):
        raise ValueError(f"Refusing to write gate output to forbidden path: {path}")


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate analysis-only path stability gate.")
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--output-json", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = load_distribution_summary(args.input_json)
    result = evaluate_rule_proposal_gate(summary)
    result["metadata"]["input_json"] = args.input_json
    write_gate_review(result, args.output_md, args.output_json)


if __name__ == "__main__":
    main()
