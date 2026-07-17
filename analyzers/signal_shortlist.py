# -*- coding: utf-8 -*-
"""Build a compact actionable shortlist without discarding research candidates."""

from __future__ import annotations

import os
from collections import defaultdict
import pandas as pd

from config.settings import AuctionConfig

try:
    from analyzers.evaluators.trend_candidate_filter import TrendCandidateFilter
except Exception:  # pragma: no cover - defensive fallback for runtime packaging
    TrendCandidateFilter = None

try:
    from analyzers.evaluators.leading_cluster_evidence import LeadingClusterEvidenceBuilder
except Exception:  # pragma: no cover - defensive fallback for runtime packaging
    LeadingClusterEvidenceBuilder = None

try:
    from analyzers.evaluators.cp_risk_evaluator import CPRiskEvaluator
except Exception:  # pragma: no cover - defensive fallback for runtime packaging
    CPRiskEvaluator = None

try:
    from analyzers.evaluators.trend_triple_gate import TrendTripleGate
except Exception:  # pragma: no cover - defensive fallback for runtime packaging
    TrendTripleGate = None

try:
    from analyzers.evaluators.prior_day_context_shadow import PriorDayContextShadowEvaluator
except Exception:  # pragma: no cover - defensive fallback for runtime packaging
    PriorDayContextShadowEvaluator = None

try:
    from analyzers.evaluators.prior_day_context_soft_score import PriorDayContextSoftScoreEvaluator
except Exception:  # pragma: no cover - defensive fallback for runtime packaging
    PriorDayContextSoftScoreEvaluator = None


