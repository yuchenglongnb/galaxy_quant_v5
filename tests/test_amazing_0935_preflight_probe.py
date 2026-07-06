import csv
import json
import subprocess
from pathlib import Path

from scripts import amazing_0935_preflight_probe as worker
from scripts import run_0935_preflight_probe as runner


def _write_candidates(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "code", "name"])
        writer.writeheader()
        writer.writerow({"date": "20260703", "code": "000001.SZ", "name": "sample_a"})
        writer.writerow({"date": "20260703", "code": "000002.SZ", "name": "sample_b"})


def test_preflight_stage_and_done_markers(capsys):
    worker.emit_stage("process_start", "ok")
    worker.emit_done({"status": "ok", "stages": []})
    out = capsys.readouterr().out
    assert worker.STAGE_MARKER in out
    assert worker.DONE_MARKER in out


def test_import_only_mocked_success(monkeypatch):
    monkeypatch.setattr(worker, "emit_stage", lambda stage, status="ok", **extra: {"stage": stage, "status": status, **extra})
    payload = worker.run({"date": "20260703", "mode": "import-only", "codes": ["000001.SZ"], "max_codes": 1})
    assert payload["status"] == "ok"
    assert payload["first_failing_stage"] == ""
    assert [stage["stage"] for stage in payload["stages"]] == [
        "process_start",
        "repo_sys_path",
        "import_project_helpers",
        "load_login_config",
    ]


def test_login_only_mocked_failure(monkeypatch):
    def fake_load(*_args, **_kwargs):
        return {
            "ready": False,
            "config_source": "missing",
            "username_present": False,
            "password_present": False,
            "host_present": False,
            "port_present": False,
        }

    monkeypatch.setattr(worker, "emit_stage", lambda stage, status="ok", **extra: {"stage": stage, "status": status, **extra})
    monkeypatch.setattr("core.amazing_login_config.load_login_config", fake_load)
    payload = worker.run({"date": "20260703", "mode": "login-only", "codes": ["000001.SZ"], "max_codes": 1})
    assert payload["status"] == "failed"
    assert payload["first_failing_stage"] in {"login", "import_amazingdata"}


def test_snapshot_preflight_mocked_success(monkeypatch):
    class FakeMarket:
        def query_snapshot(self, *_args, **_kwargs):
            return {"000001.SZ": [{"code": "000001.SZ", "trade_time": "2026-07-03 09:35:00", "open": "10", "last": "10.2"}]}

    class FakeAD:
        class constant:
            class Period:
                min1 = type("P", (), {"value": "1m"})()

        @staticmethod
        def login(*_args, **_kwargs):
            return None

        @staticmethod
        def logout(_username):
            return None

        @staticmethod
        def MarketData(_calendar):
            return FakeMarket()

    monkeypatch.setattr(worker, "emit_stage", lambda stage, status="ok", **extra: {"stage": stage, "status": status, **extra})
    monkeypatch.setattr("core.amazing_login_config.load_login_config", lambda **_kwargs: {"ready": True, "username": "u", "password": "p", "host": "h", "port": "1", "config_source": "env", "username_present": True, "password_present": True, "host_present": True, "port_present": True})
    monkeypatch.setitem(__import__("sys").modules, "AmazingData", FakeAD)
    monkeypatch.setattr("core.calendar_helper.CalendarHelper.generate_workday_calendar", lambda days=60: [])
    monkeypatch.setattr("scripts.collect_0935_feedback._snapshot_result_rows", lambda *_args, **_kwargs: [{"code": "000001.SZ", "trade_time": "2026-07-03 09:35:00", "open": "10", "last": "10.2"}])
    payload = worker.run({"date": "20260703", "mode": "snapshot-preflight", "codes": ["000001.SZ"], "max_codes": 1})
    assert payload["status"] == "ok"
    assert payload["row_count"] == 1
    assert any(stage["stage"] == "normalize_rows" for stage in payload["stages"])


def test_min1_preflight_mocked_success(monkeypatch):
    class FakeMarket:
        def query_kline(self, *_args, **_kwargs):
            return {"000001.SZ": [{"code": "000001.SZ", "kline_time": "2026-07-03 09:35:00", "open": "10", "close": "9.9"}]}

    class FakeAD:
        class constant:
            class Period:
                min1 = type("P", (), {"value": "1m"})()

        @staticmethod
        def login(*_args, **_kwargs):
            return None

        @staticmethod
        def logout(_username):
            return None

        @staticmethod
        def MarketData(_calendar):
            return FakeMarket()

    monkeypatch.setattr(worker, "emit_stage", lambda stage, status="ok", **extra: {"stage": stage, "status": status, **extra})
    monkeypatch.setattr("core.amazing_login_config.load_login_config", lambda **_kwargs: {"ready": True, "username": "u", "password": "p", "host": "h", "port": "1", "config_source": "env", "username_present": True, "password_present": True, "host_present": True, "port_present": True})
    monkeypatch.setitem(__import__("sys").modules, "AmazingData", FakeAD)
    monkeypatch.setattr("core.calendar_helper.CalendarHelper.generate_workday_calendar", lambda days=60: [])
    monkeypatch.setattr("scripts.collect_0935_feedback._kline_result_rows", lambda *_args, **_kwargs: [{"code": "000001.SZ", "kline_time": "2026-07-03 09:35:00", "open": "10", "close": "9.9"}])
    payload = worker.run({"date": "20260703", "mode": "min1-preflight", "codes": ["000001.SZ"], "max_codes": 1})
    assert payload["status"] == "ok"
    assert payload["row_count"] == 1


