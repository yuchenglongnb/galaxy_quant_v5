import csv
from pathlib import Path

import scripts.quarantine_t1backtest_bad_rows as quarantine


def _write_malformed(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "signal_category", "name"])
        writer.writerow(["20260701", "trend", "A"])
        writer.writerow(["20260701", "trend", "B", "extra"])


def test_malformed_row_enters_bad_rows(tmp_path):
    path = tmp_path / "validation.csv"
    _write_malformed(path)

    payload = quarantine.build_payload(path, dry_run=True)

    assert payload["malformed_row_count"] == 1
    assert payload["bad_rows"][0]["line_number"] == 3
    assert payload["original_file_modified"] is False


def test_quarantine_dry_run_does_not_write_files(tmp_path, monkeypatch):
    path = tmp_path / "validation.csv"
    _write_malformed(path)
    quarantine_dir = tmp_path / "quarantine"
    monkeypatch.setattr(quarantine, "QUARANTINE_ROOT", quarantine_dir)

    payload = quarantine.build_payload(path, dry_run=True)

    assert payload["dry_run"] is True
    assert payload["clean_temp_copy_written"] is False
    assert not quarantine_dir.exists()


def test_write_temp_copy_excludes_malformed_rows_without_overwriting(tmp_path, monkeypatch):
    path = tmp_path / "validation.csv"
    _write_malformed(path)
    original = path.read_text(encoding="utf-8-sig")
    quarantine_dir = tmp_path / "quarantine"
    monkeypatch.setattr(quarantine, "QUARANTINE_ROOT", quarantine_dir)

    payload = quarantine.build_payload(path, dry_run=False, write_temp_copy=True)

    assert payload["clean_temp_copy_written"] is True
    assert payload["bad_rows_file_written"] is True
    assert path.read_text(encoding="utf-8-sig") == original
    clean_path = quarantine_dir / "auction_signal_validation.clean.csv"
    with clean_path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    assert len(rows) == 2
    assert rows[1] == ["20260701", "trend", "A"]
