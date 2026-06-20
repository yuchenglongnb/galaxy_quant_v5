# -*- coding: utf-8 -*-
"""Shadow-only three-layer trend gate.

This evaluator does not change shortlist routing. It only appends explainable
shadow fields so we can compare a stricter structure-aware trend gate against
the currently active TrendCandidateFilter.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path


class TrendTripleGate:
    """Evaluate trend candidates in shadow mode."""

    CONFIG_PATH = (
        Path(__file__).resolve().parents[2]
        / "reports"
        / "analysis"
        / "configs"
        / "trend_triple_gate_config.json"
    )
    _CONFIG_CACHE = None

    DEFAULT_CONFIG = {
        "enabled": True,
        "thresholds": {
            "weak_vs_etf": -0.3,
            "weak_vs_index": -0.3,
            "leading_cluster_active_strength": 60.0,
            "leading_cluster_partial_strength": 45.0,
            "amount_confirm_ratio": 1.2,
        },
        "weights": {
            "strong_vs_etf": 10.0,
            "strong_vs_index": 8.0,
            "sector_positive_evidence": 8.0,
            "leading_cluster_active": 10.0,
            "leading_cluster_partial": 4.0,
            "amount_confirmed": 4.0,
            "stale_overlay_risk": -2.0,
            "missing_penalty": -1.0,
        },
        "regime_rules": {
            "hostile": {"default_decision": "drop"},
            "risk_off": {"default_decision": "drop"},
            "mixed": {"default_decision": "observe"},
            "repair": {"default_decision": "observe"},
            "strong_repair": {"default_decision": "observe"},
            "continuation": {"default_decision": "observe"},
        },
        "decision_thresholds": {
            "main_score": 18.0,
            "observe_score": 0.0,
        },
    }

    POSITIVE_SECTOR_FLAGS = {
        "sector_strength_score_confirmed",
        "sector_breadth_strength_confirmed",
        "sector_limitup_breadth_confirmed",
        "sector_money_flow_confirmed",
    }

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

    @classmethod
    def evaluate_shadow(cls, candidate, regime=None):
        config = cls.load_config()
        result = cls._empty_result()
        if not config.get("enabled", True):
            result["trend_gate_decision_shadow"] = "disabled"
            result["trend_gate_reasons"].append("trend_triple_gate_disabled")
            return cls._attach(candidate, result)

        if not cls._is_trend_candidate(candidate):
            result["trend_gate_decision_shadow"] = "disabled"
            result["trend_gate_reasons"].append("non_trend_candidate")
            return cls._attach(candidate, result)

        data = candidate.get("data", {}) or {}
        confirmation = data.get("confirmation_data", {}) or {}
        thresholds = config.get("thresholds", {}) or {}
        weights = config.get("weights", {}) or {}
        regime_label = cls._regime_label(regime, candidate)
        regime_rule = (config.get("regime_rules", {}) or {}).get(regime_label, {})

        rs_vs_etf, has_rs_etf = cls._field_value(
            data,
            nested_key="rs_vs_etf_pct",
            flat_keys=("confirmation_rs_vs_etf_pct", "rs_vs_etf_pct"),
        )
        rs_vs_index, has_rs_index = cls._field_value(
            data,
            nested_key="rs_vs_index_pct",
            flat_keys=("confirmation_rs_vs_index_pct", "rs_vs_index_pct"),
        )
        amount_ratio, has_amount = cls._field_value(
            data,
            nested_key="amount_1m_ratio",
            flat_keys=("confirmation_amount_1m_ratio", "amount_1m_ratio"),
        )
        benchmark_etf_code = str(
            confirmation.get("benchmark_etf_code")
            or data.get("benchmark_etf_code")
            or ""
        )
        benchmark_index_code = str(
            confirmation.get("benchmark_index_code")
            or data.get("benchmark_index_code")
            or ""
        )

        leading_membership = bool(candidate.get("leading_cluster_membership"))
        leading_name = str(candidate.get("leading_cluster_name", "") or "")
        leading_strength = cls._number(candidate.get("leading_cluster_strength"), float("nan"))
        leading_status = str(candidate.get("leading_cluster_status", "") or "")
        leading_evidence = list(candidate.get("leading_cluster_evidence", []) or [])
        leading_risk_flags = list(candidate.get("leading_cluster_risk_flags", []) or [])
        trend_filter_decision = str(candidate.get("trend_filter_decision", "") or "")
        trend_filter_status = str(candidate.get("trend_filter_status", "") or "")

        score = 0.0

        # Layer 1: stock relative strength.
        weak_vs_etf = False
        weak_vs_index = False
        if has_rs_etf:
            if rs_vs_etf < cls._number(thresholds.get("weak_vs_etf"), -0.3):
                weak_vs_etf = True
                result["trend_gate_risk_flags"].append("weak_vs_etf")
            else:
                result["trend_gate_reasons"].append("strong_vs_etf")
                score += cls._number(weights.get("strong_vs_etf"), 10.0)
        else:
            result["trend_gate_missing_fields"].append("missing_rs_vs_etf_pct")
            result["trend_gate_risk_flags"].append("relative_strength_unverified")
            score += cls._number(weights.get("missing_penalty"), -1.0)

        if has_rs_index:
            if rs_vs_index < cls._number(thresholds.get("weak_vs_index"), -0.3):
                weak_vs_index = True
                result["trend_gate_risk_flags"].append("weak_vs_index")
            else:
                result["trend_gate_reasons"].append("strong_vs_index")
                score += cls._number(weights.get("strong_vs_index"), 8.0)
        else:
            result["trend_gate_missing_fields"].append("missing_rs_vs_index_pct")
            result["trend_gate_risk_flags"].append("relative_strength_unverified")
            score += cls._number(weights.get("missing_penalty"), -1.0)

        # Layer 2: sector / ETF side evidence.
        if benchmark_etf_code:
            result["trend_gate_reasons"].append("benchmark_etf_mapped")
        else:
            result["trend_gate_missing_fields"].append("missing_benchmark_etf_code")
        if benchmark_index_code:
            result["trend_gate_reasons"].append("benchmark_index_mapped")
        else:
            result["trend_gate_missing_fields"].append("missing_benchmark_index_code")

        sector_positive_flags = [
            flag for flag in leading_evidence if flag in cls.POSITIVE_SECTOR_FLAGS
        ]
        sector_positive_evidence = bool(sector_positive_flags)
        if sector_positive_evidence:
            score += cls._number(weights.get("sector_positive_evidence"), 8.0)
            result["trend_gate_reasons"].extend(sorted(set(sector_positive_flags)))
        else:
            if not benchmark_etf_code:
                result["trend_gate_risk_flags"].append("etf_vs_index_unverified")
            result["trend_gate_risk_flags"].append("sector_vs_index_unverified")

        # Layer 3: leading cluster.
        active_leading_cluster = (
            leading_membership
            and leading_status == "active"
            and leading_strength == leading_strength
            and leading_strength >= cls._number(thresholds.get("leading_cluster_active_strength"), 60.0)
        )
        partial_leading_cluster = (
            leading_membership
            and not active_leading_cluster
            and leading_strength == leading_strength
            and leading_strength >= cls._number(thresholds.get("leading_cluster_partial_strength"), 45.0)
            and (leading_status == "partial" or sector_positive_evidence)
        )
        if active_leading_cluster:
            result["trend_gate_reasons"].append("leading_cluster_active")
            score += cls._number(weights.get("leading_cluster_active"), 10.0)
        elif partial_leading_cluster:
            result["trend_gate_reasons"].append("leading_cluster_partial")
            score += cls._number(weights.get("leading_cluster_partial"), 4.0)
        else:
            if not leading_membership:
                result["trend_gate_missing_fields"].append("leading_cluster_missing")
            else:
                result["trend_gate_risk_flags"].append("leading_cluster_weak")

        if "stale_ifind_snapshot" in leading_risk_flags:
            result["trend_gate_risk_flags"].append("leading_cluster_stale_risk")
            score += cls._number(weights.get("stale_overlay_risk"), -2.0)

        if has_amount:
            if amount_ratio >= cls._number(thresholds.get("amount_confirm_ratio"), 1.2):
                result["trend_gate_reasons"].append("amount_confirmed")
                score += cls._number(weights.get("amount_confirmed"), 4.0)
            else:
                result["trend_gate_risk_flags"].append("amount_not_confirmed")
        else:
            result["trend_gate_missing_fields"].append("missing_amount_1m_ratio")

        decision = str(regime_rule.get("default_decision", "observe") or "observe")
        if regime_label in {"hostile", "risk_off"}:
            decision = "drop"
            result["trend_gate_reasons"].append(f"regime_{regime_label}")
        elif weak_vs_etf or weak_vs_index:
            decision = "drop"
            result["trend_gate_reasons"].append("explicit_relative_weakness")
        elif not leading_membership and not sector_positive_evidence:
            decision = "observe"
            result["trend_gate_reasons"].append("leading_cluster_unverified")
        else:
            main_score = cls._number((config.get("decision_thresholds", {}) or {}).get("main_score"), 18.0)
            observe_score = cls._number((config.get("decision_thresholds", {}) or {}).get("observe_score"), 0.0)
            if (
                not weak_vs_etf
                and not weak_vs_index
                and sector_positive_evidence
                and active_leading_cluster
                and score >= main_score
            ):
                decision = "main"
            elif score >= observe_score:
                decision = "observe"
            else:
                decision = "drop"

        result["trend_gate_decision_shadow"] = decision
        result["trend_gate_score_shadow"] = round(score, 4)
        result["trend_gate_context"] = {
            "rs_vs_etf_pct": rs_vs_etf if has_rs_etf else None,
            "rs_vs_index_pct": rs_vs_index if has_rs_index else None,
            "benchmark_etf_code": benchmark_etf_code,
            "benchmark_index_code": benchmark_index_code,
            "amount_1m_ratio": amount_ratio if has_amount else None,
            "leading_cluster_membership": leading_membership,
            "leading_cluster_name": leading_name,
            "leading_cluster_strength": None if leading_strength != leading_strength else leading_strength,
            "leading_cluster_status": leading_status,
            "leading_cluster_evidence": leading_evidence,
            "trend_filter_decision": trend_filter_decision,
            "trend_filter_status": trend_filter_status,
            "regime": regime_label,
        }
        return cls._attach(candidate, result)

    @staticmethod
    def _empty_result():
        return {
            "trend_gate_decision_shadow": "observe",
            "trend_gate_score_shadow": 0.0,
            "trend_gate_reasons": [],
            "trend_gate_missing_fields": [],
            "trend_gate_risk_flags": [],
            "trend_gate_context": {
                "rs_vs_etf_pct": None,
                "rs_vs_index_pct": None,
                "benchmark_etf_code": "",
                "benchmark_index_code": "",
                "amount_1m_ratio": None,
                "leading_cluster_membership": False,
                "leading_cluster_name": "",
                "leading_cluster_strength": None,
                "leading_cluster_status": "",
                "leading_cluster_evidence": [],
                "trend_filter_decision": "",
                "trend_filter_status": "",
                "regime": "",
            },
        }

    @classmethod
    def _attach(cls, candidate, result):
        for key in ("trend_gate_reasons", "trend_gate_missing_fields", "trend_gate_risk_flags"):
            result[key] = cls._dedupe(result.get(key, []))
        candidate.update(result)
        return result

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
