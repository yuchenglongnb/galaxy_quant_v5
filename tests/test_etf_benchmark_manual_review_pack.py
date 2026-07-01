import json
from pathlib import Path

import scripts.evaluate_etf_benchmark_manual_review_pack as pack


def _write_csv(path: Path, columns: list[str], rows: list[list[str]] | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = ",".join(columns) + "\n"
    for row in rows or []:
        text += ",".join(row) + "\n"
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_no_candidate_etf_confidence_none(tmp_path, monkeypatch):
    monkeypatch.setattr(pack, "ROOT", tmp_path)
    monkeypatch.setattr(pack, "EVAL_ROOT", tmp_path / "eval")
    monkeypatch.setattr(pack, "BENCHMARK_MAP_PATH", tmp_path / "watchlists" / "group_benchmark_map.csv")
    date = "20260629"
    _write_json(pack.EVAL_ROOT / f"trend_confirmation_scope_normalization_{date}.json", {"benchmark_map_missing_groups": ["军工电子"]})
    payload = pack.build_payload(date)
    assert payload["group_review"][0]["confidence"] == "none"
    assert payload["group_review"][0]["candidate_benchmarks"] == []
    assert payload["group_review"][0]["should_auto_update_map"] is False


def test_low_confidence_never_auto_updates():
    etfs = {"159870.SZ": {"code": "159870.SZ", "name": "化工"}}
    result = pack._review_group("磷肥及磷化工", etfs, set(), {})
    assert result["confidence"] == "low"
    assert result["should_auto_update_map"] is False


def test_medium_confidence_never_auto_updates():
    etfs = {"159001.SZ": {"code": "159001.SZ", "name": "军工电子"}}
    result = pack._review_group("军工电子", etfs, {"159001.SZ"}, {})
    assert result["confidence"] == "high"
    assert result["should_auto_update_map"] is False


def test_high_confidence_from_existing_mapping_still_read_only():
    etfs = {"159001.SZ": {"code": "159001.SZ", "name": "军工电子"}}
    result = pack._review_group(
        "军工电子",
        etfs,
        {"159001.SZ"},
        {"军工电子": {"benchmark_etf_code": "159001.SZ", "note": "approved elsewhere"}},
    )
    assert result["confidence"] == "high"
    assert result["current_benchmark"] == "159001.SZ"
    assert result["should_auto_update_map"] is False


def test_build_payload_flags_and_existing_diff(tmp_path, monkeypatch):
    monkeypatch.setattr(pack, "ROOT", tmp_path)
    monkeypatch.setattr(pack, "EVAL_ROOT", tmp_path / "eval")
    map_path = tmp_path / "watchlists" / "group_benchmark_map.csv"
    monkeypatch.setattr(pack, "BENCHMARK_MAP_PATH", map_path)
    _write_csv(map_path, ["group", "benchmark_etf_code", "benchmark_index_code", "note"], [["A", "", "", ""]])
    date = "20260629"
    _write_json(pack.EVAL_ROOT / f"trend_confirmation_scope_normalization_{date}.json", {"benchmark_map_missing_groups": ["磷肥及磷化工"]})
    _write_csv(
        tmp_path / "reports" / "validation" / "daily" / date / "factor_snapshot_etf.csv",
        ["code", "name", "auction_pct", "close_pct", "body_pct"],
        [["159870.SZ", "化工", "1", "2", "1"]],
    )
    monkeypatch.setattr(pack, "_has_git_diff", lambda path: True)
    payload = pack.build_payload(date)
    assert payload["benchmark_map_modified"] is False
    assert payload["benchmark_map_change_required"] is False
    assert payload["manual_review_required"] is True
    assert payload["trend_active_allowed"] is False
    assert payload["evaluator_change_required"] is False
    assert payload["existing_benchmark_map_diff_detected"] is True
    assert "existing_group_benchmark_map_diff_requires_separate_review" in payload["warnings"]
    assert "benchmark_map_not_modified" in payload["conclusion"]


def test_write_outputs_does_not_modify_benchmark_map(tmp_path, monkeypatch):
    monkeypatch.setattr(pack, "EVAL_ROOT", tmp_path / "eval")
    map_path = tmp_path / "watchlists" / "group_benchmark_map.csv"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    original = "group,benchmark_etf_code,benchmark_index_code,note\nA,,,\n"
    map_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(pack, "BENCHMARK_MAP_PATH", map_path)
    payload = {
        "date": "20260629",
        "review_groups": [],
        "group_review": [],
        "high_confidence_candidates": [],
        "medium_confidence_candidates": [],
        "low_confidence_candidates": [],
        "no_candidate_groups": [],
        "benchmark_map_modified": False,
        "existing_benchmark_map_diff_detected": False,
        "trend_active_allowed": False,
        "evaluator_change_required": False,
        "warnings": [],
        "conclusion": ["benchmark_map_not_modified"],
    }
    pack.write_outputs(payload)
    assert map_path.read_text(encoding="utf-8") == original
