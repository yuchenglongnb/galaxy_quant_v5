# -*- coding: utf-8 -*-
"""Build normalized leading-cluster evidence from local iFinD artifacts."""

from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path

import pandas as pd

from config.settings import DBConfig
from providers.ifind_theme_provider import IFindThemeProvider


class LeadingClusterEvidenceBuilder:
    """Convert local iFinD artifacts into stable internal evidence fields."""

    CONFIG_PATH = (
        Path(__file__).resolve().parents[2]
        / "reports"
        / "analysis"
        / "configs"
        / "leading_cluster_config.json"
    )

    _CONFIG_CACHE = None
    _FRAME_CACHE = {}
    _OVERLAY_CACHE = {}
    _CATALYST_CACHE = {}
    _SECTOR_CACHE = {}
    _THEME_DIFFUSION_CACHE = {}
    _LIMITUP_CODE_CACHE = {}
    _LIMITUP_THEME_CACHE = {}
    _CLUSTER_RANK_CACHE = {}

    DEFAULT_CONFIG = {
        "enabled": True,
        "ifind_cluster_alias": {},
        "cluster_priority": [],
        "sector_alias_map": {},
        "stale_overlay_guard": {
            "enabled": True,
            "stale_overlay_source_penalty": 20.0,
            "structural_source_match_bonus": 15.0,
        },
        "min_sector_strength_for_active": 60.0,
        "min_sector_return_pct_for_active": 3.0,
        "min_catalyst_count_for_bonus": 1,
        "stale_days": 3,
        "market_structure": {
            "enabled": True,
            "allow_latest_fallback": True,
            "stale_days": 3,
            "min_sector_strength_score": 60.0,
            "min_limitup_count": 3,
            "min_limitup_ratio": 0.02,
            "min_net_active_buy_yuan": 100000000.0,
            "min_theme_limitup_count": 3,
            "min_second_board_count": 1,
            "min_high_board_count": 1,
            "core_member_bonus": 10.0,
            "theme_diffusion_bonus": 12.0,
            "sector_strength_bonus": 15.0,
            "sector_breadth_bonus": 8.0,
            "sector_money_flow_bonus": 8.0,
        },
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
        cls._FRAME_CACHE = {}
        cls._OVERLAY_CACHE = {}
        cls._CATALYST_CACHE = {}
        cls._SECTOR_CACHE = {}
        cls._THEME_DIFFUSION_CACHE = {}
        cls._LIMITUP_CODE_CACHE = {}
        cls._LIMITUP_THEME_CACHE = {}
        cls._CLUSTER_RANK_CACHE = {}

    @classmethod
    def evaluate_candidate(cls, candidate, date_int=None):
        config = cls.load_config()
        result = cls._empty_result()
        if not config.get("enabled", True):
            result["leading_cluster_status"] = "disabled"
            return result

        data = candidate.get("data", {}) or {}
        breakdown = candidate.get("action_score_breakdown", {}) or {}
        code = str(data.get("code", "") or "")
        name = str(candidate.get("name", "") or data.get("name", "") or "")
        resolved_date = cls._resolve_candidate_date(candidate, explicit_date=date_int)
        result["leading_cluster_date"] = resolved_date

        if not code:
            result["leading_cluster_missing_fields"].append("missing_code")
            cls._apply_existing_breakdown_evidence(result, breakdown)
            cls._apply_market_risk_flags(result, data)
            return cls._finalize(result)

        overlay, overlay_meta = cls._load_overlay_record(code, resolved_date, config)
        cls._apply_snapshot_meta(result, overlay_meta, config, track_market_structure=False)
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
        result["ifind_cluster"] = str(overlay.get("ifind_cluster", "") or "")
        result["ifind_catalyst_count"] = 0
        result["ifind_catalyst_summary"] = ""

        stale_days = int(cls._number(config.get("stale_days"), 3))
        snapshot_age_days = cls._snapshot_age_days(overlay.get("ifind_updated_at", ""))
        overlay_is_stale = False
        if snapshot_age_days is not None:
            result["ifind_snapshot_age_days"] = snapshot_age_days
        if snapshot_age_days is not None and snapshot_age_days > stale_days:
            overlay_is_stale = True
            result["leading_cluster_status"] = "stale_ifind_snapshot"
            result["leading_cluster_risk_flags"].append("stale_ifind_snapshot")

        sector_map, sector_meta = cls._load_sector_strength_map(resolved_date, config)
        theme_map, theme_meta = cls._load_theme_diffusion_map(resolved_date, config)
        limitup_code_map, limitup_theme_map, limitup_meta = cls._load_limitup_maps(resolved_date, config)
        cls._apply_snapshot_meta(result, sector_meta, config)
        cls._apply_snapshot_meta(result, theme_meta, config)
        cls._apply_snapshot_meta(result, limitup_meta, config)

        cluster_candidates = cls._build_cluster_candidates(candidate, overlay, config)
        scored_clusters = []
        for item in cluster_candidates:
            scored_clusters.append(
                cls._compute_cluster_score(
                    item,
                    code=code,
                    sector_map=sector_map,
                    theme_map=theme_map,
                    limitup_code_map=limitup_code_map,
                    limitup_theme_map=limitup_theme_map,
                    config=config,
                    overlay_is_stale=overlay_is_stale,
                )
            )

        primary_cluster = cls._pick_primary_cluster(scored_clusters, config)
        if primary_cluster:
            result["ifind_primary_concept"] = primary_cluster.get("concept", "") or result["ifind_primary_concept"]
            result["ifind_cluster"] = primary_cluster.get("cluster", "") or result["ifind_cluster"]
            result["leading_cluster_name"] = primary_cluster.get("cluster", "")
            result["leading_cluster_strength"] = round(cls._number(primary_cluster.get("strength")), 4)
            result["leading_cluster_rank"] = cls._cluster_rank(
                result["leading_cluster_name"],
                resolved_date,
                config,
            )
            result["leading_cluster_membership"] = True
            result["leading_cluster_evidence"].append("ifind_theme_match")
            for flag in primary_cluster.get("evidence", []):
                result["leading_cluster_evidence"].append(flag)
            for flag in primary_cluster.get("missing_fields", []):
                result["leading_cluster_missing_fields"].append(flag)
            for flag in primary_cluster.get("risk_flags", []):
                result["leading_cluster_risk_flags"].append(flag)

        cls._mark_market_structure_missing(result, sector_meta, theme_meta, limitup_meta, primary_cluster)

        catalyst_map, catalyst_meta = cls._load_catalyst_map(resolved_date, config)
        cls._apply_snapshot_meta(result, catalyst_meta, config, track_market_structure=False)
        catalyst = catalyst_map.get(code) or {}
        catalyst_count = int(cls._number(catalyst.get("count"), 0))
        result["ifind_catalyst_count"] = catalyst_count
        result["ifind_catalyst_summary"] = str(catalyst.get("summary", "") or "")
        if catalyst_count >= int(cls._number(config.get("min_catalyst_count_for_bonus"), 1)):
            result["leading_cluster_evidence"].append("ifind_catalyst_confirmed")

        cls._apply_existing_breakdown_evidence(result, breakdown)
        cls._apply_market_risk_flags(result, data)

        allow_stale_market_structure_override = bool(
            overlay_is_stale
            and primary_cluster
            and primary_cluster.get("market_structure_confirmed")
        )
        if result["leading_cluster_status"] not in {"disabled", "missing_ifind_overlay"} and (
            result["leading_cluster_status"] != "stale_ifind_snapshot" or allow_stale_market_structure_override
        ):
            if result["leading_cluster_membership"] and result["leading_cluster_strength"] is not None:
                if cls._number(result["leading_cluster_strength"]) >= cls._number(config.get("min_sector_strength_for_active"), 60.0):
                    result["leading_cluster_status"] = "active"
                elif result["leading_cluster_status"] == "":
                    result["leading_cluster_status"] = "partial"
            elif result["leading_cluster_status"] == "":
                result["leading_cluster_status"] = "partial"

        return cls._finalize(result)

    @classmethod
    def enrich_candidate(cls, candidate, date_int=None):
        result = cls.evaluate_candidate(candidate, date_int=date_int)
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
            "leading_cluster_date": None,
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
    def _build_cluster_candidates(cls, candidate, overlay, config):
        alias_map = config.get("ifind_cluster_alias", {}) or {}
        data = candidate.get("data", {}) or {}
        rows = []
        seen = set()

        overlay_concepts = cls._split_items(overlay.get("ifind_signal_concepts", ""))
        for concept in overlay_concepts:
            cluster = str(alias_map.get(concept, "") or "")
            if not cluster:
                continue
            key = (concept, cluster)
            if key in seen:
                continue
            seen.add(key)
            rows.append({"concept": concept, "cluster": cluster, "source": "ifind_signal_concepts"})

        for field_name in ("ifind_cluster", "group", "theme_cluster"):
            value = ""
            if field_name == "ifind_cluster":
                value = overlay.get("ifind_cluster", "")
            elif field_name == "theme_cluster":
                value = candidate.get("theme_cluster") or data.get("theme_cluster") or ""
            else:
                value = data.get(field_name) or candidate.get(field_name) or ""
            text = str(value or "").strip()
            if not text:
                continue
            cluster = str(alias_map.get(text, "") or text)
            key = (text, cluster)
            if key in seen:
                continue
            seen.add(key)
            rows.append({"concept": text, "cluster": cluster, "source": field_name})
        return rows

    @classmethod
    def _compute_cluster_score(
        cls,
        item,
        code,
        sector_map,
        theme_map,
        limitup_code_map,
        limitup_theme_map,
        config,
        overlay_is_stale=False,
        ):
        concept = str(item.get("concept", "") or "")
        cluster = str(item.get("cluster", "") or "")
        evidence = []
        missing_fields = []
        risk_flags = []

        sector_record = cls._match_record(concept, sector_map, config)
        theme_record = cls._match_record(concept, theme_map, config)
        limitup_theme_record = cls._match_record(concept, limitup_theme_map, config)
        limitup_code_record = limitup_code_map.get(code) or {}

        avg_return = cls._number((sector_record or {}).get("avg_return_pct"))
        amount_yuan = cls._number((sector_record or {}).get("amount_yuan"))
        member_count = cls._number((sector_record or {}).get("member_count"))
        base_strength = cls._strength_score(avg_return, amount_yuan, member_count)

        market_cfg = config.get("market_structure", {}) or {}
        sector_strength_score = cls._number((sector_record or {}).get("sector_strength_score"))
        sector_strength_scaled = min(max(sector_strength_score * 1.5, 0.0), 75.0)
        strength = max(base_strength, sector_strength_scaled)

        if sector_record:
            evidence.append("ifind_sector_strength_confirmed")
            if sector_strength_score >= cls._number(market_cfg.get("min_sector_strength_score"), 60.0):
                evidence.append("sector_strength_score_confirmed")
                evidence.append("sector_breadth_strength_confirmed")
                strength += cls._number(market_cfg.get("sector_strength_bonus"), 15.0)

            limitup_count = cls._number(sector_record.get("limitup_count"))
            limitup_ratio = cls._number(sector_record.get("limitup_ratio"))
            if (
                limitup_count >= cls._number(market_cfg.get("min_limitup_count"), 3)
                or limitup_ratio >= cls._number(market_cfg.get("min_limitup_ratio"), 0.02)
            ):
                evidence.append("sector_limitup_breadth_confirmed")
                strength += cls._number(market_cfg.get("sector_breadth_bonus"), 8.0)

            net_active_buy = cls._number(sector_record.get("net_active_buy_yuan"), float("nan"))
            dde_net_buy = cls._number(sector_record.get("dde_net_buy_yuan"), float("nan"))
            sector_money_flow = net_active_buy if net_active_buy == net_active_buy else dde_net_buy
            if sector_money_flow == sector_money_flow and sector_money_flow >= cls._number(
                market_cfg.get("min_net_active_buy_yuan"),
                100000000.0,
            ):
                evidence.append("sector_money_flow_confirmed")
                strength += cls._number(market_cfg.get("sector_money_flow_bonus"), 8.0)
        else:
            missing_fields.append("sector_strength_unmatched")

        if theme_record:
            limitup_count = int(cls._number(theme_record.get("limitup_count"), 0))
            second_board_count = int(cls._number(theme_record.get("second_board_count"), 0))
            high_board_count = int(cls._number(theme_record.get("high_board_count"), 0))
            if limitup_count >= int(cls._number(market_cfg.get("min_theme_limitup_count"), 3)):
                evidence.append("limitup_ladder_diffusion_confirmed")
            if (
                limitup_count >= int(cls._number(market_cfg.get("min_theme_limitup_count"), 3))
                and (
                    second_board_count >= int(cls._number(market_cfg.get("min_second_board_count"), 1))
                    or high_board_count >= int(cls._number(market_cfg.get("min_high_board_count"), 1))
                )
            ):
                evidence.append("theme_limitup_diffusion_confirmed")
                strength += cls._number(market_cfg.get("theme_diffusion_bonus"), 12.0)
        else:
            missing_fields.append("theme_diffusion_unmatched")

        if limitup_code_record:
            matched_themes = cls._split_items(limitup_code_record.get("signal_concepts", "")) or cls._split_items(
                limitup_code_record.get("concepts", "")
            )
            if any(cls._theme_matches(concept, theme) for theme in matched_themes) or cls._theme_matches(
                concept, limitup_code_record.get("ths_industry", "")
            ):
                evidence.append("limitup_core_member_confirmed")
                strength += cls._number(market_cfg.get("core_member_bonus"), 10.0)
        elif limitup_theme_record:
            core_codes = cls._split_items(limitup_theme_record.get("core_codes", ""))
            if code in core_codes:
                evidence.append("limitup_core_member_confirmed")
                strength += cls._number(market_cfg.get("core_member_bonus"), 10.0)
        else:
            missing_fields.append("limitup_ladder_unmatched")

        if sector_record and avg_return < cls._number(config.get("min_sector_return_pct_for_active"), 3.0):
            strength = min(strength, 59.0)

        stale_guard_cfg = config.get("stale_overlay_guard", {}) or {}
        if overlay_is_stale and stale_guard_cfg.get("enabled", True):
            source = str(item.get("source", "") or "")
            structural_source = source in {"group", "theme_cluster"}
            market_structure_confirmed = bool(sector_record or theme_record or limitup_theme_record or limitup_code_record)
            if structural_source and market_structure_confirmed:
                strength += cls._number(stale_guard_cfg.get("structural_source_match_bonus"), 15.0)
                evidence.append("structural_source_match_preferred")
            elif source in {"ifind_signal_concepts", "ifind_cluster"}:
                strength = max(
                    0.0,
                    strength - cls._number(stale_guard_cfg.get("stale_overlay_source_penalty"), 20.0),
                )
                risk_flags.append("stale_overlay_source_deprioritized")

        cluster = cls._resolve_effective_cluster_name(
            concept=concept,
            cluster=cluster,
            sector_record=sector_record,
            theme_record=theme_record,
            config=config,
        )

        return {
            "concept": concept,
            "cluster": cluster,
            "source": item.get("source", ""),
            "strength": max(0.0, min(strength, 100.0)),
            "sector_confirmed": bool(sector_record),
            "theme_confirmed": bool(theme_record),
            "limitup_confirmed": bool(limitup_theme_record or limitup_code_record),
            "market_structure_confirmed": bool(sector_record or theme_record or limitup_theme_record or limitup_code_record),
            "evidence": evidence,
            "missing_fields": missing_fields,
            "risk_flags": risk_flags,
        }

    @classmethod
    def _resolve_effective_cluster_name(cls, concept, cluster, sector_record, theme_record, config):
        current = str(cluster or concept or "").strip()
        alias_map = config.get("ifind_cluster_alias", {}) or {}
        if current in alias_map:
            return str(alias_map.get(current, current) or current)
        for record in (sector_record or {}, theme_record or {}):
            matched_name = str(
                record.get("concept")
                or record.get("theme")
                or record.get("sector_name")
                or ""
            ).strip()
            if not matched_name:
                continue
            mapped = str(alias_map.get(matched_name, "") or "").strip()
            if mapped:
                return mapped
        return current

    @classmethod
    def _pick_primary_cluster(cls, cluster_scores, config):
        if not cluster_scores:
            return None
        priority = {name: idx for idx, name in enumerate(config.get("cluster_priority", []) or [])}
        return sorted(
            cluster_scores,
            key=lambda row: (
                -cls._number(row.get("strength")),
                0 if row.get("market_structure_confirmed") else 1,
                0 if row.get("source") in {"group", "theme_cluster"} else 1,
                priority.get(row.get("cluster", ""), 999),
                row.get("concept", ""),
            ),
        )[0]

    @classmethod
    def _mark_market_structure_missing(cls, result, sector_meta, theme_meta, limitup_meta, primary_cluster):
        if sector_meta.get("missing"):
            result["leading_cluster_missing_fields"].append("missing_sector_strength_snapshot")
        if theme_meta.get("missing"):
            result["leading_cluster_missing_fields"].append("missing_theme_limitup_distribution")
        if limitup_meta.get("missing"):
            result["leading_cluster_missing_fields"].append("missing_limitup_ladder_snapshot")
        if sector_meta.get("missing") and theme_meta.get("missing") and limitup_meta.get("missing"):
            result["leading_cluster_missing_fields"].append("missing_market_structure_snapshot")
        if primary_cluster is None:
            if not sector_meta.get("missing"):
                result["leading_cluster_missing_fields"].append("sector_strength_unmatched")
            if not theme_meta.get("missing"):
                result["leading_cluster_missing_fields"].append("theme_diffusion_unmatched")
            if not limitup_meta.get("missing"):
                result["leading_cluster_missing_fields"].append("limitup_ladder_unmatched")

    @classmethod
    def _cluster_rank(cls, cluster_name, date_int, config):
        if not cluster_name:
            return None
        rank_map = cls._load_cluster_rank_map(date_int, config)
        return rank_map.get(cluster_name)

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
    def _load_overlay_record(cls, code, date_int, config):
        cache_key = date_int or "latest"
        if cache_key in cls._OVERLAY_CACHE:
            mapping, meta = cls._OVERLAY_CACHE[cache_key]
            return mapping.get(code), meta

        provider = IFindThemeProvider()
        mapping = {}
        meta = {"missing": False, "used_fallback": False, "snapshot_date": date_int}
        allow_latest_fallback = bool((config.get("market_structure", {}) or {}).get("allow_latest_fallback", True))
        frame, file_meta = cls._load_ifind_frame(
            filename="stock_theme_snapshot.csv",
            date_int=date_int,
            allow_latest_fallback=allow_latest_fallback,
        )
        if not frame.empty and "code" in frame.columns:
            work = frame.fillna("").copy()
            if "ifind_cluster" not in work.columns:
                work["ifind_cluster"] = work.get("ifind_signal_concepts", "").map(
                    lambda value: cls._infer_cluster_from_concepts(cls._split_items(value), config)
                )
            mapping = work.set_index("code").to_dict(orient="index")
            meta.update(file_meta)
        elif date_int is None or allow_latest_fallback:
            overlay = provider.load_overlay()
            if not overlay.empty and "code" in overlay.columns:
                work = overlay.fillna("").copy()
                work["ifind_cluster"] = work.get("ifind_signal_concepts", "").map(
                    lambda value: cls._infer_cluster_from_concepts(cls._split_items(value), config)
                )
                mapping = work.set_index("code").to_dict(orient="index")
                meta["used_fallback"] = True
        else:
            meta["missing"] = True
        cls._OVERLAY_CACHE[cache_key] = (mapping, meta)
        return mapping.get(code), meta

    @classmethod
    def _load_sector_strength_map(cls, date_int, config):
        cache_key = date_int or "latest"
        if cache_key in cls._SECTOR_CACHE:
            return cls._SECTOR_CACHE[cache_key]
        frame, meta = cls._load_ifind_frame(
            filename="sector_strength_snapshot.csv",
            date_int=date_int,
            allow_latest_fallback=bool((config.get("market_structure", {}) or {}).get("allow_latest_fallback", True)),
        )
        mapping = {}
        if not frame.empty:
            work = frame.fillna("").copy()
            if "sector_name" in work.columns:
                work["concept"] = work["sector_name"].astype(str)
            if "pct" in work.columns:
                work["avg_return_pct"] = work["pct"]
            for row in work.to_dict(orient="records"):
                for key in cls._record_match_keys(row.get("concept", "")):
                    mapping[key] = row
        cls._SECTOR_CACHE[cache_key] = (mapping, meta)
        return mapping, meta

    @classmethod
    def _load_theme_diffusion_map(cls, date_int, config):
        cache_key = date_int or "latest"
        if cache_key in cls._THEME_DIFFUSION_CACHE:
            return cls._THEME_DIFFUSION_CACHE[cache_key]
        frame, meta = cls._load_ifind_frame(
            filename="theme_limitup_distribution.csv",
            date_int=date_int,
            allow_latest_fallback=bool((config.get("market_structure", {}) or {}).get("allow_latest_fallback", True)),
        )
        mapping = {}
        if not frame.empty and "theme" in frame.columns:
            for row in frame.fillna("").to_dict(orient="records"):
                for key in cls._record_match_keys(row.get("theme", "")):
                    mapping[key] = row
        cls._THEME_DIFFUSION_CACHE[cache_key] = (mapping, meta)
        return mapping, meta

    @classmethod
    def _load_limitup_maps(cls, date_int, config):
        cache_key = date_int or "latest"
        if cache_key in cls._LIMITUP_CODE_CACHE and cache_key in cls._LIMITUP_THEME_CACHE:
            code_map, meta = cls._LIMITUP_CODE_CACHE[cache_key]
            theme_map, _meta = cls._LIMITUP_THEME_CACHE[cache_key]
            return code_map, theme_map, meta
        frame, meta = cls._load_ifind_frame(
            filename="limitup_ladder_snapshot.csv",
            date_int=date_int,
            allow_latest_fallback=bool((config.get("market_structure", {}) or {}).get("allow_latest_fallback", True)),
        )
        code_map = {}
        theme_map = {}
        if not frame.empty:
            work = frame.fillna("").copy()
            if "code" in work.columns:
                code_map = work.set_index("code").to_dict(orient="index")
            for row in work.to_dict(orient="records"):
                themes = cls._split_items(row.get("signal_concepts", "")) or cls._split_items(row.get("concepts", ""))
                if not themes and row.get("ths_industry"):
                    themes = [str(row.get("ths_industry", "")).strip()]
                for theme in themes:
                    for key in cls._record_match_keys(theme):
                        existing = theme_map.get(key)
                        if not existing:
                            theme_map[key] = {
                                "theme": theme,
                                "limitup_count": 1,
                                "first_board_count": 1 if row.get("limitup_tier") == "1板" else 0,
                                "second_board_count": 1 if row.get("limitup_tier") == "2板" else 0,
                                "third_board_count": 1 if row.get("limitup_tier") == "3板" else 0,
                                "high_board_count": 1 if row.get("limitup_tier") == "高度板" else 0,
                                "max_limitup_days": cls._number(row.get("limitup_days"), 0),
                                "core_codes": str(row.get("code", "")),
                                "core_names": str(row.get("name", "")),
                            }
                        else:
                            existing["limitup_count"] = int(cls._number(existing.get("limitup_count"), 0)) + 1
                            existing["first_board_count"] = int(cls._number(existing.get("first_board_count"), 0)) + (1 if row.get("limitup_tier") == "1板" else 0)
                            existing["second_board_count"] = int(cls._number(existing.get("second_board_count"), 0)) + (1 if row.get("limitup_tier") == "2板" else 0)
                            existing["third_board_count"] = int(cls._number(existing.get("third_board_count"), 0)) + (1 if row.get("limitup_tier") == "3板" else 0)
                            existing["high_board_count"] = int(cls._number(existing.get("high_board_count"), 0)) + (1 if row.get("limitup_tier") == "高度板" else 0)
                            existing["max_limitup_days"] = max(
                                cls._number(existing.get("max_limitup_days"), 0),
                                cls._number(row.get("limitup_days"), 0),
                            )
                            code_set = cls._split_items(existing.get("core_codes", ""))
                            name_set = cls._split_items(existing.get("core_names", ""))
                            if row.get("code"):
                                code_set.append(str(row.get("code")))
                            if row.get("name"):
                                name_set.append(str(row.get("name")))
                            existing["core_codes"] = ";".join(cls._dedupe(code_set))
                            existing["core_names"] = ";".join(cls._dedupe(name_set))
        cls._LIMITUP_CODE_CACHE[cache_key] = (code_map, meta)
        cls._LIMITUP_THEME_CACHE[cache_key] = (theme_map, meta)
        return code_map, theme_map, meta

    @classmethod
    def _load_catalyst_map(cls, date_int, config):
        cache_key = date_int or "latest"
        if cache_key in cls._CATALYST_CACHE:
            return cls._CATALYST_CACHE[cache_key]
        frame, meta = cls._load_ifind_frame(
            filename="catalyst_notice_digest.csv",
            date_int=date_int,
            allow_latest_fallback=bool((config.get("market_structure", {}) or {}).get("allow_latest_fallback", True)),
            dtype={"code": str},
        )
        mapping = {}
        if not frame.empty and "code" in frame.columns:
            grouped = (
                frame.fillna("")
                .groupby("code", as_index=False)
                .agg(
                    count=("code", "count"),
                    summary=("summary", lambda s: " | ".join(x for x in map(str, s) if x)),
                )
            )
            mapping = grouped.set_index("code").to_dict(orient="index")
        cls._CATALYST_CACHE[cache_key] = (mapping, meta)
        return mapping, meta

    @classmethod
    def _load_cluster_rank_map(cls, date_int, config):
        cache_key = date_int or "latest"
        if cache_key in cls._CLUSTER_RANK_CACHE:
            return cls._CLUSTER_RANK_CACHE[cache_key]
        sector_map, _meta = cls._load_sector_strength_map(date_int, config)
        theme_map, _theme_meta = cls._load_theme_diffusion_map(date_int, config)
        alias_map = config.get("ifind_cluster_alias", {}) or {}
        cluster_scores = {}

        seen_concepts = set()
        for record in list(sector_map.values()) + list(theme_map.values()):
            concept = str(record.get("concept") or record.get("theme") or record.get("sector_name") or "").strip()
            if not concept or concept in seen_concepts:
                continue
            seen_concepts.add(concept)
            cluster = alias_map.get(concept)
            if not cluster:
                continue
            sector_strength_score = cls._number(record.get("sector_strength_score"))
            limitup_count = cls._number(record.get("limitup_count"))
            score = max(sector_strength_score * 1.5, limitup_count * 5.0)
            cluster_scores[cluster] = max(score, cluster_scores.get(cluster, float("-inf")))

        ordered = sorted(cluster_scores.items(), key=lambda item: (-item[1], item[0]))
        rank_map = {name: idx for idx, (name, _score) in enumerate(ordered, start=1)}
        cls._CLUSTER_RANK_CACHE[cache_key] = rank_map
        return rank_map

    @classmethod
    def _load_ifind_frame(cls, filename, date_int=None, allow_latest_fallback=True, dtype=None):
        cache_key = (filename, date_int or "latest", bool(allow_latest_fallback), tuple(sorted((dtype or {}).items())))
        if cache_key in cls._FRAME_CACHE:
            return cls._FRAME_CACHE[cache_key]

        path, used_fallback = cls._resolve_ifind_file(filename, date_int, allow_latest_fallback)
        meta = {
            "missing": path is None,
            "used_fallback": used_fallback,
            "snapshot_date": cls._extract_snapshot_date(path),
            "path": str(path) if path else "",
        }
        if path is None or not path.exists():
            frame = pd.DataFrame()
            cls._FRAME_CACHE[cache_key] = (frame, meta)
            return frame, meta

        try:
            frame = pd.read_csv(path, encoding="utf-8-sig", dtype=dtype)
        except Exception:
            try:
                frame = pd.read_csv(path, encoding="gb18030", dtype=dtype)
            except Exception:
                frame = pd.DataFrame()
                meta["missing"] = True
        cls._FRAME_CACHE[cache_key] = (frame, meta)
        return frame, meta

    @classmethod
    def _resolve_ifind_file(cls, filename, date_int, allow_latest_fallback):
        root = Path(DBConfig.STORE_PATH)
        if not root.exists():
            return None, False

        if date_int:
            candidate = root / str(int(date_int)) / "ifind" / filename
            if candidate.exists():
                return candidate, False

        if not allow_latest_fallback:
            return None, False

        days = sorted(
            [path for path in root.iterdir() if path.is_dir() and path.name.isdigit() and len(path.name) == 8],
            reverse=True,
        )
        for day in days:
            candidate = day / "ifind" / filename
            if candidate.exists():
                return candidate, True
        return None, False

    @classmethod
    def _apply_snapshot_meta(cls, result, meta, config, track_market_structure=True):
        if not meta:
            return
        if meta.get("used_fallback"):
            result["leading_cluster_risk_flags"].append("ifind_snapshot_date_fallback")
        snapshot_date = meta.get("snapshot_date")
        target_date = result.get("leading_cluster_date")
        if track_market_structure:
            stale_days = int(cls._number((config.get("market_structure", {}) or {}).get("stale_days"), 3))
            gap = cls._date_gap_days(snapshot_date, target_date)
            if gap is not None and gap > stale_days:
                result["leading_cluster_risk_flags"].append("stale_market_structure_snapshot")

    @classmethod
    def _resolve_candidate_date(cls, candidate, explicit_date=None):
        for value in (
            explicit_date,
            candidate.get("date_int"),
            candidate.get("trade_date"),
            candidate.get("date"),
            (candidate.get("data", {}) or {}).get("date_int"),
            (candidate.get("data", {}) or {}).get("trade_date"),
            (candidate.get("data", {}) or {}).get("date"),
        ):
            normalized = cls._normalize_date_int(value)
            if normalized is not None:
                return normalized
        return None

    @staticmethod
    def _normalize_date_int(value):
        text = str(value or "").strip()
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) >= 8:
            return int(digits[:8])
        return None

    @staticmethod
    def _extract_snapshot_date(path):
        if path is None:
            return None
        try:
            name = path.parents[1].name
            return int(name) if name.isdigit() and len(name) == 8 else None
        except Exception:
            return None

    @staticmethod
    def _date_gap_days(snapshot_date, target_date):
        if not snapshot_date or not target_date:
            return None
        try:
            left = pd.Timestamp(str(int(snapshot_date)))
            right = pd.Timestamp(str(int(target_date)))
        except Exception:
            return None
        return abs((left.normalize() - right.normalize()).days)

    @staticmethod
    def _infer_cluster_from_concepts(concepts, config):
        alias_map = config.get("ifind_cluster_alias", {}) or {}
        for concept in concepts:
            cluster = str(alias_map.get(concept, "") or "")
            if cluster:
                return cluster
        return ""

    @classmethod
    def _match_record(cls, theme_name, mapping, config=None):
        if not theme_name or not mapping:
            return None
        for key in cls._expanded_match_keys(theme_name, config):
            if key in mapping:
                return mapping[key]
        return None

    @classmethod
    def _record_match_keys(cls, text):
        value = str(text or "").strip()
        if not value:
            return []
        normalized = cls._normalize_theme_label(value)
        keys = [normalized]
        if value != normalized:
            keys.append(value)
        return cls._dedupe(keys)

    @classmethod
    def _expanded_match_keys(cls, text, config=None):
        keys = cls._record_match_keys(text)
        alias_map = {}
        if isinstance(config, dict):
            alias_map = config.get("sector_alias_map", {}) or {}
        for raw_key in list(keys):
            for alias in alias_map.get(raw_key, []) or alias_map.get(cls._normalize_theme_label(raw_key), []) or []:
                keys.extend(cls._record_match_keys(alias))
        return cls._dedupe(keys)

    @staticmethod
    def _normalize_theme_label(text):
        value = str(text or "").strip()
        for suffix in ("概念", "板块", "主题"):
            if value.endswith(suffix):
                value = value[: -len(suffix)]
        return value.strip()

    @classmethod
    def _theme_matches(cls, left, right):
        return cls._normalize_theme_label(left) == cls._normalize_theme_label(right)

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
            amount_term = min(max(math.log10(amount_yuan) - 9.0, 0.0), 3.0) * 8.0
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

    @staticmethod
    def _deep_merge(base, extra):
        if not isinstance(base, dict) or not isinstance(extra, dict):
            return deepcopy(extra)
        merged = deepcopy(base)
        for key, value in extra.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = LeadingClusterEvidenceBuilder._deep_merge(merged[key], value)
            else:
                merged[key] = deepcopy(value)
        return merged
