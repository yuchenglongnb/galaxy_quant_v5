"""Observation-only state transition classification."""

from __future__ import annotations


class StateTransitionShadow:
    """Compare the active environment gate with prior-day outcome evidence."""

    THRESHOLD_STATUS = "analysis_only_shadow_threshold"

    @classmethod
    def evaluate(cls, baseline_gate: dict | None, features: dict | None) -> dict:
        baseline = baseline_gate or {}
        features = features or {}
        confidence = str(features.get("feature_confidence", "low") or "low")
        trend_count = cls._number(features.get("prior_trend_sample_count"), 0)
        path_count = cls._number(features.get("path_available_count"), 0)
        if confidence == "low" or trend_count < 8 or path_count < 8:
            return cls._result("data_insufficient", baseline, features, [], False, False)

        risk_evidence = []
        if cls._lt(features.get("prior_trend_success_rate"), 45):
            risk_evidence.append("prior_trend_success_rate_below_45")
        if cls._lt(features.get("prior_trend_avg_body"), 0):
            risk_evidence.append("prior_trend_avg_body_negative")
        if cls._ge(features.get("broad_path_risk_ratio"), 0.40):
            risk_evidence.append("broad_path_risk_ratio_at_least_40pct")
        if cls._ge(features.get("one_way_selloff_ratio"), 0.20):
            risk_evidence.append("one_way_selloff_ratio_at_least_20pct")
        broad_failure = len(risk_evidence) >= 2
        concentrated = cls._ge(features.get("cluster_top1_positive_share"), 0.35) or cls._ge(
            features.get("cluster_top3_positive_share"), 0.65
        )

        supported = (
            cls._ge(features.get("prior_trend_success_rate"), 55)
            and cls._gt(features.get("prior_trend_avg_body"), 0)
            and cls._lt(features.get("broad_path_risk_ratio"), 0.30)
        )
        baseline_label = str(baseline.get("label", "") or "")
        if supported:
            label = "broad_continuation_supported"
        elif broad_failure and concentrated:
            label = "rotational_repair_with_broad_trend_failure_risk"
        elif broad_failure and baseline_label == "continuation":
            label = "weak_continuation"
        elif broad_failure:
            label = "broad_trend_failure_risk"
        else:
            label = "mixed_wait_confirmation"
        return cls._result(label, baseline, features, risk_evidence, broad_failure, concentrated)

    @classmethod
    def _result(cls, label, baseline, features, risk_evidence, broad_failure, concentrated):
        contradictions = []
        if str(baseline.get("decision", "")) == "trend_enabled" and broad_failure:
            contradictions.append("baseline_trend_enabled_but_broad_trend_failed")
        if str(baseline.get("label", "")) == "continuation" and cls._lt(
            features.get("prior_trend_avg_body"), 0
        ):
            contradictions.append("continuation_but_negative_trend_body")
        if broad_failure and concentrated:
            contradictions.append("broad_failure_but_cluster_repair")
        return {
            "label": label,
            "observation_only": True,
            "threshold_status": cls.THRESHOLD_STATUS,
            "not_active_strategy_rule": True,
            "baseline_label": str(baseline.get("label", "") or ""),
            "baseline_decision": str(baseline.get("decision", "") or ""),
            "broad_trend_failure_risk": broad_failure,
            "cluster_concentration_evidence": concentrated,
            "risk_evidence": risk_evidence,
            "contradiction_labels": contradictions,
            "feature_confidence": features.get("feature_confidence", "low"),
        }

    @staticmethod
    def _number(value, default=None):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _lt(cls, value, limit):
        number = cls._number(value)
        return number is not None and number < limit

    @classmethod
    def _gt(cls, value, limit):
        number = cls._number(value)
        return number is not None and number > limit

    @classmethod
    def _ge(cls, value, limit):
        number = cls._number(value)
        return number is not None and number >= limit
