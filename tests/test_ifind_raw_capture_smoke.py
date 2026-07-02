import json
from pathlib import Path

import scripts.capture_ifind_market_structure_raw as capture
import scripts.evaluate_ifind_raw_readiness as readiness
import scripts.run_ifind_raw_capture_smoke as smoke


def _write_csv(path: Path, columns: list[str], rows: list[list[str]] | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = ",".join(columns) + "\n"
    for row in rows or [["1" for _ in columns]]:
        body += ",".join(row) + "\n"
    path.write_text(body, encoding="utf-8")


def _patch_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(readiness, "ROOT", tmp_path)
    monkeypatch.setattr(capture, "ROOT", tmp_path)
    monkeypatch.setattr(smoke, "ROOT", tmp_path)
    monkeypatch.setattr(smoke, "EVAL_ROOT", tmp_path / "reports" / "analysis" / "evaluations")


def _patch_metric_calls(monkeypatch):
    monkeypatch.setattr(smoke, "_metric_snapshot", lambda date: {
        "snapshot_missing": 1,
        "evidence_missing_false_positive": 1,
        "exemption_ready_false_positive": 0,
        "rule_gap_false_positive": 0,
    })


def test_raw_missing_smoke_does_not_rebuild_snapshot(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _patch_metric_calls(monkeypatch)
    called = {"rebuild": False}
    monkeypatch.setattr(smoke, "_attempt_snapshot_rebuild", lambda date, status: called.__setitem__("rebuild", True))

    payload = smoke.build_smoke_payload("20260626")

    assert payload["raw_readiness"] == "missing"
    assert payload["snapshot_rebuild_attempted"] is False
    assert payload["auction_replay_attempted"] is False
    assert payload["cp_audit_rerun_attempted"] is False
    assert called["rebuild"] is False
    assert "do_not_fabricate_snapshot" in payload["conclusion"]
    assert "keep_cp_rules_unchanged" in payload["conclusion"]
    assert "snapshot_rebuild_blocked" in payload["conclusion"]


def test_sector_only_smoke_allows_snapshot_rebuild(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _patch_metric_calls(monkeypatch)
    raw_dir = tmp_path / "AmazingData_Store" / "20260626" / "ifind" / "raw"
    _write_csv(
        raw_dir / "sector_strength_raw.csv",
        ["sector_name", "pct", "turnover_rate", "amount_yuan", "dde_net_buy_yuan", "limitup_count", "member_count"],
    )
    monkeypatch.setattr(smoke, "_attempt_snapshot_rebuild", lambda date, status: (True, {"ok": True, "status": status}, []))
    monkeypatch.setattr(smoke, "_run_auction_replay", lambda date: (True, {"ok": True}))
    monkeypatch.setattr(smoke, "_rerun_cp_audits", lambda date: (True, {"ok": True}))

    payload = smoke.build_smoke_payload("20260626")

    assert payload["raw_readiness"] == "sector_only"
    assert payload["snapshot_rebuild_attempted"] is True
    assert payload["snapshot_rebuild_success"] is True
    assert payload["auction_replay_attempted"] is True
    assert payload["cp_audit_rerun_attempted"] is True
    assert "sector_only_ready" in payload["conclusion"]
    assert "snapshot_rebuild_allowed" in payload["conclusion"]


def test_full_ready_smoke_allows_complete_rebuild(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _patch_metric_calls(monkeypatch)
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
    monkeypatch.setattr(smoke, "_attempt_snapshot_rebuild", lambda date, status: (True, {"ok": True, "status": status}, []))
    monkeypatch.setattr(smoke, "_run_auction_replay", lambda date: (True, {"ok": True}))
    monkeypatch.setattr(smoke, "_rerun_cp_audits", lambda date: (True, {"ok": True}))

    payload = smoke.build_smoke_payload("20260626")

    assert payload["raw_readiness"] == "full_ready"
    assert payload["snapshot_rebuild_attempted"] is True
    assert payload["snapshot_rebuild_success"] is True
    assert "full_ready" in payload["conclusion"]


def test_manifest_and_report_structure_are_stable(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _patch_metric_calls(monkeypatch)

    payload = smoke.build_smoke_payload("20260626")
    json_path, md_path = smoke.write_outputs(payload)
    written = json.loads(json_path.read_text(encoding="utf-8"))

    assert json_path.exists()
    assert md_path.exists()
    assert written["date"] == "20260626"
    assert "raw_files" in written
    assert "before_after" in written
    assert Path(written["manifest_path"]).name == "raw_manifest.json"


def test_missing_theme_and_ladder_do_not_become_full_ready(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _patch_metric_calls(monkeypatch)
    raw_dir = tmp_path / "AmazingData_Store" / "20260626" / "ifind" / "raw"
    _write_csv(
        raw_dir / "sector_strength_raw.csv",
        ["sector_name", "pct", "turnover_rate", "amount_yuan", "dde_net_buy_yuan", "limitup_count", "member_count"],
    )
    monkeypatch.setattr(smoke, "_attempt_snapshot_rebuild", lambda date, status: (True, {}, []))
    monkeypatch.setattr(smoke, "_run_auction_replay", lambda date: (True, {}))
    monkeypatch.setattr(smoke, "_rerun_cp_audits", lambda date: (True, {}))

    payload = smoke.build_smoke_payload("20260626")

    assert payload["raw_readiness"] == "sector_only"
    assert payload["raw_readiness"] != "full_ready"
