import json

import pandas as pd

from reports.build_state_transition_flywheel import build_pack


def _write_day(root, date, regime, scope="post_close_final"):
    analysis_dir = root / "analysis" / date
    validation_dir = root / "validation" / date
    analysis_dir.mkdir(parents=True)
    validation_dir.mkdir(parents=True)
    review = {
        "validation_scope": scope,
        "market_regime": {"label": regime},
        "environment_gate": {"label": "continuation", "decision": "trend_enabled"},
    }
    (analysis_dir / "auction_review.json").write_text(json.dumps(review), encoding="utf-8")
    detail = pd.DataFrame([
        {
            "signal_category": "trend",
            "body_pct": -1.0,
            "validation_success": False,
            "signal_path_type": "one_way_selloff",
        }
        for _ in range(20)
    ])
    detail.to_csv(validation_dir / "signal_detail.csv", index=False)
    pd.DataFrame([
        {"signal_category": "trend", "success_rate": 20.0}
    ]).to_csv(validation_dir / "signal_metrics.csv", index=False)


def test_batch_preserves_next_regime_and_strict_pair_levels(tmp_path):
    _write_day(tmp_path, "20260706", "continuation")
    _write_day(tmp_path, "20260707", "hostile")
    availability = [
        {"date": "20260706", "validation_level": "candidate_close"},
        {"date": "20260707", "validation_level": "candidate_close"},
        {"date": "20260708", "validation_level": "sector_only"},
    ]
    sector = {
        "date_start": "20260708",
        "date_end": "20260716",
        "records": [{
            "data_quality": "usable_sector_only",
            "return_scope": "period_arithmetic_mean",
            "turnover_scope": "daily",
            "daily_amount": {"20260708": 100},
            "daily_return_available": False,
        }],
    }
    payload = build_pack(
        ["20260706", "20260707", "20260708"],
        tmp_path / "analysis",
        tmp_path / "validation",
        availability_records=availability,
        sector_evidence=sector,
    )

    verified, range_context = payload["transitions"]
    assert verified["next_day_regime"] == "hostile"
    assert verified["counts_as_valid_candidate_pair"] is True
    assert verified["decision_validation_level"] == "candidate_close"
    assert verified["feedback_validation_level"] == "candidate_close"
    assert range_context["feedback_validation_level"] == "sector_range_context"
    assert range_context["feedback_label"] == "sector_context_only_no_daily_price_confirmation"
    assert range_context["counts_as_valid_candidate_pair"] is False
    assert payload["valid_candidate_pair_count"] == 1
