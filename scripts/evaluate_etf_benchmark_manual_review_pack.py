# -*- coding: utf-8 -*-
"""Build a read-only ETF benchmark manual review pack."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.encoding import configure_utf8_console  # noqa: E402


EVAL_ROOT = ROOT / "reports" / "analysis" / "evaluations"
BENCHMARK_MAP_PATH = ROOT / "watchlists" / "group_benchmark_map.csv"
REVIEW_GROUPS = [
    "军工电子",
    "其他计算机设备",
    "其他电源设备",
    "其他专用设备",
    "专业工程",
    "磷肥及磷化工",
]


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            with path.open("r", encoding=encoding, newline="") as fh:
                return list(csv.DictReader(fh))
        except UnicodeDecodeError:
            continue
        except Exception:
            return []
    return []


def _safe_float(value) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _price_action(row: dict) -> dict:
    return {
        "auction_pct": _safe_float(row.get("auction_pct")),
        "close_pct": _safe_float(row.get("close_pct")),
        "body_pct": _safe_float(row.get("body_pct")),
        "amount": _safe_float(row.get("amount")),
        "vol_ratio": _safe_float(row.get("vol_ratio")),
    }


def _etf_rows(date: str) -> dict[str, dict]:
    rows = _read_csv(ROOT / "reports" / "validation" / "daily" / date / "factor_snapshot_etf.csv")
    by_code = {}
    for row in rows:
        code = str(row.get("code", "") or "")
        if code:
            by_code[code] = row
    for row in _read_csv(ROOT / "AmazingData_Store" / date / "indices.csv"):
        code = str(row.get("code", "") or "")
        if code and code not in by_code and code.startswith(("15", "51", "56")):
            by_code[code] = row
    return by_code


def _intraday_codes(date: str) -> set[str]:
    return {
        str(row.get("code", "") or "")
        for row in _read_csv(ROOT / "AmazingData_Store" / date / "intraday" / "etf_1min.csv")
        if str(row.get("code", "") or "")
    }


def _benchmark_map() -> dict[str, dict]:
    return {str(row.get("group", "") or ""): row for row in _read_csv(BENCHMARK_MAP_PATH) if str(row.get("group", "") or "")}


def _name_score(group: str, etf_name: str) -> int:
    if not group or not etf_name:
        return 0
    if group == etf_name:
        return 3
    score = 0
    for token in ("军工", "电子", "计算机", "电源", "专用设备", "工程", "化工", "磷", "半导体", "AI"):
        if token in group and token in etf_name:
            score += 1
    return score


def _candidate_for_group(group: str, etfs: dict[str, dict], intraday_codes: set[str], mapped_code: str = "") -> list[dict]:
    candidates = []
    for code, row in etfs.items():
        name = str(row.get("name", "") or row.get("theme_cluster", "") or "")
        score = _name_score(group, name)
        if mapped_code and code == mapped_code:
            score = max(score, 3)
        if score <= 0:
            continue
        if score >= 3:
            confidence = "high"
        elif score == 2:
            confidence = "medium"
        else:
            confidence = "low"
        candidates.append(
            {
                "code": code,
                "name": name,
                "evidence_source": ["existing_benchmark_map"] if mapped_code and code == mapped_code else ["available_etf_universe_name_match"],
                "same_theme_evidence": score >= 2,
                "intraday_available": code in intraday_codes,
                "close_available": True,
                "price_action_on_20260629": _price_action(row),
                "confidence": confidence,
                "reason": f"name_match_score={score}",
                "recommended_action": "manual_review",
            }
        )
    confidence_order = {"high": 0, "medium": 1, "low": 2}
    return sorted(candidates, key=lambda item: (confidence_order.get(item["confidence"], 3), item["code"]))


def _review_group(group: str, etfs: dict[str, dict], intraday_codes: set[str], mapping: dict[str, dict]) -> dict:
    mapped = mapping.get(group, {}) or {}
    current = str(mapped.get("benchmark_etf_code", "") or "")
    candidates = _candidate_for_group(group, etfs, intraday_codes, mapped_code=current)
    best = candidates[0] if candidates else None
    confidence = best["confidence"] if best else "none"
    return {
        "group": group,
        "current_benchmark": current or None,
        "candidate_benchmarks": candidates,
        "best_candidate": best,
        "confidence": confidence,
        "recommended_action": "manual_review_required",
        "should_auto_update_map": False,
    }


def _bucket_reviews(group_reviews: list[dict], confidence: str) -> list[dict]:
    return [row for row in group_reviews if row.get("confidence") == confidence]


def build_payload(date: str) -> dict:
    date = str(date)
    normalization = _load_json(EVAL_ROOT / f"trend_confirmation_scope_normalization_{date}.json")
    review_groups = normalization.get("benchmark_map_missing_groups") or REVIEW_GROUPS
    etfs = _etf_rows(date)
    intraday_codes = _intraday_codes(date)
    mapping = _benchmark_map()
    group_review = [_review_group(group, etfs, intraday_codes, mapping) for group in review_groups]
    existing_diff = BENCHMARK_MAP_PATH.exists() and _has_git_diff(BENCHMARK_MAP_PATH)
    high = _bucket_reviews(group_review, "high")
    medium = _bucket_reviews(group_review, "medium")
    low = _bucket_reviews(group_review, "low")
    none = [row["group"] for row in group_review if row.get("confidence") == "none"]
    warnings = []
    if existing_diff:
        warnings.append("existing_group_benchmark_map_diff_requires_separate_review")
    conclusions = [
        "read_only_review_pack",
        "benchmark_map_not_modified",
        "manual_review_required",
        "keep_trend_active_disabled",
        "no_strategy_rule_change",
        "evaluator_change_not_required",
    ]
    if not high:
        conclusions.append("no_auto_benchmark_mapping")
    return {
        "date": date,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "review_groups": review_groups,
        "group_review": group_review,
        "high_confidence_candidates": high,
        "medium_confidence_candidates": medium,
        "low_confidence_candidates": low,
        "no_candidate_groups": none,
        "benchmark_map_modified": False,
        "benchmark_map_change_required": False,
        "existing_benchmark_map_diff_detected": bool(existing_diff),
        "manual_review_required": True,
        "trend_active_allowed": False,
        "evaluator_change_required": False,
        "recommended_next_actions": [
            "human_review_benchmark_candidates",
            "approve_or_reject_group_benchmark_map_patch_separately",
            "keep_trend_active_disabled",
        ],
        "warnings": warnings,
        "conclusion": conclusions,
    }


def _has_git_diff(path: Path) -> bool:
    import subprocess

    try:
        rel = str(path.relative_to(ROOT))
    except ValueError:
        rel = str(path)
    result = subprocess.run(
        ["git", "diff", "--quiet", "--", rel],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 1


def _render_markdown(payload: dict) -> str:
    lines = [
        f"# ETF Benchmark Manual Review Pack {payload['date']}",
        "",
        f"- review_groups: `{payload['review_groups']}`",
        f"- benchmark_map_modified: `{payload['benchmark_map_modified']}`",
        f"- existing_benchmark_map_diff_detected: `{payload['existing_benchmark_map_diff_detected']}`",
        f"- trend_active_allowed: `{payload['trend_active_allowed']}`",
        f"- evaluator_change_required: `{payload['evaluator_change_required']}`",
        "",
        "## Group Review",
        "",
    ]
    for row in payload["group_review"]:
        lines.append(f"- {json.dumps(row, ensure_ascii=False)}")
    lines.extend(["", "## Conclusion", ""])
    for item in payload["conclusion"]:
        lines.append(f"- {item}")
    if payload["warnings"]:
        lines.extend(["", "## Warnings", ""])
        for item in payload["warnings"]:
            lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict) -> tuple[Path, Path]:
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = EVAL_ROOT / f"etf_benchmark_manual_review_pack_{payload['date']}.json"
    md_path = EVAL_ROOT / f"etf_benchmark_manual_review_pack_{payload['date']}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Build read-only ETF benchmark manual review pack.")
    parser.add_argument("--date", required=True, help="Trade date YYYYMMDD")
    return parser.parse_args(argv)


def main(argv=None):
    configure_utf8_console()
    args = parse_args(argv)
    payload = build_payload(args.date)
    json_path, md_path = write_outputs(payload)
    print(
        json.dumps(
            {
                "json": str(json_path.relative_to(ROOT)),
                "md": str(md_path.relative_to(ROOT)),
                "review_groups": payload["review_groups"],
                "high": len(payload["high_confidence_candidates"]),
                "medium": len(payload["medium_confidence_candidates"]),
                "low": len(payload["low_confidence_candidates"]),
                "none": len(payload["no_candidate_groups"]),
                "benchmark_map_modified": payload["benchmark_map_modified"],
                "existing_benchmark_map_diff_detected": payload["existing_benchmark_map_diff_detected"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
