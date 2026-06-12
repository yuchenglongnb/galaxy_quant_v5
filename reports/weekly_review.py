# -*- coding: utf-8 -*-
"""Build a weekly auction-factor review from persisted validation artifacts."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd


SIGNAL_ORDER = ["trap", "reversal", "trend"]
SIGNAL_LABELS = {
    "trap": "CP风险",
    "reversal": "反核机会",
    "trend": "趋势机会",
}


@dataclass
class WeeklyReviewPaths:
    validation_dir: str = os.path.join("reports", "validation")
    analysis_dir: str = os.path.join("reports", "analysis")


class WeeklyReviewBuilder:
    """Summarize weekly signal quality without treating leaked labels as forecasts."""

    def __init__(self, paths: WeeklyReviewPaths | None = None):
        self.paths = paths or WeeklyReviewPaths()

    @staticmethod
    def default_week_range(today=None):
        today = today or datetime.now().date()
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=4)
        return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")

    def build(self, start_date=None, end_date=None):
        if not start_date or not end_date:
            start_date, end_date = self.default_week_range()

        detail = self._load_detail(start_date, end_date)
        statuses = self._load_daily_statuses(start_date, end_date)
        metrics = self._aggregate_metrics(detail)
        actionable_metrics = self._aggregate_metrics(self._actionable_only(detail))
        daily_metrics = self._aggregate_daily_metrics(detail)
        failures = self._records(detail[detail["validation_result"] == "failed"]) if not detail.empty else []
        successes = self._records(detail[detail["validation_result"] == "success"]) if not detail.empty else []
        snapshot_counts = self._load_snapshot_counts(start_date, end_date)

        payload = {
            "week": {"start": start_date, "end": end_date},
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "data_status": statuses,
            "snapshot_counts": snapshot_counts,
            "metrics": metrics,
            "actionable_metrics": actionable_metrics,
            "daily_metrics": daily_metrics,
            "notable_failures": failures[:30],
            "notable_successes": successes[:30],
            "integrity_warnings": [
                "Candidate generation is separated from outcome validation: body_pct is a post-close label only.",
                "CP validation uses the auction-time CP candidate and label body_pct < 0.",
                "Reversal validation uses the auction-time SA candidate and label body_pct > 0; body_pct > 2 is retained as a separate strong outcome.",
                "Trend validation uses prior trend plus auction-time conditions and label body_pct > 0; body_pct > 2 is retained as a separate strong outcome.",
                "For machine learning, use only features available by the decision timestamp; use body_pct only as the label.",
            ],
            "recommendations": self._recommendations(detail, metrics),
        }
        return self._sanitize(payload)

    def save(self, payload):
        week = payload["week"]
        out_dir = os.path.join(self.paths.analysis_dir, "weekly", f"{week['start']}_{week['end']}")
        os.makedirs(out_dir, exist_ok=True)
        json_path = os.path.join(out_dir, "week_review.json")
        md_path = os.path.join(out_dir, "week_review.md")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self._format_markdown(payload))
        return md_path, json_path

    def _load_detail(self, start_date, end_date):
        path = os.path.join(self.paths.validation_dir, "auction_signal_validation.csv")
        if not os.path.exists(path):
            return pd.DataFrame()
        df = pd.read_csv(path, encoding="utf-8-sig", dtype={"date": str})
        return df[(df["date"] >= str(start_date)) & (df["date"] <= str(end_date))].copy()

    def _load_daily_statuses(self, start_date, end_date):
        daily_root = os.path.join(self.paths.analysis_dir, "daily")
        if not os.path.isdir(daily_root):
            return []
        rows = []
        for date in sorted(os.listdir(daily_root)):
            if date < str(start_date) or date > str(end_date):
                continue
            path = os.path.join(daily_root, date, "auction_review.json")
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                review = json.load(f)
            status = review.get("data_status", {}) or {}
            rows.append({
                "date": date,
                "session_state": status.get("session_state", "unknown"),
                "fetched_at": status.get("fetched_at", ""),
                "validation_scope": review.get("validation_scope", ""),
                "market_oar": round(float(review.get("market_oar", 0) or 0), 4),
            })
        return rows

    def _load_snapshot_counts(self, start_date, end_date):
        daily_root = os.path.join(self.paths.validation_dir, "daily")
        rows = []
        if not os.path.isdir(daily_root):
            return rows
        files = {
            "index": "factor_snapshot_index.csv",
            "etf": "factor_snapshot_etf.csv",
            "stock": "factor_snapshot_stock.csv",
            "industry_topk": "factor_snapshot_industry_topk.csv",
        }
        for date in sorted(os.listdir(daily_root)):
            if date < str(start_date) or date > str(end_date):
                continue
            row = {"date": date}
            for key, filename in files.items():
                path = os.path.join(daily_root, date, filename)
                row[key] = len(pd.read_csv(path, encoding="utf-8-sig")) if os.path.exists(path) else 0
            rows.append(row)
        return rows

    def _aggregate_metrics(self, detail):
        if detail.empty:
            return []
        df = detail.copy()
        df["validation_success_bool"] = df["validation_result"] == "success"
        df["body_pct"] = pd.to_numeric(df["body_pct"], errors="coerce")
        df["directed_body_pct"] = df["body_pct"] * df["signal_category"].map(
            {"trap": -1.0, "reversal": 1.0, "trend": 1.0}
        ).fillna(0.0)
        grouped = (
            df.groupby("signal_category", dropna=False)
            .agg(
                trigger_count=("signal_category", "size"),
                success_count=("validation_success_bool", "sum"),
                avg_body_pct=("body_pct", "mean"),
                median_body_pct=("body_pct", "median"),
                avg_directed_body_pct=("directed_body_pct", "mean"),
                median_directed_body_pct=("directed_body_pct", "median"),
                p25_directed_body_pct=("directed_body_pct", lambda values: values.quantile(0.25)),
                p75_directed_body_pct=("directed_body_pct", lambda values: values.quantile(0.75)),
            )
            .reset_index()
        )
        grouped["failure_count"] = grouped["trigger_count"] - grouped["success_count"]
        grouped["success_rate"] = grouped["success_count"] / grouped["trigger_count"] * 100
        grouped["signal_family"] = grouped["signal_category"].map(SIGNAL_LABELS)
        return self._records(grouped)

    def _aggregate_daily_metrics(self, detail):
        if detail.empty:
            return []
        df = detail.copy()
        df["validation_success_bool"] = df["validation_result"] == "success"
        df["body_pct"] = pd.to_numeric(df["body_pct"], errors="coerce")
        df["directed_body_pct"] = df["body_pct"] * df["signal_category"].map(
            {"trap": -1.0, "reversal": 1.0, "trend": 1.0}
        ).fillna(0.0)
        grouped = (
            df.groupby(["date", "signal_category"], dropna=False)
            .agg(
                trigger_count=("signal_category", "size"),
                success_count=("validation_success_bool", "sum"),
                avg_body_pct=("body_pct", "mean"),
                avg_directed_body_pct=("directed_body_pct", "mean"),
                median_directed_body_pct=("directed_body_pct", "median"),
            )
            .reset_index()
        )
        grouped["failure_count"] = grouped["trigger_count"] - grouped["success_count"]
        grouped["success_rate"] = grouped["success_count"] / grouped["trigger_count"] * 100
        grouped["signal_family"] = grouped["signal_category"].map(SIGNAL_LABELS)
        return self._records(grouped)

    @staticmethod
    def _actionable_only(detail):
        if detail.empty or "actionable" not in detail.columns:
            return detail.iloc[0:0].copy()
        values = detail["actionable"].astype(str).str.strip().str.lower()
        return detail[values.isin({"true", "1", "yes", "y"})].copy()

    def _recommendations(self, detail, metrics):
        recommendations = [
            {
                "priority": "P0",
                "title": "Keep candidate and outcome fields separate",
                "detail": "The core flow now records CP/SA/trend candidates using auction-time features and computes body_pct labels after close. Keep this boundary when adding datasets and models.",
            },
            {
                "priority": "P0",
                "title": "Add a market-regime layer before CP/SA routing",
                "detail": "Use index body breadth, ETF breadth, OAR, growth/value spread and prior-day dispersion to classify continuation, repair, risk-off and mixed regimes.",
            },
            {
                "priority": "P1",
                "title": "Calibrate hard rules before training complex models",
                "detail": "Build conditional win-rate tables by regime, universe, CP/SA bins, auction_pct bins, rank bins and pos_5d bins.",
            },
            {
                "priority": "P1",
                "title": "Train tabular probability models after enough closed samples accumulate",
                "detail": "Use logistic regression as baseline, then LightGBM or XGBoost for nonlinear interactions. Predict P(body_pct < 0) for CP and P(body_pct > 0) for opportunity candidates.",
            },
            {
                "priority": "P2",
                "title": "Add a daily top-k ranker",
                "detail": "After classification is stable, group samples by date and rank candidates with LambdaMART/NDCG. Use qid=date and evaluate precision@k.",
            },
            {
                "priority": "P2",
                "title": "Use RAG/LLM only for explanation and analog retrieval",
                "detail": "Retrieve similar historical days and explain conflicts. Do not let the LLM calculate labels, CP, SA or final probabilities.",
            },
        ]
        return recommendations

    @staticmethod
    def _records(df):
        if df is None or len(df) == 0:
            return []
        return df.to_dict(orient="records")

    @staticmethod
    def _sanitize(value):
        if isinstance(value, dict):
            return {str(k): WeeklyReviewBuilder._sanitize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [WeeklyReviewBuilder._sanitize(v) for v in value]
        if hasattr(value, "item"):
            try:
                return value.item()
            except Exception:
                pass
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass
        if isinstance(value, float):
            return round(value, 4)
        return value

    def _format_markdown(self, payload):
        week = payload["week"]
        lines = [
            f"# Auction Weekly Review {week['start']} - {week['end']}",
            "",
            "## Data Status",
        ]
        for row in payload["data_status"]:
            lines.append(
                f"- {row['date']}: state={row['session_state']}, scope={row['validation_scope']}, "
                f"OAR={row['market_oar']}, fetched_at={row['fetched_at']}"
            )

        lines.extend(["", "## Weekly Metrics"])
        for row in payload["metrics"]:
            lines.append(
                f"- {row.get('signal_family')}({row.get('signal_category')}): "
                f"{row.get('success_count')}/{row.get('trigger_count')}, "
                f"directed_body={row.get('avg_directed_body_pct')}%, "
                f"median={row.get('median_directed_body_pct')}%, "
                f"direction_hit={row.get('success_rate')}%"
            )

        lines.extend(["", "## Daily Metrics"])
        for row in payload["daily_metrics"]:
            lines.append(
                f"- {row.get('date')} {row.get('signal_family')}: "
                f"{row.get('success_count')}/{row.get('trigger_count')}, "
                f"directed_body={row.get('avg_directed_body_pct')}%, "
                f"direction_hit={row.get('success_rate')}%"
            )

        lines.extend(["", "## Actionable Shortlist Metrics"])
        for row in payload.get("actionable_metrics", []):
            lines.append(
                f"- {row.get('signal_family')}({row.get('signal_category')}): "
                f"{row.get('success_count')}/{row.get('trigger_count')}, "
                f"directed_body={row.get('avg_directed_body_pct')}%, "
                f"median={row.get('median_directed_body_pct')}%, "
                f"direction_hit={row.get('success_rate')}%"
            )

        lines.extend(["", "## Integrity Warnings"])
        for item in payload["integrity_warnings"]:
            lines.append(f"- {item}")

        lines.extend(["", "## Recommendations"])
        for item in payload["recommendations"]:
            lines.append(f"- [{item['priority']}] {item['title']}: {item['detail']}")

        lines.extend(["", "## Notable Signal Failures"])
        for row in payload["notable_failures"]:
            lines.append(
                f"- {row.get('date')} {row.get('signal_family')} {row.get('target_type')} {row.get('name')}: "
                f"cp={row.get('cp')}, sa={row.get('sa')}, "
                f"auction={row.get('auction_pct')}%, body={row.get('body_pct')}%"
            )
        lines.append("")
        return "\n".join(lines)


def run_weekly_review(start_date=None, end_date=None):
    builder = WeeklyReviewBuilder()
    payload = builder.build(start_date=start_date, end_date=end_date)
    md_path, json_path = builder.save(payload)
    print(f"[weekly] Markdown: {os.path.abspath(md_path)}")
    print(f"[weekly] JSON: {os.path.abspath(json_path)}")
    return payload
