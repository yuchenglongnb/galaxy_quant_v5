import json

import pandas as pd

from reports.intraday_path_replay import (
    SAFETY_DISCLAIMER,
    build_t1_replay,
    build_input_coverage,
    build_replay_payload,
    denominator_reconciliation,
    expand_date_range,
    metric_definitions,
    render_markdown,
    summarize_paths,
    summarize_t1,
    write_outputs,
)


def test_summarize_paths_aggregates_small_frame():
    frame = pd.DataFrame(
        [
            {
                "date": "20260702",
                "signal_family": "CP风险",
                "signal_path_type": "one_way_selloff",
                "body_pct": -2.0,
                "open_to_high_pct": 0.2,
                "open_to_low_pct": -3.0,
                "close_to_high_drawdown_pct": -2.5,
                "intraday_range_pct": 3.2,
            },
            {
                "date": "20260702",
                "signal_family": "CP风险",
                "signal_path_type": "one_way_selloff",
                "body_pct": -1.0,
                "open_to_high_pct": 0.4,
                "open_to_low_pct": -2.0,
                "close_to_high_drawdown_pct": -1.5,
                "intraday_range_pct": 2.4,
            },
        ]
    )

    summary = summarize_paths(frame)

    assert summary[0]["count"] == 2
    assert summary[0]["avg_body_pct"] == -1.5
    assert summary[0]["median_open_to_low_pct"] == -2.5


def test_summarize_paths_handles_missing_fields_without_crashing():
    frame = pd.DataFrame([{"date": "20260702", "signal_family": "趋势机会", "signal_path_type": "unknown"}])

    summary = summarize_paths(frame)

    assert summary[0]["count"] == 1
    assert summary[0].get("avg_open_to_high_pct") is None


def test_summarize_paths_empty_input_is_safe():
    assert summarize_paths(pd.DataFrame()) == []


def test_t1_prefixed_fields_are_summarized():
    frame = pd.DataFrame(
        [
            {
                "signal_family": "反核机会",
                "t1_join_status": "code_joined",
                "t1_open_return": -1.0,
                "t1_close_return": -2.0,
                "t1_open_to_low_pct": -3.0,
                "t1_close_to_high_drawdown_pct": -2.5,
                "t1_signal_path_type": "low_open_rebound_failed",
            }
        ]
    )

    summary = summarize_t1(frame)

    assert summary[0]["resolved_count"] == 1
    assert summary[0]["t1_path_type_distribution"] == {"low_open_rebound_failed": 1}


def test_markdown_rendering_includes_safety_disclaimer():
    payload = {
        "date_range": {"start": "20260701", "end": "20260702"},
        "inputs": [],
        "daily_signal_summary": [],
        "t1_signal_summary": [],
        "case_studies": [],
        "limitations": [],
    }

    markdown = render_markdown(payload)

    assert SAFETY_DISCLAIMER in markdown
    assert "does not justify deterministic rule changes" in markdown


def test_outputs_do_not_target_lesson_pattern_or_registry(tmp_path):
    payload = {
        "date_range": {"start": "20260701", "end": "20260702"},
        "inputs": [],
        "daily_signal_summary": [],
        "t1_signal_summary": [],
        "case_studies": [],
        "limitations": [],
    }
    output = tmp_path / "reports" / "analysis" / "replay" / "report.md"
    json_output = tmp_path / "reports" / "analysis" / "replay" / "summary.json"

    write_outputs(payload, output, json_output)

    assert output.exists()
    assert json_output.exists()
    assert "lessons" not in str(output)
    assert "patterns" not in str(output)
    assert "market_pattern_registry" not in str(output)
    assert json.loads(json_output.read_text(encoding="utf-8"))["analysis_only"] is not False


def test_t1_replay_counts_manual_scope_pending_and_code_join(tmp_path):
    root = tmp_path
    signal_dir = root / "reports" / "validation" / "derived" / "signal_detail_manual_code_patch"
    quote_dir = root / "AmazingData_Store" / "20260702"
    signal_dir.mkdir(parents=True)
    quote_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {"date": "20260701", "signal_family": "CP风险", "code": "000001.SZ", "name": "A"},
            {
                "date": "20260701",
                "signal_family": "反核机会",
                "code": "",
                "name": "行业",
                "manual_resolution_scope": "industry_without_code",
            },
            {
                "date": "20260701",
                "signal_family": "趋势机会",
                "code": "399006.SZ",
                "name": "创业板",
                "manual_resolution_status": "pending",
            },
        ]
    ).to_csv(signal_dir / "20260701_signal_detail.manual_code_patch.csv", index=False)
    pd.DataFrame(
        [
            {
                "code": "000001.SZ",
                "name": "A",
                "open": 10.0,
                "high": 10.2,
                "low": 9.7,
                "close": 9.8,
                "pre_close": 10.1,
            }
        ]
    ).to_csv(quote_dir / "stocks.csv", index=False)
    pd.DataFrame(columns=["code", "open", "high", "low", "close", "pre_close"]).to_csv(quote_dir / "indices.csv", index=False)

    frame, metadata = build_t1_replay("20260701", "20260702", root)

    assert metadata["primary_code_join_count"] == 1
    assert metadata["manual_scope_excluded_count"] == 1
    assert metadata["pending_blocked_count"] == 1
    assert metadata["fallback_name_join_count"] == 0
    assert set(frame["t1_join_status"]) == {"code_joined", "manual_scope_excluded", "pending_blocked"}


def test_date_range_expansion_uses_local_directories(tmp_path):
    (tmp_path / "reports" / "validation" / "daily" / "20260701").mkdir(parents=True)
    (tmp_path / "AmazingData_Store" / "20260702").mkdir(parents=True)
    (tmp_path / "AmazingData_Store" / "20260703").mkdir(parents=True)

    dates = expand_date_range("20260701", "20260702", tmp_path)

    assert dates == ["20260701", "20260702"]


def test_missing_date_input_is_recorded_in_coverage(tmp_path):
    coverage = build_input_coverage(["20260701"], tmp_path)

    assert coverage[0]["signal_detail_quality"] == "missing"
    assert "missing_signal_detail" in coverage[0]["notes"]
    assert coverage[0]["path_fields_computed_from_ohlc"] is False


def test_metric_definitions_and_denominator_reconciliation_are_emitted():
    definitions = metric_definitions()
    reconciliation = denominator_reconciliation()

    assert definitions["t1_close_return"] == "T+1 close / T+1 pre_close - 1."
    assert "primary code join is required" in " ".join(reconciliation["denominator_rules"])


def test_broader_payload_contains_analysis_only_metadata(tmp_path):
    payload = build_replay_payload(["20260701"], tmp_path)

    assert payload["metadata"]["analysis_only"] is True
    assert "metric_definitions" in payload
    assert "denominator_reconciliation" in payload
    assert payload["input_coverage"][0]["date"] == "20260701"
