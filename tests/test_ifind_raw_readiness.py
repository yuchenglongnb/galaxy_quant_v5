import json
from pathlib import Path

import scripts.evaluate_ifind_raw_readiness as readiness


def _write_csv(path: Path, columns: list[str], rows: list[list[str]] | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = ",".join(columns) + "\n"
    for row in rows or [["x" for _ in columns]]:
        body += ",".join(row) + "\n"
    path.write_text(body, encoding="utf-8")


def test_missing_readiness_and_manifest_structure(tmp_path, monkeypatch):
    monkeypatch.setattr(readiness, "ROOT", tmp_path)
    payload = readiness.build_payload(["20260626"], write_manifest_files=True)
    assert payload["readiness_by_date"]["20260626"] == "missing"
    assert "20260626" in payload["missing_dates"]
    manifest = json.loads((tmp_path / "AmazingData_Store" / "20260626" / "ifind" / "raw" / "raw_manifest.json").read_text(encoding="utf-8"))
    assert manifest["readiness"] == "missing"
    assert "sector_strength_raw.csv" in manifest["files"]


def test_sector_only_readiness(tmp_path, monkeypatch):
    monkeypatch.setattr(readiness, "ROOT", tmp_path)
    raw_dir = tmp_path / "AmazingData_Store" / "20260626" / "ifind" / "raw"
    _write_csv(
        raw_dir / "sector_strength_raw.csv",
        ["sector_name", "pct", "turnover_rate", "amount_yuan", "dde_net_buy_yuan", "limitup_count", "member_count"],
    )
    payload = readiness.build_payload(["20260626"], write_manifest_files=False)
    assert payload["readiness_by_date"]["20260626"] == "sector_only"
    assert payload["sector_only_ready_dates"] == ["20260626"]
    assert payload["full_ready_dates"] == []


def test_full_ready_readiness(tmp_path, monkeypatch):
    monkeypatch.setattr(readiness, "ROOT", tmp_path)
    raw_dir = tmp_path / "AmazingData_Store" / "20260626" / "ifind" / "raw"
    _write_csv(
        raw_dir / "sector_strength_raw.csv",
        ["sector_name", "pct", "turnover_rate", "amount_yuan", "dde_net_buy_yuan", "limitup_count", "member_count"],
    )
    _write_csv(
        raw_dir / "theme_limitup_raw.csv",
        ["theme_name", "limitup_count", "second_board_count", "third_board_count", "highest_board"],
    )
    _write_csv(
        raw_dir / "limitup_ladder_raw.csv",
        ["code", "name", "board_count", "theme", "group", "limitup_time"],
    )
    payload = readiness.build_payload(["20260626"], write_manifest_files=False)
    assert payload["readiness_by_date"]["20260626"] == "full_ready"
    assert payload["full_ready_dates"] == ["20260626"]
    assert "ready_for_market_structure_snapshot_rebuild" in payload["recommended_actions"]


def test_required_fields_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(readiness, "ROOT", tmp_path)
    raw_dir = tmp_path / "AmazingData_Store" / "20260626" / "ifind" / "raw"
    _write_csv(raw_dir / "sector_strength_raw.csv", ["sector_name", "pct"])
    payload = readiness.build_payload(["20260626"], write_manifest_files=False)
    missing = payload["required_fields_missing_by_date"]["20260626"]["sector_strength_raw.csv"]
    assert "amount_yuan" in missing
    assert "fix_raw_schema_fields" in payload["recommended_actions"]


def test_theme_only_and_ladder_only_do_not_become_full_ready(tmp_path, monkeypatch):
    monkeypatch.setattr(readiness, "ROOT", tmp_path)
    raw_dir = tmp_path / "AmazingData_Store" / "20260626" / "ifind" / "raw"
    _write_csv(
        raw_dir / "theme_limitup_raw.csv",
        ["theme_name", "limitup_count", "second_board_count", "third_board_count", "highest_board"],
    )
    payload = readiness.build_payload(["20260626"], write_manifest_files=False)
    assert payload["readiness_by_date"]["20260626"] == "theme_only"

    raw_dir.joinpath("theme_limitup_raw.csv").unlink()
    _write_csv(
        raw_dir / "limitup_ladder_raw.csv",
        ["code", "name", "board_count", "theme", "group", "limitup_time"],
    )
    payload = readiness.build_payload(["20260626"], write_manifest_files=False)
    assert payload["readiness_by_date"]["20260626"] == "ladder_only"


def test_summary_conclusions_present(tmp_path, monkeypatch):
    monkeypatch.setattr(readiness, "ROOT", tmp_path)
    payload = readiness.build_payload(["20260626"], write_manifest_files=False)
    assert "do_not_fabricate_snapshot" in payload["conclusion"]
    assert "keep_cp_rules_unchanged" in payload["conclusion"]
