import tempfile
import unittest
from pathlib import Path
from unittest import mock

import scripts.probe_index_min1_query as probe_module


class IndexMin1ProbeTest(unittest.TestCase):
    def test_build_query_window_marks_current_effective_scope(self):
        window = probe_module.build_query_window(20260604)
        self.assertEqual(window["start"], "20260604 09:30:00")
        self.assertEqual(window["end"], "20260604 10:00:00")
        self.assertEqual(window["period"], "min1")
        self.assertIn("full_day", window["query_window_effective"])

    def test_classify_login_failed_from_tgw_error(self):
        error = "CheckLogonLegal server_vip is empty or over kIPMaxLen\nlogin fail"
        self.assertEqual(probe_module.classify_error(error), "login_failed")
        self.assertEqual(probe_module.sanitize_text(error), "login_failed: tgw_login_validation_failed")

    def test_same_process_mode_does_not_call_subprocess(self):
        with mock.patch.object(probe_module, "_probe_same_process", return_value={"status": "success"}) as same_mock:
            with mock.patch.object(probe_module, "_run_worker_subprocess") as sub_mock:
                results = probe_module.run_probe(20260604, ["000001.SH"], 120, "same-process")
        self.assertEqual(results[0]["status"], "success")
        same_mock.assert_called_once()
        sub_mock.assert_not_called()

    def test_subprocess_timeout_does_not_block_other_codes(self):
        with mock.patch.object(probe_module.subprocess, "run", side_effect=subprocess_timeout_side_effect):
            first = probe_module._run_worker_subprocess(20260604, "000001.SH", timeout_sec=1)
            second = probe_module._run_worker_subprocess(20260604, "000688.SH", timeout_sec=1)
        self.assertIn(first["status"], {"query_timeout", "bootstrap_timeout"})
        self.assertIn(second["status"], {"query_timeout", "bootstrap_timeout"})

    def test_write_outputs_generates_json_and_markdown_without_sensitive_fields(self):
        same_process_results = [
            {
                "original_code": "000001.SH",
                "normalized_code": "000001.SH",
                "query_code": "000001.SH",
                "market": "SH",
                "symbol": "000001",
                "date": "20260604",
                "probe_mode": "same-process",
                "status": "bootstrap_failed",
                "worker_bootstrap_status": "config_missing",
                "stage": "load_config",
                "elapsed_sec": 0.1,
                "row_count": 0,
                "first_trade_time": "",
                "last_trade_time": "",
                "error_type": "bootstrap_failed",
                "error": "config_missing",
            }
        ]
        subprocess_results = [
            {
                "original_code": "000001.SH",
                "normalized_code": "000001.SH",
                "query_code": "000001.SH",
                "market": "SH",
                "symbol": "000001",
                "date": "20260604",
                "probe_mode": "subprocess",
                "status": "login_failed",
                "worker_bootstrap_status": "login_failed",
                "stage": "login",
                "elapsed_sec": 0.2,
                "row_count": 0,
                "first_trade_time": "",
                "last_trade_time": "",
                "error_type": "login_failed",
                "error": "login_failed: tgw_init_failed",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            temp_eval_dir = Path(tmp)
            with mock.patch.object(probe_module, "EVAL_DIR", temp_eval_dir):
                json_path, md_path = probe_module.write_outputs(
                    20260604,
                    20,
                    probe_module.build_query_window(20260604),
                    same_process_results,
                    subprocess_results,
                    "both",
                )
                self.assertTrue(json_path.exists())
                self.assertTrue(md_path.exists())
                payload = json_path.read_text(encoding="utf-8")
                self.assertNotIn("server_vip", payload.lower())
                self.assertNotIn("password", payload.lower())

    def test_diagnosis_matrix_subprocess_bootstrap_issue(self):
        same_results = [{"status": "success"}]
        subprocess_results = [{"status": "login_failed"}]
        self.assertEqual(
            probe_module.build_diagnosis_matrix(same_results, subprocess_results),
            "subprocess_bootstrap_issue",
        )

    @mock.patch.object(
        probe_module,
        "bootstrap_market_data",
        side_effect=probe_module.AmazingLoginError("bootstrap_failed", "load_config", "config_missing", "config_missing"),
    )
    def test_same_process_probe_returns_bootstrap_failed_when_config_missing(self, _bootstrap_mock):
        result = probe_module._probe_same_process(20260604, "000001.SH")
        self.assertEqual(result["status"], "bootstrap_failed")
        self.assertEqual(result["worker_bootstrap_status"], "config_missing")
        self.assertEqual(result["stage"], "load_config")

    @mock.patch.object(
        probe_module,
        "bootstrap_market_data",
        side_effect=probe_module.AmazingLoginError("bootstrap_failed", "load_config", "config_missing", "config_missing"),
    )
    def test_subprocess_worker_returns_bootstrap_failed_when_config_missing(self, _bootstrap_mock):
        result = probe_module._probe_worker({"date": 20260604, "code": "000001.SH"})
        self.assertEqual(result["status"], "bootstrap_failed")
        self.assertEqual(result["worker_bootstrap_status"], "config_missing")
        self.assertEqual(result["stage"], "load_config")

    def test_run_probe_same_process_always_returns_one_result_per_code(self):
        with mock.patch.object(probe_module, "_probe_same_process", side_effect=RuntimeError("boom")):
            results = probe_module.run_probe(20260604, ["000001.SH", "000688.SH", "399006.SZ"], 120, "same-process")
        self.assertEqual(len(results), 3)
        self.assertTrue(all(row["status"] == "unknown_failed" for row in results))

    def test_worker_result_file_fallback_preserves_structured_bootstrap_failure(self):
        fake_result = {
            "query_code": "000001.SH",
            "status": "bootstrap_failed",
            "worker_bootstrap_status": "config_missing",
            "stage": "load_config",
            "row_count": 0,
            "first_trade_time": "",
            "last_trade_time": "",
            "error_type": "config_missing",
            "error": "config_missing",
        }
        completed = mock.Mock(stdout="", stderr="", returncode=0)

        def run_side_effect(*args, **kwargs):
            result_path = args[0][-1]
            Path(result_path).write_text(__import__("json").dumps(fake_result), encoding="utf-8")
            return completed

        with mock.patch.object(probe_module.subprocess, "run", side_effect=run_side_effect):
            result = probe_module._run_worker_subprocess(20260604, "000001.SH", timeout_sec=1)
        self.assertEqual(result["status"], "bootstrap_failed")
        self.assertEqual(result["stage"], "load_config")

    def test_classify_timeout_stage_from_login_start(self):
        status, stage = probe_module.classify_timeout_stage("login_start")
        self.assertEqual(status, "login_timeout")
        self.assertEqual(stage, "login")

    def test_classify_timeout_stage_from_query_start(self):
        status, stage = probe_module.classify_timeout_stage("query_start")
        self.assertEqual(status, "query_timeout")
        self.assertEqual(stage, "query")


def subprocess_timeout_side_effect(*args, **kwargs):
    raise probe_module.subprocess.TimeoutExpired(cmd=kwargs.get("args", []), timeout=kwargs.get("timeout", 1))


if __name__ == "__main__":
    unittest.main()
