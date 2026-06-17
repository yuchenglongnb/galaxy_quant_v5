# -*- coding: utf-8 -*-
"""Build normalized leading-cluster evidence from iFinD overlay artifacts."""

from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path

import pandas as pd

from config.settings import DBConfig
from providers.ifind_theme_provider import IFindThemeProvider


class LeadingClusterEvidenceBuilder:
    """Convert iFinD overlay artifacts into stable internal evidence fields."""

    CONFIG_PATH = (
        Path(__file__).resolve().parents[2]
        / "reports"
        / "analysis"
        / "configs"
        / "leading_cluster_config.json"
    )

    _CONFIG_CACHE = None
    _OVERLAY_CACHE = None
    _SECTOR_CACHE = None
    _CATALYST_CACHE = None
    _CLUSTER_RANK_CACHE = None

    DEFAULT_CONFIG = {
        "enabled": True,
        "ifind_cluster_alias": {},
        "cluster_priority": [],
        "min_sector_strength_for_active": 60.0,
        "min_sector_return_pct_for_active": 3.0,
        "min_catalyst_count_for_bonus": 1,
        "stale_days": 3,
    }

    @classmethod
    def load_config(cls):
        if cls._CONFIG_CACHE is not None:
            return deepcopy(cls._CONFIG_CACHE)
        config = deepcopy(cls.DEFAULT_CONFIG)
        try:
            with cls.CONFIG_PATH.open("r", encoding="utf-8") as fh:
                external = json.load(fh)
            config.update(external)
        except (OSError, ValueError, TypeError):
            pass
        cls._CONFIG_CACHE = config
        return deepcopy(config)

    @classmethod
    def reset_cache(cls):
        cls._CONFIG_CACHE = None
        cls._OVERLAY_CACHE = None
        cls._SECTOR_CACHE = None
        cls._CATALYST_CACHE = None
        cls._CLUSTER_RANK_CACHE = None

    @classmethod
    def evaluate_candidate(cls, candidate):
        config = cls.load_config()
        result = cls._empty_result()
        if not config.get("enabled", True):
            result["leading_cluster_status"] = "disabled"
            return result

        data = candidate.get("data", {}) or {}
        breakdown = candidate.get("action_score_breakdown", {}) or {}
        code = str(data.get("code", "") or "")
        name = str(candidate.get("name", "") or data.get("name", "") or "")
        if not code:
            result["leading_cluster_missing_fields"].append("missing_code")
            return result

        overlay = cls._load_overlay_map().get(code)
        if not overlay:
            result["leading_cluster_status"] = "missing_ifind_overlay"
            result["leading_cluster_missing_fields"].append("missing_ifind_overlay")
            cls._apply_existing_breakdown_evidence(result, breakdown)
            cls._apply_market_risk_flags(result, data)
            return cls._finalize(result)

        concepts = cls._split_items(overlay.get("ifind_signal_concepts", ""))
        if not concepts:
            result["leading_cluster_status"] = "partial"
            result["leading_cluster_missing_fields"].append("missing_ifind_signal_concepts")
        result["ifind_theme_coverage"] = True
        result["ifind_signal_concepts"] = concepts
        result["ifind_primary_concept"] = ""
        result["ifind_cluster"] = ""
        result["ifind_catalyst_count"] = 0
        result["ifind_catalyst_summary"] = ""

        stale_days = int(cls._number(config.get("stale_days"), 3))
        snapshot_age_days = cls._snapshot_age_days(overlay.get("ifind_updated_at", ""))
        if snapshot_age_days is not None:
            result["ifind_snapshot_age_days"] = snapshot_age_days
        if snapshot_age_days is not None and snapshot_age_days > stale_days:
            result["leading_cluster_status"] = "stale_ifind_snapshot"
            result["leading_cluster_risk_flags"].append("stale_ifind_snapshot")

        cluster_candidates = cls._build_cluster_candidates(concepts, config)
        sector_map = cls._load_sector_strength_map()
        cluster_scores = cls._compute_cluster_scores(cluster_candidates, sector_map, config)
        primary_cluster = cls._pick_primary_cluster(cluster_scores, config)

        if primary_cluster:
            result["ifind_primary_concept"] = primary_cluster.get("concept", "")
            result["ifind_cluster"] = primary_cluster.get("cluster", "")
            result["leading_cluster_name"] = primary_cluster.get("cluster", "")
            result["leading_cluster_strength"] = round(cls._number(primary_cluster.get("strength")), 4)
            result["leading_cluster_rank"] = cls._cluster_rank(result["leading_cluster_name"])
            result["leading_cluster_membership"] = True
            result["leading_cluster_evidence"].append("ifind_theme_match")
            if primary_cluster.get("sector_confirmed"):
                result["leading_cluster_evidence"].append("ifind_sector_strength_confirmed")
            else:
                result["leading_cluster_missing_fields"].append("missing_sector_strength")
                if result["leading_cluster_status"] not in {"stale_ifind_snapshot"}:
                    result["leading_cluster_status"] = "missing_sector_strength"

        catalyst = cls._load_catalyst_map().get(code) or {}
        catalyst_count = int(cls._number(catalyst.get("count"), 0))
        result["ifind_catalyst_count"] = catalyst_count
        result["ifind_catalyst_summary"] = str(catalyst.get("summary", "") or "")
        if catalyst_count >= int(cls._number(config.get("min_catalyst_count_for_bonus"), 1)):
            result["leading_cluster_evidence"].append("ifind_catalyst_confirmed")

        cls._apply_existing_breakdown_evidence(result, breakdown)
        cls._apply_market_risk_flags(result, data)

        if result["leading_cluster_status"] not in {"stale_ifind_snapshot", "missing_ifind_overlay"}:
            if result["leading_cluster_membership"] and result["leading_cluster_strength"] is not None:
                if cls._number(result["leading_cluster_strength"]) >= cls._number(config.get("min_sector_strength_for_active"), 60.0):
                    result["leading_cluster_status"] = "active"
                elif result["leading_cluster_status"] == "":
                    result["leading_cluster_status"] = "partial"
            elif result["leading_cluster_status"] == "":
                result["leading_cluster_status"] = "partial"

        return cls._finalize(result)

    @classmethod
    def enrich_candidate(cls, candidate):
        result = cls.evaluate_candidate(candidate)
        candidate.update(result)
        return result

    @classmethod
    def _empty_result(cls):
        return {
            "ifind_theme_coverage": False,
            "ifind_signal_concepts": [],
            "ifind_primary_concept": "",
            "ifind_cluster": "",
            "ifind_catalyst_count": 0,
            "ifind_catalyst_summary": "",
            "ifind_snapshot_age_days": None,
            "leading_cluster_membership": False,
            "leading_cluster_name": "",
            "leading_cluster_rank": None,
            "leading_cluster_strength": None,
            "leading_cluster_evidence": [],
            "leading_cluster_missing_fields": [],
            "leading_cluster_risk_flags": [],
            "leading_cluster_status": "",
        }

    @classmethod
    def _build_cluster_candidates(cls, concepts, config):
        alias_map = config.get("ifind_cluster_alias", {}) or {}
        rows = []
        for concept in concepts:
            cluster = str(alias_map.get(concept, "") or "")
            if not cluster:
                continue
            rows.append({"concept": concept, "cluster": cluster})
        return rows

    @classmethod
    def _compute_cluster_scores(cls, cluster_candidates, sector_map, config):
        rows = []
        for item in cluster_candidates:
            concept = item["concept"]
            cluster = item["cluster"]
            sector = sector_map.get(concept, {})
            avg_return = cls._number(sector.get("avg_return_pct"))
            amount = cls._number(sector.get("amount_yuan"))
            member_count = cls._number(sector.get("member_count"))
            sector_confirmed = bool(sector)
            strength = cls._strength_score(avg_return, amount, member_count)
            if sector_confirmed and avg_return < cls._number(config.get("min_sector_return_pct_for_active"), 3.0):
                strength = min(strength, 59.0)
            rows.append(
                {
                    "concept": concept,
                    "cluster": cluster,
                    "avg_return_pct": avg_return,
                    "amount_yuan": amount,
                    "member_count": member_count,
                    "sector_confirmed": sector_confirmed,
                    "strength": strength,
                }
            )
        return rows

    @classmethod
    def _pick_primary_cluster(cls, cluster_scores, config):
        if not cluster_scores:
            return None
        priority = {name: idx for idx, name in enumerate(config.get("cluster_priority", []) or [])}
        return sorted(
            cluster_scores,
            key=lambda row: (
                -cls._number(row.get("strength")),
                priority.get(row.get("cluster", ""), 999),
                row.get("concept", ""),
            ),
        )[0]

    @classmethod
    def _cluster_rank(cls, cluster_name):
        if not cluster_name:
            return None
        return cls._load_cluster_rank_map().get(cluster_name)

    @classmethod
    def _apply_existing_breakdown_evidence(cls, result, breakdown):
        if cls._number(breakdown.get("theme_cluster_bonus")) > 0:
            result["leading_cluster_evidence"].append("existing_theme_cluster_bonus")
        if cls._number(breakdown.get("group_regime_bonus")) > 0:
            result["leading_cluster_evidence"].append("existing_group_regime_bonus")

    @classmethod
    def _apply_market_risk_flags(cls, result, data):
        rs_vs_etf = cls._nested_number(data, "confirmation_data", "rs_vs_etf_pct")
        rs_vs_index = cls._nested_number(data, "confirmation_data", "rs_vs_index_pct")
        amount_ratio = cls._nested_number(data, "confirmation_data", "amount_1m_ratio")
        if rs_vs_etf < 0:
            result["leading_cluster_risk_flags"].append("weak_vs_etf")
        if rs_vs_index < 0:
            result["leading_cluster_risk_flags"].append("weak_vs_index")
        if amount_ratio == amount_ratio and amount_ratio < 1.0:
            result["leading_cluster_risk_flags"].append("amount_not_confirmed")

    @classmethod
    def _finalize(cls, result):
        for key in ("leading_cluster_evidence", "leading_cluster_missing_fields", "leading_cluster_risk_flags"):
            result[key] = cls._dedupe(result.get(key, []))
        if not result.get("leading_cluster_status"):
            result["leading_cluster_status"] = "partial"
        return result

    @classmethod
    def _load_overlay_map(cls):
        if cls._OVERLAY_CACHE is not None:
            return cls._OVERLAY_CACHE
        provider = IFindThemeProvider()
        overlay = provider.load_overlay()
        if overlay.empty:
            cls._OVERLAY_CACHE = {}
        else:
            cls._OVERLAY_CACHE = overlay.fillna("").set_index("code").to_dict(orient="index")
        return cls._OVERLAY_CACHE

    @classmethod
    def _load_sector_strength_map(cls):
        if cls._SECTOR_CACHE is not None:
            return cls._SECTOR_CACHE
        path = cls._latest_ifind_file("sector_strength_snapshot.csv")
        if not path or not path.exists():
            cls._SECTOR_CACHE = {}
            return cls._SECTOR_CACHE
        try:
            df = pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            cls._SECTOR_CACHE = {}
            return cls._SECTOR_CACHE
        if df.empty or "concept" not in df.columns:
            cls._SECTOR_CACHE = {}
            return cls._SECTOR_CACHE
        cls._SECTOR_CACHE = df.fillna("").set_index("concept").to_dict(orient="index")
        return cls._SECTOR_CACHE

    @classmethod
    def _load_catalyst_map(cls):
        if cls._CATALYST_CACHE is not None:
            return cls._CATALYST_CACHE
        path = cls._latest_ifind_file("catalyst_notice_digest.csv")
        if not path or not path.exists():
            cls._CATALYST_CACHE = {}
            return cls._CATALYST_CACHE
        try:
            df = pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str})
        except Exception:
            cls._CATALYST_CACHE = {}
            return cls._CATALYST_CACHE
        if df.empty or "code" not in df.columns:
            cls._CATALYST_CACHE = {}
            return cls._CATALYST_CACHE
        grouped = (
            df.fillna("")
            .groupby("code", as_index=False)
            .agg(
                count=("code", "count"),
                summary=("summary", lambda s: " | ".join(x for x in map(str, s) if x)),
            )
        )
        cls._CATALYST_CACHE = grouped.set_index("code").to_dict(orient="index")
        return cls._CATALYST_CACHE

    @classmethod
    def _load_cluster_rank_map(cls):
        if cls._CLUSTER_RANK_CACHE is not None:
            return cls._CLUSTER_RANK_CACHE
        sector_map = cls._load_sector_strength_map()
        config = cls.load_config()
        cluster_scores = {}
        alias_map = config.get("ifind_cluster_alias", {}) or {}
        for concept, row in sector_map.items():
            cluster = alias_map.get(concept)
            if not cluster:
                continue
            strength = cls._strength_score(
                cls._number(row.get("avg_return_pct")),
                cls._number(row.get("amount_yuan")),
                cls._number(row.get("member_count")),
            )
            cluster_scores[cluster] = max(strength, cluster_scores.get(cluster, float("-inf")))
        ordered = sorted(cluster_scores.items(), key=lambda item: (-item[1], item[0]))
        cls._CLUSTER_RANK_CACHE = {name: idx for idx, (name, _score) in enumerate(ordered, start=1)}
        return cls._CLUSTER_RANK_CACHE

    @staticmethod
    def _latest_ifind_file(filename):
        root = Path(DBConfig.STORE_PATH)
        if not root.exists():
            return None
        days = sorted(
            [path for path in root.iterdir() if path.is_dir() and path.name.isdigit() and len(path.name) == 8],
            reverse=True,
        )
        for day in days:
            candidate = day / "ifind" / filename
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    def _split_items(value):
        if pd.isna(value):
            return []
        text = str(value).strip()
        if not text:
            return []
        return [item.strip() for item in text.split(";") if item.strip()]

    @staticmethod
    def _strength_score(avg_return_pct, amount_yuan, member_count):
        avg_return_pct = LeadingClusterEvidenceBuilder._number(avg_return_pct)
        amount_yuan = LeadingClusterEvidenceBuilder._number(amount_yuan)
        member_count = LeadingClusterEvidenceBuilder._number(member_count)
        amount_term = 0.0
        if amount_yuan > 0:
            amount_term = min(math.log10(amount_yuan) - 9.0, 3.0) * 8.0
        breadth_term = min(member_count / 50.0, 2.0) * 4.0 if member_count > 0 else 0.0
        return max(0.0, min(avg_return_pct * 8.0 + amount_term + breadth_term, 100.0))

    @staticmethod
    def _snapshot_age_days(value):
        text = str(value or "").strip()
        if not text:
            return None
        try:
            ts = pd.Timestamp(text)
        except Exception:
            return None
        now = pd.Timestamp.now()
        delta = now.normalize() - ts.normalize()
        return int(delta.days)

    @staticmethod
    def _number(value, default=0.0):
        try:
            if value is None or value == "":
                return default
            if isinstance(value, str):
                text = value.strip().replace(",", "")
                if not text:
                    return default
                return float(text)
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _nested_number(data, nested_key, field):
        nested = data.get(nested_key, {}) or {}
        value = nested.get(field)
        return LeadingClusterEvidenceBuilder._number(value, float("nan"))

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
