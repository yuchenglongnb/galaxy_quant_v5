# -*- coding: utf-8 -*-
"""Small OpenAI-compatible chat-completions client for report interpretation."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from config.settings import AIReportConfig


class ModelClient:
    """Call an OpenAI-compatible model API when configured."""

    def __init__(self):
        self.api_key = AIReportConfig.API_KEY
        self.base_url = AIReportConfig.BASE_URL.rstrip("/")
        self.model = AIReportConfig.MODEL
        self.timeout = AIReportConfig.TIMEOUT_SECONDS
        self.last_error = ""
        self.last_status = None
        self.last_body_preview = ""

    def enabled(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def complete_json(self, *, system_prompt: str, user_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.enabled():
            return None

        url = self._chat_url()
        body = {
            "model": self.model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        }
        raw = self._post_json(url, body)
        if raw is None and "response_format" in body and self.last_status in {400, 422}:
            body = dict(body)
            body.pop("response_format", None)
            raw = self._post_json(url, body)
        if raw is None:
            return None

        content = (
            raw.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return self._parse_json_content(content)

    def _chat_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        if self.base_url.endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/v1/chat/completions"

    def _post_json(self, url: str, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self.last_error = ""
        self.last_status = None
        self.last_body_preview = ""
        request = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                self.last_status = resp.status
                text = resp.read().decode("utf-8", errors="replace")
                self.last_body_preview = text[:500]
                return json.loads(text)
        except urllib.error.HTTPError as e:
            self.last_status = e.code
            try:
                self.last_body_preview = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                self.last_body_preview = ""
            self.last_error = str(e)
            return None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            self.last_error = str(e)
            return None

    @staticmethod
    def _parse_json_content(content: str) -> Optional[Dict[str, Any]]:
        if not content:
            return None
        text = content.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
        if fenced:
            text = fenced.group(1)
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.S)
            if not match:
                return None
            try:
                data = json.loads(match.group(0))
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None
