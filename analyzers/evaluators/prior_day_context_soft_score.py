# -*- coding: utf-8 -*-
"""Guarded prior-day context soft-score evaluator."""

from __future__ import annotations

import json
import os
from copy import deepcopy


class PriorDayContextSoftScoreEvaluator:
    """Apply a small T-1 context bonus to real action scores with rollback guards."""

    CONFIG_PATH = os.path.join(
        "reports",
        "analysis",
        "configs",
        "prior_day_context_config.json",
    )

    _CONFIG_CACHE = None

    @classmethod
    def reset_cache(cls):
        cls._CONFIG_CACHE = None

    @classmethod
    def apply(cls, candidate: dict, prior_day_context: dict | None) -> dict:
        config = cls._load_config()
        base_score = cls._number(candidate.get("action_score"))
        target_type = cls._normalize_target_type(
            (candidate.get("data", {}) or {}).get("target_type", candidate.get("target_type", ""))
        )
        confidence = str(
            candidate.get("prior_day_context_confidence")
            or (prior_day_context or {}).get("context_confidence", "low")
            or "low"
        )
        shadow_bonus = cls._number(candidate.get("prior_day_context_bonus_shadow"))
        available = bool((prior_day_context or {}).get("available"))
        apply_enabled = bool(config.get("enabled", True)) and bool(config.get("apply_to_score", False))
        shadow_only = bool(config.get("shadow_only", False))
        disable_when_unavailable = bool(config.get("disable_when_context_unavailable", True))
        target_scope = config.get("target_type_scope", {}) or {}
        target_scope_enabled = bool(target_scope.get("enabled", False))
        apply_targets = {str(item) for item in (target_scope.get("apply_score_target_types", []) or [])}
        annotation_targets = {str(item) for item in (target_scope.get("annotation_only_target_types", []) or [])}
        unknown_mode = str(target_scope.get("unknown_target_type_mode", "annotation_only") or "annotation_only")

        applied_bonus = 0.0
        annotation_bonus = 0.0
        apply_mode = "shadow_only"
        applied = False
        scope_reason = "soft_score_disabled"

        if apply_enabled and not shadow_only:
            if confidence != "low" and (available or not disable_when_unavailable):
                scoped_bonus = cls._cap_bonus(shadow_bonus, confidence, config)
                if target_scope_enabled:
                    if target_type in apply_targets:
                        applied_bonus = scoped_bonus
                        apply_mode = "soft_score"
                        applied = abs(applied_bonus) > 1e-9
                        scope_reason = "stock_target_type"
                    elif target_type in annotation_targets:
                        annotation_bonus = scoped_bonus
                        apply_mode = "annotation_only"
                        scope_reason = "non_stock_target_type"
                    elif target_type == "unknown" and unknown_mode == "annotation_only":
                        annotation_bonus = 0.0
                        apply_mode = "annotation_only"
                        scope_reason = "unknown_target_type"
                    else:
                        applied_bonus = scoped_bonus
                        apply_mode = "soft_score"
                        applied = abs(applied_bonus) > 1e-9
                        scope_reason = "target_type_scope_fallback"
                else:
                    applied_bonus = scoped_bonus
                    apply_mode = "soft_score"
                    applied = abs(applied_bonus) > 1e-9
                    scope_reason = "scope_disabled"
            else:
                apply_mode = "disabled"
                scope_reason = "context_unavailable_or_low_confidence"

        score_after = round(base_score + applied_bonus, 4)
        bonus_capped = round(applied_bonus, 4) != round(shadow_bonus, 4) and apply_mode == "soft_score"
        return {
            "prior_day_context_bonus": round(applied_bonus, 4),
            "prior_day_context_annotation_bonus": round(annotation_bonus, 4),
            "prior_day_context_bonus_applied": applied,
            "prior_day_context_bonus_capped": bool(bonus_capped),
            "prior_day_context_apply_mode": apply_mode,
            "prior_day_context_scope_reason": scope_reason,
            "prior_day_context_target_type": target_type,
            "prior_day_context_score_before": round(base_score, 4),
            "prior_day_context_score_after": round(score_after, 4),
        }

    @classmethod
    def _cap_bonus(cls, bonus: float, confidence: str, config: dict) -> float:
        caps = (config.get("max_abs_bonus", {}) or {}) or (config.get("bonus_caps", {}) or {})
        cap = cls._number(caps.get(confidence), 0.0)
        if cap <= 0:
            return 0.0
        return max(-cap, min(cap, cls._number(bonus)))

    @classmethod
    def _load_config(cls):
        if cls._CONFIG_CACHE is not None:
            return deepcopy(cls._CONFIG_CACHE)
        if not os.path.exists(cls.CONFIG_PATH):
            cls._CONFIG_CACHE = {}
            return {}
        try:
            with open(cls.CONFIG_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            data = {}
        cls._CONFIG_CACHE = data if isinstance(data, dict) else {}
        return deepcopy(cls._CONFIG_CACHE)

    @staticmethod
    def _number(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    @staticmethod
    def _normalize_target_type(value) -> str:
        text = str(value or "").strip().lower()
        mapping = {
            "stock": "stock",
            "个股": "stock",
            "etf": "ETF",
            "index": "index",
            "指数": "index",
            "industry": "industry",
            "行业": "industry",
        }
        return mapping.get(text, "unknown")
