# -*- coding: utf-8 -*-
"""Smoke test the configured AI report model API without printing secrets."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ai.model_client import ModelClient
from config.settings import AIReportConfig


def _api_url(path: str) -> str:
    base = AIReportConfig.BASE_URL.rstrip("/")
    if base.endswith("/chat/completions"):
        base = base.rsplit("/v1/chat/completions", 1)[0]
    if base.endswith("/v1"):
        return f"{base}{path}"
    return f"{base}/v1{path}"


def list_models() -> int:
    if not AIReportConfig.API_KEY or not AIReportConfig.BASE_URL:
        print("Set AI_MODEL_API_KEY and AI_MODEL_BASE_URL first.")
        return 2
    request = urllib.request.Request(
        _api_url("/models"),
        headers={"Authorization": f"Bearer {AIReportConfig.API_KEY}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        print(f"List models failed: HTTP {e.code}")
        print(body)
        return 1
    except Exception as e:
        print(f"List models failed: {e}")
        return 1

    models = data.get("data", data)
    if isinstance(models, list):
        for item in models[:80]:
            if isinstance(item, dict):
                print(item.get("id") or item.get("model") or item)
            else:
                print(item)
        return 0
    print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
    return 0


def main() -> int:
    if "--models" in sys.argv:
        return list_models()

    client = ModelClient()
    if not client.enabled():
        print("AI API is not configured. Set AI_MODEL_API_KEY, AI_MODEL_BASE_URL, AI_MODEL_NAME.")
        return 2

    payload = {
        "task": "smoke_test",
        "facts": {"auction_pct": -0.17, "prev_pct": 7.26, "body_pct": -0.98},
        "output_schema": ["scenario_label", "direction", "confidence", "evidence", "watch_points", "invalid_if", "report_text"],
    }
    result = client.complete_json(
        system_prompt=(
            "Return a compact JSON object with keys scenario_label, direction, "
            "confidence, evidence, watch_points, invalid_if, report_text. "
            "Do not include markdown. confidence must be a number between 0 and 1, "
            "not a word. Use Simplified Chinese text."
        ),
        user_payload=payload,
    )
    if not result:
        print("AI API call failed or returned non-JSON content.")
        if client.last_status:
            print(f"HTTP status: {client.last_status}")
        if client.last_error:
            print(f"Error: {client.last_error}")
        if client.last_body_preview:
            print("Response preview:")
            print(client.last_body_preview)
        print("\nTry listing models:")
        print(r"C:\Users\40857\.conda\envs\amazing\python.exe scripts\test_ai_api.py --models")
        return 1

    safe = {k: result.get(k) for k in ("scenario_label", "direction", "confidence", "report_text")}
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
