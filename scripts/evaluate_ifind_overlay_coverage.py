# -*- coding: utf-8 -*-
"""Evaluate local iFinD overlay coverage for the tracked stock pool."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyzers.evaluators.leading_cluster_evidence import LeadingClusterEvidenceBuilder
from providers.ifind_theme_provider import IFindThemeProvider
from utils.encoding import configure_utf8_console


def _normalize_overlay_with_cluster(provider, overlay):
    config = LeadingClusterEvidenceBuilder.load_config()
    alias_map = config.get("ifind_cluster_alias", {}) or {}
    frame = overlay.copy()
    if frame.empty:
        frame["ifind_cluster"] = ""
        return frame

    def split_items(value):
        text = str(value or "").strip()
        if not text:
            return []
        return [item.strip() for item in text.split(";") if item.strip()]

    frame["ifind_signal_concepts"] = frame.get("ifind_signal_concepts", "").fillna("")
    frame["ifind_cluster"] = frame["ifind_signal_concepts"].map(
        lambda value: next((alias_map[item] for item in split_items(value) if item in alias_map), "")
    )
    return frame


def evaluate(date_int, top_missing=30):
    provider = IFindThemeProvider()
    pool = provider.load_stock_pool()
    overlay = provider.load_overlay()
    overlay = _normalize_overlay_with_cluster(provider, overlay)

    ifind_dir = ROOT / "AmazingData_Store" / str(date_int) / "ifind"
    sector_path = ifind_dir / "sector_strength_snapshot.csv"
    catalyst_path = ifind_dir / "catalyst_notice_digest.csv"

    sector = pd.read_csv(sector_path, encoding="utf-8-sig") if sector_path.exists() else pd.DataFrame()
    catalyst = pd.read_csv(catalyst_path, encoding="utf-8-sig", dtype={"code": str}) if catalyst_path.exists() else pd.DataFrame()

    overlay_cols = [col for col in overlay.columns if col != "name"]
    merged = pool.merge(overlay[overlay_cols], on="code", how="left")
    merged["has_ifind_overlay"] = merged["ifind_ths_industry"].fillna("").astype(str).str.strip() != ""
    merged["has_ifind_signal_concepts"] = merged["ifind_signal_concepts"].fillna("").astype(str).str.strip() != ""
    merged["has_ifind_cluster"] = merged["ifind_cluster"].fillna("").astype(str).str.strip() != ""

    sector_clusters = []
    if not sector.empty and "concept" in sector.columns:
        alias_map = LeadingClusterEvidenceBuilder.load_config().get("ifind_cluster_alias", {}) or {}
        sector_clusters = sorted({alias_map.get(str(concept).strip(), "") for concept in sector["concept"].fillna("") if alias_map.get(str(concept).strip(), "")})
        sector_clusters = [name for name in sector_clusters if name]

    catalyst_codes = sorted(set(catalyst["code"].astype(str))) if not catalyst.empty and "code" in catalyst.columns else []

    missing = merged.loc[~merged["has_ifind_overlay"], ["code", "name", "group"]].copy()
    missing_groups = (
        missing.groupby("group", as_index=False)
        .agg(missing_count=("code", "count"))
        .sort_values(["missing_count", "group"], ascending=[False, True])
        .reset_index(drop=True)
    )
    suggested_next_batch = missing.head(top_missing).to_dict(orient="records")

    payload = {
        "date": str(date_int),
        "stock_pool_total": int(len(pool)),
        "ifind_overlay_count": int(merged["has_ifind_overlay"].sum()),
        "ifind_signal_concepts_count": int(merged["has_ifind_signal_concepts"].sum()),
        "ifind_cluster_count": int(merged["has_ifind_cluster"].sum()),
        "sector_strength_cluster_count": int(len(sector_clusters)),
        "sector_strength_clusters": sector_clusters,
        "catalyst_digest_stock_count": int(len(catalyst_codes)),
        "coverage_ratio": round(float(merged["has_ifind_overlay"].mean()) if len(merged) else 0.0, 4),
        "signal_concept_coverage_ratio": round(float(merged["has_ifind_signal_concepts"].mean()) if len(merged) else 0.0, 4),
        "cluster_coverage_ratio": round(float(merged["has_ifind_cluster"].mean()) if len(merged) else 0.0, 4),
        "top_missing_groups": missing_groups.head(10).to_dict(orient="records"),
        "suggested_next_batch": suggested_next_batch,
    }
    return payload


def write_outputs(payload):
    date_int = payload["date"]
    out_dir = ROOT / "reports" / "analysis" / "evaluations"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"ifind_overlay_coverage_{date_int}.json"
    md_path = out_dir / f"ifind_overlay_coverage_{date_int}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# iFinD Overlay Coverage {date_int}",
        "",
        f"- stock_pool_total: `{payload['stock_pool_total']}`",
        f"- ifind_overlay_count: `{payload['ifind_overlay_count']}`",
        f"- ifind_signal_concepts_count: `{payload['ifind_signal_concepts_count']}`",
        f"- ifind_cluster_count: `{payload['ifind_cluster_count']}`",
        f"- sector_strength_cluster_count: `{payload['sector_strength_cluster_count']}`",
        f"- catalyst_digest_stock_count: `{payload['catalyst_digest_stock_count']}`",
        f"- coverage_ratio: `{payload['coverage_ratio']:.2%}`",
        f"- signal_concept_coverage_ratio: `{payload['signal_concept_coverage_ratio']:.2%}`",
        f"- cluster_coverage_ratio: `{payload['cluster_coverage_ratio']:.2%}`",
        "",
        "## Top Missing Groups",
        "",
        "| group | missing_count |",
        "|---|---:|",
    ]
    for row in payload["top_missing_groups"]:
        lines.append(f"| {row.get('group', '') or '-'} | {row.get('missing_count', 0)} |")
    lines.extend(
        [
            "",
            "## Suggested Next Batch",
            "",
            "| code | name | group |",
            "|---|---|---|",
        ]
    )
    for row in payload["suggested_next_batch"]:
        lines.append(f"| {row.get('code', '')} | {row.get('name', '')} | {row.get('group', '') or '-'} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main():
    configure_utf8_console()
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--top-missing", type=int, default=30)
    args = parser.parse_args()

    payload = evaluate(int(args.date), top_missing=args.top_missing)
    json_path, md_path = write_outputs(payload)
    print(f"[ok] coverage json: {json_path}")
    print(f"[ok] coverage md: {md_path}")


if __name__ == "__main__":
    main()
