# -*- coding: utf-8 -*-
"""Load prior-day review context for next-day auction interpretation."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .prior_day_readthrough import PriorDayReadthroughBuilder


class PriorDayContextLoader:
    """Read prior-day post-close artifacts into a stable context dict."""

    ANALYSIS_DAILY_ROOT = Path("reports") / "analysis" / "daily"
    VALIDATION_DAILY_ROOT = Path("reports") / "validation" / "daily"

    @classmethod
    def load(cls, target_date: int, data_manager=None) -> dict:
        date_str = cls._normalize_date_str(target_date)
        prev_trade_date = cls._resolve_prev_trade_date(target_date, data_manager=data_manager)
        context = cls._empty_context(date_str, prev_trade_date)
        if not prev_trade_date:
            context["notes"].append("prior_day_context_unavailable")
            context["readthrough"] = PriorDayReadthroughBuilder.build(context)
            return context

        review = cls._read_json(cls.ANALYSIS_DAILY_ROOT / prev_trade_date / "auction_review.json")
        metrics = cls._read_csv(cls.VALIDATION_DAILY_ROOT / prev_trade_date / "signal_metrics.csv")
        detail = cls._read_csv(cls.VALIDATION_DAILY_ROOT / prev_trade_date / "signal_detail.csv")

        review_available = bool(review)
        metrics_available = not metrics.empty
        detail_available = not detail.empty
        confirmation_available = bool(
            ((review.get("intraday_confirmation_summary", {}) or {}).get("available"))
        )

        if review_available:
            context["available"] = True
            context["market_regime"] = str((review.get("market_regime", {}) or {}).get("label", "") or "")
            context["environment_decision"] = str(
                (review.get("environment_gate", {}) or {}).get("decision", "") or ""
            )
            context["leading_clusters"] = cls._ensure_list(review.get("leading_clusters", []) or [])

        signal_metrics = cls._build_signal_metrics(metrics)
        context["signal_metrics"] = signal_metrics
        context["data_quality"] = {
            "review_available": review_available,
            "signal_metrics_available": metrics_available,
            "signal_detail_available": detail_available,
            "confirmation_available": confirmation_available,
            "actionable_coverage_low": cls._actionable_coverage_low(detail),
        }
        context["context_flags"] = cls._build_context_flags(context["market_regime"], signal_metrics)
        context["bias"] = cls._build_bias(context["market_regime"], signal_metrics)
        context["context_confidence"] = cls._determine_confidence(context["data_quality"])

        if not review_available and not metrics_available:
            context["available"] = False
            context["notes"].append("prior_day_context_unavailable")
        elif not review_available:
            context["notes"].append("prior_day_review_missing")
        elif not metrics_available:
            context["notes"].append("prior_day_signal_metrics_missing")
        if detail_available and context["data_quality"]["actionable_coverage_low"]:
            context["notes"].append("prior_day_actionable_coverage_low")
        if review_available and not confirmation_available:
            context["notes"].append("prior_day_confirmation_unavailable")

        context["readthrough"] = PriorDayReadthroughBuilder.build(context)
        return context

    @classmethod
    def _resolve_prev_trade_date(cls, target_date: int, data_manager=None) -> str:
        target_int = int(target_date)
        if data_manager is not None and hasattr(data_manager, "get_analysis_window_days"):
            try:
                window = data_manager.get_analysis_window_days(target_int, lookback=2)
            except Exception:
                window = []
            if len(window) >= 2:
                return cls._normalize_date_str(window[-2])

        candidates = set()
        for root in (cls.ANALYSIS_DAILY_ROOT, cls.VALIDATION_DAILY_ROOT):
            if not root.exists():
                continue
            for item in root.iterdir():
                if item.is_dir() and item.name.isdigit() and len(item.name) == 8:
                    day = int(item.name)
                    if day < target_int:
                        candidates.add(day)
        if not candidates:
            return ""
        return cls._normalize_date_str(max(candidates))

    @classmethod
    def _build_signal_metrics(cls, metrics_df: pd.DataFrame) -> dict:
        base = {
            "trap": {"count": 0, "success_rate": None},
            "reversal": {"count": 0, "success_rate": None},
            "trend": {"count": 0, "success_rate": None},
        }
        if metrics_df.empty:
            return base
        for _, row in metrics_df.iterrows():
            category = str(row.get("signal_category", "") or "")
            if category not in base:
                continue
            base[category] = {
                "count": cls._to_int(row.get("trigger_count")),
                "success_rate": cls._to_float(row.get("success_rate")),
            }
        return base

    @classmethod
    def _build_context_flags(cls, regime: str, metrics: dict) -> list[str]:
        flags = []
        if regime:
            flags.append(f"prev_day_{regime}")
        trap_rate = cls._metric_success_rate(metrics, "trap")
        reversal_rate = cls._metric_success_rate(metrics, "reversal")
        trend_rate = cls._metric_success_rate(metrics, "trend")
        if trap_rate is not None and trap_rate > 60:
            flags.append("trap_effective")
        if trap_rate is not None and trap_rate < 20:
            flags.append("trap_weak")
        if reversal_rate is not None and reversal_rate > 60:
            flags.append("reversal_effective")
        if reversal_rate is not None and reversal_rate < 35:
            flags.append("reversal_weak")
        if trend_rate is not None and trend_rate > 55:
            flags.append("trend_followthrough_effective")
        if trend_rate is not None and trend_rate < 40:
            flags.append("trend_followthrough_failed")
        return flags

    @classmethod
    def _build_bias(cls, regime: str, metrics: dict) -> dict:
        trap_rate = cls._metric_success_rate(metrics, "trap")
        reversal_rate = cls._metric_success_rate(metrics, "reversal")
        trend_rate = cls._metric_success_rate(metrics, "trend")
        bias = {
            "trend_bias": "neutral",
            "reversal_bias": "neutral",
            "cp_bias": "neutral",
        }
        if regime == "risk_off" or (trend_rate is not None and trend_rate < 40):
            bias["trend_bias"] = "negative"
        elif trend_rate is not None and trend_rate >= 55:
            bias["trend_bias"] = "positive"

        if reversal_rate is not None and reversal_rate > 60:
            bias["reversal_bias"] = "positive"
        elif reversal_rate is not None and reversal_rate < 35:
            bias["reversal_bias"] = "negative"

        if trap_rate is not None and trap_rate > 60:
            bias["cp_bias"] = "positive"
        elif trap_rate is not None and trap_rate < 20:
            bias["cp_bias"] = "negative"
        return bias

    @classmethod
    def _determine_confidence(cls, data_quality: dict) -> str:
        if not data_quality.get("review_available") or not data_quality.get("signal_metrics_available"):
            return "low"
        if data_quality.get("signal_detail_available") and not data_quality.get("actionable_coverage_low"):
            return "high"
        return "medium"

    @classmethod
    def _actionable_coverage_low(cls, detail_df: pd.DataFrame) -> bool:
        if detail_df.empty or "actionable" not in detail_df.columns:
            return True
        values = detail_df["actionable"].astype(str).str.strip().str.lower()
        actionable_count = int(values.eq("true").sum())
        total = int(len(detail_df))
        if total <= 0:
            return True
        ratio = actionable_count / float(total)
        return actionable_count <= 1 or ratio < 0.02

    @classmethod
    def _empty_context(cls, date_str: str, prev_trade_date: str) -> dict:
        return {
            "date": date_str,
            "prev_trade_date": prev_trade_date,
            "available": False,
            "context_confidence": "low",
            "market_regime": "",
            "environment_decision": "",
            "leading_clusters": [],
            "signal_metrics": {
                "trap": {"count": 0, "success_rate": None},
                "reversal": {"count": 0, "success_rate": None},
                "trend": {"count": 0, "success_rate": None},
            },
            "context_flags": [],
            "bias": {
                "trend_bias": "neutral",
                "reversal_bias": "neutral",
                "cp_bias": "neutral",
            },
            "data_quality": {
                "review_available": False,
                "signal_metrics_available": False,
                "signal_detail_available": False,
                "confirmation_available": False,
                "actionable_coverage_low": False,
            },
            "readthrough": {
                "headline": "",
                "bias": "neutral",
                "focus_points": [],
                "risk_points": [],
                "confidence": "low",
            },
            "notes": [],
        }

    @staticmethod
    def _read_json(path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @staticmethod
    def _read_csv(path: Path) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame()
        try:
            return pd.read_csv(path, encoding="utf-8-sig", dtype={"date": str})
        except Exception:
            return pd.DataFrame()

    @staticmethod
    def _ensure_list(value) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value if str(item or "").strip()]
        if value is None or (hasattr(pd, "isna") and pd.isna(value)):
            return []
        text = str(value).strip()
        if not text:
            return []
        return [text]

    @staticmethod
    def _normalize_date_str(value) -> str:
        text = str(value or "").strip()
        if text.endswith(".0"):
            text = text[:-2]
        if text.isdigit():
            return text
        try:
            return str(int(float(text)))
        except Exception:
            return text

    @staticmethod
    def _to_int(value) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _to_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _metric_success_rate(cls, metrics: dict, key: str):
        item = metrics.get(key, {}) or {}
        return cls._to_float(item.get("success_rate"))
