import unittest
from unittest import mock

from core import amazing_login_client as login_client


class AmazingLoginClientTest(unittest.TestCase):
    def test_build_login_invocation_positional_str_port(self):
        args, kwargs, meta = login_client.build_login_invocation(
            {"username": "u", "password": "p", "host": "h", "port": "8600"},
            "positional-str-port",
        )
        self.assertEqual(args, ("u", "p", "h", "8600"))
        self.assertEqual(kwargs, {})
        self.assertEqual(meta["port_type"], "str")

    def test_build_login_invocation_positional_int_port(self):
        args, kwargs, meta = login_client.build_login_invocation(
            {"username": "u", "password": "p", "host": "h", "port": "8600"},
            "positional-int-port",
        )
        self.assertEqual(args, ("u", "p", "h", 8600))
        self.assertEqual(kwargs, {})
        self.assertEqual(meta["port_type"], "int")

    def test_build_login_invocation_keyword_str_port(self):
        args, kwargs, meta = login_client.build_login_invocation(
            {"username": "u", "password": "p", "host": "h", "port": "8600"},
            "keyword-str-port",
        )
        self.assertEqual(args, ())
        self.assertEqual(kwargs["port"], "8600")
        self.assertEqual(meta["port_type"], "str")

    @mock.patch.object(login_client, "load_login_config", return_value={"ready": False})
    def test_bootstrap_returns_config_missing(self, _config_mock):
        with self.assertRaises(login_client.AmazingLoginError) as ctx:
            login_client.bootstrap_amazingdata_client()
        self.assertEqual(ctx.exception.status, "bootstrap_failed")
        self.assertEqual(ctx.exception.stage, "load_config")
        self.assertEqual(ctx.exception.error_type, "config_missing")

    @mock.patch.object(login_client, "load_login_config")
    def test_bootstrap_returns_login_failed(self, load_mock):
        load_mock.return_value = {
            "username": "u",
            "password": "p",
            "host": "h",
            "port": "8600",
            "ready": True,
        }
        fake_ad = mock.Mock()
        fake_ad.login.side_effect = RuntimeError("login fail")
        with mock.patch.dict("sys.modules", {"AmazingData": fake_ad}):
            with self.assertRaises(login_client.AmazingLoginError) as ctx:
                login_client.bootstrap_amazingdata_client()
        self.assertEqual(ctx.exception.status, "login_failed")
        self.assertEqual(ctx.exception.stage, "login")
        self.assertEqual(ctx.exception.error_type, "login_failed")

    @mock.patch.object(login_client, "load_login_config")
    def test_bootstrap_classifies_system_exit_during_login(self, load_mock):
        load_mock.return_value = {
            "username": "u",
            "password": "p",
            "host": "h",
            "port": "8600",
            "ready": True,
        }
        fake_ad = mock.Mock()
        fake_ad.login.side_effect = SystemExit(0)
        with mock.patch.dict("sys.modules", {"AmazingData": fake_ad}):
            with self.assertRaises(login_client.AmazingLoginError) as ctx:
                login_client.bootstrap_amazingdata_client()
        self.assertEqual(ctx.exception.status, "login_failed")
        self.assertEqual(ctx.exception.stage, "login")
        self.assertEqual(ctx.exception.error_type, "system_exit_during_login")

    @mock.patch.object(login_client, "load_login_config")
    def test_bootstrap_uses_keyword_login_arguments(self, load_mock):
        load_mock.return_value = {
            "username": "u",
            "password": "p",
            "host": "h",
            "port": "8600",
            "ready": True,
        }
        fake_ad = mock.Mock()
        with mock.patch.dict("sys.modules", {"AmazingData": fake_ad}):
            login_client.bootstrap_amazingdata_client()
        fake_ad.login.assert_called_once_with(
            username="u",
            password="p",
            host="h",
            port=8600,
        )

    @mock.patch.object(login_client, "load_login_config")
    def test_trace_login_behavior_records_return_semantics(self, load_mock):
        load_mock.return_value = {
            "username": "u",
            "password": "p",
            "host": "h",
            "port": "8600",
            "ready": True,
            "config_source": "env",
        }
        fake_ad = mock.Mock()
        with mock.patch.dict("sys.modules", {"AmazingData": fake_ad}):
            trace = login_client.trace_amazingdata_login("keyword-int-port")
        self.assertTrue(trace["login_start"])
        self.assertTrue(trace["login_returned"])
        self.assertTrue(trace["after_login_marker_reached"])
        self.assertEqual(trace["port_type"], "int")


if __name__ == "__main__":
    unittest.main()