class SignalShortlistBuilder:
    """Rank auction-time candidates and keep a bounded list per universe."""

    _PREOPEN_RELIABILITY_CACHE = None
    _TREND_GROUP_REGIME_CACHE = None
    _THEME_CLUSTER_STRENGTH_CACHE = None

    UNIVERSE_LIMITS = {
        "index": AuctionConfig.ACTION_TOPK_INDEX,
        "ETF": AuctionConfig.ACTION_TOPK_ETF,
        "stock": AuctionConfig.ACTION_TOPK_STOCK,
        "industry": AuctionConfig.ACTION_TOPK_INDUSTRY,
    }
    CATEGORY_MIN_SCORES = {
        "trap": AuctionConfig.ACTION_MIN_SCORE_TRAP,
        "reversal": AuctionConfig.ACTION_MIN_SCORE_REVERSAL,
        "trend": AuctionConfig.ACTION_MIN_SCORE_TREND,
    }
    CATEGORY_TOPK = {
        "trap": AuctionConfig.ACTION_TOPK_TRAP,
        "reversal": AuctionConfig.ACTION_TOPK_REVERSAL,
        "trend": AuctionConfig.ACTION_TOPK_TREND,
    }

    @classmethod
    def build(cls, signals, index_df=None, etf_df=None, prior_day_context=None):
        cls._PREOPEN_RELIABILITY_CACHE = None
        cls._TREND_GROUP_REGIME_CACHE = None
        cls._THEME_CLUSTER_STRENGTH_CACHE = None
        if LeadingClusterEvidenceBuilder is not None:
            LeadingClusterEvidenceBuilder.reset_cache()
        if CPRiskEvaluator is not None:
            CPRiskEvaluator.reset_cache()
        if TrendTripleGate is not None:
            TrendTripleGate.reset_cache()
        if PriorDayContextShadowEvaluator is not None:
            PriorDayContextShadowEvaluator.reset_cache()
        if PriorDayContextSoftScoreEvaluator is not None:
            PriorDayContextSoftScoreEvaluator.reset_cache()
        regime = cls.derive_regime(index_df, etf_df)
        shortlist = {category: [] for category in signals}
        scored_groups = {category: defaultdict(list) for category in signals}
        trend_observation = []
        trap_crowded_observation = []
        trap_exempted = []
        trend_coverage_context = cls._build_trend_coverage_context(signals.get("trend", []))

        for category, candidates in signals.items():
            grouped = defaultdict(list)
            for candidate in candidates:
                score, reasons, breakdown = cls.score(candidate, category, regime)
                candidate["action_score"] = round(score, 2)
                candidate["actionable"] = False
                candidate["shortlist_reason"] = "; ".join(reasons)
                candidate["action_score_breakdown"] = breakdown
                candidate["market_regime"] = regime["label"]
                candidate["market_regime_detail"] = regime
                cls._attach_leading_cluster_evidence(candidate)
                cp_risk_decision = "hard_trap"
                if category == "trap":
                    cp_risk_decision = cls._apply_cp_risk_evaluator(candidate, regime)
                trend_filter_decision = "keep"
                if category == "trend":
                    trend_filter_decision = cls._apply_trend_candidate_filter(
                        candidate,
                        regime,
                        trend_coverage_context,
                    )
                    cls._apply_trend_triple_gate_shadow(candidate, regime)
                    score = cls._number(candidate.get("action_score"), score)
                target_type = candidate.get("data", {}).get("target_type", "")
                scored_groups[category][target_type].append(candidate)
                if category == "trap" and cp_risk_decision in {"crowded_observe", "leading_cluster_exempt"}:
                    candidate["action_filter_reason"] = (
                        "cp_crowded_observe"
                        if cp_risk_decision == "crowded_observe"
                        else "cp_leading_cluster_exempt"
                    )
                    if cp_risk_decision == "crowded_observe":
                        trap_crowded_observation.append(candidate)
                    else:
                        trap_exempted.append(candidate)
                    continue
                if category == "trend" and trend_filter_decision in {"observe", "drop"}:
                    candidate["action_filter_reason"] = f"trend_filter_{trend_filter_decision}"
                    if trend_filter_decision == "observe":
                        trend_observation.append(candidate)
                    continue
                candidate["action_filter_reason"] = cls.filter_reason(candidate, category, score, regime)
                if not candidate["action_filter_reason"]:
                    grouped[target_type].append(candidate)

            for universe, items in grouped.items():
                limit = cls.UNIVERSE_LIMITS.get(universe, 0)
                selected = sorted(items, key=lambda item: item["action_score"], reverse=True)[:limit]
                shortlist[category].extend(selected)

            shortlist[category] = sorted(
                shortlist[category],
                key=lambda item: (
                    item.get("order", 9),
                    -item.get("action_score", 0),
                ),
            )[:cls.CATEGORY_TOPK.get(category, 0)]
            for rank, item in enumerate(shortlist[category], start=1):
                item["actionable"] = True
                item["action_filter_reason"] = "selected"
                item["action_rank"] = rank
                item["action_priority"] = (
                    "P0" if category == "trap" and rank <= AuctionConfig.ACTION_TRAP_HIGHLIGHT_TOP
                    else "P1"
                )

            for candidate in candidates:
                if not candidate["actionable"] and not candidate["action_filter_reason"]:
                    candidate["action_filter_reason"] = "topk_cutoff"

        shortlist["reversal_high_confidence"] = cls._build_high_confidence_reversal(
            signals.get("reversal", []),
            regime,
        )
        shortlist["reversal_observation"] = cls._build_observation_pool(
            signals.get("reversal", []),
            shortlisted=shortlist["reversal_high_confidence"],
            limit=AuctionConfig.ACTION_TOPK_REVERSAL,
            reason="reversal_observation_only",
            min_score=cls.CATEGORY_MIN_SCORES["reversal"],
        )
        shortlist["reversal"] = shortlist["reversal_high_confidence"]
        stock_trap_observation = cls._build_observation_pool(
            scored_groups.get("trap", {}).get("stock", []),
            shortlisted=shortlist.get("trap", []),
            limit=AuctionConfig.ACTION_TOPK_TRAP,
            reason="stock_trap_observation_only",
            min_score=cls.CATEGORY_MIN_SCORES["trap"],
        )
        shortlist["trap_observation"] = cls._merge_observation_pool(
            trap_crowded_observation,
            stock_trap_observation,
            limit=AuctionConfig.ACTION_TOPK_TRAP,
        )
        shortlist["trap_exempted"] = sorted(
            trap_exempted,
            key=lambda item: item.get("action_score", 0),
            reverse=True,
        )[: cls.CATEGORY_TOPK.get("trap", 0)]
        shortlist["trend_observation"] = sorted(
            trend_observation,
            key=lambda item: item.get("action_score", 0),
            reverse=True,
        )[: cls.CATEGORY_TOPK.get("trend", 0)]
        cls._apply_prior_day_context_shadow(signals, prior_day_context)
        cls._apply_prior_day_context_soft_score(signals, shortlist, prior_day_context)
        return shortlist, regime

    @classmethod
    def _attach_leading_cluster_evidence(cls, candidate):
        if LeadingClusterEvidenceBuilder is None:
            candidate.setdefault("leading_cluster_membership", False)
            candidate.setdefault("leading_cluster_name", "")
            candidate.setdefault("leading_cluster_rank", None)
            candidate.setdefault("leading_cluster_strength", None)
            candidate.setdefault("leading_cluster_evidence", [])
            candidate.setdefault("leading_cluster_missing_fields", ["leading_cluster_builder_unavailable"])
            candidate.setdefault("leading_cluster_risk_flags", [])
            candidate.setdefault("leading_cluster_status", "disabled")
            return
        try:
            LeadingClusterEvidenceBuilder.enrich_candidate(
                candidate,
                date_int=cls._extract_candidate_date(candidate),
            )
        except Exception:
            candidate.setdefault("leading_cluster_membership", False)
            candidate.setdefault("leading_cluster_name", "")
            candidate.setdefault("leading_cluster_rank", None)
            candidate.setdefault("leading_cluster_strength", None)
            candidate.setdefault("leading_cluster_evidence", [])
            candidate.setdefault("leading_cluster_missing_fields", ["leading_cluster_builder_error"])
            candidate.setdefault("leading_cluster_risk_flags", [])
            candidate.setdefault("leading_cluster_status", "disabled")

    @staticmethod
    def _extract_candidate_date(candidate):
        for value in (
            candidate.get("date_int"),
            candidate.get("trade_date"),
            candidate.get("date"),
            (candidate.get("data", {}) or {}).get("date_int"),
            (candidate.get("data", {}) or {}).get("trade_date"),
            (candidate.get("data", {}) or {}).get("date"),
        ):
            text = str(value or "").strip()
            digits = "".join(ch for ch in text if ch.isdigit())
            if len(digits) >= 8:
                return int(digits[:8])
        return None

    @classmethod
    def _apply_trend_candidate_filter(cls, candidate, regime, coverage_context):
        if TrendCandidateFilter is None:
            candidate.setdefault("trend_filter_decision", "keep")
            candidate.setdefault("trend_filter_status", "disabled")
            candidate.setdefault("trend_filter_context", coverage_context or {})
            candidate.setdefault("trend_filter_score", 0.0)
            candidate.setdefault("trend_filter_reasons", ["trend_filter_unavailable"])
            candidate.setdefault("trend_filter_risk_flags", [])
            candidate.setdefault("trend_filter_missing_fields", [])
            candidate.setdefault("trend_filter_invalid_conditions", [])
            return "keep"
        try:
            result = TrendCandidateFilter.evaluate_candidate(
                candidate,
                regime=regime,
                coverage_context=coverage_context,
            )
        except Exception:
            candidate.setdefault("trend_filter_decision", "keep")
            candidate.setdefault("trend_filter_status", "disabled")
            candidate.setdefault("trend_filter_context", coverage_context or {})
            candidate.setdefault("trend_filter_score", 0.0)
            candidate.setdefault("trend_filter_reasons", ["trend_filter_error_fallback"])
            candidate.setdefault("trend_filter_risk_flags", [])
            candidate.setdefault("trend_filter_missing_fields", [])
            candidate.setdefault("trend_filter_invalid_conditions", [])
            return "keep"

        adjustment = cls._number(result.get("score_adjustment"))
        candidate["action_score"] = round(cls._number(candidate.get("action_score")) + adjustment, 2)
        breakdown = candidate.get("action_score_breakdown", {}) or {}
        breakdown["trend_filter_adjustment"] = round(adjustment, 4)
        breakdown["final_score"] = round(cls._number(candidate.get("action_score")), 4)
        candidate["action_score_breakdown"] = breakdown
        return str(result.get("trend_filter_decision", "keep") or "keep")

    @classmethod
    def _apply_cp_risk_evaluator(cls, candidate, regime):
        if CPRiskEvaluator is None:
            candidate.setdefault("cp_risk_decision", "disabled")
            candidate.setdefault("cp_risk_score", 0.0)
            candidate.setdefault("cp_exempt_by_leading_cluster", False)
            candidate.setdefault("cp_risk_reasons", ["cp_risk_unavailable"])
            candidate.setdefault("cp_risk_flags", [])
            candidate.setdefault("cp_risk_missing_fields", [])
            candidate.setdefault("cp_risk_context", {})
            return "hard_trap"
        try:
            result = CPRiskEvaluator.evaluate_candidate(candidate, regime=regime)
        except Exception:
            candidate.setdefault("cp_risk_decision", "disabled")
            candidate.setdefault("cp_risk_score", 0.0)
            candidate.setdefault("cp_exempt_by_leading_cluster", False)
            candidate.setdefault("cp_risk_reasons", ["cp_risk_error_fallback"])
            candidate.setdefault("cp_risk_flags", [])
            candidate.setdefault("cp_risk_missing_fields", [])
            candidate.setdefault("cp_risk_context", {})
            return "hard_trap"

        candidate.update(result)
        return str(result.get("cp_risk_decision", "hard_trap") or "hard_trap")

    @classmethod
    def _apply_trend_triple_gate_shadow(cls, candidate, regime):
        if TrendTripleGate is None:
            candidate.setdefault("trend_gate_decision_shadow", "disabled")
            candidate.setdefault("trend_gate_score_shadow", 0.0)
            candidate.setdefault("trend_gate_reasons", ["trend_triple_gate_unavailable"])
            candidate.setdefault("trend_gate_risk_flags", [])
            candidate.setdefault("trend_gate_missing_fields", [])
            candidate.setdefault("trend_gate_context", {})
            return "disabled"
        try:
            result = TrendTripleGate.evaluate_shadow(candidate, regime=regime)
        except Exception:
            candidate.setdefault("trend_gate_decision_shadow", "disabled")
            candidate.setdefault("trend_gate_score_shadow", 0.0)
            candidate.setdefault("trend_gate_reasons", ["trend_triple_gate_error_fallback"])
            candidate.setdefault("trend_gate_risk_flags", [])
            candidate.setdefault("trend_gate_missing_fields", [])
            candidate.setdefault("trend_gate_context", {})
            return "disabled"
        candidate.update(result)
        return str(result.get("trend_gate_decision_shadow", "disabled") or "disabled")

    @classmethod
    def _build_trend_coverage_context(cls, candidates):
        if TrendCandidateFilter is None:
            return {
                "trend_total_count": len(list(candidates or [])),
                "rs_vs_etf_available_count": 0,
                "rs_vs_index_available_count": 0,
                "amount_1m_ratio_available_count": 0,
                "confirmation_coverage_count": 0,
                "confirmation_coverage_ratio": 0.0,
            }
        try:
            return TrendCandidateFilter.build_coverage_context(candidates)
        except Exception:
            return {
                "trend_total_count": len(list(candidates or [])),
                "rs_vs_etf_available_count": 0,
                "rs_vs_index_available_count": 0,
                "amount_1m_ratio_available_count": 0,
                "confirmation_coverage_count": 0,
                "confirmation_coverage_ratio": 0.0,
            }

    @classmethod
    def _apply_prior_day_context_shadow(cls, signals, prior_day_context):
        categories = [key for key in ("trap", "reversal", "trend") if key in (signals or {})]
        for category in categories:
            candidates = list((signals or {}).get(category, []) or [])
            if not candidates:
                continue
            baseline_order = sorted(
                candidates,
                key=lambda item: (-cls._number(item.get("action_score")), str(item.get("name", ""))),
            )
            baseline_rank = {id(item): idx for idx, item in enumerate(baseline_order, start=1)}
            for candidate in candidates:
                candidate["signal_category"] = category
                if PriorDayContextShadowEvaluator is None:
                    candidate.setdefault("prior_day_context_bonus_shadow", 0.0)
                    candidate.setdefault("prior_day_context_score_shadow", cls._number(candidate.get("action_score")))
                    candidate.setdefault("prior_day_context_rank_delta_shadow", 0)
                    candidate.setdefault("prior_day_context_reasons", ["prior_day_context_shadow_unavailable"])
                    candidate.setdefault("prior_day_context_flags", [])
                    candidate.setdefault("prior_day_context_confidence", "low")
                    continue
                try:
                    result = PriorDayContextShadowEvaluator.evaluate(candidate, prior_day_context)
                except Exception:
                    result = {
                        "prior_day_context_bonus_shadow": 0.0,
                        "prior_day_context_score_shadow": cls._number(candidate.get("action_score")),
                        "prior_day_context_rank_delta_shadow": 0,
                        "prior_day_context_reasons": ["prior_day_context_shadow_error_fallback"],
                        "prior_day_context_flags": [],
                        "prior_day_context_confidence": "low",
                    }
                candidate.update(result)

            shadow_order = sorted(
                candidates,
                key=lambda item: (
                    -cls._number(item.get("prior_day_context_score_shadow")),
                    -cls._number(item.get("action_score")),
                    str(item.get("name", "")),
                ),
            )
            shadow_rank = {id(item): idx for idx, item in enumerate(shadow_order, start=1)}
            for candidate in candidates:
                delta = baseline_rank.get(id(candidate), 0) - shadow_rank.get(id(candidate), 0)
                candidate["prior_day_context_rank_delta_shadow"] = int(delta)
    @classmethod
    def _apply_prior_day_context_soft_score(cls, signals, shortlist, prior_day_context):
        categories = [key for key in ("trap", "reversal", "trend") if key in (signals or {})]
        for category in categories:
            for candidate in list((signals or {}).get(category, []) or []):
                if "prior_day_context_bonus_shadow" not in candidate:
                    continue
                result = cls._evaluate_prior_day_context_soft_score(candidate, prior_day_context)
                candidate.update(result)
                cls._write_prior_day_context_soft_score(candidate, result)
        cls._resort_shortlist_after_prior_day_context(shortlist)

    @classmethod
    def _evaluate_prior_day_context_soft_score(cls, candidate, prior_day_context):
        if PriorDayContextSoftScoreEvaluator is None:
            base_score = cls._number(candidate.get("action_score"))
            return {
                "prior_day_context_bonus": 0.0,
                "prior_day_context_bonus_applied": False,
                "prior_day_context_bonus_capped": False,
                "prior_day_context_apply_mode": "disabled",
                "prior_day_context_score_before": round(base_score, 4),
                "prior_day_context_score_after": round(base_score, 4),
            }
        try:
            return PriorDayContextSoftScoreEvaluator.apply(candidate, prior_day_context)
        except Exception:
            base_score = cls._number(candidate.get("action_score"))
            return {
                "prior_day_context_bonus": 0.0,
                "prior_day_context_bonus_applied": False,
                "prior_day_context_bonus_capped": False,
                "prior_day_context_apply_mode": "disabled",
                "prior_day_context_score_before": round(base_score, 4),
                "prior_day_context_score_after": round(base_score, 4),
            }

    @classmethod
    def _write_prior_day_context_soft_score(cls, candidate, result):
        before_score = cls._number(result.get("prior_day_context_score_before"))
        after_score = cls._number(result.get("prior_day_context_score_after"))
        candidate["action_score"] = round(after_score, 2)
        breakdown = candidate.get("action_score_breakdown", {}) or {}
        breakdown["prior_day_context_bonus"] = round(cls._number(result.get("prior_day_context_bonus")), 4)
        breakdown["final_score"] = round(after_score, 4)
        candidate["action_score_breakdown"] = breakdown
        candidate.setdefault("prior_day_context_score_before", round(before_score, 4))
        candidate.setdefault("prior_day_context_score_after", round(after_score, 4))

    @classmethod
    def _resort_shortlist_after_prior_day_context(cls, shortlist):
        if not isinstance(shortlist, dict):
            return
        for category in ("trap", "trend", "reversal_high_confidence", "reversal_observation", "trap_observation", "trap_exempted", "trend_observation"):
            items = shortlist.get(category)
            if not isinstance(items, list) or not items:
                continue
            items.sort(
                key=lambda item: (
                    item.get("order", 9),
                    -cls._number(item.get("action_score")),
                    str(item.get("name", "")),
                )
            )
        shortlist["reversal"] = shortlist.get("reversal_high_confidence", [])
        for category in ("trap", "trend", "reversal"):
            items = shortlist.get(category)
            if not isinstance(items, list):
                continue
            for rank, item in enumerate(items, start=1):
                item["action_rank"] = rank
                item["action_priority"] = (
                    "P0" if category == "trap" and rank <= AuctionConfig.ACTION_TRAP_HIGHLIGHT_TOP
                    else "P1"
                )

    @classmethod
    def _build_observation_pool(cls, candidates, shortlisted, limit, reason, min_score=None):
        shortlisted_ids = {id(candidate) for candidate in shortlisted}
        observation = []
        for candidate in sorted(candidates, key=lambda item: item.get("action_score", 0), reverse=True):
            if id(candidate) in shortlisted_ids:
                continue
            if min_score is not None and candidate.get("action_score", 0) < min_score:
                continue
            candidate["actionable"] = False
            if not candidate.get("action_filter_reason") or candidate.get("action_filter_reason") == "topk_cutoff":
                candidate["action_filter_reason"] = reason
            observation.append(candidate)
            if len(observation) >= limit:
                break
        return observation

    @classmethod
    def _merge_observation_pool(cls, *pools, limit):
        merged = []
        seen = set()
        for pool in pools:
            for candidate in pool or []:
                key = id(candidate)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(candidate)
        merged.sort(key=lambda item: item.get("action_score", 0), reverse=True)
        return merged[:limit]

    @classmethod
    def _build_high_confidence_reversal(cls, candidates, regime):
        regime_label = cls._regime_label(regime)
        if regime_label not in AuctionConfig.ACTION_REVERSAL_HIGH_CONFIDENCE_REGIMES:
            return []
        if not cls._is_structural_repair_regime(regime):
            return []
        selected = []
        for candidate in candidates:
            data = candidate.get("data", {}) or {}
            if candidate.get("scenario") not in AuctionConfig.ACTION_REVERSAL_HIGH_CONFIDENCE_SCENARIOS:
                continue
            if data.get("target_type") not in AuctionConfig.ACTION_REVERSAL_HIGH_CONFIDENCE_UNIVERSES:
                continue
            if candidate.get("action_filter_reason") not in {"", "selected", "topk_cutoff"}:
                continue
            selected.append(candidate)
        selected = sorted(selected, key=lambda item: item.get("action_score", 0), reverse=True)
        selected = selected[:AuctionConfig.ACTION_TOPK_REVERSAL_HIGH_CONFIDENCE]
        for rank, candidate in enumerate(selected, start=1):
            candidate["reversal_layer"] = "high_confidence_structural_repair"
            candidate["reversal_layer_rank"] = rank
        return selected

    @classmethod
    def derive_regime(cls, index_df=None, etf_df=None):
        index_values = cls._auction_values(index_df)
        etf_values = cls._auction_values(etf_df)
        index_positive = cls._positive_ratio(index_values)
        etf_positive = cls._positive_ratio(etf_values)
        index_avg = cls._average(index_values)
        etf_avg = cls._average(etf_values)
        weak_index_states = cls._weak_index_state_count(index_df)

        if not index_values or not etf_values:
            label = "mixed"
        elif (
            index_avg <= AuctionConfig.ACTION_HOSTILE_INDEX_AVG_MAX
            and etf_avg <= AuctionConfig.ACTION_HOSTILE_ETF_AVG_MAX
            and index_positive <= AuctionConfig.ACTION_HOSTILE_INDEX_POSITIVE_MAX
            and etf_positive <= AuctionConfig.ACTION_HOSTILE_ETF_POSITIVE_MAX
            and weak_index_states >= 2
        ):
            label = "hostile"
        elif (
            index_avg >= AuctionConfig.ACTION_STRONG_REPAIR_INDEX_AVG_MIN
            and etf_avg >= AuctionConfig.ACTION_STRONG_REPAIR_ETF_AVG_MIN
            and index_positive >= AuctionConfig.ACTION_STRONG_REPAIR_INDEX_POSITIVE_MIN
            and etf_positive >= AuctionConfig.ACTION_STRONG_REPAIR_ETF_POSITIVE_MIN
            and weak_index_states >= AuctionConfig.ACTION_STRONG_REPAIR_WEAK_INDEX_STATES_MIN
        ):
            label = "strong_repair"
        elif index_avg <= -0.35 or (index_positive <= 0.25 and etf_positive <= 0.35):
            label = "risk_off"
        elif index_avg >= 0.20 and etf_positive >= 0.55:
            label = "continuation"
        elif index_avg < 0 and etf_positive >= 0.50:
            label = "repair"
        else:
            label = "mixed"

        structural_repair = cls._detect_structural_repair(index_df, etf_df, label)

        return {
            "label": label,
            "index_auction_avg": round(index_avg, 4),
            "index_positive_ratio": round(index_positive, 4),
            "etf_auction_avg": round(etf_avg, 4),
            "etf_positive_ratio": round(etf_positive, 4),
            "weak_index_state_count": weak_index_states,
            "structural_repair_detected": structural_repair["detected"],
            "structural_repair_score": structural_repair["score"],
            "structural_repair_flags": structural_repair["flags"],
            "reversal_preference": (
                "high_confidence_structural_repair"
                if structural_repair["detected"] and label == "risk_off"
                else "weak_reversal_observation"
                if label == "risk_off"
                else "default"
            ),
            "feature_timestamp": "auction",
        }

    @classmethod
    def score(cls, candidate, category, regime):
        regime_label = cls._regime_label(regime)
        data = candidate.get("data", {}) or {}
        auction_pct = cls._number(data.get("auction_pct"))
        prev_pct = cls._number(data.get("prev_pct"))
        prev_vol_ratio = cls._number(data.get("prev_vol_ratio"), 1.0)
        pos_5d = cls._number(data.get("pos_5d"), 50.0)
        rank = cls._number(candidate.get("amt_rank"), 999.0)
        rank_bonus = max(0.0, 18.0 - min(rank, 180.0) / 10.0)
        target_type = data.get("target_type", "")
        code = str(data.get("code", "") or "")
        group = str(
            data.get("group", "")
            or data.get("industry", "")
            or data.get("theme_cluster", "")
            or ""
        )
        reasons = [f"regime={regime_label}"]
        breakdown = {
            "base_score": 0.0,
            "rank_bonus": 0.0,
            "auction_bonus": 0.0,
            "prev_pct_bonus": 0.0,
            "prev_vol_bonus": 0.0,
            "position_bonus": 0.0,
            "regime_bonus": 0.0,
            "structural_bonus": 0.0,
            "theme_cluster_bonus": 0.0,
            "group_regime_bonus": 0.0,
            "confirmation_bonus": 0.0,
            "reliability_penalty": 0.0,
        }

        if category == "trap":
            cp_score = cls._number(candidate.get("cp"))
            if candidate.get("scenario") == "TRAP_OVERHEATED_ACCELERATION":
                cp_score = max(cp_score, AuctionConfig.CP_THRESHOLD)
                reasons.append("routed_from=overheated_trend")
            breakdown["base_score"] = cp_score
            breakdown["rank_bonus"] = rank_bonus
            breakdown["auction_bonus"] = max(0.0, auction_pct) * 3.0
            breakdown["position_bonus"] = max(0.0, pos_5d - 70.0) / 5.0
            breakdown["regime_bonus"] = cls._regime_bonus(category, regime_label, target_type)
            score = sum(breakdown.values())
            reasons.append(f"rank_bonus={rank_bonus:.1f}")
            reasons.append(f"cp={cls._number(candidate.get('cp')):.1f}")
        elif category == "reversal":
            breakdown["base_score"] = cls._number(candidate.get("sa"))
            breakdown["rank_bonus"] = rank_bonus
            breakdown["auction_bonus"] = min(abs(min(auction_pct, 0.0)), 3.0) * 4.0
            breakdown["prev_pct_bonus"] = max(0.0, -prev_pct) * 1.5
            breakdown["regime_bonus"] = cls._regime_bonus(category, regime_label, target_type)
            breakdown["structural_bonus"] = cls._structural_repair_bonus(category, regime, target_type)
            cluster_bonus, cluster_reasons = cls._theme_cluster_strength_adjustment(
                category=category,
                regime=regime_label,
                group=group,
                target_type=target_type,
            )
            breakdown["theme_cluster_bonus"] = cluster_bonus
            score = sum(breakdown.values())
            reasons.append(f"rank_bonus={rank_bonus:.1f}")
            reasons.append(f"sa={cls._number(candidate.get('sa')):.1f}")
            if breakdown["structural_bonus"]:
                reasons.append(f"structural_bonus={breakdown['structural_bonus']:.1f}")
            reasons.extend(cluster_reasons)
        else:
            breakdown["base_score"] = 30.0
            breakdown["prev_pct_bonus"] = max(0.0, prev_pct) * 3.0
            breakdown["prev_vol_bonus"] = max(0.0, prev_vol_ratio - 1.0) * 12.0
            breakdown["auction_bonus"] = -cls.trend_high_open_penalty(auction_pct)
            confirmation_bonus, confirmation_reasons = cls._trend_confirmation_adjustment(data)
            breakdown["confirmation_bonus"] = confirmation_bonus
            breakdown["regime_bonus"] = cls._regime_bonus(category, regime_label, target_type)
            reasons.append("rank_bonus=removed")
            reasons.append(f"prev_pct={prev_pct:.2f}")
            reasons.extend(confirmation_reasons)
            if auction_pct >= AuctionConfig.ACTION_TREND_HIGH_OPEN_PCT:
                reasons.append(f"high_open_penalty={cls.trend_high_open_penalty(auction_pct):.1f}")
            group_bonus, group_reasons = cls._trend_group_regime_adjustment(regime_label, group)
            breakdown["group_regime_bonus"] = group_bonus
            reasons.extend(group_reasons)
            cluster_bonus, cluster_reasons = cls._theme_cluster_strength_adjustment(
                category=category,
                regime=regime_label,
                group=group,
                target_type=target_type,
            )
            breakdown["theme_cluster_bonus"] = cluster_bonus
            score = sum(breakdown.values())
            reasons.extend(cluster_reasons)

        reliability_penalty, reliability_reasons = cls._preopen_reliability_adjustment(target_type, code)
        breakdown["reliability_penalty"] = -reliability_penalty
        score += breakdown["reliability_penalty"]
        reasons.extend(reliability_reasons)

        breakdown["final_score"] = round(score, 4)
        return score, reasons, breakdown

    @classmethod
    def is_eligible(cls, candidate, category, score):
        return not cls.filter_reason(candidate, category, score)

    @classmethod
    def filter_reason(cls, candidate, category, score, regime):
        regime_label = cls._regime_label(regime)
        data = candidate.get("data", {}) or {}
        auction_pct = cls._number(data.get("auction_pct"))
        target_type = data.get("target_type", "")
        rank = cls._number(candidate.get("amt_rank"), 999.0)

        if abs(auction_pct) > AuctionConfig.ACTION_MAX_ABS_AUCTION_PCT:
            return "extreme_auction_pct"
        if target_type == "stock" and rank > 100:
            return "stock_rank_gt_100"
        if category == "trap" and target_type == "stock":
            return "stock_trap_observation_only"
        if category == "trap" and candidate.get("scenario") not in AuctionConfig.ACTION_TRAP_SCENARIOS:
            return "trap_research_only_scenario"
        if category == "trend" and candidate.get("scenario") not in AuctionConfig.ACTION_TREND_SCENARIOS:
            return "trend_research_only_scenario"
        if category == "trend" and auction_pct < AuctionConfig.ACTION_TREND_MIN_AUCTION_PCT:
            return "trend_open_too_weak"
        if category == "trend" and cls.is_overheated_trend(data):
            return "trend_routed_to_cp"
        if regime_label in AuctionConfig.ACTION_BLOCKED_LONG_REGIMES and category in {"reversal", "trend"}:
            return "hostile_regime_block"
        if category == "reversal" and not cls.is_high_confidence_reversal(candidate, regime):
            return "reversal_observation_only"
        min_score = cls.CATEGORY_MIN_SCORES[category]
        if regime_label in AuctionConfig.ACTION_BLOCKED_LONG_REGIMES and category == "reversal":
            min_score = AuctionConfig.ACTION_MIN_SCORE_REVERSAL_HOSTILE
        if regime_label in AuctionConfig.ACTION_BLOCKED_LONG_REGIMES and category == "trend":
            min_score = AuctionConfig.ACTION_MIN_SCORE_TREND_HOSTILE
        if score < min_score:
            return "score_below_threshold"
        return ""

    @staticmethod
    def trend_high_open_penalty(auction_pct):
        if auction_pct < AuctionConfig.ACTION_TREND_HIGH_OPEN_PCT:
            return 0.0
        return (
            auction_pct - AuctionConfig.ACTION_TREND_HIGH_OPEN_PCT + 1.0
        ) * AuctionConfig.ACTION_TREND_HIGH_OPEN_PENALTY

    @staticmethod
    def is_overheated_trend(data):
        return (
            SignalShortlistBuilder._number(data.get("prev_pct")) >= AuctionConfig.ACTION_OVERHEATED_PREV_PCT
            and SignalShortlistBuilder._number(data.get("auction_pct")) >= AuctionConfig.ACTION_OVERHEATED_AUCTION_PCT
            and SignalShortlistBuilder._number(data.get("pos_5d"), 50.0) >= AuctionConfig.ACTION_OVERHEATED_POS_5D
        )

    @staticmethod
    def is_high_confidence_reversal(candidate, regime):
        regime_label = SignalShortlistBuilder._regime_label(regime)
        data = candidate.get("data", {}) or {}
        return (
            regime_label in AuctionConfig.ACTION_REVERSAL_HIGH_CONFIDENCE_REGIMES
            and SignalShortlistBuilder._is_structural_repair_regime(regime)
            and candidate.get("scenario") in AuctionConfig.ACTION_REVERSAL_HIGH_CONFIDENCE_SCENARIOS
            and data.get("target_type") in AuctionConfig.ACTION_REVERSAL_HIGH_CONFIDENCE_UNIVERSES
        )

    @staticmethod
    def _regime_label(regime):
        if isinstance(regime, dict):
            return str(regime.get("label", "") or "")
        return str(regime or "")

    @staticmethod
    def _is_structural_repair_regime(regime):
        return bool((regime or {}).get("structural_repair_detected")) if isinstance(regime, dict) else False

    @classmethod
    def _structural_repair_bonus(cls, category, regime, target_type):
        if category != "reversal":
            return 0.0
        if not cls._is_structural_repair_regime(regime):
            return 0.0
        if target_type not in {"index", "ETF"}:
            return 0.0
        return AuctionConfig.ACTION_RISK_OFF_STRUCTURAL_REPAIR_INDEX_ETF_BONUS

    @staticmethod
    def _regime_bonus(category, regime, target_type):
        matrix = {
            "hostile": {"trap": 8.0, "reversal": -30.0, "trend": -45.0},
            "strong_repair": {"trap": -10.0, "reversal": 2.0, "trend": 18.0},
            "continuation": {"trap": 0.0, "reversal": 0.0, "trend": 12.0},
            "repair": {"trap": -6.0, "reversal": 6.0, "trend": -8.0},
            "risk_off": {"trap": 6.0, "reversal": -10.0, "trend": -25.0},
            "mixed": {"trap": 0.0, "reversal": 0.0, "trend": 0.0},
        }
        bonus = matrix.get(regime, matrix["mixed"]).get(category, 0.0)
        if category == "trap" and target_type == "stock":
            bonus += getattr(AuctionConfig, "ACTION_TRAP_STOCK_REGIME_PENALTY", -10.0)
        if category == "trend" and regime == "repair" and target_type == "stock":
            bonus += getattr(AuctionConfig, "ACTION_TREND_REPAIR_STOCK_PENALTY", -8.0)
        if category == "trend" and regime == "strong_repair" and target_type == "stock":
            bonus += getattr(AuctionConfig, "ACTION_TREND_STRONG_REPAIR_STOCK_BONUS", 6.0)
        return bonus

    @classmethod
    def _trend_confirmation_adjustment(cls, data):
        confirmation = data.get("confirmation_data", {}) or {}
        timestamp = cls._number(confirmation.get("feature_timestamp"), 0.0)
        if timestamp < 935:
            return 0.0, []

        bias = str(confirmation.get("execution_bias", "") or "")
        price_vs_open = cls._number(confirmation.get("price_vs_open_pct"))
        rs_vs_etf = cls._number(confirmation.get("rs_vs_etf_pct"))
        rs_vs_index = cls._number(confirmation.get("rs_vs_index_pct"))
        amount_ratio = cls._number(confirmation.get("amount_1m_ratio"), float("nan"))
        relative_strength = max(rs_vs_etf, rs_vs_index)

        score = 0.0
        reasons = [f"confirm_ts={int(timestamp)}", f"confirm_bias={bias or 'missing'}"]
        if bias == "confirmed_strength":
            score += AuctionConfig.ACTION_TREND_CONFIRM_BIAS_BONUS
        else:
            score -= AuctionConfig.ACTION_TREND_CONFIRM_OBSERVE_PENALTY

        score += max(min(price_vs_open, 2.0), -2.0) * AuctionConfig.ACTION_TREND_CONFIRM_PRICE_WEIGHT
        score += max(min(relative_strength, 2.0), -2.0) * AuctionConfig.ACTION_TREND_CONFIRM_RS_WEIGHT
        if amount_ratio == amount_ratio:
            score += max(min(amount_ratio - 1.0, 1.5), -1.0) * AuctionConfig.ACTION_TREND_CONFIRM_AMOUNT_WEIGHT
            reasons.append(f"confirm_amt1m={amount_ratio:.2f}")
        reasons.append(f"confirm_open={price_vs_open:+.2f}")
        reasons.append(f"confirm_rs={relative_strength:+.2f}")
        return score, reasons

    @classmethod
    def _preopen_reliability_adjustment(cls, target_type, code):
        if target_type != "stock" or not code:
            return 0.0, []
        reliability = cls._load_preopen_reliability_map().get(code, {})
        action = str(reliability.get("preopen_signal_action", "") or "")
        if not action or action == "normal":
            return 0.0, []
        penalty_map = {
            "observe_auction_reliability": AuctionConfig.ACTION_PREOPEN_RELIABILITY_OBSERVE_PENALTY,
            "deprioritize_preopen_signal": AuctionConfig.ACTION_PREOPEN_RELIABILITY_DEPRIORITIZE_PENALTY,
            "exclude_from_0925_decision": AuctionConfig.ACTION_PREOPEN_RELIABILITY_EXCLUDE_PENALTY,
        }
        penalty = penalty_map.get(action, 0.0)
        days_missing = int(cls._number(reliability.get("days_missing"), 0))
        observed_days = int(cls._number(reliability.get("observed_days"), 0))
        missing_ratio = cls._number(reliability.get("missing_ratio"))
        reasons = [
            f"preopen_reliability={action}",
            f"preopen_missing={days_missing}/{observed_days or '?'}",
            f"preopen_missing_ratio={missing_ratio:.2f}",
        ]
        return penalty, reasons

    @classmethod
    def _theme_cluster_strength_adjustment(cls, category, regime, group, target_type):
        if category not in {"trend", "reversal"}:
            return 0.0, []
        if target_type not in {"stock", "industry"}:
            return 0.0, []
        if not group:
            return 0.0, []
        row = cls._load_theme_cluster_strength_map().get((regime, category, group))
        if not row:
            return 0.0, []

        sample_count = int(cls._number(row.get("sample_count"), 0))
        success_rate = cls._number(row.get("success_rate"))
        directed = cls._number(row.get("avg_directed_body_pct"))
        if sample_count < AuctionConfig.ACTION_THEME_CLUSTER_MIN_SAMPLE_COUNT:
            return 0.0, []

        baseline = (
            AuctionConfig.ACTION_THEME_CLUSTER_BASELINE_TREND
            if category == "trend"
            else AuctionConfig.ACTION_THEME_CLUSTER_BASELINE_REVERSAL
        )
        raw_signal = (
            max(min(directed, 2.5), -2.5) * AuctionConfig.ACTION_THEME_CLUSTER_DIRECTED_WEIGHT
            + max(min(success_rate - baseline, 30.0), -30.0) * AuctionConfig.ACTION_THEME_CLUSTER_HITRATE_WEIGHT
        )
        if category == "reversal" and regime == "risk_off":
            raw_signal += AuctionConfig.ACTION_THEME_CLUSTER_RISK_OFF_REVERSAL_BONUS
        bonus = max(
            -AuctionConfig.ACTION_THEME_CLUSTER_MAX_PENALTY,
            min(raw_signal, AuctionConfig.ACTION_THEME_CLUSTER_MAX_BONUS),
        )
        reasons = [
            f"theme_cluster={regime}/{category}/{group}",
            f"cluster_samples={sample_count}",
            f"cluster_hit={success_rate:.2f}",
            f"cluster_directed={directed:+.2f}",
        ]
        return bonus, reasons

    @classmethod
    def _trend_group_regime_adjustment(cls, regime, group):
        if not group:
            return 0.0, []
        row = cls._load_trend_group_regime_map().get((regime, group))
        if not row:
            return 0.0, []
        confirmed_count = int(cls._number(row.get("confirmed_count"), 0))
        confirmed_days = int(cls._number(row.get("confirmed_days"), 0))
        if (
            confirmed_count < AuctionConfig.ACTION_TREND_GROUP_REGIME_MIN_CONFIRMED_COUNT
            or confirmed_days < AuctionConfig.ACTION_TREND_GROUP_REGIME_MIN_CONFIRMED_DAYS
        ):
            return 0.0, []

        avg_open = cls._number(row.get("avg_price_vs_open_pct"))
        avg_rs = max(
            cls._number(row.get("avg_rs_vs_etf_pct")),
            cls._number(row.get("avg_rs_vs_index_pct")),
        )
        avg_amt = cls._number(row.get("avg_amount_1m_ratio"), 1.0)
        shortlisted_count = int(cls._number(row.get("shortlisted_count"), 0))
        signal = (
            max(min(avg_open, 2.0), -2.0) * 1.5
            + max(min(avg_rs, 2.0), -2.0) * 1.5
            + max(min(avg_amt - 1.0, 1.5), -1.0) * 2.0
        )
        if shortlisted_count <= 0:
            signal -= 1.0
        bonus = max(
            -AuctionConfig.ACTION_TREND_GROUP_REGIME_MAX_PENALTY,
            min(signal, AuctionConfig.ACTION_TREND_GROUP_REGIME_MAX_BONUS),
        )
        reasons = [
            f"group_regime={regime}/{group}",
            f"group_confirmed={confirmed_count}",
            f"group_days={confirmed_days}",
            f"group_open={avg_open:+.2f}",
            f"group_rs={avg_rs:+.2f}",
            f"group_amt={avg_amt:.2f}",
        ]
        return bonus, reasons

    @classmethod
    def _load_preopen_reliability_map(cls):
        if cls._PREOPEN_RELIABILITY_CACHE is not None:
            return cls._PREOPEN_RELIABILITY_CACHE
        path = os.path.join("reports", "validation", "stock_pool_auction_reliability.csv")
        if not os.path.exists(path):
            cls._PREOPEN_RELIABILITY_CACHE = {}
            return cls._PREOPEN_RELIABILITY_CACHE
        try:
            df = pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str})
        except Exception:
            cls._PREOPEN_RELIABILITY_CACHE = {}
            return cls._PREOPEN_RELIABILITY_CACHE
        if df.empty or "code" not in df.columns:
            cls._PREOPEN_RELIABILITY_CACHE = {}
            return cls._PREOPEN_RELIABILITY_CACHE
        cls._PREOPEN_RELIABILITY_CACHE = (
            df.fillna("")
            .assign(code=lambda x: x["code"].astype(str))
            .set_index("code")
            .to_dict(orient="index")
        )
        return cls._PREOPEN_RELIABILITY_CACHE

    @classmethod
    def _load_trend_group_regime_map(cls):
        if cls._TREND_GROUP_REGIME_CACHE is not None:
            return cls._TREND_GROUP_REGIME_CACHE
        path = os.path.join("reports", "validation", "confirmed_strength_regime_group_summary.csv")
        if not os.path.exists(path):
            cls._TREND_GROUP_REGIME_CACHE = {}
            return cls._TREND_GROUP_REGIME_CACHE
        try:
            df = pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            cls._TREND_GROUP_REGIME_CACHE = {}
            return cls._TREND_GROUP_REGIME_CACHE
        if df.empty or "market_regime" not in df.columns or "group" not in df.columns:
            cls._TREND_GROUP_REGIME_CACHE = {}
            return cls._TREND_GROUP_REGIME_CACHE
        work = df.fillna("").copy()
        work["market_regime"] = work["market_regime"].astype(str)
        work["group"] = work["group"].astype(str)
        cls._TREND_GROUP_REGIME_CACHE = {
            (row["market_regime"], row["group"]): row
            for row in work.to_dict(orient="records")
        }
        return cls._TREND_GROUP_REGIME_CACHE

    @classmethod
    def _load_theme_cluster_strength_map(cls):
        if cls._THEME_CLUSTER_STRENGTH_CACHE is not None:
            return cls._THEME_CLUSTER_STRENGTH_CACHE
        root = os.path.join("reports", "analysis", "regime_cluster")
        path = ""
        if os.path.isdir(root):
            subdirs = sorted(
                [name for name in os.listdir(root) if os.path.isdir(os.path.join(root, name))]
            )
            for name in reversed(subdirs):
                candidate = os.path.join(root, name, "regime_cluster_summary.csv")
                if os.path.exists(candidate):
                    path = candidate
                    break
        if not path or not os.path.exists(path):
            cls._THEME_CLUSTER_STRENGTH_CACHE = {}
            return cls._THEME_CLUSTER_STRENGTH_CACHE
        try:
            df = pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            cls._THEME_CLUSTER_STRENGTH_CACHE = {}
            return cls._THEME_CLUSTER_STRENGTH_CACHE
        required = {"market_regime", "signal_category", "leading_clusters"}
        if df.empty or not required.issubset(df.columns):
            cls._THEME_CLUSTER_STRENGTH_CACHE = {}
            return cls._THEME_CLUSTER_STRENGTH_CACHE
        work = df.fillna("").copy()
        work["market_regime"] = work["market_regime"].astype(str)
        work["signal_category"] = work["signal_category"].astype(str)
        work["leading_clusters"] = work["leading_clusters"].astype(str)
        cls._THEME_CLUSTER_STRENGTH_CACHE = {
            (row["market_regime"], row["signal_category"], row["leading_clusters"]): row
            for row in work.to_dict(orient="records")
        }
        return cls._THEME_CLUSTER_STRENGTH_CACHE

    @classmethod
    def _auction_values(cls, df):
        if df is None or df.empty or "_data" not in df.columns:
            return []
        values = []
        for data in df["_data"]:
            if isinstance(data, dict):
                values.append(cls._number(data.get("auction_pct")))
        return values

    @staticmethod
    def _positive_ratio(values):
        return sum(value > 0 for value in values) / len(values) if values else 0.0

    @staticmethod
    def _average(values):
        return sum(values) / len(values) if values else 0.0

    @classmethod
    def _weak_index_state_count(cls, df):
        if df is None or df.empty or "_data" not in df.columns:
            return 0
        weak = 0
        weak_states = set(AuctionConfig.ACTION_HOSTILE_WEAK_INDEX_STATES)
        for data in df["_data"]:
            if not isinstance(data, dict):
                continue
            trend_state = str(data.get("trend_state", "") or "")
            if trend_state in weak_states:
                weak += 1
        return weak

    @classmethod
    def _detect_structural_repair(cls, index_df, etf_df, regime_label):
        result = {"detected": False, "score": 0, "flags": []}
        if regime_label != "risk_off":
            return result

        index_records = cls._factor_records(index_df)
        etf_records = cls._factor_records(etf_df)
        if not index_records or not etf_records:
            return result

        growth_repair = cls._growth_index_repair(index_records)
        if growth_repair:
            result["score"] += 1
            result["flags"].append("growth_index_repair")

        semiconductor_repair = cls._theme_repair(
            etf_records,
            keywords=("半导体设备", "半导体", "芯片", "科创50ETF"),
        )
        if semiconductor_repair:
            result["score"] += 1
            result["flags"].append("semiconductor_repair")

        resource_repair = cls._theme_repair(
            etf_records,
            keywords=("工业有色", "稀有金属", "贵金属", "有色", "资源"),
        )
        if resource_repair:
            result["score"] += 1
            result["flags"].append("resource_repair")

        concentrated = cls._positive_theme_concentration(etf_records)
        if concentrated:
            result["score"] += 1
            result["flags"].append("concentrated_positive_themes")

        result["detected"] = growth_repair and concentrated and (semiconductor_repair or resource_repair)
        return result

    @classmethod
    def _factor_records(cls, df):
        if df is None or df.empty:
            return []
        records = []
        if "_data" in df.columns:
            iterator = df.to_dict(orient="records")
            for row in iterator:
                data = row.get("_data")
                if not isinstance(data, dict):
                    continue
                merged = dict(data)
                for key in ("name", "group", "theme_cluster", "code"):
                    if not merged.get(key) and row.get(key):
                        merged[key] = row.get(key)
                records.append(merged)
            return records
        return df.to_dict(orient="records")

    @classmethod
    def _theme_repair(cls, records, keywords):
        threshold_body = AuctionConfig.ACTION_RISK_OFF_STRUCTURAL_REPAIR_THEME_MIN_BODY
        threshold_close = AuctionConfig.ACTION_RISK_OFF_STRUCTURAL_REPAIR_THEME_MIN_CLOSE
        matched = 0
        for record in records:
            name = str(record.get("name", "") or "")
            if not any(keyword in name for keyword in keywords):
                continue
            body_pct = cls._number(record.get("body_pct"))
            close_pct = cls._number(record.get("close_pct"))
            if body_pct >= threshold_body or close_pct >= threshold_close:
                matched += 1
        return matched >= 1

    @classmethod
    def _growth_index_repair(cls, records):
        threshold_body = AuctionConfig.ACTION_RISK_OFF_STRUCTURAL_REPAIR_GROWTH_MIN_BODY
        threshold_close = AuctionConfig.ACTION_RISK_OFF_STRUCTURAL_REPAIR_GROWTH_MIN_CLOSE
        matched = 0
        for record in records:
            name = str(record.get("name", "") or "")
            if not any(keyword in name for keyword in ("创业板", "科创50")):
                continue
            body_pct = cls._number(record.get("body_pct"))
            close_pct = cls._number(record.get("close_pct"))
            if body_pct >= threshold_body or close_pct >= threshold_close:
                matched += 1
        return matched >= 1

    @classmethod
    def _positive_theme_concentration(cls, records):
        positive = []
        for record in records:
            body_pct = cls._number(record.get("body_pct"))
            close_pct = cls._number(record.get("close_pct"))
            strength = max(body_pct, close_pct)
            if strength <= 0:
                continue
            name = str(record.get("name", "") or "")
            positive.append((name, strength))
        if len(positive) < AuctionConfig.ACTION_RISK_OFF_STRUCTURAL_REPAIR_THEME_COUNT_MIN:
            return False
        positive.sort(key=lambda item: item[1], reverse=True)
        top_strength = sum(value for _, value in positive[:3])
        total_strength = sum(value for _, value in positive)
        if total_strength <= 0:
            return False
        return (top_strength / total_strength) >= AuctionConfig.ACTION_RISK_OFF_STRUCTURAL_REPAIR_POSITIVE_SHARE_MIN

    @staticmethod
    def _number(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
