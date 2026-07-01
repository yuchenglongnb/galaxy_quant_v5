from pathlib import Path

import scripts.evaluate_ifind_raw_readiness as readiness
import scripts.run_sector_only_snapshot_rebuild_smoke as smoke


def _write_csv(path: Path, columns: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(",".join(columns) + "\n" + ",".join("1" for _ in columns) + "\n", encoding="utf-8")


def _patch_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(readiness, "ROOT", tmp_path)
    monkeypatch.setattr(smoke, "ROOT", tmp_path)
    monkeypatch.setattr(smoke, "EVAL_ROOT", tmp_path / "reports" / "analysis" / "evaluations")


def _patch_metrics(monkeypatch):
    monkeypatch.setattr(smoke, "_metric_snapshot", lambda date: {
        "snapshot_missing": 1,
        "leading_cluster_snapshot_missing": 1,
        "sector_breadth_snapshot_missing": 1,
        "evidence_missing_false_positive": 1,
        "exemption_ready_false_positive": 0,
        "rule_gap_false_positive": 0,
        "builder_attachment_missing": 0,
        "remaining_missing_reasons": {"snapshot_missing": 1},
    })


def _write_sector_raw(tmp_path):
    raw_dir = tmp_path / "AmazingData_Store" / "20260626" / "ifind" / "raw"
    _write_csv(
        raw_dir / "sector_strength_raw.csv",
        ["sector_name", "pct", "turnover_rate", "amount_yuan", "dde_net_buy_yuan", "limitup_count", "member_count"],
    )


def _write_full_raw(tmp_path):
    raw_dir = tmp_path / "AmazingData_Store" / "20260626" / "ifind" / "raw"
    _write_sector_raw(tmp_path)
    _write_csv(
        raw_dir / "theme_limitup_raw.csv",
        ["theme_name", "limitup_count", "second_board_count", "third_board_count", "highest_board"],
    )
    _write_csv(
        raw_dir / "limitup_ladder_raw.csv",
        ["code", "name", "board_count", "theme", "group", "limitup_time"],
    )


def test_raw_missing_does_not_rebuild_snapshot(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _patch_metrics(monkeypatch)
    called = {"rebuild": False}
    monkeypatch.setattr(smoke, "_attempt_sector_snapshot_rebuild", lambda date: called.__setitem__("rebuild", True))

    payload = smoke.build_smoke_payload("20260626")

    assert payload["raw_readiness_before"] == "missing"
    assert payload["snapshot_rebuild_attempted"] is False
    assert payload["auction_replay_attempted"] is False
    assert payload["cp_audit_rerun_attempted"] is False
    assert called["rebuild"] is False
    assert "do_not_fabricate_snapshot" in payload["conclusion"]
    assert "keep_cp_rules_unchanged" in payload["conclusion"]
    assert "snapshot_rebuild_blocked" in payload["conclusion"]


def test_sector_only_allows_sector_snapshot_rebuild(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _patch_metrics(monkeypatch)
    _write_sector_raw(tmp_path)
    monkeypatch.setattr(smoke, "_attempt_sector_snapshot_rebuild", lambda date: (True, {"sector_only": True}, []))
    monkeypatch.setattr(smoke, "_run_auction_replay", lambda date: (True, {"ok": True}))
    monkeypatch.setattr(smoke, "_rerun_cp_audits", lambda date: (True, {"ok": True}))

    payload = smoke.build_smoke_payload("20260626")

    assert payload["raw_readiness_before"] == "sector_only"
    assert payload["snapshot_rebuild_attempted"] is True
    assert payload["snapshot_rebuild_success"] is True
    assert payload["auction_replay_success"] is True
    assert payload["cp_audit_rerun_success"] is True
    assert "sector_only_ready" in payload["conclusion"]
    assert "snapshot_rebuild_success" in payload["conclusion"]
    assert "cp_audit_rerun_success" in payload["conclusion"]


def test_full_ready_also_allows_sector_snapshot_rebuild(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _patch_metrics(monkeypatch)
    _write_full_raw(tmp_path)
    monkeypatch.setattr(smoke, "_attempt_sector_snapshot_rebuild", lambda date: (True, {"sector_only": True}, []))
    monkeypatch.setattr(smoke, "_run_auction_replay", lambda date: (True, {}))
    monkeypatch.setattr(smoke, "_rerun_cp_audits", lambda date: (True, {}))

    payload = smoke.build_smoke_payload("20260626")

    assert payload["raw_readiness_before"] == "full_ready"
    assert payload["snapshot_rebuild_attempted"] is True
    assert payload["snapshot_rebuild_success"] is True
    assert "full_ready" in payload["conclusion"]


def test_auction_replay_not_attempted_until_rebuild_success(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _patch_metrics(monkeypatch)
    _write_sector_raw(tmp_path)
    monkeypatch.setattr(smoke, "_attempt_sector_snapshot_rebuild", lambda date: (False, {"error": "bad raw"}, ["sector_snapshot_rebuild_failed"]))

    payload = smoke.build_smoke_payload("20260626")

    assert payload["snapshot_rebuild_attempted"] is True
    assert payload["snapshot_rebuild_success"] is False
    assert payload["auction_replay_attempted"] is False
    assert payload["cp_audit_rerun_attempted"] is False
    assert "sector_snapshot_rebuild_failed" in payload["warnings"]


def test_report_structure_is_stable(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _patch_metrics(monkeypatch)

    payload = smoke.build_smoke_payload("20260626")
    json_path, md_path = smoke.write_outputs(payload)

    assert json_path.exists()
    assert md_path.exists()
    assert "before_after" in payload
    assert "remaining_missing_reasons" in payload
    for key in [
        "snapshot_missing",
        "leading_cluster_snapshot_missing",
        "sector_breadth_snapshot_missing",
        "evidence_missing_false_positive",
        "exemption_ready_false_positive",
        "rule_gap_false_positive",
        "builder_attachment_missing",
    ]:
        assert key in payload["before_after"]
