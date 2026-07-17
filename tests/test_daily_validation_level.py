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
            "records": [{"daily_return_available": False}],
        },
    )
    assert result["validation_level"] == "sector_range_context"
    assert result["sector_context"]["daily_return_available"] is False
