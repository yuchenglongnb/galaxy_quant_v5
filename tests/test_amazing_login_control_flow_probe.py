import json
import subprocess
from unittest import mock

from scripts import amazing_login_control_flow_probe as probe
from scripts import run_amazing_login_control_flow_probe as runner


def _ready_config():
    return {
        "username": "u",
        "password": "p",
        "host": "h",
        "port": "8600",
        "ready": True,
        "config_source": "env",
        "username_present": True,
        "password_present": True,
        "host_present": True,
        "port_present": True,
    }


def test_system_exit_zero_not_safe_to_query_by_default(monkeypatch):
    fake_ad = mock.Mock()
    fake_ad.login.side_effect = SystemExit(0)
    monkeypatch.setattr("core.amazing_login_config.load_login_config", lambda **_kwargs: _ready_config())
    monkeypatch.setitem(__import__("sys").modules, "AmazingData", fake_ad)
    payload = probe.run_strategy("catch_system_exit_continue")
    assert payload["status"] == "system_exit"
    assert payload["system_exit_code"] == 0
    assert payload["safe_to_query"] is False


def test_logout_after_system_exit_mocked(monkeypatch):
    fake_ad = mock.Mock()
    fake_ad.login.side_effect = SystemExit(0)
    monkeypatch.setattr("core.amazing_login_config.load_login_config", lambda **_kwargs: _ready_config())
    monkeypatch.setitem(__import__("sys").modules, "AmazingData", fake_ad)
    payload = probe.run_strategy("catch_system_exit_then_logout")
    assert payload["status"] == "system_exit"
    assert payload["post_system_exit_checks"]["logout_callable"] is True
    assert payload["post_system_exit_checks"]["logout_returned"] is True
    assert payload["safe_to_query"] is False


def test_successful_login_sets_safe_to_query(monkeypatch):
    fake_ad = mock.Mock()
    monkeypatch.setattr("core.amazing_login_config.load_login_config", lambda **_kwargs: _ready_config())
    monkeypatch.setitem(__import__("sys").modules, "AmazingData", fake_ad)
    payload = probe.run_strategy("catch_system_exit_continue")
    assert payload["status"] == "ok"
    assert payload["login_returned"] is True
    assert payload["safe_to_query"] is True


def test_subprocess_exit_code_only_missing_marker(monkeypatch):
    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    payload = runner.run_strategy("subprocess_exit_code_only")
    assert payload["status"] == "system_exit"
    assert payload["safe_to_query"] is False
    assert "process_exited_without_framed_payload" in payload["notes"]


def test_runner_writes_sanitized_report(tmp_path, monkeypatch):
    done = {
        "strategy": "catch_system_exit_continue",
        "status": "system_exit",
        "system_exit_code": 0,
        "login_returned": False,
        "safe_to_query": False,
        "permission_hypothesis": "possible",
        "post_system_exit_checks": {"logout_callable": True, "logout_returned": False, "session_state_observable": False},
        "notes": ["system_exit_0_is_not_safe_to_query_by_default"],
    }

    def fake_run(*_args, **_kwargs):
        stdout = f"{probe.JSON_BEGIN}\n{json.dumps(done)}\n{probe.JSON_END}\n"
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="token=abc")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    payload = runner.main(["--strategies", "catch_system_exit_continue", "--output-dir", str(tmp_path)])
    assert payload["summary"]["safe_to_query"] is False
    combined = (tmp_path / "amazing_login_control_flow_probe.json").read_text(encoding="utf-8")
    combined += (tmp_path / "amazing_login_control_flow_probe.md").read_text(encoding="utf-8")
    assert "token=abc" not in combined
    assert "sensitive_error_redacted" in combined


def test_provider_fallback_summary_when_not_safe():
    payload = runner.summarize([
        {
            "strategy": "catch_system_exit_continue",
            "status": "system_exit",
            "safe_to_query": False,
        }
    ])
    assert payload["amazingdata_online_path"] == "blocked"
    assert payload["provider_fallback_decision"] == "prepare_ths_mcp_fallback"


def test_no_sensitive_fields_in_permission_hypothesis():
    payload = probe.run_strategy("vendor_permission_hypothesis")
    combined = json.dumps(payload, ensure_ascii=False).lower()
    assert payload["permission_hypothesis"] == "plausible_not_proven"
    for forbidden in ["token=", "key=", "cookie=", "host=", "port=", "username="]:
        assert forbidden not in combined
