import json

import pytest

from reports.ifind_sector_evidence import build_sector_record, write_evidence


def test_ifind_sector_record_is_sector_only_and_classified():
    row = build_sector_record(
        "机器人", "20260706", "20260710", -5.4,
        {"20260706": 100, "20260710": 120},
    )
    assert row["provider"] == "ifind_mcp"
    assert row["validation_level"] == "sector_only"
    assert row["price_turnover_confirmation"] == "high_turnover_without_price_confirmation"


def test_sector_evidence_cannot_write_candidate_validation(tmp_path):
    with pytest.raises(ValueError):
        write_evidence([], tmp_path / "reports/validation/daily/20260708")


def test_sector_output_contains_no_candidate_claim(tmp_path):
    row = build_sector_record("半导体设备", "20260706", "20260710", 3.7, {"a": 100, "b": 120})
    root = tmp_path / "reports/analysis/evidence/ifind/range"
    json_path, _ = write_evidence([row], root)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["candidate_level_data"] is False
