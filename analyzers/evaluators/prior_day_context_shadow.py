# -*- coding: utf-8 -*-
"""Shadow-only prior-day context bonus evaluator."""

from __future__ import annotations

import json
import os
from copy import deepcopy


class PriorDayContextShadowEvaluator:
    """Audit hypothetical T-1 context bonuses without changing true ranking."""

    CONFIG_PATH = os.path.join(
        "reports",
        "analysis",
        "configs",
        "prior_day_context_config.json",
    )
    LEADING_CLUSTER_CONFIG_PATH = os.path.join(
        "reports",
        "analysis",
        "configs",
        "leading_cluster_config.json",
    )

    _CONFIG_CACHE = None
    _LEADING_CLUSTER_CONFIG_CACHE = None

    @classmethod
    def reset_cache(cls):
        cls._CONFIG_CACHE = None
        cls._LEADING_CLUSTER_CONFIG_CACHE = None

    @classmethod
    def evaluate(cls, candidate: dict, prior_day_context: dict | None) -> dict:
        config = cls._load_config()
        confidence = str((prior_day_context or {}).get("context_confidence", "low") or "low")
        reasons = []
        flags = [f"context_confidence_{confidence}"]
        bonus = 0.0

        if not config.get("enabled", True):
            return cls._result(candidate, 0.0, reasons, flags + ["shadow_disabled"], confidence)
        if not (prior_day_context or {}).get("available"):
            reasons.append("prior_day_context_unavailable")
            return cls._result(candidate, 0.0, reasons, flags, confidence)
        if confidence == "low":
            reasons.append("low_confidence_zero_bonus")
            return cls._result(candidate, 0.0, reasons, flags, confidence)

        category = str(candidate.get("signal_category", "") or candidate.get("category", "") or "")
        category = cls._normalize_category(category)
        if category not in {"trend", "reversal", "trap"}:
            return cls._result(candidate, 0.0, reasons, flags + ["unsupported_category"], confidence)

        current_clusters = cls._candidate_cluster_keys(candidate)
        prev_clusters = cls._prior_day_cluster_keys(prior_day_context)
        matched_prev_cluster = bool(current_clusters & prev_clusters) if prev_clusters else False
        if matched_prev_cluster:
            reasons.append("matched_prev_leading_cluster")
        else:
            reasons.append("not_in_prev_leading_cluster")

        if category == "trend":
            bonus += cls._trend_bonus(candidate, prior_day_context, matched_prev_cluster, reasons, flags)
        elif category == "reversal":
            bonus += cls._reversal_bonus(candidate, prior_day_context, matched_prev_cluster, reasons, flags)
        elif category == "trap":
            bonus += cls._trap_bonus(candidate, prior_day_context, matched_prev_cluster, reasons, flags)

        capped = cls._apply_cap(bonus, confidence, config)
        if capped != bonus:
            flags.append("shadow_bonus_capped")
        return cls._result(candidate, capped, reasons, flags, confidence)

    @classmethod
    def _trend_bonus(cls, candidate, prior_day_context, matched_prev_cluster, reasons, flags):
        config = cls._load_config().get("trend", {}) or {}
        bias = str(((prior_day_context or {}).get("bias", {}) or {}).get("trend_bias", "neutral") or "neutral")
        leading_status = str(candidate.get("leading_cluster_status", "") or "")
        bonus = 0.0
        if bias == "negative":
            reasons.append("prev_day_trend_bias_negative")
            if matched_prev_cluster and leading_status in {"active", "partial"}:
                bonus += float(config.get("prev_cluster_continuation_bonus", 3.0) or 0.0)
                reasons.append("prev_leading_cluster_continuation_candidate")
            else:
                bonus += float(config.get("prev_day_negative_penalty", -4.0) or 0.0)
        elif matched_prev_cluster and leading_status in {"active", "partial"}:
            bonus += float(config.get("prev_cluster_continuation_bonus", 3.0) or 0.0)
            reasons.append("prev_leading_cluster_continuation_candidate")
        if leading_status == "stale_ifind_snapshot":
            flags.append("leading_cluster_stale_risk")
        return bonus

    @classmethod
    def _reversal_bonus(cls, candidate, prior_day_context, matched_prev_cluster, reasons, flags):
        config = cls._load_config().get("reversal", {}) or {}
        bias = str(((prior_day_context or {}).get("bias", {}) or {}).get("reversal_bias", "neutral") or "neutral")
        regime = str((prior_day_context or {}).get("market_regime", "") or "")
        bonus = 0.0
        if bias == "positive":
            bonus += float(config.get("prev_day_positive_bonus", 4.0) or 0.0)
            reasons.append("prev_day_reversal_bias_positive")
        if regime == "risk_off":
            bonus += float(config.get("risk_off_reversal_bonus", 3.0) or 0.0)
            reasons.append("prev_day_risk_off_reversal_watch")
        if matched_prev_cluster:
            reasons.append("prev_reversal_cluster_overlap")
        return bonus

    @classmethod
    def _trap_bonus(cls, candidate, prior_day_context, matched_prev_cluster, reasons, flags):
        config = cls._load_config().get("cp", {}) or {}
        bias = str(((prior_day_context or {}).get("bias", {}) or {}).get("cp_bias", "neutral") or "neutral")
        cp_risk_decision = str(candidate.get("cp_risk_decision", "") or "")
        leading_status = str(candidate.get("leading_cluster_status", "") or "")
        if (
            cp_risk_decision == "leading_cluster_exempt"
            and bool(config.get("leading_cluster_exempt_no_extra_cp_bonus", True))
        ):
            reasons.append("cp_leading_cluster_exempt_skip")
            return 0.0
        if bias == "positive" and leading_status != "active":
            reasons.append("prev_day_cp_bias_positive")
            if not matched_prev_cluster:
                return float(config.get("prev_day_cp_effective_bonus", 3.0) or 0.0)
        return 0.0

    @classmethod
    def _candidate_cluster_keys(cls, candidate) -> set[str]:
        data = candidate.get("data", {}) or {}
        raw_values = [
            candidate.get("leading_cluster_name", ""),
            data.get("group", ""),
            data.get("theme_cluster", ""),
            candidate.get("group", ""),
            candidate.get("theme_cluster", ""),
        ]
        ifind_concepts = candidate.get("ifind_signal_concepts", [])
        if isinstance(ifind_concepts, str):
            raw_values.extend([part.strip() for part in ifind_concepts.split(",") if part.strip()])
        elif isinstance(ifind_concepts, list):
            raw_values.extend(ifind_concepts)

        keys = set()
        for value in raw_values:
            keys.update(cls._expand_aliases(value))
        return keys

    @classmethod
    def _prior_day_cluster_keys(cls, prior_day_context) -> set[str]:
        keys = set()
        for value in (prior_day_context or {}).get("leading_clusters", []) or []:
            keys.update(cls._expand_aliases(value))
        return keys

    @classmethod
    def _expand_aliases(cls, value) -> set[str]:
        text = str(value or "").strip()
        if not text:
            return set()
        normalized = cls._normalize_cluster_name(text)
        tokens = {normalized}
        config = cls._load_leading_cluster_config()
        alias_maps = []
        alias_maps.append(config.get("sector_alias_map", {}) or {})
        alias_maps.append(config.get("ifind_cluster_alias", {}) or {})
        for alias_map in alias_maps:
            for key, mapped in alias_map.items():
                key_norm = cls._normalize_cluster_name(key)
                mapped_values = mapped if isinstance(mapped, list) else [mapped]
                mapped_norm = {cls._normalize_cluster_name(item) for item in mapped_values if str(item or "").strip()}
                if normalized == key_norm or normalized in mapped_norm:
                    tokens.add(key_norm)
                    tokens.update(mapped_norm)
        return {item for item in tokens if item}

    @staticmethod
    def _normalize_cluster_name(value) -> str:
        text = str(value or "").strip()
        for suffix in ("概念", "板块", "主题"):
            if text.endswith(suffix):
                text = text[: -len(suffix)]
        return text.lower().replace(" ", "")

    @staticmethod
    def _normalize_category(value) -> str:
        mapping = {
            "trap": "trap",
            "cp": "trap",
            "reversal": "reversal",
            "trend": "trend",
        }
        return mapping.get(str(value or "").strip().lower(), str(value or "").strip().lower())

    @classmethod
    def _apply_cap(cls, bonus: float, confidence: str, config: dict) -> float:
        caps = (config.get("bonus_caps", {}) or {})
        cap = float(caps.get(confidence, 0.0) or 0.0)
        if cap <= 0:
            return 0.0
        return max(-cap, min(cap, float(bonus or 0.0)))

    @classmethod
    def _result(cls, candidate, bonus, reasons, flags, confidence):
        base_score = cls._number(candidate.get("action_score"))
        return {
            "prior_day_context_bonus_shadow": round(float(bonus or 0.0), 4),
            "prior_day_context_score_shadow": round(base_score + float(bonus or 0.0), 4),
            "prior_day_context_rank_delta_shadow": 0,
            "prior_day_context_reasons": cls._dedupe(reasons),
            "prior_day_context_flags": cls._dedupe(flags),
            "prior_day_context_confidence": confidence or "low",
        }

    @classmethod
    def _load_config(cls):
        if cls._CONFIG_CACHE is not None:
            return deepcopy(cls._CONFIG_CACHE)
        data = cls._read_json(cls.CONFIG_PATH)
        cls._CONFIG_CACHE = data if isinstance(data, dict) else {}
        return deepcopy(cls._CONFIG_CACHE)

    @classmethod
    def _load_leading_cluster_config(cls):
        if cls._LEADING_CLUSTER_CONFIG_CACHE is not None:
            return deepcopy(cls._LEADING_CLUSTER_CONFIG_CACHE)
        data = cls._read_json(cls.LEADING_CLUSTER_CONFIG_PATH)
        cls._LEADING_CLUSTER_CONFIG_CACHE = data if isinstance(data, dict) else {}
        return deepcopy(cls._LEADING_CLUSTER_CONFIG_CACHE)

    @staticmethod
    def _read_json(path):
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}

    @staticmethod
    def _number(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    @staticmethod
    def _dedupe(items):
        seen = set()
        ordered = []
        for item in items or []:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            ordered.append(text)
        return ordered
