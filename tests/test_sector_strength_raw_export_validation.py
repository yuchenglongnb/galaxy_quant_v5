from pathlib import Path

import scripts.validate_sector_strength_raw_export as validator


def _write_csv(path: Path, columns: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(",".join(columns) + "\n" + ",".join("1" for _ in columns) + "\n", encoding="utf-8")


def test_template_fields_are_complete():
    payload = validator.validate_export("TEMPLATE", validator.TEMPLATE_PATH)
    assert payload["sector_only_ready_candidate"] is True
    assert payload["required_fields_missing"] == []


def test_required_fields_missing_blocks_sector_only(tmp_path):
    raw = tmp_path / "sector.csv"
    _write_csv(raw, ["sector_name", "pct"])
    payload = validator.validate_export("20260626", raw)
    assert payload["sector_only_ready_candidate"] is False
    assert payload["sector_only_blocked"] is True
    assert "amount_yuan" in payload["required_fields_missing"]
    assert "sector_only_blocked" in payload["conclusion"]


def test_required_fields_ready_candidate(tmp_path):
    raw = tmp_path / "sector.csv"
    _write_csv(raw, validator.REQUIRED_FIELDS)
    payload = validator.validate_export("20260626", raw)
    assert payload["sector_only_ready_candidate"] is True
    assert payload["sector_only_blocked"] is False
    assert "sector_only_ready_candidate" in payload["conclusion"]


def test_chinese_column_mapping_suggestions(tmp_path):
    raw = tmp_path / "sector_cn.csv"
    _write_csv(raw, ["板块名称", "涨跌幅", "换手率", "成交额", "DDE净额", "涨停家数", "成分股数量"])
    payload = validator.validate_export("20260626", raw)
    mapping = payload["suggested_column_mapping"]
    assert mapping["板块名称"] == "sector_name"
    assert mapping["涨跌幅"] == "pct"
    assert mapping["DDE净额"] == "dde_net_buy_yuan"
    assert "column_alias_mapping_suggested" in payload["warnings"]


def test_missing_file_does_not_raise(tmp_path):
    payload = validator.validate_export("20260626", tmp_path / "missing.csv")
    assert payload["exists"] is False
    assert payload["sector_only_blocked"] is True
    assert "raw_file_missing" in payload["warnings"]


def test_write_outputs_structure(tmp_path, monkeypatch):
    monkeypatch.setattr(validator, "EVAL_ROOT", tmp_path)
    raw = tmp_path / "sector.csv"
    _write_csv(raw, validator.REQUIRED_FIELDS)
    payload = validator.validate_export("20260626", raw)
    json_path, md_path = validator.write_outputs(payload)
    assert json_path.exists()
    assert md_path.exists()
    assert json_path.name == "sector_strength_raw_export_dry_run_20260626.json"


def test_conclusion_guardrails_present(tmp_path):
    payload = validator.validate_export("20260626", tmp_path / "missing.csv")
    assert "dry_run_only" in payload["conclusion"]
    assert "do_not_fabricate_raw" in payload["conclusion"]
    assert "do_not_fabricate_snapshot" in payload["conclusion"]
    assert "keep_cp_rules_unchanged" in payload["conclusion"]
