# -*- coding: utf-8 -*-
"""Trace AI report interpretation inputs and outputs for review."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict

from config.settings import AIReportConfig


class AITraceLogger:
    """Append JSONL traces for AI report interpretation."""

    @classmethod
    def log(cls, event: Dict[str, Any]) -> None:
        try:
            os.makedirs(AIReportConfig.TRACE_DIR, exist_ok=True)
            day = datetime.now().strftime("%Y%m%d")
            path = os.path.join(AIReportConfig.TRACE_DIR, f"{day}_auction_signal.jsonl")
            event = {"ts": datetime.now().isoformat(timespec="seconds"), **event}
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            return
