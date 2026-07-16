import json

from scripts.sync_data_flywheel import build_manifest, inspect_date


def _write_cache(root, date, stocks=True, indices=True, state="closed"):
    day = root / date
    day.mkdir(parents=True)
    if stocks:
        (day / "stocks.csv").write_text("code,close\nA,1\n", encoding="utf-8")
        (day / "stocks.meta.json").write_text(json.dumps({"session_state": state}), encoding="utf-8")
    if indices:
        (day / "indices.csv").write_text("code,close\nI,1\n", encoding="utf-8")
        (day / "indices.meta.json").write_text(json.dumps({"session_state": state}), encoding="utf-8")


def test_existing_complete_cache_is_skipped(tmp_path):
    _write_cache(tmp_path, "20260706")
    row = inspect_date("20260706", tmp_path)
    assert row["sync_status"] == "skipped_existing_complete"
    assert row["validation_level"] == "candidate_close"


def test_fetch_return_does_not_override_missing_files(tmp_path):
    row = inspect_date("20260708", tmp_path, fetch_returned=True, attempted=True)
    assert row["sync_status"] == "missing"
    assert row["cache_complete_after"] is False


def test_blocked_provider_with_sector_evidence_is_sector_only(tmp_path):
    payload = build_manifest(
        ["20260708"], tmp_path, sector_only_dates=["20260708"], provider_blocked_dates=["20260708"]
    )
    row = payload["records"][0]
    assert row["sync_status"] == "sector_only"
    assert row["validation_level"] == "sector_only"
    assert row["provider"] == "ifind_mcp"
    assert row["error_type"] == "provider_login_blocked"
