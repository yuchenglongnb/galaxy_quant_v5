import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import scripts.probe_amazingdata_query_modes as probe_module


class AmazingQueryModeProbeTest(unittest.TestCase):
    def test_build_query_cases_contains_four_expected_cases(self):
        cases = probe_module.build_query_cases(20260615, "600519.SH", "000001.SH")
        self.assertEqual([row["case"] for row in cases], list(probe_module.DATA_CASES))

    def test_implicit_query_diagnosis_when_explicit_strict_fails(self):
        summary = probe_module.summarize_results(
            [
                {"login_mode": "implicit_query", "status": "success"},
                {"login_mode": "explicit_login_continue", "status": "success"},
                {"login_mode": "explicit_login_strict", "status": "login_failed"},
            ]
        )
        self.assertEqual(summary["diagnosis"], "implicit_query_works_explicit_login_path_fails")

    def test_run_probe_filters_selected_cases(self):
        fake_result = {
            "login_mode": "implicit_query",
            "query_case": "stock_day",
            "status": "success",
        }
        with mock.patch.object(probe_module, "run_single_query", return_value=fake_result) as run_mock:
            payload = probe_module.run_probe(
                20260615,
                "600519.SH",
                "000001.SH",
                ["implicit_query"],
                selected_cases=["stock_day"],
            )
        self.assertEqual(payload["scope"]["cases"], ["stock_day"])
        run_mock.assert_called_once()

    def test_run_single_query_returns_login_failed_on_strict_explicit_mode(self):
        query_case = {
            "case": "index_day",
            "code": "000001.SH",
            "security_type": "index",
            "period_name": "day",
            "query_window_effective": "single_day_query_kline_call",
        }
        with mock.patch.object(
            probe_module,
            "create_market_with_explicit_login",
            side_effect=probe_module.AmazingLoginError("login_failed", "login", "system_exit_during_login", "system_exit_during_login:0"),
        ):
            result = probe_module.run_single_query(20260615, "explicit_login_strict", query_case)
        self.assertEqual(result["status"], "login_failed")
        self.assertEqual(result["stage"], "login")
        self.assertEqual(result["login_exception_type"], "system_exit_during_login")

    def test_run_single_query_marks_query_failed_after_continue_mode_login_exception(self):
        query_case = {
            "case": "stock_min1",
            "code": "600519.SH",
            "security_type": "stock",
            "period_name": "min1",
            "query_window_effective": "full_day_query_kline_call_in_current_implementation",
        }
        bootstrap = {
            "ad": object(),
            "config": {"ready": True},
            "market": object(),
            "login_returned": False,
            "login_exception_type": "system_exit_during_login",
            "login_exception_message": "system_exit_during_login:0",
            "execution_model": "explicit_login_marketdata",
        }
        with mock.patch.object(probe_module, "create_market_with_explicit_login", return_value=bootstrap):
            with mock.patch.object(probe_module, "query_kline_frame", side_effect=RuntimeError("query boom")):
                result = probe_module.run_single_query(20260615, "explicit_login_continue", query_case)
        self.assertEqual(result["status"], "query_failed")
        self.assertEqual(result["stage"], "query")
        self.assertEqual(result["login_exception_type"], "system_exit_during_login")

    def test_write_outputs_includes_diagnosis(self):
        payload = {
            "date": "20260615",
            "stock_code": "600519.SH",
            "index_code": "000001.SH",
            "scope": {"login_modes": list(probe_module.LOGIN_MODE_CHOICES)},
            "results": [
                {
                    "login_mode": "implicit_query",
                    "query_case": "stock_day",
                    "code": "600519.SH",
                    "status": "success",
                    "stage": "query",
                    "login_returned": None,
                    "login_exception_type": "",
                    "row_count": 1,
                    "elapsed_sec": 1.2,
                },
                {
                    "login_mode": "explicit_login_strict",
                    "query_case": "stock_day",
                    "code": "600519.SH",
                    "status": "login_failed",
                    "stage": "login",
                    "login_returned": False,
                    "login_exception_type": "system_exit_during_login",
                    "row_count": 0,
                    "elapsed_sec": 1.5,
                },
            ],
        }
        with TemporaryDirectory() as tmp:
            with mock.patch.object(probe_module, "EVAL_DIR", Path(tmp)):
                json_path, md_path = probe_module.write_outputs(payload)
                self.assertTrue(json_path.exists())
                self.assertTrue(md_path.exists())
                self.assertIn("implicit_query_works_explicit_login_path_fails", md_path.read_text(encoding="utf-8"))

    def test_run_single_query_subprocess_timeout_returns_structured_timeout(self):
        with mock.patch.object(probe_module.subprocess, "run", side_effect=probe_module.subprocess.TimeoutExpired(cmd=[], timeout=3)):
            result = probe_module.run_single_query_subprocess(
                target_date=20260615,
                login_mode="implicit_query",
                query_case_name="stock_day",
                stock_code="600519.SH",
                index_code="000001.SH",
                timeout_sec=3,
            )
        self.assertEqual(result["status"], "query_timeout")
        self.assertEqual(result["error_type"], "case_timeout")


if __name__ == "__main__":
    unittest.main()
