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


def _write_daily_validation(root: Path, date: str, rows: list[dict], metrics: str = ""):
    day = root / "reports" / "validation" / "daily" / date
    day.mkdir(parents=True, exist_ok=True)
    fields = [
        "date",
        "signal_category",
        "signal_family",
        "target_type",
        "code",
        "name",
        "scenario",
        "trigger_reason",
        "cp",
        "body_pct",
        "validation_success",
        "signal_path_type",
        "open_to_high_pct",
        "open_to_low_pct",
        "mfe_pct",
        "mae_pct",
        "close_to_high_drawdown_pct",
        "intraday_range_pct",
        "market_regime",
        "theme_cluster",
        "validation_scope",
        "data_session_state",
    ]
    lines = [",".join(fields)]
    for row in rows:
        lines.append(",".join(str(row.get(field, "")) for field in fields))
    (day / "signal_detail.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (day / "signal_metrics.csv").write_text(metrics or "date,signal_family,signal_category,success_rate\n", encoding="utf-8")


def test_daily_validation_csv_parse_and_aggregate(tmp_path, monkeypatch):
    monkeypatch.setattr(matrix, "ROOT", tmp_path)
    _write_daily_validation(
        tmp_path,
        "20260703",
        [
            {
                "date": "20260703",
                "signal_category": "trend",
                "signal_family": "趋势机会",
                "target_type": "stock",
                "code": "000001.SZ",
                "name": "sample_a",
                "body_pct": "2.5",
                "validation_success": "True",
                "signal_path_type": "close_near_high",
                "open_to_high_pct": "3.0",
                "open_to_low_pct": "-1.0",
                "mfe_pct": "3.0",
                "mae_pct": "-1.0",
                "close_to_high_drawdown_pct": "-0.5",
                "intraday_range_pct": "4.0",
                "market_regime": "risk_off",
                "theme_cluster": "theme_a",
                "validation_scope": "post_close_final",
                "data_session_state": "closed",
            },
            {
                "date": "20260703",
                "signal_category": "trend",
                "signal_family": "趋势机会",
                "target_type": "stock",
                "code": "000002.SZ",
                "name": "sample_b",
                "body_pct": "-3.0",
                "validation_success": "False",
                "signal_path_type": "high_open_trap",
            },
        ],
    )
    payload = matrix.build_matrix(
        prior_day_glob="reports/analysis/evaluations/prior_day_context_stock_effect_*.json",
        path_distribution=tmp_path / "missing_path.json",
        gate_review=tmp_path / "missing_gate.json",
        include_daily_validation=True,
        daily_validation_root=tmp_path / "reports" / "validation" / "daily",
        dates=["20260703"],
    )
    daily = [record for record in payload["records"] if record["review_status"] == "analysis_only_daily_validation"]
    assert len(daily) == 2
    assert daily[0]["feedback_label"] == "confirmed_close"
    assert daily[0]["contradiction_labels"] == ["auction_feedback_confirmed_close"]
    assert daily[1]["feedback_label"] == "failed_close"
    assert "path_risk_after_auction" in daily[1]["contradiction_labels"]
    assert "auction -> same_day_close" in payload["measurable_pairs"]
    assert payload["aggregate"]["daily_validation"]["daily_validation_record_count"] == 2
    assert payload["aggregate"]["daily_validation"]["success_rate_by_signal_category"]["trend"] == 50.0


def test_daily_validation_missing_optional_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(matrix, "ROOT", tmp_path)
    _write_daily_validation(
        tmp_path,
        "20260703",
        [{"date": "20260703", "signal_category": "trap", "name": "missing_fields"}],
    )
    payload = matrix.build_matrix(
        prior_day_glob="reports/analysis/evaluations/prior_day_context_stock_effect_*.json",
        path_distribution=tmp_path / "missing_path.json",
        gate_review=tmp_path / "missing_gate.json",
        include_daily_validation=True,
        daily_validation_root=tmp_path / "reports" / "validation" / "daily",
        dates=["20260703", "20260704"],
    )
    daily = [record for record in payload["records"] if record["review_status"] == "analysis_only_daily_validation"]
    assert daily[0]["feedback_label"] == "missing_feedback"
    assert daily[0]["data_available"] is False
    assert any(source["status"] == "missing_signal_detail" for source in payload["missing_sources"])


def test_daily_validation_output_dir_and_no_forbidden_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(matrix, "ROOT", tmp_path)
    _write_daily_validation(
        tmp_path,
        "20260703",
        [{"date": "20260703", "signal_category": "trap", "name": "sample", "body_pct": "1.0", "validation_success": "False"}],
    )
    result = matrix.main([
        "--include-daily-validation",
        "--dates",
        "20260703",
        "--daily-validation-root",
        str(tmp_path / "reports" / "validation" / "daily"),
        "--output-dir",
        str(tmp_path / "out"),
    ])
    assert result["aggregate"]["daily_validation"]["daily_validation_record_count"] == 1
    combined = (tmp_path / "out" / "temporal_feedback_matrix_daily_validation_seed.json").read_text(encoding="utf-8")
    combined += (tmp_path / "out" / "temporal_feedback_matrix_daily_validation_seed.md").read_text(encoding="utf-8")
    for forbidden in ["reports/analysis/lessons", "reports/analysis/patterns", "market_pattern_registry.json"]:
        assert forbidden not in combined
