import json
import tempfile
import unittest
from pathlib import Path

import scripts.probe_index_min1_query as probe_module


class ProbeStageHeartbeatTest(unittest.TestCase):
    def test_emit_and_read_last_heartbeat(self):
        started = 100.0
        with tempfile.TemporaryDirectory() as tmp:
            heartbeat_path = Path(tmp) / "heartbeat.jsonl"
            probe_module.emit_heartbeat(heartbeat_path, "login_start", started, {"code": "000001.SH"})
            probe_module.emit_heartbeat(heartbeat_path, "query_start", started, {"code": "000001.SH"})
            last = probe_module.read_last_heartbeat(heartbeat_path)
        self.assertEqual(last["stage"], "query_start")
        self.assertEqual(last["code"], "000001.SH")

    def test_read_last_heartbeat_returns_empty_for_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            heartbeat_path = Path(tmp) / "missing.jsonl"
            self.assertEqual(probe_module.read_last_heartbeat(heartbeat_path), {})

    def test_heartbeat_file_is_jsonl(self):
        started = 100.0
        with tempfile.TemporaryDirectory() as tmp:
            heartbeat_path = Path(tmp) / "heartbeat.jsonl"
            probe_module.emit_heartbeat(heartbeat_path, "load_config_start", started)
            lines = heartbeat_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        payload = json.loads(lines[0])
        self.assertEqual(payload["stage"], "load_config_start")


if __name__ == "__main__":
    unittest.main()
