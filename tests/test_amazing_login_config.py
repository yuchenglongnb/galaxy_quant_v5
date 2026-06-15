import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from core import amazing_login_config as login_config
from scripts import check_amazingdata_login as login_check


class AmazingLoginConfigTest(unittest.TestCase):
    def test_env_config_ready_when_all_values_present(self):
        config = login_config.load_login_config(
            env={
                "AD_USERNAME": "u",
                "AD_PASSWORD": "p",
                "AD_HOST": "h",
                "AD_PORT": "8600",
            }
        )
        self.assertTrue(config["ready"])
        self.assertEqual(config["config_source"], "env")

    def test_env_config_not_ready_when_missing_values(self):
        config = login_config.load_login_config(env={})
        self.assertFalse(config["ready"])
        self.assertEqual(config["config_source"], "missing")

    def test_dotenv_can_be_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            dotenv = Path(tmp) / ".env"
            dotenv.write_text(
                "AD_USERNAME=user\nAD_PASSWORD=pass\nAD_HOST=host\nAD_PORT=8600\n",
                encoding="utf-8",
            )
            config = login_config.load_login_config(env={}, dotenv_path=dotenv)
        self.assertTrue(config["ready"])
        self.assertEqual(config["config_source"], "dotenv")

    @mock.patch.object(login_config, "_read_windows_persistent_env")
    def test_windows_user_env_can_be_loaded(self, windows_env_mock):
        windows_env_mock.side_effect = [
            {
                "AD_USERNAME": "user",
                "AD_PASSWORD": "pass",
                "AD_HOST": "host",
                "AD_PORT": "8600",
            },
            {},
        ]
        config = login_config.load_login_config(env={})
        self.assertTrue(config["ready"])
        self.assertEqual(config["config_source"], "windows_user_env")

    def test_missing_dotenv_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = login_config.load_login_config(env={}, dotenv_path=Path(tmp) / ".env")
        self.assertFalse(config["ready"])

    def test_sanitize_does_not_output_sensitive_values(self):
        config = {
            "username": "alice",
            "password": "secret",
            "host": "1.2.3.4",
            "port": "8600",
        }
        text = "login fail host=1.2.3.4 user=alice password=secret"
        sanitized = login_config.sanitize_text(text, config)
        self.assertNotIn("alice", sanitized)
        self.assertNotIn("secret", sanitized)
        self.assertNotIn("1.2.3.4", sanitized)

    @mock.patch.object(login_check, "load_login_config", return_value={"ready": False, "config_source": "missing", "username_present": False, "password_present": False, "host_present": False, "port_present": False})
    def test_login_check_config_missing_does_not_call_login(self, _config_mock):
        result = login_check.perform_login_check()
        self.assertEqual(result["login_status"], "config_missing")
        self.assertFalse(result["config_status"]["ready"])

    @mock.patch.object(login_check, "load_login_config")
    @mock.patch.object(login_check, "bootstrap_amazingdata_client")
    @mock.patch.object(login_check, "logout_amazingdata_client")
    def test_login_check_success_with_mocked_amazingdata(self, logout_mock, bootstrap_mock, load_mock):
        load_mock.return_value = {
            "username": "u",
            "password": "p",
            "host": "h",
            "port": "8600",
            "config_source": "env",
            "username_present": True,
            "password_present": True,
            "host_present": True,
            "port_present": True,
            "ready": True,
        }
        fake_module = types.SimpleNamespace()
        bootstrap_mock.return_value = (fake_module, load_mock.return_value)
        result = login_check.perform_login_check()
        self.assertEqual(result["login_status"], "success")
        logout_mock.assert_called_once()

    def test_json_markdown_outputs_do_not_contain_raw_secrets(self):
        payload = {
            "created_at": "2026-06-15T22:00:00",
            "elapsed_sec": 0.1,
            "login_status": "login_failed",
            "error_type": "login_failed",
            "error": "login_failed: tgw_init_failed",
            "config_status": {
                "config_source": "env",
                "username_present": True,
                "password_present": True,
                "host_present": True,
                "port_present": True,
                "ready": True,
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(login_check, "EVAL_DIR", Path(tmp)):
                json_path, md_path = login_check.write_outputs(payload)
                json_text = json_path.read_text(encoding="utf-8")
                md_text = md_path.read_text(encoding="utf-8")
        self.assertNotIn("AD_PASSWORD", json_text)
        self.assertNotIn("AD_PASSWORD", md_text)


if __name__ == "__main__":
    unittest.main()
