import json
from pathlib import Path

from reports import temporal_feedback_matrix as matrix


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_missing_sources_partial_output(tmp_path, monkeypatch):
    monkeypatch.setattr(matrix, "ROOT", tmp_path)
    payload = matrix.build_matrix(
        prior_day_glob="reports/analysis/evaluations/prior_day_context_stock_effect_*.json",
        path_distribution=tmp_path / "missing_path.json",
        gate_review=tmp_path / "missing_gate.json",
    )
    assert payload["metadata"]["analysis_only"] is True
    assert payload["records"] == []
    assert len(payload["missing_sources"]) == 2


def test_prior_day_summary_parse_and_feedback_labels(tmp_path, monkeypatch):
    monkeypatch.setattr(matrix, "ROOT", tmp_path)
    day = tmp_path / "reports" / "analysis" / "evaluations" / "prior_day_context_stock_effect_20260624.json"
    _write_json(
        day,
        {
            "date": "20260624",
            "prev_trade_date": "20260623",
            "context_confidence": "medium",
            "rank_changed_count": 2,
            "positive_bonus_performance": {
                "performance_available": True,
                "avg_body_pct": -1.0,
                "median_body_pct": -0.8,
                "success_rate": 33.0,
                "candidate_count": 3,
            },
            "negative_bonus_performance": {
                "performance_available": True,
                "avg_body_pct": 1.2,
                "median_body_pct": 1.0,
                "success_rate": 66.0,
                "candidate_count": 4,
            },
            "zero_bonus_performance": {
                "performance_available": True,
                "avg_body_pct": 0.0,
                "median_body_pct": 0.0,
                "success_rate": 50.0,
                "candidate_count": 5,
            },
        },
    )
    payload = matrix.build_matrix(
        prior_day_glob="reports/analysis/evaluations/prior_day_context_stock_effect_*.json",
        path_distribution=tmp_path / "missing_path.json",
        gate_review=tmp_path / "missing_gate.json",
    )
    assert payload["metadata"]["record_count"] == 3
    assert payload["records"][0]["feedback_timepoint"] == "same_day_close"
    labels = payload["aggregate"]["contradiction_counts"]
    assert labels["positive_context_but_weak_path"] == 1
    assert labels["negative_context_but_strong_path"] == 1


def test_dry_run_no_write(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(matrix, "ROOT", tmp_path)
    monkeypatch.setattr(matrix, "build_matrix", lambda **_kwargs: {
        "metadata": {"record_count": 0},
        "missing_sources": [],
        "measurable_pairs": ["prior_day_context -> same_day_close"],
    })
    result = matrix.main(["--dry-run", "--output-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert result["metadata"]["record_count"] == 0
    assert '"dry_run": true' in captured.out
    assert not any(tmp_path.iterdir())


def test_output_dir_tmp_path_and_markdown_disclaimer(tmp_path):
    payload = {
        "metadata": {"schema_version": "p2.0_seed", "record_count": 0, "analysis_only": True},
        "sources": {"prior_day_context": [], "intraday_path_distribution": {}, "path_stability_gate": {}},
        "missing_sources": [],
        "measurable_pairs": [],
        "missing_capabilities": [],
        "aggregate": {"record_count": 0, "contradiction_counts": {}},
        "records": [],
    }
    json_path, md_path = matrix.write_outputs(payload, tmp_path)
    assert json_path.parent == tmp_path
    assert md_path.parent == tmp_path
    assert "not trading advice" in md_path.read_text(encoding="utf-8")


def test_no_lesson_pattern_registry_paths_in_rendered_output(tmp_path):
    payload = {
        "metadata": {"schema_version": "p2.0_seed", "record_count": 0, "analysis_only": True},
        "sources": {"prior_day_context": [], "intraday_path_distribution": {}, "path_stability_gate": {}},
        "missing_sources": [],
        "measurable_pairs": [],
        "missing_capabilities": [],
        "aggregate": {"record_count": 0, "contradiction_counts": {}},
        "records": [],
    }
    json_path, md_path = matrix.write_outputs(payload, tmp_path)
    combined = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
    for forbidden in ["reports/analysis/lessons", "reports/analysis/patterns", "market_pattern_registry.json"]:
        assert forbidden not in combined
