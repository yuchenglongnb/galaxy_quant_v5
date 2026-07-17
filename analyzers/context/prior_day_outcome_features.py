"""Derive observation-only prior-day outcome features from validation artifacts."""

from __future__ import annotations

from collections import Counter
from typing import Iterable

import pandas as pd


RISK_PATHS = {
    "one_way_selloff",
    "rush_up_fade",
    "high_open_trap",
    "close_near_low",
    "low_open_rebound_failed",
}
FADE_PATHS = {"rush_up_fade", "high_open_trap"}
WEAK_CLOSE_PATHS = {"close_near_low", "low_open_rebound_failed"}


class PriorDayOutcomeFeatureBuilder:
    """Build stable evidence fields without changing any active gate."""

    @classmethod
    def build(
        cls,
        detail_df: pd.DataFrame | None,
        metrics_df: pd.DataFrame | None = None,
        sector_evidence: Iterable[dict] | None = None,
    ) -> dict:
        detail = detail_df.copy() if isinstance(detail_df, pd.DataFrame) else pd.DataFrame()
        metrics = metrics_df.copy() if isinstance(metrics_df, pd.DataFrame) else pd.DataFrame()
        trend = cls._category(detail, "trend")
        trend_bodies = cls._numeric_series(trend, "body_pct")
        trend_count = int(len(trend_bodies))
        trend_success_rate = cls._success_rate(trend, metrics, "trend")

        path_values = cls._path_values(detail)
        path_count = len(path_values)
        one_way_count = sum(value == "one_way_selloff" for value in path_values)
        fade_count = sum(value in FADE_PATHS for value in path_values)
        weak_close_count = sum(value in WEAK_CLOSE_PATHS for value in path_values)
        risk_count = sum(value in RISK_PATHS for value in path_values)

        clusters = cls._positive_long_clusters(detail)
        cluster_counts = Counter(clusters)
        positive_count = int(sum(cluster_counts.values()))
        ordered_counts = sorted(cluster_counts.values(), reverse=True)
        top1_count = ordered_counts[0] if ordered_counts else 0
        top3_count = sum(ordered_counts[:3])
        top1_name = cluster_counts.most_common(1)[0][0] if cluster_counts else ""
        top1_share = cls._ratio(top1_count, positive_count)
        top3_share = cls._ratio(top3_count, positive_count)

        if trend_count >= 20 and path_count >= 20:
            confidence = "high"
        elif trend_count >= 8 and path_count >= 8:
            confidence = "medium"
        else:
            confidence = "low"

        concentration_label = "insufficient_samples"
        if positive_count >= 3:
            concentration_label = (
                "concentrated"
                if top1_share >= 0.35 or top3_share >= 0.65
                else "dispersed"
            )

        missing = []
        if detail.empty:
            missing.append("signal_detail")
        if trend_count == 0:
            missing.append("trend_body_pct")
        if path_count == 0:
            missing.append("signal_path_type")
        if not clusters:
            missing.append("positive_cluster_samples")

        return {
            "prior_trend_sample_count": trend_count,
            "prior_trend_success_rate": trend_success_rate,
            "prior_trend_avg_body": cls._round_or_none(trend_bodies.mean() if trend_count else None),
            "prior_trend_median_body": cls._round_or_none(trend_bodies.median() if trend_count else None),
            "path_available_count": path_count,
            "one_way_selloff_count": one_way_count,
            "one_way_selloff_ratio": cls._ratio(one_way_count, path_count),
            "fade_path_count": fade_count,
            "fade_path_ratio": cls._ratio(fade_count, path_count),
            "weak_close_path_count": weak_close_count,
            "weak_close_path_ratio": cls._ratio(weak_close_count, path_count),
            "broad_path_risk_count": risk_count,
            "broad_path_risk_ratio": cls._ratio(risk_count, path_count),
            "path_distribution": dict(sorted(Counter(path_values).items())),
            "long_side_positive_count": positive_count,
            "positive_cluster_count": len(cluster_counts),
            "cluster_top1": top1_name,
            "cluster_top1_count": top1_count,
            "cluster_top1_positive_share": top1_share,
            "cluster_top3_count": top3_count,
            "cluster_top3_positive_share": top3_share,
            "cluster_positive_denominator": positive_count,
            "cluster_concentration_label": concentration_label,
            "price_turnover_confirmation_summary": cls._sector_summary(sector_evidence),
            "feature_confidence": confidence,
            "missing_fields": missing,
        }

    @staticmethod
    def classify_price_turnover(period_return_pct, amount_change_pct) -> str:
        try:
            price = float(period_return_pct)
            turnover = float(amount_change_pct)
        except (TypeError, ValueError):
            return "insufficient_sector_evidence"
        if pd.isna(price) or pd.isna(turnover):
            return "insufficient_sector_evidence"
        if price > 0 and turnover > 0:
            return "price_turnover_confirmed"
        if price <= 0 and turnover > 0:
            return "high_turnover_without_price_confirmation"
        if price > 0 and turnover <= 0:
            return "price_without_turnover_confirmation"
        return "weak_or_cooling"

    @classmethod
    def _sector_summary(cls, evidence) -> dict:
        counts = Counter()
        for row in evidence or []:
            label = row.get("price_turnover_confirmation") or cls.classify_price_turnover(
                row.get("period_return_pct"), row.get("amount_change_pct")
            )
            counts[str(label)] += 1
        return dict(sorted(counts.items()))

    @staticmethod
    def _category(detail, category):
        if detail.empty or "signal_category" not in detail.columns:
            return pd.DataFrame()
        return detail[detail["signal_category"].astype(str).str.lower() == category].copy()

    @staticmethod
    def _numeric_series(frame, column):
        if frame.empty or column not in frame.columns:
            return pd.Series(dtype="float64")
        return pd.to_numeric(frame[column], errors="coerce").dropna()

    @classmethod
    def _success_rate(cls, category_df, metrics_df, category):
        if not metrics_df.empty and "signal_category" in metrics_df.columns:
            rows = metrics_df[metrics_df["signal_category"].astype(str).str.lower() == category]
            if not rows.empty and "success_rate" in rows.columns:
                value = cls._number(rows.iloc[0].get("success_rate"))
                if value is not None:
                    return round(value, 4)
        if category_df.empty or "validation_success" not in category_df.columns:
            return None
        values = category_df["validation_success"].map(cls._as_bool)
        return round(float(values.mean() * 100.0), 4) if len(values) else None

    @classmethod
    def _path_values(cls, detail):
        if detail.empty or "signal_path_type" not in detail.columns:
            return []
        values = detail["signal_path_type"].fillna("").astype(str).str.strip().str.lower()
        return [value for value in values if value and value not in {"unknown", "nan", "none"}]

    @classmethod
    def _positive_long_clusters(cls, detail):
        if detail.empty or "signal_category" not in detail.columns or "body_pct" not in detail.columns:
            return []
        frame = detail[detail["signal_category"].astype(str).str.lower().isin({"trend", "reversal"})].copy()
        frame["_body"] = pd.to_numeric(frame["body_pct"], errors="coerce")
        frame = frame[frame["_body"] > 0]
        if frame.empty:
            return []
        frame["_target_key"] = frame.apply(cls._target_key, axis=1)
        frame = frame.drop_duplicates("_target_key", keep="first")
        clusters = []
        for _, row in frame.iterrows():
            cluster = ""
            for key in ("theme_cluster", "group", "industry"):
                value = str(row.get(key, "") or "").strip()
                if value and value.lower() not in {"nan", "none", "-"}:
                    cluster = value
                    break
            if cluster:
                clusters.append(cluster)
        return clusters

    @staticmethod
    def _target_key(row):
        target_type = str(row.get("target_type", "") or "").strip().lower()
        code = str(row.get("code", "") or "").strip().lower()
        name = str(row.get("name", "") or "").strip().lower()
        return f"{target_type}:{code or name}"

    @staticmethod
    def _as_bool(value):
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y"}

    @staticmethod
    def _number(value):
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None
        return None if pd.isna(result) else result

    @staticmethod
    def _ratio(numerator, denominator):
        return round(float(numerator) / float(denominator), 4) if denominator else 0.0

    @staticmethod
    def _round_or_none(value):
        try:
            return round(float(value), 4)
        except (TypeError, ValueError):
            return None
