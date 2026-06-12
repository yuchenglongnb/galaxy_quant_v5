# -*- coding: utf-8 -*-
"""Summarize auction signal quality by market regime and leading theme clusters."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime

import pandas as pd


SIGNAL_LABELS = {
    "trap": "CP风险",
    "reversal": "反核机会",
    "trend": "趋势机会",
}


@dataclass
class RegimeClusterPaths:
    validation_path: str = os.path.join("reports", "validation", "auction_signal_validation.csv")
    analysis_daily_dir: str = os.path.join("reports", "analysis", "daily")
    output_root: str = os.path.join("reports", "analysis", "regime_cluster")


class RegimeClusterReviewBuilder:
    """Build conditional win-rate tables by regime, universe, and theme cluster."""

    def __init__(self, paths: RegimeClusterPaths | None = None):
        self.paths = paths or RegimeClusterPaths()

    def build(self, start_date=None, end_date=None):
        detail = self._load_detail(start_date, end_date)
        daily = self._load_daily_reviews(start_date, end_date)
        if detail.empty:
            raise ValueError("No closed auction validation details found for the requested range.")

        merged = detail.merge(daily, on="date", how="left")
        merged["leading_clusters"] = merged["leading_clusters"].apply(self._ensure_list)
        exploded = merged.explode("leading_clusters")
        exploded["leading_clusters"] = exploded["leading_clusters"].fillna("")

        regime_signal = self._summarize(merged, ["market_regime", "signal_category"])
        regime_universe = self._summarize(merged, ["market_regime", "signal_category", "target_type"])
        regime_cluster = self._summarize(
            exploded[exploded["leading_clusters"] != ""],
            ["market_regime", "signal_category", "leading_clusters"],
        )
        regime_gate = self._summarize_environment_gate(daily)

        payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "start_date": str(detail["date"].min()),
            "end_date": str(detail["date"].max()),
            "sample_count": int(len(detail)),
            "trading_days": int(detail["date"].nunique()),
            "recommendation": "先看 environment_gate，再看 leading_clusters，最后才看个股 CP/反核/趋势。",
        }
        return {
            "detail": merged,
            "daily": daily,
            "regime_signal": regime_signal,
            "regime_universe": regime_universe,
            "regime_cluster": regime_cluster,
            "regime_gate": regime_gate,
            "payload": payload,
        }

    def save(self, result):
        payload = result["payload"]
        output_dir = os.path.join(self.paths.output_root, f"{payload['start_date']}_{payload['end_date']}")
        os.makedirs(output_dir, exist_ok=True)
        paths = {
            "regime_signal": os.path.join(output_dir, "regime_signal_summary.csv"),
            "regime_universe": os.path.join(output_dir, "regime_universe_summary.csv"),
            "regime_cluster": os.path.join(output_dir, "regime_cluster_summary.csv"),
            "regime_gate": os.path.join(output_dir, "regime_gate_daily.csv"),
            "metadata": os.path.join(output_dir, "regime_cluster_metadata.json"),
            "report": os.path.join(output_dir, "regime_cluster_report.md"),
        }
        result["regime_signal"].to_csv(paths["regime_signal"], index=False, encoding="utf-8-sig")
        result["regime_universe"].to_csv(paths["regime_universe"], index=False, encoding="utf-8-sig")
        result["regime_cluster"].to_csv(paths["regime_cluster"], index=False, encoding="utf-8-sig")
        result["regime_gate"].to_csv(paths["regime_gate"], index=False, encoding="utf-8-sig")
        with open(paths["metadata"], "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        with open(paths["report"], "w", encoding="utf-8") as f:
            f.write(self._format_report(result))
        return paths

    def _load_detail(self, start_date, end_date):
        if not os.path.exists(self.paths.validation_path):
            return pd.DataFrame()
        df = pd.read_csv(self.paths.validation_path, encoding="utf-8-sig", dtype={"date": str})
        if start_date:
            df = df[df["date"] >= str(start_date)]
        if end_date:
            df = df[df["date"] <= str(end_date)]
        if "validation_scope" in df.columns:
            df = df[df["validation_scope"] == "post_close_final"].copy()
        else:
            df = df.copy()
        df["body_pct"] = pd.to_numeric(df.get("body_pct"), errors="coerce")
        df["validation_success_bool"] = df.get("validation_result", "").astype(str).eq("success")
        df["directed_body_pct"] = df["body_pct"] * df["signal_category"].map(
            {"trap": -1.0, "reversal": 1.0, "trend": 1.0}
        ).fillna(0.0)
        df["signal_family"] = df["signal_category"].map(SIGNAL_LABELS).fillna(df["signal_category"])
        return df

    def _load_daily_reviews(self, start_date, end_date):
        rows = []
        root = self.paths.analysis_daily_dir
        if not os.path.isdir(root):
            return pd.DataFrame(columns=["date", "market_regime_label", "leading_clusters", "environment_decision", "environment_note"])
        for date in sorted(os.listdir(root)):
            if start_date and date < str(start_date):
                continue
            if end_date and date > str(end_date):
                continue
            path = os.path.join(root, date, "auction_review.json")
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    review = json.load(f)
            except Exception:
                continue
            regime = review.get("market_regime", {}) or {}
            gate = review.get("environment_gate", {}) or {}
            rows.append({
                "date": str(date),
                "market_regime_label": str(regime.get("label", "") or ""),
                "leading_clusters": review.get("leading_clusters", []) or [],
                "environment_decision": str(gate.get("decision", "") or ""),
                "environment_note": str(gate.get("note", "") or ""),
                "broad_long_allowed": bool(gate.get("broad_long_allowed", False)),
            })
        return pd.DataFrame(rows)

    def _summarize(self, df, group_cols):
        if df.empty:
            return pd.DataFrame()
        grouped = (
            df.groupby(group_cols, dropna=False)
            .agg(
                sample_count=("signal_category", "size"),
                success_count=("validation_success_bool", "sum"),
                avg_body_pct=("body_pct", "mean"),
                median_body_pct=("body_pct", "median"),
                avg_directed_body_pct=("directed_body_pct", "mean"),
                median_directed_body_pct=("directed_body_pct", "median"),
            )
            .reset_index()
        )
        grouped["success_rate"] = grouped["success_count"] / grouped["sample_count"] * 100
        grouped["avg_body_pct"] = grouped["avg_body_pct"].round(4)
        grouped["median_body_pct"] = grouped["median_body_pct"].round(4)
        grouped["avg_directed_body_pct"] = grouped["avg_directed_body_pct"].round(4)
        grouped["median_directed_body_pct"] = grouped["median_directed_body_pct"].round(4)
        grouped["success_rate"] = grouped["success_rate"].round(2)
        return grouped.sort_values(["sample_count", "avg_directed_body_pct"], ascending=[False, False])

    def _summarize_environment_gate(self, daily):
        if daily.empty:
            return pd.DataFrame()
        work = daily.copy()
        work["cluster_count"] = work["leading_clusters"].apply(lambda x: len(self._ensure_list(x)))
        return work.sort_values("date")

    @staticmethod
    def _ensure_list(value):
        if isinstance(value, list):
            return value
        if pd.isna(value):
            return []
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            try:
                parsed = json.loads(text)
                return parsed if isinstance(parsed, list) else [text]
            except Exception:
                return [text]
        return [str(value)]

    def _format_report(self, result):
        payload = result["payload"]
        lines = [
            f"# Regime And Theme Cluster Review {payload['start_date']} - {payload['end_date']}",
            "",
            f"- 样本数: {payload['sample_count']}",
            f"- 交易日: {payload['trading_days']}",
            f"- 方法: {payload['recommendation']}",
            "",
            "## Environment Gate Daily",
        ]
        for _, row in result["regime_gate"].iterrows():
            clusters = ", ".join(self._ensure_list(row.get("leading_clusters")))
            lines.append(
                f"- {row.get('date')}: regime={row.get('market_regime_label')}, "
                f"decision={row.get('environment_decision')}, "
                f"broad_long_allowed={row.get('broad_long_allowed')}, "
                f"clusters={clusters or '-'}"
            )
        lines.extend(["", "## By Regime And Signal"])
        for _, row in result["regime_signal"].iterrows():
            lines.append(
                f"- {row.get('market_regime')} / {row.get('signal_family', row.get('signal_category'))}: "
                f"{int(row.get('success_count', 0))}/{int(row.get('sample_count', 0))}, "
                f"directed={row.get('avg_directed_body_pct')}%, hit={row.get('success_rate')}%"
            )
        lines.extend(["", "## Top Regime Clusters"])
        for _, row in result["regime_cluster"].head(20).iterrows():
            lines.append(
                f"- {row.get('market_regime')} / {row.get('leading_clusters')} / "
                f"{row.get('signal_family', row.get('signal_category'))}: "
                f"{int(row.get('success_count', 0))}/{int(row.get('sample_count', 0))}, "
                f"directed={row.get('avg_directed_body_pct')}%, hit={row.get('success_rate')}%"
            )
        lines.append("")
        return "\n".join(lines)


def run_regime_cluster_review(start_date=None, end_date=None):
    builder = RegimeClusterReviewBuilder()
    result = builder.build(start_date=start_date, end_date=end_date)
    paths = builder.save(result)
    print(f"[regime] Regime summary: {os.path.abspath(paths['regime_signal'])}")
    print(f"[regime] Cluster summary: {os.path.abspath(paths['regime_cluster'])}")
    print(f"[regime] Report: {os.path.abspath(paths['report'])}")
    return result
