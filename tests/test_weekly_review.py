# -*- coding: utf-8 -*-

import json

import pandas as pd

from reports.weekly_review import WeeklyReviewBuilder, WeeklyReviewPaths


def test_weekly_review_separates_metrics_and_emits_integrity_warnings(tmp_path):
    validation_dir = tmp_path / "validation"
    analysis_dir = tmp_path / "analysis"
    validation_dir.mkdir()
    daily_dir = analysis_dir / "daily" / "20260529"
    daily_dir.mkdir(parents=True)

    pd.DataFrame([
        {
            "date": "20260529",
            "signal_category": "trap",
            "validation_result": "success",
            "body_pct": -2.0,
            "target_type": "个股",
            "name": "A",
            "cp": 80,
            "auction_pct": 2.0,
        },
        {
            "date": "20260529",
            "signal_category": "trap",
            "validation_result": "failed",
            "body_pct": 1.0,
            "target_type": "ETF",
            "name": "B",
            "cp": 70,
            "auction_pct": 1.0,
        },
        {
            "date": "20260529",
            "signal_category": "trend",
            "validation_result": "success",
            "body_pct": 3.0,
            "target_type": "个股",
            "name": "C",
            "auction_pct": -0.5,
        },
    ]).to_csv(validation_dir / "auction_signal_validation.csv", index=False, encoding="utf-8-sig")

    (daily_dir / "auction_review.json").write_text(
        json.dumps({
            "data_status": {"session_state": "closed", "fetched_at": "2026-05-31T10:00:00"},
            "validation_scope": "post_close_final",
            "market_oar": 1.1,
        }),
        encoding="utf-8",
    )

    builder = WeeklyReviewBuilder(
        WeeklyReviewPaths(validation_dir=str(validation_dir), analysis_dir=str(analysis_dir))
    )
    payload = builder.build("20260525", "20260529")

    metrics = {row["signal_category"]: row for row in payload["metrics"]}
    assert metrics["trap"]["trigger_count"] == 2
    assert metrics["trap"]["success_rate"] == 50.0
    assert metrics["trend"]["trigger_count"] == 1
    assert payload["data_status"][0]["session_state"] == "closed"
    assert any("Candidate generation is separated" in item for item in payload["integrity_warnings"])
    assert payload["notable_failures"][0]["name"] == "B"
