# -*- coding: utf-8 -*-
"""Layer CP risk into hard trap, crowded observe, and leading-cluster exempt."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path


class CPRiskEvaluator:
    """Evaluate CP candidates using normalized leading-cluster evidence only."""

    CONFIG_PATH = (
        Path(__file__).resolve().parents[2]
        / "reports"
        / "analysis"
        / "configs"
        / "cp_risk_config.json"
    )

    DEFAULT_CONFIG = {
        "version": "0.1.0",
        "enabled": True,
        "thresholds": {
            "high_cp_score": 60.0,
            "very_high_cp_score": 100.0,
            "high_open_pct": 5.0,
            "leading_cluster_strength_exempt": 60.0,
            "amount_confirm_ratio": 1.2,
            "weak_vs_index": -0.3,
            "weak_vs_etf": -0.3,
        },
        "strong_evidence_flags": [
            "sector_strength_score_confirmed",
            "theme_limitup_diffusion_confirmed",
            "limitup_core_member_confirmed",
            "ifind_sector_strength_confirmed",
            "existing_theme_cluster_bonus",
        ],
        "regime_rules": {
            "shrinking_volume_trend_continuation": {
                "allow_leading_cluster_exempt": True,
                "default_high_cp_decision": "crowded_observe",
            },
            "strong_repair": {
                "allow_leading_cluster_exempt": True,
                "default_high_cp_decision": "crowded_observe",
            },
            "continuation": {
                "allow_leading_cluster_exempt": True,
                "default_high_cp_decision": "crowded_observe",
            },
            "strong_repair_with_rotation": {
                "allow_leading_cluster_exempt": True,
                "default_high_cp_decision": "hard_trap_if_non_leading",
            },
            "hostile": {
                "allow_leading_cluster_exempt": False,
                "default_high_cp_decision": "hard_trap",
            },
            "risk_off": {
                "allow_leading_cluster_exempt": False,
                "default_high_cp_decision": "hard_trap",
            },
        },
    }

    _CONFIG_CACHE = None

    @classmethod
    def reset_cache(cls):
        cls._CONFIG_CACHE = None

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
    def evaluate_candidate(cls, candidate, regime=None):
        config = cls.load_config()
        result = cls._empty_result()
        if not config.get("enabled", True):
            return result

        cp_score = cls._number(candidate.get("cp"), float("nan"))
        data = candidate.get("data", {}) or {}
        auction_pct = cls._first_number(
            candidate.get("auction_pct"),
            data.get("auction_pct"),
            default=float("nan"),
        )
        regime_label = cls._resolve_regime(regime, candidate)
        regime_rule = (config.get("regime_rules", {}) or {}).get(regime_label, {})
        thresholds = config.get("thresholds", {}) or {}

        leading_strength = cls._number(candidate.get("leading_cluster_strength"), float("nan"))
        leading_status = str(candidate.get("leading_cluster_status", "") or "")
        leading_membership = bool(candidate.get("leading_cluster_membership"))
        leading_rank = candidate.get("leading_cluster_rank")
        leading_evidence = list(candidate.get("leading_cluster_evidence", []) or [])
        leading_risk_flags = list(candidate.get("leading_cluster_risk_flags", []) or [])

        rs_vs_etf = cls._first_number(
            candidate.get("rs_vs_etf_pct"),
            data.get("rs_vs_etf_pct"),
            (data.get("confirmation_data", {}) or {}).get("rs_vs_etf_pct"),
            default=float("nan"),
        )
        rs_vs_index = cls._first_number(
            candidate.get("rs_vs_index_pct"),
            data.get("rs_vs_index_pct"),
            (data.get("confirmation_data", {}) or {}).get("rs_vs_index_pct"),
            default=float("nan"),
        )
        amount_1m_ratio = cls._first_number(
            candidate.get("amount_1m_ratio"),
            data.get("amount_1m_ratio"),
            (data.get("confirmation_data", {}) or {}).get("amount_1m_ratio"),
            default=float("nan"),
        )

        result["cp_risk_context"] = {
            "regime": regime_label,
            "cp_score": None if cp_score != cp_score else round(cp_score, 4),
            "auction_pct": None if auction_pct != auction_pct else round(auction_pct, 4),
            "leading_cluster_membership": leading_membership,
            "leading_cluster_strength": None if leading_strength != leading_strength else round(leading_strength, 4),
            "leading_cluster_rank": leading_rank,
            "leading_cluster_status": leading_status,
            "rs_vs_etf_pct": None if rs_vs_etf != rs_vs_etf else round(rs_vs_etf, 4),
            "rs_vs_index_pct": None if rs_vs_index != rs_vs_index else round(rs_vs_index, 4),
            "amount_1m_ratio": None if amount_1m_ratio != amount_1m_ratio else round(amount_1m_ratio, 4),
        }

        if cp_score != cp_score:
            result["cp_risk_decision"] = "disabled"
            result["cp_risk_reasons"].append("missing_cp_score")
            result["cp_risk_missing_fields"].append("missing_cp_score")
            return result

        high_cp = cp_score >= cls._number(thresholds.get("high_cp_score"), 60.0)
        very_high_cp = cp_score >= cls._number(thresholds.get("very_high_cp_score"), 100.0)
        high_open = auction_pct == auction_pct and auction_pct >= cls._number(thresholds.get("high_open_pct"), 5.0)
        allow_exempt = bool(regime_rule.get("allow_leading_cluster_exempt", True))
        default_decision = str(regime_rule.get("default_high_cp_decision", "hard_trap") or "hard_trap")

        weak_vs_etf = rs_vs_etf == rs_vs_etf and rs_vs_etf < cls._number(thresholds.get("weak_vs_etf"), -0.3)
        weak_vs_index = rs_vs_index == rs_vs_index and rs_vs_index < cls._number(thresholds.get("weak_vs_index"), -0.3)
        amount_confirmed = amount_1m_ratio == amount_1m_ratio and amount_1m_ratio >= cls._number(
            thresholds.get("amount_confirm_ratio"),
            1.2,
        )
        amount_unconfirmed = amount_1m_ratio == amount_1m_ratio and not amount_confirmed
        strong_evidence_flags = set(config.get("strong_evidence_flags", []) or [])
        strong_evidence = [flag for flag in leading_evidence if flag in strong_evidence_flags]
        strong_leading_cluster = (
            leading_membership
            and leading_status in {"active", "partial"}
            and leading_strength == leading_strength
            and leading_strength >= cls._number(thresholds.get("leading_cluster_strength_exempt"), 60.0)
        )

        if rs_vs_etf != rs_vs_etf:
            result["cp_risk_missing_fields"].append("missing_rs_vs_etf")
        if rs_vs_index != rs_vs_index:
            result["cp_risk_missing_fields"].append("missing_rs_vs_index")
        if amount_1m_ratio != amount_1m_ratio:
            result["cp_risk_missing_fields"].append("missing_amount_1m_ratio")

        result["cp_risk_flags"].extend(flag for flag in leading_risk_flags if flag in {"weak_vs_etf", "weak_vs_index", "amount_not_confirmed"})
        if weak_vs_etf:
            result["cp_risk_flags"].append("weak_vs_etf")
        if weak_vs_index:
            result["cp_risk_flags"].append("weak_vs_index")
        if amount_unconfirmed:
            result["cp_risk_flags"].append("amount_not_confirmed")

        if high_cp:
            result["cp_risk_reasons"].append("high_cp_score")
        if very_high_cp:
            result["cp_risk_reasons"].append("very_high_cp_score")
        if high_open:
            result["cp_risk_reasons"].append("high_open")
        if strong_leading_cluster:
            result["cp_risk_reasons"].append("leading_cluster_strong")
        if strong_evidence:
            result["cp_risk_reasons"].append(f"strong_evidence:{','.join(sorted(strong_evidence))}")

        partial_strength_unverified = (
            strong_leading_cluster
            and strong_evidence
            and rs_vs_etf != rs_vs_etf
            and rs_vs_index != rs_vs_index
        )
        if partial_strength_unverified:
            result["cp_risk_flags"].append("relative_strength_partially_unverified")

        if (
            high_cp
            and allow_exempt
            and strong_leading_cluster
            and not weak_vs_etf
            and not weak_vs_index
            and strong_evidence
        ):
            result["cp_risk_decision"] = "leading_cluster_exempt"
            result["cp_exempt_by_leading_cluster"] = True
            result["cp_risk_reasons"].append("leading_cluster_exempt")
            if amount_unconfirmed:
                result["cp_risk_reasons"].append("amount_unconfirmed_but_exempted")
            result["cp_risk_score"] = round(cp_score - 20.0 + min(len(strong_evidence) * 2.0, 8.0), 4)
            return cls._finalize(result)

        hostile_default = default_decision == "hard_trap" and not allow_exempt
        default_non_leading_trap = default_decision == "hard_trap_if_non_leading" and not strong_leading_cluster
        explicit_weak = weak_vs_etf or weak_vs_index
        if high_cp and (
            explicit_weak
            or hostile_default
            or default_non_leading_trap
            or (high_open and amount_unconfirmed and not strong_leading_cluster)
            or (very_high_cp and not strong_leading_cluster and not strong_evidence)
        ):
            result["cp_risk_decision"] = "hard_trap"
            result["cp_risk_reasons"].append("hard_trap_conditions_met")
            result["cp_risk_score"] = round(cp_score + 10.0 + (6.0 if explicit_weak else 0.0), 4)
            return cls._finalize(result)

        result["cp_risk_decision"] = "crowded_observe"
        result["cp_risk_reasons"].append("crowded_observe_default")
        if leading_status == "partial":
            result["cp_risk_reasons"].append("partial_leading_cluster")
        if not strong_evidence:
            result["cp_risk_reasons"].append("no_strong_exempt_evidence")
        result["cp_risk_score"] = round(cp_score - 5.0, 4)
        return cls._finalize(result)

    @classmethod
    def _empty_result(cls):
        return {
            "cp_risk_decision": "disabled",
            "cp_risk_score": 0.0,
            "cp_exempt_by_leading_cluster": False,
            "cp_risk_reasons": [],
            "cp_risk_flags": [],
            "cp_risk_missing_fields": [],
            "cp_risk_context": {
                "regime": "",
                "cp_score": None,
                "auction_pct": None,
                "leading_cluster_membership": False,
                "leading_cluster_strength": None,
                "leading_cluster_rank": None,
                "leading_cluster_status": "",
                "rs_vs_etf_pct": None,
                "rs_vs_index_pct": None,
                "amount_1m_ratio": None,
            },
        }

    @classmethod
    def _finalize(cls, result):
        for key in ("cp_risk_reasons", "cp_risk_flags", "cp_risk_missing_fields"):
            result[key] = cls._dedupe(result.get(key, []))
        return result

    @staticmethod
    def _resolve_regime(regime, candidate):
        if isinstance(regime, dict):
            return str(regime.get("label", "") or "")
        if regime:
            return str(regime)
        return str(candidate.get("market_regime", "") or "")

    @staticmethod
    def _first_number(*values, default=0.0):
        for value in values:
            number = CPRiskEvaluator._number(value, float("nan"))
            if number == number:
                return number
        return default

    @staticmethod
    def _number(value, default=0.0):
        try:
            if value is None or value == "":
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _dedupe(items):
        seen = set()
        result = []
        for item in items or []:
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    @staticmethod
    def _deep_merge(base, extra):
        if not isinstance(base, dict) or not isinstance(extra, dict):
            return deepcopy(extra)
        merged = deepcopy(base)
        for key, value in extra.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = CPRiskEvaluator._deep_merge(merged[key], value)
            else:
                merged[key] = deepcopy(value)
        return merged
