# -*- coding: utf-8 -*-
"""Relative-strength gate for trend candidates.

The filter is intentionally small and data-source agnostic. It consumes the
candidate dict already enriched by AuctionAnalyzer and appends explainable
decision fields used by SignalShortlistBuilder.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path


class TrendCandidateFilter:
    """Evaluate whether a trend candidate should be kept, observed, or dropped."""

    CONFIG_PATH = (
        Path(__file__).resolve().parents[2]
        / "reports"
        / "analysis"
        / "configs"
        / "trend_filter_config.json"
    )
    _CONFIG_CACHE = None

    DEFAULT_CONFIG = {
        "enabled": True,
        "thresholds": {
            "rs_vs_etf_keep": 0.8,
            "rs_vs_etf_observe": 0.0,
            "rs_vs_index_keep": 0.5,
            "rs_vs_index_observe": 0.0,
            "amount_1m_ratio_confirm": 1.3,
            "theme_cluster_bonus_keep": 3.0,
            "group_regime_bonus_keep": 2.0,
            "high_open_pct_risk": 5.0,
        },
        "weights": {
            "rs_vs_etf_bonus": 8.0,
            "rs_vs_index_bonus": 6.0,
            "amount_confirmation_bonus": 5.0,
            "theme_cluster_bonus": 6.0,
            "group_regime_bonus": 4.0,
            "weak_vs_etf_penalty": -12.0,
            "weak_vs_index_penalty": -8.0,
            "missing_data_penalty": -2.0,
            "strong_repair_non_confirmed_penalty": -10.0,
            "high_open_risk_penalty": -6.0,
        },
        "decision_thresholds": {"keep_score": 8.0, "observe_score": -10.0},
        "regime_rules": {
            "strong_repair": {
                "require_relative_strength_for_keep": True,
                "weak_relative_strength_decision": "observe",
            },
            "repair": {
                "require_relative_strength_for_keep": True,
                "weak_relative_strength_decision": "observe",
            },
            "hostile": {"default_decision": "drop"},
            "risk_off": {"default_decision": "observe"},
            "mixed": {"default_decision": "observe"},
            "continuation": {"default_decision": "keep"},
        },
    }

    @classmethod
    def evaluate_candidate(cls, candidate, regime=None, coverage_context=None):
        config = cls.load_config()
        result = cls._empty_result()
        if not config.get("enabled", True):
            result["trend_filter_reasons"].append("trend_filter_disabled")
            result["trend_filter_status"] = "disabled"
            return cls._attach(candidate, result)

        if not cls._is_trend_candidate(candidate):
            result["trend_filter_reasons"].append("non_trend_candidate")
            return cls._attach(candidate, result)

        data = candidate.get("data", {}) or {}
        breakdown = candidate.get("action_score_breakdown", {}) or {}
        thresholds = config.get("thresholds", {})
        weights = config.get("weights", {})
        regime_label = cls._regime_label(regime, candidate)
        coverage_guard = config.get("coverage_guard", {}) or {}
        coverage_context = cls.normalize_coverage_context(coverage_context, candidate)
        coverage_status = cls._coverage_status(coverage_context, coverage_guard)
        result["trend_filter_status"] = coverage_status
        result["trend_filter_context"] = deepcopy(coverage_context)

        score = 0.0
        has_confirmed_relative_strength = False
        has_explicit_negative_relative_strength = False

        rs_vs_etf, has_etf = cls._field_value(
            data,
            nested_key="rs_vs_etf_pct",
            flat_keys=("confirmation_rs_vs_etf_pct", "rs_vs_etf_pct"),
        )
        if has_etf:
            if rs_vs_etf >= cls._number(thresholds.get("rs_vs_etf_keep"), 0.8):
                score += cls._number(weights.get("rs_vs_etf_bonus"), 8.0)
                result["trend_filter_reasons"].append("strong_vs_etf")
                has_confirmed_relative_strength = True
            elif rs_vs_etf >= cls._number(thresholds.get("rs_vs_etf_observe"), 0.0):
                result["trend_filter_reasons"].append("neutral_vs_etf")
            else:
                score += cls._number(weights.get("weak_vs_etf_penalty"), -12.0)
                result["trend_filter_risk_flags"].append("weak_vs_etf")
                result["trend_filter_invalid_conditions"].append("rs_vs_etf_pct_below_0")
                has_explicit_negative_relative_strength = True
        elif coverage_status == "active":
            score += cls._number(weights.get("missing_data_penalty"), -2.0)
            result["trend_filter_missing_fields"].append("missing_rs_vs_etf_pct")
        elif coverage_status == "degraded_partial_missing":
            score += cls._number(weights.get("missing_data_penalty"), -2.0) / 2.0
            result["trend_filter_missing_fields"].append("missing_rs_vs_etf_pct")
            result["trend_filter_risk_flags"].append("relative_strength_unverified")
        else:
            result["trend_filter_missing_fields"].append("missing_rs_vs_etf_pct")
            result["trend_filter_risk_flags"].append("relative_strength_unverified")

        rs_vs_index, has_index = cls._field_value(
            data,
            nested_key="rs_vs_index_pct",
            flat_keys=("confirmation_rs_vs_index_pct", "rs_vs_index_pct"),
        )
        if has_index:
            if rs_vs_index >= cls._number(thresholds.get("rs_vs_index_keep"), 0.5):
                score += cls._number(weights.get("rs_vs_index_bonus"), 6.0)
                result["trend_filter_reasons"].append("strong_vs_index")
                has_confirmed_relative_strength = True
            elif rs_vs_index >= cls._number(thresholds.get("rs_vs_index_observe"), 0.0):
                result["trend_filter_reasons"].append("neutral_vs_index")
            else:
                score += cls._number(weights.get("weak_vs_index_penalty"), -8.0)
                result["trend_filter_risk_flags"].append("weak_vs_index")
                result["trend_filter_invalid_conditions"].append("rs_vs_index_pct_below_0")
                has_explicit_negative_relative_strength = True
        elif coverage_status == "active":
            score += cls._number(weights.get("missing_data_penalty"), -2.0)
            result["trend_filter_missing_fields"].append("missing_rs_vs_index_pct")
        elif coverage_status == "degraded_partial_missing":
            score += cls._number(weights.get("missing_data_penalty"), -2.0) / 2.0
            result["trend_filter_missing_fields"].append("missing_rs_vs_index_pct")
            result["trend_filter_risk_flags"].append("relative_strength_unverified")
        else:
            result["trend_filter_missing_fields"].append("missing_rs_vs_index_pct")
            result["trend_filter_risk_flags"].append("relative_strength_unverified")

        amount_ratio, has_amount = cls._field_value(
            data,
            nested_key="amount_1m_ratio",
            flat_keys=("confirmation_amount_1m_ratio", "amount_1m_ratio"),
        )
        if has_amount and amount_ratio >= cls._number(thresholds.get("amount_1m_ratio_confirm"), 1.3):
            score += cls._number(weights.get("amount_confirmation_bonus"), 5.0)
            result["trend_filter_reasons"].append("amount_confirmed")

        theme_bonus = cls._number(breakdown.get("theme_cluster_bonus"))
        group_bonus = cls._number(breakdown.get("group_regime_bonus"))
        if theme_bonus >= cls._number(thresholds.get("theme_cluster_bonus_keep"), 3.0):
            score += cls._number(weights.get("theme_cluster_bonus"), 6.0)
            result["trend_filter_reasons"].append("theme_cluster_bonus_positive")
        if group_bonus >= cls._number(thresholds.get("group_regime_bonus_keep"), 2.0):
            score += cls._number(weights.get("group_regime_bonus"), 4.0)
            result["trend_filter_reasons"].append("group_regime_bonus_positive")
        if theme_bonus <= 0 and group_bonus <= 0 and not data.get("leading_cluster_rank"):
            result["trend_filter_missing_fields"].append("missing_leading_cluster_rank")
            result["trend_filter_risk_flags"].append("non_leading_cluster_unverified")

        auction_pct = cls._number(data.get("auction_pct"))
        if auction_pct >= cls._number(thresholds.get("high_open_pct_risk"), 5.0) and not has_confirmed_relative_strength:
            score += cls._number(weights.get("high_open_risk_penalty"), -6.0)
            result["trend_filter_risk_flags"].append("high_open_risk")
            result["trend_filter_invalid_conditions"].append("high_open_without_relative_strength")

        regime_rule = (config.get("regime_rules", {}) or {}).get(regime_label, {})
        default_decision = regime_rule.get("default_decision")
        requires_rs = bool(regime_rule.get("require_relative_strength_for_keep"))
        if (
            requires_rs
            and not has_confirmed_relative_strength
            and coverage_status == "active"
        ):
            score += cls._number(weights.get("strong_repair_non_confirmed_penalty"), -10.0)
            result["trend_filter_risk_flags"].append("strong_repair_without_confirmation")
            result["trend_filter_invalid_conditions"].append("relative_strength_required_for_keep")
        elif requires_rs and not has_confirmed_relative_strength and coverage_status == "degraded_partial_missing":
            score += cls._number(weights.get("strong_repair_non_confirmed_penalty"), -10.0) / 2.0
            result["trend_filter_risk_flags"].append("relative_strength_unverified")
        elif requires_rs and not has_confirmed_relative_strength and coverage_status == "degraded_global_missing":
            result["trend_filter_risk_flags"].append("global_confirmation_unavailable")
            result["trend_filter_risk_flags"].append("relative_strength_unverified")

        result["trend_filter_score"] = round(score, 4)
        result["score_adjustment"] = round(score, 4)
        result["trend_filter_decision"] = cls._decision(
            score=score,
            config=config,
            default_decision=default_decision,
            weak_decision=regime_rule.get("weak_relative_strength_decision"),
            requires_rs=requires_rs,
            has_relative_strength=has_confirmed_relative_strength,
            coverage_status=coverage_status,
            has_explicit_negative_relative_strength=has_explicit_negative_relative_strength,
        )
        return cls._attach(candidate, result)

    @classmethod
    def load_config(cls):
        if cls._CONFIG_CACHE is not None:
            return deepcopy(cls._CONFIG_CACHE)
        config = deepcopy(cls.DEFAULT_CONFIG)
        try:
            with cls.CONFIG_PATH.open("r", encoding="utf-8") as fh:
                external = json.load(fh)
            config = cls._deep_merge(config, external)
        except (OSError, ValueError, TypeError):
            pass
        cls._CONFIG_CACHE = config
        return deepcopy(config)

    @classmethod
    def reset_cache(cls):
        cls._CONFIG_CACHE = None

    @staticmethod
    def _empty_result():
        return {
            "trend_filter_decision": "keep",
            "trend_filter_status": "active",
            "trend_filter_context": {
                "trend_total_count": 0,
                "rs_vs_etf_available_count": 0,
                "rs_vs_index_available_count": 0,
                "amount_1m_ratio_available_count": 0,
                "confirmation_coverage_count": 0,
                "confirmation_coverage_ratio": 0.0,
            },
            "trend_filter_score": 0.0,
            "score_adjustment": 0.0,
            "trend_filter_reasons": [],
            "trend_filter_risk_flags": [],
            "trend_filter_missing_fields": [],
            "trend_filter_invalid_conditions": [],
        }

    @classmethod
    def _decision(
        cls,
        score,
        config,
        default_decision=None,
        weak_decision=None,
        requires_rs=False,
        has_relative_strength=False,
        coverage_status="active",
        has_explicit_negative_relative_strength=False,
    ):
        if default_decision == "drop":
            return "drop"
        if coverage_status == "degraded_global_missing" and not has_explicit_negative_relative_strength:
            return "keep"
        if requires_rs and not has_relative_strength and weak_decision in {"observe", "drop"}:
            return weak_decision
        if default_decision in {"observe", "keep"} and score >= 0:
            return default_decision

        thresholds = config.get("decision_thresholds", {})
        keep_score = cls._number(thresholds.get("keep_score"), 8.0)
        observe_score = cls._number(thresholds.get("observe_score"), -10.0)
        if score >= keep_score:
            return "keep"
        if coverage_status == "degraded_partial_missing":
            return "observe"
        if score >= observe_score:
            return "observe"
        return "drop"

    @classmethod
    def _attach(cls, candidate, result):
        for key in (
            "trend_filter_reasons",
            "trend_filter_risk_flags",
            "trend_filter_missing_fields",
            "trend_filter_invalid_conditions",
        ):
            result[key] = cls._dedupe(result.get(key, []))
        candidate.update(result)
        return result

    @classmethod
    def build_coverage_context(cls, candidates):
        context = {
            "trend_total_count": 0,
            "rs_vs_etf_available_count": 0,
            "rs_vs_index_available_count": 0,
            "amount_1m_ratio_available_count": 0,
            "confirmation_coverage_count": 0,
            "confirmation_coverage_ratio": 0.0,
        }
        items = list(candidates or [])
        context["trend_total_count"] = len(items)
        if not items:
            return context

        for candidate in items:
            data = (candidate or {}).get("data", {}) or {}
            has_any = False
            _value, has_etf = cls._field_value(
                data,
                nested_key="rs_vs_etf_pct",
                flat_keys=("confirmation_rs_vs_etf_pct", "rs_vs_etf_pct"),
            )
            if has_etf:
                context["rs_vs_etf_available_count"] += 1
                has_any = True
            _value, has_index = cls._field_value(
                data,
                nested_key="rs_vs_index_pct",
                flat_keys=("confirmation_rs_vs_index_pct", "rs_vs_index_pct"),
            )
            if has_index:
                context["rs_vs_index_available_count"] += 1
                has_any = True
            _value, has_amount = cls._field_value(
                data,
                nested_key="amount_1m_ratio",
                flat_keys=("confirmation_amount_1m_ratio", "amount_1m_ratio"),
            )
            if has_amount:
                context["amount_1m_ratio_available_count"] += 1
                has_any = True
            if has_any:
                context["confirmation_coverage_count"] += 1

        total = float(context["trend_total_count"] or 0)
        context["confirmation_coverage_ratio"] = round(
            context["confirmation_coverage_count"] / total,
            4,
        ) if total else 0.0
        return context

    @classmethod
    def normalize_coverage_context(cls, coverage_context, candidate=None):
        if isinstance(coverage_context, dict):
            base = deepcopy(cls._empty_result()["trend_filter_context"])
            base.update({k: coverage_context.get(k, base[k]) for k in base})
            try:
                base["confirmation_coverage_ratio"] = float(base["confirmation_coverage_ratio"])
            except (TypeError, ValueError):
                base["confirmation_coverage_ratio"] = 0.0
            return base

        return cls.build_coverage_context([candidate] if candidate else [])

    @classmethod
    def _coverage_status(cls, coverage_context, coverage_guard):
        if not coverage_guard.get("enabled", True):
            return "active"
        ratio = cls._number((coverage_context or {}).get("confirmation_coverage_ratio"))
        global_threshold = cls._number(coverage_guard.get("global_missing_threshold"), 0.2)
        partial_threshold = cls._number(coverage_guard.get("partial_missing_threshold"), 0.6)
        if ratio < global_threshold:
            return "degraded_global_missing"
        if ratio < partial_threshold:
            return "degraded_partial_missing"
        return "active"

    @staticmethod
    def _is_trend_candidate(candidate):
        category = str(
            candidate.get("signal_category")
            or candidate.get("category")
            or candidate.get("signal_type")
            or "trend"
        )
        return category in {"", "trend"}

    @staticmethod
    def _regime_label(regime, candidate):
        if isinstance(regime, dict):
            return str(regime.get("label", "") or "")
        if regime:
            return str(regime)
        return str(candidate.get("market_regime", "") or "")

    @classmethod
    def _field_value(cls, data, nested_key, flat_keys):
        confirmation = data.get("confirmation_data", {}) or {}
        if nested_key in confirmation and confirmation.get(nested_key) not in (None, ""):
            return cls._number(confirmation.get(nested_key)), True
        for key in flat_keys:
            if key in data and data.get(key) not in (None, ""):
                return cls._number(data.get(key)), True
        return 0.0, False

    @staticmethod
    def _number(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _dedupe(values):
        output = []
        seen = set()
        for value in values or []:
            text = str(value)
            if text in seen:
                continue
            seen.add(text)
            output.append(value)
        return output

    @classmethod
    def _deep_merge(cls, base, update):
        for key, value in (update or {}).items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                base[key] = cls._deep_merge(base[key], value)
            else:
                base[key] = value
        return base
