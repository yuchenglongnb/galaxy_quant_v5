# -*- coding: utf-8 -*-
"""Replay auction shortlist ablations from persisted post-close signal details."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Dict

import pandas as pd

from config.settings import AuctionConfig


CATEGORIES = ["trap", "reversal", "trend"]
UNIVERSE_ORDER = {"index": 0, "ETF": 1, "stock": 2, "industry": 3}
TARGET_TYPE_MAP = {
    "指数": "index",
    "ETF": "ETF",
    "etf": "ETF",
    "个股": "stock",
    "stock": "stock",
    "行业": "industry",
    "industry": "industry",
}


@dataclass(frozen=True)
class AblationExperiment:
    experiment_id: str
    group: str
    note: str
    use_rank_bonus: bool = True
    use_auction_pct: bool = True
    use_pos_5d: bool = True
    use_prev_pct: bool = True
    use_prev_vol_ratio: bool = True
    use_regime_bonus: bool = True
    main_factor_only: bool = False
    stock_rank_limit: int = 100
    trend_min_auction_pct: float = -0.5
    use_min_score: bool = True
    final_topk: int | None = None
    universe_limits: Dict[str, int] = field(
        default_factory=lambda: {
            "index": AuctionConfig.ACTION_TOPK_INDEX,
            "ETF": AuctionConfig.ACTION_TOPK_ETF,
            "stock": AuctionConfig.ACTION_TOPK_STOCK,
            "industry": AuctionConfig.ACTION_TOPK_INDUSTRY,
        }
    )
    dynamic_regime_topk: bool = False


class AuctionAblationRunner:
    """Evaluate auction-time shortlist variants with body-amplitude quality metrics."""

    def __init__(
        self,
        validation_path=os.path.join("reports", "validation", "auction_signal_validation.csv"),
        output_root=os.path.join("reports", "ablation"),
        store_root="AmazingData_Store",
    ):
        self.validation_path = validation_path
        self.output_root = output_root
        self.store_root = store_root
        self._data_universe_mode_cache = {}

    def run(self, start_date=None, end_date=None):
        detail = self._load_detail(start_date, end_date)
        if detail.empty:
            raise ValueError("No closed auction validation details found for the requested range.")
        start_date = str(detail["date"].min())
        end_date = str(detail["date"].max())

        selected_frames = []
        for experiment in self.experiments():
            selected_frames.append(self._replay(detail, experiment))
        selected = pd.concat(selected_frames, ignore_index=True) if selected_frames else pd.DataFrame()
        summary = self._summarize(selected, detail)
        daily = self._summarize_daily(selected)
        by_regime = self._summarize_dimension(selected, "market_regime")
        by_universe = self._summarize_dimension(selected, "universe_type")
        by_data_universe = self._summarize_dimension(selected, "data_universe_mode")
        universe_topk = self._summarize_universe_topk(detail)
        event_daily, event_summary = self._summarize_events(selected)
        monthly = self._summarize_monthly(selected)
        reversal_layer_samples, reversal_layers = self._summarize_reversal_layers(detail)

        output_dir = os.path.join(self.output_root, f"{start_date}_{end_date}")
        os.makedirs(output_dir, exist_ok=True)
        paths = {
            "summary": os.path.join(output_dir, "experiment_summary.csv"),
            "daily": os.path.join(output_dir, "experiment_daily.csv"),
            "by_regime": os.path.join(output_dir, "experiment_by_regime.csv"),
            "by_universe": os.path.join(output_dir, "experiment_by_universe.csv"),
            "by_data_universe": os.path.join(output_dir, "experiment_by_data_universe.csv"),
            "universe_topk": os.path.join(output_dir, "universe_topk_summary.csv"),
            "event_daily": os.path.join(output_dir, "experiment_event_daily.csv"),
            "event_summary": os.path.join(output_dir, "experiment_event_summary.csv"),
            "monthly": os.path.join(output_dir, "experiment_monthly_walk_forward.csv"),
            "reversal_layer_samples": os.path.join(output_dir, "reversal_layer_samples.csv"),
            "reversal_layers": os.path.join(output_dir, "reversal_layer_summary.csv"),
            "selected": os.path.join(output_dir, "experiment_selected_samples.csv"),
            "report": os.path.join(output_dir, "ablation_report.md"),
            "metadata": os.path.join(output_dir, "ablation_metadata.json"),
        }
        summary.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
        daily.to_csv(paths["daily"], index=False, encoding="utf-8-sig")
        by_regime.to_csv(paths["by_regime"], index=False, encoding="utf-8-sig")
        by_universe.to_csv(paths["by_universe"], index=False, encoding="utf-8-sig")
        by_data_universe.to_csv(paths["by_data_universe"], index=False, encoding="utf-8-sig")
        universe_topk.to_csv(paths["universe_topk"], index=False, encoding="utf-8-sig")
        event_daily.to_csv(paths["event_daily"], index=False, encoding="utf-8-sig")
        event_summary.to_csv(paths["event_summary"], index=False, encoding="utf-8-sig")
        monthly.to_csv(paths["monthly"], index=False, encoding="utf-8-sig")
        reversal_layer_samples.to_csv(paths["reversal_layer_samples"], index=False, encoding="utf-8-sig")
        reversal_layers.to_csv(paths["reversal_layers"], index=False, encoding="utf-8-sig")
        selected.to_csv(paths["selected"], index=False, encoding="utf-8-sig")
        with open(paths["report"], "w", encoding="utf-8") as fh:
            fh.write(self._format_report(start_date, end_date, detail, summary))
        with open(paths["metadata"], "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "start_date": start_date,
                    "end_date": end_date,
                    "source": os.path.abspath(self.validation_path),
                    "candidate_count": int(len(detail)),
                    "data_universe_mode_counts": detail["data_universe_mode"].value_counts().to_dict(),
                    "experiments": [experiment.__dict__ for experiment in self.experiments()],
                    "primary_metric": "avg_directed_body_pct",
                    "label_boundary": "body_pct is post-close evaluation only",
                },
                fh,
                ensure_ascii=False,
                indent=2,
            )
        return {"paths": paths, "summary": summary, "selected": selected}

    @classmethod
    def experiments(cls):
        baseline = AblationExperiment("B0", "baseline", "Current auction shortlist baseline")
        return [
            baseline,
            replace(baseline, experiment_id="F01", group="feature", note="Remove rank bonus", use_rank_bonus=False),
            replace(baseline, experiment_id="F02", group="feature", note="Remove auction_pct score", use_auction_pct=False),
            replace(baseline, experiment_id="F03", group="feature", note="Remove pos_5d score", use_pos_5d=False),
            replace(baseline, experiment_id="F04", group="feature", note="Remove prev_pct score", use_prev_pct=False),
            replace(baseline, experiment_id="F05", group="feature", note="Remove prev_vol_ratio score", use_prev_vol_ratio=False),
            replace(baseline, experiment_id="F06", group="feature", note="Remove regime bonus", use_regime_bonus=False),
            replace(baseline, experiment_id="F07", group="feature", note="Keep CP/SA or trend base only", main_factor_only=True),
            replace(baseline, experiment_id="H02", group="filter", note="Stock amount rank <= 50", stock_rank_limit=50),
            replace(baseline, experiment_id="H03", group="filter", note="Stock amount rank <= 150", stock_rank_limit=150),
            replace(baseline, experiment_id="H04", group="filter", note="Trend auction_pct >= 0", trend_min_auction_pct=0.0),
            replace(baseline, experiment_id="H05", group="filter", note="Trend auction_pct >= -1", trend_min_auction_pct=-1.0),
            replace(baseline, experiment_id="H06", group="filter", note="Remove minimum action score", use_min_score=False),
            replace(baseline, experiment_id="E01", group="environment", note="Treat environment as report-only", use_regime_bonus=False),
            replace(
                baseline,
                experiment_id="E05",
                group="environment",
                note="Environment controls final TopK only",
                use_regime_bonus=False,
                dynamic_regime_topk=True,
            ),
            replace(baseline, experiment_id="K01", group="topk", note="Final TopK=1", final_topk=1),
            replace(baseline, experiment_id="K03", group="topk", note="Final TopK=3", final_topk=3),
            replace(baseline, experiment_id="K08", group="topk", note="Final TopK=8", final_topk=8),
            replace(baseline, experiment_id="K10", group="topk", note="Final TopK=10", final_topk=10),
            replace(
                baseline,
                experiment_id="U03",
                group="universe",
                note="ETF and stock candidates only",
                universe_limits={"index": 0, "ETF": 3, "stock": 5, "industry": 0},
            ),
            replace(
                baseline,
                experiment_id="U05",
                group="universe",
                note="Stock candidates only",
                universe_limits={"index": 0, "ETF": 0, "stock": 5, "industry": 0},
            ),
        ]

    def _load_detail(self, start_date, end_date):
        if not os.path.exists(self.validation_path):
            return pd.DataFrame()
        df = pd.read_csv(self.validation_path, encoding="utf-8-sig", dtype={"date": str})
        if start_date:
            df = df[df["date"] >= str(start_date)]
        if end_date:
            df = df[df["date"] <= str(end_date)]
        if "validation_scope" in df.columns:
            df = df[df["validation_scope"] == "post_close_final"]
        for column in [
            "body_pct", "auction_pct", "prev_pct", "prev_vol_ratio", "pos_5d",
            "amt_rank", "cp", "sa",
        ]:
            df[column] = pd.to_numeric(df.get(column), errors="coerce")
        df["universe_type"] = df["target_type"].map(TARGET_TYPE_MAP).fillna(df["target_type"])
        df["data_universe_mode"] = df["date"].map(self._detect_data_universe_mode)
        df = df[df["signal_category"].isin(CATEGORIES)].copy()
        return df

    def _detect_data_universe_mode(self, date):
        """Separate old full-market caches from the newer compact stock-pool caches."""
        date = str(date)
        if date in self._data_universe_mode_cache:
            return self._data_universe_mode_cache[date]
        path = os.path.join(self.store_root, str(date), "stocks.csv")
        if not os.path.exists(path):
            mode = "unknown"
            self._data_universe_mode_cache[date] = mode
            return mode
        try:
            with open(path, "r", encoding="utf-8-sig", errors="ignore") as fh:
                row_count = max(sum(1 for _ in fh) - 1, 0)
        except OSError:
            mode = "unknown"
            self._data_universe_mode_cache[date] = mode
            return mode
        mode = "stock_pool" if row_count <= 500 else "full_market"
        self._data_universe_mode_cache[date] = mode
        return mode

    def _replay(self, detail, experiment):
        rows = []
        for (date, category), candidates in detail.groupby(["date", "signal_category"], sort=True):
            work = candidates.copy()
            work["experiment_id"] = experiment.experiment_id
            work["experiment_group"] = experiment.group
            work["experiment_note"] = experiment.note
            work["replay_score"] = work.apply(
                lambda row: self._score(row, category, experiment), axis=1
            )
            work["eligible"] = work.apply(
                lambda row: self._eligible(row, category, experiment), axis=1
            )
            selected = []
            for universe, universe_rows in work[work["eligible"]].groupby("universe_type"):
                limit = experiment.universe_limits.get(universe, 0)
                if limit:
                    selected.append(universe_rows.sort_values("replay_score", ascending=False).head(limit))
            if not selected:
                continue
            shortlist = pd.concat(selected, ignore_index=True)
            shortlist["universe_order"] = shortlist["universe_type"].map(UNIVERSE_ORDER).fillna(99)
            final_topk = self._final_topk(experiment, str(shortlist["market_regime"].iloc[0]), category)
            shortlist = shortlist.sort_values(
                ["universe_order", "replay_score"], ascending=[True, False]
            ).head(final_topk)
            shortlist["rank_in_experiment"] = range(1, len(shortlist) + 1)
            shortlist["directed_body_pct"] = shortlist["body_pct"] * (-1 if category == "trap" else 1)
            shortlist["direction_hit"] = shortlist["directed_body_pct"] > 0
            shortlist["strong_direction_hit"] = shortlist["directed_body_pct"] >= 1.0
            rows.append(shortlist)
        return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()

    @staticmethod
    def _score(row, category, experiment):
        auction_pct = AuctionAblationRunner._number(row.get("auction_pct"))
        prev_pct = AuctionAblationRunner._number(row.get("prev_pct"))
        prev_vol_ratio = AuctionAblationRunner._number(row.get("prev_vol_ratio"), 1.0)
        pos_5d = AuctionAblationRunner._number(row.get("pos_5d"), 50.0)
        rank_bonus = AuctionAblationRunner._rank_bonus(row) if experiment.use_rank_bonus else 0.0
        regime_bonus = (
            AuctionAblationRunner._regime_bonus(category, row.get("market_regime"))
            if experiment.use_regime_bonus else 0.0
        )

        if category == "trap":
            score = AuctionAblationRunner._number(row.get("cp"))
            if not experiment.main_factor_only:
                score += rank_bonus
                score += max(0.0, auction_pct) * 3.0 if experiment.use_auction_pct else 0.0
                score += max(0.0, pos_5d - 70.0) / 5.0 if experiment.use_pos_5d else 0.0
                score += regime_bonus
            return score
        if category == "reversal":
            score = AuctionAblationRunner._number(row.get("sa"))
            if not experiment.main_factor_only:
                score += rank_bonus
                score += min(abs(min(auction_pct, 0.0)), 3.0) * 4.0 if experiment.use_auction_pct else 0.0
                score += max(0.0, -prev_pct) * 1.5 if experiment.use_prev_pct else 0.0
                score += regime_bonus
            return score

        score = 25.0
        if not experiment.main_factor_only:
            score += rank_bonus
            score += max(0.0, prev_pct) * 3.0 if experiment.use_prev_pct else 0.0
            score += max(0.0, prev_vol_ratio - 1.0) * 12.0 if experiment.use_prev_vol_ratio else 0.0
            if experiment.use_auction_pct:
                score -= AuctionAblationRunner._trend_high_open_penalty(auction_pct)
            score += regime_bonus
        return score

    @staticmethod
    def _eligible(row, category, experiment):
        auction_pct = AuctionAblationRunner._number(row.get("auction_pct"))
        rank = AuctionAblationRunner._number(row.get("amt_rank"), 999.0)
        if abs(auction_pct) > AuctionConfig.ACTION_MAX_ABS_AUCTION_PCT:
            return False
        if row.get("universe_type") == "stock" and rank > experiment.stock_rank_limit:
            return False
        if category == "trap" and row.get("scenario") not in AuctionConfig.ACTION_TRAP_SCENARIOS:
            return False
        if category == "trend" and row.get("scenario") not in AuctionConfig.ACTION_TREND_SCENARIOS:
            return False
        if category == "trend" and auction_pct < experiment.trend_min_auction_pct:
            return False
        if category == "trend" and AuctionAblationRunner._is_overheated_trend(row):
            return False
        if experiment.use_min_score:
            minimum = {
                "trap": AuctionConfig.ACTION_MIN_SCORE_TRAP,
                "reversal": AuctionConfig.ACTION_MIN_SCORE_REVERSAL,
                "trend": AuctionConfig.ACTION_MIN_SCORE_TREND,
            }[category]
            if float(row["replay_score"]) < minimum:
                return False
        return True

    @staticmethod
    def _final_topk(experiment, regime, category):
        if not experiment.dynamic_regime_topk:
            return experiment.final_topk or {
                "trap": AuctionConfig.ACTION_TOPK_TRAP,
                "reversal": AuctionConfig.ACTION_TOPK_REVERSAL,
                "trend": AuctionConfig.ACTION_TOPK_TREND,
            }[category]
        matrix = {
            "risk_off": {"trap": 5, "reversal": 1, "trend": 0},
            "repair": {"trap": 3, "reversal": 5, "trend": 2},
            "continuation": {"trap": 2, "reversal": 2, "trend": 5},
            "mixed": {"trap": 3, "reversal": 3, "trend": 3},
        }
        return matrix.get(regime, matrix["mixed"]).get(category, experiment.final_topk)

    @staticmethod
    def _trend_high_open_penalty(auction_pct):
        if auction_pct < AuctionConfig.ACTION_TREND_HIGH_OPEN_PCT:
            return 0.0
        return (
            auction_pct - AuctionConfig.ACTION_TREND_HIGH_OPEN_PCT + 1.0
        ) * AuctionConfig.ACTION_TREND_HIGH_OPEN_PENALTY

    @staticmethod
    def _is_overheated_trend(row):
        return (
            AuctionAblationRunner._number(row.get("prev_pct")) >= AuctionConfig.ACTION_OVERHEATED_PREV_PCT
            and AuctionAblationRunner._number(row.get("auction_pct")) >= AuctionConfig.ACTION_OVERHEATED_AUCTION_PCT
            and AuctionAblationRunner._number(row.get("pos_5d"), 50.0) >= AuctionConfig.ACTION_OVERHEATED_POS_5D
        )

    def _summarize(self, selected, detail):
        if selected.empty:
            return pd.DataFrame()
        rows = []
        for (experiment_id, category), subset in selected.groupby(["experiment_id", "signal_category"]):
            raw_count = len(detail[detail["signal_category"] == category])
            rows.append(self._metric_row(subset, experiment_id, category, raw_count))
        summary = pd.DataFrame(rows)
        baseline = summary[summary["experiment_id"] == "B0"][
            ["signal_category", "avg_directed_body_pct", "median_directed_body_pct", "direction_hit_rate"]
        ].rename(columns={
            "avg_directed_body_pct": "baseline_avg_directed_body_pct",
            "median_directed_body_pct": "baseline_median_directed_body_pct",
            "direction_hit_rate": "baseline_direction_hit_rate",
        })
        summary = summary.merge(baseline, on="signal_category", how="left")
        summary["avg_directed_body_delta"] = (
            summary["avg_directed_body_pct"] - summary["baseline_avg_directed_body_pct"]
        ).round(4)
        summary["median_directed_body_delta"] = (
            summary["median_directed_body_pct"] - summary["baseline_median_directed_body_pct"]
        ).round(4)
        summary["direction_hit_rate_delta"] = (
            summary["direction_hit_rate"] - summary["baseline_direction_hit_rate"]
        ).round(2)
        return summary.sort_values(["signal_category", "experiment_id"])

    @staticmethod
    def _metric_row(subset, experiment_id, category, raw_count):
        directed = subset["directed_body_pct"].dropna()
        daily_counts = subset.groupby("date").size()
        return {
            "experiment_id": experiment_id,
            "experiment_group": subset["experiment_group"].iloc[0],
            "experiment_note": subset["experiment_note"].iloc[0],
            "signal_category": category,
            "selected_count": int(len(subset)),
            "selected_count_per_day": round(float(daily_counts.mean()), 4),
            "selected_count_p90": round(float(daily_counts.quantile(0.9)), 4),
            "coverage_pct": round(len(subset) / raw_count * 100, 2) if raw_count else 0.0,
            "avg_directed_body_pct": round(float(directed.mean()), 4),
            "median_directed_body_pct": round(float(directed.median()), 4),
            "p25_directed_body_pct": round(float(directed.quantile(0.25)), 4),
            "p75_directed_body_pct": round(float(directed.quantile(0.75)), 4),
            "direction_hit_rate": round(float(subset["direction_hit"].mean() * 100), 2),
            "strong_direction_hit_rate": round(float(subset["strong_direction_hit"].mean() * 100), 2),
        }

    @staticmethod
    def _summarize_daily(selected):
        if selected.empty:
            return pd.DataFrame()
        return (
            selected.groupby(["date", "experiment_id", "signal_category"])
            .agg(
                selected_count=("signal_category", "size"),
                avg_directed_body_pct=("directed_body_pct", "mean"),
                median_directed_body_pct=("directed_body_pct", "median"),
                direction_hit_rate=("direction_hit", "mean"),
            )
            .reset_index()
        )

    def _summarize_universe_topk(self, detail):
        rows = []
        baseline = self.experiments()[0]
        for (date, category, universe), candidates in detail.groupby(
            ["date", "signal_category", "universe_type"], sort=True
        ):
            work = candidates.copy()
            work["replay_score"] = work.apply(
                lambda row: self._score(row, category, baseline), axis=1
            )
            work["eligible"] = work.apply(
                lambda row: self._eligible(row, category, baseline), axis=1
            )
            work = work[work["eligible"]].sort_values("replay_score", ascending=False)
            for topk in (1, 3, 5, 8):
                subset = work.head(topk).copy()
                if subset.empty:
                    continue
                subset["topk"] = topk
                subset["directed_body_pct"] = subset["body_pct"] * (-1 if category == "trap" else 1)
                subset["direction_hit"] = subset["directed_body_pct"] > 0
                subset["strong_direction_hit"] = subset["directed_body_pct"] >= 1.0
                rows.append(subset)
        if not rows:
            return pd.DataFrame()
        selected = pd.concat(rows, ignore_index=True)
        summary = (
            selected.groupby(["signal_category", "universe_type", "topk"])
            .agg(
                selected_count=("signal_category", "size"),
                trading_days=("date", "nunique"),
                avg_directed_body_pct=("directed_body_pct", "mean"),
                median_directed_body_pct=("directed_body_pct", "median"),
                direction_hit_rate=("direction_hit", "mean"),
                strong_direction_hit_rate=("strong_direction_hit", "mean"),
            )
            .reset_index()
        )
        summary["direction_hit_rate"] = (summary["direction_hit_rate"] * 100).round(2)
        summary["strong_direction_hit_rate"] = (summary["strong_direction_hit_rate"] * 100).round(2)
        return summary

    @staticmethod
    def _summarize_events(selected):
        if selected.empty:
            return pd.DataFrame(), pd.DataFrame()
        event_daily = (
            selected.groupby(["date", "experiment_id", "signal_category", "universe_type"])
            .agg(
                selected_count=("signal_category", "size"),
                event_avg_directed_body_pct=("directed_body_pct", "mean"),
                event_median_directed_body_pct=("directed_body_pct", "median"),
            )
            .reset_index()
        )
        event_daily["event_direction_hit"] = event_daily["event_avg_directed_body_pct"] > 0
        event_summary = (
            event_daily.groupby(["experiment_id", "signal_category", "universe_type"])
            .agg(
                event_count=("date", "size"),
                avg_event_directed_body_pct=("event_avg_directed_body_pct", "mean"),
                median_event_directed_body_pct=("event_avg_directed_body_pct", "median"),
                event_direction_hit_rate=("event_direction_hit", "mean"),
            )
            .reset_index()
        )
        event_summary["event_direction_hit_rate"] = (event_summary["event_direction_hit_rate"] * 100).round(2)
        return event_daily, event_summary

    @staticmethod
    def _summarize_monthly(selected):
        if selected.empty:
            return pd.DataFrame()
        work = selected.copy()
        work["month"] = work["date"].astype(str).str[:6]
        summary = (
            work.groupby(["month", "experiment_id", "signal_category", "universe_type"])
            .agg(
                selected_count=("signal_category", "size"),
                trading_days=("date", "nunique"),
                avg_directed_body_pct=("directed_body_pct", "mean"),
                median_directed_body_pct=("directed_body_pct", "median"),
                direction_hit_rate=("direction_hit", "mean"),
            )
            .reset_index()
        )
        summary["direction_hit_rate"] = (summary["direction_hit_rate"] * 100).round(2)
        return summary

    def _summarize_reversal_layers(self, detail):
        candidates = detail[
            (detail["signal_category"] == "reversal")
            & (detail["market_regime"].isin(AuctionConfig.ACTION_REVERSAL_HIGH_CONFIDENCE_REGIMES))
            & (detail["scenario"].isin(AuctionConfig.ACTION_REVERSAL_HIGH_CONFIDENCE_SCENARIOS))
            & (detail["universe_type"].isin(AuctionConfig.ACTION_REVERSAL_HIGH_CONFIDENCE_UNIVERSES))
        ].copy()
        if candidates.empty:
            return pd.DataFrame(), pd.DataFrame()
        baseline = self.experiments()[0]
        candidates["replay_score"] = candidates.apply(
            lambda row: self._score(row, "reversal", baseline), axis=1
        )
        candidates["eligible"] = candidates.apply(
            lambda row: self._eligible(row, "reversal", baseline), axis=1
        )
        candidates = candidates[candidates["eligible"]]
        samples = (
            candidates.sort_values(["date", "replay_score"], ascending=[True, False])
            .groupby("date", group_keys=False)
            .head(AuctionConfig.ACTION_TOPK_REVERSAL_HIGH_CONFIDENCE)
            .copy()
        )
        samples["reversal_layer"] = "high_confidence_oversold"
        samples["directed_body_pct"] = samples["body_pct"]
        samples["direction_hit"] = samples["directed_body_pct"] > 0
        samples["strong_direction_hit"] = samples["directed_body_pct"] >= 1.0
        summary = (
            samples.groupby(["reversal_layer", "universe_type"])
            .agg(
                selected_count=("signal_category", "size"),
                event_count=("date", "nunique"),
                avg_directed_body_pct=("directed_body_pct", "mean"),
                median_directed_body_pct=("directed_body_pct", "median"),
                direction_hit_rate=("direction_hit", "mean"),
                strong_direction_hit_rate=("strong_direction_hit", "mean"),
            )
            .reset_index()
        )
        summary["direction_hit_rate"] = (summary["direction_hit_rate"] * 100).round(2)
        summary["strong_direction_hit_rate"] = (summary["strong_direction_hit_rate"] * 100).round(2)
        return samples, summary

    @staticmethod
    def _summarize_dimension(selected, dimension):
        if selected.empty:
            return pd.DataFrame()
        return (
            selected.groupby(["experiment_id", "signal_category", dimension])
            .agg(
                selected_count=("signal_category", "size"),
                avg_directed_body_pct=("directed_body_pct", "mean"),
                median_directed_body_pct=("directed_body_pct", "median"),
                direction_hit_rate=("direction_hit", "mean"),
            )
            .reset_index()
        )

    @staticmethod
    def _regime_bonus(category, regime):
        matrix = {
            "continuation": {"trap": 0.0, "reversal": 0.0, "trend": 12.0},
            "repair": {"trap": 0.0, "reversal": 10.0, "trend": 0.0},
            "risk_off": {"trap": 0.0, "reversal": -10.0, "trend": -25.0},
            "mixed": {"trap": 0.0, "reversal": 0.0, "trend": 0.0},
        }
        return matrix.get(regime, matrix["mixed"]).get(category, 0.0)

    @staticmethod
    def _number(value, default=0.0):
        try:
            if value is None or pd.isna(value):
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _rank_bonus(row):
        """Recover the online score rank bonus, including legacy CSV records."""
        score_rank = row.get("score_amt_rank")
        if score_rank is not None and not pd.isna(score_rank):
            rank = AuctionAblationRunner._number(score_rank, 999.0)
            return max(0.0, 18.0 - min(rank, 180.0) / 10.0)
        reason = str(row.get("shortlist_reason", "") or "")
        match = re.search(r"rank_bonus=([0-9.]+)", reason)
        if match:
            return float(match.group(1))
        rank = AuctionAblationRunner._number(row.get("amt_rank"), 999.0)
        return max(0.0, 18.0 - min(rank, 180.0) / 10.0)

    @staticmethod
    def _format_report(start_date, end_date, detail, summary):
        lines = [
            f"# Auction Ablation Report {start_date} - {end_date}",
            "",
            "## Scope",
            "",
            f"- Closed auction candidates: {len(detail)}",
            f"- Trading days: {detail['date'].nunique()}",
            "- Primary metric: directed_body_pct. CP uses -body_pct; reversal/trend use +body_pct.",
            "- Direction hit rate is secondary. Minute and intraday features are excluded.",
            "",
            "## Baseline",
            "",
        ]
        baseline = summary[summary["experiment_id"] == "B0"]
        for _, row in baseline.iterrows():
            lines.append(
                f"- {row['signal_category']}: n={row['selected_count']}, "
                f"avg_directed_body={row['avg_directed_body_pct']}%, "
                f"median={row['median_directed_body_pct']}%, "
                f"direction_hit={row['direction_hit_rate']}%"
            )
        lines.extend(["", "## Largest Average Body Improvements", ""])
        for category in CATEGORIES:
            category_rows = summary[summary["signal_category"] == category].sort_values(
                "avg_directed_body_delta", ascending=False
            ).head(5)
            lines.append(f"### {category}")
            for _, row in category_rows.iterrows():
                lines.append(
                    f"- {row['experiment_id']}: avg={row['avg_directed_body_pct']}%, "
                    f"delta={row['avg_directed_body_delta']}%, "
                    f"median={row['median_directed_body_pct']}%, "
                    f"n={row['selected_count']}, note={row['experiment_note']}"
                )
            lines.append("")
        lines.extend([
            "## Interpretation Guardrails",
            "",
            f"- {detail['date'].nunique()} trading days are available. Treat this as an exploratory sample, not a frozen parameter set.",
            "- Prefer variants that improve average and median directed body while retaining practical coverage.",
            "- Re-run with walk-forward windows after at least 40 to 60 closed trading days.",
            "",
        ])
        return "\n".join(lines)


def run_auction_ablation(start_date=None, end_date=None):
    result = AuctionAblationRunner().run(start_date=start_date, end_date=end_date)
    print(f"[ablation] Summary: {os.path.abspath(result['paths']['summary'])}")
    print(f"[ablation] Report: {os.path.abspath(result['paths']['report'])}")
    return result
