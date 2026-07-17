import pandas as pd

from reports.daily_validation_level import derive_daily_validation_level


def _frame():
    return pd.DataFrame([{"signal_category": "trend"}])


def _review(scope="post_close_final"):
    return {"validation_scope": scope}


def _availability(level="candidate_close"):
    return {"date": "20260706", "validation_level": level}


def test_candidate_close_requires_all_verified_artifacts():
    result = derive_daily_validation_level(
        "20260706", _frame(), _frame(), _review(), _availability()
    )
    assert result["validation_level"] == "candidate_close"


def test_missing_metrics_cannot_be_candidate_close():
    result = derive_daily_validation_level(
        "20260706", _frame(), pd.DataFrame(), _review(), _availability()
    )
    assert result["validation_level"] == "candidate_partial"


def test_non_final_review_cannot_be_candidate_close():
    result = derive_daily_validation_level(
        "20260706", _frame(), _frame(), _review("provisional_intraday"), _availability()
    )
    assert result["validation_level"] == "candidate_partial"


def test_availability_must_confirm_candidate_close():
    result = derive_daily_validation_level(
        "20260706", _frame(), _frame(), _review(), _availability("partial_daily")
    )
    assert result["validation_level"] == "candidate_partial"


def test_missing_availability_is_unverified_not_candidate_close():
    result = derive_daily_validation_level(
        "20260706", _frame(), _frame(), _review()
    )
    assert result["validation_level"] == "candidate_close_unverified"


def test_period_sector_evidence_is_range_context():
    result = derive_daily_validation_level(
        "20260708",
        pd.DataFrame(),
        pd.DataFrame(),
        {},
        _availability("sector_only"),
        {
            "date_start": "20260708",
            "date_end": "20260716",
            "records": [{
                "data_quality": "usable_sector_only",
                "return_scope": "period_arithmetic_mean",
                "turnover_scope": "daily",
                "daily_amount": {"20260708": 100},
                "daily_return_available": False,
            }],
        },
    )
    assert result["validation_level"] == "sector_range_context"
    assert result["sector_context"]["daily_return_available"] is False
    assert result["sector_context"]["usable_record_count"] == 1


def test_empty_sector_records_do_not_create_range_context():
    result = derive_daily_validation_level(
        "20260708",
        pd.DataFrame(),
        pd.DataFrame(),
        {},
        _availability("sector_only"),
        {
            "date_start": "20260708",
            "date_end": "20260716",
            "records": [{
                "data_quality": "empty_result",
                "return_scope": "unavailable",
                "turnover_scope": "unavailable",
                "daily_amount": {},
            }],
        },
    )
    assert result["validation_level"] == "missing"
    assert result["sector_context"]["available"] is False
    assert result["sector_context"]["availability_reason"] == "no_usable_sector_records"


def test_daily_flag_without_target_date_stays_range_context():
    result = derive_daily_validation_level(
        "20260709", pd.DataFrame(), pd.DataFrame(), {}, _availability("sector_only"),
        {
            "date_start": "20260708",
            "date_end": "20260716",
            "records": [{
                "data_quality": "usable_sector_daily",
                "return_scope": "daily",
                "turnover_scope": "daily",
                "daily_return_available": True,
                "daily_returns": {"20260708": 1.2},
            }],
        },
    )
    assert result["validation_level"] == "sector_range_context"
    assert result["sector_context"]["daily_return_available"] is False


def test_target_date_daily_return_creates_daily_evidence():
    result = derive_daily_validation_level(
        "20260709", pd.DataFrame(), pd.DataFrame(), {}, _availability("sector_only"),
        {
            "date_start": "20260708",
            "date_end": "20260716",
            "records": [{
                "data_quality": "usable_sector_daily",
                "return_scope": "daily",
                "turnover_scope": "daily",
                "daily_return_available": True,
                "return_by_date": {"20260709": -0.5},
            }],
        },
    )
    assert result["validation_level"] == "sector_daily_evidence"
    assert result["sector_context"]["daily_return_available"] is True
