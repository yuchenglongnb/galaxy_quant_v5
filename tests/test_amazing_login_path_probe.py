import json
import subprocess
from unittest import mock

from scripts import amazing_login_path_probe as probe
from scripts import run_amazing_login_path_probe as runner


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


def test_login_style_payload_does_not_echo_credentials(monkeypatch):
    fake_ad = mock.Mock()
    monkeypatch.setattr("core.amazing_login_config.load_login_config", lambda **_kwargs: _ready_config())
    monkeypatch.setitem(__import__("sys").modules, "AmazingData", fake_ad)
    payload = probe.run_style("style_c_direct_keyword_args")
    combined = json.dumps(payload, ensure_ascii=False)
    assert payload["status"] == "ok"
    for forbidden in ["token", "secret", "host=", "port=", "\"u\"", "\"p\"", "\"h\""]:
        assert forbidden not in combined.lower()


def test_system_exit_zero_becomes_ambiguous_success(monkeypatch):
    fake_ad = mock.Mock()
    fake_ad.login.side_effect = SystemExit(0)
    monkeypatch.setattr("core.amazing_login_config.load_login_config", lambda **_kwargs: _ready_config())
    monkeypatch.setitem(__import__("sys").modules, "AmazingData", fake_ad)
    payload = probe.run_style("style_a_build_login_invocation_keyword_int_port")
    assert payload["status"] == "system_exit"
    assert payload["system_exit_code"] == 0
    assert payload["ambiguous_success"] is True
    assert payload["login_returned"] is False


def test_failed_login_style_mocked(monkeypatch):
    fake_ad = mock.Mock()
    fake_ad.login.side_effect = RuntimeError("login fail")
    monkeypatch.setattr("core.amazing_login_config.load_login_config", lambda **_kwargs: _ready_config())
    monkeypatch.setitem(__import__("sys").modules, "AmazingData", fake_ad)
    payload = probe.run_style("style_d_positional_args")
    assert payload["status"] == "failed"
    assert payload["ambiguous_success"] is False


def test_successful_existing_helper_mocked(monkeypatch):
    fake_ad = mock.Mock()
    monkeypatch.setattr("core.amazing_login_config.load_login_config", lambda **_kwargs: _ready_config())
    monkeypatch.setattr("core.amazing_login_client.load_login_config", lambda: _ready_config())
    monkeypatch.setitem(__import__("sys").modules, "AmazingData", fake_ad)
    payload = probe.run_style("style_e_existing_project_helper_exact")
    assert payload["status"] == "ok"
    assert payload["login_returned"] is True


def test_runner_writes_sanitized_json_md(tmp_path, monkeypatch):
    done = {
        "style": "style_a_build_login_invocation_keyword_int_port",
        "status": "system_exit",
        "error_type": "SystemExit",
        "sanitized_error": "0",
        "system_exit_code": 0,
        "ambiguous_success": True,
        "login_returned": False,
        "logout_attempted": False,
        "config_status": {"ready": True, "username_present": True, "password_present": True, "host_present": True, "port_present": True},
        "notes": [],
    }

    def fake_run(*_args, **_kwargs):
        stdout = f"{probe.JSON_BEGIN}\n{json.dumps(done)}\n{probe.JSON_END}\n"
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="password=abc")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    payload = runner.main([
        "--styles",
        "style_a_build_login_invocation_keyword_int_port",
        "--output-dir",
        str(tmp_path),
    ])
    assert payload["summary"]["diagnosis"] == "all_available_styles_system_exit_0_or_failed"
    combined = (tmp_path / "amazing_login_path_probe.json").read_text(encoding="utf-8")
    combined += (tmp_path / "amazing_login_path_probe.md").read_text(encoding="utf-8")
    assert "password=abc" not in combined
    assert "sensitive_error_redacted" in combined


def test_runner_timeout_is_structured(monkeypatch):
    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="worker", timeout=1)

    monkeypatch.setattr(runner.subprocess, "run", timeout)
    payload = runner.run_style("style_a_build_login_invocation_keyword_int_port", worker_timeout=1)
    assert payload["status"] == "failed"
    assert payload["error_type"] == "TimeoutExpired"