def test_parent_handles_missing_final_marker(tmp_path, monkeypatch):
    candidate = tmp_path / "reports" / "validation" / "daily" / "20260703" / "signal_detail.csv"
    _write_candidates(candidate)

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="sdk noise", stderr="secret=abc")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    payload = runner.run_probe("20260703", "snapshot-preflight", candidate, max_codes=1)
    assert payload["status"] == "failed"
    assert payload["first_failing_stage"] == "preflight_done_marker_missing"
    assert payload["stderr_sanitized"] == "sensitive_error_redacted"


def test_parent_writes_sanitized_json_md_report(tmp_path, monkeypatch):
    candidate = tmp_path / "reports" / "validation" / "daily" / "20260703" / "signal_detail.csv"
    _write_candidates(candidate)
    done = {"status": "ok", "mode": "import-only", "stages": [{"stage": "process_start", "status": "ok"}], "row_count": 0, "rows": []}

    def fake_run(*_args, **_kwargs):
        stdout = f"{runner.STAGE_MARKER}\n{{\"stage\":\"process_start\",\"status\":\"ok\"}}\n{runner.DONE_MARKER}\n{json.dumps(done)}\n"
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    payload = runner.main([
        "--date",
        "20260703",
        "--candidate-source",
        str(candidate),
        "--mode",
        "import-only",
        "--output-dir",
        str(tmp_path / "out"),
    ])
    assert payload["status"] == "ok"
    combined = (tmp_path / "out" / "amazing_0935_preflight_20260703.json").read_text(encoding="utf-8")
    combined += (tmp_path / "out" / "amazing_0935_preflight_20260703.md").read_text(encoding="utf-8")
    for forbidden in ["password", "token", "secret", "host=", "port="]:
        assert forbidden not in combined.lower()


def test_no_artifact_write_in_preflight_only_mode(tmp_path, monkeypatch):
    candidate = tmp_path / "reports" / "validation" / "daily" / "20260703" / "signal_detail.csv"
    _write_candidates(candidate)

    def fake_run(*_args, **_kwargs):
        stdout = f"{runner.DONE_MARKER}\n{{\"status\":\"ok\",\"mode\":\"import-only\",\"stages\":[],\"rows\":[],\"row_count\":0}}\n"
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    runner.main([
        "--date",
        "20260703",
        "--candidate-source",
        str(candidate),
        "--mode",
        "import-only",
        "--output-dir",
        str(tmp_path / "out"),
    ])
    assert not (tmp_path / "AmazingData_Store").exists()


def test_no_lesson_pattern_registry_writes(tmp_path, monkeypatch):
    candidate = tmp_path / "reports" / "validation" / "daily" / "20260703" / "signal_detail.csv"
    _write_candidates(candidate)

    def fake_run(*_args, **_kwargs):
        stdout = f"{runner.DONE_MARKER}\n{{\"status\":\"ok\",\"mode\":\"import-only\",\"stages\":[],\"rows\":[],\"row_count\":0}}\n"
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    runner.main([
        "--date",
        "20260703",
        "--candidate-source",
        str(candidate),
        "--mode",
        "import-only",
        "--output-dir",
        str(tmp_path / "out"),
    ])
    assert not (tmp_path / "reports" / "analysis" / "lessons").exists()
    assert not (tmp_path / "reports" / "analysis" / "patterns").exists()
    assert not (tmp_path / "market_pattern_registry.json").exists()


def test_preflight_accepts_login_style(monkeypatch):
    observed = {}

    def fake_build(_config, login_style):
        observed["login_style"] = login_style
        return (), {}, {"login_style": login_style, "port_type": "int"}

    class FakeAD:
        @staticmethod
        def login(*_args, **_kwargs):
            return None

        @staticmethod
        def logout(_username):
            return None

    monkeypatch.setattr(worker, "emit_stage", lambda stage, status="ok", **extra: {"stage": stage, "status": status, **extra})
    monkeypatch.setattr("core.amazing_login_config.load_login_config", lambda **_kwargs: {"ready": True, "username": "u", "password": "p", "host": "h", "port": "1", "config_source": "env", "username_present": True, "password_present": True, "host_present": True, "port_present": True})
    monkeypatch.setattr("core.amazing_login_client.build_login_invocation", fake_build)
    monkeypatch.setitem(__import__("sys").modules, "AmazingData", FakeAD)
    payload = worker.run({
        "date": "20260703",
        "mode": "login-only",
        "codes": ["000001.SZ"],
        "login_style": "positional-int-port",
    })
    assert payload["status"] == "ok"
    assert observed["login_style"] == "positional-int-port"
