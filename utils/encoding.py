# -*- coding: utf-8 -*-
"""Console encoding helpers."""

from __future__ import annotations

import os
import sys


def configure_utf8_console() -> None:
    """Prefer UTF-8 for console output on Windows and other terminals."""
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
