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
            insufficient_reasons = []
            if confidence == "low":
                insufficient_reasons.append("feature_confidence_low")
            if trend_count < 8:
                insufficient_reasons.append("trend_sample_count_below_8")
            if path_count < 8:
                insufficient_reasons.append("path_sample_count_below_8")
            return cls._result(
                "data_insufficient",
                baseline,
                features,
                [],
                False,
                contradiction_evidence_usable=False,
                insufficient_reasons=insufficient_reasons,
            )

        broad_failure_status = cls.broad_failure_status(features)
        risk_evidence = broad_failure_status["risk_evidence"]
        broad_failure = broad_failure_status["broad_failure"]

        concentration = cls.cluster_concentration_status(features)
        concentrated = concentration["concentrated"]

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
        return cls._result(label, baseline, features, risk_evidence, broad_failure)

    @classmethod
    def broad_failure_status(cls, features: dict | None) -> dict:
        features = features or {}
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
        return {
            "risk_evidence": risk_evidence,
            "evidence_count": len(risk_evidence),
            "broad_failure": broad_failure,
        }

    @classmethod
    def cluster_concentration_status(cls, features: dict | None) -> dict:
        features = features or {}
        try:
            denominator = int(cls._number(features.get("cluster_positive_denominator"), 0) or 0)
        except (TypeError, ValueError, OverflowError):
            denominator = 0
        label = str(features.get("cluster_concentration_label", "") or "")
        top1 = cls._number(features.get("cluster_top1_positive_share"), 0)
        top3 = cls._number(features.get("cluster_top3_positive_share"), 0)
        usable = denominator >= 3 and label == "concentrated"
        concentrated = usable and (top1 >= 0.35 or top3 >= 0.65)
        if denominator < 3:
            reason = "insufficient_positive_cluster_samples"
        elif label != "concentrated":
            reason = "cluster_label_not_concentrated"
        elif concentrated:
            reason = "share_threshold_confirmed"
        else:
            reason = "share_threshold_not_met"
        return {
            "usable": usable,
            "concentrated": concentrated,
            "denominator": denominator,
            "reason": reason,
        }

    @classmethod
    def _result(
        cls,
        label,
        baseline,
        features,
        risk_evidence,
        broad_failure,
        contradiction_evidence_usable=True,
        insufficient_reasons=None,
    ):
        concentration = cls.cluster_concentration_status(features)
        concentrated = concentration["concentrated"]
        contradictions = []
        if contradiction_evidence_usable:
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
            "cluster_positive_denominator": concentration["denominator"],
            "cluster_concentration_usable": concentration["usable"],
            "cluster_concentration_evidence": concentrated,
            "cluster_concentration_reason": concentration["reason"],
            "risk_evidence": risk_evidence,
            "contradiction_labels": contradictions,
            "contradiction_evidence_usable": contradiction_evidence_usable,
            "insufficient_reasons": list(insufficient_reasons or []),
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
