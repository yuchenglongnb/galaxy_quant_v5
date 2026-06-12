# -*- coding: utf-8 -*-
"""Simple stdout/stderr tee logging for command runners."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import TextIO

from utils.encoding import configure_utf8_console


class TeeStream:
    """Mirror writes to the original console stream and a UTF-8 log file."""

    def __init__(self, console: TextIO, log_file: TextIO):
        self.console = console
        self.log_file = log_file
        self.encoding = getattr(console, "encoding", None) or "utf-8"

    def write(self, data: str) -> int:
        self.console.write(data)
        self.log_file.write(data)
        return len(data)

    def flush(self) -> None:
        self.console.flush()
        self.log_file.flush()

    def isatty(self) -> bool:
        return bool(getattr(self.console, "isatty", lambda: False)())

    def fileno(self) -> int:
        return self.console.fileno()


class RunnerLogSession:
    """Context-style log session used by BaseRunner."""

    def __init__(self, runner_name: str, log_dir: str = "logs"):
        self.runner_name = runner_name
        self.log_dir = os.path.join(log_dir, self._category_for(runner_name))
        self.log_path = None
        self._file = None
        self._stdout = None
        self._stderr = None

    @staticmethod
    def _category_for(runner_name: str) -> str:
        if runner_name == "SyncRunner":
            return "sync"
        if runner_name in {"AuctionRunner", "ReviewRunner"}:
            return "reports"
        if runner_name == "MonitorRunner":
            return "monitor"
        return "other"

    def start(self) -> str:
        configure_utf8_console()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir = self._log_dir_for_timestamp(timestamp)
        os.makedirs(log_dir, exist_ok=True)
        self.log_path = os.path.join(log_dir, f"{timestamp}_{self.runner_name}.log")
        self._file = open(self.log_path, "a", encoding="utf-8", buffering=1)
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        sys.stdout = TeeStream(sys.stdout, self._file)
        sys.stderr = TeeStream(sys.stderr, self._file)
        print(f"[log] 输出日志: {os.path.abspath(self.log_path)}")
        return self.log_path

    def _log_dir_for_timestamp(self, timestamp: str) -> str:
        if os.path.basename(self.log_dir) != "reports":
            return self.log_dir
        year = timestamp[0:4]
        month = timestamp[4:6]
        day = timestamp[6:8]
        return os.path.join(self.log_dir, year, month, day)

    def stop(self) -> None:
        if self._file is None:
            return
        try:
            print(f"[log] 日志已保存: {os.path.abspath(self.log_path)}")
        finally:
            sys.stdout = self._stdout
            sys.stderr = self._stderr
            self._file.close()
            self._file = None
