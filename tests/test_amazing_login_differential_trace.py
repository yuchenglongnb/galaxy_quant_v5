import unittest
from unittest import mock

import scripts.check_amazingdata_login as login_check_module


class AmazingLoginDifferentialTraceTest(unittest.TestCase):
    @mock.patch.object(login_check_module, "trace_amazingdata_login")
    @mock.patch.object(login_check_module.subprocess, "run")
    def test_run_login_style_differential_collects_styles(self, run_mock, trace_mock):
        trace_mock.side_effect = [
            {
                "login_style": "positional-str-port",
                "status": "success",
                "login_returned": True,
                "system_exit_during_login": False,
                "system_exit_code": None,
                "port_type": "str",
                "error_type": "",
            },
            {
                "login_style": "positional-int-port",
                "status": "login_failed",
                "login_returned": False,
                "system_exit_during_login": False,
                "system_exit_code": None,
                "port_type": "int",
                "error_type": "login_failed",
            },
            {
                "login_style": "keyword-str-port",
                "status": "login_failed",
                "login_returned": False,
                "system_exit_during_login": False,
                "system_exit_code": None,
                "port_type": "str",
                "error_type": "login_failed",
            },
            {
                "login_style": "keyword-int-port",
                "status": "login_failed",
                "login_returned": False,
                "system_exit_during_login": False,
                "system_exit_code": None,
                "port_type": "int",
                "error_type": "login_failed",
            },
        ]
        run_mock.return_value = mock.Mock(
            stdout='{"status":"success","login_style":"keyword-int-port","port_type":"int","login_returned":true,"system_exit_during_login":false,"system_exit_code":null,"after_login_marker_reached":true}\n',
            stderr="",
            returncode=0,
        )
        payload = login_check_module.run_login_style_differential()
        self.assertEqual(len(payload["helper_styles"]), 4)
        self.assertEqual(payload["diagnosis"], "positional_style_success")


if __name__ == "__main__":
    unittest.main()
